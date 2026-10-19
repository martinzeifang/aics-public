"""WiBA-Modul — REST-Blueprint (``/api/wiba``).

BSI „Weg in die Basis-Absicherung": Prüffragen als Kontrollen. Muster wie CRA.
Permission: JWT pflicht + modul-spezifische ``WIBA_*``-Permissions.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from server.models.permission import Permission, require_permission

from wiba import db as wdb
from wiba.constants import STATUS_META, STATUS_WERTE

wiba_bp = Blueprint('wiba', __name__)

DB_PATH = Path('data/db/wiba.sqlite')

# Einheitliches Berichts-Center (Sprint #35) — Standard-Routen über das geteilte
# Framework; WiBA liefert nur Katalog + Render (reuse wiba.report_export).
try:
    from shared.reports.api import register_report_routes as _register_report_routes
    from wiba import berichte_provider as _wiba_berichte
    _register_report_routes(
        wiba_bp, modul='wiba', db_path=DB_PATH,
        catalog=_wiba_berichte.catalog(), render=_wiba_berichte.render,
        project_scoped=True, zeitraum=False,
    )
except Exception as _e:  # pragma: no cover — Berichts-Center optional, App startet trotzdem
    import logging as _logging
    _logging.getLogger(__name__).warning("WiBA-Berichts-Center nicht registriert: %s", _e)


def _log_500(e: Exception):
    current_app.logger.exception(
        '%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
    return jsonify({'error': 'Interner Serverfehler'}), 500


def _require_projekt(projekt_name: str):
    p = wdb.load_projekt(DB_PATH, projekt_name)
    if not p:
        return None, (jsonify({'error': 'Projekt nicht gefunden'}), 404)
    return p, None


# ── Konstanten ────────────────────────────────────────────────────────────────

@wiba_bp.get('/constants')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def get_constants():
    return jsonify({
        'status_werte': list(STATUS_WERTE),
        'status_meta': STATUS_META,
    })


# ── Katalog (Themen + Prüffragen) ─────────────────────────────────────────────

@wiba_bp.get('/catalog')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def get_catalog():
    try:
        return jsonify({
            'meta': wdb.catalog_meta(DB_PATH),
            'themen': wdb.list_themen(DB_PATH),
            'prueffragen': wdb.list_prueffragen(DB_PATH),
        })
    except Exception as e:
        return _log_500(e)


@wiba_bp.get('/catalog/status')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def get_catalog_status():
    try:
        return jsonify(wdb.catalog_meta(DB_PATH))
    except Exception as e:
        return _log_500(e)


_SOURCE_DIR = Path('data/wiba/source')


@wiba_bp.post('/catalog/download')
@jwt_required()
@require_permission(Permission.WIBA_CATALOG)
def catalog_download():
    """Lädt die BSI-WiBA-Quelldateien (Tool + Checklisten) herunter (Admin)."""
    try:
        from wiba.io_source import download_sources
        report = download_sources(_SOURCE_DIR)
        code = 200 if report.get('ok') else 502
        return jsonify(report), code
    except Exception as e:
        return _log_500(e)


@wiba_bp.post('/catalog/ingest')
@jwt_required()
@require_permission(Permission.WIBA_CATALOG)
def catalog_ingest():
    """Parst die heruntergeladenen Quelldateien → DB-Katalog (idempotent/update)."""
    try:
        from wiba.io_source import build_catalog, CATALOG_VERSION
        themen, fragen = build_catalog(_SOURCE_DIR)
        res = wdb.replace_catalog(DB_PATH, themen, fragen,
                                  version=CATALOG_VERSION, quelle='BSI WiBA')
        return jsonify({'ok': True, **res, 'meta': wdb.catalog_meta(DB_PATH)})
    except FileNotFoundError as e:
        return jsonify({'error': f'Quelldatei fehlt — erst herunterladen. ({e})'}), 400
    except Exception as e:
        return _log_500(e)


@wiba_bp.post('/catalog/refresh')
@jwt_required()
@require_permission(Permission.WIBA_CATALOG)
def catalog_refresh():
    """Download + Ingest in einem Schritt (Admin)."""
    try:
        from wiba.io_source import download_sources, build_catalog, CATALOG_VERSION
        dl = download_sources(_SOURCE_DIR)
        if not dl.get('ok'):
            return jsonify({'error': 'Download fehlgeschlagen', 'log': dl.get('log')}), 502
        themen, fragen = build_catalog(_SOURCE_DIR)
        res = wdb.replace_catalog(DB_PATH, themen, fragen,
                                  version=CATALOG_VERSION, quelle='BSI WiBA')
        return jsonify({'ok': True, **res, 'log': dl.get('log'), 'meta': wdb.catalog_meta(DB_PATH)})
    except Exception as e:
        return _log_500(e)


# ── Projekte ──────────────────────────────────────────────────────────────────

@wiba_bp.get('/projekte')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def list_projekte():
    try:
        return jsonify(wdb.list_projekte(DB_PATH))
    except Exception as e:
        return _log_500(e)


@wiba_bp.get('/projekte/<projekt_name>')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def get_projekt(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    return jsonify(p)


@wiba_bp.post('/projekte')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def create_projekt():
    body = request.get_json(silent=True) or {}
    try:
        rid = wdb.save_projekt(
            DB_PATH, name=body.get('name', ''),
            unternehmen=body.get('unternehmen', ''),
            beschreibung=body.get('beschreibung', ''),
            berater=body.get('berater', ''),
            meta=body.get('meta') or {})
        return jsonify({'id': rid, 'ok': True}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return _log_500(e)


@wiba_bp.put('/projekte/<projekt_name>')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def update_projekt(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        wdb.save_projekt(
            DB_PATH, name=projekt_name,
            unternehmen=body.get('unternehmen', p.get('unternehmen', '')),
            beschreibung=body.get('beschreibung', p.get('beschreibung', '')),
            berater=body.get('berater', p.get('berater', '')),
            meta=body.get('meta', p.get('meta') or {}))
        return jsonify({'ok': True})
    except Exception as e:
        return _log_500(e)


@wiba_bp.delete('/projekte/<projekt_name>')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def delete_projekt(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        wdb.delete_projekt(DB_PATH, projekt_name)
        return jsonify({'ok': True})
    except Exception as e:
        return _log_500(e)


# ── Controls (Katalog + Antworten + Reifegrad) ────────────────────────────────

@wiba_bp.get('/projekte/<projekt_name>/controls')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def get_controls(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        themen = wdb.list_themen(DB_PATH)
        fragen = wdb.list_prueffragen(DB_PATH)
        antworten = wdb.load_antworten(DB_PATH, projekt_name)
        by_theme: dict[str, dict] = {}
        for t in themen:
            by_theme[t['theme_key']] = {**t, 'prueffragen': []}
        for f in fragen:
            a = antworten.get(f['control_id'], {})
            entry = {
                **f,
                'status': a.get('status', 'offen'),
                'notiz': a.get('notiz', ''),
                'verantwortlich': a.get('verantwortlich', ''),
                'zieldatum': a.get('zieldatum', ''),
                'evidence_doc_ids': a.get('evidence_doc_ids', []),
            }
            by_theme.setdefault(
                f['theme_key'],
                {'theme_key': f['theme_key'], 'titel': f['theme_key'], 'prueffragen': []}
            )['prueffragen'].append(entry)
        return jsonify({
            'themen': list(by_theme.values()),
            'reifegrad': wdb.compute_reifegrad(DB_PATH, projekt_name),
        })
    except Exception as e:
        return _log_500(e)


@wiba_bp.post('/projekte/<projekt_name>/antworten')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def save_antwort(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    cid = body.get('control_id')
    if not cid:
        return jsonify({'error': "'control_id' ist Pflicht"}), 400
    try:
        wdb.save_antwort(
            DB_PATH, projekt_name, cid,
            status=body.get('status'),
            notiz=body.get('notiz', ''),
            verantwortlich=body.get('verantwortlich', ''),
            zieldatum=body.get('zieldatum', ''),
            evidence_doc_ids=body.get('evidence_doc_ids') or [])
        # #1526: keine automatische Antwort-Änderung beim Speichern (manuelle Antwort gilt).
        tom = _sync_dsgvo_tom(projekt_name)  # #1575: WiBA-Erfüllung → DSGVO-TOM-Status
        return jsonify({'ok': True, 'reifegrad': wdb.compute_reifegrad(DB_PATH, projekt_name),
                        'tom_sync': tom})
    except Exception as e:
        return _log_500(e)


# ════════════════════════════════════════════════════════════════════
# W3 Issue-Tracking · W4 KI-Prompts · W5 Firmen-Nachweise
# W6 DSGVO-TOM · W7 Risikobewertung
# ════════════════════════════════════════════════════════════════════

import os as _os
from contextlib import contextmanager

_OBJECT_KIND = 'wiba_control'


def _sync_dsgvo_tom(projekt_name: str) -> list:
    """#1575: Nach einer Antwort-Änderung die DSGVO-TOM (Quelle WiBA) aller DSGVO-Projekte
    nachziehen, die diese WiBA-Instanz nutzen. Best effort — darf WiBA nie blockieren."""
    try:
        from dsgvo.tom_wiba import sync_for_wiba_projekt
        return sync_for_wiba_projekt(projekt_name, wiba_db=DB_PATH)
    except Exception:  # noqa: BLE001
        current_app.logger.warning('TOM-Abgleich (#1575) fehlgeschlagen', exc_info=True)
        return []


@wiba_bp.get('/tom-mapping')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def tom_mapping():
    """#1575: control_id → verknüpfte DSGVO-TOM (Filter „TOM-relevant" in WiBA)."""
    try:
        from dsgvo.tom_wiba import control_index
        from dsgvo.tom_katalog import SEED_KATALOG
        titel = {e['massnahme_key']: {'titel': e['titel'], 'ziel': e['ziel']} for e in SEED_KATALOG}
        idx = control_index()
        return jsonify({
            'controls': {cid: [{'key': k, **titel.get(k, {})} for k in keys] for cid, keys in idx.items()},
            'toms': [{'key': k, **v} for k, v in titel.items()
                     if any(k in keys for keys in idx.values())],
        })
    except Exception as e:
        return _log_500(e)
_EVIDENCE_DB = Path('data/db/evidence.sqlite')
_DSGVO_DB = Path('data/db/dsgvo.sqlite')
_RB_DB = Path('data/db/risikobewertung.sqlite')


def _vcs_block(p: dict) -> dict:
    meta = p.get('meta') or {}
    v = meta.get('vcs_publish')
    return v if isinstance(v, dict) else {}


def _control_lookup(control_id: str) -> dict | None:
    for f in wdb.list_prueffragen(DB_PATH):
        if f['control_id'] == control_id:
            return f
    return None


def _complete_control_if_issue_resolved(projekt_name: str, control_id: str) -> bool:
    """#1526/#1520: Markiert eine WiBA-Prüffrage als „Neubewertung erforderlich"
    (Notiz-Marker), sobald sich ein verknüpftes Issue geschlossen/geöffnet hat — die
    **Antwort (offen/ja/nein/nicht_relevant) bleibt UNVERÄNDERT** (Compliance: keine
    automatische Erfüllung). Nur bereits in-Scope bewertete Controls (``ja``/``nein``)
    werden markiert; ``offen``/``nicht_relevant`` bleiben unberührt.
    """
    from shared.issue_links import list_links
    from shared.issue_completion import reassessment_kommentar

    links = list_links(DB_PATH, projekt_name=projekt_name,
                       object_kind=_OBJECT_KIND, object_id=control_id)
    existing = wdb.load_antworten(DB_PATH, projekt_name).get(control_id, {})
    status = str(existing.get('status') or 'offen')
    notiz = str(existing.get('notiz') or '')
    if status not in ('ja', 'nein'):
        return False
    new_notiz = reassessment_kommentar(links, notiz)
    if new_notiz is None:
        return False
    wdb.save_antwort(
        DB_PATH, projekt_name, control_id,
        status=status,  # ANTWORT UNVERÄNDERT (#1526)
        notiz=new_notiz,
        verantwortlich=str(existing.get('verantwortlich') or ''),
        zieldatum=str(existing.get('zieldatum') or ''),
        evidence_doc_ids=existing.get('evidence_doc_ids') or [])
    return True


def _theme_lookup(theme_key: str) -> dict:
    for t in wdb.list_themen(DB_PATH):
        if t['theme_key'] == theme_key:
            return t
    return {}


@contextmanager
def _vcs_token_env(provider: str, vcs: dict):
    from shared.vcs_repo_config import vcs_token
    token = vcs_token(vcs)
    names = ['GITLAB_TOKEN'] if provider == 'gitlab' else ['GH_TOKEN', 'GITHUB_TOKEN']
    saved: dict[str, str | None] = {}
    try:
        if token:
            for n in names:
                saved[n] = _os.environ.get(n)
                _os.environ[n] = token
        yield
    finally:
        for n, val in saved.items():
            if val is None:
                _os.environ.pop(n, None)
            else:
                _os.environ[n] = val


def _serialize_link(li) -> dict:
    return {
        'link_id': li.id, 'provider': li.provider, 'repo': li.repo,
        'issue_number': li.issue_number, 'issue_iid': li.issue_iid,
        'url': li.url, 'title': li.title, 'state': li.state,
        'state_reason': li.state_reason,
    }


# ── Repo-Konfiguration (pro Projekt) ──────────────────────────────────────────

@wiba_bp.get('/projekte/<projekt_name>/repo-config')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def get_repo_config(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    from shared.vcs_repo_config import public_vcs
    return jsonify(public_vcs(_vcs_block(p)))


@wiba_bp.put('/projekte/<projekt_name>/repo-config')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def put_repo_config(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    from shared.vcs_repo_config import sanitize_vcs, public_vcs
    body = request.get_json(silent=True) or {}
    meta = dict(p.get('meta') or {})
    meta['vcs_publish'] = sanitize_vcs(body.get('vcs_publish'), _vcs_block(p))
    wdb.update_projekt_meta(DB_PATH, projekt_name, meta)
    return jsonify(public_vcs(meta['vcs_publish']))


# ── W3: Issues je Prüffrage ───────────────────────────────────────────────────

@wiba_bp.get('/projekte/<projekt_name>/controls/<control_id>/issues')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def list_control_issues(projekt_name, control_id):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from shared.issue_links import list_links, ensure_tables
        ensure_tables(DB_PATH)
        links = list_links(DB_PATH, projekt_name=projekt_name,
                           object_kind=_OBJECT_KIND, object_id=control_id)
        return jsonify([_serialize_link(li) for li in links])
    except Exception as e:
        return _log_500(e)


@wiba_bp.post('/projekte/<projekt_name>/controls/<control_id>/issues')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def create_control_issue(projekt_name, control_id):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from shared.vcs_repo_config import resolve_repo
        from shared.issue_links import add_link, ensure_tables
        ensure_tables(DB_PATH)
        body = request.get_json(silent=True) or {}
        vcs = _vcs_block(p)
        provider = str(body.get('provider') or vcs.get('provider') or 'github').lower()
        repo = resolve_repo(vcs, body.get('repo'))
        if not repo:
            return jsonify({'error': 'Kein Repository konfiguriert (Repo-Config setzen)'}), 400
        ctrl = _control_lookup(control_id) or {}
        theme = _theme_lookup(ctrl.get('theme_key', ''))
        title = body.get('title') or f"[WiBA] {control_id}: {ctrl.get('frage', '')[:80]}"
        bodytext = body.get('body') or (
            f"**WiBA-Prüffrage** ({control_id}) — Thema: {theme.get('titel', '')}"
            f" (BSI: {theme.get('bausteine', '')})\n\n"
            f"**Frage:** {ctrl.get('frage', '')}\n\n"
            f"**Hilfestellung:** {ctrl.get('hilfsmittel', '')}\n\n"
            f"_Offener Punkt der Basis-Absicherung._")
        with _vcs_token_env(provider, vcs):
            if provider == 'gitlab':
                from vcs.gitlab_issues import create_issue as gl_create
                created = gl_create(repo=repo, title=title, body=bodytext)
            else:
                from vcs.github_issues import create_issue as gh_create
                created = gh_create(repo=repo, title=title, body=bodytext)
        link_id = add_link(
            DB_PATH, projekt_name=projekt_name, object_kind=_OBJECT_KIND,
            object_id=control_id, provider=provider, repo=repo,
            issue_number=getattr(created, 'number', None),
            issue_iid=getattr(created, 'iid', None),
            url=created.url, title=title, state='open')
        return jsonify({'ok': True, 'link_id': link_id, 'url': created.url,
                        'issue_number': getattr(created, 'number', None)}), 201
    except Exception as e:
        return _log_500(e)


@wiba_bp.post('/projekte/<projekt_name>/controls/<control_id>/issues/sync')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def sync_control_issues(projekt_name, control_id):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from shared.issue_links import list_links, update_issue_state
        from shared.issue_sync import sync_github_issue, sync_gitlab_issue
        vcs = _vcs_block(p)
        links = list_links(DB_PATH, projekt_name=projekt_name,
                           object_kind=_OBJECT_KIND, object_id=control_id)
        for li in links:
            try:
                with _vcs_token_env(li.provider, vcs):
                    if li.provider == 'gitlab':
                        st = sync_gitlab_issue(
                            base_url=vcs.get('base_url', ''),
                            token_env=vcs.get('token_env', 'GITLAB_TOKEN'),
                            project=li.repo, iid=li.issue_iid or 0)
                    else:
                        st = sync_github_issue(repo=li.repo, number=li.issue_number or 0)
                update_issue_state(DB_PATH, li.id, state=st.state, state_reason=st.state_reason)
            except Exception:
                continue
        # #1508: gelöstes Issue → Prüffrage auto-vervollständigen (Neubewertungs-Standard).
        _complete_control_if_issue_resolved(projekt_name, control_id)
        links = list_links(DB_PATH, projekt_name=projekt_name,
                           object_kind=_OBJECT_KIND, object_id=control_id)
        return jsonify([_serialize_link(li) for li in links])
    except Exception as e:
        return _log_500(e)


@wiba_bp.delete('/projekte/<projekt_name>/controls/<control_id>/issues/<link_id>')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def unlink_control_issue(projekt_name, control_id, link_id):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from shared.issue_links import delete_link
        delete_link(DB_PATH, link_id)
        return jsonify({'ok': True})
    except Exception as e:
        return _log_500(e)


# ── W5: Firmen-Nachweise (Evidence) ───────────────────────────────────────────

@wiba_bp.get('/projekte/<projekt_name>/firmen-evidence')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def list_firmen_evidence(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    firma = (p.get('unternehmen') or '').strip()
    if not firma:
        return jsonify({'firma': '', 'dokumente': []})
    try:
        from evidence.db import list_documents
        docs = list_documents(_EVIDENCE_DB, firmen_id=firma)
        return jsonify({'firma': firma, 'dokumente': [
            {'id': d.id, 'filename': d.filename, 'doc_type': d.doc_type,
             'version': d.version} for d in docs]})
    except Exception as e:
        return _log_500(e)


def _firma_evidence_texts(firma: str, max_docs: int = 5) -> list[dict]:
    out: list[dict] = []
    if not firma:
        return out
    try:
        from evidence.db import list_documents, get_extracted_text
        for d in list_documents(_EVIDENCE_DB, firmen_id=firma)[:max_docs]:
            txt = get_extracted_text(_EVIDENCE_DB, d.id)
            if txt:
                out.append({'filename': d.filename, 'text': txt})
    except Exception:
        pass
    return out


# ── W6: DSGVO-TOM als Nachweis-Vorschlag ──────────────────────────────────────

@wiba_bp.get('/projekte/<projekt_name>/tom-evidence')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def tom_evidence(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    firma = (p.get('unternehmen') or '').strip()
    if not firma:
        return jsonify({'firma': '', 'massnahmen': []})
    try:
        from shared import db as _sdb
        from dsgvo import tom_katalog as tk
        con = _sdb.connect(str(_DSGVO_DB))
        try:
            rows = con.execute(
                "SELECT name FROM dsgvo_projekte WHERE unternehmen=?", (firma,)).fetchall()
        finally:
            con.close()
        massnahmen = []
        for (dp,) in rows:
            for m in tk.list_massnahmen(_DSGVO_DB, dp):
                if int(m.get('status') or 0) > 0:
                    massnahmen.append({
                        'dsgvo_projekt': dp, 'ziel': m.get('ziel'),
                        'titel': m.get('titel'), 'status': m.get('status'),
                        'wirksamkeit_ergebnis': m.get('wirksamkeit_ergebnis', '')})
        return jsonify({'firma': firma, 'massnahmen': massnahmen})
    except Exception as e:
        return _log_500(e)


# ── W7: „Nein"-Befund → Risiko (Risikobewertung) ──────────────────────────────

def _wiba_rb_name(projekt_name: str) -> str:
    """URL-sicherer Name des verknüpften RB-Projekts (kein '/', vgl. #1116)."""
    return f"WiBA-Befunde: {str(projekt_name).replace('/', '-').strip()}"


def _ensure_wiba_rb_projekt(p: dict, projekt_name: str) -> str:
    from risikobewertung.db import load_projekt as rb_load, save_projekt as rb_save
    from risikobewertung.frameworks import FRAMEWORK_IDS
    rb_name = _wiba_rb_name(projekt_name)
    if not rb_load(_RB_DB, rb_name):
        fw = 'STRIDE' if 'STRIDE' in FRAMEWORK_IDS else list(FRAMEWORK_IDS)[0]
        rb_save(_RB_DB, name=rb_name, framework=fw,
                beschreibung=f"Offene WiBA-Befunde (Basis-Absicherung) zu Projekt '{projekt_name}'.",
                unternehmen=p.get('unternehmen', '') or '', produkt='',
                berater=p.get('berater', '') or '',
                meta={'linked_wiba_projekt': projekt_name, 'source': 'wiba'})
    # Verknüpfung im WiBA-Projekt vermerken
    meta = dict(p.get('meta') or {})
    if meta.get('linked_risk_projekt') != rb_name:
        meta['linked_risk_projekt'] = rb_name
        wdb.update_projekt_meta(DB_PATH, projekt_name, meta)
    return rb_name


@wiba_bp.post('/projekte/<projekt_name>/controls/<control_id>/risk')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def promote_control_risk(projekt_name, control_id):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from risikobewertung.db import save_risiko as rb_save_risiko
        from risikobewertung.frameworks import berechne_risiko
        rb_name = _ensure_wiba_rb_projekt(p, projekt_name)
        ctrl = _control_lookup(control_id) or {}
        theme = _theme_lookup(ctrl.get('theme_key', ''))
        from risikobewertung.db import load_projekt as rb_load
        fw = (rb_load(_RB_DB, rb_name) or {}).get('framework', 'STRIDE')
        felder = request.get_json(silent=True) or {}
        felder = felder.get('felder', {}) if isinstance(felder, dict) else {}
        wert, label, detail = berechne_risiko(fw, felder)
        rid = rb_save_risiko(_RB_DB, {
            'projekt_name': rb_name, 'framework': fw,
            'risk_name': f"WiBA {control_id}: {ctrl.get('frage', '')[:70]}",
            'beschreibung': (f"Offener Punkt der Basis-Absicherung — Thema "
                             f"{theme.get('titel', '')} (BSI {theme.get('bausteine', '')}).\n"
                             f"{ctrl.get('frage', '')}"),
            'felder': felder, 'risikowert': wert, 'risiko_label': label,
            'detail_text': detail})
        return jsonify({'ok': True, 'rb_projekt': rb_name, 'risk_id': rid}), 201
    except Exception as e:
        return _log_500(e)


@wiba_bp.get('/projekte/<projekt_name>/risiken')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def list_wiba_risiken(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    rb_name = (p.get('meta') or {}).get('linked_risk_projekt')
    if not rb_name:
        return jsonify({'rb_projekt': None, 'risiken': []})
    try:
        from risikobewertung.db import load_risiken
        rows = load_risiken(_RB_DB, rb_name)
        return jsonify({'rb_projekt': rb_name, 'risiken': [
            {'id': r.get('id'), 'risk_name': r.get('risk_name'),
             'risiko_label': r.get('risiko_label'), 'risikowert': r.get('risikowert'),
             'is_resolved': bool(r.get('is_resolved'))} for r in rows]})
    except Exception as e:
        return _log_500(e)


# ── W8: Nachweis-Report (DOCX/PDF) ────────────────────────────────────────────

@wiba_bp.get('/projekte/<projekt_name>/report')
@jwt_required()
@require_permission(Permission.WIBA_EXPORT)
def export_report(projekt_name):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    fmt = (request.args.get('format') or 'pdf').lower()
    if fmt not in {'pdf', 'docx'}:
        return jsonify({'error': 'Format muss pdf|docx sein'}), 400
    try:
        from flask import send_file
        from server.api.workspace_tmp import workspace_tmpdir
        out_dir = workspace_tmpdir('wiba_report_')
        if fmt == 'docx':
            from wiba.report_export import export_report_docx
            path = export_report_docx(out_dir, projekt_name, DB_PATH)
        else:
            from wiba.report_export import export_report_pdf
            path = export_report_pdf(out_dir, projekt_name, DB_PATH)
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except Exception as e:
        return _log_500(e)


# ── W4: KI-Prompts (Copy/Paste) ───────────────────────────────────────────────

@wiba_bp.post('/projekte/<projekt_name>/controls/<control_id>/prompt')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def build_control_prompt(projekt_name, control_id):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from wiba.prompts import build_prompt
        ctrl = _control_lookup(control_id)
        if not ctrl:
            # Leeren Katalog von unbekannter Control unterscheiden (#1364): ohne
            # geladenen BSI-Katalog gibt es keine Prüffragen → klare Handlungsanweisung.
            if not wdb.list_prueffragen(DB_PATH):
                return jsonify({'error': 'WiBA-Katalog ist nicht geladen — bitte unter '
                                'Admin → WiBA-Katalog die BSI-Quellen herunterladen und '
                                'einlesen.'}), 409
            return jsonify({'error': 'Prüffrage nicht gefunden'}), 404
        theme = _theme_lookup(ctrl.get('theme_key', ''))
        body = request.get_json(silent=True) or {}
        ev = _firma_evidence_texts(p.get('unternehmen', '')) if body.get('include_evidence', True) else []
        # #1524: Neubewertung mit Issue-Feedback — Inhalt verknüpfter Issues einbeziehen.
        issue_context = str(body.get('issue_context') or '').strip()
        if not issue_context and body.get('use_issue_feedback'):
            from shared.issue_feedback import collect_object_feedback
            issue_context = collect_object_feedback(DB_PATH, projekt_name, _OBJECT_KIND, control_id)
        prompt = build_prompt(ctrl, theme, ev, issue_context=issue_context)
        return jsonify({'prompt': prompt, 'control_id': control_id,
                        'evidence_used': [e['filename'] for e in ev]})
    except Exception as e:
        return _log_500(e)


@wiba_bp.post('/projekte/<projekt_name>/controls/<control_id>/import-issue')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def control_import_issue(projekt_name, control_id):
    """#1521/#1524: Inhalt verknüpfter Issues in die Notiz übernehmen — die WiBA-Antwort
    (offen/ja/nein/nicht_relevant) bleibt UNVERÄNDERT (score-neutral)."""
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        data = request.get_json(silent=True) or {}
        issue_context = str(data.get('issue_context') or '').strip()
        if not issue_context:
            from shared.issue_feedback import collect_object_feedback
            issue_context = collect_object_feedback(DB_PATH, projekt_name, _OBJECT_KIND, control_id)
            if not issue_context:
                return jsonify({'error': 'Keine verknüpften Issue-Inhalte gefunden'}), 400
        from shared.issue_feedback import merge_feedback_into_comment
        existing = wdb.load_antworten(DB_PATH, projekt_name).get(control_id, {})
        neue_notiz = merge_feedback_into_comment(existing.get('notiz', '') or '', issue_context)
        wdb.save_antwort(
            DB_PATH, projekt_name, control_id,
            status=str(existing.get('status') or 'offen'),  # ANTWORT UNVERÄNDERT
            notiz=neue_notiz,
            verantwortlich=str(existing.get('verantwortlich') or ''),
            zieldatum=str(existing.get('zieldatum') or ''),
            evidence_doc_ids=existing.get('evidence_doc_ids') or [])
        return jsonify({'imported': True, 'control_id': control_id, 'notiz': neue_notiz})
    except Exception as e:
        return _log_500(e)


@wiba_bp.post('/projekte/<projekt_name>/controls/<control_id>/parse-response')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def parse_control_response(projekt_name, control_id):
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from wiba.prompts import parse_json_antwort
        body = request.get_json(silent=True) or {}
        parsed = parse_json_antwort(body.get('raw', ''))
        if isinstance(parsed, list):
            parsed = next((x for x in parsed
                           if str(x.get('control_id')) == control_id), parsed[0] if parsed else {})
        result = {
            'status': parsed.get('status', 'offen'),
            'notiz': parsed.get('notiz', ''),
            'empfehlung': parsed.get('empfehlung', ''),
        }
        if body.get('apply'):
            wdb.save_antwort(DB_PATH, projekt_name, control_id,
                             status=result['status'], notiz=result['notiz'])
            _sync_dsgvo_tom(projekt_name)  # #1575
        return jsonify({'ok': True, 'parsed': result,
                        'reifegrad': wdb.compute_reifegrad(DB_PATH, projekt_name)})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return _log_500(e)


_WIBA_AUTO_SYSTEM = (
    'Du bist ein erfahrener Prüfer für die BSI-Basis-Absicherung (WiBA). '
    'Beantworte die Prüffrage ausschließlich anhand der bereitgestellten Informationen '
    'und antworte im geforderten JSON-Format.')


@wiba_bp.post('/projekte/<projekt_name>/controls/<control_id>/auto-bewertung/stream')
@jwt_required()
@require_permission(Permission.WIBA_WRITE)
def control_auto_bewertung_stream(projekt_name, control_id):
    """#1573: Automatische Bewertung einer Prüffrage über den konfigurierten KI-Provider
    (Parität zu CRA/NIS2/AI-Act/DSGVO/Risikobewertung). Live-SSE; am Ende wird die
    Antwort (ja/nein/nicht_relevant + Notiz) gespeichert — übrige Felder bleiben erhalten.

    Body: { use_issue_feedback?: bool, issue_context?: str }
    """
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from wiba.prompts import build_prompt, parse_json_antwort
        from wiba.constants import normalize_status
        from server.services.auto_bewertung import ensure_ai_available, ki_kennzeichnung, AutoBewertungUnavailable
        ctrl = _control_lookup(control_id)
        if not ctrl:
            return jsonify({'error': 'Prüffrage nicht gefunden'}), 404
        try:
            ensure_ai_available()
        except AutoBewertungUnavailable as e:
            return jsonify({'error': str(e)}), 409
        theme = _theme_lookup(ctrl.get('theme_key', ''))
        body = request.get_json(silent=True) or {}
        ev = _firma_evidence_texts(p.get('unternehmen', ''))
        issue_context = str(body.get('issue_context') or '').strip()
        if not issue_context and body.get('use_issue_feedback'):
            from shared.issue_feedback import collect_object_feedback
            issue_context = collect_object_feedback(DB_PATH, projekt_name, _OBJECT_KIND, control_id)
        prompt = build_prompt(ctrl, theme, ev, issue_context=issue_context)

        def _finalize(full_text: str) -> dict:
            from ai_compliance_suite.ai.dispatch import current_provider_name
            parsed = parse_json_antwort(full_text)
            if isinstance(parsed, list):
                parsed = next((x for x in parsed if str(x.get('control_id')) == control_id),
                              parsed[0] if parsed else {})
            if not isinstance(parsed, dict):
                raise ValueError('KI-Antwort enthält kein JSON-Objekt')
            status = normalize_status(parsed.get('status'))
            notiz = ki_kennzeichnung(str(parsed.get('notiz') or ''), current_provider_name())
            empfehlung = str(parsed.get('empfehlung') or '')
            existing = wdb.load_antworten(DB_PATH, projekt_name).get(control_id, {})
            wdb.save_antwort(
                DB_PATH, projekt_name, control_id, status=status, notiz=notiz,
                verantwortlich=str(existing.get('verantwortlich') or ''),
                zieldatum=str(existing.get('zieldatum') or ''),
                evidence_doc_ids=existing.get('evidence_doc_ids') or [])
            _sync_dsgvo_tom(projekt_name)  # #1575
            return {'status': status, 'status_label': STATUS_META.get(status, {}).get('label', status),
                    'kommentar': notiz, 'notiz': notiz,
                    'massnahmen': [empfehlung] if empfehlung else [], 'saved': True}

        from shared.sse import stream_ai_sse
        return stream_ai_sse(_WIBA_AUTO_SYSTEM, prompt, finalize=_finalize, force_json=True,
                             temperature=0.2, num_predict=4096)  # #1588
    except Exception as e:
        return _log_500(e)


# #1528 (WiBA) — Massenbewertung über EINEN Sammel-Prompt (themenübergreifend)
@wiba_bp.post('/projekte/<projekt_name>/controls/mass-prompt')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def controls_mass_prompt(projekt_name):
    """EIN Sammel-Prompt für mehrere ausgewählte Prüffragen. Filter: control_ids /
    only_open (status 'offen') / only_reassess (Marker in Notiz)."""
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from wiba.prompts import build_mass_control_prompt
        body = request.get_json(silent=True) or {}
        fragen = wdb.list_prueffragen(DB_PATH)
        if not fragen:
            return jsonify({'error': 'WiBA-Katalog ist nicht geladen — bitte unter '
                            'Admin → WiBA-Katalog die BSI-Quellen importieren.'}), 409
        antworten = wdb.load_antworten(DB_PATH, projekt_name)
        themen = {t['theme_key']: t for t in wdb.list_themen(DB_PATH)}
        ids = body.get('control_ids')
        ids_set = {str(x) for x in ids} if ids else None
        only_open = bool(body.get('only_open'))
        only_reassess = bool(body.get('only_reassess'))
        selected = []
        for f in fragen:
            cid = str(f.get('control_id'))
            if ids_set is not None and cid not in ids_set:
                continue
            a = antworten.get(cid, {})
            status = str(a.get('status') or 'offen')
            notiz = str(a.get('notiz') or '')
            if only_open and status != 'offen':
                continue
            if only_reassess and 'Neubewertung erforderlich' not in notiz:
                continue
            th = themen.get(f.get('theme_key'), {})
            selected.append({**f, 'theme_titel': th.get('titel', ''),
                             'bausteine': th.get('bausteine', '')})
        if not selected:
            return jsonify({'error': 'Keine passenden Prüffragen gefunden'}), 400
        ev = _firma_evidence_texts(p.get('unternehmen', '')) if body.get('include_evidence', True) else []
        prompt = build_mass_control_prompt(selected, ev)
        return jsonify({'prompt': prompt, 'count': len(selected),
                        'controls': [{'control_id': s['control_id'], 'frage': s.get('frage', '')}
                                     for s in selected],
                        'evidence_used': [e['filename'] for e in ev]})
    except Exception as e:
        return _log_500(e)


@wiba_bp.post('/projekte/<projekt_name>/controls/mass-preview')
@jwt_required()
@require_permission(Permission.WIBA_READ)
def controls_mass_preview(projekt_name):
    """Parst die Sammel-Antwort (JSON-Array) → Vorschau je Prüffrage (KEIN Speichern)."""
    p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from wiba.prompts import parse_json_antwort
        from wiba.constants import STATUS_WERTE
        body = request.get_json(silent=True) or {}
        parsed = parse_json_antwort(body.get('response') or body.get('raw') or '')
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            return jsonify({'error': 'Antwort ist kein JSON-Array'}), 400
        frage_map = {str(f['control_id']): f.get('frage', '') for f in wdb.list_prueffragen(DB_PATH)}
        items = []
        for e in parsed:
            if not isinstance(e, dict):
                continue
            cid = str(e.get('control_id') or '').strip()
            if not cid or cid not in frage_map:
                continue
            status = str(e.get('status') or 'offen')
            if status not in STATUS_WERTE:
                status = 'offen'
            items.append({'control_id': cid, 'frage': frage_map[cid],
                          'status': status, 'notiz': str(e.get('notiz') or '')})
        if not items:
            return jsonify({'error': 'Keine gültigen Antworten erkannt'}), 400
        return jsonify({'items': items, 'count': len(items)})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return _log_500(e)
