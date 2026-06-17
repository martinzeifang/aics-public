"""#1048 — Massenbewertung über EINEN Sammel-Prompt (Prompt → Vorschau → Übernehmen)."""
import json
from pathlib import Path

import pytest

from server.api.risikobewertung import DB_PATH
from risikobewertung.db import save_projekt, save_risiko, load_risiken, delete_projekt
from risikobewertung.prompts import build_mass_assessment_prompt, parse_mass_assessment_antwort

PROJ = 'pytest-rb-mass-1048'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekt():
    delete_projekt(DB_PATH, PROJ)
    save_projekt(DB_PATH, PROJ, framework='STRIDE', beschreibung='', unternehmen='ACME')
    save_risiko(DB_PATH, {'projekt_name': PROJ, 'nr': 1, 'risk_name': 'Manipulation Konfig',
                          'beschreibung': 'Angreifer ändert Settings', 'framework': 'STRIDE'})
    save_risiko(DB_PATH, {'projekt_name': PROJ, 'nr': 2, 'risk_name': 'DoS auf API',
                          'beschreibung': 'Lastspitzen legen API lahm', 'framework': 'STRIDE'})
    yield
    delete_projekt(DB_PATH, PROJ)
    import sqlite3
    con = sqlite3.connect(str(DB_PATH))
    con.execute("DELETE FROM rb_risiken WHERE projekt_name=?", (PROJ,))
    con.commit(); con.close()


def _u(s=''):
    return f'/api/risikobewertung/projekte/{PROJ}/risiken/mass-assess{s}'


# ── reine Lib ───────────────────────────────────────────────────────

def test_build_mass_prompt_lists_all_risks_and_array_format():
    risks = [{'nr': 1, 'risk_name': 'A', 'beschreibung': 'desc-a', 'felder': {}},
             {'nr': 2, 'risk_name': 'B', 'beschreibung': 'desc-b', 'felder': {}}]
    p = build_mass_assessment_prompt(risks, 'STRIDE')
    assert 'nr 1' in p and 'nr 2' in p
    assert 'JSON-Array' in p
    assert 'eintrittswahrscheinlichkeit' in p  # Feld-Optionen eingebettet
    assert 'desc-a' in p and 'desc-b' in p


def test_parse_mass_array_skips_invalid_and_keeps_valid():
    raw = """```json
[
  {"nr": 1, "felder": {"auswirkung": "Hoch"}, "bewertung": "x", "empfehlungen": ["m1"]},
  {"nr": "kaputt", "felder": {}},
  {"felder": {"a": "b"}},
  {"nr": 2, "felder": {"auswirkung": "Gering"}, "bewertung": "y"}
]
```"""
    out = parse_mass_assessment_antwort(raw)
    assert [o['nr'] for o in out] == [1, 2]
    assert out[0]['bewertung'] == 'x'


def test_parse_mass_garbage_raises():
    with pytest.raises(ValueError):
        parse_mass_assessment_antwort('kein json hier')


# ── Endpoints: Prompt → Vorschau (kein Save) → Übernehmen ───────────

def test_mass_prompt_endpoint(client, auth_headers, projekt):
    r = client.post(_u('-prompt'), json={'only_open': True}, headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['count'] == 2
    assert 'nr 1' in body['prompt'] and 'nr 2' in body['prompt']
    assert {x['nr'] for x in body['risiken']} == {1, 2}


def _answer():
    return json.dumps([
        {'nr': 1, 'felder': {'stride_kategorie': 'Tampering (T) – Manipulation von Daten',
                             'eintrittswahrscheinlichkeit': 'Wahrscheinlich', 'auswirkung': 'Hoch'},
         'bewertung': 'Bewertung Risiko 1'},
        {'nr': 2, 'felder': {'stride_kategorie': 'Denial of Service (D) – Dienstverweigerung',
                             'eintrittswahrscheinlichkeit': 'Möglich', 'auswirkung': 'Mittel'},
         'bewertung': 'Bewertung Risiko 2'},
    ])


def test_mass_preview_does_not_save(client, auth_headers, projekt):
    r = client.post(_u('-preview'), json={'raw': _answer()}, headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['count'] == 2
    a1 = next(a for a in body['assessments'] if a['nr'] == 1)
    assert a1['risikowert'] is not None and a1['risiko_label']
    assert a1['bewertung_text'] == 'Bewertung Risiko 1'
    # KEINE Persistenz in der Vorschau
    for rr in load_risiken(DB_PATH, PROJ):
        assert not rr.get('bewertung_text')
        assert rr.get('risikowert') in (None, 0, '')


def test_mass_apply_saves_only_confirmed(client, auth_headers, projekt):
    prev = client.post(_u('-preview'), json={'raw': _answer()}, headers=auth_headers).get_json()
    # Nur Risiko 1 bestätigen (Review-Schritt: Auswahl)
    chosen = [a for a in prev['assessments'] if a['nr'] == 1]
    r = client.post(_u('-apply'), json={'assessments': chosen}, headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['applied_count'] == 1
    by_nr = {rr['nr']: rr for rr in load_risiken(DB_PATH, PROJ)}
    assert by_nr[1].get('bewertung_text') == 'Bewertung Risiko 1'
    assert by_nr[1].get('risikowert')
    # Risiko 2 wurde NICHT gespeichert
    assert not by_nr[2].get('bewertung_text')


def test_mass_preview_empty_raw_400(client, auth_headers, projekt):
    r = client.post(_u('-preview'), json={'raw': '   '}, headers=auth_headers)
    assert r.status_code == 400
