"""Gutachten Module API — vollständige CRUD: Projekte, Fragen, Sections, Prompt-Generierung,
ChatGPT-Antwort-Import, Gutachten-Generierung + Export."""

import shutil
import json
from pathlib import Path
from typing import Any, Dict

from server.api.workspace_tmp import workspace_tmpdir
from flask import current_app, Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from server.models.permission import require_permission, Permission  # #969

# Projekte/Fragen/Sections des Compliance-Audits liegen seit v7.4.0 in
# server/api/compliance_audit.py — hier bleibt nur die Gutachten-Seite.
from gutachten.db import ensure_db
from datetime import datetime

from shared.html_sanitize import sanitize_html

# Rich-Text-Felder, die als HTML gespeichert + per v-html gerendert werden.
# Server-seitige Sanitisierung als Defense-in-Depth (Issue #740, WP-07).
_HTML_TEXT_FIELDS = (
    'beschreibung_text',
    'soll_text',
    'ist_text',
    'kausalitaet_text',
    'bewertung_text',
)


def _sanitize_html_fields(body: Dict[str, Any]) -> Dict[str, Any]:
    """Bereinige bekannte Rich-Text-HTML-Felder im Request-Body (XSS-Härtung)."""
    for field in _HTML_TEXT_FIELDS:
        if field in body and isinstance(body[field], str):
            body[field] = sanitize_html(body[field])
    return body


gutachten_bp = Blueprint('gutachten', __name__, url_prefix='/api/gutachten')

DB_PATH = Path('data/db/gutachten.sqlite')

# DB sicherstellen
try:
    ensure_db(DB_PATH)
except Exception:
    pass


# ============================================================
# Feld-Allowlists für Gerichts-Schreib-Endpunkte (#743, WP-10)
# Statt ungefiltertes **body in die DB-Save-Funktionen zu spritzen, werden nur
# bekannte Felder übernommen (Mass-Assignment-Schutz, OWASP A03/A04, ASVS V5).
# ============================================================

_GERICHTS_PROJEKT_FIELDS = (
    'name', 'gutachten_art', 'gericht', 'kammer', 'aktenzeichen',
    'klaeger_name', 'klaeger_anwalt', 'beklagter_name', 'beklagter_anwalt',
    'beweisbeschluss_datum', 'auftraggeber', 'auftrags_art', 'auftrags_datum',
    'auftrags_nummer', 'honorarvereinbarung', 'thema', 'vertraulichkeit',
    'sv_name', 'sv_zertifizierung', 'sv_anschrift', 'sv_kontakt',
    'erstellt_von', 'status', 'meta',
)
_GERICHTS_BEWEISFRAGE_FIELDS = (
    'id', 'projekt_name', 'nr', 'frage_text', 'antwort_text', 'antwort_kurz',
    'referenz_beurteilung_ids',
)
_GERICHTS_BEFUND_FIELDS = (
    'id', 'projekt_name', 'nr', 'titel', 'beschreibung_text', 'methode',
    'werkzeug_name', 'werkzeug_version', 'asset_ids', 'erhebung_datum',
    'erhebung_ort', 'zeugen_text', 'non_liquet', 'non_liquet_grund',
)
_GERICHTS_BEURTEILUNG_FIELDS = (
    'id', 'projekt_name', 'nr', 'titel', 'befund_ids', 'norm_referenz',
    'soll_text', 'ist_text', 'kausalitaet_text', 'bewertung_text',
    'non_liquet', 'non_liquet_grund',
)
_GERICHTS_ASSET_FIELDS = (
    'id', 'projekt_name', 'bezeichnung', 'sha256', 'akquisitions_utc',
    'akquisitions_ort', 'werkzeug_name', 'werkzeug_version',
    'parteien_anwesend', 'gegengezeichnet_von', 'bemerkungen',
    'original_dateiname',
)
_GERICHTS_VERFAHREN_FIELDS = (
    'id', 'projekt_name', 'ereignis_datum', 'ereignis_typ', 'titel',
    'beschreibung', 'empfaenger',
)


def _allowlist(body: Any, allowed: tuple) -> Dict[str, Any]:
    """Reduziere ein Request-JSON auf erlaubte Felder (Mass-Assignment-Schutz)."""
    if not isinstance(body, dict):
        return {}
    return {k: body[k] for k in allowed if k in body}


# ============================================================
# Phase G0 — Foundation (Sprint ε-A)
# G0-1 Normen-Library | G0-2 Linter | G0-3 Werkzeug-Register | G0-9 Befangenheits-Check
# ============================================================

from gutachten import normen as _normen
from gutachten import linters as _linters
from gutachten import werkzeuge as _werkzeuge
from gutachten import befangenheit as _befangenheit


@gutachten_bp.get('/normen')
@jwt_required()
def normen_list():
    """G0-1 — Liste aller Normen (Kurz-Index)."""
    return jsonify({'normen': _normen.list_normen()})


@gutachten_bp.get('/normen/<norm_id>')
@jwt_required()
def normen_detail(norm_id: str):
    """G0-1 — Voll-Detail einer Norm inkl. Kategorien + Sub-Merkmale."""
    n = _normen.get_norm(norm_id)
    if not n:
        return jsonify({'error': f'Norm "{norm_id}" nicht gefunden'}), 404
    return jsonify(n)


@gutachten_bp.get('/normen/<norm_id>/<kategorie_id>/<sub_id>')
@jwt_required()
def normen_sub_merkmal(norm_id: str, kategorie_id: str, sub_id: str):
    """G0-1 — Einzelnes Sub-Merkmal (für Beurteilungs-Referenzen)."""
    sm = _normen.get_sub_merkmal(norm_id, sub_id)
    if not sm:
        return jsonify({'error': 'Sub-Merkmal nicht gefunden'}), 404
    return jsonify(sm)


@gutachten_bp.get('/normen-search')
@jwt_required()
def normen_search():
    """G0-1 — Volltextsuche."""
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'results': []})
    return jsonify({'results': _normen.search_normen(q)})


@gutachten_bp.post('/lint')
@jwt_required()
def lint_text():
    """G0-2 — Universal-Linter. Body: {text, context: 'audit'|'gerichts', kind: 'sprache'|'cross_ref'|'anonym'|'alle'}."""
    body = request.get_json(silent=True) or {}
    text = body.get('text') or ''
    context = body.get('context') or 'gerichts'
    kind = body.get('kind') or 'sprache'
    return jsonify({'hints': _linters.lint(text, context=context, kind=kind)})


@gutachten_bp.get('/werkzeuge')
@jwt_required()
def werkzeuge_list():
    """G0-3 — Liste aller Werkzeuge im Register."""
    return jsonify({'werkzeuge': _werkzeuge.list_werkzeuge(DB_PATH)})


@gutachten_bp.post('/werkzeuge')
@jwt_required()
def werkzeuge_create():
    """G0-3 — Neues Werkzeug im Register."""
    body = request.get_json(silent=True) or {}
    name = (body.get('tool_name') or '').strip()
    version = (body.get('version') or '').strip()
    if not name or not version:
        return jsonify({'error': 'tool_name + version sind Pflichtfelder'}), 400
    try:
        wid = _werkzeuge.save_werkzeug(
            DB_PATH,
            tool_name=name,
            version=version,
            hersteller=body.get('hersteller', ''),
            zweck=body.get('zweck', ''),
            nachweis_url=body.get('nachweis_url', ''),
            bemerkungen=body.get('bemerkungen', ''),
            erstellt_von=body.get('erstellt_von', ''),
        )
        return jsonify({'id': wid, 'ok': True}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@gutachten_bp.delete('/werkzeuge/<int:werkzeug_id>')
@jwt_required()
def werkzeuge_delete(werkzeug_id: int):
    """G0-3 — Werkzeug entfernen."""
    _werkzeuge.delete_werkzeug(DB_PATH, werkzeug_id)
    return '', 204


@gutachten_bp.post('/befangenheits-check')
@jwt_required()
def befangenheits_check():
    """G0-9 — Befangenheits-Warnung. Body: {firma, system, partei_namen[], sv_user}."""
    body = request.get_json(silent=True) or {}
    firma = (body.get('firma') or '').strip()
    system = (body.get('system') or '').strip()
    parteien = body.get('partei_namen') or []
    sv_user = body.get('sv_user') or ''
    if not firma:
        return jsonify({'error': '`firma` ist Pflichtfeld'}), 400
    treffer = _befangenheit.check(DB_PATH, firma=firma, system=system, parteien=parteien)
    risiko = _befangenheit.aggregate_risk(treffer)
    _befangenheit.log_check(DB_PATH, sv_user=sv_user, firma=firma, system=system,
                            treffer_json=json.dumps(treffer, ensure_ascii=False),
                            entscheidung='pending')
    return jsonify({
        'firma': firma,
        'system': system,
        'treffer': treffer,
        'risiko': risiko,
        'empfehlung': _befangenheit.recommendation(risiko),
    })


@gutachten_bp.post('/befangenheits-check/<int:log_id>/entscheidung')
@jwt_required()
def befangenheits_entscheidung(log_id: int):
    """G0-9 — Markiere Entscheidung (annehmen|ablehnen) zu einem Check."""
    body = request.get_json(silent=True) or {}
    entscheidung = body.get('entscheidung', '')
    if entscheidung not in ('annehmen', 'ablehnen', 'offen'):
        return jsonify({'error': 'entscheidung muss annehmen|ablehnen|offen sein'}), 400
    _befangenheit.update_entscheidung(DB_PATH, log_id, entscheidung)
    return jsonify({'ok': True})


# ============================================================
# G0-4 Honorar-Tracker
# ============================================================
from gutachten import honorar as _honorar


@gutachten_bp.get('/honorar/kategorien')
@jwt_required()
def honorar_kategorien():
    return jsonify({
        'kategorien': _honorar.list_kategorien(),
        'jveg_tarife': _honorar.list_jveg_tarife(),
    })


@gutachten_bp.get('/honorar/eintraege')
@jwt_required()
def honorar_list():
    projekt_typ = request.args.get('projekt_typ')
    projekt_name = request.args.get('projekt_name')
    sv_user = request.args.get('sv_user')
    eintraege = _honorar.list_eintraege(DB_PATH, projekt_typ, projekt_name, sv_user)
    return jsonify({'eintraege': eintraege})


@gutachten_bp.post('/honorar/eintraege')
@jwt_required()
def honorar_save():
    body = request.get_json(silent=True) or {}
    try:
        eid = _honorar.save_eintrag(
            DB_PATH,
            sv_user=body.get('sv_user', ''),
            projekt_typ=body.get('projekt_typ', 'gerichts'),
            projekt_name=body.get('projekt_name', ''),
            kategorie=body.get('kategorie', 'sonstiges'),
            dauer_minuten=int(body.get('dauer_minuten') or 0),
            beschreibung=body.get('beschreibung', ''),
            tarif_modell=body.get('tarif_modell', 'jveg'),
            stundensatz_eur=float(body.get('stundensatz_eur') or 0.0),
            auslage_eur=float(body.get('auslage_eur') or 0.0),
            datum=body.get('datum'),
        )
        return jsonify({'id': eid, 'ok': True}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@gutachten_bp.delete('/honorar/eintraege/<int:eintrag_id>')
@jwt_required()
def honorar_delete(eintrag_id: int):
    _honorar.delete_eintrag(DB_PATH, eintrag_id)
    return '', 204


@gutachten_bp.get('/honorar/summary')
@jwt_required()
def honorar_summary():
    projekt_typ = request.args.get('projekt_typ')
    projekt_name = request.args.get('projekt_name')
    return jsonify(_honorar.summary(DB_PATH, projekt_typ, projekt_name))


# ============================================================
# G0-5 Living-Norms-Watcher
# ============================================================
from gutachten import norms_watcher as _norms_watcher


@gutachten_bp.post('/normen/subscribe')
@jwt_required()
def normen_subscribe():
    body = request.get_json(silent=True) or {}
    norm_id = (body.get('norm_id') or '').strip()
    projekt_typ = body.get('projekt_typ', 'gerichts')
    projekt_name = (body.get('projekt_name') or '').strip()
    if not norm_id or not projekt_name:
        return jsonify({'error': 'norm_id + projekt_name sind Pflicht'}), 400
    try:
        _norms_watcher.subscribe(DB_PATH, norm_id, projekt_typ, projekt_name)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True})


@gutachten_bp.post('/normen/unsubscribe')
@jwt_required()
def normen_unsubscribe():
    body = request.get_json(silent=True) or {}
    _norms_watcher.unsubscribe(
        DB_PATH,
        body.get('norm_id', ''),
        body.get('projekt_typ', 'gerichts'),
        body.get('projekt_name', ''),
    )
    return jsonify({'ok': True})


@gutachten_bp.get('/normen/subscriptions')
@jwt_required()
def normen_subscriptions():
    return jsonify({'subscriptions': _norms_watcher.list_subscriptions(
        DB_PATH,
        norm_id=request.args.get('norm_id'),
        projekt_typ=request.args.get('projekt_typ'),
        projekt_name=request.args.get('projekt_name'),
    )})


@gutachten_bp.post('/normen/check-updates')
@jwt_required()
def normen_check_updates():
    updates = _norms_watcher.check_updates(DB_PATH)
    return jsonify({'updates': updates, 'count': len(updates)})


@gutachten_bp.get('/normen/notifications')
@jwt_required()
def normen_notifications():
    only_open = request.args.get('only_open', 'true').lower() == 'true'
    return jsonify({'notifications': _norms_watcher.list_notifications(DB_PATH, only_open=only_open)})


@gutachten_bp.post('/normen/notifications/<int:notif_id>/ack')
@jwt_required()
def normen_notification_ack(notif_id: int):
    _norms_watcher.acknowledge_notification(DB_PATH, notif_id)
    return jsonify({'ok': True})


# ============================================================
# G0-6/7/8 Cross-View + Audit-Kandidaten + Norm-Zitate
# ============================================================
from gutachten import cross_view as _cross_view


@gutachten_bp.get('/firma/<firma>/gutachten')
@jwt_required()
def cross_view_firma(firma: str):
    """G0-7 — alle Gutachten zum Firmen mit Warnung bei Mischbestand."""
    return jsonify(_cross_view.list_gutachten_for_firma(DB_PATH, firma))


@gutachten_bp.get('/firma/<firma>/audit-kandidaten')
@jwt_required()
def cross_view_kandidaten(firma: str):
    """G0-6 — Read-only Liste von Audit-Bewertungs-Lücken als Kandidaten-Anhaltspunkte."""
    system = request.args.get('system', '')
    return jsonify({
        'firma': firma,
        'kandidaten': _cross_view.list_audit_kandidaten(DB_PATH, firma, system),
        'disclaimer': (
            'Die persönliche Tatsachenfeststellung kann nicht delegiert werden (§ 407a Abs. 2 ZPO). '
            'Die hier gelisteten Audit-Inhalte dienen ausschließlich als Anhaltspunkt — '
            'der Sachverständige muss jeden Befund unabhängig neu erheben und formulieren.'
        ),
    })


@gutachten_bp.post('/audit/<audit_projekt>/norm-zitat')
@jwt_required()
def cross_view_link_norm(audit_projekt: str):
    """G0-8 — markiert, dass ein Audit-Bericht eine Norm zitiert (für Living-Norms-Watcher)."""
    body = request.get_json(silent=True) or {}
    norm_id = (body.get('norm_id') or '').strip()
    if not norm_id:
        return jsonify({'error': 'norm_id Pflicht'}), 400
    _cross_view.link_norm_to_audit(DB_PATH, audit_projekt, norm_id, body.get('kategorie_id', ''))
    return jsonify({'ok': True}), 201


@gutachten_bp.get('/audit/<audit_projekt>/norm-zitate')
@jwt_required()
def cross_view_norm_zitate(audit_projekt: str):
    return jsonify({'zitate': _cross_view.list_norm_zitate(DB_PATH, audit_projekt)})


# ============================================================
# Phase G1 — Gerichtsgutachten (DB + DOCX)
# ============================================================
from gutachten import gerichts_db as _gdb
from gutachten import gerichtsgutachten_gen as _ggen


# ─── Projekte ───
@gutachten_bp.get('/gerichts')
@jwt_required()
def gerichts_list():
    return jsonify({'projekte': _gdb.list_gerichts_projekte(DB_PATH)})


@gutachten_bp.get('/gerichts/<path:projekt_name>')
@jwt_required()
def gerichts_get(projekt_name: str):
    p = _gdb.load_gerichts_projekt(DB_PATH, projekt_name)
    if not p:
        return jsonify({'error': 'nicht gefunden'}), 404
    return jsonify(p)


@gutachten_bp.post('/gerichts')
@jwt_required()
def gerichts_create():
    body = _allowlist(request.get_json(silent=True), _GERICHTS_PROJEKT_FIELDS)
    try:
        name = _gdb.save_gerichts_projekt(DB_PATH, **body)
        return jsonify({'name': name, 'ok': True}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@gutachten_bp.put('/gerichts/<path:projekt_name>')
@jwt_required()
def gerichts_update(projekt_name: str):
    body = _allowlist(request.get_json(silent=True), _GERICHTS_PROJEKT_FIELDS)
    body['name'] = projekt_name
    existing = _gdb.load_gerichts_projekt(DB_PATH, projekt_name) or {}
    cur_status = existing.get('status', 'in_bearbeitung')
    # #966: Vertraulichkeit nach Finalisierung sperren.
    if ('vertraulichkeit' in body
            and cur_status in ('finalisiert', 'eingereicht')
            and (body.get('vertraulichkeit') or '') != (existing.get('vertraulichkeit') or '')):
        return jsonify({'error': 'vertraulichkeit nach Finalisierung gesperrt',
                        'current_status': cur_status}), 409
    try:
        _gdb.save_gerichts_projekt(DB_PATH, **body)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    # #966: Status-Wechsel auditieren.
    new_status = body.get('status', cur_status)
    if new_status != cur_status:
        try:
            from shared.audit import audit_event
            from flask_jwt_extended import get_jwt_identity
            audit_event('gutachten.status_changed', module='gutachten', outcome='success',
                        details={'projekt': projekt_name, 'alt': cur_status, 'neu': new_status,
                                 'user': get_jwt_identity()})
        except Exception:
            current_app.logger.exception('Audit gutachten.status_changed fehlgeschlagen')
    return jsonify({'ok': True})


@gutachten_bp.delete('/gerichts/<path:projekt_name>')
@jwt_required()
def gerichts_delete(projekt_name: str):
    _gdb.delete_gerichts_projekt(DB_PATH, projekt_name)
    return '', 204


# ─── Beweisfragen ───
@gutachten_bp.get('/gerichts/<projekt_name>/beweisfragen')
@jwt_required()
def gerichts_beweisfragen_list(projekt_name: str):
    return jsonify({'beweisfragen': _gdb.list_beweisfragen(DB_PATH, projekt_name)})


@gutachten_bp.post('/gerichts/<projekt_name>/beweisfragen')
@jwt_required()
def gerichts_beweisfrage_save(projekt_name: str):
    body = _allowlist(request.get_json(silent=True), _GERICHTS_BEWEISFRAGE_FIELDS)
    body['projekt_name'] = projekt_name
    bid = _gdb.save_beweisfrage(DB_PATH, **body)
    return jsonify({'id': bid, 'ok': True}), 201


@gutachten_bp.delete('/gerichts/beweisfragen/<int:bfid>')
@jwt_required()
def gerichts_beweisfrage_delete(bfid: int):
    _gdb.delete_beweisfrage(DB_PATH, bfid)
    return '', 204


# ─── Befunde ───
@gutachten_bp.get('/gerichts/<projekt_name>/befunde')
@jwt_required()
def gerichts_befunde_list(projekt_name: str):
    return jsonify({'befunde': _gdb.list_befunde(DB_PATH, projekt_name)})


@gutachten_bp.post('/gerichts/<projekt_name>/befunde')
@jwt_required()
def gerichts_befund_save(projekt_name: str):
    body = _allowlist(request.get_json(silent=True), _GERICHTS_BEFUND_FIELDS)
    body['projekt_name'] = projekt_name
    _sanitize_html_fields(body)
    bid = _gdb.save_befund(DB_PATH, **body)
    return jsonify({'id': bid, 'ok': True}), 201


@gutachten_bp.delete('/gerichts/befunde/<int:bid>')
@jwt_required()
def gerichts_befund_delete(bid: int):
    _gdb.delete_befund(DB_PATH, bid)
    return '', 204


# ─── Beurteilungen ───
@gutachten_bp.get('/gerichts/<projekt_name>/beurteilungen')
@jwt_required()
def gerichts_beurteilungen_list(projekt_name: str):
    return jsonify({'beurteilungen': _gdb.list_beurteilungen(DB_PATH, projekt_name)})


@gutachten_bp.post('/gerichts/<projekt_name>/beurteilungen')
@jwt_required()
def gerichts_beurteilung_save(projekt_name: str):
    body = _allowlist(request.get_json(silent=True), _GERICHTS_BEURTEILUNG_FIELDS)
    body['projekt_name'] = projekt_name
    _sanitize_html_fields(body)
    bid = _gdb.save_beurteilung(DB_PATH, **body)
    return jsonify({'id': bid, 'ok': True}), 201


@gutachten_bp.delete('/gerichts/beurteilungen/<int:bid>')
@jwt_required()
def gerichts_beurteilung_delete(bid: int):
    _gdb.delete_beurteilung(DB_PATH, bid)
    return '', 204


# ─── Assets ───
@gutachten_bp.get('/gerichts/<projekt_name>/assets')
@jwt_required()
def gerichts_assets_list(projekt_name: str):
    return jsonify({'assets': _gdb.list_assets(DB_PATH, projekt_name)})


@gutachten_bp.post('/gerichts/<projekt_name>/assets')
@jwt_required()
def gerichts_asset_save(projekt_name: str):
    body = _allowlist(request.get_json(silent=True), _GERICHTS_ASSET_FIELDS)
    body['projekt_name'] = projekt_name
    aid = _gdb.save_asset(DB_PATH, **body)
    return jsonify({'id': aid, 'ok': True}), 201


@gutachten_bp.delete('/gerichts/assets/<int:aid>')
@jwt_required()
def gerichts_asset_delete(aid: int):
    _gdb.delete_asset(DB_PATH, aid)
    return '', 204


@gutachten_bp.post('/gerichts/sha256')
@jwt_required()
def gerichts_sha256():
    """Berechnet SHA-256 für eine hochgeladene Datei (Multipart)."""
    if 'file' not in request.files:
        return jsonify({'error': 'file fehlt'}), 400
    data = request.files['file'].read()
    return jsonify({'sha256': _gdb.compute_sha256(data), 'size_bytes': len(data)})


# ─── Verfahrensereignisse ───
@gutachten_bp.get('/gerichts/<projekt_name>/verfahren')
@jwt_required()
def gerichts_verfahren_list(projekt_name: str):
    return jsonify({'ereignisse': _gdb.list_verfahrensereignisse(DB_PATH, projekt_name)})


@gutachten_bp.post('/gerichts/<projekt_name>/verfahren')
@jwt_required()
def gerichts_verfahren_save(projekt_name: str):
    body = _allowlist(request.get_json(silent=True), _GERICHTS_VERFAHREN_FIELDS)
    body['projekt_name'] = projekt_name
    eid = _gdb.save_verfahrensereignis(DB_PATH, **body)
    return jsonify({'id': eid, 'ok': True}), 201


@gutachten_bp.delete('/gerichts/verfahren/<int:eid>')
@jwt_required()
def gerichts_verfahren_delete(eid: int):
    _gdb.delete_verfahrensereignis(DB_PATH, eid)
    return '', 204


@gutachten_bp.put('/gerichts/<projekt_name>/verfahren/reorder')
@jwt_required()
def gerichts_verfahren_reorder(projekt_name: str):
    """#979: manuelle Reihenfolge der Verfahrensereignisse setzen. Body: {ordered_ids:[...]}."""
    body = request.get_json(silent=True) or {}
    ids = body.get('ordered_ids') or []
    if not isinstance(ids, list):
        return jsonify({'error': 'ordered_ids muss eine Liste sein'}), 400
    _gdb.reorder_verfahrensereignisse(DB_PATH, projekt_name, [int(x) for x in ids])
    return jsonify({'ok': True})


# ─── DOCX-Export + Validator ───
@gutachten_bp.get('/gerichts/<projekt_name>/validate')
@jwt_required()
def gerichts_validate(projekt_name: str):
    errors = _ggen.validate_pflichtfelder(DB_PATH, projekt_name)
    return jsonify({'errors': errors, 'release_ready': not errors})


@gutachten_bp.get('/gerichts/<path:projekt_name>/docx')
@jwt_required()
def gerichts_docx(projekt_name: str):
    # #956/#967/#968: Export-Optionen (alle Default an).
    def _flag(name):
        return request.args.get(name, 'true').lower() != 'false'
    export_options = {
        'include_anhang': _flag('include_anhang'),
        'include_methode_werkzeug': _flag('include_methode_werkzeug'),
        'include_beurteilung_subheadings': _flag('include_beurteilung_subheadings'),
        'include_verfahren_datum': _flag('include_verfahren_datum'),  # #979
        'include_glossar': _flag('include_glossar'),  # #985
    }
    include_anhang = export_options['include_anhang']
    # #1000: Dateiname-Stamm <Datum>_<Projekt>_<PG|GG>
    _base = _ggen.export_basename(_gdb.load_gerichts_projekt(DB_PATH, projekt_name) or {'name': projekt_name})
    # #957: optional in eine hochgeladene Custom-Vorlage rendern.
    template_id = request.args.get('template_id')
    from io import BytesIO

    if template_id:
        try:
            import json as _json
            from gutachten.template_render import (
                build_template_context, render_with_template,
                render_with_bracket_mapping, template_has_jinja,
            )
            tpl = _gdb.get_template(DB_PATH, int(template_id))
            if not tpl:
                return jsonify({'error': 'Vorlage nicht gefunden'}), 404
            tpl_path = Path(tpl['datei_pfad'])
            ctx = build_template_context(DB_PATH, projekt_name)
            ctx.update(export_options)  # #977: Toggles auch im Vorlagen-Pfad wirksam
            import uuid
            out = _TEMPLATE_DIR.parent / f'_render_{uuid.uuid4().hex}.docx'
            if template_has_jinja(tpl_path):
                render_with_template(tpl_path, ctx, out)
            else:
                mapping = _json.loads(tpl.get('mapping_json') or '{}')
                render_with_bracket_mapping(tpl_path, mapping, ctx, out)
            data = out.read_bytes()
            try:
                out.unlink(missing_ok=True)
            except Exception:
                pass
            fname = f"{_base}_vorlage.docx"  # #1000
            return send_file(BytesIO(data),
                             mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                             as_attachment=True, download_name=fname)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

    try:
        doc = _ggen.build_gerichtsgutachten_docx(projekt_name, DB_PATH, export_options=export_options)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    suffix = '' if include_anhang else '_ohne-anhang'
    fname = f"{_base}{suffix}.docx"  # #1000
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                     as_attachment=True, download_name=fname)


# ============================================================
# Phase G2 — 5 BISG-Wizards
# ============================================================
from gutachten import wizards as _wizards


@gutachten_bp.get('/gerichts/wizards/selbstcheck-fragen')
@jwt_required()
def gerichts_wizard_selbstcheck_fragen():
    return jsonify({'fragen': _wizards.SELBSTCHECK_FRAGEN})


@gutachten_bp.post('/gerichts/<projekt_name>/wizards/selbstcheck')
@jwt_required()
def gerichts_wizard_selbstcheck(projekt_name: str):
    body = request.get_json(silent=True) or {}
    antworten = body.get('antworten') or {}
    sv_user = body.get('sv_user') or ''
    return jsonify(_wizards.selbstcheck(DB_PATH, projekt_name, antworten, sv_user))


@gutachten_bp.post('/gerichts/<projekt_name>/wizards/asservat/protokoll')
@jwt_required()
def gerichts_wizard_asservat_protokoll(projekt_name: str):
    """Generiert Sicherungsprotokoll für ein Asset (asset-id im Body)."""
    body = request.get_json(silent=True) or {}
    asset_id = body.get('asset_id')
    if not asset_id:
        return jsonify({'error': 'asset_id Pflicht'}), 400
    assets = _gdb.list_assets(DB_PATH, projekt_name)
    asset = next((a for a in assets if a['id'] == int(asset_id)), None)
    if not asset:
        return jsonify({'error': 'asset nicht gefunden'}), 404
    return jsonify(_wizards.sicherungsprotokoll(asset))


@gutachten_bp.post('/gerichts/wizards/befund-validate')
@jwt_required()
def gerichts_wizard_befund_validate():
    """Befund-Text vor Save validieren (live im Editor)."""
    body = request.get_json(silent=True) or {}
    return jsonify(_wizards.validate_befund_text(body.get('text', '')))


@gutachten_bp.post('/gerichts/<projekt_name>/wizards/beurteilung/prompt')
@jwt_required()
def gerichts_wizard_beurteilung_prompt(projekt_name: str):
    body = request.get_json(silent=True) or {}
    norm_id = (body.get('norm_id') or '').strip()
    if not norm_id:
        return jsonify({'error': 'norm_id Pflicht'}), 400
    befund_ids = body.get('befund_ids') or []
    projekt = _gdb.load_gerichts_projekt(DB_PATH, projekt_name)
    if not projekt:
        return jsonify({'error': 'projekt nicht gefunden'}), 404
    all_befunde = _gdb.list_befunde(DB_PATH, projekt_name)
    befunde = [b for b in all_befunde if not befund_ids or b['id'] in befund_ids]
    try:
        prompt = _wizards.build_beurteilung_prompt(projekt, befunde, norm_id, body.get('sub_id'))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'prompt': prompt})


@gutachten_bp.post('/gerichts/<projekt_name>/wizards/beurteilung/parse')
@jwt_required()
def gerichts_wizard_beurteilung_parse(projekt_name: str):
    body = request.get_json(silent=True) or {}
    response = body.get('response') or ''
    norm_id = body.get('norm_id') or ''
    sub_id = body.get('sub_id')
    parsed = _wizards.parse_beurteilung_response(response, norm_id, sub_id)
    return jsonify({'parsed': parsed, 'applied': False,
                    'hinweis_407a': 'Bitte vor Speichern persönlich übernehmen (§ 407a Abs. 2 ZPO).'})


@gutachten_bp.get('/gerichts/<projekt_name>/wizards/schluss-validator')
@jwt_required()
def gerichts_wizard_schluss(projekt_name: str):
    return jsonify(_wizards.schluss_validator(DB_PATH, projekt_name))


# ============================================================
# Phase G3 — Schutzschilde
# ============================================================
from gutachten import schutzschilde as _schutz


@gutachten_bp.post('/gerichts/<projekt_name>/parteikommunikation')
@jwt_required()
def gerichts_parteikom_log(projekt_name: str):
    body = request.get_json(silent=True) or {}
    eid = _schutz.log_parteikommunikation(
        DB_PATH, projekt_name,
        titel=body.get('titel', ''),
        beschreibung=body.get('beschreibung', ''),
        empfaenger=body.get('empfaenger') or [],
        ereignis_datum=body.get('ereignis_datum'),
    )
    return jsonify({'id': eid, 'ok': True}), 201


@gutachten_bp.get('/gerichts/<projekt_name>/symmetrie-check')
@jwt_required()
def gerichts_symmetrie(projekt_name: str):
    return jsonify(_schutz.check_symmetrie(DB_PATH, projekt_name))


@gutachten_bp.post('/gerichts/befunde/<int:bid>/non-liquet')
@jwt_required()
def gerichts_befund_nonliquet(bid: int):
    body = request.get_json(silent=True) or {}
    grund = (body.get('grund') or '').strip()
    if not grund:
        return jsonify({'error': 'grund Pflicht'}), 400
    _schutz.mark_non_liquet_befund(DB_PATH, bid, grund)
    return jsonify({'ok': True})


@gutachten_bp.post('/gerichts/beurteilungen/<int:uid>/non-liquet')
@jwt_required()
def gerichts_beurteilung_nonliquet(uid: int):
    body = request.get_json(silent=True) or {}
    grund = (body.get('grund') or '').strip()
    if not grund:
        return jsonify({'error': 'grund Pflicht'}), 400
    _schutz.mark_non_liquet_beurteilung(DB_PATH, uid, grund)
    return jsonify({'ok': True})


@gutachten_bp.get('/gerichts/<projekt_name>/non-liquet')
@jwt_required()
def gerichts_nonliquet_list(projekt_name: str):
    return jsonify(_schutz.list_non_liquet(DB_PATH, projekt_name))


@gutachten_bp.get('/gerichts/disclaimer-407a')
@jwt_required()
def gerichts_disclaimer_407a():
    return jsonify({'text': _schutz.DISCLAIMER_407A})


@gutachten_bp.post('/gerichts/<projekt_name>/ki-akzeptanz')
@jwt_required()
def gerichts_ki_akzeptanz_log(projekt_name: str):
    body = request.get_json(silent=True) or {}
    aid = _schutz.log_ki_akzeptanz(
        DB_PATH, projekt_name,
        vorschlag_typ=body.get('vorschlag_typ', ''),
        vorschlag_text=body.get('vorschlag_text', ''),
        akzeptiert_von=body.get('akzeptiert_von', ''),
        akzeptiert=bool(body.get('akzeptiert', True)),
    )
    return jsonify({'id': aid, 'ok': True}), 201


@gutachten_bp.get('/gerichts/<projekt_name>/ki-akzeptanz')
@jwt_required()
def gerichts_ki_akzeptanz_list(projekt_name: str):
    return jsonify({'eintraege': _schutz.list_ki_akzeptanz(DB_PATH, projekt_name)})


# ============================================================
# Phase G4 — Forensik-Workflow
# ============================================================
from gutachten import forensik as _forensik


@gutachten_bp.get('/gerichts/assets/<int:aid>/sicherungsprotokoll.pdf')
@jwt_required()
def gerichts_asset_protokoll_pdf(aid: int):
    """G4-1 — Sicherungsprotokoll als PDF."""
    con = __import__('sqlite3').connect(str(DB_PATH))
    con.row_factory = __import__('sqlite3').Row
    try:
        r = con.execute("SELECT * FROM gerichtsgutachten_assets WHERE id=?", (aid,)).fetchone()
    finally:
        con.close()
    if not r:
        return jsonify({'error': 'asset nicht gefunden'}), 404
    asset = dict(r)
    if asset.get("parteien_anwesend"):
        try:
            asset["parteien_anwesend"] = json.loads(asset["parteien_anwesend"])
        except Exception:
            asset["parteien_anwesend"] = []
    pdf = _forensik.build_sicherungsprotokoll_pdf(asset)
    from io import BytesIO
    return send_file(BytesIO(pdf), mimetype='application/pdf', as_attachment=True,
                     download_name=f"sicherungsprotokoll_{aid}.pdf")


@gutachten_bp.get('/gerichts/<projekt_name>/werkzeug-validator')
@jwt_required()
def gerichts_werkzeug_validator(projekt_name: str):
    return jsonify(_forensik.validate_werkzeuge_in_befunden(DB_PATH, projekt_name))


@gutachten_bp.get('/gerichts/<projekt_name>/macb')
@jwt_required()
def gerichts_macb_list(projekt_name: str):
    return jsonify({'eintraege': _forensik.list_macb(DB_PATH, projekt_name)})


@gutachten_bp.post('/gerichts/<projekt_name>/macb')
@jwt_required()
def gerichts_macb_save(projekt_name: str):
    body = _allowlist(
        request.get_json(silent=True),
        ('id', 'projekt_name', 'datei_pfad', 'modified_at', 'accessed_at',
         'changed_at', 'born_at', 'bemerkung'),
    )
    body['projekt_name'] = projekt_name
    mid = _forensik.save_macb(DB_PATH, **body)
    return jsonify({'id': mid, 'ok': True}), 201


@gutachten_bp.delete('/gerichts/macb/<int:mid>')
@jwt_required()
def gerichts_macb_delete(mid: int):
    _forensik.delete_macb(DB_PATH, mid)
    return '', 204


@gutachten_bp.get('/gerichts/volatility-checklist')
@jwt_required()
def gerichts_volatility():
    return jsonify({'checklist': _forensik.get_volatility_checklist()})


@gutachten_bp.post('/gerichts/log-classify')
@jwt_required()
def gerichts_log_classify():
    if 'file' not in request.files:
        body = request.get_json(silent=True) or {}
        filename = body.get('filename', '')
        return jsonify({'klasse': _forensik.classify_log(filename)})
    f = request.files['file']
    head = f.read(2000)
    return jsonify({'klasse': _forensik.classify_log(f.filename or '', head),
                    'filename': f.filename})


# ============================================================
# Phase G5 — Qualitäts-Gates + Compliance
# ============================================================
from gutachten import qualitaet as _qual


# G5-2 Peer-Review
@gutachten_bp.post('/gerichts/<projekt_name>/peer-review/request')
@jwt_required()
def gerichts_peer_request(projekt_name: str):
    body = request.get_json(silent=True) or {}
    rid = _qual.request_peer_review(DB_PATH, projekt_name, body.get('reviewer_name', ''))
    return jsonify({'id': rid, 'ok': True}), 201


@gutachten_bp.post('/gerichts/peer-review/<int:rid>/kommentar')
@jwt_required()
def gerichts_peer_kommentar(rid: int):
    body = request.get_json(silent=True) or {}
    try:
        _qual.add_peer_kommentar(DB_PATH, rid, body.get('kapitel', ''),
                                 body.get('text', ''), body.get('author', ''))
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    return jsonify({'ok': True})


@gutachten_bp.post('/gerichts/peer-review/<int:rid>/close')
@jwt_required()
def gerichts_peer_close(rid: int):
    _qual.close_peer_review(DB_PATH, rid)
    return jsonify({'ok': True})


@gutachten_bp.get('/gerichts/<projekt_name>/peer-review')
@jwt_required()
def gerichts_peer_list(projekt_name: str):
    return jsonify({'reviews': _qual.list_peer_reviews(DB_PATH, projekt_name)})


# G5-3 PDF + QES
@gutachten_bp.get('/gerichts/<projekt_name>/pdf')
@jwt_required()
def gerichts_pdf(projekt_name: str):
    try:
        doc = _ggen.build_gerichtsgutachten_docx(projekt_name, DB_PATH)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    from io import BytesIO
    docx_buf = BytesIO()
    doc.save(docx_buf)
    pdf_bytes = _qual.docx_to_pdf_bytes(docx_buf.getvalue())
    return send_file(BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True,
                     download_name=f"Gerichtsgutachten_{projekt_name}.pdf")


@gutachten_bp.get('/gerichts/<projekt_name>/pdf/sha256')
@jwt_required()
def gerichts_pdf_hash(projekt_name: str):
    try:
        doc = _ggen.build_gerichtsgutachten_docx(projekt_name, DB_PATH)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    from io import BytesIO
    docx_buf = BytesIO()
    doc.save(docx_buf)
    pdf_bytes = _qual.docx_to_pdf_bytes(docx_buf.getvalue())
    return jsonify({
        'sha256': _qual.compute_hash_sidecar(pdf_bytes),
        'qes_hinweis': _qual.QES_HINWEIS,
    })


# G5-4 Rechnung
@gutachten_bp.get('/gerichts/<projekt_name>/rechnung.pdf')
@jwt_required()
def gerichts_rechnung(projekt_name: str):
    auftraggeber = request.args.get('auftraggeber', '')
    rechnungs_nr = request.args.get('rechnungs_nr', f"RE-{datetime.now().strftime('%Y%m%d')}-{projekt_name}")
    pdf = _qual.build_rechnung_pdf(DB_PATH, projekt_name, projekt_typ='gerichts',
                                    rechnungs_nr=rechnungs_nr, auftraggeber=auftraggeber)
    from io import BytesIO
    return send_file(BytesIO(pdf), mimetype='application/pdf', as_attachment=True,
                     download_name=f"Rechnung_{rechnungs_nr}.pdf")


# G5-5 10-Jahre-Aufbewahrung + Archiv
@gutachten_bp.post('/gerichts/<projekt_name>/aufbewahrung')
@jwt_required()
def gerichts_aufbewahrung_set(projekt_name: str):
    body = request.get_json(silent=True) or {}
    jahre = int(body.get('jahre') or 10)
    bis = _qual.set_aufbewahrung(DB_PATH, projekt_name, jahre)
    return jsonify({'archiv_bis_datum': bis, 'ok': True})


@gutachten_bp.get('/gerichts/<projekt_name>/aufbewahrung')
@jwt_required()
def gerichts_aufbewahrung_get(projekt_name: str):
    d = _qual.get_aufbewahrung(DB_PATH, projekt_name)
    return jsonify(d) if d else (jsonify({}), 404)


@gutachten_bp.get('/gerichts/archive-due')
@jwt_required()
def gerichts_archive_due():
    return jsonify({'projekte': _qual.list_archive_due(DB_PATH)})


@gutachten_bp.get('/gerichts/<projekt_name>/archiv.zip')
@jwt_required()
def gerichts_archiv(projekt_name: str):
    from io import BytesIO
    docx_bytes = None
    try:
        doc = _ggen.build_gerichtsgutachten_docx(projekt_name, DB_PATH)
        buf = BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()
    except ValueError:
        pass
    zip_bytes = _qual.build_archiv_zip(DB_PATH, projekt_name, docx_bytes=docx_bytes)
    return send_file(BytesIO(zip_bytes), mimetype='application/zip', as_attachment=True,
                     download_name=f"Archiv_{projekt_name}.zip")


# ============================================================
# Phase G6 — Kreative Ideen
# ============================================================
from gutachten import ideen as _ideen


# G6-1 Hypothesen-Tree
@gutachten_bp.get('/gerichts/hypothesen/beurteilung/<int:bid>')
@jwt_required()
def gerichts_hypothesen_list(bid: int):
    return jsonify({'hypothesen': _ideen.list_hypothesen(DB_PATH, beurteilung_id=bid)})


@gutachten_bp.get('/gerichts/<projekt_name>/hypothesen')
@jwt_required()
def gerichts_hypothesen_projekt(projekt_name: str):
    return jsonify({'hypothesen': _ideen.list_hypothesen(DB_PATH, projekt_name=projekt_name)})


@gutachten_bp.post('/gerichts/hypothesen')
@jwt_required()
def gerichts_hypothese_save():
    body = request.get_json(silent=True) or {}
    hid = _ideen.save_hypothese(
        DB_PATH,
        beurteilung_id=int(body.get('beurteilung_id') or 0),
        hypothese_text=body.get('hypothese_text', ''),
        status=body.get('status', 'offen'),
        begruendung=body.get('begruendung', ''),
    )
    return jsonify({'id': hid, 'ok': True}), 201


@gutachten_bp.put('/gerichts/hypothesen/<int:hid>')
@jwt_required()
def gerichts_hypothese_update(hid: int):
    body = request.get_json(silent=True) or {}
    _ideen.update_hypothese_status(DB_PATH, hid, body.get('status', 'offen'), body.get('begruendung', ''))
    return jsonify({'ok': True})


@gutachten_bp.delete('/gerichts/hypothesen/<int:hid>')
@jwt_required()
def gerichts_hypothese_delete(hid: int):
    _ideen.delete_hypothese(DB_PATH, hid)
    return '', 204


# G6-2 Drittgutachter-Simulator
@gutachten_bp.post('/gerichts/befunde/<int:bid>/drittgutachter/prompt')
@jwt_required()
def gerichts_drittgutachter_prompt(bid: int):
    con = __import__('sqlite3').connect(str(DB_PATH))
    con.row_factory = __import__('sqlite3').Row
    try:
        r = con.execute("SELECT * FROM gerichtsgutachten_befunde WHERE id=?", (bid,)).fetchone()
    finally:
        con.close()
    if not r:
        return jsonify({'error': 'befund nicht gefunden'}), 404
    return jsonify({'prompt': _ideen.build_drittgutachter_prompt(dict(r))})


@gutachten_bp.post('/gerichts/drittgutachter/audit')
@jwt_required()
def gerichts_drittgutachter_audit():
    body = request.get_json(silent=True) or {}
    return jsonify(_ideen.selbst_audit(body))


# G6-6 Cross-Ref-Linter für Gerichtsgutachten
@gutachten_bp.get('/gerichts/<projekt_name>/cross-ref-check')
@jwt_required()
def gerichts_cross_ref_check(projekt_name: str):
    return jsonify(_ideen.cross_ref_check_gerichts(DB_PATH, projekt_name))


# G6-7 Anonymisierte Projekt-Daten
@gutachten_bp.get('/gerichts/<projekt_name>/anonymized')
@jwt_required()
def gerichts_anonymized(projekt_name: str):
    return jsonify(_ideen.anonymize_gerichts_data(DB_PATH, projekt_name))


# ============================================================
# Hilfen (#671) — BISG-Schulungs-Kontext pro Workflow-Punkt
# ============================================================
from gutachten import bisg_help as _help


@gutachten_bp.get('/help/keys')
@jwt_required()
def help_keys():
    return jsonify({'keys': _help.list_keys()})


@gutachten_bp.get('/help/<key>')
@jwt_required()
def help_get(key: str):
    h = _help.get_help(key)
    if not h:
        return jsonify({'error': f'Hilfe-Key "{key}" nicht gefunden'}), 404
    return jsonify(h)


@gutachten_bp.get('/help-search')
@jwt_required()
def help_search():
    q = (request.args.get('q') or '').strip()
    return jsonify({'results': _help.search_help(q)})


# ============================================================
# Phase H — Audit-Bericht → Privatgutachten Konversion
# (Issues #680-#689)
# ============================================================
from gutachten import audit_to_pg as _a2pg


@gutachten_bp.get('/<projekt_name>/audit-summary')
@jwt_required()
def audit_summary(projekt_name: str):
    """H-A — Audit-Bericht Summary für Wizard Step 1."""
    s = _a2pg.get_audit_summary(DB_PATH, projekt_name)
    if not s:
        return jsonify({'error': f"Audit '{projekt_name}' nicht gefunden"}), 404
    return jsonify(s)


@gutachten_bp.get('/<projekt_name>/vorbefassung-warning')
@jwt_required()
def vorbefassung_warning(projekt_name: str):
    """H-A #682 — Vorbefassungs-Warnung. #705: ?einheitlicher_auftrag=1 → Variante 2."""
    einheitlich = request.args.get('einheitlicher_auftrag', '').lower() in ('1', 'true', 'yes')
    return jsonify(_a2pg.get_vorbefassungs_warning(
        DB_PATH, projekt_name, audit_teil_des_gutachtens=einheitlich))


@gutachten_bp.get('/<projekt_name>/audit-gaps')
@jwt_required()
def audit_gaps(projekt_name: str):
    """H-B #685 — Befund-Kandidaten (Score<70)."""
    max_score = int(request.args.get('max_score', '70'))
    return jsonify({'gaps': _a2pg.get_audit_gap_candidates(DB_PATH, projekt_name, max_score)})


@gutachten_bp.get('/<projekt_name>/abgeleitete-pgs')
@jwt_required()
def abgeleitete_pgs(projekt_name: str):
    """H-A #681 — Cross-Ref Audit → PGs (bidirektional, hier Audit→PGs)."""
    return jsonify({'pgs': _a2pg.list_konvertierungen(DB_PATH, audit_projekt=projekt_name)})


@gutachten_bp.get('/gerichts/<projekt_name>/audit-source')
@jwt_required()
def gerichts_audit_source(projekt_name: str):
    """H-A #681 — Audit-Quelle des PGs (bidirektional, hier PG→Audit)."""
    from gutachten import gerichts_db as _gdb
    p = _gdb.load_gerichts_projekt(DB_PATH, projekt_name)
    if not p:
        return jsonify({'error': f"PG '{projekt_name}' nicht gefunden"}), 404
    meta = p.get('meta', {}) if isinstance(p.get('meta'), dict) else {}
    src = meta.get('audit_source') or {}
    konv = _a2pg.list_konvertierungen(DB_PATH, pg_projekt=projekt_name)
    return jsonify({'audit_source': src, 'konvertierungen': konv})


@gutachten_bp.post('/<projekt_name>/konvertieren-zu-pg')
@jwt_required()
def konvertieren_zu_pg(projekt_name: str):
    """H-A #680 — Audit → PG Konversion (Wizard-Abschluss)."""
    payload = request.get_json(force=True) or {}
    try:
        result = _a2pg.convert_audit_to_pg(
            DB_PATH,
            audit_projekt_name=projekt_name,
            pg_name=payload.get('pg_name', ''),
            sv_name=payload.get('sv_name', ''),
            auftrags_art=payload.get('auftrags_art', 'Tauglichkeitsprüfung'),
            auftrags_datum=payload.get('auftrags_datum'),
            auftrags_nummer=payload.get('auftrags_nummer'),
            honorarvereinbarung=payload.get('honorarvereinbarung'),
            thema=payload.get('thema'),
            befangenheits_akzeptanz=bool(payload.get('befangenheits_akzeptanz', False)),
            audit_teil_des_gutachtens=bool(payload.get('audit_teil_des_gutachtens', False)),
        )
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Konversion fehlgeschlagen: {e}'}), 500


@gutachten_bp.post('/<projekt_name>/build-pg-questions-prompt')
@jwt_required()
def build_pg_questions_prompt(projekt_name: str):
    """H-B #684 — Beweisfragen-Prompt aus Audit-Summary."""
    payload = request.get_json(force=True) or {}
    summary = _a2pg.get_audit_summary(DB_PATH, projekt_name)
    prompt = _a2pg.build_pg_questions_prompt(
        summary,
        auftrags_art=payload.get('auftrags_art', 'Tauglichkeitsprüfung'),
        kategorien=payload.get('kategorien'),
    )
    return jsonify({'prompt': prompt})


@gutachten_bp.post('/gerichts/<pg_name>/import-pg-questions')
@jwt_required()
def import_pg_questions(pg_name: str):
    """H-B #684 — geparste Beweisfragen ins PG übernehmen."""
    payload = request.get_json(force=True) or {}
    raw = payload.get('raw_response', '')
    fragen = _a2pg.parse_pg_questions_response(raw)
    count = _a2pg.apply_questions_to_pg(DB_PATH, pg_name, fragen)
    return jsonify({'imported': count, 'fragen': fragen})


@gutachten_bp.post('/gerichts/<pg_name>/befund-from-gap')
@jwt_required()
def befund_from_gap(pg_name: str):
    """H-B #685 — Befund-Skeleton aus einem Audit-Gap erzeugen (§ 407a-Disclaimer)."""
    payload = request.get_json(force=True) or {}
    gap = payload.get('gap', {})
    nr = payload.get('nr', 'B-1')
    bid = _a2pg.create_befund_skeleton_from_gap(DB_PATH, pg_name, gap, nr)
    return jsonify({'befund_id': bid, 'disclaimer': _a2pg.PG_BEFUND_DISCLAIMER})


@gutachten_bp.post('/<projekt_name>/smart-suggestions-prompt')
@jwt_required()
def smart_suggestions_prompt(projekt_name: str):
    """H-C #688 — Top-3-Lows Smart-Suggestions Prompt."""
    summary = _a2pg.get_audit_summary(DB_PATH, projekt_name)
    return jsonify({'prompt': _a2pg.build_smart_suggestions_prompt(summary)})


@gutachten_bp.post('/parse-smart-suggestions')
@jwt_required()
def parse_smart_suggestions():
    """H-C #688 — parse ChatGPT-Antwort."""
    payload = request.get_json(force=True) or {}
    raw = payload.get('raw_response', '')
    return jsonify(_a2pg.parse_smart_suggestions_response(raw))


@gutachten_bp.get('/framework-norm-map')
@jwt_required()
def framework_norm_map():
    """H-C #687 — Framework→Norm Mapping-Tabelle."""
    return jsonify({'map': _a2pg.FRAMEWORK_TO_NORM_MAP})


@gutachten_bp.get('/<projekt_name>/auto-thema')
@jwt_required()
def auto_thema(projekt_name: str):
    """H-C #689 — Thema-Auto-Befüllung aus Audit."""
    auftrags_art = request.args.get('auftrags_art', 'Tauglichkeitsprüfung')
    summary = _a2pg.get_audit_summary(DB_PATH, projekt_name)
    if not summary:
        return jsonify({'thema': ''})
    return jsonify({'thema': _a2pg.generate_pg_thema_from_audit(summary, auftrags_art)})


# ============================================================
# #955 — Stammdaten: Gutachter-Profile + Hilfspersonen
# ============================================================

@gutachten_bp.get('/gutachter')
@jwt_required()
def gutachter_list():
    only_active = request.args.get('aktiv') == 'true'
    return jsonify({'gutachter': _gdb.list_gutachter(DB_PATH, only_active)})


@gutachten_bp.post('/gutachter')
@jwt_required()
def gutachter_save():
    body = request.get_json(silent=True) or {}
    try:
        gid = _gdb.save_gutachter(DB_PATH, **body)
        return jsonify({'id': gid, 'ok': True}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@gutachten_bp.put('/gutachter/<int:gid>')
@jwt_required()
def gutachter_update(gid: int):
    body = request.get_json(silent=True) or {}
    body['id'] = gid
    try:
        _gdb.save_gutachter(DB_PATH, **body)
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@gutachten_bp.delete('/gutachter/<int:gid>')
@jwt_required()
def gutachter_delete(gid: int):
    _gdb.delete_gutachter(DB_PATH, gid)
    return '', 204


@gutachten_bp.get('/hilfspersonen')
@jwt_required()
def hilfspersonen_list():
    only_active = request.args.get('aktiv') == 'true'
    return jsonify({'hilfspersonen': _gdb.list_hilfspersonen(DB_PATH, only_active)})


@gutachten_bp.post('/hilfspersonen')
@jwt_required()
def hilfsperson_save():
    body = request.get_json(silent=True) or {}
    try:
        hid = _gdb.save_hilfsperson(DB_PATH, **body)
        return jsonify({'id': hid, 'ok': True}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@gutachten_bp.put('/hilfspersonen/<int:hid>')
@jwt_required()
def hilfsperson_update(hid: int):
    body = request.get_json(silent=True) or {}
    body['id'] = hid
    try:
        _gdb.save_hilfsperson(DB_PATH, **body)
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@gutachten_bp.delete('/hilfspersonen/<int:hid>')
@jwt_required()
def hilfsperson_delete(hid: int):
    _gdb.delete_hilfsperson(DB_PATH, hid)
    return '', 204


# ============================================================
# #957 — Custom-Word-Vorlagen (Upload + CRUD + Render)
# ============================================================

_TEMPLATE_DIR = Path('data/gutachten/templates')


def _safe_template_name(filename: str) -> str:
    import re
    base = Path(filename or 'vorlage.docx').name  # kein Pfad
    base = re.sub(r'[^A-Za-z0-9._-]', '_', base)
    return base[:120] or 'vorlage.docx'


@gutachten_bp.get('/templates')
@jwt_required()
def templates_list():
    import json as _json
    out = []
    for t in _gdb.list_templates(DB_PATH):
        t['variablen'] = _json.loads(t.get('variablen_json') or '[]')
        out.append(t)
    return jsonify({'templates': out})


@gutachten_bp.get('/templates/schema')
@jwt_required()
def templates_schema():
    """Kanonische Ziel-Variablen für Mapping-Wizard + Variablen-Hilfe (#959/#962).

    Jede Variable bekommt zusätzlich ihren direkt einsetzbaren Platzhalter-Token
    ``[key]`` — kopierbar in die Word-Vorlage, wird beim Export automatisch
    befüllt (kein manuelles Mapping nötig).
    """
    from gutachten.template_schema import TEMPLATE_VARIABLES
    out = [{**v, 'token': f"[{v['key']}]"} for v in TEMPLATE_VARIABLES]
    return jsonify({'variables': out})


@gutachten_bp.get('/templates/<int:tid>')
@jwt_required()
def template_detail(tid: int):
    """Vorlagen-Detail inkl. erkannter Platzhalter + aktuellem Mapping (Wizard, #959)."""
    import json as _json
    t = _gdb.get_template(DB_PATH, tid)
    if not t:
        return jsonify({'error': 'Vorlage nicht gefunden'}), 404
    t['variablen'] = _json.loads(t.get('variablen_json') or '[]')
    t['mapping'] = _json.loads(t.get('mapping_json') or '{}')
    return jsonify(t)


@gutachten_bp.post('/templates')
@jwt_required()
def template_upload():
    import json as _json
    from gutachten.template_render import validate_template_bytes
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'Keine Datei hochgeladen (Feld "file")'}), 400
    data = f.read()
    errors = validate_template_bytes(data, f.filename or '')
    if errors:
        return jsonify({'error': 'Vorlage abgelehnt', 'details': errors}), 400

    name = (request.form.get('name') or Path(f.filename or 'Vorlage').stem).strip()
    art = request.form.get('gutachten_art', 'beide')
    try:
        from shared.fs_perms import ensure_private_dir
        ensure_private_dir(_TEMPLATE_DIR)
    except Exception:
        _TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    safe = _safe_template_name(f.filename or f'{name}.docx')
    sha = _gdb.compute_sha256(data)
    dest = _TEMPLATE_DIR / f"{sha[:12]}__{safe}"
    dest.write_bytes(data)

    # Platzhalter erkennen. Bevorzugt [Klammer]-Stil (reale Vorlagen, #959),
    # sonst docxtpl-{{ }} (Power-User). Auto-Mapping vorschlagen.
    from gutachten.template_render import (
        detect_bracket_placeholders, suggest_mapping, template_has_jinja,
    )
    engine = 'jinja' if template_has_jinja(dest) else 'bracket'
    placeholders: list[str] = []
    suggested: dict = {}
    if engine == 'bracket':
        placeholders = detect_bracket_placeholders(dest)
        suggested = suggest_mapping(placeholders)
    else:
        try:
            from gutachten.template_render import extract_variables
            placeholders = sorted(extract_variables(dest))
        except Exception as e:
            current_app.logger.info('docxtpl-Extraktion übersprungen: %s', e)

    variablen = [{'token': t, 'engine': engine} for t in placeholders]
    try:
        tid = _gdb.save_template(
            DB_PATH, name=name, gutachten_art=art, datei_pfad=str(dest),
            datei_sha256=sha, variablen_json=_json.dumps(variablen, ensure_ascii=False),
            mapping_json=_json.dumps(suggested, ensure_ascii=False),
            hochgeladen_von=request.form.get('user', ''))
    except ValueError as e:
        dest.unlink(missing_ok=True)
        return jsonify({'error': str(e)}), 400
    return jsonify({'id': tid, 'ok': True, 'engine': engine,
                    'placeholders': placeholders, 'suggested_mapping': suggested,
                    'placeholder_count': len(placeholders)}), 201


@gutachten_bp.put('/templates/<int:tid>/mapping')
@jwt_required()
def template_mapping(tid: int):
    import json as _json
    body = request.get_json(silent=True) or {}
    t = _gdb.get_template(DB_PATH, tid)
    if not t:
        return jsonify({'error': 'Vorlage nicht gefunden'}), 404
    _gdb.save_template(DB_PATH, id=tid, name=t['name'], gutachten_art=t['gutachten_art'],
                       datei_pfad=t['datei_pfad'], datei_sha256=t['datei_sha256'],
                       variablen_json=t['variablen_json'],
                       mapping_json=_json.dumps(body.get('mapping') or {}, ensure_ascii=False),
                       ist_default=t['ist_default'], aktiv=t['aktiv'])
    return jsonify({'ok': True})


@gutachten_bp.post('/templates/<int:tid>/default')
@jwt_required()
def template_set_default(tid: int):
    art = (request.get_json(silent=True) or {}).get('gutachten_art', 'beide')
    if not _gdb.get_template(DB_PATH, tid):
        return jsonify({'error': 'Vorlage nicht gefunden'}), 404
    _gdb.set_default_template(DB_PATH, tid, art)
    return jsonify({'ok': True})


@gutachten_bp.delete('/templates/<int:tid>')
@jwt_required()
def template_delete(tid: int):
    pfad = _gdb.delete_template(DB_PATH, tid)
    if pfad:
        try:
            Path(pfad).unlink(missing_ok=True)
        except Exception:
            pass
    return '', 204


@gutachten_bp.get('/gerichts/<path:projekt_name>/hilfspersonen')
@jwt_required()
def gerichts_hilfspersonen_get(projekt_name: str):
    return jsonify({'hilfspersonen': _gdb.list_hilfspersonen_for_projekt(DB_PATH, projekt_name)})


@gutachten_bp.put('/gerichts/<path:projekt_name>/hilfspersonen')
@jwt_required()
def gerichts_hilfspersonen_set(projekt_name: str):
    body = request.get_json(silent=True) or {}
    entries = body.get('hilfspersonen') or body.get('entries') or []
    _gdb.link_hilfspersonen(DB_PATH, projekt_name, entries)
    return jsonify({'ok': True})


# ============================================================
# #969 — Final-Archiv (SHA-256, Admin-only-Delete, Soft-Delete)
# ============================================================

_FINAL_DIR = Path('data/gutachten/final_exports')
_FINAL_ALLOWED = {'docx': '.docx', 'pdf': '.pdf'}


def _safe_seg(name: str) -> str:
    import re
    return re.sub(r'[^A-Za-z0-9._-]', '_', name or 'x')[:80] or 'x'


@gutachten_bp.post('/gerichts/<path:projekt_name>/final-export')
@require_permission(Permission.GUTACHTEN_WRITE)
def final_export_upload(projekt_name: str):
    from shared.upload_validation import validate_upload_file
    from shared.audit import audit_event
    from flask_jwt_extended import get_jwt_identity
    if not _gdb.load_gerichts_projekt(DB_PATH, projekt_name):
        return jsonify({'error': 'Projekt nicht gefunden'}), 404
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'Keine Datei (Feld "file")'}), 400
    ext = Path(f.filename or '').suffix.lower().lstrip('.')
    if ext not in _FINAL_ALLOWED:
        return jsonify({'error': 'Nur DOCX oder PDF erlaubt'}), 400
    data = f.read()
    sha = _gdb.compute_sha256(data)
    # Magic-Bytes/Zip-Bomb-Validierung auf Temp-Datei mit korrekter Endung.
    tmp = workspace_tmpdir() / f'final_{sha[:8]}{_FINAL_ALLOWED[ext]}'
    tmp.write_bytes(data)
    try:
        validate_upload_file(tmp, suffix=_FINAL_ALLOWED[ext])
    except Exception as e:
        tmp.unlink(missing_ok=True)
        return jsonify({'error': f'Datei abgelehnt: {e}'}), 400
    from datetime import datetime, timezone
    dest_dir = _FINAL_DIR / _safe_seg(projekt_name)
    try:
        from shared.fs_perms import ensure_private_dir
        ensure_private_dir(dest_dir)
    except Exception:
        dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%S')
    dest = dest_dir / f'{stamp}__{sha[:8]}{_FINAL_ALLOWED[ext]}'
    dest.write_bytes(data)
    tmp.unlink(missing_ok=True)
    user = get_jwt_identity()
    fid = _gdb.save_final_export(DB_PATH, projekt_name=projekt_name,
                                 dateiname=Path(f.filename or '').name, format=ext,
                                 datei_pfad=str(dest.resolve()), datei_groesse=len(data),
                                 sha256=sha, hochgeladen_von=str(user),
                                 bemerkung=request.form.get('bemerkung', ''))
    audit_event('gutachten.final_export.uploaded', module='gutachten', outcome='success',
                details={'projekt': projekt_name, 'final_id': fid, 'sha256': sha,
                         'format': ext, 'datei_groesse': len(data), 'user': user})
    return jsonify({'id': fid, 'sha256': sha, 'format': ext, 'datei_groesse': len(data)}), 201


@gutachten_bp.get('/gerichts/<path:projekt_name>/final-exports')
@require_permission(Permission.GUTACHTEN_READ)
def final_export_list(projekt_name: str):
    rows = _gdb.list_final_exports(DB_PATH, projekt_name)
    for r in rows:
        r['deleted'] = bool(r.get('deleted_at'))
        r.pop('datei_pfad', None)  # internen Pfad nicht ausliefern
    return jsonify({'final_exports': rows})


@gutachten_bp.get('/gerichts/<path:projekt_name>/final-export/<int:fid>/download')
@require_permission(Permission.GUTACHTEN_READ)
def final_export_download(projekt_name: str, fid: int):
    from shared.audit import audit_event
    from flask_jwt_extended import get_jwt_identity
    rec = _gdb.get_final_export(DB_PATH, fid)
    if not rec or rec.get('projekt_name') != projekt_name:
        return jsonify({'error': 'Nicht gefunden'}), 404
    if rec.get('deleted_at'):
        return jsonify({'error': 'Eintrag wurde gelöscht', 'deleted_at': rec['deleted_at']}), 410
    # #1180: Pfad-Containment unter dem Final-Export-Store erzwingen.
    try:
        from security_utils import ensure_within_root
        p = ensure_within_root(Path(rec['datei_pfad']), _FINAL_DIR)
    except ValueError:
        current_app.logger.error("final_export_download: Pfad außerhalb des Stores: %r",
                                  rec.get('datei_pfad'))
        return jsonify({'error': 'Nicht gefunden'}), 404
    if not p.exists():
        return jsonify({'error': 'Datei nicht mehr vorhanden'}), 410
    audit_event('gutachten.final_export.downloaded', module='gutachten', outcome='success',
                details={'projekt': projekt_name, 'final_id': fid, 'sha256': rec.get('sha256'),
                         'user': get_jwt_identity()})
    mime = ('application/pdf' if rec['format'] == 'pdf'
            else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    return send_file(str(p), mimetype=mime, as_attachment=True, download_name=rec['dateiname'])


@gutachten_bp.delete('/gerichts/<path:projekt_name>/final-export/<int:fid>')
@require_permission(Permission.GUTACHTEN_FINAL_DELETE)
def final_export_delete(projekt_name: str, fid: int):
    from shared.audit import audit_event
    from flask_jwt_extended import get_jwt_identity
    body = request.get_json(silent=True) or {}
    reason = (body.get('reason') or '').strip()
    if len(reason) < 10:
        return jsonify({'error': 'Begründung (mind. 10 Zeichen) ist Pflicht'}), 400
    rec = _gdb.get_final_export(DB_PATH, fid)
    if not rec or rec.get('projekt_name') != projekt_name:
        return jsonify({'error': 'Nicht gefunden'}), 404
    if rec.get('deleted_at'):
        return jsonify({'error': 'Bereits gelöscht'}), 409
    user = get_jwt_identity()
    _gdb.soft_delete_final_export(DB_PATH, fid, str(user), reason)
    try:
        # #1180: nur löschen, wenn der Pfad innerhalb des Final-Export-Stores liegt.
        from security_utils import ensure_within_root
        ensure_within_root(Path(rec['datei_pfad']), _FINAL_DIR).unlink(missing_ok=True)
    except Exception:
        current_app.logger.exception('Final-Export-Datei-Löschung fehlgeschlagen')
    audit_event('gutachten.final_export.deleted', module='gutachten', outcome='success',
                details={'projekt': projekt_name, 'final_id': fid, 'sha256': rec.get('sha256'),
                         'reason': reason, 'deleted_by': user})
    return jsonify({'ok': True}), 200


# ============================================================
# #983/#984 — Glossar (CRUD + Auto-Generierung)
# ============================================================

@gutachten_bp.get('/gerichts/<path:projekt_name>/glossar')
@jwt_required()
def glossar_list(projekt_name: str):
    return jsonify({'glossar': _gdb.list_glossar(DB_PATH, projekt_name)})


@gutachten_bp.post('/gerichts/<path:projekt_name>/glossar')
@jwt_required()
def glossar_save(projekt_name: str):
    body = request.get_json(silent=True) or {}
    body['projekt_name'] = projekt_name
    body.pop('id', None)
    try:
        gid = _gdb.save_glossar_eintrag(DB_PATH, **body)
        return jsonify({'id': gid, 'ok': True}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@gutachten_bp.put('/gerichts/<path:projekt_name>/glossar/<int:gid>')
@jwt_required()
def glossar_update(projekt_name: str, gid: int):
    body = request.get_json(silent=True) or {}
    body['projekt_name'] = projekt_name
    body['id'] = gid
    body.setdefault('quelle', 'manuell')  # Bearbeitung = manuell (vor Auto-Gen geschützt)
    try:
        _gdb.save_glossar_eintrag(DB_PATH, **body)
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@gutachten_bp.delete('/gerichts/<path:projekt_name>/glossar/<int:gid>')
@jwt_required()
def glossar_delete(projekt_name: str, gid: int):
    _gdb.delete_glossar_eintrag(DB_PATH, gid)
    return '', 204


@gutachten_bp.post('/gerichts/<path:projekt_name>/glossar/generate')
@jwt_required()
def glossar_generate(projekt_name: str):
    """#984: Glossar automatisch aus DB-Daten + Seed erzeugen (idempotent)."""
    if not _gdb.load_gerichts_projekt(DB_PATH, projekt_name):
        return jsonify({'error': 'Projekt nicht gefunden'}), 404
    stats = _gdb.generate_glossar(DB_PATH, projekt_name)
    return jsonify({'ok': True, 'stats': stats, 'glossar': _gdb.list_glossar(DB_PATH, projekt_name)})
