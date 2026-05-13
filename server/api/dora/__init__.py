"""DORA REST API — Projekte, Anforderungen, Bewertungen, TPP, Testing, Reports + Issues."""

import shutil
from flask import current_app, Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from pathlib import Path
from typing import Any, Dict, List
import tempfile

from server.api._tmp import workspace_tmpdir
import json
import re

from dora.db import (
    ensure_db,
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
    save_tpp,
    list_tpp,
    delete_tpp as db_delete_tpp,
    save_test,
    list_tests,
    delete_test as db_delete_test,
)

from dora.requirements import (
    DORA_ANFORDERUNGEN,
    PFEILER,
    anforderungen_by_pfeiler,
    load_merged_anforderungen,
    berechne_reifegrad,
)

dora_bp = Blueprint('dora', __name__, url_prefix='/api/dora')

DB_PATH = Path('data/db/dora.sqlite')

ensure_db(DB_PATH)

ALLOWED_FINANZ_KLASSEN = {'bank', 'insurer', 'investment', 'other', ''}


# ============================================================
# Hilfsfunktionen
# ============================================================

def _serialize_projekt(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': p.get('name'),
        'name': p.get('name', ''),
        'company': p.get('unternehmen', ''),
        'unternehmen': p.get('unternehmen', ''),
        'finanzeinrichtung_klasse': p.get('finanzeinrichtung_klasse', ''),
        'beschreibung': p.get('beschreibung', ''),
        'description': p.get('beschreibung', ''),
        'berater': p.get('berater', ''),
        'meta_json': p.get('meta_json', '{}'),
        'meta': p.get('meta_json', '{}'),
        'created_at': p.get('created_at'),
        'updated_at': p.get('updated_at'),
    }


def _serialize_anforderung(req: Dict[str, Any], bewertung: Dict[str, Any]) -> Dict[str, Any]:
    score = int(bewertung.get('bewertung', 0))
    return {
        'id': req.get('id'),
        'kapitel': req.get('pfeiler', ''),  # Frontend nutzt 'kapitel' generisch
        'pfeiler': req.get('pfeiler', ''),
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
        'kommentar': bewertung.get('kommentar', ''),
        'notes': bewertung.get('kommentar', ''),
        'massnahme': bewertung.get('massnahme', ''),
        'verantwortlich': bewertung.get('verantwortlich', ''),
        'zieldatum': bewertung.get('zieldatum', ''),
        'updated_at': bewertung.get('updated_at'),
        'status': 'complete' if score >= 4 else 'partial' if score >= 2 else 'pending',
    }


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
    return next((r for r in load_merged_anforderungen(DB_PATH) if r.get('id') == req_id), None)


# ============================================================
# Konstanten
# ============================================================

_PFEILER_INFO = {
    'ICT-RM': {'titel': 'ICT Risk Management',          'untertitel': 'Art. 5–16',  'farbe': '#1565c0', 'soft': '#e3f2fd', 'referenz': 'DORA Art. 5–16',  'beschreibung': 'Governance, Risikomanagement-Rahmenwerk, Identifikation kritischer ICT-Assets, Schutz, Erkennung, Reaktion und Wiederherstellung.'},
    'ICT-IM': {'titel': 'ICT Incident Management',      'untertitel': 'Art. 17–23', 'farbe': '#bf360c', 'soft': '#fbe9e7', 'referenz': 'DORA Art. 17–23', 'beschreibung': 'Klassifikation, Berichtspflichten und Behandlung schwerwiegender ICT-Vorfälle.'},
    'ICT-RT': {'titel': 'Resilience Testing',           'untertitel': 'Art. 24–27', 'farbe': '#4a148c', 'soft': '#f3e5f5', 'referenz': 'DORA Art. 24–27', 'beschreibung': 'Programm digitaler operativer Resilienz-Tests, Threat-Led Penetration Testing (TLPT) für signifikante Einrichtungen.'},
    'ICT-TP': {'titel': 'Third-Party Risk Management',  'untertitel': 'Art. 28–44', 'farbe': '#00695c', 'soft': '#e0f2f1', 'referenz': 'DORA Art. 28–44', 'beschreibung': 'Steuerung des ICT-Drittanbieter-Risikos, Vertragsanforderungen, Konzentrationsrisiken, kritische Anbieter-Aufsicht.'},
    'ICT-IS': {'titel': 'Information Sharing',          'untertitel': 'Art. 45',    'farbe': '#e65100', 'soft': '#fff3e0', 'referenz': 'DORA Art. 45',    'beschreibung': 'Freiwilliger Austausch von Cyber-Bedrohungsinformationen zwischen Finanzeinrichtungen.'},
}


@dora_bp.get('/constants')
@jwt_required()
def get_constants():
    return {
        'pfeiler': PFEILER,
        'kapitel': _PFEILER_INFO,  # alias für generischen HelpDialog
        'finanzeinrichtung_klassen': sorted(ALLOWED_FINANZ_KLASSEN - {''}),
    }, 200


@dora_bp.get('/pfeiler')
@jwt_required()
def get_pfeiler():
    return anforderungen_by_pfeiler(), 200


# ============================================================
# Projekte
# ============================================================

@dora_bp.get('/projekte')
@jwt_required()
def get_projekte():
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


@dora_bp.get('/projekte/<projekt_name>')
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


@dora_bp.post('/projekte')
@jwt_required()
def create_projekt():
    try:
        data = request.json or {}
        name = (data.get('name') or '').strip()
        if not name:
            return {'error': 'Feld "name" ist Pflicht'}, 400
        if load_projekt(DB_PATH, name):
            return {'error': 'Projekt existiert bereits'}, 409

        klasse = data.get('finanzeinrichtung_klasse', '')
        if klasse not in ALLOWED_FINANZ_KLASSEN:
            return {'error': f'finanzeinrichtung_klasse muss eines sein von {sorted(ALLOWED_FINANZ_KLASSEN)}'}, 400

        save_projekt(
            DB_PATH,
            name=name,
            unternehmen=data.get('unternehmen', '') or data.get('company', ''),
            finanzeinrichtung_klasse=klasse,
            beschreibung=data.get('beschreibung', '') or data.get('description', ''),
            berater=data.get('berater', ''),
        )
        return _serialize_projekt(load_projekt(DB_PATH, name)), 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.put('/projekte/<projekt_name>')
@jwt_required()
def update_projekt(projekt_name: str):
    try:
        existing = load_projekt(DB_PATH, projekt_name)
        if not existing:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        klasse = data.get('finanzeinrichtung_klasse', existing.get('finanzeinrichtung_klasse', ''))
        if klasse not in ALLOWED_FINANZ_KLASSEN:
            return {'error': f'Ungültige finanzeinrichtung_klasse'}, 400
        save_projekt(
            DB_PATH,
            name=projekt_name,
            unternehmen=data.get('unternehmen', existing.get('unternehmen', '')),
            finanzeinrichtung_klasse=klasse,
            beschreibung=data.get('beschreibung', existing.get('beschreibung', '')),
            berater=data.get('berater', existing.get('berater', '')),
        )
        return _serialize_projekt(load_projekt(DB_PATH, projekt_name)), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.delete('/projekte/<projekt_name>')
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

@dora_bp.get('/projekte/<projekt_name>/anforderungen')
@jwt_required()
def get_anforderungen(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        reqs = load_merged_anforderungen(DB_PATH)
        bewertungen = load_bewertungen(DB_PATH, projekt_name)
        result = [_serialize_anforderung(r, bewertungen.get(r.get('id'), {})) for r in reqs]
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.post('/projekte/<projekt_name>/bewertungen')
@jwt_required()
def save_bewertung(projekt_name: str):
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


@dora_bp.get('/projekte/<projekt_name>/reifegrad')
@jwt_required()
def get_reifegrad(projekt_name: str):
    """Reifegrad pro Pfeiler im Frontend-Format."""
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
        for pid, ps in raw.get('pfeiler_scores', {}).items():
            kapitel_out[pid] = {
                'prozent': ps.get('prozent', 0),
                'ampel': _ampel(ps.get('prozent', 0)),
                'bewertet': ps.get('bewertet', 0),
                'gesamt': ps.get('anzahl', 0),
            }

        luecken_out = []
        for req in raw.get('luecken', []):
            rid = req.get('id')
            score = int(bewertungen.get(rid, {}).get('bewertung', 0))
            luecken_out.append({
                'id': rid,
                'kapitel': req.get('pfeiler', ''),
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
            'pfeiler': kapitel_out,  # Alias
            'luecken': luecken_out,
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Custom-Anforderungen
# ============================================================

@dora_bp.get('/anforderungen/custom')
@jwt_required()
def get_custom():
    try:
        return load_custom_anforderungen(DB_PATH), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.post('/anforderungen/custom')
@jwt_required()
def create_custom():
    try:
        data = request.json or {}
        if not data.get('id'):
            return {'error': 'Feld "id" ist Pflicht'}, 400
        save_custom_anforderung(DB_PATH, {
            'id': data['id'],
            'pfeiler': data.get('pfeiler', 'ICT-RM'),
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


@dora_bp.delete('/anforderungen/custom/<req_id>')
@jwt_required()
def delete_custom(req_id: str):
    try:
        db_delete_custom(DB_PATH, req_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# TPP-Register
# ============================================================

@dora_bp.get('/projekte/<projekt_name>/tpp')
@jwt_required()
def get_tpps(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        return list_tpp(DB_PATH, projekt_name), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.post('/projekte/<projekt_name>/tpp')
@jwt_required()
def create_tpp(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        if not data.get('name'):
            return {'error': 'Feld "name" ist Pflicht'}, 400
        tid = save_tpp(DB_PATH, projekt_name=projekt_name, tpp=data)
        return {'id': tid, 'created': True}, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.put('/projekte/<projekt_name>/tpp/<tpp_id>')
@jwt_required()
def update_tpp(projekt_name: str, tpp_id: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        data['id'] = tpp_id
        save_tpp(DB_PATH, projekt_name=projekt_name, tpp=data)
        return {'id': tpp_id, 'updated': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.delete('/projekte/<projekt_name>/tpp/<tpp_id>')
@jwt_required()
def delete_tpp(projekt_name: str, tpp_id: str):
    try:
        db_delete_tpp(DB_PATH, tpp_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Testing-Plan
# ============================================================

@dora_bp.get('/projekte/<projekt_name>/testing')
@jwt_required()
def get_tests(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        return list_tests(DB_PATH, projekt_name), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.post('/projekte/<projekt_name>/testing')
@jwt_required()
def create_test(projekt_name: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        tid = save_test(DB_PATH, projekt_name=projekt_name, test=data)
        return {'id': tid, 'created': True}, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.put('/projekte/<projekt_name>/testing/<test_id>')
@jwt_required()
def update_test(projekt_name: str, test_id: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        data['id'] = test_id
        save_test(DB_PATH, projekt_name=projekt_name, test=data)
        return {'id': test_id, 'updated': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.delete('/projekte/<projekt_name>/testing/<test_id>')
@jwt_required()
def delete_test(projekt_name: str, test_id: str):
    try:
        db_delete_test(DB_PATH, test_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Reports
# ============================================================

@dora_bp.get('/projekte/<projekt_name>/report')
@jwt_required()
def export_report(projekt_name: str):
    fmt = (request.args.get('format') or 'pdf').lower()
    if fmt not in {'pdf', 'docx'}:
        return {'error': 'Format muss pdf|docx sein'}, 400
    if not load_projekt(DB_PATH, projekt_name):
        return {'error': 'Projekt nicht gefunden'}, 404

    out_dir = workspace_tmpdir('dora_report_')
    try:
        if fmt == 'docx':
            from dora.report_export import export_report_docx
            path = export_report_docx(db_path=DB_PATH, projekt_name=projekt_name, out_dir=out_dir)
        else:
            from dora.report_export import export_report_pdf
            path = export_report_pdf(db_path=DB_PATH, projekt_name=projekt_name, out_dir=out_dir)
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Anforderungs-Aktionen: Prompt, JSON-Parse, Issues (für RequirementActions)
# ============================================================

def _build_anforderung_prompt(req: Dict[str, Any], projekt: Dict[str, Any], current: Dict[str, Any]) -> str:
    return f"""🔒 SECURITY: Verwende AUSSCHLIESSLICH die bereitgestellten Informationen.

Du bist ein Experte für DORA-Compliance (Digital Operational Resilience Act, EU 2022/2554).
Bewerte die Umsetzung der folgenden DORA-Anforderung im Kontext von {projekt.get('unternehmen') or projekt.get('name', '—')}.

## Anforderung
ID:           {req.get('id')}
Pfeiler:      {req.get('pfeiler', '')} ({PFEILER.get(req.get('pfeiler', ''), '')})
EU-Referenz:  {req.get('ref', '')}
Titel:        {req.get('titel', '')}
Beschreibung: {req.get('beschreibung', '')}
Hinweise:     {req.get('hinweise', '')}
Gewichtung:   {req.get('gewichtung', 1)}

## Aktueller Stand
Score:      {int(current.get('bewertung', 0) or 0)}/5
Kommentar:  {current.get('kommentar', '') or '(leer)'}

## Auftrag
1. Bewertung 0-5.
2. Kommentar in 2-4 Sätzen.
3. 2-3 konkrete Maßnahmen.

## Format
```json
{{"score": 0-5, "kommentar": "...", "massnahme": "..."}}
```
"""


@dora_bp.get('/projekte/<projekt_name>/anforderungen/<req_id>/prompt')
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
        return {'prompt': _build_anforderung_prompt(req, projekt, bewertungen.get(req_id, {})),
                'req_id': req_id}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/parse-response')
@jwt_required()
def anf_parse(projekt_name: str, req_id: str):
    try:
        if not load_projekt(DB_PATH, projekt_name):
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
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            return {'error': f'JSON-Parse-Fehler: {e}'}, 400

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


# Issue-Linking (analog NIS2)

@dora_bp.get('/projekte/<projekt_name>/anforderungen/<req_id>/issues')
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


@dora_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues')
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

        title = data.get('title') or f"DORA Gap: {req_id} {req.get('titel', '')}".strip()
        existing = load_bewertungen(DB_PATH, projekt_name).get(req_id, {})
        body = data.get('body') or f"""## DORA-Anforderung: {req_id}

**Titel**: {req.get('titel', '')}
**Pfeiler**: {req.get('pfeiler', '')} ({PFEILER.get(req.get('pfeiler', ''), '')})
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
_Generiert aus dem AI Compliance Suite DORA-Modul._
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


@dora_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues/link')
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


@dora_bp.post('/projekte/<projekt_name>/anforderungen/<req_id>/issues/sync')
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


@dora_bp.delete('/projekte/<projekt_name>/anforderungen/<req_id>/issues/<link_id>')
@jwt_required()
def anf_unlink_issue(projekt_name: str, req_id: str, link_id: str):
    try:
        from shared.issue_links import delete_link
        delete_link(DB_PATH, link_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@dora_bp.post('/projekte/<projekt_name>/fragebogen/import')
@jwt_required()
def import_fragebogen_endpoint(projekt_name: str):
    """Excel-Fragebogen importieren (multipart, Feld 'file')."""
    if not load_projekt(DB_PATH, projekt_name):
        return {'error': 'Projekt nicht gefunden'}, 404
    f = request.files.get('file')
    if not f or not f.filename:
        return {'error': 'Datei-Feld "file" fehlt'}, 400
    if not f.filename.lower().endswith('.xlsx'):
        return {'error': 'Nur .xlsx wird unterstützt'}, 400

    tmp_dir = workspace_tmpdir('dora_import_')
    try:
        tmp_path = tmp_dir / 'upload.xlsx'
        f.save(str(tmp_path))
        from shared.xlsx_import import import_bewertungen
        from dora.requirements import DORA_ANFORDERUNGEN
        known = {r['id'] for r in DORA_ANFORDERUNGEN}
        items = import_bewertungen(tmp_path, known_ids=known, expected_label='DORA-Fragebogen')
        if items:
            bulk_save_bewertungen(DB_PATH, projekt_name, items)
        return {'imported': len(items)}, 200
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# Backwards-compat
# ============================================================

@dora_bp.get('')
@jwt_required()
def list_all_legacy():
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
