"""Ein GET auf einen Release-Vorgang darf nichts anlegen (#1747-Fund).

Beim Bau der Oberfläche fiel auf, dass `GET /releases/<version>` den Vorgang
anlegte, wenn es keinen gab. Zwei Folgen: Ein Deep-Link mit Tippfehler in der
Version hinterlässt einen leeren Entwurf, und jeder Vorab-Abruf eines Browsers
schreibt in die Datenbank. Angelegt wird deshalb ausdrücklich per POST.
"""
import pytest

CRA = '/api/cra'
KONF = '/api/cra-konformitaet'
FIRMA = 'pytest-firma-1747'
PROJ = 'pytest-cra-1747'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': PROJ, 'unternehmen': FIRMA})
    yield PROJ
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)


def test_get_legt_nichts_an(client, auth_headers, projekt):
    r = client.get(f'{KONF}/projekte/{projekt}/releases/9.9.9', headers=auth_headers)
    assert r.status_code == 200, r.json
    assert r.json['vorgang'] is None and r.json['existiert'] is False
    # Die Ampel steht trotzdem zur Verfügung — man will wissen, wie der Stand
    # wäre, bevor man einen Vorgang eröffnet.
    assert r.json['gate']['ampel'] in ('gruen', 'bedingt', 'rot')
    assert r.json['katalog'] and r.json['stand']

    liste = client.get(f'{KONF}/projekte/{projekt}/releases', headers=auth_headers)
    versionen = [v['release_version'] for v in liste.json['releases']]
    assert '9.9.9' not in versionen, 'der GET hat einen Vorgang hinterlassen'


def test_post_legt_an_und_ist_idempotent(client, auth_headers, projekt):
    r = client.post(f'{KONF}/projekte/{projekt}/releases/1.2.3', headers=auth_headers)
    assert r.status_code == 200, r.json
    assert r.json['release_version'] == '1.2.3'
    assert r.json['freigabe_status'] == 'entwurf'

    r2 = client.post(f'{KONF}/projekte/{projekt}/releases/1.2.3', headers=auth_headers)
    assert r2.status_code == 200
    liste = client.get(f'{KONF}/projekte/{projekt}/releases', headers=auth_headers)
    treffer = [v for v in liste.json['releases'] if v['release_version'] == '1.2.3']
    assert len(treffer) == 1, treffer


def test_liste_liefert_phase_1_mit(client, auth_headers, projekt):
    """Das Frontend zeigt Phase 1 als eine Zeile über der Liste und soll dafür
    keinen zweiten Aufruf brauchen."""
    r = client.get(f'{KONF}/projekte/{projekt}/releases', headers=auth_headers)
    assert r.status_code == 200, r.json
    cr = r.json['cra_ready']
    assert cr['status'] == 'offen'
    assert 'ueberholt' in cr


def test_katalog_ohne_vorgang_abrufbar(client, auth_headers, projekt):
    r = client.get(f'{KONF}/projekte/{projekt}/releases/katalog', headers=auth_headers)
    assert r.status_code == 200
    arten = {i['art'] for i in r.json['katalog']}
    # `neubewertung` kam mit #1755 dazu (wesentliche Änderung, Art. 3 Nr. 30).
    assert arten == {'gerechnet', 'entscheidung', 'gleichbleibend',
                     'neubewertung'}
