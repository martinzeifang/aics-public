"""Tests für die Massenanlage von Issues im AI-Act-Modul (#795).

Die VCS-API (vcs.github_issues.create_issue) wird gemockt (kein Netz),
getestet wird die Endpoint-Logik: Repo-Pflicht, Verknüpfung in linked_issues,
Bulk-Summary, skip_linked.
"""

import pytest

BASE = '/api/aiact'
PROJ = 'pytest-issues-795'


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

    class _Obj:
        def __init__(self, number, url):
            self.number = number
            self.url = url

    def fake(*, repo, title, body):
        state['n'] += 1
        num = state['n']
        return _Obj(num, f'https://github.com/{repo}/issues/{num}')

    monkeypatch.setattr('vcs.github_issues.create_issue', fake)
    return state


def _clear_links(projekt):
    """Stale linked_issues entfernen — die persistente Test-DB recycelt
    Requirement-IDs nach Löschung, sonst greift skip_linked fälschlich."""
    import sqlite3
    from server.api.aiact import DB_PATH
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
                    json={'name': PROJ, 'produkt': 'Test-KI'})
    assert r.status_code in (200, 201), r.get_json()
    yield PROJ
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)


def test_bulk_creates_and_skips_on_second_run(client, auth_headers, projekt):
    # Repo-Pflicht
    bad = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers,
                      json={'only_gaps': False})
    assert bad.status_code == 400

    # unbekanntes Projekt → 404
    nf = client.post(f'{BASE}/projekte/__nicht_da__/issues/bulk', headers=auth_headers,
                     json={'repo': 'owner/repo', 'only_gaps': False})
    assert nf.status_code == 404

    # Erster Lauf: alle Anforderungen → created > 0
    r = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers,
                    json={'repo': 'owner/repo', 'only_gaps': False})
    assert r.status_code == 200, r.get_json()
    s = r.get_json()['summary']
    assert s['created'] > 0
    assert s['failed'] == 0

    # Zweiter Lauf: alle bereits verknüpft → übersprungen
    r2 = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers,
                     json={'repo': 'owner/repo', 'only_gaps': False})
    assert r2.status_code == 200, r2.get_json()
    s2 = r2.get_json()['summary']
    assert s2['created'] == 0
    assert s2['skipped'] == s['created']
