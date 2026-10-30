"""Tests für Issue-Feedback in die Bewertung (#830).

- Shared-Helper: build_combined_issue_text, collect_issue_feedback,
  merge_feedback_into_comment (idempotent), group_links_by_object.
- Aussagekräftige Issue-Titel mit AICS-Präfix (CRA/NIS2/AI-Act/RB).
- Endpoint: CRA per-Anforderung import-issue (issue_context) und
  projektweiter Import (gemockter Issue-Abruf) schreiben in den Kommentar.
"""

import sqlite3

import pytest


# ── Shared-Helper ──────────────────────────────────────────────────────────

def test_build_combined_issue_text():
    from shared.issue_sync import build_combined_issue_text
    details = {
        'title': 'Fix logging', 'state': 'closed', 'state_reason': 'completed',
        'body': 'Body-Text', 'comments': [{'author': 'alice', 'body': 'erledigt'}],
    }
    out = build_combined_issue_text(details)
    assert '# Fix logging' in out
    assert '**Status:** closed (completed)' in out
    assert 'Body-Text' in out
    assert '**alice:** erledigt' in out


def test_merge_feedback_idempotent():
    from shared.issue_feedback import merge_feedback_into_comment
    base = 'Ursprüngliche Notiz'
    once = merge_feedback_into_comment(base, 'FB-1')
    assert base in once and 'FB-1' in once
    # Erneuter Import ersetzt den Block statt ihn zu duplizieren
    twice = merge_feedback_into_comment(once, 'FB-2')
    assert twice.count('Issue-Feedback') == 1
    assert 'FB-2' in twice and 'FB-1' not in twice
    assert base in twice


def test_collect_issue_feedback(monkeypatch):
    import shared.issue_feedback as fb

    def _fake(url, *, gitlab_token_env='GITLAB_TOKEN'):
        return {'combined': f'INHALT::{url}'}
    monkeypatch.setattr(fb, 'fetch_issue_content_by_url', _fake)

    class L:
        def __init__(self, url): self.url = url
    text, sources = fb.collect_issue_feedback([L('u1'), L('u2')])
    assert 'INHALT::u1' in text and 'INHALT::u2' in text
    assert all(s['ok'] for s in sources)


def test_collect_issue_feedback_handles_errors(monkeypatch):
    import shared.issue_feedback as fb

    def _boom(url, *, gitlab_token_env='GITLAB_TOKEN'):
        raise RuntimeError('rate limit')
    monkeypatch.setattr(fb, 'fetch_issue_content_by_url', _boom)

    class L:
        url = 'https://github.com/o/r/issues/1'
    text, sources = fb.collect_issue_feedback([L()])
    assert text == ''
    assert sources[0]['ok'] is False and 'rate limit' in sources[0]['error']


def test_group_links_by_object():
    from shared.issue_feedback import group_links_by_object

    class L:
        def __init__(self, oid): self.object_id = oid
    groups = group_links_by_object([L('A'), L('B'), L('A')])
    assert set(groups) == {'A', 'B'} and len(groups['A']) == 2


# ── AICS-Titel ─────────────────────────────────────────────────────────────

def test_issue_titles_have_aics_prefix():
    from server.api.cra import _cra_issue_content
    from server.api.nis2 import _nis2_issue_content
    from server.api.aiact import _aiact_issue_content

    req = {'titel': 'Sichere Defaults', 'kapitel': 'AI1', 'ref': 'Annex I'}
    t_cra, _ = _cra_issue_content('AI1-01', req, {})
    t_nis2, _ = _nis2_issue_content('NIS-01', req, {})
    t_ai, _ = _aiact_issue_content('AIA-01', req, {})
    assert t_cra == 'AICS · CRA-Gap [AI1-01]: Sichere Defaults'
    assert t_nis2 == 'AICS · NIS2-Gap [NIS-01]: Sichere Defaults'
    assert t_ai == 'AICS · AI-Act-Gap [AIA-01]: Sichere Defaults'


def test_rb_risk_issue_title_aics_prefix():
    from server.api.risikobewertung import _risk_issue_content
    title, _ = _risk_issue_content('P', {'nr': 7, 'risk_name': 'Prompt Injection',
                                         'risiko_label': 'Hoch'})
    assert title == 'AICS · Risiko [7]: Prompt Injection (Hoch)'


# ── CRA-Endpoints ──────────────────────────────────────────────────────────

class TestCraImport:
    BASE = '/api/cra'
    PROJ = 'pytest-feedback-830'

    @pytest.fixture(autouse=True)
    def _full_license(self):
        from server import license_state
        cur = license_state._current
        prev = (cur.state, list(cur.modules))
        cur.state, cur.modules = 'ok', ['*']
        yield
        cur.state, cur.modules = prev[0], prev[1]

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.cra import DB_PATH
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        self._clear_links(DB_PATH)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'unternehmen': 'U'})
        yield DB_PATH
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        self._clear_links(DB_PATH)

    def _clear_links(self, db_path):
        try:
            con = sqlite3.connect(str(db_path))
            con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (self.PROJ,))
            con.commit(); con.close()
        except Exception:
            pass

    def _first_req_id(self):
        from cra.requirements import CRA_ANFORDERUNGEN
        return CRA_ANFORDERUNGEN[0]['id']

    def test_import_issue_context_into_comment(self, client, auth_headers, projekt):
        rid = self._first_req_id()
        r = client.post(
            f'{self.BASE}/projekte/{self.PROJ}/anforderungen/{rid}/import-issue',
            headers=auth_headers, json={'issue_context': 'Maßnahme umgesetzt: TLS aktiv.'})
        assert r.status_code == 200, r.get_json()
        assert 'TLS aktiv' in r.get_json()['kommentar']
        # persistiert?
        g = client.get(f'{self.BASE}/projekte/{self.PROJ}/anforderungen', headers=auth_headers)
        anf = {a['id']: a for a in g.get_json()}
        assert 'TLS aktiv' in (anf[rid].get('kommentar') or anf[rid].get('bewertung', {}).get('kommentar', ''))

    def test_import_issue_no_links_400(self, client, auth_headers, projekt):
        rid = self._first_req_id()
        r = client.post(
            f'{self.BASE}/projekte/{self.PROJ}/anforderungen/{rid}/import-issue',
            headers=auth_headers, json={})
        assert r.status_code == 400

    def test_project_import_pulls_linked_issue(self, client, auth_headers, projekt, monkeypatch):
        import shared.issue_feedback as fb
        from shared.issue_links import add_link
        db_path = projekt
        rid = self._first_req_id()
        add_link(db_path, projekt_name=self.PROJ, object_kind='requirement',
                 object_id=rid, provider='github', repo='o/r',
                 url='https://github.com/o/r/issues/3', issue_number=3,
                 title='X', state='closed')
        monkeypatch.setattr(fb, 'fetch_issue_content_by_url',
                            lambda url, **kw: {'combined': 'Issue sagt: behoben.'})
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/import',
                        headers=auth_headers, json={})
        assert r.status_code == 200, r.get_json()
        d = r.get_json()
        assert d['imported'] == 1 and d['total'] == 1
        g = client.get(f'{self.BASE}/projekte/{self.PROJ}/anforderungen', headers=auth_headers)
        anf = {a['id']: a for a in g.get_json()}
        kom = anf[rid].get('kommentar') or anf[rid].get('bewertung', {}).get('kommentar', '')
        assert 'behoben' in kom
