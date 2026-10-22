"""#1588: Lange KI-Antworten (Massenbewertung) kommen vollständig an.

- Cloud streamt echt (Anthropic-SSE / OpenAI ``stream=true``) statt blockierend.
- Abschneiden am Token-Limit wird erkannt (``truncated``) und klar gemeldet.
- Ausgabebudget für ``/api/ai/run-stream`` reicht für Sammel-Prompts.
- Ollama bekommt ein zur Länge passendes ``num_ctx``.
"""
import io
import json
from types import SimpleNamespace

import pytest


class _FakeResp:
    def __init__(self, lines=(), status=200, text=''):
        self._lines = [l.encode() if isinstance(l, str) else l for l in lines]
        self.status_code = status
        self.text = text
        self.closed = False

    def iter_lines(self, decode_unicode=False):
        yield from self._lines

    def close(self):
        self.closed = True


def _sse(obj):
    return 'data: ' + json.dumps(obj)


@pytest.fixture
def cloud(monkeypatch):
    import shared.audit as audit
    from ai_compliance_suite.ai.providers import cloud as cloud_mod
    monkeypatch.setattr(cloud_mod, 'audit_event', lambda *a, **k: None)
    monkeypatch.setattr(audit, 'audit_event', lambda *a, **k: None)
    return cloud_mod


def _provider(cloud_mod, base_url):
    return cloud_mod.CloudProvider({'allow_data_egress': True, 'api_key': 'k', 'model': 'm',
                                    'base_url': base_url, 'timeout_s': 60})


def test_anthropic_stream_vollstaendig_und_abgeschnitten(cloud, monkeypatch):
    from ai_compliance_suite.ai.provider import AITextRequest
    calls = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        calls.append({'url': url, 'payload': dict(json), 'stream': stream, 'timeout': timeout})
        return _FakeResp([
            'event: message_start', _sse({'type': 'message_start'}),
            _sse({'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': '{"a":'}}),
            _sse({'type': 'ping'}),
            _sse({'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': ' 1}'}}),
            _sse({'type': 'message_delta', 'delta': {'stop_reason': 'max_tokens'}}),
            _sse({'type': 'message_stop'}),
        ])
    monkeypatch.setattr(cloud.requests, 'post', fake_post)
    p = _provider(cloud, 'https://api.anthropic.com/v1')
    evs = list(p.stream_text(AITextRequest(system='s', prompt='p', max_output_tokens=16384)))
    assert ''.join(e['text'] for e in evs if e['kind'] == 'chunk') == '{"a": 1}'
    assert evs[-1] == {'kind': 'end', 'stop_reason': 'max_tokens', 'truncated': True}
    c = calls[0]
    assert c['url'].endswith('/messages') and c['stream'] is True
    assert c['payload']['stream'] is True and c['payload']['max_tokens'] == 16384
    # Read-Timeout gilt zwischen Tokens und ist nicht mehr nur 60 s
    assert c['timeout'][1] >= 300


def test_openai_stream_und_max_tokens_rueckfall(cloud, monkeypatch):
    from ai_compliance_suite.ai.provider import AITextRequest
    budgets = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        budgets.append(json['max_tokens'])
        if json['max_tokens'] > 8192:
            return _FakeResp(status=400, text='max_tokens is too large: 16384')
        return _FakeResp([
            _sse({'choices': [{'delta': {'content': 'Hallo '}}]}),
            _sse({'choices': [{'delta': {'content': 'Welt'}, 'finish_reason': 'stop'}]}),
            'data: [DONE]',
        ])
    monkeypatch.setattr(cloud.requests, 'post', fake_post)
    p = _provider(cloud, 'https://api.openai.com/v1')
    evs = list(p.stream_text(AITextRequest(system='s', prompt='p', max_output_tokens=16384)))
    assert budgets == [16384, 8192]
    assert ''.join(e['text'] for e in evs if e['kind'] == 'chunk') == 'Hallo Welt'
    assert evs[-1]['truncated'] is False


def test_anthropic_generate_text_fuegt_alle_bloecke_zusammen(cloud, monkeypatch):
    from ai_compliance_suite.ai.provider import AITextRequest

    class _R:
        status_code = 200
        text = ''

        def json(self):
            return {'content': [{'type': 'text', 'text': 'A'}, {'type': 'text', 'text': 'B'}]}
    monkeypatch.setattr(cloud.requests, 'post', lambda *a, **k: _R())
    p = _provider(cloud, 'https://api.anthropic.com/v1')
    assert p.generate_text(AITextRequest(system='s', prompt='p')).text == 'AB'


def test_auto_num_ctx(monkeypatch):
    import ai_compliance_suite.ai.dispatch as dispatch
    from ai_compliance_suite.ai.streaming import auto_num_ctx
    monkeypatch.setattr(dispatch, 'max_num_ctx', lambda: 32768)
    assert auto_num_ctx(1000, 1024) is None            # kurze Anfrage → Ollama-Default
    assert auto_num_ctx(3000, 4096) == 8192
    assert auto_num_ctx(30000, 16384) == 32768          # Sammel-Prompt → großes Fenster
    assert auto_num_ctx(300000, 16384) == 32768         # Deckel
    assert auto_num_ctx(1000, 1024, 16384) == 16384     # Mindestwert des Aufrufers


def test_ollama_done_reason_length_wird_erkannt(monkeypatch):
    import ai_compliance_suite.ai.dispatch as dispatch
    import shared.net_validation as nv
    import shared.ollama_config as oc
    import urllib.request
    monkeypatch.setattr(dispatch, 'current_provider_name', lambda: 'on_prem')
    monkeypatch.setattr(dispatch, 'is_cloud_provider', lambda: False)
    monkeypatch.setattr(dispatch, 'max_num_ctx', lambda: 32768)
    monkeypatch.setattr(oc, 'get_ollama_config',
                        lambda: SimpleNamespace(model='m', base_url='http://127.0.0.1:11434', timeout_s=60))
    monkeypatch.setattr(nv, 'enforce_loopback_base_url', lambda *a, **k: None)
    gesendet = {}

    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _open(req, timeout=None):
        gesendet.update(json.loads(req.data))
        lines = [{'response': '[{"id":'}, {'done': True, 'done_reason': 'length'}]
        return _Resp(b'\n'.join(json.dumps(l).encode() for l in lines))
    monkeypatch.setattr(urllib.request, 'urlopen', _open)
    from ai_compliance_suite.ai.streaming import stream_generate
    evs = list(stream_generate('s', 'x' * 30000, num_predict=16384))
    assert evs[-1]['kind'] == 'done' and evs[-1]['truncated'] is True
    assert gesendet['options']['num_ctx'] == 32768 and gesendet['options']['num_predict'] == 16384


def _done(body):
    return json.loads(body.split('event: done\ndata: ', 1)[1].split('\n', 1)[0])


def test_run_stream_budget_und_abschneide_meldung(client, auth_headers, monkeypatch):
    from ai_compliance_suite.ai import streaming
    from server.services import prefill
    gesehen = {}

    def fake_stream(system, prompt, **kw):
        gesehen.update(kw)
        yield {'kind': 'chunk', 'text': '[{"id": "A-1", "score": 3}, {"id": "A-2"'}
        yield {'kind': 'done', 'provider': 'cloud', 'truncated': True,
               'num_predict': kw.get('num_predict')}
    monkeypatch.setattr(prefill, 'is_ai_available', lambda: (True, ''))
    monkeypatch.setattr(streaming, 'stream_generate', fake_stream)
    r = client.post('/api/ai/run-stream', headers=auth_headers,
                    json={'prompt': 'Sammel-Prompt', 'confirmed': True})
    assert r.status_code == 200
    done = _done(r.get_data(as_text=True))
    assert gesehen['num_predict'] >= 16384
    assert done['ok'] is False and done['truncated'] is True
    assert 'abgeschnitten' in done['error'] and done['text'].startswith('[{"id": "A-1"')


def test_run_stream_vollstaendig(client, auth_headers, monkeypatch):
    from ai_compliance_suite.ai import streaming
    from server.services import prefill

    def fake_stream(system, prompt, **kw):
        yield {'kind': 'chunk', 'text': '[{"id": "A-1", '}
        yield {'kind': 'chunk', 'text': '"score": 3}]'}
        yield {'kind': 'done', 'provider': 'cloud', 'truncated': False}
    monkeypatch.setattr(prefill, 'is_ai_available', lambda: (True, ''))
    monkeypatch.setattr(streaming, 'stream_generate', fake_stream)
    r = client.post('/api/ai/run-stream', headers=auth_headers,
                    json={'prompt': 'Sammel-Prompt', 'confirmed': True})
    done = _done(r.get_data(as_text=True))
    assert done['ok'] is True and done['text'] == '[{"id": "A-1", "score": 3}]'
