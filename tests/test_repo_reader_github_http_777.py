"""Tests für #777: GitHub-Repo-Kontext über HTTP-API statt gh-CLI.

Stellt sicher, dass im Web/Container (ohne `gh`) der HTTP-Pfad genutzt wird
und dass gh-CLI-Fehler transparent auf HTTP zurückfallen.
"""

import base64
import io
import json

import pytest

import vcs.repo_reader as rr


def _fake_http(path):
    """Kanned GitHub-HTTP-API-Antworten je nach Pfad."""
    if path.endswith('/readme'):
        content = base64.b64encode(b'# Demo README\nInhalt').decode()
        return {'content': content}
    if '/git/trees/' in path:
        return {'tree': [
            {'type': 'blob', 'path': 'src/app.py'},
            {'type': 'blob', 'path': '.hidden'},   # wird gefiltert
            {'type': 'tree', 'path': 'src'},        # kein blob
        ]}
    # repos/{owner}/{repo}
    return {'description': 'Mein Tool', 'default_branch': 'main'}


def test_uses_http_when_gh_absent(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, 'which', lambda _n: None)  # gh nicht vorhanden
    monkeypatch.setattr(rr, '_github_http_api', _fake_http)

    ctx = rr.fetch_repo_context('owner/repo')
    assert ctx.provider == 'github'
    assert ctx.description == 'Mein Tool'
    assert 'Demo README' in ctx.readme
    assert 'src/app.py' in ctx.file_tree
    assert '.hidden' not in ctx.file_tree


def test_gh_failure_falls_back_to_http(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, 'which', lambda _n: '/usr/bin/gh')

    def _boom(_path):
        raise RuntimeError('gh not authenticated')
    monkeypatch.setattr(rr, '_gh_api', _boom)
    monkeypatch.setattr(rr, '_github_http_api', _fake_http)

    ctx = rr.fetch_repo_context('owner/repo')
    assert ctx.description == 'Mein Tool'
    assert 'src/app.py' in ctx.file_tree


def test_http_api_sets_headers_and_optional_token(monkeypatch):
    captured = {}

    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_urlopen(req, timeout=0):
        captured['url'] = req.full_url
        captured['headers'] = {k.lower(): v for k, v in req.header_items()}
        return _Resp(json.dumps({'ok': True}).encode())

    monkeypatch.setattr(rr.urllib.request, 'urlopen', _fake_urlopen)
    monkeypatch.setenv('GITHUB_TOKEN', 'tok-xyz')

    out = rr._github_http_api('repos/o/r')
    assert out == {'ok': True}
    assert captured['url'].startswith('https://api.github.com/repos/o/r')
    assert 'user-agent' in captured['headers']
    assert captured['headers'].get('Authorization'.lower()) == 'Bearer tok-xyz'


def test_http_api_without_token(monkeypatch):
    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_urlopen(req, timeout=0):
        assert not any(k.lower() == 'authorization' for k, _ in req.header_items())
        return _Resp(b'{}')

    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    monkeypatch.delenv('GH_TOKEN', raising=False)
    monkeypatch.setattr(rr.urllib.request, 'urlopen', _fake_urlopen)
    assert rr._github_http_api('repos/o/r') == {}
