"""Tests für Risiko-Assistent Web-Parität (#763).

WP-1 #764 Repo-Anbindung · WP-2 #765 Anhänge · WP-3 #766 Doku-/Software-URLs.
Deckt Persistenz von vcs_publish/software, meta-Merge (kein Wipe),
repo-config/-context-Endpoints, Datei-Anhänge + Text-Extraktion,
SSRF-Ablehnung interner URLs und Discovery-Prompt-Anreicherung.
"""

import io

import pytest

BASE = '/api/risikobewertung'


@pytest.fixture(autouse=True)
def _full_license():
    """In CI gibt es keine Lizenz → Schreib-Endpoints würden mit 423 geblockt.
    Für diese Tests den License-State auf 'alle Module erlaubt' setzen."""
    from server import license_state
    cur = license_state._current
    prev_state, prev_mods = cur.state, list(cur.modules)
    cur.state = 'ok'
    cur.modules = ['*']
    yield
    cur.state, cur.modules = prev_state, prev_mods


@pytest.fixture
def projekt(client, auth_headers):
    """Legt ein Testprojekt an und räumt es danach wieder ab."""
    name = 'pytest-parity-projekt'
    client.delete(f'{BASE}/projekte/{name}', headers=auth_headers)
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': name, 'framework': 'STRIDE',
                          'beschreibung': 'Test'})
    assert r.status_code in (201, 409), r.get_json()
    yield name
    client.delete(f'{BASE}/projekte/{name}', headers=auth_headers)


class TestProjectMetaPersistence:
    def test_create_with_vcs_and_software(self, client, auth_headers):
        name = 'pytest-parity-create'
        client.delete(f'{BASE}/projekte/{name}', headers=auth_headers)
        try:
            r = client.post(f'{BASE}/projekte', headers=auth_headers, json={
                'name': name, 'framework': 'STRIDE',
                'vcs_publish': {'provider': 'github', 'repo': 'owner/repo'},
                'software': {'description': 'Mein Tool',
                             'doc_urls': ['https://example.com/doc']},
            })
            assert r.status_code == 201, r.get_json()
            body = r.get_json()
            assert body['vcs_publish']['repo'] == 'owner/repo'
            assert body['software']['description'] == 'Mein Tool'
            assert body['software']['doc_urls'] == ['https://example.com/doc']
        finally:
            client.delete(f'{BASE}/projekte/{name}', headers=auth_headers)

    def test_update_does_not_wipe_meta(self, client, auth_headers, projekt):
        # vcs setzen
        client.put(f'{BASE}/projekte/{projekt}', headers=auth_headers,
                   json={'vcs_publish': {'provider': 'github', 'repo': 'a/b'}})
        # unabhängiges Feld ändern, OHNE vcs/software mitzuschicken
        client.put(f'{BASE}/projekte/{projekt}', headers=auth_headers,
                   json={'beschreibung': 'geändert'})
        r = client.get(f'{BASE}/projekte/{projekt}', headers=auth_headers)
        body = r.get_json()
        assert body['beschreibung'] == 'geändert'
        assert body['vcs_publish'].get('repo') == 'a/b'  # nicht gewiped

    def test_vcs_field_allowlist(self, client, auth_headers, projekt):
        client.put(f'{BASE}/projekte/{projekt}', headers=auth_headers, json={
            'vcs_publish': {'repo': 'a/b', 'evil': 'x', 'token': 'secret'}})
        r = client.get(f'{BASE}/projekte/{projekt}/repo-config', headers=auth_headers)
        vcs = r.get_json()['vcs_publish']
        assert vcs.get('repo') == 'a/b'
        assert 'evil' not in vcs and 'token' not in vcs


class TestRepoConfigEndpoints:
    def test_repo_config_roundtrip(self, client, auth_headers, projekt):
        r = client.put(f'{BASE}/projekte/{projekt}/repo-config', headers=auth_headers,
                       json={'vcs_publish': {'provider': 'gitlab', 'repo': 'g/p',
                                             'token_env': 'GITLAB_TOKEN'}})
        assert r.status_code == 200
        r = client.get(f'{BASE}/projekte/{projekt}/repo-config', headers=auth_headers)
        vcs = r.get_json()['vcs_publish']
        assert vcs['provider'] == 'gitlab'
        assert vcs['token_env'] == 'GITLAB_TOKEN'

    def test_repo_context_no_repo_400(self, client, auth_headers, projekt):
        r = client.post(f'{BASE}/projekte/{projekt}/repo-context',
                        headers=auth_headers, json={})
        assert r.status_code == 400

    def test_repo_context_bad_format_400(self, client, auth_headers, projekt):
        r = client.post(f'{BASE}/projekte/{projekt}/repo-context',
                        headers=auth_headers, json={'repo': 'not a repo!!'})
        assert r.status_code == 400


class TestAttachments:
    def test_upload_list_text_delete(self, client, auth_headers, projekt):
        data = {'file': (io.BytesIO(b'Geheimer Risiko-Kontext aus Datei.'),
                         'kontext.txt')}
        r = client.post(f'{BASE}/projekte/{projekt}/attachments/file',
                        headers=auth_headers, data=data,
                        content_type='multipart/form-data')
        assert r.status_code == 201, r.get_json()
        doc_id = r.get_json()['id']

        r = client.get(f'{BASE}/projekte/{projekt}/attachments', headers=auth_headers)
        assert any(d['id'] == doc_id for d in r.get_json())

        r = client.get(f'{BASE}/projekte/{projekt}/attachments/texts',
                       headers=auth_headers)
        texts = r.get_json()['texts']
        assert any('Geheimer Risiko-Kontext' in t['text'] for t in texts)

        r = client.delete(f'{BASE}/projekte/{projekt}/attachments/{doc_id}',
                          headers=auth_headers)
        assert r.status_code == 200
        r = client.get(f'{BASE}/projekte/{projekt}/attachments', headers=auth_headers)
        assert not any(d['id'] == doc_id for d in r.get_json())

    def test_reject_disallowed_extension(self, client, auth_headers, projekt):
        data = {'file': (io.BytesIO(b'MZ...'), 'malware.exe')}
        r = client.post(f'{BASE}/projekte/{projekt}/attachments/file',
                        headers=auth_headers, data=data,
                        content_type='multipart/form-data')
        assert r.status_code == 400

    def test_attachment_url_ssrf_blocked(self, client, auth_headers, projekt):
        r = client.post(f'{BASE}/projekte/{projekt}/attachments/url',
                        headers=auth_headers,
                        json={'url': 'http://169.254.169.254/latest/'})
        assert r.status_code == 400


class TestDiscoveryPromptEnrichment:
    def test_use_attachments_includes_text(self, client, auth_headers, projekt):
        data = {'file': (io.BytesIO(b'Architektur: Microservice mit DB.'),
                         'arch.txt')}
        up = client.post(f'{BASE}/projekte/{projekt}/attachments/file',
                         headers=auth_headers, data=data,
                         content_type='multipart/form-data')
        assert up.status_code == 201

        r = client.post(f'{BASE}/projekte/{projekt}/risiken/discovery-prompt',
                        headers=auth_headers,
                        json={'anwendung': 'X', 'use_attachments': True,
                              'n_risiken': 5})
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body['anhang_texte_count'] >= 1
        assert 'Microservice' in body['prompt']

    def test_use_doc_urls_ssrf_is_skipped_gracefully(self, client, auth_headers, projekt):
        # interne Doku-URL → wird beim Abruf SSRF-sicher verworfen, kein Crash
        client.put(f'{BASE}/projekte/{projekt}', headers=auth_headers, json={
            'software': {'description': 'd',
                         'doc_urls': ['http://169.254.169.254/']}})
        r = client.post(f'{BASE}/projekte/{projekt}/risiken/discovery-prompt',
                        headers=auth_headers,
                        json={'anwendung': 'X', 'use_doc_urls': True, 'n_risiken': 5})
        assert r.status_code == 200
        assert r.get_json()['anhang_texte_count'] == 0
