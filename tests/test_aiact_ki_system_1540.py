"""Epic #1540 — AI Act hybrid: Organisation (Firma) + KI-System je Produkt.

- #1541 Scope, KI-System-Anlage (idempotent, Konflikt 409), Projektliste mit scope,
        PUT erhält meta (Regression: meta_json wurde auf '{}' zurückgesetzt).
- #1542 AI-Literacy (Art. 4) firmenweit: KI-System liest/schreibt das Org-Register.
"""
import pytest

BASE = '/api/aiact'
LIT = '/api/aiact-literacy'
FIRMA = 'pytest-1540-firma'
SYSTEM = f'{FIRMA} – Chatbot'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _clear_literacy(*names):
    from shared import db as _sdb
    from server.api.aiact import DB_PATH
    from ai_act.ai_literacy import ensure_table
    try:
        ensure_table(DB_PATH)
    except Exception:
        pass
    with _sdb.connect(DB_PATH) as con:
        for n in names:
            con.execute("DELETE FROM aiact_ai_literacy WHERE projekt_name=?", (n,))


@pytest.fixture
def org(client, auth_headers):
    for n in (SYSTEM, FIRMA, f'{FIRMA} – Fremd'):
        client.delete(f'{BASE}/projekte/{n}', headers=auth_headers)
    _clear_literacy(FIRMA, SYSTEM)
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': FIRMA, 'organisation': FIRMA})
    assert r.status_code == 201, r.get_json()
    yield FIRMA
    for n in (SYSTEM, FIRMA, f'{FIRMA} – Fremd'):
        client.delete(f'{BASE}/projekte/{n}', headers=auth_headers)
    _clear_literacy(FIRMA, SYSTEM)


def test_legacy_projekt_is_organisation(client, auth_headers, org):
    d = client.get(f'{BASE}/projekte/{org}/scope', headers=auth_headers).get_json()
    assert d['scope'] == 'organisation'
    assert d['org_projekt'] == org and d['firma'] == org
    assert d['systeme'] == []


def test_create_system_idempotent_and_listed(client, auth_headers, org):
    r = client.post(f'{BASE}/projekte/{org}/systeme', headers=auth_headers,
                    json={'produkt': 'Chatbot', 'beschreibung': 'LLM-Support'})
    assert r.status_code == 201, r.get_json()
    p = r.get_json()
    assert p['name'] == SYSTEM and p['scope'] == 'system'
    assert p['organisation'] == FIRMA and p['produkt'] == 'Chatbot'

    again = client.post(f'{BASE}/projekte/{org}/systeme', headers=auth_headers,
                        json={'produkt': 'Chatbot'})
    assert again.status_code == 200 and again.get_json()['created'] is False

    # Aus dem KI-System heraus: Scope zeigt auf die Organisation.
    d = client.get(f'{BASE}/projekte/{SYSTEM}/scope', headers=auth_headers).get_json()
    assert d['scope'] == 'system' and d['org_projekt'] == FIRMA
    assert [s['name'] for s in d['systeme']] == [SYSTEM]

    lst = {p['name']: p for p in client.get(f'{BASE}/projekte', headers=auth_headers).get_json()}
    assert lst[SYSTEM]['scope'] == 'system' and lst[FIRMA]['scope'] == 'organisation'


def test_create_system_validation_and_conflict(client, auth_headers, org):
    assert client.post(f'{BASE}/projekte/{org}/systeme', headers=auth_headers,
                       json={}).status_code == 400
    assert client.post(f'{BASE}/projekte/gibt-es-nicht-1540/systeme', headers=auth_headers,
                       json={'produkt': 'X'}).status_code == 404
    # Fremdes (Nicht-System-)Projekt belegt den Namen → 409
    client.post(f'{BASE}/projekte', headers=auth_headers, json={'name': f'{FIRMA} – Fremd'})
    assert client.post(f'{BASE}/projekte/{org}/systeme', headers=auth_headers,
                       json={'produkt': 'Fremd'}).status_code == 409


def test_put_preserves_meta(client, auth_headers, org):
    client.post(f'{BASE}/projekte/{org}/systeme', headers=auth_headers, json={'produkt': 'Chatbot'})
    r = client.put(f'{BASE}/projekte/{SYSTEM}', headers=auth_headers,
                   json={'beschreibung': 'neu'})
    assert r.status_code == 200
    assert r.get_json()['scope'] == 'system'          # meta.scope überlebt den PUT


def test_literacy_is_inherited_from_organisation(client, auth_headers, org):
    client.post(f'{BASE}/projekte/{org}/systeme', headers=auth_headers, json={'produkt': 'Chatbot'})
    # Im KI-System erfasst …
    r = client.post(f'{LIT}/projekte/{SYSTEM}/nachweise', headers=auth_headers,
                    json={'person': 'A. Muster', 'gueltig_bis': '2099-01-01'})
    assert r.status_code == 201, r.get_json()
    client.put(f'{LIT}/projekte/{SYSTEM}/konzept', headers=auth_headers,
               json={'konzept': 'Firmenweites Konzept'})
    # … landet im Organisations-Register.
    o = client.get(f'{LIT}/projekte/{FIRMA}/literacy', headers=auth_headers).get_json()
    assert [n['person'] for n in o['nachweise']] == ['A. Muster']
    assert o['konzept']['konzept'] == 'Firmenweites Konzept'
    assert o['inherited'] is False
    s = client.get(f'{LIT}/projekte/{SYSTEM}/literacy', headers=auth_headers).get_json()
    assert s['inherited'] is True and s['resolved_projekt'] == FIRMA
    assert [n['person'] for n in s['nachweise']] == ['A. Muster']
    # KI-System bleibt Projekt mit scope=system (Konzept-Save darf meta nicht zerstören)
    assert client.get(f'{BASE}/projekte/{SYSTEM}/scope',
                      headers=auth_headers).get_json()['scope'] == 'system'
