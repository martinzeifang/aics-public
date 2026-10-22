"""#1518 — OWASP „Automatische Bewertung" (Streaming) — behebt HTTP 404.

Das Frontend (RequirementActions) ruft für OWASP immer ``…/auto-bewertung/stream``.
Bisher existierte für CRA-OWASP nur die Nicht-Stream-Variante → 404. Hier wird der
neue Stream-Endpoint verdrahtet getestet (ohne echten LLM, via Monkeypatch).
Zusätzlich: optionaler ``issue_context`` landet im Prompt (#1521).
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


class TestCraOwaspAutoBewertungStream:
    BASE = '/api/cra'
    PROJ = 'pytest-owasp-stream-1518'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.cra import DB_PATH
        from cra.owasp_proactive_controls import OWASP_PC_V3
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'unternehmen': 'U'})
        yield DB_PATH, str(OWASP_PC_V3[0]['id'])
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)

    def _patch_stream(self, monkeypatch, captured, score=4):
        import server.services.auto_bewertung as ab

        def fake_stream(prompt, *, save):
            captured['prompt'] = prompt
            save(score, 'KI-Begründung zum Control', 'Konkrete Maßnahme X')
            return Response('event: done\ndata: {}\n\n', mimetype='text/event-stream')

        monkeypatch.setattr(ab, 'stream_auto_bewertung', fake_stream)

    def test_stream_endpoint_exists_and_saves(self, client, auth_headers, projekt, monkeypatch):
        from cra.db import load_owasp_checks
        db, owasp_id = projekt
        captured = {}
        self._patch_stream(monkeypatch, captured, score=4)

        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp/{owasp_id}/auto-bewertung/stream',
                        headers=auth_headers, json={})
        assert r.status_code == 200, r.data[:200]   # NICHT 404
        chk = load_owasp_checks(db, self.PROJ).get(owasp_id, {})
        assert int(chk.get('status')) == 4
        assert 'Konkrete Maßnahme X' in chk.get('kommentar', '')

    def test_issue_context_in_prompt(self, client, auth_headers, projekt, monkeypatch):
        db, owasp_id = projekt
        captured = {}
        self._patch_stream(monkeypatch, captured)
        marker = 'REVIEW-FEEDBACK-ABC123'
        client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp/{owasp_id}/auto-bewertung/stream',
                    headers=auth_headers, json={'issue_context': marker})
        assert marker in captured.get('prompt', '')

    def test_unknown_owasp_404(self, client, auth_headers, projekt, monkeypatch):
        captured = {}
        self._patch_stream(monkeypatch, captured)
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp/NOPE-999/auto-bewertung/stream',
                        headers=auth_headers, json={})
        assert r.status_code == 404
