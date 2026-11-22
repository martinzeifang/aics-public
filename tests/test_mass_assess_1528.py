"""#1528 — Massenbewertung über EINEN Sammel-Prompt (Anforderungen + WiBA-Prüffragen)."""
import json

import pytest


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ── Reine Lib: select_for_mass / build / parse (Anforderungen) ───────────────

def test_select_for_mass_filters():
    from server.services.anforderung_prompt import select_for_mass
    reqs = [{'id': 'A', 'titel': 'ta'}, {'id': 'B', 'titel': 'tb'}, {'id': 'C', 'titel': 'tc'}]
    currents = {
        'A': {'bewertung': 5, 'kommentar': ''},
        'B': {'bewertung': 2, 'kommentar': '⚠️ Neubewertung erforderlich – verknüpftes Issue geändert'},
        'C': {'bewertung': 0, 'kommentar': ''},
    }
    ids = lambda sel: [s['id'] for s in sel]
    assert ids(select_for_mass(reqs, currents, only_open=True)) == ['B', 'C']       # A hat Score 5
    assert ids(select_for_mass(reqs, currents, only_reassess=True)) == ['B']         # nur Marker
    assert ids(select_for_mass(reqs, currents, req_ids=['A', 'C'])) == ['A', 'C']
    assert ids(select_for_mass(reqs, currents, limit=2)) == ['A', 'B']


def test_build_mass_prompt_lists_all_and_array_format():
    from server.services.anforderung_prompt import build_mass_anforderung_prompt
    selected = [{'id': 'A', 'req': {'titel': 'Titel A', 'beschreibung': 'desc-a'}, 'current': {'bewertung': 1}},
                {'id': 'B', 'req': {'titel': 'Titel B', 'beschreibung': 'desc-b'}, 'current': {'bewertung': 3}}]
    p = build_mass_anforderung_prompt('CRA', 'Cyber Resilience Act', selected, {'unternehmen': 'ACME'})
    assert 'A — Titel A' in p and 'B — Titel B' in p
    assert 'JSON-Array' in p and '"id"' in p and '"score"' in p
    assert 'desc-a' in p and 'ACME' in p


def test_parse_mass_response_skips_invalid_and_normalizes():
    from server.services.anforderung_prompt import parse_mass_response
    raw = """Hier das Ergebnis:
```json
[
  {"id": "A", "score": 4, "kommentar": "gut", "massnahmen": ["m1", "m2"], "normbezug": "Art. 13"},
  {"score": 3, "kommentar": "keine id -> raus"},
  {"id": "B", "score": 9, "kommentar": "über 5 -> geklemmt"}
]
```"""
    out = parse_mass_response(raw)
    assert [o['id'] for o in out] == ['A', 'B']
    assert out[0]['score'] == 4 and 'm1' in out[0]['massnahme']
    assert out[0]['normbezug'] == 'Art. 13'
    assert out[1]['score'] == 5  # 9 -> auf 5 geklemmt


def test_parse_mass_response_garbage_returns_empty():
    from server.services.anforderung_prompt import parse_mass_response
    assert parse_mass_response('kein json') == []


# ── CRA-Endpoints: mass-prompt → mass-preview ───────────────────────────────

class TestCraMassEndpoints:
    BASE = '/api/cra'
    PROJ = 'pytest-mass-cra-1528'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from cra.requirements import CRA_ANFORDERUNGEN
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'unternehmen': 'ACME'})
        ids = [str(r['id']) for r in CRA_ANFORDERUNGEN[:3]]
        # erste Anforderung vollständig (Score 5) → aus "only_open" ausgeschlossen
        client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                    json={'anforderung_id': ids[0], 'bewertung': 5, 'kommentar': 'fertig'})
        yield ids
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)

    def test_mass_prompt_only_open_excludes_complete(self, client, auth_headers, projekt):
        ids = projekt
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/anforderungen/mass-prompt',
                        headers=auth_headers, json={'only_open': True, 'limit': 5})
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        got = {a['id'] for a in body['anforderungen']}
        assert ids[0] not in got          # Score 5 ausgeschlossen
        assert 'JSON-Array' in body['prompt']

    def test_mass_prompt_req_ids_selection(self, client, auth_headers, projekt):
        ids = projekt
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/anforderungen/mass-prompt',
                        headers=auth_headers, json={'req_ids': [ids[1], ids[2]]})
        assert r.status_code == 200, r.get_json()
        assert {a['id'] for a in r.get_json()['anforderungen']} == {ids[1], ids[2]}

    def test_mass_preview_parses_and_maps(self, client, auth_headers, projekt):
        ids = projekt
        arr = json.dumps([{'id': ids[1], 'score': 4, 'kommentar': 'ok', 'massnahmen': ['x']}])
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/anforderungen/mass-preview',
                        headers=auth_headers, json={'response': f'```json\n{arr}\n```'})
        assert r.status_code == 200, r.get_json()
        items = r.get_json()['items']
        assert len(items) == 1 and items[0]['id'] == ids[1]
        assert items[0]['bewertung'] == 4 and items[0]['titel']

    def test_mass_prompt_empty_selection_400(self, client, auth_headers, projekt):
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/anforderungen/mass-prompt',
                        headers=auth_headers, json={'req_ids': ['GIBT-ES-NICHT']})
        assert r.status_code == 400


# ── WiBA: reine Lib (Katalog ist im Test-PG nicht geladen) ──────────────────

def test_wiba_build_mass_control_prompt_and_parse():
    from wiba.prompts import build_mass_control_prompt, parse_json_antwort
    ctrls = [{'control_id': 'orga-1', 'frage': 'Leitlinie vorhanden?', 'theme_titel': 'Organisation', 'bausteine': 'ORP.1'},
             {'control_id': 'orga-2', 'frage': 'IT-Verantwortlicher benannt?', 'theme_titel': 'Organisation'}]
    p = build_mass_control_prompt(ctrls)
    assert 'orga-1' in p and 'orga-2' in p and 'JSON-Array' in p and 'ORP.1' in p
    parsed = parse_json_antwort('```json\n[{"control_id":"orga-1","status":"ja","notiz":"da"},'
                                '{"control_id":"orga-2","status":"nein"}]\n```')
    assert [(x['control_id'], x['status']) for x in parsed] == [('orga-1', 'ja'), ('orga-2', 'nein')]
