"""Tests für Issue-Erstellung aus Risiken (#786) — einzeln + Massenaktion.

Die eigentliche VCS-API wird gemockt (kein Netz), getestet wird die Endpoint-
Logik: Repo-Pflicht, Verknüpfung in linked_issues, Bulk-Summary, skip_linked.
"""

import pytest

BASE = '/api/risikobewertung'
PROJ = 'pytest-issues-786'


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
    """_create_repo_issue durch einen Zähler-Fake ersetzen (kein Netz)."""
    import server.api.risikobewertung as rb
    state = {'n': 100}

    def _fake(vcs, token, title, body):
        state['n'] += 1
        num = state['n']
        return ('github', 'owner/repo', num, None,
                f'https://github.com/owner/repo/issues/{num}')
    monkeypatch.setattr(rb, '_create_repo_issue', _fake)
    return state


def _clear_links(projekt):
    """Stale linked_issues entfernen — die persistente Test-DB recycelt
    Risiko-IDs nach Löschung, sonst greift skip_linked fälschlich."""
    import sqlite3
    from server.api.risikobewertung import DB_PATH
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (projekt,))
        con.commit(); con.close()
    except Exception:
        pass


@pytest.fixture
def projekt_mit_risiken(client, auth_headers):
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)
    client.post(f'{BASE}/projekte', headers=auth_headers,
                json={'name': PROJ, 'framework': 'STRIDE'})
    # Repo-Kontext setzen (Pflicht für Issue-Erstellung)
    client.put(f'{BASE}/projekte/{PROJ}/repo-config', headers=auth_headers,
               json={'vcs_publish': {'provider': 'github', 'repo': 'owner/repo'}})
    ids = []
    for i in range(3):
        r = client.post(f'{BASE}/projekte/{PROJ}/risiken', headers=auth_headers,
                        json={'risk_name': f'Risiko {i}', 'framework': 'STRIDE',
                              'beschreibung': f'Beschreibung {i}', 'felder': {}})
        assert r.status_code in (200, 201), r.get_json()
        ids.append(r.get_json()['id'])
    yield ids
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)


class TestSingleIssue:
    def test_create_issue_for_risk(self, client, auth_headers, projekt_mit_risiken):
        rid = projekt_mit_risiken[0]
        r = client.post(f'{BASE}/projekte/{PROJ}/risiken/{rid}/issue', headers=auth_headers)
        assert r.status_code == 201, r.get_json()
        body = r.get_json()
        assert body['url'].startswith('https://github.com/owner/repo/issues/')
        assert body['number'] >= 101 and body['provider'] == 'github'
        # als verknüpft gespeichert
        g = client.get(f'{BASE}/projekte/{PROJ}/risiken/{rid}/linked-issues', headers=auth_headers)
        assert g.get_json()['total'] >= 1

    def test_no_repo_configured_400(self, client, auth_headers):
        name = 'pytest-issues-norepo'
        client.delete(f'{BASE}/projekte/{name}', headers=auth_headers)
        client.post(f'{BASE}/projekte', headers=auth_headers, json={'name': name, 'framework': 'STRIDE'})
        try:
            r = client.post(f'{BASE}/projekte/{name}/risiken', headers=auth_headers,
                            json={'risk_name': 'R', 'framework': 'STRIDE', 'felder': {}})
            rid = r.get_json()['id']
            resp = client.post(f'{BASE}/projekte/{name}/risiken/{rid}/issue', headers=auth_headers)
            assert resp.status_code == 400
        finally:
            client.delete(f'{BASE}/projekte/{name}', headers=auth_headers)


class TestBulkIssues:
    def test_bulk_creates_for_all_open(self, client, auth_headers, projekt_mit_risiken):
        r = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers,
                        json={'only_open': True})
        assert r.status_code == 200, r.get_json()
        s = r.get_json()['summary']
        assert s['created'] == 3 and s['failed'] == 0

    def test_bulk_skips_already_linked(self, client, auth_headers, projekt_mit_risiken):
        # erster Lauf legt an
        client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers, json={})
        # zweiter Lauf: alle bereits verknüpft → übersprungen
        r2 = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers, json={})
        s = r2.get_json()['summary']
        assert s['created'] == 0 and s['skipped'] == 3

    def test_bulk_subset_via_risk_ids(self, client, auth_headers, projekt_mit_risiken):
        subset = projekt_mit_risiken[:2]
        r = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers,
                        json={'risk_ids': subset})
        assert r.get_json()['summary']['created'] == 2
