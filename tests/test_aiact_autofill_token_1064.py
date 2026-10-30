"""#1064/#1065 — AI-Act-Autofill & Repo-Scan reichen den GitHub-Token durch
(HTTP-API statt gh-CLI → containertauglich)."""
import ai_act.repo_alignment as ra
import ai_act.system_doku_autofill as sda
import ai_act.data_governance_autofill as dga
import ai_act.repo_autoanswer as raa


def test_gh_api_json_uses_http_api_with_token(monkeypatch):
    seen = {}

    def fake_github_api(path, token=None):
        seen['path'] = path
        seen['token'] = token
        return {'type': 'file', 'encoding': 'base64', 'size': 3, 'content': 'YWJj'}  # "abc"

    monkeypatch.setattr('vcs.repo_reader._github_api', fake_github_api)
    out = ra.github_fetch_text('owner', 'repo', 'README.md', token='TOK123')
    assert out == 'abc'
    assert seen['token'] == 'TOK123'
    assert 'owner/repo' in seen['path']


def test_path_exists_passes_token(monkeypatch):
    seen = {}
    monkeypatch.setattr(ra, '_gh_api_json',
                        lambda path, token=None: seen.update(token=token) or {'type': 'file'})
    ok, _info = ra.github_path_exists('o', 'r', 'docs', token='T-EXIST')
    assert ok is True
    assert seen['token'] == 'T-EXIST'


def test_suggest_system_doku_threads_token(monkeypatch):
    seen = {}
    monkeypatch.setattr(sda, 'github_fetch_text',
                        lambda owner, name, path, branch, token=None: seen.update(token=token) or '')
    sda.suggest_system_doku('owner/repo', token='SD-TOK')
    assert seen['token'] == 'SD-TOK'


def test_suggest_data_governance_threads_token(monkeypatch):
    seen = {}
    monkeypatch.setattr(dga, 'github_fetch_text',
                        lambda owner, name, path, branch, token=None: seen.update(token=token) or '')
    dga.suggest_data_governance('owner/repo', token='DG-TOK')
    assert seen['token'] == 'DG-TOK'


def test_repo_signals_threads_token(monkeypatch):
    seen = {}
    monkeypatch.setattr(raa, 'github_path_exists',
                        lambda owner, name, path, branch, token=None: seen.update(token=token) or (False, None))
    raa.suggest_from_repo_signals(repo='owner/repo', token='RS-TOK')
    assert seen['token'] == 'RS-TOK'
