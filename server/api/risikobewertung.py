"""Risikobewertung Module API — vollständige CRUD + 5 Frameworks + Audit."""

from flask import current_app, Blueprint, request, jsonify
from server.api._tmp import workspace_tmpdir
from flask_jwt_extended import jwt_required
from pathlib import Path
from typing import Any, Dict, List
import json
import sqlite3

from risikobewertung.db import (
    list_projekte,
    save_projekt,
    load_projekt,
    delete_projekt as db_delete_projekt,
    load_risiken,
    save_risiko as db_save_risiko,
    delete_risiko as db_delete_risiko,
    set_risiko_resolved as db_set_resolved,
    bulk_insert_risiken,
)

from risikobewertung.frameworks import (
    FRAMEWORK_IDS,
    FRAMEWORK_LABELS,
    FRAMEWORK_ERKLAERUNG,
    framework_felder,
    berechne_risiko,
    risiko_farbe,
)

rb_bp = Blueprint('risikobewertung', __name__)

DB_PATH = Path('data/db/risikobewertung.sqlite')


# ============================================================
# Hilfsfunktionen
# ============================================================

def _serialize_risiko(r: Dict[str, Any]) -> Dict[str, Any]:
    """DB-Risiko zu API-Format."""
    felder = r.get('felder') or {}
    if isinstance(felder, str):
        try:
            felder = json.loads(felder)
        except Exception:
            felder = {}
    return {
        'id': r.get('id'),
        'projekt': r.get('projekt_name', ''),
        'nr': r.get('nr', 0),
        'name': r.get('risk_name', ''),
        'risk_name': r.get('risk_name', ''),
        'beschreibung': r.get('beschreibung', ''),
        'framework': r.get('framework', ''),
        'felder': felder,
        'risikowert': r.get('risikowert'),
        'wert': r.get('risikowert'),
        'risiko_label': r.get('risiko_label', ''),
        'level': r.get('risiko_label', ''),
        'detail_text': r.get('detail_text', ''),
        'bewertung_text': r.get('bewertung_text', ''),
        'prompt_text': r.get('prompt_text', ''),
        'is_resolved': bool(r.get('is_resolved', 0)),
        'resolved_at': r.get('resolved_at'),
        'resolved_reason': r.get('resolved_reason', ''),
        'farbe': risiko_farbe(r.get('risiko_label', '')),
        'status': 'Resolved' if r.get('is_resolved') else 'Aktiv',
        'created_at': r.get('created_at'),
        'updated_at': r.get('updated_at'),
    }


def _serialize_projekt(p: Dict[str, Any], risk_count: int = 0) -> Dict[str, Any]:
    """DB-Projekt zu API-Format."""
    return {
        'id': p.get('name'),
        'name': p.get('name', ''),
        'framework': p.get('framework', 'STRIDE'),
        'beschreibung': p.get('beschreibung', ''),
        'description': p.get('beschreibung', ''),
        'risiken_count': risk_count,
        'created_at': p.get('created_at'),
        'updated_at': p.get('updated_at'),
    }


def _next_nr(projekt_name: str) -> int:
    """Nächste freie Nummer für ein neues Risiko in einem Projekt."""
    risiken = load_risiken(DB_PATH, projekt_name)
    return max([r.get('nr', 0) for r in risiken], default=0) + 1


# ============================================================
# Frameworks (Konstanten)
# ============================================================

@rb_bp.post('/projekte/<projekt_name>/issue-sync')
@jwt_required()
def bulk_issue_sync(projekt_name: str):
    """Bulk-Sync: für alle Risiken im Projekt, die ein verknüpftes Issue haben
    (Tabelle `linked_issues`, von der Desktop-Variante befüllt), holt der Server
    den aktuellen Issue-Status.

    Body: { "refresh": bool } — wenn true, GitHub/GitLab-API live abfragen;
        sonst nur DB-Snapshot aus `linked_issues` zurückgeben.
    Returns: { items: [{risk_id, risk_name, url, provider, title, state, ...}] }
    """
    import re
    import sqlite3
    if not load_projekt(DB_PATH, projekt_name):
        return {'error': 'Projekt nicht gefunden'}, 404

    data = request.get_json(silent=True) or {}
    refresh = bool(data.get('refresh'))

    risiken = load_risiken(DB_PATH, projekt_name)
    by_id: dict[int, dict] = {}
    for r in risiken:
        try:
            by_id[int(r.get('id'))] = r
        except (TypeError, ValueError):
            pass

    # Verknüpfungen kommen aus `linked_issues` (von der Desktop-Variante befüllt).
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT * FROM linked_issues "
            "WHERE projekt_name = ? AND object_kind = 'risk' "
            "ORDER BY object_id, issue_number",
            (projekt_name,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        con.close()

    items = []
    for row in rows:
        try:
            rid = int(row['object_id'])
        except (TypeError, ValueError):
            continue
        url = row['url'] or ''
        item: dict = {
            'risk_id': rid,
            'risk_name': by_id.get(rid, {}).get('risk_name', ''),
            'url': url,
            'provider': row['provider'],
            'title': row['title'] or '',
            'state': row['state'] or '',
            'state_reason': row['state_reason'] or '',
            'updated_at': row['updated_at'],
            'ok': True,
        }

        if refresh and url:
            try:
                m = re.match(r'^https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)', url, re.IGNORECASE)
                if m:
                    from shared.issue_sync import fetch_github_issue_details
                    d = fetch_github_issue_details(
                        repo=f'{m.group(1)}/{m.group(2)}', number=int(m.group(3)),
                    )
                    item['title'] = d.get('title') or item['title']
                    item['state'] = d.get('state') or item['state']
                    item['body'] = (d.get('body') or '')[:600]
                    item['comments_count'] = len(d.get('comments') or [])
                else:
                    m = re.match(r'^https?://([^/]+)/(.+)/-/issues/(\d+)', url)
                    if m:
                        from shared.issue_sync import fetch_gitlab_issue_details
                        d = fetch_gitlab_issue_details(
                            base_url=f'https://{m.group(1)}', token_env='GITLAB_TOKEN',
                            project=m.group(2), iid=int(m.group(3)),
                        )
                        item['title'] = d.get('title') or item['title']
                        item['state'] = d.get('state') or item['state']
                        item['body'] = (d.get('body') or '')[:600]
                        item['comments_count'] = len(d.get('comments') or [])
            except Exception as e:
                item['ok'] = False
                item['error'] = f'{type(e).__name__}: {e}'

        items.append(item)

    return {'items': items, 'total': len(items), 'from_db_only': not refresh}, 200


@rb_bp.get('/projekte/<projekt_name>/risiken/<int:risk_id>/linked-issues')
@jwt_required()
def linked_issues_for_risk(projekt_name: str, risk_id: int):
    """Verknüpfte Issues eines Risikos (aus Tabelle linked_issues, befüllt
    durch die Desktop-Variante). Frontend nutzt das für Vorbefüllung des
    "Issue-Inhalt importieren"-Modals.
    """
    import sqlite3
    if not load_projekt(DB_PATH, projekt_name):
        return {'error': 'Projekt nicht gefunden'}, 404

    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT url, title, state, state_reason, provider, issue_number, updated_at "
            "FROM linked_issues "
            "WHERE projekt_name = ? AND object_kind = 'risk' AND object_id = ? "
            "ORDER BY updated_at DESC, issue_number DESC",
            (projekt_name, str(risk_id)),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        con.close()

    items = [dict(r) for r in rows]
    return {'items': items, 'total': len(items)}, 200


@rb_bp.post('/issue-content')
@jwt_required()
def fetch_issue_content():
    """Holt Title+Body+Kommentare einer GitHub-/GitLab-Issue-URL (Issue #392/#404).

    Body: { "url": "https://github.com/owner/repo/issues/123" }
    Returns: { "title": str, "body": str, "comments": [str], "combined": str }
    """
    import re
    data = request.get_json(silent=True) or {}
    url = str(data.get('url') or '').strip()
    if not url:
        return {'error': 'url fehlt'}, 400

    # GitHub-URL parsen
    m = re.match(r'^https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)', url, re.IGNORECASE)
    if m:
        owner, repo, num = m.group(1), m.group(2), int(m.group(3))
        try:
            from shared.issue_sync import fetch_github_issue_details
            details = fetch_github_issue_details(repo=f"{owner}/{repo}", number=num)
        except Exception as e:
            return {'error': f'Issue konnte nicht geholt werden: {e}'}, 502
        title = details.get('title') or ''
        body = details.get('body') or ''
        comments = details.get('comments') or []
        combined = f"# {title}\n\n{body}"
        if comments:
            combined += "\n\n---\n\n## Kommentare\n\n" + "\n\n---\n\n".join(
                str(c) for c in comments
            )
        return {'title': title, 'body': body, 'comments': comments, 'combined': combined}, 200

    # GitLab-URL parsen
    m = re.match(r'^https?://([^/]+)/(.+)/-/issues/(\d+)', url)
    if m:
        host, project, iid = m.group(1), m.group(2), int(m.group(3))
        try:
            from shared.issue_sync import fetch_gitlab_issue_details
            details = fetch_gitlab_issue_details(
                base_url=f"https://{host}", token_env="GITLAB_TOKEN",
                project=project, iid=iid,
            )
        except Exception as e:
            return {'error': f'GitLab-Issue konnte nicht geholt werden: {e}'}, 502
        title = details.get('title') or ''
        body = details.get('body') or ''
        comments = details.get('comments') or []
        combined = f"# {title}\n\n{body}"
        if comments:
            combined += "\n\n---\n\n## Kommentare\n\n" + "\n\n---\n\n".join(str(c) for c in comments)
        return {'title': title, 'body': body, 'comments': comments, 'combined': combined}, 200

    return {'error': 'URL-Format nicht erkannt (GitHub-/GitLab-Issue-URL erwartet)'}, 400


@rb_bp.get('/frameworks')
@jwt_required()
def list_frameworks():
    """Liste der 5 verfügbaren Frameworks mit Beschreibungen."""
    return [
        {
            'id': fw_id,
            'label': FRAMEWORK_LABELS.get(fw_id, fw_id),
            'description': FRAMEWORK_ERKLAERUNG.get(fw_id, ''),
        }
        for fw_id in FRAMEWORK_IDS
    ], 200


@rb_bp.get('/frameworks/<framework_id>/felder')
@jwt_required()
def get_framework_felder(framework_id: str):
    """Eingabefelder für ein Framework (für dynamischen Editor)."""
    if framework_id not in FRAMEWORK_IDS:
        return {'error': f'Unbekanntes Framework: {framework_id}'}, 404
    try:
        felder = framework_felder(framework_id)
        return {
            'framework': framework_id,
            'label': FRAMEWORK_LABELS.get(framework_id, framework_id),
            'description': FRAMEWORK_ERKLAERUNG.get(framework_id, ''),
            'felder': felder,
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/frameworks/<framework_id>/calculate')
@jwt_required()
def calculate_score(framework_id: str):
    """Score+Label aus Eingabewerten berechnen (Live-Vorschau im Editor)."""
    if framework_id not in FRAMEWORK_IDS:
        return {'error': f'Unbekanntes Framework: {framework_id}'}, 404
    try:
        data = request.json or {}
        felder = data.get('felder', {})
        risikowert, label, detail_text = berechne_risiko(framework_id, felder)
        return {
            'framework': framework_id,
            'risikowert': risikowert,
            'risiko_label': label,
            'detail_text': detail_text,
            'farbe': risiko_farbe(label),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Projekte
# ============================================================

@rb_bp.get('/projekte')
@jwt_required()
def get_projekte():
    """Liste aller Projekte mit Risiko-Anzahl."""
    try:
        names = list_projekte(DB_PATH)
        result = []
        for name in names:
            p = load_projekt(DB_PATH, name)
            if p:
                count = len(load_risiken(DB_PATH, name))
                result.append(_serialize_projekt(p, count))
        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.get('/projekte/<projekt_name>')
@jwt_required()
def get_projekt(projekt_name: str):
    """Projekt-Detail laden."""
    try:
        p = load_projekt(DB_PATH, projekt_name)
        if not p:
            return {'error': 'Projekt nicht gefunden'}, 404
        count = len(load_risiken(DB_PATH, projekt_name))
        return _serialize_projekt(p, count), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte')
@jwt_required()
def create_projekt():
    """Neues Projekt anlegen."""
    try:
        data = request.json or {}
        name = (data.get('name') or '').strip()
        if not name:
            return {'error': 'Feld "name" ist Pflicht'}, 400
        framework = data.get('framework', 'STRIDE')
        if framework not in FRAMEWORK_IDS:
            return {'error': f'Ungültiges Framework: {framework}'}, 400
        if load_projekt(DB_PATH, name):
            return {'error': 'Projekt existiert bereits'}, 409

        save_projekt(DB_PATH, name=name, framework=framework, beschreibung=data.get('beschreibung', '') or data.get('description', ''))
        p = load_projekt(DB_PATH, name)
        return _serialize_projekt(p, 0), 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.put('/projekte/<projekt_name>')
@jwt_required()
def update_projekt(projekt_name: str):
    """Projekt aktualisieren."""
    try:
        existing = load_projekt(DB_PATH, projekt_name)
        if not existing:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        framework = data.get('framework')
        if framework and framework not in FRAMEWORK_IDS:
            return {'error': f'Ungültiges Framework: {framework}'}, 400

        save_projekt(
            DB_PATH,
            name=projekt_name,
            framework=framework or existing.get('framework', 'STRIDE'),
            beschreibung=data.get('beschreibung', '') or data.get('description', ''),
        )
        p = load_projekt(DB_PATH, projekt_name)
        count = len(load_risiken(DB_PATH, projekt_name))
        return _serialize_projekt(p, count), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.delete('/projekte/<projekt_name>')
@jwt_required()
def delete_projekt(projekt_name: str):
    """Projekt löschen (inkl. aller Risiken)."""
    try:
        db_delete_projekt(DB_PATH, projekt_name)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Risiken
# ============================================================

@rb_bp.get('/projekte/<projekt_name>/risiken')
@jwt_required()
def get_risiken(projekt_name: str):
    """Risiken eines Projekts."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        risiken = load_risiken(DB_PATH, projekt_name)
        for r in risiken:
            r['projekt_name'] = projekt_name
        return [_serialize_risiko(r) for r in risiken], 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte/<projekt_name>/risiken')
@jwt_required()
def create_risiko(projekt_name: str):
    """Neues Risiko — Score wird aus framework + felder berechnet."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}

        framework = data.get('framework') or projekt.get('framework') or 'STRIDE'
        if framework not in FRAMEWORK_IDS:
            return {'error': f'Ungültiges Framework: {framework}'}, 400

        felder = data.get('felder', {})
        risikowert, label, detail_text = berechne_risiko(framework, felder)

        risk = {
            'projekt_name': projekt_name,
            'nr': data.get('nr') or _next_nr(projekt_name),
            'risk_name': data.get('risk_name') or data.get('name', ''),
            'beschreibung': data.get('beschreibung', ''),
            'framework': framework,
            'felder': felder,
            'risikowert': risikowert,
            'risiko_label': label,
            'detail_text': detail_text,
            'bewertung_text': data.get('bewertung_text', ''),
            'prompt_text': data.get('prompt_text', ''),
        }
        new_id = db_save_risiko(DB_PATH, risk)
        risk['id'] = new_id
        return _serialize_risiko(risk), 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.put('/projekte/<projekt_name>/risiken/<int:risk_id>')
@jwt_required()
def update_risiko(projekt_name: str, risk_id: int):
    """Risiko aktualisieren — Re-Berechnung bei felder-Änderung."""
    try:
        risiken = load_risiken(DB_PATH, projekt_name)
        existing = next((r for r in risiken if r.get('id') == risk_id), None)
        if not existing:
            return {'error': 'Risiko nicht gefunden'}, 404

        data = request.json or {}
        framework = data.get('framework', existing.get('framework', 'STRIDE'))
        if framework not in FRAMEWORK_IDS:
            return {'error': f'Ungültiges Framework: {framework}'}, 400

        felder = data.get('felder', existing.get('felder', {}))
        risikowert, label, detail_text = berechne_risiko(framework, felder)

        risk = {
            'id': risk_id,
            'projekt_name': projekt_name,
            'nr': data.get('nr', existing.get('nr', 0)),
            'risk_name': data.get('risk_name', existing.get('risk_name', '')),
            'beschreibung': data.get('beschreibung', existing.get('beschreibung', '')),
            'framework': framework,
            'felder': felder,
            'risikowert': risikowert,
            'risiko_label': label,
            'detail_text': detail_text,
            'bewertung_text': data.get('bewertung_text', existing.get('bewertung_text', '')),
            'prompt_text': data.get('prompt_text', existing.get('prompt_text', '')),
        }
        db_save_risiko(DB_PATH, risk)
        return _serialize_risiko(risk), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.delete('/projekte/<projekt_name>/risiken/<int:risk_id>')
@jwt_required()
def delete_risiko(projekt_name: str, risk_id: int):
    """Risiko löschen."""
    try:
        db_delete_risiko(DB_PATH, risk_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.patch('/projekte/<projekt_name>/risiken/<int:risk_id>/resolve')
@jwt_required()
def resolve_risiko(projekt_name: str, risk_id: int):
    """Risiko als gelöst/wiedereröffnet markieren."""
    try:
        data = request.json or {}
        resolved = bool(data.get('resolved', True))
        reason = data.get('reason', '') or data.get('resolved_reason', '')
        db_set_resolved(DB_PATH, risk_id, resolved=resolved, reason=reason)
        return {'updated': True, 'resolved': resolved, 'reason': reason}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Audit-Trail (rb_change_log)
# ============================================================

@rb_bp.get('/projekte/<projekt_name>/audit')
@jwt_required()
def get_audit(projekt_name: str):
    """Audit-Trail (Changelog) eines Projekts."""
    try:
        limit = min(int(request.args.get('limit', 200)), 1000)
        offset = int(request.args.get('offset', 0))

        con = sqlite3.connect(str(DB_PATH))
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rb_change_log'")
        if not cur.fetchone():
            con.close()
            return {'events': [], 'total': 0}, 200

        cur.execute('SELECT COUNT(*) AS c FROM rb_change_log WHERE projekt_name=?', (projekt_name,))
        total = cur.fetchone()['c']

        cur.execute(
            'SELECT * FROM rb_change_log WHERE projekt_name=? ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (projekt_name, limit, offset),
        )
        events = []
        for row in cur.fetchall():
            ev = dict(row)
            for k in ('before_json', 'after_json'):
                if ev.get(k):
                    try:
                        ev[k.replace('_json', '')] = json.loads(ev[k])
                    except Exception:
                        pass
            events.append(ev)
        con.close()
        return {'events': events, 'total': total, 'limit': limit, 'offset': offset}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Einzelne Risiko-Aktionen: Prompt, JSON-Parse, Ollama, Re-Assessment
# ============================================================

def _find_risk(projekt_name: str, risk_id: int) -> Dict[str, Any] | None:
    """Helper: einzelnes Risiko aus DB laden."""
    risiken = load_risiken(DB_PATH, projekt_name)
    return next((r for r in risiken if r.get('id') == risk_id), None)


@rb_bp.get('/projekte/<projekt_name>/risiken/<int:risk_id>/prompt')
@jwt_required()
def get_risk_prompt(projekt_name: str, risk_id: int):
    """Generiert ChatGPT-Prompt für ein einzelnes Risiko (Erstbewertung)."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        existing = _find_risk(projekt_name, risk_id)
        if not existing:
            return {'error': 'Risiko nicht gefunden'}, 404

        from risikobewertung.prompts import build_prompt
        risk = dict(existing)
        risk['projekt_name'] = projekt_name
        risk['framework'] = risk.get('framework') or projekt.get('framework', 'STRIDE')
        prompt = build_prompt(risk)
        return {'prompt': prompt, 'risk_id': risk_id, 'framework': risk['framework']}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte/<projekt_name>/risiken/<int:risk_id>/parse-response')
@jwt_required()
def parse_response(projekt_name: str, risk_id: int):
    """Parst eine ChatGPT-JSON-Antwort und übernimmt sie ins Risiko."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        existing = _find_risk(projekt_name, risk_id)
        if not existing:
            return {'error': 'Risiko nicht gefunden'}, 404

        data = request.json or {}
        raw = data.get('raw') or data.get('antwort') or data.get('response')
        if not raw:
            return {'error': 'Feld "raw" mit der ChatGPT-Antwort ist Pflicht'}, 400
        apply = bool(data.get('apply', False))

        from risikobewertung.prompts import parse_json_antwort
        parsed = parse_json_antwort(raw)

        framework = existing.get('framework') or projekt.get('framework', 'STRIDE')
        felder = parsed.get('felder', {}) or existing.get('felder', {})
        risikowert, label, detail_text = berechne_risiko(framework, felder)

        result = {
            'parsed': parsed,
            'felder': felder,
            'risikowert': risikowert,
            'risiko_label': label,
            'detail_text': detail_text,
            'bewertung_text': parsed.get('bewertung', ''),
        }

        if apply:
            risk = dict(existing)
            risk['projekt_name'] = projekt_name
            risk['framework'] = framework
            risk['felder'] = felder
            risk['risikowert'] = risikowert
            risk['risiko_label'] = label
            risk['detail_text'] = detail_text
            risk['bewertung_text'] = parsed.get('bewertung', '') or existing.get('bewertung_text', '')
            risk['prompt_text'] = raw
            db_save_risiko(DB_PATH, risk)
            result['saved'] = True

        return result, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte/<projekt_name>/risiken/<int:risk_id>/ollama/stream')
@jwt_required()
def ollama_stream(projekt_name: str, risk_id: int):
    """Streaming-Ollama-Bewertung als Server-Sent-Events für Live-Status im UI.

    Events:
      - status   : {message} — Hinweis ("Verbinde…", "Streame Antwort…")
      - chunk    : {text} — Roh-Chunk vom Generator
      - progress : {bytes} — kumulative Bytes
      - done     : {ok, felder?, risikowert?, …, error?} — Endresultat
    """
    from flask import Response, stream_with_context

    @stream_with_context
    def _gen():
        import json as _json
        import time as _time
        from risikobewertung.prompts import generate_llm_with_meta
        from shared.ollama_config import get_ollama_config

        def _ev(name, data):
            return f'event: {name}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n'

        try:
            yield _ev('phase', {'phase': 'prepare', 'message': 'Lade Risiko + Konfiguration …'})
            projekt = load_projekt(DB_PATH, projekt_name)
            if not projekt:
                yield _ev('done', {'ok': False, 'error': 'Projekt nicht gefunden'})
                return
            existing = _find_risk(projekt_name, risk_id)
            if not existing:
                yield _ev('done', {'ok': False, 'error': 'Risiko nicht gefunden'})
                return

            oc = get_ollama_config()
            if not oc.model:
                yield _ev('done', {'ok': False, 'error': 'Kein Ollama-Modell konfiguriert'})
                return

            yield _ev('phase', {
                'phase': 'connect',
                'message': f'Verbinde mit Ollama ({oc.base_url}) — Modell {oc.model}',
                'ollama_url': oc.base_url,
                'ollama_model': oc.model,
            })

            framework = existing.get('framework') or projekt.get('framework', 'STRIDE')
            risk = dict(existing)
            risk['projekt_name'] = projekt_name
            risk['framework'] = framework

            yield _ev('phase', {
                'phase': 'generate',
                'message': 'Modell wird geladen / generiert Antwort …',
            })

            chunks = []
            total = 0
            first_token_at = None
            t0 = _time.monotonic()
            done_stats = {}
            try:
                for ev in generate_llm_with_meta(
                    risk=risk, base_url=oc.base_url, model=oc.model, timeout_s=oc.timeout_s,
                ):
                    kind = ev.get('kind')
                    if kind == 'chunk':
                        if first_token_at is None:
                            first_token_at = _time.monotonic() - t0
                            yield _ev('phase', {
                                'phase': 'streaming',
                                'message': f'Antwort kommt (erste Tokens nach {first_token_at:.1f}s)',
                                'first_token_s': round(first_token_at, 1),
                            })
                        text = ev['text']
                        chunks.append(text)
                        total += len(text)
                        yield _ev('chunk', {'text': text})
                    elif kind == 'stats':
                        yield _ev('progress', {
                            'bytes': total,
                            'tokens': ev.get('tokens', 0),
                            'elapsed_s': ev.get('elapsed_s', 0),
                            't_per_s': ev.get('t_per_s', 0),
                        })
                    elif kind == 'done':
                        done_stats = ev
            except Exception as e:
                yield _ev('done', {
                    'ok': False,
                    'error': f'{type(e).__name__}: {e}',
                    'ollama_url': oc.base_url,
                    'ollama_model': oc.model,
                })
                return

            yield _ev('phase', {
                'phase': 'parse',
                'message': 'Generierung abgeschlossen, parse JSON …',
                **{k: done_stats.get(k) for k in ('total_tokens', 'elapsed_s', 'eval_count', 'load_duration_s') if k in done_stats},
            })

            full_text = ''.join(chunks)
            try:
                parsed = _json.loads(full_text) if full_text.strip() else {}
            except _json.JSONDecodeError as je:
                yield _ev('done', {
                    'ok': False,
                    'error': f'JSON-Parse: {je}',
                    'raw_preview': full_text[:400],
                })
                return

            yield _ev('phase', {'phase': 'save', 'message': 'Bewertung wird gespeichert …'})

            felder = parsed.get('felder', risk.get('felder', {}))
            risikowert, label, detail_text = berechne_risiko(framework, felder)
            risk['felder'] = felder
            risk['risikowert'] = risikowert
            risk['risiko_label'] = label
            risk['detail_text'] = detail_text
            risk['bewertung_text'] = parsed.get('bewertung', existing.get('bewertung_text', ''))
            db_save_risiko(DB_PATH, risk)

            yield _ev('done', {
                'ok': True,
                'felder': felder,
                'risikowert': risikowert,
                'risiko_label': label,
                'detail_text': detail_text,
                'bewertung_text': risk['bewertung_text'],
                'bytes': total,
                'total_tokens': done_stats.get('total_tokens', 0),
                'elapsed_s': done_stats.get('elapsed_s', 0),
                'load_duration_s': done_stats.get('load_duration_s', 0),
                'eval_count': done_stats.get('eval_count', 0),
                'first_token_s': round(first_token_at, 1) if first_token_at else 0,
            })
        except Exception as e:
            yield _ev('done', {'ok': False, 'error': f'{type(e).__name__}: {e}'})

    return Response(_gen(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
    })


@rb_bp.post('/projekte/<projekt_name>/risiken/<int:risk_id>/ollama')
@jwt_required()
def ollama_single(projekt_name: str, risk_id: int):
    """Synchroner Ollama-Aufruf für ein einzelnes Risiko."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        existing = _find_risk(projekt_name, risk_id)
        if not existing:
            return {'error': 'Risiko nicht gefunden'}, 404

        from risikobewertung.prompts import generate_llm
        from shared.ollama_config import get_ollama_config

        oc = get_ollama_config()
        if not oc.model:
            return {'error': 'Kein Ollama-Modell konfiguriert (weder ENV OLLAMA_DEFAULT_MODEL noch ai_compliance_suite.config.json).'}, 400

        framework = existing.get('framework') or projekt.get('framework', 'STRIDE')
        risk = dict(existing)
        risk['projekt_name'] = projekt_name
        risk['framework'] = framework

        # generate_llm() ist ein Stream-Generator — Chunks sammeln + JSON parsen
        current_app.logger.info('Ollama single-call: model=%s url=%s timeout=%ds risk_id=%s',
                                oc.model, oc.base_url, oc.timeout_s, risk_id)
        try:
            full_text = ''.join(generate_llm(
                risk=risk, base_url=oc.base_url, model=oc.model, timeout_s=oc.timeout_s,
            ))
        except Exception as e:
            current_app.logger.exception('Ollama generate_llm fehlgeschlagen')
            return {
                'error': f'Ollama-Aufruf fehlgeschlagen: {type(e).__name__}: {e}',
                'ollama_source': oc.source,
                'ollama_url': oc.base_url,
                'ollama_model': oc.model,
            }, 502
        current_app.logger.info('Ollama-Antwort: %d Zeichen', len(full_text))
        try:
            parsed = json.loads(full_text) if full_text.strip() else {}
        except json.JSONDecodeError as je:
            current_app.logger.warning('Ollama-JSON-Parse-Fehler: %s', je)
            return {
                'error': f'Ollama-Antwort konnte nicht als JSON gelesen werden: {je}',
                'raw_preview': full_text[:300],
                'ollama_url': oc.base_url,
                'ollama_model': oc.model,
            }, 502
        felder = parsed.get('felder', risk.get('felder', {}))
        risikowert, label, detail_text = berechne_risiko(framework, felder)

        # Persist
        risk['felder'] = felder
        risk['risikowert'] = risikowert
        risk['risiko_label'] = label
        risk['detail_text'] = detail_text
        risk['bewertung_text'] = parsed.get('bewertung', existing.get('bewertung_text', ''))
        db_save_risiko(DB_PATH, risk)

        return {
            'ok': True,
            'felder': felder,
            'risikowert': risikowert,
            'risiko_label': label,
            'detail_text': detail_text,
            'bewertung_text': risk['bewertung_text'],
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte/<projekt_name>/risiken/<int:risk_id>/re-assessment/stream')
@jwt_required()
def re_assessment_stream(projekt_name: str, risk_id: int):
    """Streaming-Neubewertung mit Issue-Kontext und KI-API (Ollama oder Cloud).

    Wie `ollama/stream`, aber nutzt build_re_assessment_prompt mit issue_context.
    Body: { "issue_context": "..." }
    """
    from flask import Response, stream_with_context

    data = request.get_json(silent=True) or {}
    issue_context = str(data.get('issue_context') or '').strip()

    @stream_with_context
    def _gen():
        import json as _json
        from risikobewertung.prompts import build_re_assessment_prompt, generate_llm
        from shared.ollama_config import get_ollama_config

        def _ev(name, payload):
            return f'event: {name}\ndata: {_json.dumps(payload, ensure_ascii=False)}\n\n'

        try:
            projekt = load_projekt(DB_PATH, projekt_name)
            if not projekt:
                yield _ev('done', {'ok': False, 'error': 'Projekt nicht gefunden'})
                return
            existing = _find_risk(projekt_name, risk_id)
            if not existing:
                yield _ev('done', {'ok': False, 'error': 'Risiko nicht gefunden'})
                return
            if not issue_context:
                yield _ev('done', {'ok': False, 'error': 'issue_context fehlt'})
                return

            oc = get_ollama_config()
            if not oc.model:
                yield _ev('done', {'ok': False, 'error': 'Kein KI-Modell konfiguriert'})
                return

            framework = existing.get('framework') or projekt.get('framework', 'STRIDE')
            risk = dict(existing)
            risk['projekt_name'] = projekt_name
            risk['framework'] = framework

            yield _ev('status', {'message': f'Erzeuge Neubewertungs-Prompt für {oc.model} …'})
            # Custom-Prompt mit Issue-Kontext erzeugen
            prompt_text = build_re_assessment_prompt(risk, issue_context)

            yield _ev('status', {'message': f'Sende an Ollama {oc.base_url} …'})

            # Wir nutzen generate_llm aber mit dem RE-ASSESSMENT-Prompt.
            # generate_llm baut den Prompt selbst → wir hijacken via prompt-override
            # durch direkten urlopen-Call.
            import json as _j
            import urllib.request as _ur
            import urllib.error as _ue

            req = _ur.Request(
                oc.base_url.rstrip('/') + '/api/generate',
                data=_j.dumps({
                    'model': oc.model,
                    'prompt': prompt_text,
                    'stream': True,
                    'format': 'json',
                    'options': {'temperature': 0.2},
                }).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )

            chunks = []
            total = 0
            try:
                with _ur.urlopen(req, timeout=oc.timeout_s) as resp:
                    for raw_line in resp:
                        line = raw_line.decode('utf-8', errors='replace').strip()
                        if not line:
                            continue
                        try:
                            obj = _j.loads(line)
                        except Exception:
                            continue
                        chunk = obj.get('response', '')
                        if chunk:
                            chunks.append(chunk)
                            total += len(chunk)
                            yield _ev('chunk', {'text': chunk})
                            yield _ev('progress', {'bytes': total})
                        if obj.get('done'):
                            break
            except _ue.HTTPError as e:
                yield _ev('done', {'ok': False,
                                    'error': f'HTTP {e.code}: {e.reason}',
                                    'ollama_url': oc.base_url, 'ollama_model': oc.model})
                return
            except OSError as e:
                yield _ev('done', {'ok': False,
                                    'error': f'Ollama nicht erreichbar: {e}',
                                    'ollama_url': oc.base_url, 'ollama_model': oc.model})
                return

            full_text = ''.join(chunks)
            try:
                parsed = _json.loads(full_text) if full_text.strip() else {}
            except _json.JSONDecodeError as je:
                yield _ev('done', {'ok': False,
                                    'error': f'JSON-Parse: {je}',
                                    'raw_preview': full_text[:400]})
                return

            yield _ev('status', {'message': 'Speichere Neubewertung …'})
            felder = parsed.get('felder', risk.get('felder', {}))
            risikowert, label, detail_text = berechne_risiko(framework, felder)
            risk['felder'] = felder
            risk['risikowert'] = risikowert
            risk['risiko_label'] = label
            risk['detail_text'] = detail_text
            # Anhängen statt überschreiben — Audit-Trail
            new_bewertung = parsed.get('bewertung', '')
            old_bewertung = (existing.get('bewertung_text') or '').strip()
            risk['bewertung_text'] = (
                f"## Neubewertung mit Issue-Feedback\n\n{new_bewertung}"
                + (f"\n\n---\n\n## Ursprüngliche Bewertung\n\n{old_bewertung}" if old_bewertung else '')
            )
            db_save_risiko(DB_PATH, risk)

            yield _ev('done', {
                'ok': True,
                'felder': felder,
                'risikowert': risikowert,
                'risiko_label': label,
                'detail_text': detail_text,
                'bewertung_text': risk['bewertung_text'],
                'risiko_veraenderung': parsed.get('risiko_veraenderung', ''),
            })
        except Exception as e:
            yield _ev('done', {'ok': False, 'error': f'{type(e).__name__}: {e}'})

    return Response(_gen(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
    })


@rb_bp.post('/projekte/<projekt_name>/risiken/<int:risk_id>/re-assessment-prompt')
@jwt_required()
def re_assessment_prompt(projekt_name: str, risk_id: int):
    """Generiert Neubewertungs-Prompt mit Issue-Kontext."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        existing = _find_risk(projekt_name, risk_id)
        if not existing:
            return {'error': 'Risiko nicht gefunden'}, 404

        data = request.json or {}
        issue_context = data.get('issue_context', '').strip()
        if not issue_context:
            return {'error': 'Feld "issue_context" ist Pflicht (Issue-Body, Kommentare oder Feedback-Text)'}, 400

        from risikobewertung.prompts import build_re_assessment_prompt
        risk = dict(existing)
        risk['projekt_name'] = projekt_name
        risk['framework'] = risk.get('framework') or projekt.get('framework', 'STRIDE')
        prompt = build_re_assessment_prompt(risk, issue_context)
        return {'prompt': prompt, 'risk_id': risk_id, 'mode': 'reassessment'}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte/<projekt_name>/risiken/<int:risk_id>/import-issue')
@jwt_required()
def import_issue_text(projekt_name: str, risk_id: int):
    """Issue-Text/Feedback in bewertung_text einfügen (Rückspielen aus Issue)."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        existing = _find_risk(projekt_name, risk_id)
        if not existing:
            return {'error': 'Risiko nicht gefunden'}, 404

        data = request.json or {}
        issue_context = data.get('issue_context', '').strip()
        if not issue_context:
            return {'error': 'Feld "issue_context" ist Pflicht'}, 400

        current = existing.get('bewertung_text', '') or ''
        if current:
            combined = f"## Feedback aus GitHub/GitLab Review\n\n{issue_context}\n\n---\n\n## Ursprüngliche Bewertung\n\n{current}"
        else:
            combined = f"## Feedback aus GitHub/GitLab Review\n\n{issue_context}"

        risk = dict(existing)
        risk['projekt_name'] = projekt_name
        risk['bewertung_text'] = combined
        db_save_risiko(DB_PATH, risk)
        return {'ok': True, 'bewertung_text': combined}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# Backwards-compat: flacher /risikobewertung Endpoint (für KundenView)
# ============================================================

@rb_bp.get('')
@jwt_required()
def list_all_risiken():
    """Alle Risiken über alle Projekte (flach)."""
    try:
        results = []
        for projekt_name in list_projekte(DB_PATH):
            for risiko in load_risiken(DB_PATH, projekt_name):
                risiko['projekt_name'] = projekt_name
                results.append(_serialize_risiko(risiko))
        return results, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('')
@jwt_required()
def create_risiko_flat():
    """Backwards-compat: flacher POST mit projekt im Body."""
    data = request.json or {}
    projekt_name = data.get('projekt') or data.get('projekt_name')
    if not projekt_name:
        return {'error': 'Feld "projekt" oder "projekt_name" ist Pflicht'}, 400
    if not load_projekt(DB_PATH, projekt_name):
        save_projekt(DB_PATH, name=projekt_name, framework=data.get('framework', 'STRIDE'))

    try:
        framework = data.get('framework') or load_projekt(DB_PATH, projekt_name).get('framework', 'STRIDE')
        felder = data.get('felder', {})
        if not felder and 'wert' in data:
            wert = int(data['wert'])
            felder = {'wert': wert}
            risikowert = wert
            label = 'Kritisch' if wert >= 4 else 'Hoch' if wert >= 3 else 'Mittel'
            detail_text = f'Direkter Wert: {wert}'
        else:
            risikowert, label, detail_text = berechne_risiko(framework, felder)

        risk = {
            'projekt_name': projekt_name,
            'nr': _next_nr(projekt_name),
            'risk_name': data.get('name', '') or data.get('risk_name', ''),
            'beschreibung': data.get('beschreibung', ''),
            'kategorie': data.get('kategorie', ''),
            'framework': framework,
            'felder': felder,
            'risikowert': risikowert,
            'risiko_label': label,
            'detail_text': detail_text,
        }
        new_id = db_save_risiko(DB_PATH, risk)
        risk['id'] = new_id
        return _serialize_risiko(risk), 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.delete('/<int:risk_id>')
@jwt_required()
def delete_risiko_flat(risk_id: int):
    """Backwards-compat: flacher DELETE per Risiko-ID."""
    try:
        db_delete_risiko(DB_PATH, risk_id)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# F2e — Reports (PDF / DOCX / Excel / JSON / Markdown)
# ============================================================

import tempfile

from server.api._tmp import workspace_tmpdir
from flask import send_file


@rb_bp.get('/projekte/<projekt_name>/report')
@jwt_required()
def export_report(projekt_name: str):
    """Report-Export: format=pdf|docx|xlsx|json|md."""
    fmt = (request.args.get('format') or 'pdf').lower()
    if fmt not in {'pdf', 'docx', 'xlsx', 'json', 'md'}:
        return {'error': f'Unbekanntes Format: {fmt}. Erlaubt: pdf|docx|xlsx|json|md'}, 400

    projekt = load_projekt(DB_PATH, projekt_name)
    if not projekt:
        return {'error': 'Projekt nicht gefunden'}, 404

    # Risiken laden
    risiken = load_risiken(DB_PATH, projekt_name)
    framework = projekt.get('framework', 'STRIDE')
    scope_label = projekt.get('beschreibung') or framework

    out_dir = workspace_tmpdir('rb_report_')

    try:
        if fmt == 'docx':
            from risikobewertung.report_export import export_report_docx
            path = export_report_docx(
                out_dir=out_dir,
                projekt_name=projekt_name,
                projekt_beschreibung=projekt.get('beschreibung', ''),
                framework=framework,
                scope_label=scope_label,
                risks=risiken,
                include_recommendations=True,
            )
            return send_file(str(path), as_attachment=True, download_name=path.name)
        elif fmt == 'pdf':
            from risikobewertung.report_export import export_report_pdf
            path = export_report_pdf(
                out_dir=out_dir,
                projekt_name=projekt_name,
                projekt_beschreibung=projekt.get('beschreibung', ''),
                framework=framework,
                scope_label=scope_label,
                risks=risiken,
                include_recommendations=True,
            )
            return send_file(str(path), as_attachment=True, download_name=path.name)
        elif fmt == 'xlsx':
            from risikobewertung.io_xlsx import export_risiken
            xlsx_path = out_dir / f'{projekt_name}_risiken.xlsx'
            export_risiken(risks=risiken, out_path=xlsx_path, projekt_name=projekt_name, framework=framework)
            return send_file(str(xlsx_path), as_attachment=True, download_name=xlsx_path.name)
        elif fmt in ('json', 'md'):
            from risikobewertung.risk_export import export_risk_json_md
            json_path, md_path = export_risk_json_md(
                out_dir=out_dir,
                projekt_name=projekt_name,
                framework=framework,
                scope_label=scope_label,
                risks=risiken,
            )
            send_path = json_path if fmt == 'json' else md_path
            return send_file(str(send_path), as_attachment=True, download_name=send_path.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


# ============================================================
# F2d — Massen-Bewertung (Ollama + ChatGPT JSON)
# ============================================================

@rb_bp.post('/projekte/<projekt_name>/mass-prompt')
@jwt_required()
def mass_prompt(projekt_name: str):
    """Generiert Prompts für offene Risiken (für ChatGPT-JSON-Modus)."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        from risikobewertung.prompts import build_prompt

        data = request.json or {}
        only_open = data.get('only_open', True)
        risk_ids = data.get('risk_ids')  # Optional: spezifische IDs

        risiken = load_risiken(DB_PATH, projekt_name)
        if only_open:
            risiken = [r for r in risiken if not r.get('is_resolved')]
        if risk_ids:
            risk_ids_set = set(risk_ids)
            risiken = [r for r in risiken if r.get('id') in risk_ids_set]

        prompts = []
        for r in risiken:
            r_with_proj = dict(r)
            r_with_proj['projekt_name'] = projekt_name
            r_with_proj['framework'] = projekt.get('framework', 'STRIDE')
            try:
                prompts.append({
                    'risk_id': r.get('id'),
                    'risk_name': r.get('risk_name', ''),
                    'prompt': build_prompt(r_with_proj),
                })
            except Exception as e:
                prompts.append({'risk_id': r.get('id'), 'risk_name': r.get('risk_name', ''), 'error': str(e)})

        return {'prompts': prompts, 'count': len(prompts)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte/<projekt_name>/mass-apply')
@jwt_required()
def mass_apply(projekt_name: str):
    """Übernimmt JSON-Antworten (z.B. von ChatGPT) für mehrere Risiken."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        from risikobewertung.prompts import parse_json_antwort

        data = request.json or {}
        responses = data.get('responses') or []
        if not isinstance(responses, list):
            return {'error': 'responses muss eine Liste sein'}, 400

        risiken = {r.get('id'): r for r in load_risiken(DB_PATH, projekt_name)}
        applied = []
        errors = []

        for resp in responses:
            risk_id = resp.get('risk_id')
            raw = resp.get('raw') or resp.get('antwort') or resp.get('response')
            if not risk_id or not raw:
                errors.append({'risk_id': risk_id, 'error': 'risk_id + raw erforderlich'})
                continue

            existing = risiken.get(risk_id)
            if not existing:
                errors.append({'risk_id': risk_id, 'error': 'Risiko nicht gefunden'})
                continue

            try:
                parsed = parse_json_antwort(raw)
                # Felder + Bewertung übernehmen
                felder = parsed.get('felder', existing.get('felder', {}))
                framework = projekt.get('framework', 'STRIDE')
                risikowert, label, detail_text = berechne_risiko(framework, felder)

                risk = dict(existing)
                risk['felder'] = felder
                risk['risikowert'] = risikowert
                risk['risiko_label'] = label
                risk['detail_text'] = detail_text
                risk['bewertung_text'] = parsed.get('bewertung', existing.get('bewertung_text', ''))
                risk['prompt_text'] = raw
                risk['projekt_name'] = projekt_name
                db_save_risiko(DB_PATH, risk)
                applied.append({'risk_id': risk_id, 'risikowert': risikowert, 'risiko_label': label})
            except Exception as e:
                errors.append({'risk_id': risk_id, 'error': str(e)})

        return {'applied': applied, 'errors': errors, 'applied_count': len(applied)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte/<projekt_name>/mass-ollama')
@jwt_required()
def mass_ollama(projekt_name: str):
    """Synchron: ruft Ollama auf, bewertet alle offenen Risiken automatisch."""
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        from risikobewertung.prompts import generate_llm
        from shared.ollama_config import get_ollama_config

        oc = get_ollama_config()
        if not oc.model:
            return {'error': 'Kein Ollama-Modell konfiguriert (weder ENV OLLAMA_DEFAULT_MODEL noch Config).'}, 400

        data = request.json or {}
        risk_ids = data.get('risk_ids')
        risiken = load_risiken(DB_PATH, projekt_name)
        if risk_ids:
            ids_set = set(risk_ids)
            risiken = [r for r in risiken if r.get('id') in ids_set]

        framework = projekt.get('framework', 'STRIDE')
        results = []
        for r in risiken:
            r_with_proj = dict(r)
            r_with_proj['projekt_name'] = projekt_name
            r_with_proj['framework'] = framework
            try:
                full_text = ''.join(generate_llm(
                    risk=r_with_proj, base_url=oc.base_url, model=oc.model, timeout_s=oc.timeout_s,
                ))
                parsed = json.loads(full_text) if full_text.strip() else {}
                felder = parsed.get('felder', r.get('felder', {}))
                risikowert, label, detail_text = berechne_risiko(framework, felder)

                risk = dict(r)
                risk['felder'] = felder
                risk['risikowert'] = risikowert
                risk['risiko_label'] = label
                risk['detail_text'] = detail_text
                risk['bewertung_text'] = parsed.get('bewertung', r.get('bewertung_text', ''))
                risk['projekt_name'] = projekt_name
                db_save_risiko(DB_PATH, risk)
                results.append({'risk_id': r.get('id'), 'risikowert': risikowert, 'risiko_label': label, 'ok': True})
            except Exception as e:
                results.append({'risk_id': r.get('id'), 'ok': False, 'error': str(e)})

        return {'results': results, 'total': len(results)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte/<projekt_name>/risiken/import')
@jwt_required()
def import_risiken_endpoint(projekt_name: str):
    """Excel-Risiken importieren (multipart/form-data, Feld 'file').
    Nutzt das Framework des Ziel-Projekts.
    """
    import shutil
    projekt = load_projekt(DB_PATH, projekt_name)
    if not projekt:
        return {'error': 'Projekt nicht gefunden'}, 404

    f = request.files.get('file')
    if not f or not f.filename:
        return {'error': 'Datei-Feld "file" fehlt'}, 400
    if not f.filename.lower().endswith('.xlsx'):
        return {'error': 'Nur .xlsx wird unterstützt'}, 400

    framework = projekt.get('framework') or 'STRIDE'
    tmp_dir = workspace_tmpdir('rb_import_')
    try:
        tmp_path = tmp_dir / 'upload.xlsx'
        f.save(str(tmp_path))
        from risikobewertung.io_xlsx import import_risiken
        risks = import_risiken(tmp_path, framework=framework)
        if risks:
            bulk_insert_risiken(DB_PATH, projekt_name, risks)
        return {'imported': len(risks), 'framework': framework}, 200
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# Risiken-Assistent (Discovery / Wizard)
# ============================================================

# Schutzziele (Standard-Set, identisch zum Desktop)
SCHUTZZIELE = [
    {'key': 'A', 'en': 'Availability',    'de': 'Verfügbarkeit',                'farbe': '#1565c0'},
    {'key': 'C', 'en': 'Confidentiality', 'de': 'Vertraulichkeit',              'farbe': '#4a148c'},
    {'key': 'I', 'en': 'Integrity',       'de': 'Integrität',                   'farbe': '#bf360c'},
    {'key': 'N', 'en': 'Non-repudiation', 'de': 'Nichtabstreitbarkeit',         'farbe': '#2e7d32'},
    {'key': 'S', 'en': 'Safety',          'de': 'Sicherheit / Personenschutz',  'farbe': '#e65100'},
    {'key': 'P', 'en': 'Privacy',         'de': 'Datenschutz / Privacy',        'farbe': '#37474f'},
]


@rb_bp.get('/assistent/schutzziele')
@jwt_required()
def assistent_schutzziele():
    """Liste der 6 Standard-Schutzziele für den Assistenten."""
    return SCHUTZZIELE, 200


@rb_bp.post('/projekte/<projekt_name>/risiken/discovery-prompt')
@jwt_required()
def assistent_discovery_prompt(projekt_name: str):
    """Schritt 5 des Risiken-Assistenten: ChatGPT-Prompt zum Risiko-Discovery.

    Body: {
      anwendung: 'System/App-Name',
      risikobereich: 'Komponente/Bereich',
      schutzziele: ['A','C','I'],
      beschreibung: '...',
      n_risiken: 10,
      anhang_texte: ['...'] (optional, Auszüge aus hochgeladenen Dokumenten),
      repo_context: '...' (optional)
    }
    """
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404

        data = request.json or {}
        from risikobewertung.prompts import build_discovery_prompt
        prompt = build_discovery_prompt(
            anwendung=data.get('anwendung', '') or '',
            risikobereich=data.get('risikobereich', '') or '',
            schutzziele=data.get('schutzziele') or [],
            beschreibung=data.get('beschreibung', '') or '',
            anhang_texte=data.get('anhang_texte') or [],
            framework=projekt.get('framework', 'STRIDE'),
            n_risiken=int(data.get('n_risiken', 10)),
            repo_context=data.get('repo_context', '') or '',
        )
        return {
            'prompt': prompt,
            'framework': projekt.get('framework'),
            'n_risiken': int(data.get('n_risiken', 10)),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte/<projekt_name>/risiken/discovery-import')
@jwt_required()
def assistent_discovery_import(projekt_name: str):
    """Schritt 6: ChatGPT-JSON-Antwort parsen → Vorschau zurück (kein DB-Write)."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return {'error': 'Projekt nicht gefunden'}, 404

        data = request.json or {}
        raw = data.get('raw') or ''
        if not raw:
            return {'error': 'Feld "raw" mit der ChatGPT-Antwort ist Pflicht'}, 400

        from risikobewertung.prompts import parse_discovery_antwort
        try:
            risks = parse_discovery_antwort(raw)
        except ValueError as e:
            return {'error': f'Parse-Fehler: {e}'}, 400

        return {'count': len(risks), 'risks': risks}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500


@rb_bp.post('/projekte/<projekt_name>/risiken/discovery-apply')
@jwt_required()
def assistent_discovery_apply(projekt_name: str):
    """Schritt 6 final: ausgewählte Risiken in DB speichern.

    Body: { risks: [{risk_name, beschreibung}, ...] }
    """
    try:
        projekt = load_projekt(DB_PATH, projekt_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404

        data = request.json or {}
        risks = data.get('risks') or []
        if not isinstance(risks, list) or not risks:
            return {'error': 'Liste "risks" mit mindestens einem Eintrag erforderlich'}, 400

        framework = projekt.get('framework', 'STRIDE')
        # Build rows kompatibel mit bulk_insert_risiken
        rows = []
        for r in risks:
            name = (r.get('risk_name') or r.get('name') or '').strip()
            if not name:
                continue
            rows.append({
                'risikoname': name,
                'name': name,
                'beschreibung': (r.get('beschreibung') or '').strip(),
                'framework': framework,
            })
        if not rows:
            return {'error': 'Keine Risiken mit gültigem Namen'}, 400

        n = bulk_insert_risiken(DB_PATH, projekt_name, rows)
        current_app.logger.info('RB Assistent-Apply: projekt=%r imported=%d', projekt_name, n)
        return {'imported': n}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': str(e), 'type': type(e).__name__}, 500
