"""#1550 (AIA-HR-04, Art. 12): On-Prem-Streaming protokolliert jeden KI-Aufruf — nur Metadaten."""
import io
import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def env(monkeypatch):
    import ai_compliance_suite.ai.dispatch as dispatch
    import shared.ollama_config as oc
    import shared.net_validation as nv
    import shared.audit as audit
    events = []
    monkeypatch.setattr(dispatch, 'current_provider_name', lambda: 'on_prem')
    monkeypatch.setattr(dispatch, 'is_cloud_provider', lambda: False)
    monkeypatch.setattr(oc, 'get_ollama_config',
                        lambda: SimpleNamespace(model='m1', base_url='http://127.0.0.1:11434', timeout_s=60))
    monkeypatch.setattr(nv, 'enforce_loopback_base_url', lambda *a, **k: None)
    monkeypatch.setattr(audit, 'audit_event',
                        lambda action, **kw: events.append((action, kw.get('outcome'), kw.get('details'))))
    return events


def _fake_urlopen(lines):
    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def _open(req, timeout=None):
        return _Resp(b"\n".join(json.dumps(l).encode() for l in lines))
    return _open


def test_success_logged_without_content(env, monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlopen',
                        _fake_urlopen([{'response': 'GEHEIM'}, {'response': '!'}, {'done': True}]))
    from ai_compliance_suite.ai.streaming import stream_generate
    out = list(stream_generate('SYS', 'VERTRAULICHER PROMPT'))
    assert out[-1]['kind'] == 'done'
    assert [(a, o) for a, o, _ in env] == [('ai.on_prem.stream', 'start'), ('ai.on_prem.stream', 'success')]
    blob = json.dumps([d for _, _, d in env])
    assert 'VERTRAULICHER' not in blob and 'GEHEIM' not in blob          # Datenminimierung
    assert env[1][2]['tokens'] == 2 and env[0][2]['model'] == 'm1'


def test_failure_and_abort_logged(env, monkeypatch):
    import urllib.request
    def _boom(req, timeout=None):
        raise OSError('connection refused')
    monkeypatch.setattr(urllib.request, 'urlopen', _boom)
    from ai_compliance_suite.ai.streaming import stream_generate
    assert list(stream_generate('s', 'p'))[-1]['kind'] == 'error'
    assert env[-1][1] == 'fail'

    env.clear()
    monkeypatch.setattr(urllib.request, 'urlopen', _fake_urlopen([{'response': 'a'}, {'response': 'b'}]))
    gen = stream_generate('s', 'p')
    next(gen)          # Client bricht nach dem ersten Chunk ab
    gen.close()
    assert [o for _, o, _ in env] == ['start', 'aborted']


# ── #1551/#1552 → #1765: Kennzeichnung ja, aber nicht im gespeicherten Text ──

def test_ki_kennzeichnung_bleibt_aus_dem_text_heraus():
    """Der Vertrag hat sich mit v8.0.0 umgedreht (#1765).

    Bis dahin verlangte dieser Test den Marker **im Text** — und genau das war
    der Fehler: Er stand damit in jedem Bericht, bis in die
    EU-Konformitätserklärung. Die Pflicht aus #1551/#1552 bleibt, sie wird nur
    anders erfüllt: strukturiert in `shared/ki_herkunft`, samt der Angabe, wer
    die Bewertung fachlich geprüft hat.

    Der Test ist deshalb nicht gelöscht, sondern umgedreht — er hält jetzt fest,
    dass der Text sauber bleibt **und** der Vermerk trotzdem existiert.
    """
    from server.services.auto_bewertung import ki_kennzeichnung, KI_MARKER
    from shared.ki_herkunft import status, vermerken

    a = ki_kennzeichnung('Begründung', 'on_prem')
    assert a == 'Begründung'
    assert KI_MARKER not in a
    # Bestandstexte tragen den alten Marker; er wird beim Durchreichen entfernt.
    alt_text = 'Begründung\n\n— 🤖 KI-generiert (on_prem, 2026-10-01) — fachlich zu prüfen.'
    assert ki_kennzeichnung(alt_text, 'cloud') == 'Begründung'
    assert ki_kennzeichnung('', 'on_prem') == ''

    # Die Herkunft selbst geht nicht verloren — sie steht jetzt im Register.
    vermerken('cra', 'pytest-1550', 'requirement', 'X-1', provider='on_prem')
    st = status('cra', 'pytest-1550', 'requirement', 'X-1')
    assert st['ki'] is True and st['provider'] == 'on_prem'
    assert st['geprueft'] is False   # erzeugt ≠ geprüft
