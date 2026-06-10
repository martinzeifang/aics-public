"""DSGVO Compliance Module API — vollständige CRUD + Anforderungs-Katalog + Reports."""

import shutil
import tempfile
from typing import Any, Dict, List

from server.api.workspace_tmp import workspace_tmpdir
from server.api._common import require_projekt
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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@dsgvo_bp.delete('/projekte/<projekt_name>')
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

@dsgvo_bp.get('/projekte/<projekt_name>/anforderungen')
@jwt_required()
def get_anforderungen(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        return _build_anforderungen_response(projekt_name), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@dsgvo_bp.delete('/anforderungen/custom/<anf_id>')
@jwt_required()
def delete_custom_anforderung_endpoint(anf_id: str):
    try:
        delete_custom_anforderung(DB_PATH, anf_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
    # Pflicht-Doku-Daten (Sprint δ)
    pflicht_doku = {
        'vvt': db_list_vvt(DB_PATH, projekt_name),
        'tom': db_list_tom(DB_PATH, projekt_name),
        'dpia': db_list_dpia(DB_PATH, projekt_name),
        'avv': db_list_avv(DB_PATH, projekt_name),
        'datenpannen': db_list_pannen(DB_PATH, projekt_name),
    }
    common = dict(
        out_dir=out_dir,
        projekt_name=projekt_name,
        unternehmen=projekt.get('unternehmen', ''),
        organisationstyp=projekt.get('organisationstyp', ''),
        berater=projekt.get('berater', ''),
        bewertungen_raw=bewertungen,
    )

    # DS13 (#1113): DSMS-Bereiche für den Gesamtbericht (TOM-Katalog, Betroffenenrechte, …)
    try:
        from dsgvo.template_context import build_dsgvo_context
        _dsms = build_dsgvo_context(DB_PATH, projekt_name)
    except Exception:
        _dsms = None

    try:
        current_app.logger.info('DSGVO export start: projekt=%r fmt=%s', projekt_name, fmt)
        if fmt == 'docx':
            from dsgvo.report_export import export_report_docx
            path = export_report_docx(pflicht_doku=pflicht_doku, dsms=_dsms, **common)
        elif fmt == 'pdf':
            from dsgvo.report_export import export_report_pdf
            path = export_report_pdf(pflicht_doku=pflicht_doku, dsms=_dsms, **common)
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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        # #743 (WP-10): Magic-Byte- + Zip-Bomb-Prüfung vor dem Parsen.
        from shared.upload_validation import validate_upload_file
        validate_upload_file(tmp_path, suffix='.xlsx')
        from dsgvo.io_xlsx import import_fragebogen as do_import
        items = do_import(tmp_path)
        if items:
            bulk_save_bewertungen(DB_PATH, projekt_name, items)
        return {'imported': len(items), 'items': items}, 200
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# Helpers: Firmen-Evidence sammeln
# ============================================================

def _evidence_excerpts(firma_name: str, max_chunks: int = 12,
                       max_chars_per_chunk: int = 600) -> list[dict]:
    """Liest die Top-N Text-Chunks eines Firmen für Prompt-Kontext.

    Returns: Liste [{doc_name, doc_type, excerpt}]
    """
    try:
        from evidence.db import list_documents, get_extracted_text
    except Exception:
        return []

    docs = list_documents(EVIDENCE_DB, firmen_id=firma_name)
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


def _firma_for_projekt(projekt: dict) -> str | None:
    """Versucht den verknüpften Firmen zu bestimmen.

    Heuristik: meta.linked_firma, dann unternehmen, dann Projektname.
    """
    try:
        meta = projekt.get('meta', {})
        if isinstance(meta, str):
            meta = json.loads(meta or '{}')
    except Exception:
        meta = {}
    return (meta.get('linked_firma')
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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@dsgvo_bp.post('/projekte/<projekt_name>/tom/ai-prompt')
@jwt_required()
def build_tom_prompt(projekt_name: str):
    """Erzeugt einen ChatGPT-Prompt für TOM-Inhalte (10 Abschnitte) auf Basis
    von Firmen-Dokumenten (Evidence-Store).

    Body: { firma: 'FirmenName' (optional, default: Projekt-Unternehmen) }
    """
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        body = request.json or {}
        firma = body.get('firma') or _firma_for_projekt(projekt)
        excerpts = _evidence_excerpts(firma, max_chunks=15) if firma else []

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
            lines.append(f'## Vorhandene Unterlagen ({len(excerpts)} Auszüge aus Firmen-Dokumenten)')
            for ex in excerpts:
                lines.append(f"--- [{ex['doc_type']}] {ex['doc_name']}")
                lines.append(ex['excerpt'].replace('\n', ' '))
            lines.append('')
        else:
            lines.append('Hinweis: Keine Firmen-Dokumente vorhanden. Erstelle einen generischen Entwurf.')
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
            'firma': firma,
            'evidence_count': len(excerpts),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@dsgvo_bp.post('/projekte/<projekt_name>/privacy/ai-prompt')
@jwt_required()
def build_privacy_prompt(projekt_name: str):
    """Erzeugt ChatGPT-Prompt zum Vorbefüllen des Datenschutzerklärungs-Intakes.

    Nutzt: vorhandenes Intake (falls vorhanden) + Firmen-Dokumente.
    Body: { firma: 'FirmenName' (optional) }
    """
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        body = request.json or {}
        firma = body.get('firma') or _firma_for_projekt(projekt)
        excerpts = _evidence_excerpts(firma, max_chunks=15) if firma else []

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
            lines.append('Hinweis: Keine Firmen-Dokumente vorhanden. Markiere unbekannte Felder mit "".')
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
            'firma': firma,
            'evidence_count': len(excerpts),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


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
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ════════════════════════════════════════════════════════════════════
# Sprint δ Phase A — Pflicht-Doku-Manager (Issue #584)
# ════════════════════════════════════════════════════════════════════

from dsgvo.db import (
    list_vvt as db_list_vvt, save_vvt as db_save_vvt, delete_vvt as db_delete_vvt,
    list_tom as db_list_tom, save_tom as db_save_tom, delete_tom as db_delete_tom,
    list_dpia as db_list_dpia, save_dpia as db_save_dpia, delete_dpia as db_delete_dpia,
    get_dpia as db_get_dpia, set_dpia_rb_projekt as db_set_dpia_rb_projekt,
    schwellwert_kriterien as db_schwellwert_kriterien,
    auswerten_schwellwert as db_auswerten_schwellwert,
    DSFA_STAGES as DB_DSFA_STAGES,
    list_avv as db_list_avv, save_avv as db_save_avv, delete_avv as db_delete_avv,
    list_pannen as db_list_pannen, save_panne as db_save_panne, delete_panne as db_delete_panne,
)


def _require_dsgvo_projekt(projekt_name: str):
    return require_projekt(load_projekt, DB_PATH, projekt_name)


def _crud_get_list(handler, projekt_name: str):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    return jsonify(handler(DB_PATH, projekt_name))


def _crud_post(handler, projekt_name: str):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    try:
        rid = handler(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'id': rid, 'ok': True}), 201


def _crud_delete(handler, projekt_name: str, row_id: int):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    handler(DB_PATH, row_id)
    return jsonify({'ok': True})


# D1 VVT
@dsgvo_bp.get('/projekte/<projekt_name>/vvt')
@jwt_required()
def dsgvo_vvt_list(projekt_name):
    # #1101: optionaler Rollen-Filter Art. 30(1) (verantwortlicher) / 30(2) (auftragsverarbeiter)
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    rolle = request.args.get('rolle') or None
    return jsonify(db_list_vvt(DB_PATH, projekt_name, rolle))

@dsgvo_bp.post('/projekte/<projekt_name>/vvt')
@jwt_required()
def dsgvo_vvt_save(projekt_name): return _crud_post(db_save_vvt, projekt_name)

@dsgvo_bp.delete('/projekte/<projekt_name>/vvt/<int:row_id>')
@jwt_required()
def dsgvo_vvt_delete(projekt_name, row_id): return _crud_delete(db_delete_vvt, projekt_name, row_id)


# D2 TOM
@dsgvo_bp.get('/projekte/<projekt_name>/tom')
@jwt_required()
def dsgvo_tom_list(projekt_name): return _crud_get_list(db_list_tom, projekt_name)

@dsgvo_bp.post('/projekte/<projekt_name>/tom')
@jwt_required()
def dsgvo_tom_save(projekt_name): return _crud_post(db_save_tom, projekt_name)

@dsgvo_bp.delete('/projekte/<projekt_name>/tom/<int:row_id>')
@jwt_required()
def dsgvo_tom_delete(projekt_name, row_id): return _crud_delete(db_delete_tom, projekt_name, row_id)


# ════════════════════════════════════════════════════════════════════
# D3 DPIA / DSFA  ↔  Risikobewertung-Verknüpfung (#1084 / #1085)
# ════════════════════════════════════════════════════════════════════
#
# Compliance-Aufteilung (Art. 35 Abs. 7 DSGVO):
#   - lit. a (Beschreibung der Verarbeitung)  → dsgvo_dpia.beschreibung_verarbeitung
#   - lit. b (Notwendigkeit/Verhältnismäßig.) → dsgvo_dpia.notwendigkeit_grund  (BLEIBT lokal)
#   - lit. c (Risiken f. Rechte/Freiheiten)   → verknüpftes rb_projekt (DSGVO-DSFA)
#   - lit. d (Abhilfemaßnahmen)               → verknüpftes rb_projekt (DSGVO-DSFA)
#   - Art. 36 (Konsultation Aufsicht/DSB)     → dsgvo_dpia.konsultation_*  (BLEIBT lokal)
#   - Art. 35 Abs. 11 (Review)                → dsgvo_dpia.naechstes_review (BLEIBT lokal)

_RB_DB_PATH = Path('data/db/risikobewertung.sqlite')
_DSFA_FRAMEWORK = 'DSGVO-DSFA'


def _dsfa_rb_name(projekt_name: str, dpia_id: str) -> str:
    """Deterministischer, **URL-sicherer** Name des verknüpften RB-Projekts.

    Wichtig (#1116): KEINE Slashes — der Name wird als ``<projekt_name>``-
    Pfadsegment in die Risikobewertungs-Routen eingesetzt, deren string-Converter
    keine '/' matcht. Ein '/' im Namen führte zu 404 „not found"."""
    safe_p = str(projekt_name or '').replace('/', '-').strip()
    safe_d = str(dpia_id or '').replace('/', '-').strip()
    return f'DSFA: {safe_p} – {safe_d}'


def _legacy_dsfa_rb_name(projekt_name: str, dpia_id: str) -> str:
    """Alt-Format (#1084) mit Slash — nur zum Auffinden/Migrieren alter Links."""
    return f'DSFA: {projekt_name} / {dpia_id}'


def _ensure_dsfa_rb_projekt(projekt: dict, projekt_name: str, dpia_row: dict) -> str:
    """Legt (idempotent) das verknüpfte rb_projekt (Framework DSGVO-DSFA) an und
    gibt seinen Namen zurück. Speichert die Verknüpfung in beiden Richtungen.
    Migriert dabei ältere Slash-Namen auf das URL-sichere Schema (#1116)."""
    from risikobewertung.db import (
        load_projekt as rb_load, save_projekt as rb_save,
        update_projekt_meta as rb_update_meta, rename_projekt as rb_rename,
    )
    dpia_id = str(dpia_row.get('dpia_id') or dpia_row.get('id') or '')
    rb_name = _dsfa_rb_name(projekt_name, dpia_id)
    # Migration (#1116): Alt-Projekt mit Slash-Namen URL-sicher umbenennen,
    # damit die im RB gepflegten Risiken erhalten bleiben.
    legacy = _legacy_dsfa_rb_name(projekt_name, dpia_id)
    if legacy != rb_name and rb_load(_RB_DB_PATH, legacy) and not rb_load(_RB_DB_PATH, rb_name):
        try:
            rb_rename(_RB_DB_PATH, legacy, rb_name)
        except Exception as e:
            current_app.logger.exception(
                'DSFA-RB-Rename (#1116) fehlgeschlagen: %s: %s', type(e).__name__, e)
    existing = rb_load(_RB_DB_PATH, rb_name)
    beschreibung = (
        f"Risiken für die Rechte und Freiheiten der betroffenen Personen "
        f"(Art. 35 Abs. 7 lit. c+d DSGVO) zur DSFA '{dpia_row.get('titel', '')}'."
    )
    if not existing:
        rb_save(
            _RB_DB_PATH,
            name=rb_name,
            framework=_DSFA_FRAMEWORK,
            beschreibung=beschreibung,
            unternehmen=projekt.get('unternehmen', '') or '',
            produkt='',
            berater=projekt.get('berater', '') or '',
            meta={
                'linked_dsgvo_projekt': projekt_name,
                'linked_dsgvo_dpia_id': dpia_id,
                'source': 'dsgvo-dsfa',
            },
        )
    else:
        # Verknüpfungs-Meta aktualisieren, Framework NICHT überschreiben.
        meta = dict(existing.get('meta') or {})
        meta.update({
            'linked_dsgvo_projekt': projekt_name,
            'linked_dsgvo_dpia_id': dpia_id,
            'source': 'dsgvo-dsfa',
        })
        rb_update_meta(_RB_DB_PATH, rb_name, meta)
    return rb_name


# D3 DPIA — List
@dsgvo_bp.get('/projekte/<projekt_name>/dpia')
@jwt_required()
def dsgvo_dpia_list(projekt_name): return _crud_get_list(db_list_dpia, projekt_name)


# D3 DPIA — Create/Update (auto-verknüpft ein rb_projekt bei Neuanlage, #1084)
@dsgvo_bp.post('/projekte/<projekt_name>/dpia')
@jwt_required()
def dsgvo_dpia_save(projekt_name):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    is_new = not body.get('id')
    try:
        row_id = db_save_dpia(DB_PATH, projekt_name, body)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    rb_name = None
    if is_new:
        # Auto-Anlage des verknüpften Risikobewertungs-Projekts (DSGVO-DSFA).
        try:
            dpia_row = db_get_dpia(DB_PATH, row_id) or {}
            rb_name = _ensure_dsfa_rb_projekt(p, projekt_name, dpia_row)
            db_set_dpia_rb_projekt(DB_PATH, row_id, rb_name)
        except Exception as e:
            # Verknüpfung ist Best-Effort; DSFA bleibt nutzbar (BLEIBT lokal).
            current_app.logger.exception(
                'DSFA-RB-Auto-Link fehlgeschlagen: %s: %s', type(e).__name__, e)
    return jsonify({'id': row_id, 'ok': True, 'rb_projekt_id': rb_name}), 201


@dsgvo_bp.delete('/projekte/<projekt_name>/dpia/<int:row_id>')
@jwt_required()
def dsgvo_dpia_delete(projekt_name, row_id): return _crud_delete(db_delete_dpia, projekt_name, row_id)


# D3 DPIA — verknüpftes rb_projekt + Risiken(c)/Maßnahmen(d) READ-ONLY (#1085)
@dsgvo_bp.get('/projekte/<projekt_name>/dpia/<int:row_id>/risk-link')
@jwt_required()
def dsgvo_dpia_risk_link(projekt_name, row_id):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err:
        return err
    dpia_row = db_get_dpia(DB_PATH, row_id)
    if not dpia_row or dpia_row.get('projekt_name') != projekt_name:
        return jsonify({'error': 'DSFA nicht gefunden'}), 404

    rb_name = (dpia_row.get('rb_projekt_id') or '').strip()
    # Lazy-Heilung: DSFAs ohne Link ODER mit altem Slash-Namen (#1116) bekommen
    # die kanonische, URL-sichere Verknüpfung nachgezogen (inkl. Migration).
    _canonical = _dsfa_rb_name(
        projekt_name, str(dpia_row.get('dpia_id') or dpia_row.get('id') or ''))
    if not rb_name or rb_name != _canonical:
        try:
            rb_name = _ensure_dsfa_rb_projekt(p, projekt_name, dpia_row)
            db_set_dpia_rb_projekt(DB_PATH, row_id, rb_name)
        except Exception as e:
            current_app.logger.exception(
                'DSFA-RB-Lazy-Link fehlgeschlagen: %s: %s', type(e).__name__, e)
            rb_name = rb_name or ''

    risiken = []
    framework = ''
    if rb_name:
        try:
            from risikobewertung.db import load_projekt as rb_load, load_risiken
            rbp = rb_load(_RB_DB_PATH, rb_name) or {}
            framework = rbp.get('framework', '')
            for r in load_risiken(_RB_DB_PATH, rb_name):
                felder = r.get('felder') or {}
                risiken.append({
                    'id': r.get('id'),
                    'nr': r.get('nr'),
                    'risk_name': r.get('risk_name', ''),
                    'beschreibung': r.get('beschreibung', ''),
                    # Art. 35 Abs. 7 lit. c — Bedrohung für Rechte/Freiheiten
                    'bedrohung_rechte_freiheiten': felder.get('bedrohung_rechte_freiheiten', ''),
                    'eintrittswahrscheinlichkeit': felder.get('eintrittswahrscheinlichkeit', ''),
                    'schwere': felder.get('schwere', ''),
                    # Art. 35 Abs. 7 lit. d — Abhilfemaßnahme
                    'massnahme': felder.get('massnahme', ''),
                    'risikowert': r.get('risikowert'),
                    'risiko_label': r.get('risiko_label', ''),
                    'is_resolved': bool(r.get('is_resolved')),
                })
        except Exception as e:
            current_app.logger.exception(
                'DSFA-RB-Risiken laden fehlgeschlagen: %s: %s', type(e).__name__, e)

    try:
        import json as _json
        schwellwert = _json.loads(dpia_row.get('schwellwert_json') or '{}')
    except Exception:
        schwellwert = {}

    return jsonify({
        'rb_projekt_id': rb_name or None,
        'framework': framework,
        # DS6: aktueller Prozess-Schritt + verfügbare Stufen
        'stage': dpia_row.get('stage', 'schwellwert'),
        'stages': list(DB_DSFA_STAGES),
        # DS5: Schwellwertanalyse (Art. 35 Abs. 1/3/4) — bleibt lokal
        'schwellwert': schwellwert,
        # Lokale Art. 35 Abs. 7 a+b Felder (BLEIBEN im dsgvo_dpia-Hull)
        'beschreibung_verarbeitung': dpia_row.get('beschreibung_verarbeitung', ''),
        'notwendigkeit_grund': dpia_row.get('notwendigkeit_grund', ''),
        # DS6: Maßnahmen + Restrisiko + Art. 36 (BLEIBEN lokal)
        'massnahmen': dpia_row.get('massnahmen', ''),
        'restrisiko': dpia_row.get('restrisiko', ''),
        'art36_required': int(dpia_row.get('art36_required') or 0),
        'konsultation_dsb': dpia_row.get('konsultation_dsb', ''),
        'konsultation_aufsicht': int(dpia_row.get('konsultation_aufsicht') or 0),
        # DS6: Freigabe + Review (BLEIBEN lokal, Art. 35 Abs. 11)
        'freigabe_durch': dpia_row.get('freigabe_durch', ''),
        'freigabe_datum': dpia_row.get('freigabe_datum', ''),
        'naechstes_review': dpia_row.get('naechstes_review', ''),
        # Read-only Risiken(c) + Maßnahmen(d) aus dem rb_projekt
        'risiken': risiken,
    })


# ════════════════════════════════════════════════════════════════════
# DS5 Schwellwertanalyse (Art. 35 Abs. 1/3/4) + DS6 mehrstufiger Prozess
# (#1105 / #1106)
# ════════════════════════════════════════════════════════════════════

# DS5 — Kriterienkatalog (statisch, projektunabhängig)
@dsgvo_bp.get('/dsfa/schwellwert-kriterien')
@jwt_required()
def dsgvo_schwellwert_kriterien():
    return jsonify(db_schwellwert_kriterien())


# DS5 — Schwellwert auswerten (ohne Persistenz, z. B. Live-Vorschau)
@dsgvo_bp.post('/dsfa/schwellwert-auswerten')
@jwt_required()
def dsgvo_schwellwert_auswerten():
    return jsonify(db_auswerten_schwellwert(request.get_json(silent=True) or {}))


# DS6 — Prozess-Metadaten (verfügbare Stufen)
@dsgvo_bp.get('/dsfa/stages')
@jwt_required()
def dsgvo_dsfa_stages():
    return jsonify({'stages': list(DB_DSFA_STAGES)})


# DS5 — Schwellwert eines konkreten DSFA auswerten + persistieren
@dsgvo_bp.post('/projekte/<projekt_name>/dpia/<int:row_id>/schwellwert')
@jwt_required()
def dsgvo_dpia_schwellwert(projekt_name, row_id):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err:
        return err
    dpia_row = db_get_dpia(DB_PATH, row_id)
    if not dpia_row or dpia_row.get('projekt_name') != projekt_name:
        return jsonify({'error': 'DSFA nicht gefunden'}), 404
    body = request.get_json(silent=True) or {}
    ergebnis = db_auswerten_schwellwert(body)
    # in dsgvo_dpia persistieren (Schwellwert bleibt lokal)
    payload = dict(dpia_row)
    payload['id'] = row_id
    payload['schwellwert_json'] = ergebnis
    # Bei „erforderlich" in die nächste Stufe rücken, falls noch im Schwellwert.
    if ergebnis.get('erforderlich') and dpia_row.get('stage', 'schwellwert') == 'schwellwert':
        payload['stage'] = 'beschreibung'
    try:
        db_save_dpia(DB_PATH, projekt_name, payload)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True, 'schwellwert': ergebnis,
                    'stage': payload.get('stage', dpia_row.get('stage'))})


# DS6 — Stufenwechsel im DSFA-Prozess
@dsgvo_bp.post('/projekte/<projekt_name>/dpia/<int:row_id>/stage')
@jwt_required()
def dsgvo_dpia_stage(projekt_name, row_id):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err:
        return err
    dpia_row = db_get_dpia(DB_PATH, row_id)
    if not dpia_row or dpia_row.get('projekt_name') != projekt_name:
        return jsonify({'error': 'DSFA nicht gefunden'}), 404
    body = request.get_json(silent=True) or {}
    stage = str(body.get('stage', '') or '')
    if stage not in DB_DSFA_STAGES:
        return jsonify({'error': f'Ungültige Stufe: {stage}'}), 400
    payload = dict(dpia_row)
    payload['id'] = row_id
    payload['stage'] = stage
    try:
        db_save_dpia(DB_PATH, projekt_name, payload)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True, 'stage': stage})


# D4 AVV
@dsgvo_bp.get('/projekte/<projekt_name>/avv')
@jwt_required()
def dsgvo_avv_list(projekt_name): return _crud_get_list(db_list_avv, projekt_name)

@dsgvo_bp.post('/projekte/<projekt_name>/avv')
@jwt_required()
def dsgvo_avv_save(projekt_name): return _crud_post(db_save_avv, projekt_name)

@dsgvo_bp.delete('/projekte/<projekt_name>/avv/<int:row_id>')
@jwt_required()
def dsgvo_avv_delete(projekt_name, row_id): return _crud_delete(db_delete_avv, projekt_name, row_id)


# D5 Datenpannen
@dsgvo_bp.get('/projekte/<projekt_name>/datenpannen')
@jwt_required()
def dsgvo_pannen_list(projekt_name): return _crud_get_list(db_list_pannen, projekt_name)

@dsgvo_bp.post('/projekte/<projekt_name>/datenpannen')
@jwt_required()
def dsgvo_pannen_save(projekt_name): return _crud_post(db_save_panne, projekt_name)

@dsgvo_bp.delete('/projekte/<projekt_name>/datenpannen/<int:row_id>')
@jwt_required()
def dsgvo_pannen_delete(projekt_name, row_id): return _crud_delete(db_delete_panne, projekt_name, row_id)


# Status-Aggregator
@dsgvo_bp.get('/projekte/<projekt_name>/pflicht-doku')
@jwt_required()
def dsgvo_pflicht_doku_status(projekt_name: str):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    vvt = db_list_vvt(DB_PATH, projekt_name)
    tom = db_list_tom(DB_PATH, projekt_name)
    dpia = db_list_dpia(DB_PATH, projekt_name)
    avv = db_list_avv(DB_PATH, projekt_name)
    pannen = db_list_pannen(DB_PATH, projekt_name)
    offene_pannen = [x for x in pannen if x.get('status') in ('offen', 'gemeldet')]
    tom_offen = [x for x in tom if x.get('umsetzungsstatus') != 'umgesetzt']
    # #1193: Datenpannen-Status frist/status-abhängig — nicht mehr fix True.
    from dsgvo import datenpannen_frist as panne_frist
    panne_fristen = panne_frist.offene_fristen(DB_PATH, projekt_name)
    return jsonify({
        'vvt': {'count': len(vvt), 'ok': len(vvt) > 0},
        'tom': {'count': len(tom), 'open': len(tom_offen), 'ok': len(tom) > 0 and len(tom_offen) == 0},
        'dpia': {'count': len(dpia), 'ok': len(dpia) > 0},
        'avv': {'count': len(avv), 'ok': len(avv) > 0},
        'datenpannen': {'count': len(pannen), 'open': len(offene_pannen),
                        'overdue': panne_fristen['overdue'], 'ok': panne_fristen['ok']},
    })


# ════════════════════════════════════════════════════════════════════
# Sprint δ Phase B — KI-Wizards (Issue #584)
# ════════════════════════════════════════════════════════════════════

from dsgvo.ai_wizards import (
    build_rechtsgrundlage_prompt, parse_rechtsgrundlage_response,
    list_branchen_templates_dsgvo, get_branchen_template_dsgvo,
    build_datenpanne_meldung_prompt, parse_datenpanne_meldung_response,
    build_betroffenenrechte_prompt, parse_betroffenenrechte_response,
)


def _should_apply_dsgvo(body: dict) -> bool:
    if request.args.get('dry_run') == 'true' or body.get('dry_run') is True:
        return False
    if request.args.get('apply') == 'false':
        return False
    return True


# ─── D6 Rechtsgrundlagen-Klassifikator ─────────────────────────────

@dsgvo_bp.post('/projekte/<projekt_name>/wizards/rechtsgrundlage/prompt')
@jwt_required()
def dsgvo_rg_prompt(projekt_name: str):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    verarbeitung = request.get_json(silent=True) or {}
    return jsonify({'prompt': build_rechtsgrundlage_prompt(p, verarbeitung)})


@dsgvo_bp.post('/projekte/<projekt_name>/wizards/rechtsgrundlage/parse')
@jwt_required()
def dsgvo_rg_parse(projekt_name: str):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_rechtsgrundlage_response(body.get('response', ''))
    applied = False
    if _should_apply_dsgvo(body) and body.get('vvt_id'):
        # In das VVT-Item schreiben
        items = db_list_vvt(DB_PATH, projekt_name)
        v = next((x for x in items if x['id'] == int(body['vvt_id'])), None)
        if v:
            v['rechtsgrundlage'] = parsed.get('art_referenz') or parsed.get('rechtsgrundlage')
            v['notizen'] = (v.get('notizen', '') + '\n\n--- KI-Empfehlung ---\n' + parsed.get('begruendung', '')).strip()
            db_save_vvt(DB_PATH, projekt_name, v)
            applied = True
            current_app.logger.info('wizard.applied kind=dsgvo-rg project=%r vvt_id=%s', projekt_name, body['vvt_id'])
            # #1205: Auto-Trigger LIA-Anlage, wenn Interessenabwägung nötig.
            if parsed.get('interessenabwaegung_noetig'):
                try:
                    from dsgvo import lia_db
                    lia_db.ensure_for_vvt(
                        DB_PATH, projekt_name, vvt_ref=str(v.get('vvt_id') or v.get('id')),
                        verarbeitung=v.get('name', ''), zweck=v.get('zweck', ''))
                except Exception:  # noqa: BLE001
                    current_app.logger.exception('LIA auto-trigger fehlgeschlagen')
    return jsonify({**parsed, 'applied': applied})


# ─── D7 Branchen-Templates ─────────────────────────────────────────

@dsgvo_bp.get('/wizards/branchen-templates')
@jwt_required()
def dsgvo_branchen_list():
    return jsonify(list_branchen_templates_dsgvo())


@dsgvo_bp.post('/projekte/<projekt_name>/wizards/branchen-template/apply')
@jwt_required()
def dsgvo_branchen_apply(projekt_name: str):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    branche_id = (request.get_json(silent=True) or {}).get('branche_id', '')
    tpl = get_branchen_template_dsgvo(branche_id)
    if not tpl:
        return jsonify({'error': f'Branche "{branche_id}" unbekannt'}), 400
    # TOM-Defaults anlegen (falls noch nicht vorhanden)
    existing_tom = db_list_tom(DB_PATH, projekt_name)
    existing_keys = {(t.get('kategorie'), t.get('massnahme')) for t in existing_tom}
    added = 0
    for kategorie, massnahme in (tpl.get('tom_defaults') or {}).items():
        if (kategorie, massnahme) not in existing_keys:
            try:
                db_save_tom(DB_PATH, projekt_name, {
                    'kategorie': kategorie, 'massnahme': massnahme,
                    'umsetzungsstatus': 'geplant',
                    'notizen': f'Aus Branchen-Template "{tpl["name"]}" angelegt',
                })
                added += 1
            except Exception:
                pass
    return jsonify({'ok': True, 'template': tpl, 'tom_added': added, 'applied': True})


# ─── D8 Datenpannen-Meldung ────────────────────────────────────────

@dsgvo_bp.post('/projekte/<projekt_name>/wizards/datenpanne-meldung/prompt')
@jwt_required()
def dsgvo_panne_prompt(projekt_name: str):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    panne = request.get_json(silent=True) or {}
    return jsonify({'prompt': build_datenpanne_meldung_prompt(p, panne)})


@dsgvo_bp.post('/projekte/<projekt_name>/wizards/datenpanne-meldung/parse')
@jwt_required()
def dsgvo_panne_parse(projekt_name: str):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_datenpanne_meldung_response(body.get('response', ''))
    applied = False
    if _should_apply_dsgvo(body) and body.get('panne_id_db'):
        pannen = db_list_pannen(DB_PATH, projekt_name)
        pn = next((x for x in pannen if x['id'] == int(body['panne_id_db'])), None)
        if pn:
            pn['notizen'] = (
                (pn.get('notizen') or '')
                + '\n\n--- Aufsicht-Meldung ---\n' + parsed.get('aufsicht_meldung_text', '')
                + ('\n\n--- Betroffene-Info ---\n' + parsed['betroffene_info_text']
                   if parsed.get('betroffene_info_erforderlich') and parsed.get('betroffene_info_text') else '')
            ).strip()
            if parsed.get('betroffene_info_erforderlich'):
                pn['meldung_betroffene_pflicht'] = 1
            db_save_panne(DB_PATH, projekt_name, pn)
            applied = True
            current_app.logger.info('wizard.applied kind=dsgvo-panne project=%r panne_id=%s', projekt_name, pn.get('panne_id'))
    return jsonify({**parsed, 'applied': applied})


# ─── D9 Betroffenenrechte-Workflow ─────────────────────────────────

@dsgvo_bp.post('/projekte/<projekt_name>/wizards/betroffenenrechte/prompt')
@jwt_required()
def dsgvo_br_prompt(projekt_name: str):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    anfrage = request.get_json(silent=True) or {}
    return jsonify({'prompt': build_betroffenenrechte_prompt(p, anfrage)})


@dsgvo_bp.post('/projekte/<projekt_name>/wizards/betroffenenrechte/parse')
@jwt_required()
def dsgvo_br_parse(projekt_name: str):
    p, err = _require_dsgvo_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_betroffenenrechte_response(body.get('response', ''))
    # Apply ist nur "logged" hier — Antwort-Templates werden vom User
    # an Betroffenen verschickt, nicht intern persistiert
    applied = True
    current_app.logger.info('wizard.applied kind=dsgvo-betroffenenrechte project=%r art=%s',
                            projekt_name, parsed.get('art_referenz'))
    return jsonify({**parsed, 'applied': applied})


@dsgvo_bp.post('/projekte/<projekt_name>/issues/sync')
@jwt_required()
def dsgvo_sync_project_issues(projekt_name: str):
    """#788: Status ALLER im Projekt verlinkten Issues live abrufen + persistent
    synchronisieren (GitHub/GitLab). Liefert {synced, errors, total, items}."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        from shared.issue_sync import sync_project_links
        return sync_project_links(DB_PATH, projekt_name), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


# ════════════════════════════════════════════════════════════════════
# #862 — Pro-Projekt-Repository-Konfiguration (vcs_publish) + Issue-Erstellung
# ════════════════════════════════════════════════════════════════════

from shared.vcs_repo_config import (
    vcs_token as _vcs_token,
    public_vcs as _public_vcs,
    sanitize_vcs as _sanitize_vcs,
    resolve_repo as _resolve_repo,
)
from dsgvo.db import update_projekt_meta as _update_projekt_meta


def _projekt_meta(projekt: Dict[str, Any]) -> Dict[str, Any]:
    """meta-Dict eines Projekts robust extrahieren (meta oder meta_json)."""
    meta = projekt.get('meta')
    if isinstance(meta, dict):
        return meta
    raw = projekt.get('meta_json') or '{}'
    try:
        import json as _j
        m = _j.loads(raw)
        return m if isinstance(m, dict) else {}
    except Exception:
        return {}


# ── Repo-Konfiguration ──────────────────────────────────────────────

@dsgvo_bp.get('/projekte/<projekt_name>/repo-config')
@jwt_required()
def dsgvo_get_repo_config(projekt_name: str):
    """Repo-Einstellungen (vcs_publish) eines Projekts lesen — ohne Token."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        meta = _projekt_meta(projekt)
        return {'vcs_publish': _public_vcs(meta.get('vcs_publish') or {})}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@dsgvo_bp.put('/projekte/<projekt_name>/repo-config')
@jwt_required()
def dsgvo_put_repo_config(projekt_name: str):
    """Repo-Einstellungen speichern. Partial-Update bewahrt bestehenden Token."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        meta = _projekt_meta(projekt)
        prev_vcs = meta.get('vcs_publish') if isinstance(meta.get('vcs_publish'), dict) else {}
        vcs = _sanitize_vcs(data.get('vcs_publish', data), prev_vcs)
        meta['vcs_publish'] = vcs
        _update_projekt_meta(DB_PATH, projekt_name, meta)
        return {'vcs_publish': _public_vcs(vcs)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/repo-context')
@jwt_required()
def dsgvo_post_repo_context(projekt_name: str):
    """Repo-Kontext testen/abrufen. Repo aus Request ODER gespeichert."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        meta = _projekt_meta(projekt)
        vcs = meta.get('vcs_publish') if isinstance(meta.get('vcs_publish'), dict) else {}
        repo = _resolve_repo(vcs, data.get('repo'))
        if not repo:
            return {'error': 'Kein Repository für dieses Projekt konfiguriert (Repo-Konfig speichern oder repo übergeben)'}, 400
        from vcs.repo_reader import detect_provider, fetch_repo_context, format_repo_context
        try:
            detect_provider(repo)
        except ValueError as e:
            return {'error': str(e)}, 400
        try:
            ctx = fetch_repo_context(repo, token=_vcs_token(vcs))
        except Exception as e:
            current_app.logger.warning('repo-context fetch failed (%s): %s', repo, e)
            return {'error': f'Repository konnte nicht gelesen werden: {e}'}, 502
        return {
            'repo': ctx.repo,
            'provider': ctx.provider,
            'description': ctx.description,
            'context': format_repo_context(ctx),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


# ── Issue-Inhalt + Erstellung ───────────────────────────────────────

def _dsgvo_issue_content(req_id: str, req: Dict[str, Any], existing: Dict[str, Any]) -> tuple[str, str]:
    """Erzeugt (Titel, Body) für ein DSGVO-Gap-Issue.

    Wird von Einzel- (anf_create_issue) und Massenanlage (dsgvo_bulk_create_issues)
    gemeinsam genutzt — konsistent zu CRA/NIS2/AI-Act.
    """
    titel = (req.get('titel') or req.get('title') or req_id).strip()
    title = f"AICS · DSGVO-Gap [{req_id}]: {titel}".strip().rstrip(':').strip()

    lines: List[str] = []
    beschreibung = (req.get('beschreibung') or req.get('description') or '').strip()
    if beschreibung:
        lines.append(beschreibung)
        lines.append('')
    kapitel = (req.get('kapitel') or '').strip()
    ref = (req.get('ref') or '').strip()
    meta_bits = [b for b in (f'Kapitel: {kapitel}' if kapitel else '',
                             f'Referenz: {ref}' if ref else '') if b]
    if meta_bits:
        lines.append('**' + ' · '.join(meta_bits) + '**')
    score = int(existing.get('bewertung', 0) or 0)
    lines.append(f'**Aktuelle Bewertung:** {score}/5')
    kommentar = (existing.get('kommentar') or '').strip()
    if kommentar:
        lines.append('')
        lines.append('**Bewertungs-Kommentar:**')
        lines.append(kommentar)
    massnahme = (existing.get('massnahme') or '').strip()
    if massnahme:
        lines.append('')
        lines.append('**Geplante Maßnahme:**')
        lines.append(massnahme)
    hinweise = (req.get('hinweise') or '').strip()
    if hinweise:
        lines.append('')
        lines.append('**Hinweise:**')
        lines.append(hinweise)
    lines.append('')
    lines.append('---')
    lines.append('_Automatisch erstellt durch AI Compliance Suite (DSGVO-Modul, #862)._')
    return title, '\n'.join(lines)


def _create_vcs_issue(vcs: Dict[str, Any], repo: str, title: str, body: str) -> tuple[str, int | None, int | None, str]:
    """Legt ein Issue über GitHub oder GitLab an. Liefert (url, number, iid, provider)."""
    provider = (vcs.get('provider') or 'github').lower()
    if provider == 'gitlab':
        from vcs.gitlab_issues import create_issue as gl_create
        created = gl_create(
            base_url=vcs.get('base_url') or 'https://gitlab.com',
            token_env=vcs.get('token_env') or 'GITLAB_TOKEN',
            project=repo,
            title=title,
            description=body,
        )
        return (str(getattr(created, 'url', '') or ''),
                None, getattr(created, 'iid', None), 'gitlab')
    from vcs.github_issues import create_issue as gh_create
    created = gh_create(repo=repo, title=title, body=body)
    return (str(getattr(created, 'url', '') or ''),
            getattr(created, 'number', None), None, 'github')


@dsgvo_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues')
@jwt_required()
def dsgvo_anf_create_issue(projekt_name: str, req_id: str):
    """Einzel-Issue für eine DSGVO-Anforderung anlegen + verknüpfen."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        meta = _projekt_meta(projekt)
        vcs = meta.get('vcs_publish') if isinstance(meta.get('vcs_publish'), dict) else {}
        repo = _resolve_repo(vcs, data.get('repo'))
        if not repo:
            return {'error': 'Kein Repository für dieses Projekt konfiguriert (Repo-Konfig speichern oder repo übergeben)'}, 400
        req = next((r for r in load_merged_anforderungen(DB_PATH) if str(r.get('id')) == str(req_id)), None)
        if not req:
            return {'error': f'Anforderung nicht gefunden: {req_id}'}, 404

        bewertungen = load_bewertungen(DB_PATH, projekt_name)
        existing = bewertungen.get(req_id, {})
        title, body = _dsgvo_issue_content(req_id, req, existing)
        if data.get('title'):
            title = str(data['title'])
        if data.get('body'):
            body = str(data['body'])

        try:
            url, number, iid, provider = _create_vcs_issue(vcs, repo, title, body)
        except Exception as e:
            return {'error': f'Issue-Erstellung fehlgeschlagen: {e}'}, 502

        from shared.issue_links import add_link
        add_link(
            DB_PATH,
            projekt_name=projekt_name,
            object_kind='requirement', object_id=req_id,
            provider=provider, repo=repo, url=url,
            issue_number=number, issue_iid=iid, title=title,
        )
        return {'ok': True, 'url': url, 'issue_number': number, 'issue_iid': iid}, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@dsgvo_bp.post('/projekte/<projekt_name>/issues/bulk')
@jwt_required()
def dsgvo_bulk_create_issues(projekt_name: str):
    """Massenanlage von Issues für alle Gap-Anforderungen (Bewertung < 5).

    Body (optional): only_gaps (default true), skip_linked (default true),
    req_ids (Liste), repo (override). Liefert Summary {created, skipped, failed}.
    """
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        meta = _projekt_meta(projekt)
        vcs = meta.get('vcs_publish') if isinstance(meta.get('vcs_publish'), dict) else {}
        repo = _resolve_repo(vcs, data.get('repo'))
        if not repo:
            return {'error': 'Kein Repository für dieses Projekt konfiguriert (Repo-Konfig speichern oder repo übergeben)'}, 400

        only_gaps = data.get('only_gaps', True)
        skip_linked = data.get('skip_linked', True)
        req_ids = data.get('req_ids')
        req_id_filter = set(str(x) for x in req_ids) if isinstance(req_ids, list) else None

        anforderungen = load_merged_anforderungen(DB_PATH)
        bewertungen = load_bewertungen(DB_PATH, projekt_name)

        from shared.issue_links import list_links, add_link, ensure_tables
        ensure_tables(DB_PATH)

        created: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        for req in anforderungen:
            rid = str(req.get('id'))
            if req_id_filter is not None and rid not in req_id_filter:
                continue
            existing = bewertungen.get(rid, {})
            score = int(existing.get('bewertung', 0) or 0)
            if only_gaps and score >= 5:
                skipped.append({'req_id': rid, 'grund': 'kein Gap (Bewertung 5)'})
                continue
            if skip_linked and list_links(DB_PATH, projekt_name=projekt_name,
                                          object_kind='requirement', object_id=rid):
                skipped.append({'req_id': rid, 'grund': 'bereits verknüpft'})
                continue

            title, body = _dsgvo_issue_content(rid, req, existing)
            try:
                url, number, iid, provider = _create_vcs_issue(vcs, repo, title, body)
            except Exception as e:
                failed.append({'req_id': rid, 'error': str(e)})
                continue

            add_link(
                DB_PATH,
                projekt_name=projekt_name,
                object_kind='requirement', object_id=rid,
                provider=provider, repo=repo, url=url,
                issue_number=number, issue_iid=iid, title=title,
            )
            created.append({'req_id': rid, 'url': url})

        return {
            'ok': True,
            'created': len(created),
            'skipped': len(skipped),
            'failed': len(failed),
            'created_items': created,
            'skipped_items': skipped,
            'failed_items': failed,
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500
