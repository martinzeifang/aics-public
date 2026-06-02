"""Tests für projektweiten Issue-Sync (#788).

Unit: shared.issue_sync.sync_project_links persistiert den Live-Status.
Endpoint: POST /projekte/<name>/issues/sync (Beispiel risikobewertung).
"""

import sqlite3
import uuid
from pathlib import Path

import pytest

import shared.issue_sync as isync
from shared.issue_links import add_link


@pytest.fixture
def repo_db():
    """Temp-SQLite INNERHALB des Repos (connect_sqlite erlaubt nur Workspace-Pfade)."""
    d = Path('data/db'); d.mkdir(parents=True, exist_ok=True)
    p = d / f'_test788_{uuid.uuid4().hex}.sqlite'
    yield p
    for suf in ('', '-wal', '-shm'):
        Path(str(p) + suf).unlink(missing_ok=True)


def _fake_gh(*, repo, number):
    return isync.SyncedIssue('github', repo, number, None,
                             f'https://github.com/{repo}/issues/{number}',
                             'GH-neu', 'closed', 'completed', [])


def _fake_gl(*, base_url, token_env, project, iid):
    return isync.SyncedIssue('gitlab', project, None, iid,
                             f'{base_url}/{project}/-/issues/{iid}',
                             'GL-neu', 'closed', '', [])


def test_sync_project_links_persists(repo_db, monkeypatch):
    db = repo_db
    add_link(db, projekt_name='P', object_kind='risk', object_id='1', provider='github',
             repo='o/r', url='https://github.com/o/r/issues/5', issue_number=5,
             title='Alt', state='open')
    add_link(db, projekt_name='P', object_kind='requirement', object_id='2', provider='gitlab',
             repo='g/p', url='https://gitlab.com/g/p/-/issues/7', issue_iid=7,
             title='Alt2', state='opened')
    monkeypatch.setattr(isync, 'sync_github_issue', _fake_gh)
    monkeypatch.setattr(isync, 'sync_gitlab_issue', _fake_gl)

    res = isync.sync_project_links(db, 'P')
    assert res['synced'] == 2 and res['errors'] == 0 and res['total'] == 2

    con = sqlite3.connect(str(db)); con.row_factory = sqlite3.Row
    rows = {r['object_id']: r for r in con.execute(
        "SELECT * FROM linked_issues WHERE projekt_name='P'")}
    con.close()
    assert rows['1']['state'] == 'closed' and rows['1']['title'] == 'GH-neu'
    assert rows['2']['state'] == 'closed' and rows['2']['title'] == 'GL-neu'


def test_sync_collects_errors(repo_db, monkeypatch):
    db = repo_db
    add_link(db, projekt_name='P', object_kind='risk', object_id='1', provider='github',
             repo='o/r', url='https://github.com/o/r/issues/5', issue_number=5, state='open')

    def _boom(**kw):
        raise RuntimeError('API down')
    monkeypatch.setattr(isync, 'sync_github_issue', _boom)
    res = isync.sync_project_links(db, 'P')
    assert res['errors'] == 1 and res['synced'] == 0
    assert res['items'][0]['ok'] is False and 'API down' in res['items'][0]['error']


class TestSyncEndpoint:
    @pytest.fixture(autouse=True)
    def _full_license(self):
        from server import license_state
        cur = license_state._current
        prev = (cur.state, list(cur.modules))
        cur.state, cur.modules = 'ok', ['*']
        yield
        cur.state, cur.modules = prev[0], prev[1]

    def test_project_sync_endpoint(self, client, auth_headers, monkeypatch):
        BASE = '/api/risikobewertung'
        name = 'pytest-sync-788'
        from server.api.risikobewertung import DB_PATH
        client.delete(f'{BASE}/projekte/{name}', headers=auth_headers)
        client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': name, 'framework': 'STRIDE'})
        try:
            # verlinktes Issue direkt eintragen
            add_link(DB_PATH, projekt_name=name, object_kind='risk', object_id='1',
                     provider='github', repo='o/r',
                     url='https://github.com/o/r/issues/9', issue_number=9,
                     title='X', state='open')
            monkeypatch.setattr(isync, 'sync_github_issue', _fake_gh)
            r = client.post(f'{BASE}/projekte/{name}/issues/sync', headers=auth_headers)
            assert r.status_code == 200, r.get_json()
            assert r.get_json()['synced'] >= 1
            # persistiert?
            con = sqlite3.connect(str(DB_PATH)); con.row_factory = sqlite3.Row
            row = con.execute("SELECT state FROM linked_issues WHERE projekt_name=? AND object_id='1'",
                              (name,)).fetchone()
            con.close()
            assert row['state'] == 'closed'
        finally:
            con = sqlite3.connect(str(DB_PATH))
            con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (name,)); con.commit(); con.close()
            client.delete(f'{BASE}/projekte/{name}', headers=auth_headers)
