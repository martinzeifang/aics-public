"""#1560 CRA-Auswahl · #1561 HR-01 über Risikobewertung · #1562 Organisation ohne System-Controls."""
import pytest

BASE = '/api/aiact'
FIRMA = 'pytest-1562-firma'
SYSTEM = f'{FIRMA} – Bot'
CRA = f'{FIRMA} – Bot'          # gleiches Namensschema wie CRA #435
RB_PREFIX = f'{FIRMA}'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _cleanup(client, h):
    for n in (SYSTEM, FIRMA):
        client.delete(f'{BASE}/projekte/{n}', headers=h)
    client.delete(f'/api/cra/projekte/{CRA}', headers=h)
    from risikobewertung.db import list_projekte, delete_projekt
    from server.api.aiact import _RB_DB_PATH
    for n in list_projekte(_RB_DB_PATH):
        if n.startswith(RB_PREFIX):
            delete_projekt(_RB_DB_PATH, n)


@pytest.fixture
def org(client, auth_headers):
    _cleanup(client, auth_headers)
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': FIRMA, 'organisation': FIRMA})
    assert r.status_code == 201
    yield FIRMA
    _cleanup(client, auth_headers)


# ── #1560 ─────────────────────────────────────────────────────────────────────

def test_cra_projekte_lists_all_and_suggests_product(client, auth_headers, org):
    client.post('/api/cra/projekte', headers=auth_headers,
                json={'name': CRA, 'unternehmen': FIRMA, 'produkt': 'Bot'})
    client.post(f'{BASE}/projekte/{org}/systeme', headers=auth_headers, json={'produkt': 'Bot'})
    r = client.get('/api/aiact-conformity/cra-projekte', headers=auth_headers,
                   query_string={'projekt': SYSTEM})
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert CRA in d['projekte']                       # ohne Konformitäts-Eintrag gelistet
    assert d['projekte'][0] == CRA and d['vorschlag'] == CRA


# ── #1561 ─────────────────────────────────────────────────────────────────────

def test_hr01_score_follows_risk_content():
    from ai_act.risk_link import risk_stats, score_from_stats
    s = lambda rs: score_from_stats(risk_stats(rs))
    assert s([]) == 1
    assert s([{'risikowert': None}]) == 2
    hoch = {'risikowert': 16, 'risiko_label': 'Hoch'}
    assert s([hoch, {**hoch}]) == 3
    assert s([hoch, {**hoch, 'is_resolved': 1}]) == 4
    assert s([{**hoch, 'is_resolved': 1}, {'risikowert': 3, 'risiko_label': 'Niedrig'}]) == 5


def test_create_link_and_apply_hr01(client, auth_headers, org):
    r = client.post(f'{BASE}/projekte/{org}/risk-link/create', headers=auth_headers)
    assert r.status_code == 201, r.get_json()
    rb = r.get_json()['linked_risk_projekt']
    assert r.get_json()['hr01']['score'] == 1          # leer → 1, nicht pauschal 5
    assert client.post(f'{BASE}/projekte/{org}/risk-link/create',
                       headers=auth_headers).status_code == 409
    from risikobewertung.db import load_projekt as rb_load
    from server.api.aiact import _RB_DB_PATH
    assert rb_load(_RB_DB_PATH, rb)['framework'] == 'EU-AI-Act'

    a = client.post(f'{BASE}/projekte/{org}/anforderungen/AIA-HR-01/apply-risk-link',
                    headers=auth_headers)
    assert a.status_code == 200, a.get_json()
    from ai_act.db import load_bewertungen
    from server.api.aiact import DB_PATH
    b = load_bewertungen(DB_PATH, org)['AIA-HR-01']
    assert int(b['bewertung']) == 1 and 'Art. 9' in b['kommentar']
    # erneute Übernahme ersetzt den Block statt ihn zu doppeln
    client.post(f'{BASE}/projekte/{org}/anforderungen/AIA-HR-01/apply-risk-link', headers=auth_headers)
    assert load_bewertungen(DB_PATH, org)['AIA-HR-01']['kommentar'].count('Risikomanagement-System (Art. 9)') == 1


# ── #1562 ─────────────────────────────────────────────────────────────────────

def test_org_locked_after_first_system_with_copy(client, auth_headers, org):
    from ai_act.db import save_bewertung, load_bewertungen
    from server.api.aiact import DB_PATH
    save_bewertung(DB_PATH, projekt_name=org, anforderung_id='AIA-HR-03', bewertung=4, kommentar='Alt')
    sc = client.get(f'{BASE}/projekte/{org}/scope', headers=auth_headers).get_json()
    assert sc['locked'] is False and sc['org_has_data'] is True

    r = client.post(f'{BASE}/projekte/{org}/systeme', headers=auth_headers,
                    json={'produkt': 'Bot', 'uebernehmen': True})
    assert r.status_code == 201
    assert int(load_bewertungen(DB_PATH, SYSTEM)['AIA-HR-03']['bewertung']) == 4   # übernommen
    assert int(load_bewertungen(DB_PATH, org)['AIA-HR-03']['bewertung']) == 4      # Original bleibt

    assert client.get(f'{BASE}/projekte/{org}/scope', headers=auth_headers).get_json()['locked'] is True
    # System-Controls der Organisation sind gesperrt …
    w = client.post(f'{BASE}/projekte/{org}/anforderungen/AIA-HR-01/apply-risk-link', headers=auth_headers)
    assert w.status_code == 409 and w.get_json()['code'] == 'org_controls_locked'
    assert client.put(f'/api/aiact-art5/projekte/{org}/screening/x', headers=auth_headers,
                      json={}).status_code in (404, 405, 409)
    # … Stammdaten, KI-System-Anlage und Literacy bleiben erlaubt
    assert client.put(f'{BASE}/projekte/{org}', headers=auth_headers,
                      json={'beschreibung': 'neu'}).status_code == 200
    assert client.post(f'/api/aiact-literacy/projekte/{org}/nachweise', headers=auth_headers,
                       json={'person': 'X', 'gueltig_bis': '2099-01-01'}).status_code == 201
    # … und im KI-System ist alles schreibbar
    assert client.post(f'{BASE}/projekte/{SYSTEM}/risk-link/create',
                       headers=auth_headers).status_code == 201


def test_second_system_does_not_copy(client, auth_headers, org):
    from ai_act.db import save_bewertung, load_bewertungen
    from server.api.aiact import DB_PATH
    save_bewertung(DB_PATH, projekt_name=org, anforderung_id='AIA-HR-03', bewertung=4)
    client.post(f'{BASE}/projekte/{org}/systeme', headers=auth_headers, json={'produkt': 'Bot'})
    assert 'AIA-HR-03' not in load_bewertungen(DB_PATH, SYSTEM)   # ohne Option keine Kopie
