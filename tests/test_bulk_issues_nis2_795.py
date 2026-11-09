"""Tests für die Massenanlage von Issues im NIS2-Modul (#795).

Die VCS-API wird gemockt (kein Netz). Getestet wird die Endpoint-Logik:
Repo-Pflicht, Verknüpfung in linked_issues, Bulk-Summary, skip_linked.
"""

import pytest

BASE = '/api/nis2'
PROJ = 'pytest-issues-795'


@pytest.fixture(autouse=True)
def _full_license():
    # Schreibzugriffe auf NIS2 (lizenziert) liefern sonst 423 in CI.
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture(autouse=True)
def _fake_vcs(monkeypatch):
    """vcs.github_issues.create_issue durch einen Zähler-Fake ersetzen.

    Der Endpoint importiert create_issue erst zur Laufzeit, daher wirkt
    das Patchen der Quelle."""
    from vcs.github_issues import CreatedIssue
    state = {'n': 100}

    def _fake(*, repo, title, body):
        state['n'] += 1
        num = state['n']
        return CreatedIssue(number=num, url=f'https://github.com/{repo}/issues/{num}')

    monkeypatch.setattr('vcs.github_issues.create_issue', _fake)
    return state


def _clear_links(projekt):
    """Stale linked_issues entfernen — die persistente Test-DB recycelt
    Req-IDs/Projektnamen, sonst greift skip_linked fälschlich."""
    import sqlite3
    from server.api.nis2 import DB_PATH
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
    r = client.post(f'{BASE}/projekte', headers=auth_headers, json={'name': PROJ})
    assert r.status_code in (200, 201), r.get_json()
    yield PROJ
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)


class TestBulkIssues:
    def test_repo_required_400(self, client, auth_headers, projekt):
        r = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers,
                        json={'only_gaps': False})
        assert r.status_code == 400, r.get_json()

    def test_project_missing_404(self, client, auth_headers):
        r = client.post(f'{BASE}/projekte/does-not-exist-795/issues/bulk',
                        headers=auth_headers, json={'repo': 'owner/repo'})
        assert r.status_code == 404, r.get_json()

    def test_bulk_creates_then_skips_linked(self, client, auth_headers, projekt):
        # Erster Lauf: alle Anforderungen (only_gaps=False) → Issues anlegen.
        r = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers,
                        json={'repo': 'owner/repo', 'only_gaps': False})
        assert r.status_code == 200, r.get_json()
        s = r.get_json()['summary']
        assert s['created'] > 0, r.get_json()
        assert s['failed'] == 0
        first_created = s['created']

        # Zweiter Lauf: alle bereits verknüpft → übersprungen.
        r2 = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers,
                         json={'repo': 'owner/repo', 'only_gaps': False})
        assert r2.status_code == 200, r2.get_json()
        s2 = r2.get_json()['summary']
        assert s2['created'] == 0
        assert s2['skipped'] == first_created
