"""#1199 — AI-Act Art. 4 AI-Literacy-Register: Konzept, Nachweise, Ablauf-Ampel, A4-Link."""

import pytest

BASE = '/api/aiact'
LIT = '/api/aiact-literacy'
PROJ = 'pytest-literacy-1199'


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
        con.execute("DELETE FROM aiact_ai_literacy WHERE projekt_name=?", (projekt,))
        con.commit()
        con.close()
    except Exception:
        pass


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear(PROJ)
    r = client.post(f'{BASE}/projekte', headers=auth_headers, json={'name': PROJ})
    assert r.status_code in (200, 201), r.get_json()
    yield PROJ
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear(PROJ)


def test_empty_register(client, auth_headers, projekt):
    r = client.get(f'{LIT}/projekte/{PROJ}/literacy', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d['nachweise'] == []
    assert d['summary']['gesamt'] == 0
    assert 'oversight_personen' in d


def test_save_konzept(client, auth_headers, projekt):
    r = client.put(f'{LIT}/projekte/{PROJ}/konzept', headers=auth_headers,
                   json={'konzept': 'Abgestuftes KI-Kompetenz-Konzept'})
    assert r.status_code == 200, r.get_json()
    g = client.get(f'{LIT}/projekte/{PROJ}/literacy', headers=auth_headers).get_json()
    assert g['konzept']['konzept'] == 'Abgestuftes KI-Kompetenz-Konzept'
    assert g['konzept']['stand']  # Datum gesetzt


def test_crud_nachweis(client, auth_headers, projekt):
    r = client.post(f'{LIT}/projekte/{PROJ}/nachweise', headers=auth_headers,
                    json={'rolle': 'Entwickler', 'person': 'A. Muster',
                          'schulungsmodul': 'AI-Act Basics', 'kompetenzlevel': 'anwender',
                          'durchgefuehrt_am': '2026-01-01', 'gueltig_bis': '2099-01-01'})
    assert r.status_code == 201, r.get_json()
    pk = r.get_json()['id']
    lst = client.get(f'{LIT}/projekte/{PROJ}/literacy', headers=auth_headers).get_json()
    assert lst['summary']['gesamt'] == 1
    assert lst['nachweise'][0]['ablauf_status'] == 'gueltig'
    # Löschen
    d = client.delete(f'{LIT}/projekte/{PROJ}/nachweise/{pk}', headers=auth_headers)
    assert d.status_code == 200
    assert client.get(f'{LIT}/projekte/{PROJ}/literacy', headers=auth_headers).get_json()['summary']['gesamt'] == 0


def test_expired_status(client, auth_headers, projekt):
    client.post(f'{LIT}/projekte/{PROJ}/nachweise', headers=auth_headers,
                json={'person': 'B', 'gueltig_bis': '2000-01-01'})
    lst = client.get(f'{LIT}/projekte/{PROJ}/literacy', headers=auth_headers).get_json()
    assert lst['nachweise'][0]['ablauf_status'] == 'abgelaufen'
    assert lst['summary']['abgelaufen'] == 1


def test_invalid_level(client, auth_headers, projekt):
    r = client.post(f'{LIT}/projekte/{PROJ}/nachweise', headers=auth_headers,
                    json={'person': 'C', 'kompetenzlevel': 'guru'})
    assert r.status_code == 400


def test_oversight_personen_link(client, auth_headers, projekt):
    # A4-Oversight-Person setzen → muss als Vorschlag erscheinen.
    from ai_act.db import save_human_oversight
    from server.api.aiact import DB_PATH
    save_human_oversight(DB_PATH, PROJ, {
        'oversight_mode': 'human-in-the-loop',
        'oversight_persons': [{'rolle': 'Aufsicht', 'person': 'O. Verseher'}],
    })
    g = client.get(f'{LIT}/projekte/{PROJ}/literacy', headers=auth_headers).get_json()
    assert 'O. Verseher' in g['oversight_personen']
