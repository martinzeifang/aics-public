"""AI Act Compliance Module API — vollständige CRUD + Reifegrad + Repo-Auto-Answer + Reports."""

from flask import current_app, Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from pathlib import Path
from typing import Any, Dict, List
import tempfile

from server.api.workspace_tmp import workspace_tmpdir
from server.api._common import require_projekt

from ai_act.db import (
    list_projekte,
    save_projekt,
    load_projekt,
    update_projekt_meta,
    delete_projekt as db_delete_projekt,
    save_bewertung as db_save_bewertung,
    load_bewertungen,
    upsert_overlay_check,
    load_overlay_checks,
)

from ai_act.requirements import (
    AI_ACT_REQUIREMENTS,
    KAPITEL,
    BEWERTUNG_SKALA,
    berechne_reifegrad,
)

# Pro-Projekt-Repository-Konfiguration (#862): gemeinsame Helfer.
from shared.vcs_repo_config import vcs_token, public_vcs, sanitize_vcs, resolve_repo


# Kapitel-Metadaten für Hilfe-Dialog (UI-Annotation für die Kurz-Codes HR/GOV/DATA/OPS)
_KAPITEL_INFO = {
    'HR':   {'titel': 'Human Resources & Schulung',     'untertitel': 'Personalbezogene Pflichten', 'farbe': '#1565c0', 'soft': '#e3f2fd', 'beschreibung': 'AI-Literacy, Schulungen, Rollen und Verantwortlichkeiten beim Einsatz von KI-Systemen.'},
    'GOV':  {'titel': 'Governance & Risk Management',   'untertitel': 'Steuerung & Aufsicht',        'farbe': '#4a148c', 'soft': '#f3e5f5', 'beschreibung': 'Risikomanagement-System, Konformitätsbewertung, technische Dokumentation, menschliche Aufsicht.'},
    'DATA': {'titel': 'Datenqualität & Transparenz',     'untertitel': 'Trainings- und Eingabedaten', 'farbe': '#00695c', 'soft': '#e0f2f1', 'beschreibung': 'Anforderungen an Trainings-, Validierungs- und Testdaten, Bias-Mitigation, Transparenzpflichten.'},
    'OPS':  {'titel': 'Betrieb & Cybersicherheit',       'untertitel': 'Lebenszyklus-Management',     'farbe': '#bf360c', 'soft': '#fbe9e7', 'beschreibung': 'Logging, Monitoring, Robustheit, Cybersicherheit, Vorfallsmeldungen, Post-Market-Monitoring.'},
}

aiact_bp = Blueprint('aiact', __name__, url_prefix='/api/aiact')

DB_PATH = Path('data/db/ai_act.sqlite')

# OWASP LLM Top 10 → AI Act Requirement Mapping (statisch aus ai_act/owasp_llm_top10.py)
try:
    from ai_act.owasp_llm_top10 import OWASP_LLM_TOP10
    # Konvertiere zu {LLM-ID: [requirement_ids]} Mapping
    OWASP_LLM_TOP10_MAPPING = {
        item['id']: item.get('maps_to', [])
        for item in OWASP_LLM_TOP10
    }
    # Index für Lookup pro Requirement-ID
    OWASP_BY_REQ: Dict[str, List[Dict[str, Any]]] = {}
    for item in OWASP_LLM_TOP10:
        for req_id in item.get('maps_to', []):
            OWASP_BY_REQ.setdefault(req_id, []).append({
                'id': item['id'],
                'title': item['title'],
                'ref': item.get('ref', ''),
            })
except Exception:
    OWASP_LLM_TOP10 = []
    OWASP_LLM_TOP10_MAPPING = {}
    OWASP_BY_REQ = {}


# ============================================================
# Hilfsfunktionen
# ============================================================

def _serialize_projekt(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': p.get('name'),
        'name': p.get('name', ''),
        'organisation': p.get('organisation', ''),
        'company': p.get('organisation', ''),
        'produkt': p.get('produkt', ''),
        'beschreibung': p.get('beschreibung', ''),
        'description': p.get('beschreibung', ''),
        'meta': p.get('meta_json', '{}'),
        'created_at': p.get('created_at'),
        'updated_at': p.get('updated_at'),
    }


def _build_anforderungen_response(projekt_name: str) -> List[Dict[str, Any]]:
    """Anforderungen mit Bewertungen pro Projekt + OWASP-LLM-Mapping."""
    bewertungen = load_bewertungen(DB_PATH, projekt_name)

    result = []
    for req in AI_ACT_REQUIREMENTS:
        rid = req.get('id')
        b = bewertungen.get(rid, {})
        score = b.get('bewertung', 0)

        # OWASP-LLM-Top-10-Risiken, die zu dieser Anforderung mappen
        owasp_links = OWASP_BY_REQ.get(rid, [])

        result.append({
            'id': rid,
            'kapitel': req.get('kapitel', ''),
            'titel': req.get('titel', ''),
            'title': req.get('titel', ''),
            'beschreibung': req.get('beschreibung', ''),
            'description': req.get('beschreibung', ''),
            'hinweise': req.get('hinweise', ''),
            'guidance': req.get('guidance', ''),
            'evidence': req.get('evidence', []),
            'rubric': req.get('rubric', {}),
            'ref': req.get('ref', ''),
            'gewichtung': req.get('gewichtung', 1),
            'owasp_llm': owasp_links,
            # Bewertung
            'bewertung': score,
            'score': score,
            'kommentar': b.get('kommentar', ''),
            'notes': b.get('kommentar', ''),
            'massnahme': b.get('massnahme', ''),
            'verantwortlich': b.get('verantwortlich', ''),
            'zieldatum': b.get('zieldatum', ''),
            'updated_at': b.get('updated_at'),
            'status': 'complete' if score >= 4 else 'partial' if score >= 2 else 'pending',
        })
    return result


def _complete_requirement_if_issue_resolved(projekt_name: str, req_id: str) -> bool:
    """Setzt eine Anforderung auf "vollständig erfüllt" (Score 5 + Auto-Notiz),
    falls ein verknüpftes Issue gelöst ist und die Anforderung bereits bewertet
    wurde. Liest ausschließlich den persistierten Issue-Status (kein Netzwerk).

    Rückgabe: True, wenn die Anforderung jetzt automatisch vervollständigt wurde.
    """
    from shared.issue_links import list_links
    from shared.issue_completion import (
        COMPLETION_SCORE, first_resolved_link, completion_note,
        already_completed, is_assessed, merge_completion_note,
    )

    links = list_links(DB_PATH, projekt_name=projekt_name,
                       object_kind='requirement', object_id=req_id)
    resolved = first_resolved_link(links)
    if resolved is None:
        return False
    existing = load_bewertungen(DB_PATH, projekt_name).get(req_id, {})
    try:
        prev_score = int(existing.get('bewertung') or 0)
    except (TypeError, ValueError):
        prev_score = 0
    kommentar = str(existing.get('kommentar') or '')
    if prev_score >= COMPLETION_SCORE and already_completed(kommentar):
        return False
    if not is_assessed(prev_score, kommentar):
        return False
    note = completion_note(resolved, prev_score)
    # AI-Act-Bewertung kennt nur bewertung/kommentar/massnahme.
    db_save_bewertung(
        DB_PATH,
        projekt_name=projekt_name,
        anforderung_id=req_id,
        bewertung=COMPLETION_SCORE,
        kommentar=merge_completion_note(kommentar, note),
        massnahme=str(existing.get('massnahme') or ''),
    )
    return True


def _complete_all_resolved_requirements(projekt_name: str) -> int:
    """Vervollständigungs-Pass über alle verknüpften Anforderungen eines
    Projekts. Rückgabe: Anzahl automatisch vervollständigter Anforderungen."""
    from shared.issue_links import list_project_links
    from shared.issue_feedback import group_links_by_object

    links = list_project_links(DB_PATH, projekt_name=projekt_name,
                               object_kind='requirement')
    groups = group_links_by_object(links)
    count = 0
    for req_id in groups:
        if _complete_requirement_if_issue_resolved(projekt_name, req_id):
            count += 1
    return count


# ============================================================
# Projekte
# ============================================================

@aiact_bp.get('/projekte')
@jwt_required()
def get_projekte():
    """Liste aller AI-Act-Projekte."""
    try:
        names = list_projekte(DB_PATH)
        result = []
        for n in names:
            p = load_projekt(DB_PATH, n)
            if p:
                result.append(_serialize_projekt(p))
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.get('/projekte/<projekt_name>')
@jwt_required()
def get_projekt(projekt_name: str):
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return {'error': 'Projekt nicht gefunden'}, 404
        return _serialize_projekt(p), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.post('/projekte')
@jwt_required()
def create_projekt():
    try:
        data = request.json or {}
        name = (data.get('name') or '').strip()
        if not name:
            return {'error': 'Feld "name" ist Pflicht'}, 400
        if load_projekt(DB_PATH, name):
            return {'error': 'Projekt existiert bereits'}, 409

        save_projekt(
            DB_PATH,
            name=name,
            organisation=data.get('organisation', '') or data.get('company', ''),
            produkt=data.get('produkt', ''),
            beschreibung=data.get('beschreibung', '') or data.get('description', ''),
        )
        p = load_projekt(DB_PATH, name)
        return _serialize_projekt(p), 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.put('/projekte/<projekt_name>')
@jwt_required()
def update_projekt(projekt_name: str):
    try:
        existing = load_projekt(DB_PATH, projekt_name)
        if not existing:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        save_projekt(
            DB_PATH,
            name=projekt_name,
            organisation=data.get('organisation', existing.get('organisation', '')),
            produkt=data.get('produkt', existing.get('produkt', '')),
            beschreibung=data.get('beschreibung', existing.get('beschreibung', '')),
        )
        return _serialize_projekt(load_projekt(DB_PATH, projekt_name)), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.delete('/projekte/<projekt_name>')
@jwt_required()
def delete_projekt(projekt_name: str):
    try:
        db_delete_projekt(DB_PATH, projekt_name)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Anforderungen + Bewertungen
# ============================================================

@aiact_bp.get('/projekte/<projekt_name>/anforderungen')
@jwt_required()
def get_anforderungen(projekt_name: str):
    """Anforderungen mit Bewertung + OWASP-LLM-Top-10-Mapping."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        return _build_anforderungen_response(projekt_name), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.post('/projekte/<projekt_name>/bewertungen')
@jwt_required()
def save_bewertung(projekt_name: str):
    """Einzelne Bewertung speichern."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        anforderung_id = data.get('anforderung_id') or data.get('id')
        if not anforderung_id:
            return {'error': 'Feld "anforderung_id" ist Pflicht'}, 400
        bewertung = int(data.get('bewertung', data.get('score', 0)))
        if bewertung < 0 or bewertung > 5:
            return {'error': 'bewertung muss 0-5 sein'}, 400

        db_save_bewertung(
            DB_PATH,
            projekt_name=projekt_name,
            anforderung_id=anforderung_id,
            bewertung=bewertung,
            kommentar=data.get('kommentar', '') or data.get('notes', ''),
            massnahme=data.get('massnahme', ''),
        )
        # Aufgeschobene Vervollständigung bei bereits gelöstem Issue (#833).
        if _complete_requirement_if_issue_resolved(projekt_name, anforderung_id):
            bewertung = 5
        return {'anforderung_id': anforderung_id, 'bewertung': bewertung, 'updated': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.get('/projekte/<projekt_name>/reifegrad')
@jwt_required()
def get_reifegrad(projekt_name: str):
    """Gewichteter Reifegrad pro Kapitel + gesamt."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        bewertungen = load_bewertungen(DB_PATH, projekt_name)
        # bewertungen: {req_id: {bewertung, kommentar, ...}} → {req_id: bewertung}
        scores = {k: int(v.get('bewertung', 0)) for k, v in bewertungen.items()}
        return berechne_reifegrad(scores), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# OWASP LLM Top 10 Mapping
# ============================================================

@aiact_bp.get('/constants')
@jwt_required()
def get_constants():
    return {
        'kapitel': _KAPITEL_INFO,
        'bewertung_skala': BEWERTUNG_SKALA,
    }, 200


@aiact_bp.get('/owasp-llm')
@jwt_required()
def get_owasp_llm_mapping():
    """OWASP LLM Top 10 → AI-Act Anforderungen Mapping (statisch)."""
    return {
        'top10': OWASP_LLM_TOP10,
        'mapping': OWASP_LLM_TOP10_MAPPING,
        'by_requirement': OWASP_BY_REQ,
    }, 200


# ============================================================
# OWASP-LLM-Top-10-Register (#1087, Sprint #21 S17)
# Full-parity zum CRA-OWASP-Panel: Status (0-5) · Auto-Detect · KI-Wizard ·
# Issue-Link (object_kind='owasp_llm', spiegelt CRA-Vuln-Pattern #1041).
# COMPLIANCE: rein additiv — A1-A5 + owasp_llm_top10.maps_to bleiben unberührt.
# ============================================================

@aiact_bp.get('/projekte/<projekt_name>/owasp-llm')
@jwt_required()
def owasp_llm_list(projekt_name: str):
    """Register-Items inkl. gespeichertem Status/Kommentar/Evidence + verlinkten Issues."""
    try:
        from ai_act.db import load_owasp_llm_checks
        from ai_act.owasp_llm_register import register_items
        from shared.issue_links import list_links, ensure_tables

        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404

        ensure_tables(DB_PATH)
        saved = load_owasp_llm_checks(DB_PATH, projekt_name)
        out: List[Dict[str, Any]] = []
        for it in register_items():
            lid = it['id']
            row = saved.get(lid, {})
            links = list_links(DB_PATH, projekt_name=projekt_name,
                               object_kind='owasp_llm', object_id=lid)
            out.append({
                **it,
                'status': int(row.get('status', 0) or 0),
                'kommentar': str(row.get('kommentar', '') or ''),
                'evidence': row.get('evidence') or [],
                'issues': [_serialize_link(l) for l in links],
            })
        return {'items': out}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@aiact_bp.post('/projekte/<projekt_name>/owasp-llm/<llm_id>')
@jwt_required()
def owasp_llm_save(projekt_name: str, llm_id: str):
    """Status (0-5) + Kommentar eines LLM-Top-10-Items speichern."""
    try:
        from ai_act.db import upsert_owasp_llm_check, load_owasp_llm_checks
        from ai_act.owasp_llm_register import find_item

        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        if not find_item(llm_id):
            return {'error': 'OWASP-LLM-Item nicht gefunden'}, 404

        data = request.json or {}
        try:
            status = int(data.get('status', 0) or 0)
        except (TypeError, ValueError):
            return {'error': 'status muss 0-5 sein'}, 400
        if status < 0 or status > 5:
            return {'error': 'status muss 0-5 sein'}, 400

        # Bestehende Evidence bewahren, falls keine neue übergeben wird.
        existing = load_owasp_llm_checks(DB_PATH, projekt_name).get(llm_id, {})
        evidence = data.get('evidence')
        if evidence is None:
            evidence = existing.get('evidence') or []

        upsert_owasp_llm_check(
            DB_PATH, projekt_name=projekt_name, llm_id=llm_id,
            status=status, kommentar=str(data.get('kommentar', '') or ''),
            evidence=evidence,
        )
        return {'saved': True, 'id': llm_id, 'status': status}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@aiact_bp.post('/projekte/<projekt_name>/owasp-llm/autodetect')
@jwt_required()
def owasp_llm_autodetect(projekt_name: str):
    """Token-aware Repo-Scan (10 LLM-Heuristiken) + Speichern der Treffer (#1064)."""
    try:
        from ai_act.db import upsert_owasp_llm_check, load_owasp_llm_checks
        from ai_act.owasp_llm_register import autodetect_owasp_llm

        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return {'error': 'Projekt nicht gefunden'}, 404

        data = request.json or {}
        vcs = _project_vcs(p)
        repo = resolve_repo(vcs, data.get('repo'))
        if not repo:
            return {'error': 'Kein Repository für dieses Projekt konfiguriert '
                             '(Repo-Konfig speichern oder repo übergeben)'}, 400
        branch = str(data.get('branch') or vcs.get('branch') or '').strip()
        token = vcs_token(vcs)
        apply = bool(data.get('apply', True))

        try:
            results = autodetect_owasp_llm(repo=repo, branch=branch, token=token)
        except ValueError as e:
            return {'error': str(e)}, 400
        except Exception as e:
            current_app.logger.warning('owasp-llm autodetect failed (%s): %s', repo, e)
            return {'error': _repo_fetch_hint(e)}, 502

        existing = load_owasp_llm_checks(DB_PATH, projekt_name)
        out = []
        applied = 0
        for r in results:
            # Nur positive Treffer schreiben; bestehende (manuelle) Bewertungen
            # nur anheben, nie verschlechtern (parity zur CRA-Idempotenz).
            cur = int(existing.get(r.llm_id, {}).get('status', 0) or 0)
            new_status = max(cur, r.status) if r.matched else cur
            if apply and r.matched and new_status != cur:
                upsert_owasp_llm_check(
                    DB_PATH, projekt_name=projekt_name, llm_id=r.llm_id,
                    status=new_status,
                    kommentar=r.kommentar or existing.get(r.llm_id, {}).get('kommentar', ''),
                    evidence=r.evidence or existing.get(r.llm_id, {}).get('evidence') or [],
                )
                applied += 1
            out.append({
                'id': r.llm_id, 'matched': r.matched, 'status': new_status,
                'detected_status': r.status, 'kommentar': r.kommentar,
                'evidence': r.evidence,
            })
        return {'results': out, 'applied': applied,
                'summary': {'matched': sum(1 for r in results if r.matched),
                            'total': len(results)}}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@aiact_bp.get('/projekte/<projekt_name>/owasp-llm/wizard/prompt')
@jwt_required()
def owasp_llm_wizard_prompt(projekt_name: str):
    """KI-Prompt zum Bewerten aller OWASP-LLM-Top-10-Items."""
    try:
        from ai_act.db import load_system_doku, load_owasp_llm_checks
        from ai_act.owasp_llm_register import build_owasp_llm_prompt

        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return {'error': 'Projekt nicht gefunden'}, 404
        sd = load_system_doku(DB_PATH, projekt_name) or {}
        checks = load_owasp_llm_checks(DB_PATH, projekt_name)
        prompt = build_owasp_llm_prompt(p, sd, checks)
        return {'prompt': prompt}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@aiact_bp.post('/projekte/<projekt_name>/owasp-llm/wizard/parse')
@jwt_required()
def owasp_llm_wizard_parse(projekt_name: str):
    """KI-Antwort parsen und (optional) als Status/Kommentar übernehmen."""
    try:
        from ai_act.db import upsert_owasp_llm_check, load_owasp_llm_checks
        from ai_act.owasp_llm_register import parse_owasp_llm_response

        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        raw = data.get('response') or data.get('raw') or ''
        if not raw:
            return {'error': 'Feld "response" ist Pflicht'}, 400
        apply = bool(data.get('apply', True))

        items = parse_owasp_llm_response(raw)
        if not items:
            return {'error': 'Kein gültiges JSON mit OWASP-LLM-Items erkannt'}, 400

        if apply:
            existing = load_owasp_llm_checks(DB_PATH, projekt_name)
            for it in items:
                upsert_owasp_llm_check(
                    DB_PATH, projekt_name=projekt_name, llm_id=it['id'],
                    status=it['status'], kommentar=it['kommentar'],
                    evidence=existing.get(it['id'], {}).get('evidence') or [],
                )
        return {'items': items, 'saved': apply, 'count': len(items)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


# ── OWASP-LLM-Issue-Link (object_kind='owasp_llm', spiegelt #1041) ──────────

def _owasp_llm_issue_defaults(projekt_name: str, item: Dict[str, Any],
                              check: Dict[str, Any]) -> tuple[str, str]:
    lid = item['id']
    title = f"[AI-Act-OWASP-LLM] {lid} · {item['title']}".strip()
    status = int(check.get('status', 0) or 0)
    maps_to = ', '.join(item.get('maps_to') or []) or '—'
    body = f"""## OWASP-LLM-Top-10: {lid} {item['title']}

**Projekt**: {projekt_name}
**Aktueller Status**: {status}/5
**AI-Act-Mapping**: {maps_to}  (Art. 9 Risikomanagement · Art. 15 Genauigkeit/Robustheit/Cybersicherheit)

### Beobachtung
{check.get('kommentar', '') or '_(noch keine Notizen)_'}

### Referenz
{item.get('ref', '')}

---
_Generiert aus dem AI Compliance Suite AI-Act-Modul (OWASP-LLM-Register · #1087)._
"""
    return title, body


@aiact_bp.get('/projekte/<projekt_name>/owasp-llm/<llm_id>/issues')
@jwt_required()
def owasp_llm_list_issues(projekt_name: str, llm_id: str):
    """Verknüpfte Issues eines OWASP-LLM-Items."""
    try:
        from shared.issue_links import list_links, ensure_tables
        ensure_tables(DB_PATH)
        links = list_links(DB_PATH, projekt_name=projekt_name,
                           object_kind='owasp_llm', object_id=llm_id)
        return [_serialize_link(l) for l in links], 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@aiact_bp.post('/projekte/<projekt_name>/owasp-llm/<llm_id>/issues')
@jwt_required()
def owasp_llm_create_issue(projekt_name: str, llm_id: str):
    """GitHub/GitLab-Issue für ein OWASP-LLM-Item anlegen (#1087, spiegelt #1041)."""
    try:
        from ai_act.db import load_owasp_llm_checks
        from ai_act.owasp_llm_register import find_item

        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        item = find_item(llm_id)
        if not item:
            return {'error': 'OWASP-LLM-Item nicht gefunden'}, 404

        data = request.json or {}
        vcs = _project_vcs(projekt)
        repo = resolve_repo(vcs, data.get('repo'))
        if not repo:
            return {'error': 'Kein Repository für dieses Projekt konfiguriert '
                             '(Repo-Konfig speichern oder repo übergeben)'}, 400
        provider = (data.get('provider') or vcs.get('provider') or 'github').lower()

        check = load_owasp_llm_checks(DB_PATH, projekt_name).get(llm_id, {})
        def_title, def_body = _owasp_llm_issue_defaults(projekt_name, item, check)
        title = data.get('title') or def_title
        body = data.get('body') or def_body

        issue_url = ''
        issue_number = None
        issue_iid = None
        if provider == 'github':
            from vcs.github_issues import create_issue as gh_create
            ci = gh_create(repo=repo, title=title, body=body)
            issue_url, issue_number = ci.url, ci.number
        elif provider == 'gitlab':
            from vcs.gitlab_issues import create_issue as gl_create
            base_url = data.get('gitlab_base_url') or vcs.get('base_url') or 'https://gitlab.com'
            token_env = data.get('gitlab_token_env') or vcs.get('token_env') or 'GITLAB_TOKEN'
            ci = gl_create(base_url=base_url, token_env=token_env, project=repo, title=title, body=body)
            issue_url, issue_iid = ci.url, ci.iid
        else:
            return {'error': f'Unbekannter Provider: {provider}'}, 400

        from shared.issue_links import add_link
        add_link(
            DB_PATH, projekt_name=projekt_name,
            object_kind='owasp_llm', object_id=llm_id,
            provider=provider, repo=repo, url=issue_url,
            issue_number=issue_number, issue_iid=issue_iid, title=title,
        )
        try:
            from shared.audit import audit_event
            audit_event('aiact.owasp_llm_issue.created', module='aiact', details={
                'projekt': projekt_name, 'llm_id': llm_id,
                'provider': provider, 'repo': repo, 'url': issue_url})
        except Exception:
            pass
        return {
            'created': True, 'provider': provider, 'url': issue_url,
            'issue_number': issue_number, 'issue_iid': issue_iid, 'title': title,
        }, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@aiact_bp.post('/projekte/<projekt_name>/owasp-llm/<llm_id>/issues/link')
@jwt_required()
def owasp_llm_link_issue(projekt_name: str, llm_id: str):
    """Bestehendes Issue manuell mit einem OWASP-LLM-Item verknüpfen."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        provider = (data.get('provider') or 'github').lower()
        url = data.get('url') or ''
        repo = data.get('repo') or ''
        if not url:
            return {'error': 'Feld "url" ist Pflicht'}, 400

        if not repo:
            gh_match = re.match(r'https?://github\.com/([^/]+/[^/]+)/issues/\d+', url)
            gl_match = re.match(r'https?://[^/]+/([^/]+/[^/]+)/-/issues/\d+', url)
            if gh_match:
                repo, provider = gh_match.group(1), 'github'
            elif gl_match:
                repo, provider = gl_match.group(1), 'gitlab'

        num_match = re.search(r'/(?:issues|merge_requests)/(\d+)', url)
        number = int(num_match.group(1)) if num_match else None

        from shared.issue_links import add_link
        add_link(
            DB_PATH, projekt_name=projekt_name,
            object_kind='owasp_llm', object_id=llm_id,
            provider=provider, repo=repo, url=url,
            issue_number=number if provider == 'github' else None,
            issue_iid=number if provider == 'gitlab' else None,
            title=data.get('title') or url,
        )
        return {'linked': True, 'url': url, 'number': number, 'provider': provider}, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@aiact_bp.post('/projekte/<projekt_name>/owasp-llm/<llm_id>/issues/sync')
@jwt_required()
def owasp_llm_sync_issues(projekt_name: str, llm_id: str):
    """Status verknüpfter OWASP-LLM-Issues von GitHub aktualisieren."""
    try:
        from shared.issue_links import list_links, update_issue_state
        from shared.issue_sync import sync_github_issue, is_successfully_resolved

        links = list_links(DB_PATH, projekt_name=projekt_name,
                           object_kind='owasp_llm', object_id=llm_id)
        if not links:
            return {'synced': 0, 'links': []}, 200

        synced_count = 0
        results = []
        for li in links:
            try:
                if li.provider == 'github' and li.repo and li.issue_number:
                    synced = sync_github_issue(repo=li.repo, number=li.issue_number)
                    update_issue_state(
                        DB_PATH, link_id=li.id,
                        state=synced.state, state_reason=synced.state_reason or '',
                        title=synced.title or li.title,
                    )
                    synced_count += 1
                    results.append({
                        'id': li.id, 'state': synced.state,
                        'state_reason': synced.state_reason,
                        'resolved': is_successfully_resolved(
                            state=synced.state, state_reason=synced.state_reason or '',
                            labels=getattr(synced, 'labels', []) or []),
                    })
            except Exception as e:
                results.append({'id': li.id, 'error': str(e)})
        return {'synced': synced_count, 'links': results}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@aiact_bp.delete('/projekte/<projekt_name>/owasp-llm/issues/<link_id>')
@jwt_required()
def owasp_llm_unlink_issue(projekt_name: str, link_id: str):
    """Verknüpfung zu einem OWASP-LLM-Issue entfernen (Issue bleibt beim Provider)."""
    try:
        from shared.issue_links import delete_link
        delete_link(DB_PATH, link_id)
        return {'deleted': True, 'link_id': link_id}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


# ============================================================
# Pro-Projekt-Repository-Konfiguration (#862)
# ============================================================

def _repo_fetch_hint(exc: Exception) -> str:
    """Nicht-sensible Fehlerhinweise (Rate-Limit/Token) weiterreichen, sonst generisch (#737)."""
    msg = str(exc)
    if any(k in msg for k in ('Limit', 'limit', 'Token', 'token')):
        return msg[:300]
    return ('Repository-Kontext konnte nicht geladen werden. '
            'Repo, Zugriffsrechte/Token (token_env) prüfen.')


def _project_vcs(projekt: Dict[str, Any]) -> Dict[str, Any]:
    """vcs_publish-Block eines Projekts (aus meta) als Dict zurückgeben."""
    meta = projekt.get('meta') if isinstance(projekt.get('meta'), dict) else {}
    vcs = meta.get('vcs_publish') if isinstance(meta.get('vcs_publish'), dict) else {}
    return vcs


@aiact_bp.get('/projekte/<projekt_name>/repo-config')
@jwt_required()
def get_repo_config(projekt_name: str):
    """Repo-Einstellungen (vcs_publish) eines Projekts lesen."""
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return {'error': 'Projekt nicht gefunden'}, 404
        return {'vcs_publish': public_vcs(_project_vcs(p))}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.put('/projekte/<projekt_name>/repo-config')
@jwt_required()
def put_repo_config(projekt_name: str):
    """Repo-Einstellungen speichern. Ein eingegebener Token-Wert wird
    verschlüsselt at-rest abgelegt (#784), nie im Klartext/Response (#737).
    Teil-Update bewahrt einen bestehenden Token."""
    try:
        existing = load_projekt(DB_PATH, projekt_name)
        if not existing:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        meta = dict(existing.get('meta') or {})
        prev_vcs = meta.get('vcs_publish') if isinstance(meta.get('vcs_publish'), dict) else {}
        vcs = sanitize_vcs(data.get('vcs_publish', data), prev_vcs)
        meta['vcs_publish'] = vcs
        update_projekt_meta(DB_PATH, projekt_name, meta)
        return {'vcs_publish': public_vcs(vcs)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.post('/projekte/<projekt_name>/repo-context')
@jwt_required()
def post_repo_context(projekt_name: str):
    """Repo-Zugriff testen / Kontext abrufen. Body: {repo?: 'owner/repo'|URL}.
    Ohne repo wird die gespeicherte vcs_publish.repo verwendet."""
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        vcs = _project_vcs(p)
        repo = resolve_repo(vcs, data.get('repo'))
        if not repo:
            return {'error': 'Kein Repository angegeben oder gespeichert'}, 400

        from vcs.repo_reader import detect_provider, fetch_repo_context, format_repo_context
        try:
            provider, _owner_repo, canon_url = detect_provider(repo)
        except ValueError as e:
            return {'error': str(e)}, 400

        # #741 (SSRF): bei GitLab den (vom Nutzer ableitbaren) Host gegen
        # private/interne Ziele absichern, bevor abgerufen wird.
        if provider == 'gitlab':
            from shared.net_validation import SSRFError, validate_outbound_url
            try:
                validate_outbound_url(canon_url)
            except SSRFError as e:
                return {'error': f'Repo-URL nicht erlaubt: {e}'}, 400

        token = vcs_token(vcs)
        try:
            ctx = fetch_repo_context(repo, token=token)
        except Exception as e:
            current_app.logger.warning('repo-context fetch failed (%s): %s', repo, e)
            return {'error': _repo_fetch_hint(e)}, 502

        return {
            'provider': ctx.provider,
            'repo': ctx.repo,
            'url': ctx.url,
            'repo_context': format_repo_context(ctx),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Repo-Auto-Answer
# ============================================================

@aiact_bp.post('/projekte/<projekt_name>/repo-scan')
@jwt_required()
def repo_scan(projekt_name: str):
    """Repo-Signale scannen und Bewertungs-Vorschläge generieren."""
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        # #1019: Repo aus Request ODER aus der pro-Projekt gespeicherten Konfig
        # (meta.vcs_publish.repo) auflösen — nicht mehr nur aus dem Request-Body.
        vcs = _project_vcs(p)
        repo = resolve_repo(vcs, data.get('repo'))
        branch = (data.get('branch') or vcs.get('branch') or '').strip()
        if not repo:
            return {'error': 'Kein Repo verknüpft. Bitte unter Integration / '
                             'Repo-Konfiguration ein Repository hinterlegen.'}, 400
        repo_source = 'request' if (data.get('repo') or '').strip() else 'stored'

        from ai_act.repo_autoanswer import suggest_from_repo_signals
        token = vcs_token(vcs)  # #1065: HTTP-API-Token für private Repos im Container
        suggestions = suggest_from_repo_signals(repo=repo, branch=branch, token=token)

        result = []
        for s in suggestions:
            # AIActRepoSuggestion-Dataclass zu Dict
            result.append({
                'field_id': getattr(s, 'field_id', ''),
                'score': getattr(s, 'score', 0),
                'kommentar': getattr(s, 'kommentar', ''),
                'confidence': getattr(s, 'confidence', 0.0),
                'rationale': getattr(s, 'rationale', ''),
                'evidence': getattr(s, 'evidence', []),
            })
        return {'suggestions': result, 'count': len(result), 'repo': repo,
                'repo_source': repo_source}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Reports
# ============================================================

@aiact_bp.get('/projekte/<projekt_name>/report')
@jwt_required()
def export_report(projekt_name: str):
    """Report-Export: format=md | docx | pdf."""
    fmt = (request.args.get('format') or 'md').lower()
    if fmt not in {'md', 'markdown', 'docx', 'pdf'}:
        return {'error': 'Format muss md|docx|pdf sein'}, 400

    if not load_projekt(DB_PATH, projekt_name):
        return {'error': 'Projekt nicht gefunden'}, 404

    out_dir = workspace_tmpdir('aiact_report_')

    try:
        if fmt in ('md', 'markdown'):
            from ai_act.report_export import export_markdown
            path = export_markdown(db_path=DB_PATH, projekt_name=projekt_name, out_dir=out_dir)
        elif fmt == 'docx':
            from ai_act.report_export import export_docx
            path = export_docx(db_path=DB_PATH, projekt_name=projekt_name, out_dir=out_dir)
        else:  # pdf
            from ai_act.report_export import export_pdf
            path = export_pdf(db_path=DB_PATH, projekt_name=projekt_name, out_dir=out_dir)
        current_app.logger.info('AIAct export ok: fmt=%s path=%s', fmt, path.name)
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Anforderungs-Aktionen: Prompt, JSON-Parse, Issue-Linking
# ============================================================

import re
import json as _json


def _serialize_link(li: Any) -> Dict[str, Any]:
    return {
        'id': getattr(li, 'id', None),
        'provider': getattr(li, 'provider', ''),
        'repo': getattr(li, 'repo', ''),
        'url': getattr(li, 'url', ''),
        'issue_number': getattr(li, 'issue_number', None),
        'issue_iid': getattr(li, 'issue_iid', None),
        'title': getattr(li, 'title', ''),
        'state': getattr(li, 'state', ''),
        'state_reason': getattr(li, 'state_reason', ''),
    }


def _find_anforderung(req_id: str) -> Dict[str, Any] | None:
    return next((r for r in AI_ACT_REQUIREMENTS if r.get('id') == req_id), None)


def _build_anforderung_prompt(req: Dict[str, Any], projekt: Dict[str, Any], current: Dict[str, Any]) -> str:
    return f"""🔒 SECURITY: Verwende AUSSCHLIESSLICH die bereitgestellten Informationen.

Du bist ein Experte für EU AI Act-Compliance (Verordnung EU 2024/1689).
Bewerte die Umsetzung der folgenden AI-Act-Anforderung im Kontext von {projekt.get('produkt') or projekt.get('name', '—')}.

## Anforderung
ID:           {req.get('id')}
Kapitel:      {req.get('kapitel', '')}
EU-Referenz:  {req.get('ref', '')}
Titel:        {req.get('titel', '')}
Beschreibung: {req.get('beschreibung', '')}
Hinweise:     {req.get('hinweise', '')}
Gewichtung:   {req.get('gewichtung', 1)}

## Aktueller Stand
Score:      {int(current.get('bewertung', 0) or 0)}/5
Kommentar:  {current.get('kommentar', '') or '(leer)'}
Maßnahme:   {current.get('massnahme', '') or '(leer)'}

## Auftrag
1. Bewertung 0-5.
2. Kommentar in 2-4 Sätzen.
3. 2-3 konkrete Maßnahmen.

## Format
```json
{{
  "score": 0-5,
  "kommentar": "Begründung...",
  "massnahme": "Maßnahmen..."
}}
```
"""


@aiact_bp.get('/projekte/<projekt_name>/anforderungen/<req_id>/prompt')
@jwt_required()
def anf_prompt(projekt_name: str, req_id: str):
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        req = _find_anforderung(req_id)
        if not req:
            return {'error': 'Anforderung nicht gefunden'}, 404
        bewertungen = load_bewertungen(DB_PATH, projekt_name)
        prompt = _build_anforderung_prompt(req, projekt, bewertungen.get(req_id, {}))
        return {'prompt': prompt, 'req_id': req_id}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/parse-response')
@jwt_required()
def anf_parse(projekt_name: str, req_id: str):
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        if not _find_anforderung(req_id):
            return {'error': 'Anforderung nicht gefunden'}, 404

        data = request.json or {}
        raw = data.get('raw') or ''
        if not raw:
            return {'error': 'Feld "raw" ist Pflicht'}, 400
        apply = bool(data.get('apply', False))

        json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            m = re.search(r'(\{[^{}]*"score"[^{}]*\})', raw, re.DOTALL)
            json_str = m.group(1) if m else raw.strip()

        try:
            parsed = _json.loads(json_str)
        except _json.JSONDecodeError as e:
            return {'error': f'JSON-Parse-Fehler: {e}'}, 400

        score = int(parsed.get('score', 0))
        if score < 0 or score > 5:
            return {'error': 'score muss 0-5 sein'}, 400

        kommentar = parsed.get('kommentar', '') or ''
        massnahme = parsed.get('massnahme', '') or ''
        result = {'parsed': parsed, 'bewertung': score, 'kommentar': kommentar, 'massnahme': massnahme}

        if apply:
            db_save_bewertung(
                DB_PATH,
                projekt_name=projekt_name,
                anforderung_id=req_id,
                bewertung=score,
                kommentar=kommentar,
                massnahme=massnahme,
            )
            result['saved'] = True
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.get('/projekte/<projekt_name>/anforderungen/<req_id>/issues')
@jwt_required()
def anf_list_issues(projekt_name: str, req_id: str):
    try:
        from shared.issue_links import list_links, ensure_tables
        ensure_tables(DB_PATH)
        links = list_links(DB_PATH, projekt_name=projekt_name,
                           object_kind='requirement', object_id=req_id)
        return [_serialize_link(l) for l in links], 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


def _aiact_issue_content(req_id: str, req: Dict[str, Any], existing: Dict[str, Any]) -> tuple[str, str]:
    """Titel + Body für ein AI-Act-Issue aus Anforderung + Bewertung (#795).

    Wird von Einzel- (anf_create_issue) und Massenanlage (aiact_bulk_create_issues)
    gemeinsam genutzt, damit beide identische Issues erzeugen."""
    titel = (req.get('titel', '') or '').strip()
    title = f"AICS · AI-Act-Gap [{req_id}]: {titel}".strip().rstrip(':').strip()
    body = f"""## EU AI Act-Anforderung: {req_id}

**Titel**: {req.get('titel', '')}
**Kapitel**: {req.get('kapitel', '')}
**EU-Referenz**: {req.get('ref', '')}
**Aktueller Score**: {existing.get('bewertung', 0)}/5
**Gewichtung**: {req.get('gewichtung', 1)}

### Beschreibung
{req.get('beschreibung', '')}

### Aktueller Stand
{existing.get('kommentar', '') or '_(noch keine Notizen)_'}

### Hinweise
{req.get('hinweise', '')}

---
_Generiert aus dem AI Compliance Suite AI-Act-Modul._
"""
    return title, body


@aiact_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues')
@jwt_required()
def anf_create_issue(projekt_name: str, req_id: str):
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        req = _find_anforderung(req_id)
        if not req:
            return {'error': 'Anforderung nicht gefunden'}, 404

        data = request.json or {}
        # #862: Repo + Provider/Token aus der gespeicherten Projekt-Konfig
        # ableiten; explizite Request-Felder bleiben rückwärtskompatibel.
        vcs = _project_vcs(projekt)
        repo = resolve_repo(vcs, data.get('repo'))
        if not repo:
            return {'error': 'Kein Repository für dieses Projekt konfiguriert '
                             '(Repo-Konfig speichern oder repo übergeben)'}, 400
        provider = (data.get('provider') or vcs.get('provider') or 'github').lower()

        existing = load_bewertungen(DB_PATH, projekt_name).get(req_id, {})
        default_title, default_body = _aiact_issue_content(req_id, req, existing)
        title = data.get('title') or default_title
        body = data.get('body') or default_body

        issue_url = ''
        issue_number = None
        issue_iid = None

        if provider == 'github':
            # GitHub-Token via Umgebung (GH_TOKEN/GITHUB_TOKEN), siehe vcs.github_issues.
            from vcs.github_issues import create_issue as gh_create
            ci = gh_create(repo=repo, title=title, body=body)
            issue_url, issue_number = ci.url, ci.number
        elif provider == 'gitlab':
            from vcs.gitlab_issues import create_issue as gl_create
            base_url = data.get('gitlab_base_url') or vcs.get('base_url') or 'https://gitlab.com'
            token_env = data.get('gitlab_token_env') or vcs.get('token_env') or 'GITLAB_TOKEN'
            ci = gl_create(base_url=base_url, token_env=token_env, project=repo, title=title, body=body)
            issue_url, issue_iid = ci.url, ci.iid
        else:
            return {'error': f'Unbekannter Provider: {provider}'}, 400

        from shared.issue_links import add_link
        add_link(
            DB_PATH, projekt_name=projekt_name,
            object_kind='requirement', object_id=req_id,
            provider=provider, repo=repo, url=issue_url,
            issue_number=issue_number, issue_iid=issue_iid, title=title,
        )
        return {
            'created': True, 'provider': provider, 'url': issue_url,
            'issue_number': issue_number, 'issue_iid': issue_iid, 'title': title,
        }, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.post('/projekte/<projekt_name>/issues/bulk')
@jwt_required()
def aiact_bulk_create_issues(projekt_name: str):
    """Massenanlage von Issues für AI-Act-Anforderungen (#795).

    Body: { provider='github', repo, gitlab_base_url?, gitlab_token_env?,
            only_gaps?=true, skip_linked?=true, req_ids?: [str] }.
    Legt für jede passende Anforderung ein Issue an und verknüpft es. Bei
    Auth-/Rate-Limit-Fehlern wird abgebrochen (sonst scheitern alle weiteren)."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404

        data = request.json or {}
        # #862: Repo + Provider/Token aus der gespeicherten Projekt-Konfig
        # ableiten; explizite Request-Felder bleiben rückwärtskompatibel.
        vcs = _project_vcs(projekt)
        repo = resolve_repo(vcs, data.get('repo'))
        if not repo:
            return {'error': 'Kein Repository für dieses Projekt konfiguriert '
                             '(Repo-Konfig speichern oder repo übergeben)'}, 400
        provider = (data.get('provider') or vcs.get('provider') or 'github').lower()
        only_gaps = data.get('only_gaps', True)
        skip_linked = data.get('skip_linked', True)
        req_ids = data.get('req_ids')

        bewertungen = load_bewertungen(DB_PATH, projekt_name)

        from shared.issue_links import add_link, list_links, ensure_tables
        ensure_tables(DB_PATH)

        gh_create = gl_create = None
        if provider == 'github':
            from vcs.github_issues import create_issue as gh_create
        elif provider == 'gitlab':
            from vcs.gitlab_issues import create_issue as gl_create
            base_url = data.get('gitlab_base_url') or vcs.get('base_url') or 'https://gitlab.com'
            token_env = data.get('gitlab_token_env') or vcs.get('token_env') or 'GITLAB_TOKEN'
        else:
            return {'error': f'Unbekannter Provider: {provider}'}, 400

        # Kandidaten: req_ids-Filter, sonst alle; only_gaps → Score < 5 (fehlend = Gap).
        candidates: List[Dict[str, Any]] = []
        for req in AI_ACT_REQUIREMENTS:
            rid = req.get('id')
            if req_ids and rid not in req_ids:
                continue
            existing = bewertungen.get(rid, {})
            score = int(existing.get('bewertung', 0) or 0)
            if only_gaps and score >= 5:
                continue
            candidates.append(req)

        created, skipped, failed = [], [], []
        for req in candidates:
            rid = req.get('id')
            if skip_linked and list_links(DB_PATH, projekt_name=projekt_name,
                                          object_kind='requirement', object_id=rid):
                skipped.append({'req_id': rid, 'reason': 'bereits verknüpft'})
                continue

            existing = bewertungen.get(rid, {})
            title, body = _aiact_issue_content(rid, req, existing)
            try:
                issue_number = issue_iid = None
                if provider == 'github':
                    ci = gh_create(repo=repo, title=title, body=body)
                    issue_url, issue_number = ci.url, ci.number
                else:
                    ci = gl_create(base_url=base_url, token_env=token_env,
                                   project=repo, title=title, body=body)
                    issue_url, issue_iid = ci.url, ci.iid
                add_link(
                    DB_PATH, projekt_name=projekt_name,
                    object_kind='requirement', object_id=rid,
                    provider=provider, repo=repo, url=issue_url,
                    issue_number=issue_number, issue_iid=issue_iid, title=title,
                )
                created.append({'req_id': rid, 'url': issue_url, 'title': title})
            except Exception as e:  # noqa: BLE001
                current_app.logger.warning('bulk issue create failed (%s/%s): %s', projekt_name, rid, e)
                msg = str(e)
                failed.append({'req_id': rid, 'error': msg})
                # Bei Auth-/Rate-Limit-Fehler abbrechen (sonst scheitern alle weiteren).
                if any(k in msg for k in ('Token', 'Limit', '401', '403')):
                    break

        return {'created': created, 'skipped': skipped, 'failed': failed,
                'summary': {'created': len(created), 'skipped': len(skipped), 'failed': len(failed)}}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues/link')
@jwt_required()
def anf_link_issue(projekt_name: str, req_id: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        provider = (data.get('provider') or 'github').lower()
        url = data.get('url') or ''
        repo = data.get('repo') or ''
        if not url:
            return {'error': 'Feld "url" ist Pflicht'}, 400

        if not repo:
            gh_match = re.match(r'https?://github\.com/([^/]+/[^/]+)/issues/\d+', url)
            gl_match = re.match(r'https?://[^/]+/([^/]+/[^/]+)/-/issues/\d+', url)
            if gh_match:
                repo, provider = gh_match.group(1), 'github'
            elif gl_match:
                repo, provider = gl_match.group(1), 'gitlab'

        num_match = re.search(r'/(?:issues|merge_requests)/(\d+)', url)
        number = int(num_match.group(1)) if num_match else None

        from shared.issue_links import add_link
        add_link(
            DB_PATH, projekt_name=projekt_name,
            object_kind='requirement', object_id=req_id,
            provider=provider, repo=repo, url=url,
            issue_number=number if provider == 'github' else None,
            issue_iid=number if provider == 'gitlab' else None,
            title=data.get('title') or url,
        )
        return {'linked': True, 'url': url, 'number': number, 'provider': provider}, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues/sync')
@jwt_required()
def anf_sync_issues(projekt_name: str, req_id: str):
    try:
        from shared.issue_links import list_links, update_issue_state
        from shared.issue_sync import sync_github_issue, is_successfully_resolved

        links = list_links(DB_PATH, projekt_name=projekt_name,
                           object_kind='requirement', object_id=req_id)
        if not links:
            return {'synced': 0, 'links': []}, 200

        synced_count = 0
        results = []
        for li in links:
            try:
                if li.provider == 'github' and li.repo and li.issue_number:
                    synced = sync_github_issue(repo=li.repo, number=li.issue_number)
                    update_issue_state(
                        DB_PATH, link_id=li.id,
                        state=synced.state, state_reason=synced.state_reason or '',
                        title=synced.title or li.title,
                    )
                    synced_count += 1
                    results.append({
                        'id': li.id, 'state': synced.state,
                        'state_reason': synced.state_reason,
                        'resolved': is_successfully_resolved(
                            state=synced.state,
                            state_reason=synced.state_reason or '',
                            labels=getattr(synced, 'labels', []) or [],
                        ),
                    })
            except Exception as e:
                results.append({'id': li.id, 'error': str(e)})
        return {'synced': synced_count, 'links': results}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/import-issue')
@jwt_required()
def anf_import_issue(projekt_name: str, req_id: str):
    """Inhalt der verknüpften Issues in den Bewertungs-Kommentar der Anforderung
    übernehmen (#830, analog Risikobewertung)."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        req = _find_anforderung(req_id)
        if not req:
            return {'error': f'Anforderung nicht gefunden: {req_id}'}, 404

        data = request.json or {}
        issue_context = str(data.get('issue_context', '') or '').strip()
        sources: list[dict] = []

        if not issue_context:
            from shared.issue_links import list_links, ensure_tables
            from shared.issue_feedback import collect_issue_feedback
            ensure_tables(DB_PATH)
            links = list_links(DB_PATH, projekt_name=projekt_name,
                               object_kind='requirement', object_id=req_id)
            if not links:
                return {'error': 'Keine verknüpften Issues für diese Anforderung'}, 400
            gitlab_token_env = data.get('gitlab_token_env') or 'GITLAB_TOKEN'
            issue_context, sources = collect_issue_feedback(
                links, gitlab_token_env=gitlab_token_env)
            if not issue_context:
                errs = '; '.join(s.get('error', '') for s in sources if not s.get('ok'))
                return {'error': f'Issue-Inhalt konnte nicht geladen werden: {errs}'}, 502

        from shared.issue_feedback import merge_feedback_into_comment
        existing = load_bewertungen(DB_PATH, projekt_name).get(req_id, {})
        neuer_kommentar = merge_feedback_into_comment(existing.get('kommentar', ''), issue_context)

        db_save_bewertung(
            DB_PATH,
            projekt_name=projekt_name,
            anforderung_id=req_id,
            bewertung=int(existing.get('bewertung', 0) or 0),
            kommentar=neuer_kommentar,
            massnahme=existing.get('massnahme', '') or '',
        )
        return {'imported': True, 'anforderung_id': req_id,
                'kommentar': neuer_kommentar, 'sources': sources}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.delete('/projekte/<projekt_name>/anforderungen/<req_id>/issues/<link_id>')
@jwt_required()
def anf_unlink_issue(projekt_name: str, req_id: str, link_id: str):
    try:
        from shared.issue_links import delete_link
        delete_link(DB_PATH, link_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Backwards-compat
# ============================================================

@aiact_bp.get('')
@jwt_required()
def list_all_legacy():
    """Backwards-compat: flacher GET ohne /projekte."""
    try:
        names = list_projekte(DB_PATH)
        result = []
        for n in names:
            p = load_projekt(DB_PATH, n)
            if p:
                result.append(_serialize_projekt(p))
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@aiact_bp.post('/projekte/<projekt_name>/fragebogen/import')
@jwt_required()
def import_fragebogen_endpoint(projekt_name: str):
    """Excel-Fragebogen importieren (multipart, Feld 'file')."""
    import shutil
    if not load_projekt(DB_PATH, projekt_name):
        return {'error': 'Projekt nicht gefunden'}, 404
    f = request.files.get('file')
    if not f or not f.filename:
        return {'error': 'Datei-Feld \"file\" fehlt'}, 400
    if not f.filename.lower().endswith('.xlsx'):
        return {'error': 'Nur .xlsx wird unterstützt'}, 400

    tmp_dir = workspace_tmpdir('aiact_import_')
    try:
        tmp_path = tmp_dir / 'upload.xlsx'
        f.save(str(tmp_path))
        # #743 (WP-10): Magic-Byte- + Zip-Bomb-Prüfung vor dem Parsen.
        from shared.upload_validation import validate_upload_file
        validate_upload_file(tmp_path, suffix='.xlsx')
        from shared.xlsx_import import import_bewertungen
        known = {r['id'] for r in AI_ACT_REQUIREMENTS}
        items = import_bewertungen(tmp_path, known_ids=known, expected_label='AI-Act-Fragebogen')
        for it in items:
            db_save_bewertung(
                DB_PATH,
                projekt_name=projekt_name,
                anforderung_id=it['anforderung_id'],
                bewertung=it['bewertung'],
                kommentar=it.get('kommentar', ''),
                massnahme=it.get('massnahme', ''),
            )
        return {'imported': len(items)}, 200
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ════════════════════════════════════════════════════════════════════
# Sprint γ Phase A — Pflicht-Doku-Manager (Issue #583)
# ════════════════════════════════════════════════════════════════════

from ai_act.db import (
    load_system_doku as db_load_sd, save_system_doku as db_save_sd,
    load_data_governance as db_load_dg, save_data_governance as db_save_dg,
    # #1047: A3-Risiken kommen aus der verknüpften Risikobewertung (kein lokales Register mehr)
    linked_a3_risks as db_list_aiact_risks,
    load_human_oversight as db_load_ho, save_human_oversight as db_save_ho,
    load_pmm as db_load_pmm, save_pmm as db_save_pmm,
)


def _require_aiact_projekt(projekt_name: str):
    return require_projekt(load_projekt, DB_PATH, projekt_name)


# ─── A1 System-Doku ────────────────────────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/system-doku')
@jwt_required()
def aiact_sd_get(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    return jsonify(db_load_sd(DB_PATH, projekt_name) or {})


@aiact_bp.post('/projekte/<projekt_name>/system-doku')
@jwt_required()
def aiact_sd_save(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    db_save_sd(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    return jsonify({'ok': True})


# ─── A2 Data-Governance ────────────────────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/data-governance')
@jwt_required()
def aiact_dg_get(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    return jsonify(db_load_dg(DB_PATH, projekt_name) or {})


@aiact_bp.post('/projekte/<projekt_name>/data-governance')
@jwt_required()
def aiact_dg_save(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    db_save_dg(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    return jsonify({'ok': True})


# ─── A3 Risk-Management ────────────────────────────────────────────
# Kein lokales Register/CRUD mehr (#1047). A3-Risiken werden im
# Risikobewertungs-Modul gepflegt; die Verknüpfung läuft über die
# /risk-link- und /linked-risks-Endpoints (#1044/#1046).


# ─── A4 Human-Oversight ────────────────────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/human-oversight')
@jwt_required()
def aiact_ho_get(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    return jsonify(db_load_ho(DB_PATH, projekt_name) or {})


@aiact_bp.post('/projekte/<projekt_name>/human-oversight')
@jwt_required()
def aiact_ho_save(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    db_save_ho(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    return jsonify({'ok': True})


# ─── A5 Post-Market-Monitoring ─────────────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/pmm')
@jwt_required()
def aiact_pmm_get(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    return jsonify(db_load_pmm(DB_PATH, projekt_name) or {})


@aiact_bp.post('/projekte/<projekt_name>/pmm')
@jwt_required()
def aiact_pmm_save(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    db_save_pmm(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    return jsonify({'ok': True})


@aiact_bp.get('/projekte/<projekt_name>/pflicht-doku')
@jwt_required()
def aiact_pflicht_doku_status(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    dg = db_load_dg(DB_PATH, projekt_name) or {}
    risks = db_list_aiact_risks(DB_PATH, projekt_name)  # #1047: aus verknüpfter Risikobewertung
    ho = db_load_ho(DB_PATH, projekt_name) or {}
    pmm = db_load_pmm(DB_PATH, projekt_name) or {}
    meta = p.get('meta') if isinstance(p.get('meta'), dict) else {}
    linked = bool((meta.get('linked_risk_projekt') or '').strip())
    open_risks = [r for r in risks if r.get('status') in ('offen', 'in-behandlung')]

    # #1070: Vollständigkeit konsistent prüfen — eine Sektion ist erst „ok"/grün,
    # wenn ALLE inhaltlichen Pflichtfelder befüllt sind (nicht nur ein Einzelfeld).
    def _missing(data: dict, fields: list[str]) -> list[str]:
        return [f for f in fields if not str(data.get(f) or '').strip()]

    sd_req = ['system_name', 'version', 'provider', 'intended_purpose', 'architecture',
              'training_methodology', 'computational_resources', 'test_methodology',
              'cybersecurity_measures', 'accuracy_robustness']
    dg_req = ['training_data_source', 'training_data_size', 'validation_data_split',
              'test_data_split', 'data_collection_method', 'data_labelling_method',
              'bias_assessment', 'bias_mitigation', 'representativeness']
    if dg.get('personal_data_used'):
        dg_req = dg_req + ['legal_basis_gdpr']
    ho_req = ['oversight_mode', 'intervention_mechanisms', 'monitoring_interface',
              'output_interpretation_aids', 'abnormal_behavior_detection', 'training_program']
    pmm_req = ['monitoring_plan', 'performance_metrics', 'drift_detection',
               'user_feedback_channel', 'incident_threshold', 'market_surveillance_contact',
               'serious_incident_reporting_sla']

    sd_missing, dg_missing = _missing(sd, sd_req), _missing(dg, dg_req)
    ho_missing, pmm_missing = _missing(ho, ho_req), _missing(pmm, pmm_req)
    return jsonify({
        'system_doku': {'ok': not sd_missing, 'missing': sd_missing},
        'data_governance': {'ok': not dg_missing, 'missing': dg_missing},
        # A3 ok = verknüpft + keine offenen Risiken im verknüpften RB-Projekt
        'risk_management': {'linked': linked, 'total': len(risks), 'open': len(open_risks),
                            'ok': linked and len(open_risks) == 0},
        'human_oversight': {'ok': not ho_missing, 'missing': ho_missing},
        'post_market_monitoring': {'ok': not pmm_missing, 'missing': pmm_missing},
    })


# ════════════════════════════════════════════════════════════════════
# Sprint #18 — Auto-Fill (A1/A2) + Wizards (A3/A4/A5) (#1018)
# ════════════════════════════════════════════════════════════════════

def _aiact_audit(action: str, projekt_name: str, **details):
    try:
        from shared.audit import audit_event
        audit_event(action, module='aiact', details={'projekt': projekt_name, **details})
    except Exception:
        pass


def _aiact_apply_fields(load_fn, save_fn, projekt_name: str, fields: dict) -> list[str]:
    """Merge ausgewählter Felder in den bestehenden Datensatz (kein Überschreiben
    nicht genannter Felder)."""
    existing = dict(load_fn(DB_PATH, projekt_name) or {})
    applied = []
    for k, v in (fields or {}).items():
        existing[k] = v
        applied.append(k)
    save_fn(DB_PATH, projekt_name, existing)
    return applied


def _aiact_resolve_repo(p: dict, data: dict) -> tuple[str, str]:
    vcs = _project_vcs(p)
    repo = resolve_repo(vcs, data.get('repo'))
    branch = (data.get('branch') or vcs.get('branch') or '').strip()
    return repo, branch


# ─── A1 System-Doku: Auto-Fill (#1020) ─────────────────────────────

@aiact_bp.post('/projekte/<projekt_name>/system-doku/suggest')
@jwt_required()
def aiact_sd_suggest(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    data = request.get_json(silent=True) or {}
    source = (data.get('source') or 'repo').lower()
    from ai_act.autofill_common import suggestions_to_dict
    from ai_act import system_doku_autofill as sda
    try:
        if source == 'url':
            url = (data.get('url') or '').strip()
            if not url:
                return jsonify({'error': 'Feld "url" ist Pflicht'}), 400
            sug = sda.suggest_from_url(url)
        else:
            repo, branch = _aiact_resolve_repo(p, data)
            if not repo:
                return jsonify({'error': 'Kein Repo verknüpft. Bitte Repo-Konfiguration speichern.'}), 400
            token = vcs_token(_project_vcs(p))  # #1064: HTTP-API-Token für private Repos im Container
            sug = sda.suggest_system_doku(repo, branch, token=token)
    except Exception as e:
        current_app.logger.warning('system-doku suggest failed: %s', e)
        return jsonify({'error': 'Vorschläge konnten nicht erzeugt werden'}), 502
    return jsonify({'suggestions': suggestions_to_dict(sug), 'count': len(sug)})


@aiact_bp.post('/projekte/<projekt_name>/system-doku/apply')
@jwt_required()
def aiact_sd_apply(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    fields = (request.get_json(silent=True) or {}).get('fields') or {}
    applied = _aiact_apply_fields(db_load_sd, db_save_sd, projekt_name, fields)
    _aiact_audit('aiact.system_doku.applied', projekt_name, fields=applied)
    return jsonify({'ok': True, 'applied': applied})


# ─── A2 Data-Governance: Auto-Fill (#1021) ─────────────────────────

@aiact_bp.post('/projekte/<projekt_name>/data-governance/suggest')
@jwt_required()
def aiact_dg_suggest(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    data = request.get_json(silent=True) or {}
    source = (data.get('source') or 'repo').lower()
    from ai_act.autofill_common import suggestions_to_dict
    from ai_act import data_governance_autofill as dga
    try:
        if source == 'url':
            url = (data.get('url') or '').strip()
            if not url:
                return jsonify({'error': 'Feld "url" ist Pflicht'}), 400
            sug = dga.suggest_from_url(url)
        else:
            repo, branch = _aiact_resolve_repo(p, data)
            if not repo:
                return jsonify({'error': 'Kein Repo verknüpft. Bitte Repo-Konfiguration speichern.'}), 400
            token = vcs_token(_project_vcs(p))  # #1064: HTTP-API-Token für private Repos im Container
            sug = dga.suggest_data_governance(repo, branch, token=token)
    except Exception as e:
        current_app.logger.warning('data-governance suggest failed: %s', e)
        return jsonify({'error': 'Vorschläge konnten nicht erzeugt werden'}), 502
    return jsonify({'suggestions': suggestions_to_dict(sug), 'count': len(sug)})


@aiact_bp.post('/projekte/<projekt_name>/data-governance/apply')
@jwt_required()
def aiact_dg_apply(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    fields = (request.get_json(silent=True) or {}).get('fields') or {}
    applied = _aiact_apply_fields(db_load_dg, db_save_dg, projekt_name, fields)
    _aiact_audit('aiact.data_governance.applied', projekt_name, fields=applied)
    return jsonify({'ok': True, 'applied': applied})


# ─── A3 Risk-Management ────────────────────────────────────────────
# Kein A3-Prompt-Wizard mehr (#1047). Risiken werden im Risikobewertungs-Modul
# über dessen Risiko-Assistenten erzeugt (inkl. EU-AI-Act-Kontext, #1045).


# ─── A4 Human-Oversight: Wizard (#1023) ────────────────────────────

@aiact_bp.post('/projekte/<projekt_name>/human-oversight/wizard-prompt')
@jwt_required()
def aiact_ho_wizard_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    from ai_act.ai_wizards import build_human_oversight_prompt
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    return jsonify({'prompt': build_human_oversight_prompt(p, sd)})


@aiact_bp.post('/projekte/<projekt_name>/human-oversight/wizard-apply')
@jwt_required()
def aiact_ho_wizard_apply(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    from ai_act.ai_wizards import parse_human_oversight_response
    raw = (request.get_json(silent=True) or {}).get('response') or ''
    fields = {k: v for k, v in (parse_human_oversight_response(raw) or {}).items() if str(v or '').strip()}
    if not fields:
        return jsonify({'error': 'Keine befüllten Felder erkannt. Bitte gültiges JSON '
                                 'aus der KI-Antwort einfügen.'}), 400
    applied = _aiact_apply_fields(db_load_ho, db_save_ho, projekt_name, fields)
    _aiact_audit('aiact.human_oversight.applied', projekt_name, fields=applied)
    return jsonify({'ok': True, 'applied': applied})


# ─── A5 Post-Market-Monitoring: Hilfe + Wizard (#1024) ─────────────

@aiact_bp.get('/pmm/help')
@jwt_required()
def aiact_pmm_help():
    from ai_act.pmm_help import get_pmm_help
    return jsonify(get_pmm_help())


@aiact_bp.post('/projekte/<projekt_name>/pmm/wizard-prompt')
@jwt_required()
def aiact_pmm_wizard_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    from ai_act.ai_wizards import build_pmm_plan_prompt
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    risks = db_list_aiact_risks(DB_PATH, projekt_name) or []
    return jsonify({'prompt': build_pmm_plan_prompt(p, sd, risks)})


@aiact_bp.post('/projekte/<projekt_name>/pmm/wizard-apply')
@jwt_required()
def aiact_pmm_wizard_apply(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    from ai_act.ai_wizards import parse_pmm_response
    raw = (request.get_json(silent=True) or {}).get('response') or ''
    fields = {k: v for k, v in (parse_pmm_response(raw) or {}).items() if str(v or '').strip()}
    if not fields:
        return jsonify({'error': 'Keine befüllten Felder erkannt. Bitte gültiges JSON '
                                 'aus der KI-Antwort einfügen.'}), 400
    applied = _aiact_apply_fields(db_load_pmm, db_save_pmm, projekt_name, fields)
    _aiact_audit('aiact.pmm.applied', projekt_name, fields=applied)
    return jsonify({'ok': True, 'applied': applied})


# ─── A3 via Risikobewertung-Verknüpfung (#1044) ────────────────────
# Statt eigener aiact_risk_management-Tabelle wird A3 an ein Risikobewertungs-
# Projekt (Bewertungsart „EU-AI-Act", Art. 9) gekoppelt — analog CRA (#880/#881).

_RB_DB_PATH = Path('data/db/risikobewertung.sqlite')


def _rb_risk_summary(rb_name: str) -> dict:
    try:
        from risikobewertung.db import load_projekt as rb_load, load_risiken
        rbp = rb_load(_RB_DB_PATH, rb_name) or {}
        risiken = load_risiken(_RB_DB_PATH, rb_name)
        by_label: dict[str, int] = {}
        for r in risiken:
            lbl = r.get('risiko_label') or 'unbewertet'
            by_label[lbl] = by_label.get(lbl, 0) + 1
        geloest = sum(1 for r in risiken if r.get('is_resolved'))
        return {'framework': rbp.get('framework', ''), 'total': len(risiken),
                'offen': len(risiken) - geloest, 'geloest': geloest, 'by_label': by_label}
    except Exception:
        return {'framework': '', 'total': 0, 'offen': 0, 'geloest': 0, 'by_label': {}}


@aiact_bp.get('/projekte/<projekt_name>/risk-link/candidates')
@jwt_required()
def aiact_risk_link_candidates(projekt_name: str):
    """#1046: Nur EU-AI-Act-Risikobewertungen als A3-Kandidaten — firmenübergreifend.

    Reine Firmengleichheit (organisation == unternehmen) war zu eng (Liste blieb
    leer). Für A3 sind ausschließlich Risikobewertungen mit Bewertungsart
    ``EU-AI-Act`` zulässig; diese werden firmenübergreifend gelistet, Firmen-Treffer
    nur priorisiert (Flag ``firma_match`` + Sortierung)."""
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    firma = (p.get('organisation') or '').strip()
    candidates = []
    try:
        from risikobewertung.db import list_projekte as rb_list_all, load_projekt as rb_load_one
        for nm in rb_list_all(_RB_DB_PATH):
            rbp = rb_load_one(_RB_DB_PATH, nm) or {}
            fw = rbp.get('framework', '') or ''
            if fw != 'EU-AI-Act':
                continue  # andere Bewertungsarten sind für A3 nicht zulässig
            unt = (rbp.get('unternehmen') or '').strip()
            firma_match = bool(firma) and unt.casefold() == firma.casefold()
            candidates.append({'name': nm, 'framework': fw, 'unternehmen': unt,
                               'firma_match': firma_match, 'framework_match': True})
        candidates.sort(key=lambda c: (not c['firma_match'], c['name'].casefold()))
    except Exception:
        pass
    return jsonify({'firma': firma, 'candidates': candidates})


@aiact_bp.get('/projekte/<projekt_name>/risk-link')
@jwt_required()
def aiact_risk_link_get(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    meta = p.get('meta') if isinstance(p.get('meta'), dict) else {}
    linked = (meta.get('linked_risk_projekt') or '').strip()
    out = {'linked_risk_projekt': linked or None}
    if linked:
        out['summary'] = _rb_risk_summary(linked)
    return jsonify(out)


@aiact_bp.put('/projekte/<projekt_name>/risk-link')
@jwt_required()
def aiact_risk_link_set(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    data = request.get_json(silent=True) or {}
    rb_name = (data.get('risk_projekt') or '').strip()
    if not rb_name:
        return jsonify({'error': 'Feld "risk_projekt" ist Pflicht'}), 400
    from risikobewertung.db import load_projekt as rb_load, update_projekt_meta as rb_update_meta
    rb_p = rb_load(_RB_DB_PATH, rb_name)
    if not rb_p:
        return jsonify({'error': f'Risikobewertungs-Projekt nicht gefunden: {rb_name}'}), 404
    # #1046: A3 darf nur mit einer EU-AI-Act-Risikobewertung verknüpft werden.
    if (rb_p.get('framework') or '') != 'EU-AI-Act':
        return jsonify({'error': 'Nur Risikobewertungen mit Bewertungsart "EU-AI-Act" '
                                 'sind für A3 zulässig.'}), 400
    meta = dict(p.get('meta') or {})
    meta['linked_risk_projekt'] = rb_name
    update_projekt_meta(DB_PATH, projekt_name, meta)
    rb_meta = dict(rb_p.get('meta') or {})
    rb_meta['linked_aiact_projekt'] = projekt_name
    rb_update_meta(_RB_DB_PATH, rb_name, rb_meta)
    _aiact_audit('aiact.risk_link.set', projekt_name, rb_projekt=rb_name)
    return jsonify({'linked_risk_projekt': rb_name, 'summary': _rb_risk_summary(rb_name)})


@aiact_bp.delete('/projekte/<projekt_name>/risk-link')
@jwt_required()
def aiact_risk_link_delete(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    meta = dict(p.get('meta') or {})
    rb_name = (meta.pop('linked_risk_projekt', None) or '').strip()
    update_projekt_meta(DB_PATH, projekt_name, meta)
    if rb_name:
        try:
            from risikobewertung.db import load_projekt as rb_load, update_projekt_meta as rb_update_meta
            rb_p = rb_load(_RB_DB_PATH, rb_name)
            if rb_p:
                rb_meta = dict(rb_p.get('meta') or {})
                if rb_meta.pop('linked_aiact_projekt', None) is not None:
                    rb_update_meta(_RB_DB_PATH, rb_name, rb_meta)
        except Exception:
            pass
    _aiact_audit('aiact.risk_link.deleted', projekt_name)
    return jsonify({'deleted': True})


@aiact_bp.get('/projekte/<projekt_name>/linked-risks')
@jwt_required()
def aiact_linked_risks(projekt_name: str):
    """Risiken des verknüpften RB-Projekts (read-only für A3)."""
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    meta = p.get('meta') if isinstance(p.get('meta'), dict) else {}
    rb_name = (meta.get('linked_risk_projekt') or '').strip()
    if not rb_name:
        return jsonify({'linked': False, 'risiken': []})
    from risikobewertung.db import load_risiken
    out = []
    for r in load_risiken(_RB_DB_PATH, rb_name):
        out.append({'id': r.get('id'), 'nr': r.get('nr'), 'risk_name': r.get('risk_name', ''),
                    'framework': r.get('framework', ''), 'risikowert': r.get('risikowert'),
                    'risiko_label': r.get('risiko_label', ''), 'is_resolved': bool(r.get('is_resolved'))})
    return jsonify({'linked': True, 'rb_projekt': rb_name, 'risiken': out,
                    'summary': _rb_risk_summary(rb_name)})


# ════════════════════════════════════════════════════════════════════
# Sprint γ Phase B — KI-Wizards (Issue #583)
# ════════════════════════════════════════════════════════════════════

from ai_act.ai_wizards import (
    build_risk_tier_prompt, parse_risk_tier_response,
    list_use_case_templates, get_use_case_template,
    build_eu_doc_prompt, parse_eu_doc_response,
    build_transparency_prompt, parse_transparency_response,
    build_llm_card_prompt, parse_llm_card_response,
    build_high_risk_doc_prompt, parse_high_risk_doc_response,
    build_prompt_injection_test_prompt, parse_prompt_injection_test_response,
    build_hitl_workflow_prompt, parse_hitl_workflow_response,
    build_eu_db_registration_prompt, parse_eu_db_registration_response,
    build_aiact_chat_prompt, parse_aiact_chat_response,
    build_eu_office_report_prompt, parse_eu_office_report_response,
)
from ai_act.model_card_importer import import_model_card, SUPPORTED_FORMATS as MODEL_CARD_FORMATS
from ai_act.owasp_llm_top10 import compute_watch_status


def _should_apply_aiact(body: dict) -> bool:
    if request.args.get('dry_run') == 'true' or body.get('dry_run') is True:
        return False
    if request.args.get('apply') == 'false':
        return False
    return True


# ─── A6 Risk-Tier-Klassifikator ────────────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/wizards/risk-tier/prompt')
@jwt_required()
def aiact_risk_tier_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    return jsonify({'prompt': build_risk_tier_prompt(p)})


@aiact_bp.post('/projekte/<projekt_name>/wizards/risk-tier/parse')
@jwt_required()
def aiact_risk_tier_parse(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_risk_tier_response(body.get('response', ''))
    applied = False
    if _should_apply_aiact(body) and parsed.get('tier'):
        import json as _j
        meta = _j.loads(p.get('meta_json') or '{}')
        meta.setdefault('aiact', {})['risk_tier'] = parsed
        from ai_act.db import save_projekt as aiact_save_projekt
        aiact_save_projekt(DB_PATH, name=p['name'],
                           organisation=p.get('organisation', ''),
                           produkt=p.get('produkt', ''),
                           beschreibung=p.get('beschreibung', ''),
                           meta=meta)
        applied = True
        current_app.logger.info('wizard.applied kind=aiact-risk-tier project=%r tier=%r',
                                projekt_name, parsed.get('tier'))
    return jsonify({**parsed, 'applied': applied})


# ─── A7 Use-Case-Templates ─────────────────────────────────────────

@aiact_bp.get('/wizards/use-case-templates')
@jwt_required()
def aiact_uc_list():
    return jsonify(list_use_case_templates())


@aiact_bp.post('/projekte/<projekt_name>/wizards/use-case-template/apply')
@jwt_required()
def aiact_uc_apply(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    uc_id = (request.get_json(silent=True) or {}).get('use_case_id', '')
    tpl = get_use_case_template(uc_id)
    if not tpl:
        return jsonify({'error': f'Use-Case "{uc_id}" unbekannt'}), 400
    defaults = tpl.get('pflicht_defaults', {})
    # Human-Oversight Mode setzen
    if defaults.get('oversight_mode'):
        ho = db_load_ho(DB_PATH, projekt_name) or {}
        if not ho.get('oversight_mode') or ho.get('oversight_mode') == 'human-in-the-loop':
            ho['oversight_mode'] = defaults['oversight_mode']
            db_save_ho(DB_PATH, projekt_name, ho)
    # PMM-SLA
    if defaults.get('serious_incident_reporting_sla'):
        pmm = db_load_pmm(DB_PATH, projekt_name) or {}
        pmm['serious_incident_reporting_sla'] = defaults['serious_incident_reporting_sla']
        db_save_pmm(DB_PATH, projekt_name, pmm)
    return jsonify({'ok': True, 'template': tpl, 'applied': True})


# ─── A8 EU-DOC ─────────────────────────────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/wizards/eu-doc/prompt')
@jwt_required()
def aiact_eu_doc_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    import json as _j
    meta = _j.loads(p.get('meta_json') or '{}')
    tier = (meta.get('aiact') or {}).get('risk_tier', {}).get('tier', 'high-risk')
    return jsonify({'prompt': build_eu_doc_prompt(p, sd, tier)})


@aiact_bp.post('/projekte/<projekt_name>/wizards/eu-doc/parse')
@jwt_required()
def aiact_eu_doc_parse(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_eu_doc_response(body.get('response', ''))
    applied = False
    if _should_apply_aiact(body) and parsed.get('doc_text'):
        sd = db_load_sd(DB_PATH, projekt_name) or {}
        sd['notizen'] = (sd.get('notizen', '') + '\n\n--- EU-Konformitätserklärung ---\n' + parsed['doc_text']).strip()
        db_save_sd(DB_PATH, projekt_name, sd)
        applied = True
        current_app.logger.info('wizard.applied kind=aiact-eu-doc project=%r', projekt_name)
    return jsonify({**parsed, 'applied': applied})


# ─── A9 Transparenz-Hinweise (Art. 50) ─────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/wizards/transparency/prompt')
@jwt_required()
def aiact_trans_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    return jsonify({'prompt': build_transparency_prompt(p, sd)})


@aiact_bp.post('/projekte/<projekt_name>/wizards/transparency/parse')
@jwt_required()
def aiact_trans_parse(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_transparency_response(body.get('response', ''))
    applied = False
    if _should_apply_aiact(body):
        sd = db_load_sd(DB_PATH, projekt_name) or {}
        sd['notizen'] = (
            sd.get('notizen', '') + '\n\n--- Transparenz-Hinweise (Art. 50) ---\n'
            + (parsed.get('chatbot_hinweis') or {}).get('user_text', '') + '\n'
            + (parsed.get('ai_content_marker') or {}).get('user_text', '') + '\n'
        ).strip()
        db_save_sd(DB_PATH, projekt_name, sd)
        applied = True
        current_app.logger.info('wizard.applied kind=aiact-transparency project=%r', projekt_name)
    return jsonify({**parsed, 'applied': applied})


# ════════════════════════════════════════════════════════════════════
# Sprint γ Phase D — Spezifische Wizards (#541-#545)
# ════════════════════════════════════════════════════════════════════

def _aiact_meta(projekt: dict) -> dict:
    import json as _j
    try:
        return _j.loads(projekt.get('meta_json') or '{}')
    except Exception:
        return {}


def _save_aiact_meta_and_append_note(projekt: dict, projekt_name: str, meta_key: str,
                                     parsed: dict, note_title: str, note_text: str) -> None:
    """Helper: store wizard-result in meta_json + append a short note in system_doku.notizen."""
    import json as _j
    meta = _aiact_meta(projekt)
    meta.setdefault('aiact', {})[meta_key] = parsed
    from ai_act.db import save_projekt as aiact_save_projekt
    aiact_save_projekt(DB_PATH, name=projekt['name'],
                       organisation=projekt.get('organisation', ''),
                       produkt=projekt.get('produkt', ''),
                       beschreibung=projekt.get('beschreibung', ''),
                       meta=meta)
    if note_text:
        sd = db_load_sd(DB_PATH, projekt_name) or {}
        sd['notizen'] = (
            (sd.get('notizen') or '') + f'\n\n--- {note_title} ---\n' + note_text
        ).strip()
        db_save_sd(DB_PATH, projekt_name, sd)


# ─── A15 LLM-System-Card ───────────────────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/wizards/llm-card/prompt')
@jwt_required()
def aiact_llm_card_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    dg = db_load_dg(DB_PATH, projekt_name) or {}
    return jsonify({'prompt': build_llm_card_prompt(p, sd, dg)})


@aiact_bp.post('/projekte/<projekt_name>/wizards/llm-card/parse')
@jwt_required()
def aiact_llm_card_parse(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_llm_card_response(body.get('response', ''))
    applied = False
    if _should_apply_aiact(body) and parsed.get('card_markdown'):
        _save_aiact_meta_and_append_note(
            p, projekt_name, 'llm_system_card', parsed,
            note_title='LLM-System-Card (HuggingFace-Format)',
            note_text=parsed.get('card_markdown', ''),
        )
        applied = True
        current_app.logger.info('wizard.applied kind=aiact-llm-card project=%r', projekt_name)
    return jsonify({**parsed, 'applied': applied})


# ─── A16 High-Risk-Konformitätserklärung ───────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/wizards/high-risk-doc/prompt')
@jwt_required()
def aiact_high_risk_doc_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    dg = db_load_dg(DB_PATH, projekt_name) or {}
    ho = db_load_ho(DB_PATH, projekt_name) or {}
    pmm = db_load_pmm(DB_PATH, projekt_name) or {}
    risks = db_list_aiact_risks(DB_PATH, projekt_name) or []
    return jsonify({
        'prompt': build_high_risk_doc_prompt(p, sd, dg, ho, pmm, len(risks)),
    })


@aiact_bp.post('/projekte/<projekt_name>/wizards/high-risk-doc/parse')
@jwt_required()
def aiact_high_risk_doc_parse(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_high_risk_doc_response(body.get('response', ''))
    applied = False
    if _should_apply_aiact(body) and parsed.get('doc_text'):
        _save_aiact_meta_and_append_note(
            p, projekt_name, 'high_risk_doc', parsed,
            note_title='EU-Konformitätserklärung (High-Risk, Annex V + IV)',
            note_text=parsed.get('doc_text', ''),
        )
        applied = True
        current_app.logger.info('wizard.applied kind=aiact-high-risk-doc project=%r', projekt_name)
    return jsonify({**parsed, 'applied': applied})


# ─── A17 Prompt-Injection-Test-Plan ────────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/wizards/prompt-injection-tests/prompt')
@jwt_required()
def aiact_pi_tests_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    return jsonify({'prompt': build_prompt_injection_test_prompt(p, sd)})


@aiact_bp.post('/projekte/<projekt_name>/wizards/prompt-injection-tests/parse')
@jwt_required()
def aiact_pi_tests_parse(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_prompt_injection_test_response(body.get('response', ''))
    applied = False
    if _should_apply_aiact(body) and parsed.get('testcases'):
        tcs = parsed.get('testcases') or []
        summary = (
            f"Test-Methodologie: {parsed.get('test_methodologie') or '—'}\n"
            f"Frequenz: {parsed.get('frequenz') or '—'} | Verantwortlich: {parsed.get('verantwortlich') or '—'}\n"
            f"Testcases: {len(tcs)} (über OWASP LLM Top 10)\n"
        )
        _save_aiact_meta_and_append_note(
            p, projekt_name, 'prompt_injection_tests', parsed,
            note_title='Prompt-Injection-Test-Plan (OWASP LLM Top 10)',
            note_text=summary,
        )
        applied = True
        current_app.logger.info('wizard.applied kind=aiact-pi-tests project=%r count=%d',
                                projekt_name, len(tcs))
    return jsonify({**parsed, 'applied': applied})


# ─── A18 HITL-Workflow-Designer ────────────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/wizards/hitl-workflow/prompt')
@jwt_required()
def aiact_hitl_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    ho = db_load_ho(DB_PATH, projekt_name) or {}
    tier = (_aiact_meta(p).get('aiact') or {}).get('risk_tier', {}).get('tier', 'high-risk')
    return jsonify({'prompt': build_hitl_workflow_prompt(p, sd, ho, tier)})


@aiact_bp.post('/projekte/<projekt_name>/wizards/hitl-workflow/parse')
@jwt_required()
def aiact_hitl_parse(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_hitl_workflow_response(body.get('response', ''))
    applied = False
    if _should_apply_aiact(body) and parsed.get('decision_points'):
        ho = db_load_ho(DB_PATH, projekt_name) or {}
        modus = parsed.get('modus') or ho.get('oversight_mode') or 'human-in-the-loop'
        ho['oversight_mode'] = modus
        dp_summary = '; '.join(
            f"{d.get('id', '?')}={d.get('name', '?')}" for d in (parsed.get('decision_points') or [])
        )
        existing = ho.get('intervention_mechanisms') or ''
        if dp_summary and dp_summary not in existing:
            ho['intervention_mechanisms'] = (existing + ('\n' if existing else '') + dp_summary).strip()
        db_save_ho(DB_PATH, projekt_name, ho)
        meta = _aiact_meta(p)
        meta.setdefault('aiact', {})['hitl_workflow'] = parsed
        from ai_act.db import save_projekt as aiact_save_projekt
        aiact_save_projekt(DB_PATH, name=p['name'],
                           organisation=p.get('organisation', ''),
                           produkt=p.get('produkt', ''),
                           beschreibung=p.get('beschreibung', ''),
                           meta=meta)
        applied = True
        current_app.logger.info('wizard.applied kind=aiact-hitl project=%r modus=%r',
                                projekt_name, modus)
    return jsonify({**parsed, 'applied': applied})


# ─── A19 EU-Datenbank-Anmeldung (Art. 49) ──────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/wizards/eu-db-registration/prompt')
@jwt_required()
def aiact_eudb_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    rt = (_aiact_meta(p).get('aiact') or {}).get('risk_tier', {})
    return jsonify({
        'prompt': build_eu_db_registration_prompt(
            p, sd,
            tier=rt.get('tier', 'high-risk'),
            annex_iii_kategorie=rt.get('annex_iii_kategorie', ''),
        ),
    })


@aiact_bp.post('/projekte/<projekt_name>/wizards/eu-db-registration/parse')
@jwt_required()
def aiact_eudb_parse(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_eu_db_registration_response(body.get('response', ''))
    applied = False
    if _should_apply_aiact(body):
        pflicht = parsed.get('registrierung_pflicht')
        steps = parsed.get('naechste_schritte') or []
        summary = (
            f"Registrierungspflicht: {'JA' if pflicht else 'NEIN'}\n"
            f"Begründung: {parsed.get('begruendung') or '—'}\n"
            + (f"Nächste Schritte: {'; '.join(steps)}\n" if steps else '')
        )
        _save_aiact_meta_and_append_note(
            p, projekt_name, 'eu_db_registration', parsed,
            note_title='EU-Datenbank-Anmeldung (Art. 49)',
            note_text=summary,
        )
        applied = True
        current_app.logger.info('wizard.applied kind=aiact-eu-db-registration project=%r pflicht=%s',
                                projekt_name, pflicht)
    return jsonify({**parsed, 'applied': applied})


# ════════════════════════════════════════════════════════════════════
# Sprint γ Phase E — Erweiterungen (#546-#550)
# ════════════════════════════════════════════════════════════════════

# ─── A20 Model-Card-Importer (#546) ─────────────────────────────────

@aiact_bp.get('/wizards/model-card-formats')
@jwt_required()
def aiact_mc_formats():
    return jsonify({'formats': list(MODEL_CARD_FORMATS)})


@aiact_bp.post('/projekte/<projekt_name>/wizards/model-card-import')
@jwt_required()
def aiact_mc_import(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    text = (body.get('text') or '').strip()
    fmt = (body.get('format') or 'huggingface').strip().lower()
    if not text:
        return jsonify({'error': 'Feld "text" mit Model-Card-Inhalt ist erforderlich'}), 400
    parsed = import_model_card(text, fmt=fmt)
    applied = False
    if _should_apply_aiact(body):
        sd = db_load_sd(DB_PATH, projekt_name) or {}
        for k in ('system_name', 'version', 'provider', 'intended_purpose', 'architecture',
                  'training_methodology', 'accuracy_robustness', 'cybersecurity_measures'):
            v = parsed.get(k)
            if v and not sd.get(k):
                sd[k] = v
        sd['notizen'] = (
            (sd.get('notizen') or '')
            + f"\n\n--- Importierte Model-Card ({parsed.get('_source_format')}) ---\n"
            + parsed.get('notizen', '')
        ).strip()
        db_save_sd(DB_PATH, projekt_name, sd)
        applied = True
        current_app.logger.info('wizard.applied kind=aiact-model-card-import project=%r format=%r',
                                projekt_name, parsed.get('_source_format'))
    return jsonify({**parsed, 'applied': applied})


# ─── A21 OWASP-LLM-Top-10-Watch (#547) ──────────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/owasp-llm-watch')
@jwt_required()
def aiact_owasp_llm_watch(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    dg = db_load_dg(DB_PATH, projekt_name) or {}
    ho = db_load_ho(DB_PATH, projekt_name) or {}
    rows = compute_watch_status(sd, dg, ho)
    summary = {
        'mitigiert': sum(1 for r in rows if r['status'] == 'mitigiert'),
        'offen': sum(1 for r in rows if r['status'] == 'offen'),
        'n.a.': sum(1 for r in rows if r['status'] == 'n.a.'),
    }
    return jsonify({'rows': rows, 'summary': summary})


# ─── A22 AI-Act-Chat (#548) ─────────────────────────────────────────

@aiact_bp.post('/projekte/<projekt_name>/wizards/chat/prompt')
@jwt_required()
def aiact_chat_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    frage = (body.get('frage') or '').strip()
    if not frage:
        return jsonify({'error': 'Feld "frage" ist erforderlich'}), 400
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    dg = db_load_dg(DB_PATH, projekt_name) or {}
    ho = db_load_ho(DB_PATH, projekt_name) or {}
    pmm = db_load_pmm(DB_PATH, projekt_name) or {}
    risks = db_list_aiact_risks(DB_PATH, projekt_name) or []
    tier = (_aiact_meta(p).get('aiact') or {}).get('risk_tier', {}).get('tier', 'unbekannt')
    return jsonify({'prompt': build_aiact_chat_prompt(p, sd, dg, ho, pmm, risks, tier, frage)})


@aiact_bp.post('/projekte/<projekt_name>/wizards/chat/parse')
@jwt_required()
def aiact_chat_parse(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_aiact_chat_response(body.get('response', ''))
    # Chat-Antworten werden NICHT in Pflicht-Doku gespeichert (volatil).
    current_app.logger.info('wizard.applied kind=aiact-chat project=%r konfidenz=%r',
                            projekt_name, parsed.get('konfidenz'))
    return jsonify({**parsed, 'applied': False})


# ─── A23 EU-AI-Office-Reporting-Template (#549) ─────────────────────

@aiact_bp.post('/projekte/<projekt_name>/wizards/eu-office-report/prompt')
@jwt_required()
def aiact_eu_office_prompt(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    incident = body.get('incident') or {}
    if not (incident.get('summary') or '').strip():
        return jsonify({'error': '`incident.summary` ist erforderlich'}), 400
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    tier = (_aiact_meta(p).get('aiact') or {}).get('risk_tier', {}).get('tier', 'high-risk')
    return jsonify({'prompt': build_eu_office_report_prompt(p, sd, tier, incident)})


@aiact_bp.post('/projekte/<projekt_name>/wizards/eu-office-report/parse')
@jwt_required()
def aiact_eu_office_parse(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_eu_office_report_response(body.get('response', ''))
    applied = False
    if _should_apply_aiact(body) and parsed.get('report_text'):
        _save_aiact_meta_and_append_note(
            p, projekt_name, 'eu_office_report', parsed,
            note_title=f"EU-AI-Office-Reporting (Art. 73) — {parsed.get('art73_kategorie', '')}",
            note_text=parsed.get('report_text', ''),
        )
        applied = True
        current_app.logger.info('wizard.applied kind=aiact-eu-office-report project=%r', projekt_name)
    return jsonify({**parsed, 'applied': applied})


# ─── A24 Pre-Market-Check Validator (#550) ──────────────────────────

@aiact_bp.get('/projekte/<projekt_name>/pre-market-check')
@jwt_required()
def aiact_pre_market_check(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    sd = db_load_sd(DB_PATH, projekt_name) or {}
    dg = db_load_dg(DB_PATH, projekt_name) or {}
    ho = db_load_ho(DB_PATH, projekt_name) or {}
    pmm = db_load_pmm(DB_PATH, projekt_name) or {}
    risks = db_list_aiact_risks(DB_PATH, projekt_name) or []
    meta = _aiact_meta(p).get('aiact') or {}

    rt = meta.get('risk_tier') or {}
    tier = rt.get('tier') or ''
    notizen = (sd.get('notizen') or '').lower()
    open_risks = [r for r in risks if r.get('status') in ('offen', 'in-behandlung')]

    checks: list[dict[str, Any]] = []

    def _check(key: str, ok: bool, label: str, severity: str, hint: str) -> None:
        checks.append({'key': key, 'ok': bool(ok), 'label': label, 'severity': severity, 'hint': hint})

    # Pflicht-Doku
    _check('system_doku', bool(sd.get('system_name') and sd.get('version') and sd.get('intended_purpose')),
           'A1 System-Doku vollständig', 'critical',
           'System-Name, Version und Intended-Purpose pflegen (Annex IV Nr. 1-2)')
    _check('data_governance', bool(dg.get('training_data_source')),
           'A2 Data-Governance erfasst', 'critical',
           'Training-Data-Source + Bias-Assessment dokumentieren (Art. 10)')
    _check('risk_management', not open_risks,
           f'A3 Risk-Management — {len(open_risks)} offene Risiken', 'high',
           'Alle Risiken nach Art. 9 bewerten und in Behandlung bringen')
    _check('oversight', bool(ho.get('oversight_mode') and ho.get('intervention_mechanisms')),
           'A4 Human-Oversight definiert', 'critical',
           'Oversight-Mode + Intervention-Mechanismen (Art. 14)')
    _check('pmm', bool(pmm.get('monitoring_plan')),
           'A5 Post-Market-Monitoring-Plan', 'high',
           'Monitoring-Plan (Art. 72-73) inkl. SLA für Serious-Incident-Reporting')

    # Risiko-Klasse
    _check('risk_tier_known', bool(tier and tier != 'unbekannt'),
           'A6 Risk-Tier klassifiziert', 'critical',
           'Risk-Tier-Wizard ausführen — bestimmt prohibited/high/limited/minimal')

    # High-Risk-Pflichten
    is_high = tier == 'high-risk'
    _check('eu_doc', not is_high or 'eu-konformitätserklärung' in notizen.lower(),
           'High-Risk: EU-Konformitätserklärung (Annex V)', 'critical' if is_high else 'info',
           'EU-DOC-Wizard (A8) oder High-Risk-DOC (A16) ausführen')
    _check('eu_db_registration', not is_high or bool(meta.get('eu_db_registration')),
           'High-Risk: EU-Datenbank-Anmeldung (Art. 49)', 'critical' if is_high else 'info',
           'A19 Wizard ausführen → Anmeldedaten generieren + an EU-DB einreichen')
    _check('hitl_designed', not is_high or bool(meta.get('hitl_workflow')),
           'High-Risk: HITL-Workflow definiert', 'high' if is_high else 'info',
           'A18 HITL-Workflow-Designer mit Decision-Points + Eskalations-Pfaden')

    # Limited-Risk-Pflichten
    is_limited = tier in ('limited-risk', 'high-risk')
    has_transparency = 'transparenz' in notizen or 'art. 50' in notizen
    _check('transparency', not is_limited or has_transparency,
           'Limited/High-Risk: Transparenz-Hinweise (Art. 50)', 'high' if is_limited else 'info',
           'A9 Transparenz-Wizard ausführen für Chatbot/Deepfake-Marker')

    # Verboten
    if tier == 'prohibited':
        _check('prohibited', False, 'System ist prohibited (Art. 5) — kein Release', 'critical',
               'Use-Case überdenken — Inverkehrbringen ist NICHT erlaubt')

    critical_fail = [c for c in checks if not c['ok'] and c['severity'] == 'critical']
    high_fail = [c for c in checks if not c['ok'] and c['severity'] == 'high']
    release_ready = not critical_fail
    return jsonify({
        'projekt': projekt_name,
        'tier': tier or 'unbekannt',
        'release_ready': release_ready,
        'summary': {
            'total': len(checks),
            'passed': sum(1 for c in checks if c['ok']),
            'critical_fail': len(critical_fail),
            'high_fail': len(high_fail),
        },
        'checks': checks,
    })


@aiact_bp.post('/projekte/<projekt_name>/issues/sync')
@jwt_required()
def aiact_sync_project_issues(projekt_name: str):
    """#788: Status ALLER im Projekt verlinkten Issues live abrufen + persistent
    synchronisieren (GitHub/GitLab). Liefert {synced, errors, total, items}."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        from shared.issue_sync import sync_project_links
        result = sync_project_links(DB_PATH, projekt_name)
        # Nach dem Status-Sync: gelöste Issues automatisch als vollständig
        # bearbeitet markieren (#833).
        result['auto_completed'] = _complete_all_resolved_requirements(projekt_name)
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@aiact_bp.post('/projekte/<projekt_name>/issues/import')
@jwt_required()
def aiact_import_project_issues(projekt_name: str):
    """#830: Inhalt ALLER verknüpften Issues in die jeweiligen Anforderungs-
    Bewertungen (Kommentar) übernehmen. Liefert {imported, failed, total, items}."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        from shared.issue_links import list_project_links
        from shared.issue_feedback import (
            collect_issue_feedback, merge_feedback_into_comment, group_links_by_object)

        data = request.json or {}
        gitlab_token_env = data.get('gitlab_token_env') or 'GITLAB_TOKEN'
        links = list_project_links(DB_PATH, projekt_name=projekt_name, object_kind='requirement')
        groups = group_links_by_object(links)
        bewertungen = load_bewertungen(DB_PATH, projekt_name)

        imported = 0
        failed = 0
        items = []
        for req_id, req_links in groups.items():
            feedback, sources = collect_issue_feedback(req_links, gitlab_token_env=gitlab_token_env)
            if not feedback:
                failed += 1
                items.append({'anforderung_id': req_id, 'ok': False, 'sources': sources})
                continue
            existing = bewertungen.get(req_id, {})
            neuer_kommentar = merge_feedback_into_comment(existing.get('kommentar', ''), feedback)
            db_save_bewertung(
                DB_PATH, projekt_name=projekt_name, anforderung_id=req_id,
                bewertung=int(existing.get('bewertung', 0) or 0),
                kommentar=neuer_kommentar,
                massnahme=existing.get('massnahme', '') or '',
            )
            imported += 1
            items.append({'anforderung_id': req_id, 'ok': True, 'sources': sources})
        return {'imported': imported, 'failed': failed, 'total': len(groups), 'items': items}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500
