"""#1573 — Einheitliche automatische Bewertung in allen Modulen.

- WiBA bekommt (wie CRA/NIS2/AI-Act/DSGVO/RB) einen Auto-Bewertungs-Stream je Prüffrage;
  Antwort + Notiz werden gespeichert, übrige Felder bleiben erhalten.
- Egress-Audit/Gate lesen den Provider aus ``provider`` (vorher ``active`` → „unknown").
- RB ``mass-ollama`` respektiert ``only_open``.
"""
import json

import pytest
from flask import Response

WP = 'pytest-1573-wiba'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def wiba_setup():
    from server.api.wiba import DB_PATH
    from wiba import db as wdb
    wdb.ensure_db(DB_PATH)
    wdb.replace_catalog(
        DB_PATH,
        themen=[{'theme_key': 'backup', 'titel': 'Backup', 'bausteine': 'CON.3',
                 'ziel': 'Z', 'reihenfolge': 1}],
        prueffragen=[{'control_id': 'backup-1', 'theme_key': 'backup', 'nr': 1,
                      'frage': 'Ist Backup festgelegt?', 'hilfsmittel': '', 'aufwand': '1'}],
        version='test', quelle='pytest')
    wdb.save_projekt(DB_PATH, name=WP, unternehmen='Acme')
    yield DB_PATH
    try:
        wdb.delete_projekt(DB_PATH, WP)
    except Exception:
        pass


def _fake_sse(monkeypatch, raw_answer: str, captured: dict):
    """stream_ai_sse ersetzen: finalize mit der Fake-KI-Antwort aufrufen."""
    import shared.sse as sse

    def fake(system, prompt, *, finalize=None, **kw):
        captured['prompt'] = prompt
        result = finalize(raw_answer) if finalize else {}
        captured['result'] = result
        return Response(f'event: done\ndata: {json.dumps({"ok": True, **result})}\n\n',
                        mimetype='text/event-stream')

    monkeypatch.setattr(sse, 'stream_ai_sse', fake)


def test_wiba_auto_stream_saves_answer_and_keeps_fields(client, auth_headers, wiba_setup, monkeypatch):
    import server.services.auto_bewertung as ab
    import ai_compliance_suite.ai.dispatch as dispatch
    from wiba import db as wdb
    monkeypatch.setattr(ab, 'ensure_ai_available', lambda: None)
    monkeypatch.setattr(dispatch, 'current_provider_name', lambda: 'cloud')
    wdb.save_antwort(wiba_setup, WP, 'backup-1', status='nein', notiz='alt',
                     verantwortlich='IT-Leitung', zieldatum='2026-12-31')
    cap: dict = {}
    _fake_sse(monkeypatch, '```json\n{"status":"ja","notiz":"Backup-Konzept liegt vor",'
                           '"empfehlung":"Restore jährlich testen"}\n```', cap)

    r = client.post(f'/api/wiba/projekte/{WP}/controls/backup-1/auto-bewertung/stream',
                    headers=auth_headers, json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert 'Ist Backup festgelegt?' in cap['prompt']
    res = cap['result']
    assert res['status'] == 'ja' and res['saved'] is True
    assert res['massnahmen'] == ['Restore jährlich testen']
    a = wdb.load_antworten(wiba_setup, WP)['backup-1']
    assert a['status'] == 'ja'
    assert 'Backup-Konzept liegt vor' in a['notiz']
    # #1765: Der Text bleibt sauber. Die Kennzeichnungspflicht (#1551/#1552)
    # ist damit nicht aufgehoben — sie wandert aus dem gespeicherten Inhalt in
    # das Register `shared/ki_herkunft` und in die Oberfläche. Im Dokument hat
    # der Hinweis nichts verloren: „fachlich zu prüfen" nimmt einem
    # freigegebenen Nachweis seine Aussage.
    assert 'KI-generiert' not in a['notiz']
    from shared.ki_herkunft import status
    h = status('wiba', WP, 'wiba_control', 'backup-1')
    assert h['ki'] is True and h['geprueft'] is False
    assert a['verantwortlich'] == 'IT-Leitung'          # übrige Felder bleiben
    assert a['zieldatum'] == '2026-12-31'


def test_wiba_auto_stream_ki_unavailable_409(client, auth_headers, wiba_setup, monkeypatch):
    import server.services.auto_bewertung as ab

    def _unavail():
        raise ab.AutoBewertungUnavailable('Kein Provider')
    monkeypatch.setattr(ab, 'ensure_ai_available', _unavail)
    r = client.post(f'/api/wiba/projekte/{WP}/controls/backup-1/auto-bewertung/stream',
                    headers=auth_headers, json={})
    assert r.status_code == 409


def test_wiba_auto_stream_unknown_control_404(client, auth_headers, wiba_setup):
    r = client.post(f'/api/wiba/projekte/{WP}/controls/gibts-nicht/auto-bewertung/stream',
                    headers=auth_headers, json={})
    assert r.status_code == 404


def test_egress_audit_uses_provider_key(client, auth_headers, monkeypatch):
    import server.services.prefill as prefill
    import server.api.ai_status as ai_status
    import shared.sse as sse
    import shared.audit as audit
    monkeypatch.setattr(prefill, 'is_ai_available', lambda: (True, ''))
    monkeypatch.setattr(ai_status, '_build_provider_status', lambda: {'provider': 'cloud'})
    monkeypatch.setattr(sse, 'stream_ai_sse',
                        lambda *a, **k: Response('event: done\ndata: {"ok":true}\n\n',
                                                 mimetype='text/event-stream'))
    cap = {}
    monkeypatch.setattr(audit, 'audit_event',
                        lambda action, *, module, outcome='success', details=None: cap.update(details or {}))
    r = client.post('/api/ai/run-stream', headers=auth_headers,
                    json={'prompt': 'x', 'confirmed': True})
    assert r.status_code == 200
    assert cap.get('provider') == 'cloud'


def test_rb_mass_ollama_respects_only_open(client, auth_headers, monkeypatch):
    from server.api.risikobewertung import DB_PATH
    from risikobewertung.db import save_projekt, load_risiken, bulk_insert_risiken, delete_projekt
    import risikobewertung.db as rdb
    import risikobewertung.prompts as rp
    import ai_compliance_suite.ai.dispatch as dispatch
    import server.services.prefill as prefill
    name = 'pytest-1573-rb'
    try:
        delete_projekt(DB_PATH, name)
    except Exception:
        pass
    save_projekt(DB_PATH, name, 'STRIDE', '')
    bulk_insert_risiken(DB_PATH, name, [
        {'risk_name': 'Offen', 'beschreibung': 'a', 'framework': 'STRIDE'},
        {'risk_name': 'Erledigt', 'beschreibung': 'b', 'framework': 'STRIDE'}])
    erledigt = next(r for r in load_risiken(DB_PATH, name) if r['risk_name'] == 'Erledigt')
    rdb.set_risiko_resolved(DB_PATH, erledigt['id'], resolved=True, reason='test')
    monkeypatch.setattr(dispatch, 'is_cloud_provider', lambda: True)
    monkeypatch.setattr(prefill, 'is_ai_available', lambda: (True, ''))
    seen = []

    def fake_llm(*, risk, **kw):
        seen.append(risk['risk_name'])
        yield '```json\n{"felder": {}, "bewertung": "ok"}\n```'
    monkeypatch.setattr(rp, 'generate_llm', fake_llm)
    try:
        r = client.post(f'/api/risikobewertung/projekte/{name}/mass-ollama',
                        headers=auth_headers, json={'only_open': True})
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert all(x['ok'] for x in body['results']), body   # Fences werden robust geparst
        assert seen == ['Offen']                             # erledigte Risiken ausgenommen
    finally:
        delete_projekt(DB_PATH, name)


def test_cloud_stream_reports_provider_cloud(monkeypatch):
    """#1573: Cloud-Stream meldet ``cloud`` (nicht den Anbieternamen) → korrekte ☁️-Anzeige."""
    import ai_compliance_suite.ai.dispatch as dispatch
    from ai_compliance_suite.ai import streaming

    def _stream(**kw):  # #1588: Cloud streamt jetzt echt (dispatch.stream_text)
        yield {'kind': 'chunk', 'text': '{"score": 3}'}
        yield {'kind': 'end', 'stop_reason': 'end_turn', 'truncated': False}
    monkeypatch.setattr(dispatch, 'current_provider_name', lambda: 'cloud')
    monkeypatch.setattr(dispatch, 'is_cloud_provider', lambda: True)
    monkeypatch.setattr(dispatch, 'stream_text', _stream)
    evs = list(streaming.stream_generate('sys', 'prompt'))
    done = [e for e in evs if e.get('kind') == 'done'][0]
    assert done['provider'] == 'cloud'
