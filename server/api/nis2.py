"""NIS2 Compliance Module API — vollständige CRUD + Reifegrad + Reports."""

from flask import current_app, Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from pathlib import Path
from typing import Any, Dict, List
import tempfile

from server.api._tmp import workspace_tmpdir

from nis2.db import (
    list_projekte,
    save_projekt,
    load_projekt,
    delete_projekt as db_delete_projekt,
    save_bewertung as db_save_bewertung,
    bulk_save_bewertungen,
    load_bewertungen,
    save_custom_anforderung,
    delete_custom_anforderung as db_delete_custom,
    load_custom_anforderungen,
)

from nis2.requirements import (
    KAPITEL,
    BEWERTUNG_SKALA,
    anforderungen_by_kapitel,
    load_merged_anforderungen,
    berechne_reifegrad,
)

nis2_bp = Blueprint('nis2', __name__, url_prefix='/api/nis2')

DB_PATH = Path('data/db/nis2.sqlite')


# ============================================================
# Hilfsfunktionen
# ============================================================

ALLOWED_EINRICHTUNGSKLASSEN = {'wesentlich', 'wichtig'}


def _serialize_projekt(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': p.get('name'),
        'name': p.get('name', ''),
        'company': p.get('unternehmen', ''),
        'unternehmen': p.get('unternehmen', ''),
        'einrichtungsklasse': p.get('einrichtungsklasse', ''),
        'beschreibung': p.get('beschreibung', ''),
        'description': p.get('beschreibung', ''),
        'berater': p.get('berater', ''),
        'created_at': p.get('created_at'),
        'updated_at': p.get('updated_at'),
    }


def _build_anforderungen_response(projekt_name: str) -> List[Dict[str, Any]]:
    """Listet alle Anforderungen (Standard + Custom + Override) mit Bewertungen pro Projekt."""
    reqs = load_merged_anforderungen(DB_PATH)
    bewertungen = load_bewertungen(DB_PATH, projekt_name)

    result = []
    for req in reqs:
        rid = req.get('id')
        b = bewertungen.get(rid, {})
        score = b.get('bewertung', 0)
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
            'verantwortlich': b.get('verantwortlich', ''),
            'zieldatum': b.get('zieldatum', ''),
            'updated_at': b.get('updated_at'),
            'status': 'complete' if score >= 4 else 'partial' if score >= 2 else 'pending',
        })
    return result


# ============================================================
# Projekte
# ============================================================

@nis2_bp.get('/projekte')
@jwt_required()
def get_projekte():
    """Liste aller NIS2-Projekte."""
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


@nis2_bp.get('/projekte/<projekt_name>')
@jwt_required()
def get_projekt(projekt_name: str):
    """Projekt-Detail."""
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return {'error': 'Projekt nicht gefunden'}, 404
        return _serialize_projekt(p), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.post('/projekte')
@jwt_required()
def create_projekt():
    """Neues Projekt anlegen."""
    try:
        data = request.json or {}
        name = (data.get('name') or '').strip()
        if not name:
            return {'error': 'Feld "name" ist Pflicht'}, 400
        if load_projekt(DB_PATH, name):
            return {'error': 'Projekt existiert bereits'}, 409

        einrichtungsklasse = (data.get('einrichtungsklasse', '') or '').lower()
        if einrichtungsklasse and einrichtungsklasse not in ALLOWED_EINRICHTUNGSKLASSEN:
            return {'error': 'einrichtungsklasse muss "wesentlich" oder "wichtig" sein'}, 400

        save_projekt(
            DB_PATH,
            name=name,
            unternehmen=data.get('unternehmen', '') or data.get('company', ''),
            einrichtungsklasse=einrichtungsklasse,
            beschreibung=data.get('beschreibung', '') or data.get('description', ''),
            berater=data.get('berater', ''),
        )
        p = load_projekt(DB_PATH, name)
        return _serialize_projekt(p), 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.put('/projekte/<projekt_name>')
@jwt_required()
def update_projekt(projekt_name: str):
    """Projekt aktualisieren."""
    try:
        existing = load_projekt(DB_PATH, projekt_name)
        if not existing:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}

        einrichtungsklasse = (data.get('einrichtungsklasse', existing.get('einrichtungsklasse', '')) or '').lower()
        if einrichtungsklasse and einrichtungsklasse not in ALLOWED_EINRICHTUNGSKLASSEN:
            return {'error': 'einrichtungsklasse muss "wesentlich" oder "wichtig" sein'}, 400

        save_projekt(
            DB_PATH,
            name=projekt_name,
            unternehmen=data.get('unternehmen', existing.get('unternehmen', '')),
            einrichtungsklasse=einrichtungsklasse,
            beschreibung=data.get('beschreibung', existing.get('beschreibung', '')),
            berater=data.get('berater', existing.get('berater', '')),
        )
        p = load_projekt(DB_PATH, projekt_name)
        return _serialize_projekt(p), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.delete('/projekte/<projekt_name>')
@jwt_required()
def delete_projekt(projekt_name: str):
    """Projekt löschen."""
    try:
        db_delete_projekt(DB_PATH, projekt_name)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Anforderungen + Bewertungen
# ============================================================

@nis2_bp.get('/projekte/<projekt_name>/anforderungen')
@jwt_required()
def get_anforderungen(projekt_name: str):
    """Alle Anforderungen mit aktueller Bewertung pro Projekt."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        return _build_anforderungen_response(projekt_name), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.post('/projekte/<projekt_name>/bewertungen')
@jwt_required()
def save_single_bewertung(projekt_name: str):
    """Einzelne Bewertung speichern (Upsert)."""
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
            verantwortlich=data.get('verantwortlich', ''),
            zieldatum=data.get('zieldatum', ''),
        )
        return {'anforderung_id': anforderung_id, 'bewertung': bewertung, 'updated': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.post('/projekte/<projekt_name>/bewertungen/bulk')
@jwt_required()
def save_bulk_bewertungen(projekt_name: str):
    """Mehrere Bewertungen auf einmal speichern."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        items = data.get('bewertungen') or data.get('items') or []
        if not isinstance(items, list):
            return {'error': 'bewertungen muss eine Liste sein'}, 400

        bulk_save_bewertungen(DB_PATH, projekt_name, items)
        return {'count': len(items), 'updated': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Custom-Anforderungen
# ============================================================

@nis2_bp.get('/anforderungen/custom')
@jwt_required()
def get_custom_anforderungen():
    """Liste der Custom-Anforderungen."""
    try:
        return load_custom_anforderungen(DB_PATH), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.post('/anforderungen/custom')
@jwt_required()
def create_custom_anforderung():
    """Neue Custom-Anforderung oder Override."""
    try:
        data = request.json or {}
        if not data.get('id'):
            return {'error': 'Feld "id" ist Pflicht'}, 400
        save_custom_anforderung(DB_PATH, {
            'id': data['id'],
            'kapitel': data.get('kapitel', 'NIS1'),
            'ref': data.get('ref', ''),
            'titel': data.get('titel', '') or data.get('title', ''),
            'beschreibung': data.get('beschreibung', '') or data.get('description', ''),
            'hinweise': data.get('hinweise', ''),
            'gewichtung': int(data.get('gewichtung', 1)),
            'ist_override': bool(data.get('ist_override', False)),
        })
        return {'id': data['id'], 'created': True}, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.delete('/anforderungen/custom/<req_id>')
@jwt_required()
def delete_custom_endpoint(req_id: str):
    """Custom-Anforderung löschen."""
    try:
        db_delete_custom(DB_PATH, req_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Reifegrad + Kapitel
# ============================================================

@nis2_bp.get('/projekte/<projekt_name>/reifegrad')
@jwt_required()
def get_reifegrad(projekt_name: str):
    """Reifegrad pro Kapitel + gesamt im Frontend-Format."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404

        bewertungen = load_bewertungen(DB_PATH, projekt_name)
        anforderungen = load_merged_anforderungen(DB_PATH)
        raw = berechne_reifegrad(bewertungen, anforderungen)

        def _ampel(p: float) -> str:
            if p >= 70:
                return 'gruen'
            elif p >= 40:
                return 'orange'
            return 'rot'

        kapitel_out = {}
        for kid, ks in raw.get('kapitel_scores', {}).items():
            kapitel_out[kid] = {
                'prozent': ks.get('prozent', 0),
                'ampel': _ampel(ks.get('prozent', 0)),
                'bewertet': ks.get('bewertet', 0),
                'gesamt': ks.get('anzahl', 0),
            }

        luecken_out = []
        for req in raw.get('luecken', []):
            rid = req.get('id')
            score = int(bewertungen.get(rid, {}).get('bewertung', 0))
            luecken_out.append({
                'id': rid,
                'kapitel': req.get('kapitel', ''),
                'titel': req.get('titel', ''),
                'bewertung': score,
                'gewichtung': req.get('gewichtung', 1),
            })
        luecken_out.sort(key=lambda x: (-x['gewichtung'], x['bewertung']))

        gesamt_prozent = raw.get('prozent', 0)
        return {
            'gesamt': {
                'prozent': gesamt_prozent,
                'ampel': _ampel(gesamt_prozent),
                'punkte_aktuell': raw.get('gesamt_punkte', 0),
                'punkte_max': raw.get('max_punkte', 0),
            },
            'kapitel': kapitel_out,
            'luecken': luecken_out,
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.get('/constants')
@jwt_required()
def get_constants():
    return {
        'kapitel': KAPITEL,
        'bewertung_skala': BEWERTUNG_SKALA,
    }, 200


@nis2_bp.get('/kapitel')
@jwt_required()
def get_kapitel():
    """Anforderungen nach Kapitel (Standard-Katalog ohne Bewertungen)."""
    try:
        return anforderungen_by_kapitel(), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Reports
# ============================================================

@nis2_bp.get('/projekte/<projekt_name>/report')
@jwt_required()
def export_report(projekt_name: str):
    """Report-Export: format=pdf|docx|xlsx."""
    fmt = (request.args.get('format') or 'pdf').lower()
    if fmt not in {'pdf', 'docx', 'xlsx'}:
        return {'error': 'Format muss pdf|docx|xlsx sein'}, 400

    projekt = load_projekt(DB_PATH, projekt_name)
    if not projekt:
        return {'error': 'Projekt nicht gefunden'}, 404

    out_dir = workspace_tmpdir('nis2_report_')
    bewertungen = load_bewertungen(DB_PATH, projekt_name)

    # Pflicht-Doku-Daten (Sprint β) — werden in DOCX/PDF eingebunden
    pflicht_doku = {
        'assets': db_list_assets(DB_PATH, projekt_name),
        'risiken': db_list_risiken(DB_PATH, projekt_name),
        'incident_response': db_load_ir(DB_PATH, projekt_name) or {},
        'vendors': db_list_vendors(DB_PATH, projekt_name),
        'bcp': db_load_bcp(DB_PATH, projekt_name) or {},
    }
    klassifikator = {}
    try:
        meta = json.loads(projekt.get('meta_json') or '{}')
        klassifikator = (meta.get('nis2') or {}).get('klassifikator') or {}
    except Exception:
        pass

    common = dict(
        out_dir=out_dir,
        projekt_name=projekt_name,
        unternehmen=projekt.get('unternehmen', ''),
        einrichtungsklasse=projekt.get('einrichtungsklasse', 'wesentlich'),
        berater=projekt.get('berater', ''),
        bewertungen_raw=bewertungen,
    )

    try:
        current_app.logger.info('NIS2 export start: projekt=%r fmt=%s', projekt_name, fmt)
        if fmt == 'docx':
            from nis2.report_export import export_report_docx
            path = export_report_docx(pflicht_doku=pflicht_doku, klassifikator=klassifikator, **common)
        elif fmt == 'pdf':
            from nis2.report_export import export_report_pdf
            path = export_report_pdf(pflicht_doku=pflicht_doku, klassifikator=klassifikator, **common)
        else:  # xlsx
            from nis2.io_xlsx import export_fragebogen
            path = export_fragebogen(
                out_dir=out_dir,
                projekt_name=projekt_name,
                unternehmen=projekt.get('unternehmen', ''),
                einrichtungsklasse=projekt.get('einrichtungsklasse', 'wesentlich'),
                berater=projekt.get('berater', ''),
                bestehende_bewertungen=bewertungen,
            )
        current_app.logger.info('NIS2 export ok: path=%s', path.name)
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.post('/projekte/<projekt_name>/fragebogen/import')
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

    import shutil
    tmp_dir = workspace_tmpdir('nis2_import_')
    try:
        tmp_path = tmp_dir / 'upload.xlsx'
        f.save(str(tmp_path))
        from nis2.io_xlsx import import_fragebogen as do_import
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
    for req in load_merged_anforderungen(DB_PATH):
        if req.get('id') == req_id:
            return req
    return None


def _build_anforderung_prompt(req: Dict[str, Any], projekt: Dict[str, Any], current: Dict[str, Any]) -> str:
    return f"""🔒 SECURITY: Verwende AUSSCHLIESSLICH die bereitgestellten Informationen.

Du bist ein Experte für NIS2-Compliance (NIS2-Richtlinie EU 2022/2555).
Bewerte die Umsetzung der folgenden NIS2-Anforderung im Kontext von {projekt.get('unternehmen') or projekt.get('name', '—')}.

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
1. Bewertung 0-5 vergeben.
2. Kommentar in 2-4 Sätzen begründen.
3. 2-3 konkrete Maßnahmen empfehlen.

## Format
```json
{{
  "score": 0-5,
  "kommentar": "Begründung...",
  "massnahme": "Konkrete Maßnahmen..."
}}
```
"""


@nis2_bp.get('/projekte/<projekt_name>/anforderungen/<req_id>/prompt')
@jwt_required()
def anf_prompt(projekt_name: str, req_id: str):
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        req = _find_anforderung(req_id)
        if not req:
            return {'error': f'Anforderung nicht gefunden'}, 404
        bewertungen = load_bewertungen(DB_PATH, projekt_name)
        prompt = _build_anforderung_prompt(req, projekt, bewertungen.get(req_id, {}))
        return {'prompt': prompt, 'req_id': req_id}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/parse-response')
@jwt_required()
def anf_parse(projekt_name: str, req_id: str):
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        if not _find_anforderung(req_id):
            return {'error': f'Anforderung nicht gefunden'}, 404

        data = request.json or {}
        raw = data.get('raw') or ''
        if not raw:
            return {'error': 'Feld "raw" ist Pflicht'}, 400
        apply = bool(data.get('apply', False))

        json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw, re.DOTALL)
        json_str = json_match.group(1) if json_match else (
            re.search(r'(\{[^{}]*"score"[^{}]*\})', raw, re.DOTALL).group(1)
            if re.search(r'(\{[^{}]*"score"[^{}]*\})', raw, re.DOTALL) else raw.strip()
        )

        try:
            parsed = _json.loads(json_str)
        except _json.JSONDecodeError as e:
            return {'error': f'JSON-Parse-Fehler: {e}', 'raw_excerpt': json_str[:200]}, 400

        score = int(parsed.get('score', 0))
        if score < 0 or score > 5:
            return {'error': 'score muss 0-5 sein'}, 400

        kommentar = parsed.get('kommentar', '') or ''
        massnahme = parsed.get('massnahme', '') or ''
        result = {'parsed': parsed, 'bewertung': score, 'kommentar': kommentar, 'massnahme': massnahme}

        if apply:
            existing = load_bewertungen(DB_PATH, projekt_name).get(req_id, {})
            db_save_bewertung(
                DB_PATH,
                projekt_name=projekt_name,
                anforderung_id=req_id,
                bewertung=score,
                kommentar=kommentar,
                massnahme=massnahme,
                verantwortlich=existing.get('verantwortlich', ''),
                zieldatum=existing.get('zieldatum', ''),
            )
            result['saved'] = True
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@nis2_bp.get('/projekte/<projekt_name>/anforderungen/<req_id>/issues')
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


@nis2_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues')
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

        title = data.get('title') or f"NIS2 Gap: {req_id} {req.get('titel', '')}".strip()
        existing = load_bewertungen(DB_PATH, projekt_name).get(req_id, {})
        body = data.get('body') or f"""## NIS2-Anforderung: {req_id}

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
_Generiert aus dem AI Compliance Suite NIS2-Modul._
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


@nis2_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues/link')
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


@nis2_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues/sync')
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


@nis2_bp.delete('/projekte/<projekt_name>/anforderungen/<req_id>/issues/<link_id>')
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
# Backwards-compat (KundenView/Sidebar)
# ============================================================

@nis2_bp.get('')
@jwt_required()
def list_all_legacy():
    """Backwards-compat."""
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


# ════════════════════════════════════════════════════════════════════
# Sprint β Phase A — Pflicht-Doku-Manager (Issue #579)
# ════════════════════════════════════════════════════════════════════

from nis2.db import (
    list_assets as db_list_assets, save_asset as db_save_asset, delete_asset as db_delete_asset,
    list_risiken as db_list_risiken, save_risiko as db_save_risiko, delete_risiko as db_delete_risiko,
    load_incident_response as db_load_ir, save_incident_response as db_save_ir,
    list_vendors as db_list_vendors, save_vendor as db_save_vendor, delete_vendor as db_delete_vendor,
    load_bcp as db_load_bcp, save_bcp as db_save_bcp,
)


def _require_nis2_projekt(projekt_name: str):
    p = load_projekt(DB_PATH, projekt_name)
    if not p:
        return None, (jsonify({'error': f'Projekt "{projekt_name}" nicht gefunden'}), 404)
    return p, None


# ─── N1: Asset-Inventar ────────────────────────────────────────────

@nis2_bp.get('/projekte/<projekt_name>/assets')
@jwt_required()
def assets_list(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    return jsonify(db_list_assets(DB_PATH, projekt_name))


@nis2_bp.post('/projekte/<projekt_name>/assets')
@jwt_required()
def assets_save(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    try:
        aid = db_save_asset(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'id': aid, 'ok': True}), 201


@nis2_bp.delete('/projekte/<projekt_name>/assets/<int:asset_id>')
@jwt_required()
def assets_delete(projekt_name: str, asset_id: int):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    db_delete_asset(DB_PATH, asset_id)
    return jsonify({'ok': True})


# ─── N2: Risiko-Register ───────────────────────────────────────────

@nis2_bp.get('/projekte/<projekt_name>/risiken')
@jwt_required()
def risiken_list(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    return jsonify(db_list_risiken(DB_PATH, projekt_name, request.args.get('status')))


@nis2_bp.post('/projekte/<projekt_name>/risiken')
@jwt_required()
def risiken_save(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    try:
        rid = db_save_risiko(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'id': rid, 'ok': True}), 201


@nis2_bp.delete('/projekte/<projekt_name>/risiken/<int:risk_id>')
@jwt_required()
def risiken_delete(projekt_name: str, risk_id: int):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    db_delete_risiko(DB_PATH, risk_id)
    return jsonify({'ok': True})


# ─── N3: Incident-Response ─────────────────────────────────────────

@nis2_bp.get('/projekte/<projekt_name>/incident-response')
@jwt_required()
def ir_get(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    return jsonify(db_load_ir(DB_PATH, projekt_name) or {})


@nis2_bp.post('/projekte/<projekt_name>/incident-response')
@jwt_required()
def ir_save(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    db_save_ir(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    return jsonify({'ok': True})


# ─── N4: Supply-Chain ──────────────────────────────────────────────

@nis2_bp.get('/projekte/<projekt_name>/vendors')
@jwt_required()
def vendors_list(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    return jsonify(db_list_vendors(DB_PATH, projekt_name))


@nis2_bp.post('/projekte/<projekt_name>/vendors')
@jwt_required()
def vendors_save(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    try:
        vid = db_save_vendor(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'id': vid, 'ok': True}), 201


@nis2_bp.delete('/projekte/<projekt_name>/vendors/<int:vendor_id>')
@jwt_required()
def vendors_delete(projekt_name: str, vendor_id: int):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    db_delete_vendor(DB_PATH, vendor_id)
    return jsonify({'ok': True})


# ─── N5: BCP ───────────────────────────────────────────────────────

@nis2_bp.get('/projekte/<projekt_name>/bcp')
@jwt_required()
def bcp_get(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    return jsonify(db_load_bcp(DB_PATH, projekt_name) or {})


@nis2_bp.post('/projekte/<projekt_name>/bcp')
@jwt_required()
def bcp_save(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    db_save_bcp(DB_PATH, projekt_name, request.get_json(silent=True) or {})
    return jsonify({'ok': True})


# ─── Status-Aggregator ─────────────────────────────────────────────

@nis2_bp.get('/projekte/<projekt_name>/pflicht-doku')
@jwt_required()
def pflicht_doku_status(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    assets = db_list_assets(DB_PATH, projekt_name)
    risiken = db_list_risiken(DB_PATH, projekt_name)
    ir = db_load_ir(DB_PATH, projekt_name)
    vendors = db_list_vendors(DB_PATH, projekt_name)
    bcp = db_load_bcp(DB_PATH, projekt_name)
    open_risiken = [r for r in risiken if r.get('status') in ('offen', 'in-behandlung')]
    high_kritisch = [a for a in assets if a.get('kritikalitaet') in ('hoch', 'kritisch')]
    return jsonify({
        'assets': {'count': len(assets), 'high_critical': len(high_kritisch), 'ok': len(assets) > 0},
        'risiken': {'total': len(risiken), 'open': len(open_risiken), 'ok': len(open_risiken) == 0},
        'incident_response': {'ok': bool(ir and ir.get('csirt_kontakt'))},
        'supply_chain': {'count': len(vendors), 'ok': len(vendors) > 0},
        'bcp': {'ok': bool(bcp and bcp.get('backup_strategie')), 'rpo': (bcp or {}).get('rpo_minuten'),
                'rto': (bcp or {}).get('rto_minuten')},
    })


# ════════════════════════════════════════════════════════════════════
# Sprint β Phase B — KI-Wizards (Issue #580)
# ════════════════════════════════════════════════════════════════════

from nis2.ai_wizards import (
    build_incident_24h_prompt, parse_incident_24h_response,
    build_incident_72h_prompt, parse_incident_72h_response,
    build_incident_final_prompt, parse_incident_final_response,
    build_cyberhygiene_quiz_prompt, parse_cyberhygiene_quiz_response,
    build_vendor_tiering_prompt, parse_vendor_tiering_response,
    build_klassifikator_prompt as nis2_build_klass_prompt,
    parse_klassifikator_response as nis2_parse_klass,
    list_sektor_templates, get_sektor_template,
    build_incident_notification_prompt, parse_incident_notification_response,
    build_supply_chain_assessment_prompt, parse_supply_chain_assessment_response,
)


def _should_apply_nis2(body: dict) -> bool:
    if request.args.get('dry_run') == 'true' or body.get('dry_run') is True:
        return False
    if request.args.get('apply') == 'false':
        return False
    return True


# ─── N6: Entity-Klassifikator ──────────────────────────────────────

@nis2_bp.get('/projekte/<projekt_name>/wizards/klassifikator/prompt')
@jwt_required()
def nis2_klass_prompt(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    return jsonify({'prompt': nis2_build_klass_prompt(p)})


@nis2_bp.post('/projekte/<projekt_name>/wizards/klassifikator/parse')
@jwt_required()
def nis2_klass_parse(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = nis2_parse_klass(body.get('response', ''))
    applied = False
    if _should_apply_nis2(body) and parsed.get('klasse'):
        meta = json.loads(p.get('meta_json') or '{}')
        meta.setdefault('nis2', {})['klassifikator'] = parsed
        # einrichtungsklasse-Spalte auch updaten (essential/important/out-of-scope)
        from nis2.db import save_projekt as nis2_save_projekt
        nis2_save_projekt(DB_PATH, p['name'], p.get('unternehmen', ''),
                          parsed['klasse'], p.get('beschreibung', ''),
                          p.get('berater', ''), meta)
        applied = True
        current_app.logger.info('wizard.applied kind=nis2-klassifikator project=%r klasse=%r',
                                projekt_name, parsed.get('klasse'))
    return jsonify({**parsed, 'applied': applied})


# ─── N7: Sektor-Templates ──────────────────────────────────────────

@nis2_bp.get('/wizards/sektor-templates')
@jwt_required()
def nis2_sektor_list():
    return jsonify(list_sektor_templates())


@nis2_bp.post('/projekte/<projekt_name>/wizards/sektor-template/apply')
@jwt_required()
def nis2_sektor_apply(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    sektor_id = (request.get_json(silent=True) or {}).get('sektor_id', '')
    tpl = get_sektor_template(sektor_id)
    if not tpl:
        return jsonify({'error': f'Sektor "{sektor_id}" unbekannt'}), 400
    # Incident-Response Defaults
    ir = db_load_ir(DB_PATH, projekt_name) or {}
    ir.update({'csirt_kontakt': tpl.get('csirt_kontakt', ir.get('csirt_kontakt', '')),
               'csirt_email': tpl.get('csirt_email', ir.get('csirt_email', ''))})
    db_save_ir(DB_PATH, projekt_name, ir)
    # BCP Defaults
    bcp = db_load_bcp(DB_PATH, projekt_name) or {}
    if not bcp.get('rpo_minuten') or bcp.get('rpo_minuten') == 60:
        bcp['rpo_minuten'] = tpl.get('rpo_minuten', 60)
        bcp['rto_minuten'] = tpl.get('rto_minuten', 240)
        db_save_bcp(DB_PATH, projekt_name, bcp)
    return jsonify({'ok': True, 'template': tpl, 'applied': True})


# ─── N8: Incident-Notification-Generator ───────────────────────────

@nis2_bp.post('/projekte/<projekt_name>/wizards/incident-notification/prompt')
@jwt_required()
def nis2_incident_prompt(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    incident_meta = request.get_json(silent=True) or {}
    return jsonify({'prompt': build_incident_notification_prompt(p, incident_meta)})


@nis2_bp.post('/projekte/<projekt_name>/wizards/incident-notification/parse')
@jwt_required()
def nis2_incident_parse(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_incident_notification_response(body.get('response', ''))
    applied = False
    if _should_apply_nis2(body) and parsed.get('early_warning'):
        ir = db_load_ir(DB_PATH, projekt_name) or {}
        templates_text = (
            "\n\n--- 24h Early-Warning ---\n" + parsed['early_warning']
            + "\n\n--- 72h Notification ---\n" + parsed.get('notification', '')
            + "\n\n--- 1M Final-Report ---\n" + parsed.get('final_report', '')
        )
        ir['kommunikationsplan'] = (ir.get('kommunikationsplan', '') + templates_text).strip()
        db_save_ir(DB_PATH, projekt_name, ir)
        applied = True
        current_app.logger.info('wizard.applied kind=nis2-incident-notification project=%r', projekt_name)
    return jsonify({**parsed, 'applied': applied})


# ─── N9: Supply-Chain-Assessment ───────────────────────────────────

@nis2_bp.post('/projekte/<projekt_name>/wizards/supply-chain/prompt')
@jwt_required()
def nis2_sc_prompt(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    vendor = request.get_json(silent=True) or {}
    return jsonify({'prompt': build_supply_chain_assessment_prompt(p, vendor)})


@nis2_bp.post('/projekte/<projekt_name>/wizards/supply-chain/parse')
@jwt_required()
def nis2_sc_parse(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_supply_chain_assessment_response(body.get('response', ''))
    applied = False
    vendor_id = body.get('vendor_id')
    if _should_apply_nis2(body) and parsed.get('gesamt_score') and vendor_id:
        # Score + Notizen in vendor schreiben
        vendors = db_list_vendors(DB_PATH, projekt_name)
        v = next((x for x in vendors if x['id'] == int(vendor_id)), None)
        if v:
            v['assessment_score'] = parsed['gesamt_score']
            v['assessment_datum'] = __import__('datetime').datetime.utcnow().strftime('%Y-%m-%d')
            kategorien_text = '\n'.join(
                f"- {k.get('name')}: {k.get('score')}/10 — {k.get('kommentar', '')}"
                for k in parsed.get('kategorien', [])
            )
            v['notizen'] = (
                (v.get('notizen') or '')
                + f"\n\n--- Assessment {v['assessment_datum']} ---\n"
                + f"Empfehlung: {parsed.get('empfehlung')}\n"
                + f"Gesamt-Score: {parsed['gesamt_score']}/100\n\n"
                + kategorien_text + "\n\nNächste Schritte: " + parsed.get('naechste_schritte', '')
            ).strip()
            db_save_vendor(DB_PATH, projekt_name, v)
            applied = True
            current_app.logger.info('wizard.applied kind=nis2-supply-chain project=%r vendor_id=%s', projekt_name, vendor_id)
    return jsonify({**parsed, 'applied': applied})


# ════════════════════════════════════════════════════════════════════
# Risiken aus RB-Modul importieren (#582)
# ════════════════════════════════════════════════════════════════════

RB_DB_PATH = Path('data/db/risikobewertung.sqlite')


def _rb_score_to_categories(risikowert: int | None) -> tuple[str, str]:
    """Mapt RB-Risikowert (0-100) auf nis2-Auswirkung+Eintrittswkt."""
    rw = int(risikowert or 0)
    if rw >= 75:
        return ('kritisch', 'wahrscheinlich')
    if rw >= 50:
        return ('hoch', 'wahrscheinlich')
    if rw >= 25:
        return ('mittel', 'gelegentlich')
    return ('niedrig', 'selten')


@nis2_bp.get('/projekte/<projekt_name>/wizards/rb-risks')
@jwt_required()
def nis2_rb_risks_list(projekt_name: str):
    """Liefert RB-Risiken für den Kunden des NIS2-Projekts."""
    p, err = _require_nis2_projekt(projekt_name)
    if err:
        return err
    kunde = p.get('unternehmen', '')
    if not kunde:
        return jsonify({'error': 'NIS2-Projekt hat keinen Kunden — RB-Import nicht möglich',
                        'risiken': [], 'rb_projekte': []}), 200

    if not RB_DB_PATH.exists():
        return jsonify({'risiken': [], 'rb_projekte': [],
                        'warnings': ['Risikobewertungs-DB existiert noch nicht']}), 200

    import sqlite3 as _sql
    con = _sql.connect(str(RB_DB_PATH))
    con.row_factory = _sql.Row
    try:
        # RB-Projekte des Kunden
        rb_projects = [dict(r) for r in con.execute(
            "SELECT name FROM rb_projekte WHERE unternehmen=? OR name=?",
            (kunde, kunde)).fetchall()]
        if not rb_projects:
            return jsonify({'risiken': [], 'rb_projekte': [],
                            'warnings': [f'Keine RB-Projekte für Kunde "{kunde}" gefunden']}), 200

        rb_names = [rp['name'] for rp in rb_projects]
        placeholders = ','.join('?' * len(rb_names))
        rows = con.execute(
            f"""SELECT id, projekt_name, risk_name, beschreibung, framework,
                       risikowert, risiko_label, detail_text, bewertung_text,
                       is_resolved, created_at
                FROM rb_risiken WHERE projekt_name IN ({placeholders})
                ORDER BY risikowert DESC NULLS LAST""",
            rb_names).fetchall()
    finally:
        con.close()

    # Bereits importierte erkennen (über source_rb_risk_id in nis2_risiko notizen)
    already_imported_ids: set[int] = set()
    for r in db_list_risiken(DB_PATH, projekt_name):
        notizen = r.get('notizen') or ''
        if 'source_rb_risk_id=' in notizen:
            try:
                rid = int(notizen.split('source_rb_risk_id=')[1].split()[0].strip(',;'))
                already_imported_ids.add(rid)
            except (ValueError, IndexError):
                pass

    out = []
    for r in rows:
        d = dict(r)
        d['already_imported'] = r['id'] in already_imported_ids
        out.append(d)
    return jsonify({'risiken': out, 'rb_projekte': rb_projects, 'kunde': kunde}), 200


@nis2_bp.post('/projekte/<projekt_name>/wizards/import-rb-risks/apply')
@jwt_required()
def nis2_rb_risks_import(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    risk_ids = body.get('risk_ids') or []
    if not risk_ids:
        return jsonify({'error': 'risk_ids fehlt oder leer'}), 400

    if not RB_DB_PATH.exists():
        return jsonify({'error': 'Risikobewertungs-DB nicht gefunden'}), 404

    import sqlite3 as _sql
    con = _sql.connect(str(RB_DB_PATH))
    con.row_factory = _sql.Row
    try:
        placeholders = ','.join('?' * len(risk_ids))
        rb_rows = con.execute(
            f"SELECT * FROM rb_risiken WHERE id IN ({placeholders})",
            [int(x) for x in risk_ids]).fetchall()
    finally:
        con.close()

    imported = 0
    skipped: list[dict] = []
    existing_risiken = db_list_risiken(DB_PATH, projekt_name)
    existing_ids = {r.get('risiko_id') for r in existing_risiken}

    for r in rb_rows:
        rb = dict(r)
        nis2_risiko_id = f"RB-{rb['id']:04d}"
        if nis2_risiko_id in existing_ids:
            skipped.append({'rb_id': rb['id'], 'reason': 'bereits vorhanden'})
            continue
        auswirkung, wkt = _rb_score_to_categories(rb.get('risikowert'))
        payload = {
            'risiko_id': nis2_risiko_id,
            'titel': rb.get('risk_name', '')[:200],
            'bedrohung': rb.get('beschreibung', '')[:500],
            'auswirkung': auswirkung,
            'eintrittswkt': wkt,
            'massnahmen': rb.get('detail_text') or rb.get('bewertung_text', ''),
            'status': 'mitigiert' if rb.get('is_resolved') else 'offen',
            'notizen': (
                f"Importiert aus Risikobewertung: source_rb_risk_id={rb['id']} "
                f"projekt={rb.get('projekt_name')} framework={rb.get('framework')} "
                f"score={rb.get('risikowert')} ({rb.get('risiko_label')})"
            ),
        }
        try:
            db_save_risiko(DB_PATH, projekt_name, payload)
            imported += 1
        except Exception as e:
            skipped.append({'rb_id': rb['id'], 'reason': str(e)})

    current_app.logger.info('wizard.applied kind=nis2-rb-import project=%r imported=%d skipped=%d',
                            projekt_name, imported, len(skipped))
    return jsonify({'imported': imported, 'skipped': skipped, 'applied': True}), 200


# ════════════════════════════════════════════════════════════════════
# Sprint δ Phase D — Incident-/Meldungs-Wizards (#513-#516)
# ════════════════════════════════════════════════════════════════════

def _append_to_ir_kommunikation(projekt_name: str, title: str, body: str) -> None:
    """Helper: hänge einen Block an ir.kommunikationsplan an."""
    ir = db_load_ir(DB_PATH, projekt_name) or {}
    ir['kommunikationsplan'] = (
        (ir.get('kommunikationsplan') or '')
        + f"\n\n--- {title} ---\n" + body
    ).strip()
    db_save_ir(DB_PATH, projekt_name, ir)


# ─── N14 — 24h-Erstmeldung (#513) ───────────────────────────────────

@nis2_bp.post('/projekte/<projekt_name>/wizards/incident-24h/prompt')
@jwt_required()
def nis2_incident_24h_prompt(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    incident = request.get_json(silent=True) or {}
    return jsonify({'prompt': build_incident_24h_prompt(p, incident)})


@nis2_bp.post('/projekte/<projekt_name>/wizards/incident-24h/parse')
@jwt_required()
def nis2_incident_24h_parse(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_incident_24h_response(body.get('response', ''))
    applied = False
    if _should_apply_nis2(body) and parsed.get('kurztext'):
        summary = (
            f"Incident-ID: {parsed.get('incident_id', '')}\n"
            f"Signifikant: {parsed.get('signifikant')}  ·  "
            f"Bösw. Verdacht: {parsed.get('boeswillig_verdacht')}  ·  "
            f"Grenzüberschr.: {parsed.get('grenzueberschreitend')}\n"
            f"Empfänger: {', '.join(parsed.get('empfaenger', []))}\n\n"
            + parsed.get('kurztext', '')
        )
        _append_to_ir_kommunikation(projekt_name, '24h-Erstmeldung (Art. 23 Abs. 4 lit. a)', summary)
        applied = True
        current_app.logger.info('wizard.applied kind=nis2-incident-24h project=%r incident=%r',
                                projekt_name, parsed.get('incident_id'))
    return jsonify({**parsed, 'applied': applied})


# ─── N15a — 72h-Aktualisierung (#514) ───────────────────────────────

@nis2_bp.post('/projekte/<projekt_name>/wizards/incident-72h/prompt')
@jwt_required()
def nis2_incident_72h_prompt(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    incident = request.get_json(silent=True) or {}
    return jsonify({'prompt': build_incident_72h_prompt(p, incident)})


@nis2_bp.post('/projekte/<projekt_name>/wizards/incident-72h/parse')
@jwt_required()
def nis2_incident_72h_parse(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_incident_72h_response(body.get('response', ''))
    applied = False
    if _should_apply_nis2(body) and parsed.get('ersteinschaetzung'):
        iocs = parsed.get('iocs') or []
        iocs_str = ('\n'.join(f"  · {i.get('typ')}: {i.get('wert')} ({i.get('kommentar', '')})" for i in iocs)
                    or '  (keine)')
        summary = (
            f"Incident-ID: {parsed.get('incident_id', '')}\n"
            f"Schweregrad: {parsed.get('schweregrad')}\n\n"
            f"Ersteinschätzung:\n{parsed.get('ersteinschaetzung', '')}\n\n"
            f"Sofortmaßnahmen:\n" + '\n'.join(f"  - {m}" for m in parsed.get('sofortmassnahmen', []))
            + f"\n\nKompromittierungs-Indikatoren (IoCs):\n{iocs_str}\n\n"
            f"Auswirkung: {parsed.get('auswirkung', '')}\n"
            f"Zeitrahmen: {parsed.get('zeitrahmen', '')}"
        )
        _append_to_ir_kommunikation(projekt_name, '72h-Aktualisierung (Art. 23 Abs. 4 lit. b)', summary)
        applied = True
        current_app.logger.info('wizard.applied kind=nis2-incident-72h project=%r incident=%r severity=%r',
                                projekt_name, parsed.get('incident_id'), parsed.get('schweregrad'))
    return jsonify({**parsed, 'applied': applied})


# ─── N15b — 1-Monats-Abschlussmeldung (#514) ────────────────────────

@nis2_bp.post('/projekte/<projekt_name>/wizards/incident-final/prompt')
@jwt_required()
def nis2_incident_final_prompt(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    incident = request.get_json(silent=True) or {}
    return jsonify({'prompt': build_incident_final_prompt(p, incident)})


@nis2_bp.post('/projekte/<projekt_name>/wizards/incident-final/parse')
@jwt_required()
def nis2_incident_final_parse(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_incident_final_response(body.get('response', ''))
    applied = False
    if _should_apply_nis2(body) and parsed.get('report_text'):
        _append_to_ir_kommunikation(
            projekt_name,
            '1-Monats-Abschlussmeldung (Art. 23 Abs. 4 lit. c)',
            parsed.get('report_text', ''),
        )
        applied = True
        current_app.logger.info('wizard.applied kind=nis2-incident-final project=%r incident=%r',
                                projekt_name, parsed.get('incident_id'))
    return jsonify({**parsed, 'applied': applied})


# ─── N16 — Cyberhygiene-Quiz (#515) ─────────────────────────────────

@nis2_bp.post('/projekte/<projekt_name>/wizards/cyberhygiene-quiz/prompt')
@jwt_required()
def nis2_quiz_prompt(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    themen = body.get('themen') or None
    niveau = body.get('niveau') or 'mittel'
    return jsonify({'prompt': build_cyberhygiene_quiz_prompt(p, themen=themen, niveau=niveau)})


@nis2_bp.post('/projekte/<projekt_name>/wizards/cyberhygiene-quiz/parse')
@jwt_required()
def nis2_quiz_parse(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_cyberhygiene_quiz_response(body.get('response', ''))
    applied = False
    fragen = parsed.get('fragen') or []
    if _should_apply_nis2(body) and fragen:
        # Quiz in nis2_projekte.meta_json.cyberhygiene_quiz speichern + Listing in IR.kommunikationsplan
        import json as _j
        meta = _j.loads(p.get('meta_json') or '{}')
        quizzes = meta.setdefault('nis2', {}).setdefault('cyberhygiene_quizzes', [])
        from datetime import datetime as _dt
        quizzes.append({
            'titel': parsed.get('titel', 'Cyberhygiene-Quiz'),
            'created_at': _dt.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'fragen_count': len(fragen),
            'fragen': fragen,
            'auswertung': parsed.get('auswertung', {}),
        })
        from nis2.db import save_projekt as nis2_save_projekt
        nis2_save_projekt(
            DB_PATH,
            name=p['name'],
            unternehmen=p.get('unternehmen', ''),
            einrichtungsklasse=p.get('einrichtungsklasse', ''),
            beschreibung=p.get('beschreibung', ''),
            berater=p.get('berater', ''),
            meta=meta,
        )
        listing = '\n'.join(
            f"  Q{i+1} ({f.get('thema')}): {f.get('frage', '')}"
            for i, f in enumerate(fragen[:10])
        )
        _append_to_ir_kommunikation(
            projekt_name,
            f"Cyberhygiene-Quiz '{parsed.get('titel', 'Quiz')}' ({len(fragen)} Fragen)",
            listing,
        )
        applied = True
        current_app.logger.info('wizard.applied kind=nis2-cyberhygiene-quiz project=%r fragen=%d',
                                projekt_name, len(fragen))
    return jsonify({**parsed, 'applied': applied})


# ─── N17 — Lieferanten-Tiering (#516) ───────────────────────────────

@nis2_bp.post('/projekte/<projekt_name>/wizards/vendor-tiering/prompt')
@jwt_required()
def nis2_vendor_tiering_prompt(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    vendor = request.get_json(silent=True) or {}
    return jsonify({'prompt': build_vendor_tiering_prompt(p, vendor)})


@nis2_bp.post('/projekte/<projekt_name>/wizards/vendor-tiering/parse')
@jwt_required()
def nis2_vendor_tiering_parse(projekt_name: str):
    p, err = _require_nis2_projekt(projekt_name)
    if err: return err
    body = request.get_json(silent=True) or {}
    parsed = parse_vendor_tiering_response(body.get('response', ''))
    applied = False
    vendor_id = body.get('vendor_id')
    if _should_apply_nis2(body) and parsed.get('tier') and vendor_id:
        vendors = db_list_vendors(DB_PATH, projekt_name)
        v = next((x for x in vendors if x['id'] == int(vendor_id)), None)
        if v:
            v['kritikalitaet'] = parsed['tier']
            kontrollen_str = '\n'.join(
                f"  - {k.get('id', '?')} {k.get('name', '')} (Pflicht ab {k.get('pflicht_ab_tier', 'n.a.')})"
                for k in parsed.get('kontrollen_empfehlung', [])
            )
            v['notizen'] = (
                (v.get('notizen') or '')
                + f"\n\n--- Tiering-Assessment ---\n"
                + f"Tier: {parsed['tier']} (Konfidenz: {parsed.get('konfidenz')})\n"
                + f"Begründung: {parsed.get('tier_begruendung', '')}\n"
                + f"Fragebogen versenden: {'JA' if parsed.get('fragebogen_versenden') else 'NEIN'}\n"
                + f"Nächste Review: {parsed.get('naechste_review', '')}\n\n"
                + f"Kontroll-Empfehlungen:\n{kontrollen_str}\n\n"
                + f"Soforthandlungen: " + '; '.join(parsed.get('soforthandlungen', []))
            ).strip()
            db_save_vendor(DB_PATH, projekt_name, v)
            applied = True
            current_app.logger.info('wizard.applied kind=nis2-vendor-tiering project=%r vendor_id=%s tier=%s',
                                    projekt_name, vendor_id, parsed['tier'])
    return jsonify({**parsed, 'applied': applied})
