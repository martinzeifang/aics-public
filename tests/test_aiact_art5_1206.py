"""#1206 — AI-Act Art. 5 Verbots-Screening: 8 Tatbestände, Gate, Wizard, Export."""

import pytest

BASE = '/api/aiact'
A5 = '/api/aiact-art5'
PROJ = 'pytest-art5-1206'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _clear(projekt):
    import sqlite3
    from server.api.aiact import DB_PATH
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("DELETE FROM aiact_art5_screening WHERE projekt_name=?", (projekt,))
        con.commit()
        con.close()
    except Exception:
        pass


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear(PROJ)
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': PROJ, 'produkt': 'Test-KI', 'beschreibung': 'Use-Case'})
    assert r.status_code in (200, 201), r.get_json()
    yield PROJ
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear(PROJ)


def test_catalog_has_eight():
    from ai_act import art5_screening as a5
    assert len(a5.catalog()) == 8
    assert {t['code'] for t in a5.catalog()} == set('abcdefgh')


def test_screening_lists_all_eight(client, auth_headers, projekt):
    r = client.get(f'{A5}/projekte/{PROJ}/screening', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert len(d['items']) == 8
    assert d['summary']['gesamt'] == 8
    assert d['summary']['offen'] == 8
    assert d['summary']['has_prohibited'] is False


def test_save_negativ_befund(client, auth_headers, projekt):
    r = client.post(f'{A5}/projekte/{PROJ}/screening/c', headers=auth_headers,
                    json={'betroffen': 'nein', 'begruendung': 'Kein Social Scoring',
                          'geprueft_von': 'Tester'})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['summary']['offen'] == 7


def test_treffer_sets_tier_prohibited(client, auth_headers, projekt):
    r = client.post(f'{A5}/projekte/{PROJ}/screening/a', headers=auth_headers,
                    json={'betroffen': 'ja', 'begruendung': 'Manipulation erkannt'})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['summary']['has_prohibited'] is True
    # Projekt-Meta muss risk_tier=prohibited tragen (serialisiert als JSON-String).
    import json
    p = client.get(f'{BASE}/projekte/{PROJ}', headers=auth_headers).get_json()
    meta = p.get('meta') or {}
    if isinstance(meta, str):
        meta = json.loads(meta or '{}')
    assert meta.get('risk_tier') == 'prohibited'


def test_gate_blocks_until_complete(client, auth_headers, projekt):
    g = client.get(f'{A5}/projekte/{PROJ}/gate', headers=auth_headers).get_json()
    assert g['allow_confirm'] is False
    # Alle 8 mit 'nein' beantworten.
    for code in 'abcdefgh':
        client.post(f'{A5}/projekte/{PROJ}/screening/{code}', headers=auth_headers,
                    json={'betroffen': 'nein', 'begruendung': 'n/a'})
    g = client.get(f'{A5}/projekte/{PROJ}/gate', headers=auth_headers).get_json()
    assert g['allow_confirm'] is True
    assert g['forced_tier'] is None


def test_invalid_value_rejected(client, auth_headers, projekt):
    r = client.post(f'{A5}/projekte/{PROJ}/screening/a', headers=auth_headers,
                    json={'betroffen': 'vielleicht'})
    assert r.status_code == 400


def test_wizard_prompt_and_parse(client, auth_headers, projekt):
    pr = client.get(f'{A5}/projekte/{PROJ}/wizard/prompt', headers=auth_headers)
    assert pr.status_code == 200
    assert 'Art. 5' in pr.get_json()['prompt']
    raw = '{"items":[{"code":"f","betroffen":"ja","begruendung":"Emotion am Arbeitsplatz"}]}'
    pa = client.post(f'{A5}/projekte/{PROJ}/wizard/parse', headers=auth_headers,
                     json={'response': raw, 'apply': True})
    assert pa.status_code == 200, pa.get_json()
    assert pa.get_json()['summary']['has_prohibited'] is True


def test_export(client, auth_headers, projekt):
    client.post(f'{A5}/projekte/{PROJ}/screening/a', headers=auth_headers,
                json={'betroffen': 'nein', 'begruendung': 'ok'})
    r = client.get(f'{A5}/projekte/{PROJ}/export', headers=auth_headers)
    assert r.status_code == 200
    assert b'Verbots-Screening' in r.data
