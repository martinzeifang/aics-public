"""Tests für Massenanlage von Issues aus CRA-Anforderungen (#795).

Die VCS-API (vcs.github_issues.create_issue) wird gemockt (kein Netz),
getestet wird die Endpoint-Logik: Repo-Pflicht, Bulk-Summary, skip_linked.
"""

import sqlite3

import pytest

BASE = '/api/cra'
PROJ = 'pytest-bulk-issues-795'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture(autouse=True)
def _fake_vcs(monkeypatch):
    """vcs.github_issues.create_issue durch einen Zähler-Fake ersetzen (kein Netz)."""
    state = {'n': 100}

    class _FakeIssue:
        def __init__(self, number, url):
            self.number = number
            self.url = url

    def _fake(*, repo, title, body):
        state['n'] += 1
        num = state['n']
        return _FakeIssue(num, f'https://github.com/{repo}/issues/{num}')

    monkeypatch.setattr('vcs.github_issues.create_issue', _fake)
    return state


def _clear_links(projekt):
    """Stale linked_issues entfernen — die persistente Test-DB recycelt
    Anforderungs-IDs, sonst greift skip_linked fälschlich."""
    from server.api.cra import DB_PATH
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (projekt,))
        con.commit()
        con.close()
    except Exception:
        pass


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': PROJ, 'produkt': 'TestProdukt'})
    assert r.status_code in (200, 201), r.get_json()
    yield PROJ
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)


class TestBulkIssues:
    def test_repo_required_400(self, client, auth_headers, projekt):
        r = client.post(f'{BASE}/projekte/{projekt}/issues/bulk', headers=auth_headers,
                        json={'only_gaps': False})
        assert r.status_code == 400, r.get_json()

    def test_project_not_found_404(self, client, auth_headers):
        r = client.post(f'{BASE}/projekte/__does_not_exist__/issues/bulk',
                        headers=auth_headers, json={'repo': 'owner/repo'})
        assert r.status_code == 404

    def test_bulk_creates_then_skips(self, client, auth_headers, projekt):
        # erster Lauf: legt Issues für alle Anforderungen an
        r = client.post(f'{BASE}/projekte/{projekt}/issues/bulk', headers=auth_headers,
                        json={'repo': 'owner/repo', 'only_gaps': False})
        assert r.status_code == 200, r.get_json()
        s = r.get_json()['summary']
        assert s['created'] > 0 and s['failed'] == 0

        created_first = s['created']

        # zweiter Lauf: alle bereits verknüpft → übersprungen
        r2 = client.post(f'{BASE}/projekte/{projekt}/issues/bulk', headers=auth_headers,
                         json={'repo': 'owner/repo', 'only_gaps': False})
        s2 = r2.get_json()['summary']
        assert s2['created'] == 0
        assert s2['skipped'] == created_first
