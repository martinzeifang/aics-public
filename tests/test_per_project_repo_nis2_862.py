"""Tests für pro-Projekt-Repository-Konfiguration im NIS2-Modul (#862).

repo-config Roundtrip, Token-Verschlüsselung (nie ausgeliefert), Partial-Update
bewahrt Token, Bulk-Issue-Erstellung nutzt das gespeicherte Repo ohne `repo`
im Request. Netz (VCS-Create) wird gemockt.
"""

import pytest

BASE = '/api/nis2'
PROJ = 'pytest-repo-nis2-862'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _clear_links(projekt):
    import sqlite3 as _s
    from server.api.nis2 import DB_PATH
    try:
        con = _s.connect(str(DB_PATH))
        con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (projekt,))
        con.commit(); con.close()
    except Exception:
        pass


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)
    client.post(f'{BASE}/projekte', headers=auth_headers,
                json={'name': PROJ, 'unternehmen': 'TestOrg'})
    yield PROJ
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)


class TestRepoConfig:
    def test_put_get_roundtrip(self, client, auth_headers, projekt):
        r = client.put(f'{BASE}/projekte/{projekt}/repo-config', headers=auth_headers,
                       json={'vcs_publish': {'provider': 'github', 'repo': 'owner/repo'}})
        assert r.status_code == 200, r.get_json()
        body = r.get_json()['vcs_publish']
        assert body['repo'] == 'owner/repo' and body['provider'] == 'github'
        g = client.get(f'{BASE}/projekte/{projekt}/repo-config', headers=auth_headers)
        assert g.get_json()['vcs_publish']['repo'] == 'owner/repo'

    def test_token_encrypted_never_served(self, client, auth_headers, projekt):
        secret = 'dummy-pat-not-real-862'
        r = client.put(f'{BASE}/projekte/{projekt}/repo-config', headers=auth_headers,
                       json={'vcs_publish': {'provider': 'github', 'repo': 'o/r', 'token': secret}})
        body = r.get_json()['vcs_publish']
        assert body.get('has_token') is True
        assert 'token' not in body and 'token_enc' not in body
        g = client.get(f'{BASE}/projekte/{projekt}/repo-config', headers=auth_headers).get_json()
        assert g['vcs_publish'].get('has_token') is True
        assert 'token_enc' not in g['vcs_publish']
        from server.api.nis2 import DB_PATH
        from nis2.db import load_projekt
        from shared.vcs_repo_config import vcs_token
        meta = (load_projekt(DB_PATH, projekt) or {}).get('meta') or {}
        vcs = meta.get('vcs_publish') or {}
        assert vcs.get('token_enc') and secret not in str(vcs.get('token_enc'))
        assert vcs_token(vcs) == secret

    def test_partial_update_preserves_token(self, client, auth_headers, projekt):
        client.put(f'{BASE}/projekte/{projekt}/repo-config', headers=auth_headers,
                   json={'vcs_publish': {'provider': 'github', 'repo': 'o/r', 'token': 'dummy-keep-862'}})
        client.put(f'{BASE}/projekte/{projekt}/repo-config', headers=auth_headers,
                   json={'vcs_publish': {'provider': 'github', 'repo': 'o/r2'}})
        from server.api.nis2 import DB_PATH
        from nis2.db import load_projekt
        from shared.vcs_repo_config import vcs_token
        vcs = ((load_projekt(DB_PATH, projekt) or {}).get('meta') or {}).get('vcs_publish') or {}
        assert vcs_token(vcs) == 'dummy-keep-862' and vcs.get('repo') == 'o/r2'


class TestBulkUsesStoredRepo:
    def test_bulk_without_repo_uses_stored(self, client, auth_headers, projekt, monkeypatch):
        client.put(f'{BASE}/projekte/{projekt}/repo-config', headers=auth_headers,
                   json={'vcs_publish': {'provider': 'github', 'repo': 'owner/stored-repo'}})

        import vcs.github_issues as ghi
        seen = {}
        class _CI:
            def __init__(self, n):
                self.url = f'https://github.com/owner/stored-repo/issues/{n}'
                self.number = n
                self.iid = None
        def _fake(repo, title, body):
            seen['repo'] = repo
            return _CI(1)
        monkeypatch.setattr(ghi, 'create_issue', _fake)

        # Bulk OHNE repo im Request → nutzt gespeichertes Repo
        r = client.post(f'{BASE}/projekte/{projekt}/issues/bulk', headers=auth_headers, json={})
        assert r.status_code == 200, r.get_json()
        assert seen.get('repo') == 'owner/stored-repo'

    def test_bulk_without_repo_no_config_400(self, client, auth_headers, projekt):
        r = client.post(f'{BASE}/projekte/{projekt}/issues/bulk', headers=auth_headers, json={})
        assert r.status_code == 400
