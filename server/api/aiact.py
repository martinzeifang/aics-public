"""AI Act Compliance Module API — vollständige CRUD + Reifegrad + Repo-Auto-Answer + Reports."""

from flask import current_app, Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from pathlib import Path
from typing import Any, Dict, List
import tempfile

from server.api._tmp import workspace_tmpdir

from ai_act.db import (
    list_projekte,
    save_projekt,
    load_projekt,
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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


@aiact_bp.delete('/projekte/<projekt_name>')
@jwt_required()
def delete_projekt(projekt_name: str):
    try:
        db_delete_projekt(DB_PATH, projekt_name)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'anforderung_id': anforderung_id, 'bewertung': bewertung, 'updated': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
# Repo-Auto-Answer
# ============================================================

@aiact_bp.post('/projekte/<projekt_name>/repo-scan')
@jwt_required()
def repo_scan(projekt_name: str):
    """Repo-Signale scannen und Bewertungs-Vorschläge generieren."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        repo = (data.get('repo') or '').strip()
        branch = data.get('branch', '')
        if not repo:
            return {'error': 'Feld "repo" ist Pflicht (z.B. owner/name)'}, 400

        from ai_act.repo_autoanswer import suggest_from_repo_signals
        suggestions = suggest_from_repo_signals(repo=repo, branch=branch)

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
        return {'suggestions': result, 'count': len(result), 'repo': repo}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        provider = (data.get('provider') or 'github').lower()
        repo = data.get('repo') or ''
        if not repo:
            return {'error': 'Feld "repo" ist Pflicht'}, 400

        title = data.get('title') or f"AI-Act Gap: {req_id} {req.get('titel', '')}".strip()
        existing = load_bewertungen(DB_PATH, projekt_name).get(req_id, {})
        body = data.get('body') or f"""## EU AI Act-Anforderung: {req_id}

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

        issue_url = ''
        issue_number = None
        issue_iid = None

        if provider == 'github':
            from vcs.github_issues import create_issue as gh_create
            ci = gh_create(repo=repo, title=title, body=body)
            issue_url, issue_number = ci.url, ci.number
        elif provider == 'gitlab':
            from vcs.gitlab_issues import create_issue as gl_create
            base_url = data.get('gitlab_base_url') or 'https://gitlab.com'
            token_env = data.get('gitlab_token_env') or 'GITLAB_TOKEN'
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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


@aiact_bp.delete('/projekte/<projekt_name>/anforderungen/<req_id>/issues/<link_id>')
@jwt_required()
def anf_unlink_issue(projekt_name: str, req_id: str, link_id: str):
    try:
        from shared.issue_links import delete_link
        delete_link(DB_PATH, link_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500


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
        return {'error': str(e), 'type': type(e).__name__}, 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ════════════════════════════════════════════════════════════════════
# Sprint γ Phase A — Pflicht-Doku-Manager (Issue #583)
# ════════════════════════════════════════════════════════════════════

from ai_act.db import (
    load_system_doku as db_load_sd, save_system_doku as db_save_sd,
    load_data_governance as db_load_dg, save_data_governance as db_save_dg,
    list_aiact_risks as db_list_aiact_risks, save_aiact_risk as db_save_aiact_risk,
    delete_aiact_risk as db_delete_aiact_risk,
    load_human_oversight as db_load_ho, save_human_oversight as db_save_ho,
    load_pmm as db_load_pmm, save_pmm as db_save_pmm,
)


def _require_aiact_projekt(projekt_name: str):
    p = load_projekt(DB_PATH, projekt_name)
    if not p:
        return None, (jsonify({'error': f'Projekt "{projekt_name}" nicht gefunden'}), 404)
    return p, None


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

@aiact_bp.get('/projekte/<projekt_name>/risks')
@jwt_required()
def aiact_risks_list(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    return jsonify(db_list_aiact_risks(DB_PATH, projekt_name))


@aiact_bp.post('/projekte/<projekt_name>/risks')
@jwt_required()
def aiact_risks_save(projekt_name: str):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    try:
        rid = db_save_aiact_risk(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'id': rid, 'ok': True}), 201


@aiact_bp.delete('/projekte/<projekt_name>/risks/<int:risk_id>')
@jwt_required()
def aiact_risks_delete(projekt_name: str, risk_id: int):
    p, err = _require_aiact_projekt(projekt_name)
    if err: return err
    db_delete_aiact_risk(DB_PATH, risk_id)
    return jsonify({'ok': True})


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
    risks = db_list_aiact_risks(DB_PATH, projekt_name)
    ho = db_load_ho(DB_PATH, projekt_name) or {}
    pmm = db_load_pmm(DB_PATH, projekt_name) or {}
    open_risks = [r for r in risks if r.get('status') in ('offen', 'in-behandlung')]
    return jsonify({
        'system_doku': {'ok': bool(sd.get('system_name'))},
        'data_governance': {'ok': bool(dg.get('training_data_source'))},
        'risk_management': {'total': len(risks), 'open': len(open_risks), 'ok': len(open_risks) == 0},
        'human_oversight': {'ok': bool(ho.get('oversight_mode')) and bool(ho.get('intervention_mechanisms'))},
        'post_market_monitoring': {'ok': bool(pmm.get('monitoring_plan'))},
    })


# ════════════════════════════════════════════════════════════════════
# Sprint γ Phase B — KI-Wizards (Issue #583)
# ════════════════════════════════════════════════════════════════════

from ai_act.ai_wizards import (
    build_risk_tier_prompt, parse_risk_tier_response,
    list_use_case_templates, get_use_case_template,
    build_eu_doc_prompt, parse_eu_doc_response,
    build_transparency_prompt, parse_transparency_response,
)


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
