"""Tests für die pro-Projekt-Repository-Konfiguration im AI-Act-Modul (#862).

Deckt ab:
- repo-config Roundtrip (GET/PUT)
- Token wird verschlüsselt abgelegt und NIE ausgeliefert (nur has_token-Flag)
- Partial-Update bewahrt einen bestehenden Token
- Bulk-Create nutzt das gespeicherte Repo OHNE `repo` im Request

vcs.github_issues.create_issue wird gemockt (kein Netz).
"""

import sqlite3

import pytest

BASE = '/api/aiact'
PROJ = 'pytest-repo-862'


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
    """vcs.github_issues.create_issue durch einen Zähler-Fake ersetzen (kein Netz).

    Signatur exakt wie die echte Funktion (repo/title/body), damit der Test die
    reale Aufruf-Schnittstelle abdeckt."""
    state = {'n': 100, 'repos': []}

    class _Obj:
        def __init__(self, number, url):
            self.number = number
            self.url = url
            self.iid = None

    def fake(*, repo, title, body):
        state['n'] += 1
        state['repos'].append(repo)
        num = state['n']
        return _Obj(num, f'https://github.com/{repo}/issues/{num}')

    monkeypatch.setattr('vcs.github_issues.create_issue', fake)
    return state


def _clear_links(projekt):
    """Stale linked_issues entfernen — die persistente Test-DB recycelt
    Requirement-IDs nach Löschung, sonst greift skip_linked fälschlich."""
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
                    json={'name': PROJ, 'organisation': 'Test-AG', 'produkt': 'Test-KI'})
    assert r.status_code in (200, 201), r.get_json()
    yield PROJ
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)


def test_repo_config_roundtrip(client, auth_headers, projekt):
    # Initial leer
    r0 = client.get(f'{BASE}/projekte/{PROJ}/repo-config', headers=auth_headers)
    assert r0.status_code == 200, r0.get_json()
    assert r0.get_json()['vcs_publish'].get('has_token') is False

    # Speichern (mit Token)
    put = client.put(f'{BASE}/projekte/{PROJ}/repo-config', headers=auth_headers,
                     json={'vcs_publish': {'provider': 'github', 'repo': 'owner/repo',
                                           'token': 'dummy-pat-not-real-862'}})
    assert put.status_code == 200, put.get_json()
    pub = put.get_json()['vcs_publish']
    assert pub['repo'] == 'owner/repo'
    assert pub['provider'] == 'github'
    assert pub['has_token'] is True
    # Token NIE im Response
    assert 'token' not in pub
    assert 'token_enc' not in pub

    # Erneut lesen → Repo persistiert, Token weiterhin nur als Flag
    r1 = client.get(f'{BASE}/projekte/{PROJ}/repo-config', headers=auth_headers)
    pub1 = r1.get_json()['vcs_publish']
    assert pub1['repo'] == 'owner/repo'
    assert pub1['has_token'] is True
    assert 'token' not in pub1 and 'token_enc' not in pub1


def test_token_encrypted_in_db_and_partial_update_preserves_it(client, auth_headers, projekt):
    from server.api.aiact import DB_PATH

    client.put(f'{BASE}/projekte/{PROJ}/repo-config', headers=auth_headers,
               json={'vcs_publish': {'provider': 'github', 'repo': 'owner/repo',
                                     'token': 'dummy-pat-not-real-862'}})

    # Token liegt verschlüsselt (token_enc) in der DB, NICHT im Klartext
    con = sqlite3.connect(str(DB_PATH))
    row = con.execute("SELECT meta_json FROM ai_act_projekte WHERE name=?", (PROJ,)).fetchone()
    con.close()
    meta_json = row[0]
    assert 'dummy-pat-not-real-862' not in meta_json
    assert 'token_enc' in meta_json

    # Partial-Update ohne Token → bestehender Token bleibt erhalten (has_token True)
    put = client.put(f'{BASE}/projekte/{PROJ}/repo-config', headers=auth_headers,
                     json={'vcs_publish': {'provider': 'github', 'repo': 'owner/other'}})
    assert put.status_code == 200, put.get_json()
    pub = put.get_json()['vcs_publish']
    assert pub['repo'] == 'owner/other'
    assert pub['has_token'] is True


def test_bulk_uses_saved_repo_without_repo_in_request(client, auth_headers, projekt, _fake_vcs):
    # Ohne gespeichertes Repo und ohne repo im Request → 400
    bad = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers,
                      json={'only_gaps': False})
    assert bad.status_code == 400

    # Repo speichern
    put = client.put(f'{BASE}/projekte/{PROJ}/repo-config', headers=auth_headers,
                     json={'vcs_publish': {'provider': 'github', 'repo': 'saved/repo'}})
    assert put.status_code == 200, put.get_json()

    # Bulk OHNE repo im Request → nutzt gespeichertes Repo
    r = client.post(f'{BASE}/projekte/{PROJ}/issues/bulk', headers=auth_headers,
                    json={'only_gaps': False})
    assert r.status_code == 200, r.get_json()
    s = r.get_json()['summary']
    assert s['created'] > 0
    assert s['failed'] == 0
    # Alle Issues wurden im gespeicherten Repo angelegt
    assert _fake_vcs['repos']
    assert all(repo == 'saved/repo' for repo in _fake_vcs['repos'])
