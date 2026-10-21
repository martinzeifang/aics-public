"""#1523/#1524 — Per-Item Issue-Import (score-/antwort-neutral) + Reassess-Stream
für AI-Act OWASP-LLM und WiBA-Prüffragen."""
import pytest
from flask import Response


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


class TestAiActOwaspLlm1523:
    BASE = '/api/aiact'
    PROJ = 'pytest-1523-owasp-llm'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.aiact import DB_PATH
        from ai_act.owasp_llm_register import register_items
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'organisation': 'U'})
        yield DB_PATH, str(register_items()[0]['id'])
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)

    def _load(self, llm_id):
        from ai_act.db import load_owasp_llm_checks
        from server.api.aiact import DB_PATH
        return load_owasp_llm_checks(DB_PATH, self.PROJ).get(llm_id, {})

    def test_import_issue_score_neutral(self, client, auth_headers, projekt):
        db, llm_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp-llm/{llm_id}', headers=auth_headers,
                    json={'status': 2, 'kommentar': 'Basis'})
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp-llm/{llm_id}/import-issue',
                        headers=auth_headers, json={'issue_context': 'LLM-FEEDBACK-7'})
        assert r.status_code == 200, r.get_json()
        chk = self._load(llm_id)
        assert int(chk['status']) == 2                  # SCORE UNVERÄNDERT
        assert 'LLM-FEEDBACK-7' in chk['kommentar']

    def test_stream_use_issue_feedback(self, client, auth_headers, projekt, monkeypatch):
        db, llm_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp-llm/{llm_id}', headers=auth_headers,
                    json={'status': 1, 'kommentar': 'x'})
        import shared.issue_feedback as fb
        import server.services.auto_bewertung as ab
        monkeypatch.setattr(fb, 'collect_object_feedback', lambda *a, **k: 'LLM-COLLECTED-42')
        cap = {}

        def fake_stream(prompt, *, save):
            cap['prompt'] = prompt
            save(4, 'ok', '')
            return Response('event: done\ndata: {}\n\n', mimetype='text/event-stream')

        monkeypatch.setattr(ab, 'stream_auto_bewertung', fake_stream)
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp-llm/{llm_id}/auto-bewertung/stream',
                        headers=auth_headers, json={'use_issue_feedback': True})
        assert r.status_code == 200
        assert 'LLM-COLLECTED-42' in cap.get('prompt', '')


class TestWibaImport1524:
    BASE = '/api/wiba'
    PROJ = 'pytest-1524-wiba'
    CID = 'orga-1'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.wiba import DB_PATH
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'unternehmen': 'U'})
        yield DB_PATH
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)

    def _load(self):
        from wiba.db import load_antworten
        from server.api.wiba import DB_PATH
        return load_antworten(DB_PATH, self.PROJ).get(self.CID, {})

    def test_import_issue_answer_neutral(self, client, auth_headers, projekt):
        client.post(f'{self.BASE}/projekte/{self.PROJ}/antworten', headers=auth_headers,
                    json={'control_id': self.CID, 'status': 'nein', 'notiz': 'Lücke'})
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/controls/{self.CID}/import-issue',
                        headers=auth_headers, json={'issue_context': 'WIBA-FEEDBACK-3'})
        assert r.status_code == 200, r.get_json()
        a = self._load()
        assert a['status'] == 'nein'                    # ANTWORT UNVERÄNDERT
        assert 'WIBA-FEEDBACK-3' in a['notiz']
