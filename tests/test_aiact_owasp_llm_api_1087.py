"""#1087 — OWASP-LLM-Register API: Status-Speichern, Auto-Detect, Wizard-Parse,
Issue-Link (object_kind='owasp_llm'). VCS + Repo-Scan werden gemockt (kein Netz)."""

import pytest

BASE = '/api/aiact'
PROJ = 'pytest-owasp-llm-1087'


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
    class _Obj:
        def __init__(self, number, url):
            self.number = number
            self.url = url

    def fake(*, repo, title, body):
        return _Obj(4242, f'https://github.com/{repo}/issues/4242')

    monkeypatch.setattr('vcs.github_issues.create_issue', fake)


def _clear_links(projekt):
    import sqlite3
    from server.api.aiact import DB_PATH
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (projekt,))
        con.execute("DELETE FROM aiact_owasp_llm_checks WHERE projekt_name=?", (projekt,))
        con.commit()
        con.close()
    except Exception:
        pass


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': PROJ, 'produkt': 'Test-LLM'})
    assert r.status_code in (200, 201), r.get_json()
    # Repo speichern (vcs_publish) damit Auto-Detect/Issue ohne Body-Repo läuft.
    client.put(f'{BASE}/projekte/{PROJ}/repo-config', headers=auth_headers,
               json={'vcs_publish': {'provider': 'github', 'repo': 'owner/repo'}})
    yield PROJ
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(PROJ)


def test_list_returns_all_ten_items(client, auth_headers, projekt):
    r = client.get(f'{BASE}/projekte/{PROJ}/owasp-llm', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    items = r.get_json()['items']
    assert len(items) == 10
    assert items[0]['id'] == 'LLM01'
    assert 'maps_to' in items[0]
    assert items[0]['status'] == 0


def test_save_status(client, auth_headers, projekt):
    r = client.post(f'{BASE}/projekte/{PROJ}/owasp-llm/LLM01', headers=auth_headers,
                    json={'status': 4, 'kommentar': 'Guards aktiv'})
    assert r.status_code == 200, r.get_json()
    lst = client.get(f'{BASE}/projekte/{PROJ}/owasp-llm', headers=auth_headers).get_json()
    by_id = {i['id']: i for i in lst['items']}
    assert by_id['LLM01']['status'] == 4
    assert by_id['LLM01']['kommentar'] == 'Guards aktiv'


def test_save_invalid_status(client, auth_headers, projekt):
    r = client.post(f'{BASE}/projekte/{PROJ}/owasp-llm/LLM01', headers=auth_headers,
                    json={'status': 99})
    assert r.status_code == 400


def test_save_unknown_item(client, auth_headers, projekt):
    r = client.post(f'{BASE}/projekte/{PROJ}/owasp-llm/LLM99', headers=auth_headers,
                    json={'status': 1})
    assert r.status_code == 404


def test_autodetect_applies_status(client, auth_headers, projekt, monkeypatch):
    from ai_act.owasp_llm_register import LlmDetectResult

    def fake_detect(*, repo, branch='', token=None):
        assert repo == 'owner/repo'  # aus vcs_publish aufgelöst
        return [LlmDetectResult('LLM08', True, 4, 'requirements.txt',
                                [{'url': 'u', 'path': 'requirements.txt'}])] + \
               [LlmDetectResult(f'LLM{n:02d}', False, 0, 'nichts', [])
                for n in range(1, 11) if n != 8]

    monkeypatch.setattr('ai_act.owasp_llm_register.autodetect_owasp_llm', fake_detect)

    r = client.post(f'{BASE}/projekte/{PROJ}/owasp-llm/autodetect', headers=auth_headers,
                    json={})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['applied'] == 1
    by_id = {x['id']: x for x in body['results']}
    assert by_id['LLM08']['status'] == 4
    # persistiert
    lst = client.get(f'{BASE}/projekte/{PROJ}/owasp-llm', headers=auth_headers).get_json()
    assert {i['id']: i for i in lst['items']}['LLM08']['status'] == 4


def test_autodetect_requires_repo(client, auth_headers):
    # Projekt ohne vcs_publish.repo
    proj = 'pytest-owasp-llm-norepo'
    client.delete(f'{BASE}/projekte/{proj}', headers=auth_headers)
    client.post(f'{BASE}/projekte', headers=auth_headers, json={'name': proj})
    try:
        r = client.post(f'{BASE}/projekte/{proj}/owasp-llm/autodetect',
                        headers=auth_headers, json={})
        assert r.status_code == 400
    finally:
        client.delete(f'{BASE}/projekte/{proj}', headers=auth_headers)


def test_wizard_prompt_and_parse(client, auth_headers, projekt):
    pr = client.get(f'{BASE}/projekte/{PROJ}/owasp-llm/wizard/prompt', headers=auth_headers)
    assert pr.status_code == 200
    assert 'LLM01' in pr.get_json()['prompt']

    raw = '```json\n{"items": [{"id": "LLM02", "status": 3, "kommentar": "ok"}]}\n```'
    r = client.post(f'{BASE}/projekte/{PROJ}/owasp-llm/wizard/parse', headers=auth_headers,
                    json={'response': raw, 'apply': True})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['count'] == 1
    lst = client.get(f'{BASE}/projekte/{PROJ}/owasp-llm', headers=auth_headers).get_json()
    assert {i['id']: i for i in lst['items']}['LLM02']['status'] == 3


def test_wizard_parse_garbage(client, auth_headers, projekt):
    r = client.post(f'{BASE}/projekte/{PROJ}/owasp-llm/wizard/parse', headers=auth_headers,
                    json={'response': 'kein json'})
    assert r.status_code == 400


def test_issue_create_and_unlink(client, auth_headers, projekt):
    r = client.post(f'{BASE}/projekte/{PROJ}/owasp-llm/LLM01/issues', headers=auth_headers,
                    json={})
    assert r.status_code == 201, r.get_json()
    assert r.get_json()['url'].endswith('/issues/4242')

    # Liste zeigt den Link
    issues = client.get(f'{BASE}/projekte/{PROJ}/owasp-llm/LLM01/issues',
                        headers=auth_headers).get_json()
    assert len(issues) == 1
    link_id = issues[0]['id']

    # Item-Liste enthält issues
    lst = client.get(f'{BASE}/projekte/{PROJ}/owasp-llm', headers=auth_headers).get_json()
    assert len({i['id']: i for i in lst['items']}['LLM01']['issues']) == 1

    # Unlink
    d = client.delete(f'{BASE}/projekte/{PROJ}/owasp-llm/issues/{link_id}',
                      headers=auth_headers)
    assert d.status_code == 200
    issues2 = client.get(f'{BASE}/projekte/{PROJ}/owasp-llm/LLM01/issues',
                         headers=auth_headers).get_json()
    assert issues2 == []


def test_issue_manual_link(client, auth_headers, projekt):
    r = client.post(f'{BASE}/projekte/{PROJ}/owasp-llm/LLM03/issues/link',
                    headers=auth_headers,
                    json={'url': 'https://github.com/owner/repo/issues/77'})
    assert r.status_code == 201, r.get_json()
    issues = client.get(f'{BASE}/projekte/{PROJ}/owasp-llm/LLM03/issues',
                        headers=auth_headers).get_json()
    assert issues[0]['issue_number'] == 77
    assert issues[0]['provider'] == 'github'
