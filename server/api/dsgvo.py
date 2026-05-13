"""DSGVO Compliance Module API — vollständige CRUD + Anforderungs-Katalog + Reports."""

import shutil
import tempfile
from typing import Any, Dict, List

from server.api._tmp import workspace_tmpdir
from flask import current_app, Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from pathlib import Path

from dsgvo.db import (
    list_projekte,
    save_projekt,
    load_projekt,
    delete_projekt as db_delete_projekt,
    save_bewertung,
    bulk_save_bewertungen,
    load_bewertungen,
    save_custom_anforderung,
    load_custom_anforderungen,
    delete_custom_anforderung,
    save_privacy_intake,
    load_privacy_intake,
    save_ai_draft,
    load_ai_draft,
)

# Evidence-Store
EVIDENCE_DB = Path('data/db/evidence.sqlite')
from dsgvo.requirements import (
    DSGVO_ANFORDERUNGEN,
    KAPITEL,
    BEWERTUNG_SKALA,
    ORGANISATIONSTYPEN,
    anforderungen_by_kapitel,
    load_merged_anforderungen,
    berechne_reifegrad,
)

dsgvo_bp = Blueprint('dsgvo', __name__)

DB_PATH = Path('data/db/dsgvo.sqlite')


# ============================================================
# Hilfsfunktionen
# ============================================================

def _serialize_projekt(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': p.get('name'),
        'name': p.get('name', ''),
        'unternehmen': p.get('unternehmen', ''),
        'company': p.get('unternehmen', ''),
        'organisationstyp': p.get('organisationstyp', ''),
        'beschreibung': p.get('beschreibung', ''),
        'description': p.get('beschreibung', ''),
        'berater': p.get('berater', ''),
        'meta_json': p.get('meta_json', '{}'),
        'created_at': p.get('created_at'),
        'updated_at': p.get('updated_at'),
    }


def _build_anforderungen_response(projekt_name: str) -> List[Dict[str, Any]]:
    """Standard-Katalog + custom + Bewertungen pro Projekt."""
    reqs = load_merged_anforderungen(DB_PATH)
    bewertungen = load_bewertungen(DB_PATH, projekt_name)

    result: List[Dict[str, Any]] = []
    for req in reqs:
        rid = req.get('id')
        b = bewertungen.get(rid, {})
        score = int(b.get('bewertung', 0))
        result.append({
            'id': rid,
            'kapitel': req.get('kapitel', ''),
            'ref': req.get('ref', ''),
            'titel': req.get('titel', ''),
            'title': req.get('titel', ''),
            'beschreibung': req.get('beschreibung', ''),
            'description': req.get('beschreibung', ''),
            'hinweise': req.get('hinweise', ''),
            'gewichtung': req.get('gewichtung', 1),
            'quelle': req.get('_quelle', 'standard'),
            'bewertung': score,
            'score': score,
            'kommentar': b.get('kommentar', ''),
            'notes': b.get('kommentar', ''),
            'massnahme': b.get('massnahme', ''),
            'updated_at': b.get('updated_at'),
            'status': 'complete' if score >= 4 else 'partial' if score >= 2 else 'pending',
        })
    return result


# ============================================================
# Konstanten
# ============================================================

@dsgvo_bp.get('/constants')
@jwt_required()
def get_constants():
    return {
        'kapitel': KAPITEL,
        'bewertung_skala': BEWERTUNG_SKALA,
        'organisationstypen': list(ORGANISATIONSTYPEN.keys()) if isinstance(ORGANISATIONSTYPEN, dict) else list(ORGANISATIONSTYPEN),
    }, 200


@dsgvo_bp.get('/kapitel')
@jwt_required()
def get_kapitel():
    return anforderungen_by_kapitel(), 200


# ============================================================
# Projekte
# ============================================================

@dsgvo_bp.get('/projekte')
@jwt_required()
def get_projekte():
    """Liste aller DSGVO-Projekte."""
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


@dsgvo_bp.get('/projekte/<projekt_name>')
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


@dsgvo_bp.post('/projekte')
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
            unternehmen=data.get('unternehmen', '') or data.get('company', ''),
            organisationstyp=data.get('organisationstyp', ''),
            beschreibung=data.get('beschreibung', '') or data.get('description', ''),
            berater=data.get('berater', ''),
        )
        return _serialize_projekt(load_projekt(DB_PATH, name)), 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.put('/projekte/<projekt_name>')
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
            unternehmen=data.get('unternehmen', existing.get('unternehmen', '')),
            organisationstyp=data.get('organisationstyp', existing.get('organisationstyp', '')),
            beschreibung=data.get('beschreibung', existing.get('beschreibung', '')),
            berater=data.get('berater', existing.get('berater', '')),
        )
        return _serialize_projekt(load_projekt(DB_PATH, projekt_name)), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.delete('/projekte/<projekt_name>')
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

@dsgvo_bp.get('/projekte/<projekt_name>/anforderungen')
@jwt_required()
def get_anforderungen(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        return _build_anforderungen_response(projekt_name), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.get('/projekte/<projekt_name>/reifegrad')
@jwt_required()
def get_reifegrad(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        bewertungen = load_bewertungen(DB_PATH, projekt_name)
        scores = {rid: int(b.get('bewertung', 0)) for rid, b in bewertungen.items()}
        return berechne_reifegrad(scores), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/bewertungen')
@jwt_required()
def save_single_bewertung(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        anf_id = data.get('anforderung_id')
        if not anf_id:
            return {'error': 'Feld "anforderung_id" ist Pflicht'}, 400
        save_bewertung(
            DB_PATH,
            projekt_name,
            anf_id,
            int(data.get('bewertung', 0)),
            data.get('kommentar', ''),
            data.get('massnahme', ''),
        )
        return {'ok': True, 'anforderung_id': anf_id}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/bewertungen/bulk')
@jwt_required()
def save_bulk_bewertungen(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        items = request.json or []
        if not isinstance(items, list):
            return {'error': 'Erwartet: Liste'}, 400
        bulk_save_bewertungen(DB_PATH, projekt_name, items)
        return {'ok': True, 'count': len(items)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Custom-Anforderungen
# ============================================================

@dsgvo_bp.get('/anforderungen/custom')
@jwt_required()
def get_custom_anforderungen():
    try:
        return load_custom_anforderungen(DB_PATH), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.post('/anforderungen/custom')
@jwt_required()
def add_custom_anforderung():
    try:
        data = request.json or {}
        if not data.get('id') or not data.get('titel'):
            return {'error': 'Felder "id" und "titel" sind Pflicht'}, 400
        save_custom_anforderung(DB_PATH, data)
        return {'ok': True, 'id': data['id']}, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.delete('/anforderungen/custom/<anf_id>')
@jwt_required()
def delete_custom_anforderung_endpoint(anf_id: str):
    try:
        delete_custom_anforderung(DB_PATH, anf_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# KI-Bewertung (ChatGPT-Prompt + Antwort-Parser)
# ============================================================

def _find_anforderung(req_id: str) -> Dict[str, Any] | None:
    return next((r for r in load_merged_anforderungen(DB_PATH) if r.get('id') == req_id), None)


@dsgvo_bp.get('/projekte/<projekt_name>/anforderungen/<req_id>/prompt')
@jwt_required()
def anf_get_prompt(projekt_name: str, req_id: str):
    """ChatGPT-Prompt für DSGVO-Anforderung."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        req = _find_anforderung(req_id)
        if not req:
            return {'error': f'Anforderung nicht gefunden: {req_id}'}, 404

        from server.services.anforderung_prompt import build_anforderung_prompt
        bewertungen = load_bewertungen(DB_PATH, projekt_name)
        prompt = build_anforderung_prompt(
            framework='DSGVO',
            framework_full='DSGVO / Verordnung (EU) 2016/679',
            req=req,
            projekt=projekt,
            current=bewertungen.get(req_id, {}),
        )
        return {'prompt': prompt, 'req_id': req_id}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/parse-response')
@jwt_required()
def anf_parse_response(projekt_name: str, req_id: str):
    """Parst ChatGPT-JSON-Antwort und übernimmt sie optional."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        req = _find_anforderung(req_id)
        if not req:
            return {'error': f'Anforderung nicht gefunden: {req_id}'}, 404

        data = request.json or {}
        raw = data.get('raw') or ''
        if not raw:
            return {'error': 'Feld "raw" mit der ChatGPT-Antwort ist Pflicht'}, 400
        apply = bool(data.get('apply', False))

        from server.services.anforderung_prompt import parse_chatgpt_json
        try:
            parsed = parse_chatgpt_json(raw)
        except ValueError as e:
            return {'error': str(e)}, 400

        score = int(parsed.get('score', 0))
        if score < 0 or score > 5:
            return {'error': 'score muss zwischen 0-5 liegen'}, 400

        kommentar = parsed.get('kommentar', '') or ''
        massnahme = parsed.get('massnahme', '') or ''

        result = {
            'parsed': parsed,
            'bewertung': score,
            'kommentar': kommentar,
            'massnahme': massnahme,
        }

        if apply:
            save_bewertung(DB_PATH, projekt_name, req_id, score, kommentar, massnahme)
            result['saved'] = True

        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Issue-Verknüpfung (Stub — DSGVO-spezifisch)
# ============================================================

@dsgvo_bp.get('/projekte/<projekt_name>/anforderungen/<req_id>/issues')
@jwt_required()
def anf_list_issues(projekt_name: str, req_id: str):
    """Liefert verknüpfte GitHub/GitLab-Issues. Greift auf shared/issue_links zu, falls verfügbar."""
    try:
        from shared.issue_links import list_links_for
        links = list_links_for(module='dsgvo', projekt=projekt_name, anforderung_id=req_id)
        return [link for link in links], 200
    except Exception:
        # Falls shared/issue_links nicht verfügbar: leere Liste
        return [], 200


@dsgvo_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues/link')
@jwt_required()
def anf_link_issue(projekt_name: str, req_id: str):
    """Vorhandenes Issue verknüpfen."""
    try:
        from shared.issue_links import link_existing_issue
        data = request.json or {}
        url = data.get('url', '').strip()
        if not url:
            return {'error': 'Feld "url" ist Pflicht'}, 400
        link_existing_issue(module='dsgvo', projekt=projekt_name, anforderung_id=req_id, url=url)
        return {'ok': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Reports + Excel-Import/Export
# ============================================================

@dsgvo_bp.get('/projekte/<projekt_name>/report')
@jwt_required()
def export_report(projekt_name: str):
    """Report-Export: format=pdf|docx|xlsx."""
    fmt = (request.args.get('format') or 'pdf').lower()
    if fmt not in {'pdf', 'docx', 'xlsx'}:
        return {'error': 'Format muss pdf|docx|xlsx sein'}, 400

    projekt = load_projekt(DB_PATH, projekt_name)
    if not projekt:
        return {'error': 'Projekt nicht gefunden'}, 404

    out_dir = workspace_tmpdir('dsgvo_report_')
    bewertungen = load_bewertungen(DB_PATH, projekt_name)
    common = dict(
        out_dir=out_dir,
        projekt_name=projekt_name,
        unternehmen=projekt.get('unternehmen', ''),
        organisationstyp=projekt.get('organisationstyp', ''),
        berater=projekt.get('berater', ''),
        bewertungen_raw=bewertungen,
    )

    try:
        current_app.logger.info('DSGVO export start: projekt=%r fmt=%s', projekt_name, fmt)
        if fmt == 'docx':
            from dsgvo.report_export import export_report_docx
            path = export_report_docx(**common)
        elif fmt == 'pdf':
            from dsgvo.report_export import export_report_pdf
            path = export_report_pdf(**common)
        else:  # xlsx
            from dsgvo.io_xlsx import export_fragebogen
            path = export_fragebogen(
                out_dir=out_dir,
                projekt_name=projekt_name,
                unternehmen=projekt.get('unternehmen', ''),
                organisationstyp=projekt.get('organisationstyp', ''),
                berater=projekt.get('berater', ''),
                bestehende_bewertungen=bewertungen,
            )
        current_app.logger.info('DSGVO export ok: path=%s', path.name)
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/fragebogen/import')
@jwt_required()
def import_fragebogen_endpoint(projekt_name: str):
    """Excel-Fragebogen importieren (multipart/form-data, Feld 'file')."""
    if not load_projekt(DB_PATH, projekt_name):
        return {'error': 'Projekt nicht gefunden'}, 404
    f = request.files.get('file')
    if not f or not f.filename:
        return {'error': 'Datei-Feld "file" fehlt'}, 400
    if not f.filename.lower().endswith('.xlsx'):
        return {'error': 'Nur .xlsx wird unterstützt'}, 400

    tmp_dir = workspace_tmpdir('dsgvo_import_')
    try:
        tmp_path = tmp_dir / 'upload.xlsx'
        f.save(str(tmp_path))
        from dsgvo.io_xlsx import import_fragebogen as do_import
        items = do_import(tmp_path)
        if items:
            bulk_save_bewertungen(DB_PATH, projekt_name, items)
        return {'imported': len(items), 'items': items}, 200
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# Helpers: Kunden-Evidence sammeln
# ============================================================

def _evidence_excerpts(kunde_name: str, max_chunks: int = 12,
                       max_chars_per_chunk: int = 600) -> list[dict]:
    """Liest die Top-N Text-Chunks eines Kunden für Prompt-Kontext.

    Returns: Liste [{doc_name, doc_type, excerpt}]
    """
    try:
        from evidence.db import list_documents, get_extracted_text
    except Exception:
        return []

    docs = list_documents(EVIDENCE_DB, kunden_id=kunde_name)
    excerpts: list[dict] = []
    for d in docs:
        if len(excerpts) >= max_chunks:
            break
        text = None
        try:
            text = get_extracted_text(EVIDENCE_DB, d.id)
        except Exception:
            pass
        if not text or len(text) < 50:
            continue
        excerpt = text[:max_chars_per_chunk].strip()
        if len(text) > max_chars_per_chunk:
            excerpt += ' …'
        excerpts.append({
            'doc_id': d.id,
            'doc_name': d.filename,
            'doc_type': d.doc_type,
            'excerpt': excerpt,
        })
    return excerpts


def _kunde_for_projekt(projekt: dict) -> str | None:
    """Versucht den verknüpften Kunden zu bestimmen.

    Heuristik: meta.linked_kunde, dann unternehmen, dann Projektname.
    """
    try:
        meta = projekt.get('meta', {})
        if isinstance(meta, str):
            meta = json.loads(meta or '{}')
    except Exception:
        meta = {}
    return (meta.get('linked_kunde')
            or projekt.get('unternehmen')
            or projekt.get('name'))


# ============================================================
# TOM-Generator (Art. 32 DSGVO)
# ============================================================

@dsgvo_bp.get('/tom/abschnitte')
@jwt_required()
def get_tom_abschnitte():
    """Liste aller TOM-Abschnitte (Zutritts-, Zugangs-, Zugriffskontrolle, …)."""
    try:
        from dsgvo.tom import TOM_ABSCHNITTE
        return TOM_ABSCHNITTE, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/tom/ai-prompt')
@jwt_required()
def build_tom_prompt(projekt_name: str):
    """Erzeugt einen ChatGPT-Prompt für TOM-Inhalte (10 Abschnitte) auf Basis
    von Kunden-Dokumenten (Evidence-Store).

    Body: { kunde: 'KundenName' (optional, default: Projekt-Unternehmen) }
    """
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        body = request.json or {}
        kunde = body.get('kunde') or _kunde_for_projekt(projekt)
        excerpts = _evidence_excerpts(kunde, max_chunks=15) if kunde else []

        from dsgvo.tom import TOM_ABSCHNITTE
        from server.services.anforderung_prompt import build_anforderung_prompt  # noqa

        # Eigener Prompt-Builder für TOM (10 Abschnitte gleichzeitig)
        lines = []
        lines.append('🔒 SECURITY: Verwende AUSSCHLIESSLICH die bereitgestellten Informationen.')
        lines.append('')
        lines.append('Du bist Datenschutz-Experte. Erstelle einen Entwurf eines TOM-Konzepts')
        lines.append(f'(Technische und Organisatorische Maßnahmen nach Art. 32 DSGVO) für')
        lines.append(f'das Unternehmen "{projekt.get("unternehmen") or projekt_name}".')
        lines.append('')
        if excerpts:
            lines.append(f'## Vorhandene Unterlagen ({len(excerpts)} Auszüge aus Kunden-Dokumenten)')
            for ex in excerpts:
                lines.append(f"--- [{ex['doc_type']}] {ex['doc_name']}")
                lines.append(ex['excerpt'].replace('\n', ' '))
            lines.append('')
        else:
            lines.append('Hinweis: Keine Kunden-Dokumente vorhanden. Erstelle einen generischen Entwurf.')
            lines.append('')

        lines.append('## TOM-Abschnitte (alle 10 ausfüllen)')
        for s in TOM_ABSCHNITTE:
            lines.append(f"- {s['id']}: {s['titel']} — {s.get('untertitel','')}")
        lines.append('')

        lines.append('## Auftrag')
        lines.append('Für jeden der 10 TOM-Abschnitte:')
        lines.append('1. Beschreibe konkret die in den Unterlagen identifizierbaren Maßnahmen.')
        lines.append('2. Markiere Lücken (was fehlt?).')
        lines.append('3. Empfehle 2-3 konkrete Verbesserungen.')
        lines.append('')
        lines.append('## Format')
        lines.append('Antwort als JSON in genau diesem Format:')
        lines.append('```json')
        lines.append('{')
        lines.append('  "abschnitte": {')
        lines.append('    "TOM-A": {')
        lines.append('      "vorhandene_massnahmen": ["…", "…"],')
        lines.append('      "luecken": ["…"],')
        lines.append('      "empfehlungen": ["…"]')
        lines.append('    },')
        lines.append('    "TOM-B": {…}, …')
        lines.append('  },')
        lines.append('  "fazit": "Gesamtzusammenfassung in 3-5 Sätzen"')
        lines.append('}')
        lines.append('```')

        prompt = '\n'.join(lines)
        return {
            'prompt': prompt,
            'kunde': kunde,
            'evidence_count': len(excerpts),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/tom/ai-import')
@jwt_required()
def import_tom_ai(projekt_name: str):
    """Importiert ChatGPT-JSON-Antwort und speichert als KI-Draft.

    Body: { raw: '<text>', source_documents: [doc_ids] }
    """
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        body = request.json or {}
        raw = body.get('raw') or ''
        if not raw:
            return {'error': 'Feld "raw" mit der ChatGPT-Antwort ist Pflicht'}, 400

        from server.services.anforderung_prompt import parse_chatgpt_json
        try:
            payload = parse_chatgpt_json(raw)
        except ValueError as e:
            return {'error': str(e)}, 400
        if not isinstance(payload, dict) or 'abschnitte' not in payload:
            return {'error': 'JSON muss "abschnitte" enthalten'}, 400

        save_ai_draft(DB_PATH, projekt_name, 'tom', payload, body.get('source_documents'))
        return {'ok': True, 'abschnitte_count': len(payload.get('abschnitte', {}))}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.get('/projekte/<projekt_name>/tom/ai-draft')
@jwt_required()
def get_tom_ai_draft(projekt_name: str):
    """Lädt den gespeicherten KI-Draft."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        draft = load_ai_draft(DB_PATH, projekt_name, 'tom')
        return {'draft': draft}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.get('/projekte/<projekt_name>/tom/export')
@jwt_required()
def export_tom(projekt_name: str):
    """TOM-Entwurf als DOCX exportieren."""
    projekt = load_projekt(DB_PATH, projekt_name)
    if not projekt:
        return {'error': 'Projekt nicht gefunden'}, 404
    out_dir = workspace_tmpdir('dsgvo_tom_')
    try:
        current_app.logger.info('DSGVO TOM-export start: projekt=%r', projekt_name)
        from dsgvo.tom import export_tom_docx
        bewertungen = load_bewertungen(DB_PATH, projekt_name)

        # KI-Draft falls vorhanden: konvertiere zu approved_mappings je TOM-ID
        approved_mappings: dict | None = None
        ai = load_ai_draft(DB_PATH, projekt_name, 'tom')
        if ai and isinstance(ai.get('payload'), dict):
            abschnitte = ai['payload'].get('abschnitte') or {}
            approved_mappings = {}
            for tom_id, content in abschnitte.items():
                items = []
                for m in (content.get('vorhandene_massnahmen') or []):
                    items.append({'text': str(m), 'doc_id': 'ai', 'doc_name': 'KI-Entwurf'})
                for g in (content.get('luecken') or []):
                    items.append({'text': f'⚠ Lücke: {g}', 'doc_id': 'ai', 'doc_name': 'KI-Entwurf'})
                for r in (content.get('empfehlungen') or []):
                    items.append({'text': f'→ Empfehlung: {r}', 'doc_id': 'ai', 'doc_name': 'KI-Entwurf'})
                if items:
                    approved_mappings[tom_id] = items
            current_app.logger.info('TOM-export nutzt KI-Draft: %d Abschnitte', len(approved_mappings))

        path = export_tom_docx(
            out_dir=out_dir,
            projekt_name=projekt_name,
            unternehmen=projekt.get('unternehmen', ''),
            berater=projekt.get('berater', ''),
            bewertungen=bewertungen,
            approved_mappings=approved_mappings,
        )
        current_app.logger.info('DSGVO TOM-export ok: path=%s', path.name)
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Datenschutzerklärung-Generator
# ============================================================

@dsgvo_bp.get('/privacy/intake-schema')
@jwt_required()
def get_privacy_intake_schema():
    """Liefert Felder + Gruppen für das Intake-Formular."""
    try:
        from dsgvo.privacy import INTAKE_FELDER, INTAKE_GRUPPEN
        return {'felder': INTAKE_FELDER, 'gruppen': INTAKE_GRUPPEN}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/privacy/ai-prompt')
@jwt_required()
def build_privacy_prompt(projekt_name: str):
    """Erzeugt ChatGPT-Prompt zum Vorbefüllen des Datenschutzerklärungs-Intakes.

    Nutzt: vorhandenes Intake (falls vorhanden) + Kunden-Dokumente.
    Body: { kunde: 'KundenName' (optional) }
    """
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        body = request.json or {}
        kunde = body.get('kunde') or _kunde_for_projekt(projekt)
        excerpts = _evidence_excerpts(kunde, max_chunks=15) if kunde else []

        from dsgvo.privacy import INTAKE_FELDER
        existing_intake = load_privacy_intake(DB_PATH, projekt_name)

        lines = []
        lines.append('🔒 SECURITY: Verwende AUSSCHLIESSLICH die bereitgestellten Informationen.')
        lines.append('')
        lines.append('Du bist Datenschutz-Experte. Befülle den Intake einer Datenschutzerklärung')
        lines.append(f'für "{projekt.get("unternehmen") or projekt_name}" auf Basis der vorhandenen Unterlagen.')
        lines.append('')

        if excerpts:
            lines.append(f'## Vorhandene Unterlagen ({len(excerpts)} Auszüge)')
            for ex in excerpts:
                lines.append(f"--- [{ex['doc_type']}] {ex['doc_name']}")
                lines.append(ex['excerpt'].replace('\n', ' '))
            lines.append('')
        else:
            lines.append('Hinweis: Keine Kunden-Dokumente vorhanden. Markiere unbekannte Felder mit "".')
            lines.append('')

        if existing_intake:
            lines.append('## Bereits gesetzt (NICHT überschreiben):')
            for k, v in existing_intake.items():
                if v not in (None, '', [], False):
                    lines.append(f'- {k}: {str(v)[:200]}')
            lines.append('')

        lines.append('## Felder (alle ausfüllen falls aus Unterlagen ableitbar)')
        for f in INTAKE_FELDER:
            ftype = f.get('type', 'text')
            req = ' [PFLICHT]' if f.get('required') else ''
            lines.append(f"- {f['key']} ({ftype}, Gruppe '{f.get('group','')}'){req}: {f['label']}")
            if f.get('tip'):
                lines.append(f"  Hinweis: {f['tip']}")
            if ftype == 'checklist':
                opts = ', '.join(f"{c[0]}={c[1]}" for c in f.get('optionen', []))
                lines.append(f"  Optionen: {opts}")
        lines.append('')

        lines.append('## Auftrag')
        lines.append('Wenn ein Feld aus den Unterlagen ableitbar ist: setze es konkret.')
        lines.append('Wenn nicht ableitbar: leerer String "" (oder false bei bool).')
        lines.append('Bei checklist-Feldern: Liste der ausgewählten Schlüssel.')
        lines.append('')
        lines.append('## Format')
        lines.append('Antwort als JSON-Objekt mit den `key`-Feldnamen:')
        lines.append('```json')
        lines.append('{')
        lines.append('  "app_name": "...",')
        lines.append('  "betreiber_name": "...",')
        lines.append('  "zwecke": ["kontaktformular", "newsletter"],')
        lines.append('  "rechtsgrundlage_einwilligung": true,')
        lines.append('  "drittland": false,')
        lines.append('  "...": "..."')
        lines.append('}')
        lines.append('```')

        prompt = '\n'.join(lines)
        return {
            'prompt': prompt,
            'kunde': kunde,
            'evidence_count': len(excerpts),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/privacy/ai-import')
@jwt_required()
def import_privacy_ai(projekt_name: str):
    """Importiert ChatGPT-Antwort als Intake (merge mit existing).

    Body: { raw: '<text>', merge: bool (default true), source_documents: [...] }
    """
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        body = request.json or {}
        raw = body.get('raw') or ''
        if not raw:
            return {'error': 'Feld "raw" mit der ChatGPT-Antwort ist Pflicht'}, 400
        merge = bool(body.get('merge', True))

        from server.services.anforderung_prompt import parse_chatgpt_json
        try:
            payload = parse_chatgpt_json(raw)
        except ValueError as e:
            return {'error': str(e)}, 400
        if not isinstance(payload, dict):
            return {'error': 'JSON muss ein Objekt sein'}, 400

        existing = load_privacy_intake(DB_PATH, projekt_name) if merge else {}
        merged = {**(existing or {}), **payload}
        save_privacy_intake(DB_PATH, projekt_name, merged)
        save_ai_draft(DB_PATH, projekt_name, 'privacy', payload, body.get('source_documents'))

        from dsgvo.privacy import intake_missing_fields
        return {
            'ok': True,
            'fields_set': len([k for k, v in payload.items() if v not in (None, '', [], False)]),
            'missing': intake_missing_fields(merged),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.get('/projekte/<projekt_name>/privacy/intake')
@jwt_required()
def get_privacy_intake(projekt_name: str):
    """Holt gespeicherte Intake-Daten."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        from dsgvo.privacy import intake_missing_fields
        intake = load_privacy_intake(DB_PATH, projekt_name)
        return {'intake': intake, 'missing': intake_missing_fields(intake)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.put('/projekte/<projekt_name>/privacy/intake')
@jwt_required()
def put_privacy_intake(projekt_name: str):
    """Speichert Intake-Daten."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        intake = request.json or {}
        save_privacy_intake(DB_PATH, projekt_name, intake)
        from dsgvo.privacy import intake_missing_fields
        return {'ok': True, 'missing': intake_missing_fields(intake)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.get('/projekte/<projekt_name>/privacy/export')
@jwt_required()
def export_privacy(projekt_name: str):
    """Datenschutzerklärung als DOCX exportieren."""
    if not load_projekt(DB_PATH, projekt_name):
        return {'error': 'Projekt nicht gefunden'}, 404
    out_dir = workspace_tmpdir('dsgvo_privacy_')
    try:
        current_app.logger.info('DSGVO Privacy-export start: projekt=%r', projekt_name)
        from dsgvo.privacy import export_privacy_docx
        intake = load_privacy_intake(DB_PATH, projekt_name)
        path = export_privacy_docx(
            out_dir=out_dir,
            projekt_name=projekt_name,
            intake=intake,
        )
        current_app.logger.info('DSGVO Privacy-export ok: path=%s', path.name)
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Schulungs-Generator
# ============================================================

@dsgvo_bp.get('/training/outline')
@jwt_required()
def get_training_outline():
    """Liefert ZIELGRUPPEN + TRAINING_OUTLINE (für UI-Auswahl)."""
    try:
        from dsgvo.training import TRAINING_OUTLINE, ZIELGRUPPEN
        return {'zielgruppen': ZIELGRUPPEN, 'outline': TRAINING_OUTLINE}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/training/export')
@jwt_required()
def export_training(projekt_name: str):
    """Schulungs-Skript + Quiz als DOCX exportieren.

    Body: { zielgruppen: ['alle','hr',...], themen: ['A1','HR1',...] (optional) }
    """
    projekt = load_projekt(DB_PATH, projekt_name)
    if not projekt:
        return {'error': 'Projekt nicht gefunden'}, 404
    data = request.json or {}
    zielgruppen = data.get('zielgruppen') or ['alle']
    themen = data.get('themen') or None

    out_dir = workspace_tmpdir('dsgvo_training_')
    try:
        current_app.logger.info('DSGVO Training-export start: projekt=%r zielgruppen=%s', projekt_name, zielgruppen)
        from dsgvo.training import export_training_docx
        path = export_training_docx(
            out_dir=out_dir,
            projekt_name=projekt_name,
            unternehmen=projekt.get('unternehmen', ''),
            berater=projekt.get('berater', ''),
            zielgruppen=zielgruppen,
            themen=themen,
        )
        current_app.logger.info('DSGVO Training-export ok: path=%s', path.name)
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Backwards-compat Aliase (alte Frontend-Store-Routen)
# ============================================================

@dsgvo_bp.get('')
@jwt_required()
def list_legacy():
    """Legacy: GET /api/dsgvo  → Projektliste."""
    return get_projekte()


@dsgvo_bp.get('/<projekt_name>')
@jwt_required()
def get_anforderungen_legacy(projekt_name: str):
    """Legacy: GET /api/dsgvo/<name>  → Anforderungen mit Bewertung."""
    if projekt_name in {'projekte', 'constants', 'kapitel', 'anforderungen'}:
        # Wird von einer spezifischen Route abgefangen, nie hier
        return {'error': 'Reserved name'}, 404
    return get_anforderungen(projekt_name)


@dsgvo_bp.post('/bewertung')
@jwt_required()
def save_bewertung_legacy():
    """Legacy: POST /api/dsgvo/bewertung mit projekt im Body."""
    try:
        data = request.json or {}
        projekt_name = data.get('projekt')
        if not projekt_name:
            return {'error': 'Feld "projekt" ist Pflicht'}, 400
        save_bewertung(
            DB_PATH,
            projekt_name,
            data.get('anforderung_id'),
            int(data.get('bewertung', 0)),
            data.get('kommentar', ''),
            data.get('massnahme', ''),
        )
        return {'ok': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500
