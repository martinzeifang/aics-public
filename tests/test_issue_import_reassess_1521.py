"""#1521 — Per-Item Issue-Inhalt-Import (score-neutral) + Neubewertung mit Issue-Feedback.

- Import schreibt das Issue-Feedback NUR in den Kommentar (Score/Status unverändert).
- Der Auto-Bewertung-Stream nimmt `issue_context` bzw. `use_issue_feedback` entgegen
  und fädelt das Feedback in den Prompt ein.
"""
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


# ── CRA OWASP: import-issue (score-neutral) + stream issue_context ──────────

class TestCraOwaspImportAndReassess:
    BASE = '/api/cra'
    PROJ = 'pytest-1521-cra-owasp'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.cra import DB_PATH
        from cra.owasp_proactive_controls import OWASP_PC_V3
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'unternehmen': 'U'})
        yield DB_PATH, str(OWASP_PC_V3[0]['id'])
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)

    def _load(self, owasp_id):
        from cra.db import load_owasp_checks
        from server.api.cra import DB_PATH
        return load_owasp_checks(DB_PATH, self.PROJ).get(owasp_id, {})

    def test_import_issue_is_score_neutral(self, client, auth_headers, projekt):
        db, owasp_id = projekt
        # Vorbewertung Status 3.
        client.put(f'{self.BASE}/projekte/{self.PROJ}/owasp/{owasp_id}', headers=auth_headers,
                   json={'status': 3, 'kommentar': 'Ursprung'})
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp/{owasp_id}/import-issue',
                        headers=auth_headers, json={'issue_context': 'REVIEW-INHALT-XYZ'})
        assert r.status_code == 200, r.get_json()
        chk = self._load(owasp_id)
        assert int(chk['status']) == 3                      # SCORE UNVERÄNDERT (#1521)
        assert 'REVIEW-INHALT-XYZ' in chk['kommentar']
        assert 'Ursprung' in chk['kommentar']

    def test_stream_use_issue_feedback_threads_into_prompt(self, client, auth_headers, projekt, monkeypatch):
        db, owasp_id = projekt
        client.put(f'{self.BASE}/projekte/{self.PROJ}/owasp/{owasp_id}', headers=auth_headers,
                   json={'status': 2, 'kommentar': 'x'})
        import shared.issue_feedback as fb
        import server.services.auto_bewertung as ab
        monkeypatch.setattr(fb, 'collect_object_feedback', lambda *a, **k: 'GESAMMELTES-FEEDBACK-123')
        captured = {}

        def fake_stream(prompt, *, save, herkunft=None):  # herkunft: #1765
            captured['prompt'] = prompt
            save(4, 'ok', '')
            return Response('event: done\ndata: {}\n\n', mimetype='text/event-stream')

        monkeypatch.setattr(ab, 'stream_auto_bewertung', fake_stream)
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp/{owasp_id}/auto-bewertung/stream',
                        headers=auth_headers, json={'use_issue_feedback': True})
        assert r.status_code == 200
        assert 'GESAMMELTES-FEEDBACK-123' in captured.get('prompt', '')


# ── DSGVO requirement: import-issue (score-neutral) ─────────────────────────

class TestDsgvoRequirementImport:
    BASE = '/api/dsgvo'
    PROJ = 'pytest-1521-dsgvo'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.dsgvo import DB_PATH
        from dsgvo.requirements import DSGVO_ANFORDERUNGEN
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'unternehmen': 'U'})
        yield DB_PATH, str(DSGVO_ANFORDERUNGEN[0]['id'])
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)

    def test_import_issue_score_neutral(self, client, auth_headers, projekt):
        from dsgvo.db import load_bewertungen
        db, req_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                    json={'anforderung_id': req_id, 'bewertung': 4, 'kommentar': 'Basis'})
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/anforderungen/{req_id}/import-issue',
                        headers=auth_headers, json={'issue_context': 'DSGVO-FEEDBACK-9'})
        assert r.status_code == 200, r.get_json()
        bw = load_bewertungen(db, self.PROJ).get(req_id, {})
        assert int(bw['bewertung']) == 4                    # SCORE UNVERÄNDERT
        assert 'DSGVO-FEEDBACK-9' in bw['kommentar']
