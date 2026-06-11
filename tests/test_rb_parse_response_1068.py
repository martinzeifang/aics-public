"""#1068 — Einzelbewertung: ungültiges JSON liefert 400 (nicht 500)."""
from pathlib import Path

import pytest

from server.api.risikobewertung import DB_PATH
from risikobewertung.db import save_projekt, save_risiko, delete_projekt

PROJ = 'pytest-rb-parse-1068'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def risk_id():
    delete_projekt(DB_PATH, PROJ)
    save_projekt(DB_PATH, PROJ, framework='STRIDE', beschreibung='', unternehmen='ACME')
    rid = save_risiko(DB_PATH, {'projekt_name': PROJ, 'nr': 1, 'risk_name': 'X',
                                'framework': 'STRIDE'})
    yield rid
    delete_projekt(DB_PATH, PROJ)
    import sqlite3
    con = sqlite3.connect(str(DB_PATH))
    con.execute("DELETE FROM rb_risiken WHERE projekt_name=?", (PROJ,))
    con.commit(); con.close()


def _u(rid):
    return f'/api/risikobewertung/projekte/{PROJ}/risiken/{rid}/parse-response'


def test_invalid_json_returns_400(client, auth_headers, risk_id):
    r = client.post(_u(risk_id), json={'raw': 'das ist kein JSON'}, headers=auth_headers)
    assert r.status_code == 400, r.get_json()
    assert 'JSON' in r.get_json()['error']


def test_single_quote_json_returns_400_not_500(client, auth_headers, risk_id):
    r = client.post(_u(risk_id), json={'raw': "{'felder': {}}"}, headers=auth_headers)
    assert r.status_code == 400


def test_valid_json_still_ok(client, auth_headers, risk_id):
    raw = '{"felder": {"stride_kategorie": "Tampering (T) – Manipulation von Daten", ' \
          '"eintrittswahrscheinlichkeit": "Möglich", "auswirkung": "Hoch"}, "bewertung": "ok"}'
    r = client.post(_u(risk_id), json={'raw': raw, 'apply': False}, headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['risikowert'] is not None
