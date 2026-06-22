"""Cross-Modul Issue-Übersicht — alle verlinkten Issues über alle Module.

Aggregiert über cra.sqlite, nis2.sqlite, aiact.sqlite, risikobewertung.sqlite.
Nutzt shared/issue_links für Datenzugriff.
"""

from contextlib import closing

from flask import current_app, Blueprint, request
from flask_jwt_extended import jwt_required
from pathlib import Path
from typing import Any, Dict, List

from server.models.permission import require_permission

issues_bp = Blueprint('issues', __name__, url_prefix='/api/issues')


# Module → DB-Pfad-Mapping
MODULE_DBS = {
    'cra': Path('data/db/cra.sqlite'),
    'nis2': Path('data/db/nis2.sqlite'),
    'aiact': Path('data/db/ai_act.sqlite'),
    'risikobewertung': Path('data/db/risikobewertung.sqlite'),
}


def _serialize_link(li: Any, module: str) -> Dict[str, Any]:
    return {
        'id': getattr(li, 'id', None),
        'module': module,
        'projekt_name': getattr(li, 'projekt_name', ''),
        'object_kind': getattr(li, 'object_kind', ''),
        'object_id': getattr(li, 'object_id', ''),
        'provider': getattr(li, 'provider', ''),
        'repo': getattr(li, 'repo', ''),
        'url': getattr(li, 'url', ''),
        'issue_number': getattr(li, 'issue_number', None),
        'issue_iid': getattr(li, 'issue_iid', None),
        'title': getattr(li, 'title', ''),
        'state': getattr(li, 'state', ''),
        'state_reason': getattr(li, 'state_reason', ''),
    }


@issues_bp.get('/all')
@require_permission('admin:audit')
def list_all_issues():
    """Alle Issue-Verknüpfungen über alle Module."""
    try:
        from shared.issue_links import ensure_tables, list_links
        from shared import db as _sdb

        filter_module = request.args.get('module', '').lower()
        filter_state = request.args.get('state', '').lower()
        filter_projekt = request.args.get('projekt', '')

        result: List[Dict[str, Any]] = []

        for module, db_path in MODULE_DBS.items():
            if filter_module and filter_module != module:
                continue
            if not db_path.exists():
                continue

            try:
                ensure_tables(db_path)
                # Direkt SQL für Performance — list_links benötigt object_kind+object_id
                with closing(_sdb.connect(str(db_path))) as con:
                    cur = con.cursor()
                    # Tabelle gibts?
                    row = cur.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='linked_issues'"
                    ).fetchone()
                    if not row:
                        continue

                    where_parts: List[str] = []
                    params: List[Any] = []
                    if filter_state:
                        where_parts.append('state=?')
                        params.append(filter_state)
                    if filter_projekt:
                        where_parts.append('projekt_name=?')
                        params.append(filter_projekt)
                    where_sql = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''

                    rows = cur.execute(
                        f'SELECT * FROM linked_issues {where_sql} ORDER BY projekt_name, object_id LIMIT 500',
                        params,
                    ).fetchall()

                for r in rows:
                    result.append({
                        'id': r['id'],
                        'module': module,
                        'projekt_name': r['projekt_name'],
                        'object_kind': r['object_kind'],
                        'object_id': r['object_id'],
                        'provider': r['provider'],
                        'repo': r['repo'] if 'repo' in r.keys() else '',
                        'url': r['url'],
                        'issue_number': r['issue_number'] if 'issue_number' in r.keys() else None,
                        'issue_iid': r['issue_iid'] if 'issue_iid' in r.keys() else None,
                        'title': r['title'] if 'title' in r.keys() else '',
                        'state': r['state'] if 'state' in r.keys() else '',
                        'state_reason': r['state_reason'] if 'state_reason' in r.keys() else '',
                    })
            except Exception:
                current_app.logger.warning(
                    'Issue-Aggregation für Modul %s übersprungen', module, exc_info=True)
                continue

        return {
            'issues': result,
            'count': len(result),
            'modules': list(MODULE_DBS.keys()),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@issues_bp.post('/sync-all')
@require_permission('admin:audit')
def sync_all_issues():
    """Synchronisiert alle GitHub-Issues über alle Module mit ihrem aktuellen Status."""
    try:
        from shared.issue_links import list_links, update_issue_state
        from shared.issue_sync import sync_github_issue
        from shared import db as _sdb

        synced = 0
        errors: List[Dict[str, Any]] = []

        for module, db_path in MODULE_DBS.items():
            if not db_path.exists():
                continue
            try:
                with closing(_sdb.connect(str(db_path))) as con:
                    row = con.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='linked_issues'"
                    ).fetchone()
                    if not row:
                        continue
                    rows = con.execute(
                        "SELECT id, repo, issue_number, title FROM linked_issues "
                        "WHERE provider='github' AND issue_number IS NOT NULL"
                    ).fetchall()

                for r in rows:
                    try:
                        s = sync_github_issue(repo=r['repo'], number=r['issue_number'])
                        update_issue_state(
                            db_path, link_id=r['id'],
                            state=s.state,
                            state_reason=s.state_reason or '',
                            title=s.title or r['title'],
                        )
                        synced += 1
                    except Exception as e:
                        errors.append({'module': module, 'id': r['id'], 'error': str(e)})
            except Exception as e:
                errors.append({'module': module, 'error': str(e)})

        return {'synced': synced, 'errors': errors}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@issues_bp.get('/stats')
@require_permission('admin:audit')
def issues_stats():
    """Statistiken: Anzahl pro Modul, pro Status, pro Provider."""
    try:
        from shared import db as _sdb

        stats = {
            'by_module': {},
            'by_state': {},
            'by_provider': {},
            'total': 0,
        }

        for module, db_path in MODULE_DBS.items():
            if not db_path.exists():
                continue
            try:
                with closing(_sdb.connect(str(db_path))) as con:
                    row = con.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='linked_issues'"
                    ).fetchone()
                    if not row:
                        continue

                    count = con.execute('SELECT COUNT(*) FROM linked_issues').fetchone()[0]
                    stats['by_module'][module] = count
                    stats['total'] += count

                    # row[0]/row[1] statt Tuple-Unpacking: DBRow ist dict-artig (#PG).
                    for row in con.execute(
                        "SELECT COALESCE(state, 'unknown') AS s, COUNT(*) FROM linked_issues GROUP BY state"
                    ).fetchall():
                        state, c = row[0], row[1]
                        stats['by_state'][state] = stats['by_state'].get(state, 0) + c

                    for row in con.execute(
                        "SELECT provider, COUNT(*) FROM linked_issues GROUP BY provider"
                    ).fetchall():
                        prov, c = row[0], row[1]
                        stats['by_provider'][prov] = stats['by_provider'].get(prov, 0) + c
            except Exception:
                current_app.logger.warning(
                    'Issue-Statistik für Modul %s übersprungen', module, exc_info=True)
                continue

        return stats, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)
