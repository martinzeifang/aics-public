"""DSGVO DS3+DS4 (#1103/#1104) — TOM-Katalog REST-Blueprint.

Self-contained Area. Der Integrator registriert das Blueprint in ``server/app.py``
mit ``url_prefix='/api/dsgvo-tom'``.

Permission-Pattern wie ``server/api/dsgvo.py``: JWT pflicht; zusätzlich
modul-spezifische DSGVO-Permissions (read/write/export) via ``require_permission``.
"""
from flask import current_app, Blueprint, request

from flask_jwt_extended import jwt_required

from pathlib import Path

from server.models.permission import Permission, require_permission

from dsgvo import tom_katalog as tk

dsgvo_tom_bp = Blueprint('dsgvo_tom', __name__)

DB_PATH = Path('data/db/dsgvo.sqlite')


def _log_500(e: Exception):
    current_app.logger.exception(
        '%s %s — %s: %s', request.method, request.path, type(e).__name__, e
    )
    return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Konstanten / Ziel-Katalog
# ============================================================

@dsgvo_tom_bp.get('/ziele')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_ziele():
    """Die 7 SDM-Gewährleistungsziele + Seed-Übersicht."""
    try:
        seed_by_ziel: dict[str, list] = {z: [] for z in tk.ZIELE}
        for entry in tk.SEED_KATALOG:
            seed_by_ziel.setdefault(entry['ziel'], []).append({
                'massnahme_key': entry['massnahme_key'],
                'titel': entry['titel'],
                'beschreibung': entry['beschreibung'],
            })
        return {'ziele': tk.ZIELE, 'seed': seed_by_ziel}, 200
    except Exception as e:
        return _log_500(e)


# ============================================================
# Katalog je Projekt
# ============================================================

@dsgvo_tom_bp.get('/projekte/<projekt_name>/massnahmen')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_massnahmen(projekt_name: str):
    """Alle Katalog-Maßnahmen eines Projekts, gruppiert nach Ziel."""
    try:
        items = tk.list_massnahmen(DB_PATH, projekt_name)
        from dsgvo.tom_wiba import effektive_quelle, TOM_WIBA_MAPPING
        for m in items:  # #1575: Statusquelle + ob WiBA-Prüffragen verknüpft sind
            m['status_quelle_effektiv'] = effektive_quelle(m)
            m['wiba_verknuepft'] = len(TOM_WIBA_MAPPING.get(m['massnahme_key'], []))
        gruppen = []
        for ziel in tk.ZIELE:
            zg = [m for m in items if m['ziel'] == ziel]
            gruppen.append({'ziel': ziel, 'massnahmen': zg})
        bewertet = sum(1 for m in items if int(m['status']) > 0)
        return {
            'projekt': projekt_name,
            'items': items,
            'gruppen': gruppen,
            'gesamt': len(items),
            'bewertet': bewertet,
        }, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.post('/projekte/<projekt_name>/seed')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def post_seed(projekt_name: str):
    """Standard-Maßnahmenkatalog einspielen (idempotent; ?force=1 aktualisiert Texte)."""
    try:
        data = request.json or {}
        force = bool(data.get('force')) or request.args.get('force') in ('1', 'true')
        inserted = tk.seed_projekt(DB_PATH, projekt_name, force=force)
        items = tk.list_massnahmen(DB_PATH, projekt_name)
        return {'inserted': inserted, 'gesamt': len(items), 'items': items}, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.post('/projekte/<projekt_name>/massnahmen')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def upsert_massnahme(projekt_name: str):
    """Maßnahme anlegen oder aktualisieren (Upsert über massnahme_key)."""
    try:
        data = request.json or {}
        if not str(data.get('massnahme_key', '')).strip():
            return {'error': 'Feld "massnahme_key" ist Pflicht'}, 400
        try:
            saved = tk.upsert_massnahme(DB_PATH, projekt_name, data)
        except ValueError as ve:
            return {'error': str(ve)}, 400
        return saved, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.get('/projekte/<projekt_name>/massnahmen/<massnahme_key>')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_one(projekt_name: str, massnahme_key: str):
    try:
        m = tk.get_massnahme(DB_PATH, projekt_name, massnahme_key)
        if not m:
            return {'error': 'Maßnahme nicht gefunden'}, 404
        return m, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.delete('/projekte/<projekt_name>/massnahmen/<massnahme_key>')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def delete_one(projekt_name: str, massnahme_key: str):
    try:
        ok = tk.delete_massnahme(DB_PATH, projekt_name, massnahme_key)
        if not ok:
            return {'error': 'Maßnahme nicht gefunden'}, 404
        return {'deleted': massnahme_key}, 200
    except Exception as e:
        return _log_500(e)


# ============================================================
# Wirksamkeitsprüfung
# ============================================================

@dsgvo_tom_bp.post('/projekte/<projekt_name>/massnahmen/<massnahme_key>/wirksamkeit')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def post_wirksamkeit(projekt_name: str, massnahme_key: str):
    """Wirksamkeitsprüfung dokumentieren (Datum + Ergebnis, optional Status)."""
    try:
        if not tk.get_massnahme(DB_PATH, projekt_name, massnahme_key):
            return {'error': 'Maßnahme nicht gefunden'}, 404
        data = request.json or {}
        status = data.get('status')
        m = tk.set_wirksamkeit(
            DB_PATH,
            projekt_name,
            massnahme_key,
            datum=str(data.get('datum', '') or data.get('wirksamkeit_datum', '')),
            ergebnis=str(data.get('ergebnis', '') or data.get('wirksamkeit_ergebnis', '')),
            status=None if status is None else int(status),
        )
        return m or {'error': 'Maßnahme nicht gefunden'}, (200 if m else 404)
    except Exception as e:
        return _log_500(e)


# ============================================================
# KI-Vorschlag (Stub)
# ============================================================

@dsgvo_tom_bp.get('/projekte/<projekt_name>/ki-vorschlag')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_ki_vorschlag(projekt_name: str):
    """KI-Vorschlag-Stub: heuristische Empfehlungen je Ziel (#1104)."""
    try:
        return tk.ki_vorschlag(DB_PATH, projekt_name), 200
    except Exception as e:
        return _log_500(e)


# ============================================================
# #1575 — WiBA-Verknüpfung: Ableitung, Abgleich, Formulierung
# ============================================================

def _projekt_or_404(projekt_name: str):
    from dsgvo.db import load_projekt
    p = load_projekt(DB_PATH, projekt_name)
    if not p:
        return None, ({'error': 'Projekt nicht gefunden'}, 404)
    return p, None


def _audit(action: str, details: dict) -> None:
    try:
        from shared.audit import audit_event
        audit_event(action, module='dsgvo', details=details)
    except Exception:  # noqa: BLE001 — Audit best effort
        current_app.logger.warning('Audit %s fehlgeschlagen', action, exc_info=True)


@dsgvo_tom_bp.get('/projekte/<projekt_name>/wiba')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_wiba_ableitung(projekt_name: str):
    """Verknüpfte WiBA-Instanz + je TOM die Prüffragen, Antworten und den abgeleiteten Status."""
    try:
        from dsgvo import tom_wiba as tw
        p, err = _projekt_or_404(projekt_name)
        if err:
            return err
        abl = tw.ableitung(p)
        meta = p.get('meta') if isinstance(p.get('meta'), dict) else {}
        return {**abl, 'explizit': bool(meta.get('linked_wiba_projekt')),
                'kandidaten': tw.wiba_kandidaten()}, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.put('/projekte/<projekt_name>/wiba-link')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def put_wiba_link(projekt_name: str):
    """WiBA-Instanz explizit verknüpfen (leer = automatisch über die Firma)."""
    try:
        from dsgvo.db import update_projekt_meta
        p, err = _projekt_or_404(projekt_name)
        if err:
            return err
        name = str((request.get_json(silent=True) or {}).get('wiba_projekt') or '').strip()
        meta = dict(p.get('meta') or {})
        if name:
            meta['linked_wiba_projekt'] = name
        else:
            meta.pop('linked_wiba_projekt', None)
        update_projekt_meta(DB_PATH, projekt_name, meta)
        _audit('dsgvo.tom.wiba_linked', {'projekt': projekt_name, 'wiba_projekt': name or '(automatisch)'})
        return {'ok': True, 'wiba_projekt': name or None}, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.post('/projekte/<projekt_name>/wiba/sync')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def post_wiba_sync(projekt_name: str):
    """Status aller TOM mit Quelle WiBA aus den WiBA-Antworten übernehmen.
    Ergänzt fehlende Standard-TOM (z. B. die WiBA-Zusatz-TOM), wenn der Katalog geseedet ist."""
    try:
        from dsgvo import tom_wiba as tw
        p, err = _projekt_or_404(projekt_name)
        if err:
            return err
        if tk.list_massnahmen(DB_PATH, projekt_name):
            tk.seed_projekt(DB_PATH, projekt_name)
        res = tw.sync_projekt(DB_PATH, projekt_name)
        if not res['wiba_projekt']:
            return {'error': 'Keine WiBA-Instanz für diese Firma gefunden — in WiBA ein Projekt '
                             'für die Firma anlegen oder hier explizit verknüpfen.'}, 409
        _audit('dsgvo.tom.wiba_sync', {'projekt': projekt_name, 'wiba_projekt': res['wiba_projekt'],
                                       'aktualisiert': len(res['updated'])})
        return res, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.put('/projekte/<projekt_name>/massnahmen/<massnahme_key>/status-quelle')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def put_status_quelle(projekt_name: str, massnahme_key: str):
    """Statusquelle umschalten (wiba = aus WiBA ableiten | manuell). Bei wiba sofort abgleichen."""
    try:
        from dsgvo import tom_wiba as tw
        quelle = str((request.get_json(silent=True) or {}).get('quelle') or '')
        if not tk.get_massnahme(DB_PATH, projekt_name, massnahme_key):
            return {'error': 'Maßnahme nicht gefunden'}, 404
        try:
            m = tk.set_status_quelle(DB_PATH, projekt_name, massnahme_key, quelle)
        except ValueError as ve:
            return {'error': str(ve)}, 400
        if quelle == 'wiba':
            tw.sync_projekt(DB_PATH, projekt_name)
            m = tk.get_massnahme(DB_PATH, projekt_name, massnahme_key)
        _audit('dsgvo.tom.status_quelle', {'projekt': projekt_name, 'massnahme': massnahme_key,
                                           'quelle': quelle})
        return m or {}, 200
    except Exception as e:
        return _log_500(e)


def _tom_kontext(projekt_name: str, massnahme_key: str):
    from dsgvo import tom_wiba as tw
    p, err = _projekt_or_404(projekt_name)
    if err:
        return None, err
    m = tk.get_massnahme(DB_PATH, projekt_name, massnahme_key)
    if not m:
        return None, ({'error': 'Maßnahme nicht gefunden'}, 404)
    abl = tw.ableitung(p)
    fragen = (abl['items'].get(massnahme_key) or {}).get('fragen', [])
    return {'projekt': p, 'massnahme': m, 'fragen': fragen, 'wiba_projekt': abl['wiba_projekt']}, None


@dsgvo_tom_bp.get('/projekte/<projekt_name>/massnahmen/<massnahme_key>/formulierung')
@jwt_required()
@require_permission(Permission.DSGVO_READ)
def get_formulierung(projekt_name: str, massnahme_key: str):
    """Entwurf (deterministisch aus WiBA) + KI-Prompt für die Umsetzungsbeschreibung."""
    try:
        from dsgvo import tom_wiba as tw
        ctx, err = _tom_kontext(projekt_name, massnahme_key)
        if err:
            return err
        return {
            'entwurf': tw.entwurf_umsetzung(ctx['massnahme'], ctx['fragen'], ctx['wiba_projekt'] or ''),
            'prompt': tw.build_formulierung_prompt(ctx['massnahme'], ctx['fragen'],
                                                   ctx['projekt'].get('unternehmen', '')),
            'fragen': len(ctx['fragen']),
            'wiba_projekt': ctx['wiba_projekt'],
        }, 200
    except Exception as e:
        return _log_500(e)


@dsgvo_tom_bp.post('/projekte/<projekt_name>/massnahmen/<massnahme_key>/umsetzung')
@jwt_required()
@require_permission(Permission.DSGVO_WRITE)
def post_umsetzung(projekt_name: str, massnahme_key: str):
    """Umsetzungsbeschreibung speichern — Text direkt oder KI-Antwort ({"umsetzung": …})."""
    try:
        data = request.get_json(silent=True) or {}
        if not tk.get_massnahme(DB_PATH, projekt_name, massnahme_key):
            return {'error': 'Maßnahme nicht gefunden'}, 404
        quelle = str(data.get('quelle') or 'manuell')
        text = str(data.get('umsetzung') or '').strip()
        luecken: list = []
        raw = str(data.get('raw') or '').strip()
        if raw:  # KI-Antwort (JSON, ggf. in Fences)
            from shared.json_io import safe_json_loads
            import re as _re
            m = _re.search(r'\{.*\}', raw, _re.DOTALL)
            try:
                parsed = safe_json_loads(m.group() if m else raw, context='dsgvo.tom.umsetzung')
            except ValueError as ve:
                return {'error': f'KI-Antwort nicht verwertbar: {ve}'}, 400
            text = str((parsed or {}).get('umsetzung') or '').strip()
            luecken = [str(x) for x in ((parsed or {}).get('luecken') or []) if str(x).strip()]
            if luecken:
                text += '\n\nOffene Punkte:\n' + '\n'.join(f'• {x}' for x in luecken)
            quelle = 'ki'
            try:
                from ai_compliance_suite.ai.dispatch import current_provider_name
                from server.services.auto_bewertung import ki_kennzeichnung
                text = ki_kennzeichnung(text, current_provider_name())
            except Exception:  # noqa: BLE001
                pass
        if not text:
            return {'error': 'Keine Umsetzungsbeschreibung übergeben'}, 400
        m = tk.set_umsetzung(DB_PATH, projekt_name, massnahme_key, text, quelle)
        _audit('dsgvo.tom.umsetzung', {'projekt': projekt_name, 'massnahme': massnahme_key,
                                       'quelle': quelle, 'laenge': len(text)})
        return {**(m or {}), 'luecken': luecken}, 200
    except Exception as e:
        return _log_500(e)
