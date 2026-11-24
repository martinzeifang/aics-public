"""#1519 — Datenübermittlung an die KI erst nach Bestätigung + append-only Audit."""
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


def test_run_stream_requires_confirmation(client, auth_headers):
    r = client.post('/api/ai/run-stream', headers=auth_headers, json={'prompt': 'Hallo KI'})
    assert r.status_code == 428
    assert 'estätigung' in (r.get_json() or {}).get('error', '')


def test_run_stream_confirmed_audits_egress(client, auth_headers, monkeypatch):
    import server.services.prefill as prefill
    import shared.sse as sse
    import shared.audit as audit
    monkeypatch.setattr(prefill, 'is_ai_available', lambda: (True, ''))
    monkeypatch.setattr(sse, 'stream_ai_sse',
                        lambda *a, **k: Response('event: done\ndata: {"ok":true}\n\n',
                                                 mimetype='text/event-stream'))
    captured = {}

    def fake_audit(action, *, module, outcome='success', details=None):
        captured['action'] = action
        captured['details'] = details or {}

    monkeypatch.setattr(audit, 'audit_event', fake_audit)

    r = client.post('/api/ai/run-stream', headers=auth_headers,
                    json={'prompt': 'Bewerte X', 'confirmed': True,
                          'egress_context': 'CRA/CRA-1', 'modul': 'cra'})
    assert r.status_code == 200
    assert captured.get('action') == 'ai.egress.confirmed'
    assert captured['details'].get('prompt_laenge') == len('Bewerte X')
    assert 'prompt_sha256' in captured['details']
    assert captured['details'].get('kontext') == 'CRA/CRA-1'


def test_audit_events_action_filter(client, auth_headers):
    # #1519: action-Filter im Revisionsbericht vorhanden (kein 500, Liste/total).
    r = client.get('/api/admin/audit/events?action=ai.egress.confirmed&limit=5', headers=auth_headers)
    assert r.status_code in (200, 403)  # 403 falls Test-User keine admin:audit-Permission hat
    if r.status_code == 200:
        body = r.get_json()
        assert 'events' in body and 'total' in body
