"""Tests #1200: CRA Art. 19-22 Wirtschaftsakteure-Register.

- cra_akteure-Tabelle mit Rolle + Projekt-Verknüpfung.
- Rollen-spezifische Pflicht-Checklisten (Importeur/Händler/Bevollmächtigter).
- Mandats-/Nachweis-Referenz + Status.
- Endpoints GET/POST/PUT/DELETE /projekte/<p>/akteure (IDOR-scoped).
"""
import pytest

CRA = '/api/cra'
AKT = '/api/cra-akteure'
FIRMA = 'pytest-firma-1200'
PROJ = 'pytest-cra-1200'


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


# ── Konstanten / Checklisten ──────────────────────────────────────────────────

def test_constants(client, auth_headers):
    r = client.get(f'{AKT}/constants', headers=auth_headers)
    assert r.status_code == 200
    assert 'importeur' in r.json['rollen'] and 'bevollmaechtigter' in r.json['rollen']
    # Importeur: CE+DoC+Annex-II-Pflichtnachweise
    imp = r.json['checkliste']['importeur']
    assert 'ce_kennzeichnung_geprueft' in imp
    assert 'doc_aufbewahrung_10_jahre' in imp
    # Bevollmächtigter: schriftliches Mandat
    assert 'schriftliches_mandat_vorhanden' in r.json['checkliste']['bevollmaechtigter']


# ── DB-Ebene (tmp-DB) ─────────────────────────────────────────────────────────

def test_rollen_checkliste_vollstaendigkeit(tmp_path):
    from cra import akteure_db as adb
    db = tmp_path / 'cra.sqlite'
    aid = adb.create_akteur(db, PROJ, {'rolle': 'haendler', 'name': 'Distri GmbH'})
    a = adb.get_akteur(db, aid, PROJ)
    assert a['rolle'] == 'haendler'
    assert a['soll_nachweise']  # Händler-Checkliste vorhanden
    assert a['checkliste_vollstaendig'] is False
    # Alle Soll-Nachweise abhaken → vollständig
    cl = {n: True for n in a['soll_nachweise']}
    adb.update_akteur(db, aid, PROJ, {'checkliste': cl})
    a2 = adb.get_akteur(db, aid, PROJ)
    assert a2['checkliste_vollstaendig'] is True


def test_invalid_rolle(tmp_path):
    from cra import akteure_db as adb
    db = tmp_path / 'cra.sqlite'
    with pytest.raises(ValueError):
        adb.create_akteur(db, PROJ, {'rolle': 'hersteller'})


# ── Endpoints ─────────────────────────────────────────────────────────────────

def test_akteur_crud_api(client, auth_headers, projekt):
    r = client.post(f'{AKT}/projekte/{projekt}/akteure', headers=auth_headers,
                    json={'rolle': 'bevollmaechtigter', 'name': 'EU-Rep Ltd',
                          'aufgabenumfang': 'DoC vorhalten',
                          'mandat_ref': 'MANDAT-2026-01'})
    assert r.status_code == 201, r.json
    aid = r.json['id']
    assert r.json['rolle'] == 'bevollmaechtigter'
    assert 'schriftliches_mandat_vorhanden' in r.json['soll_nachweise']

    r = client.put(f'{AKT}/projekte/{projekt}/akteure/{aid}', headers=auth_headers,
                   json={'status': 'konform'})
    assert r.status_code == 200, r.json
    assert r.json['status'] == 'konform'

    r = client.get(f'{AKT}/projekte/{projekt}/akteure', headers=auth_headers)
    assert r.status_code == 200 and len(r.json) == 1

    r = client.delete(f'{AKT}/projekte/{projekt}/akteure/{aid}', headers=auth_headers)
    assert r.status_code == 200
    r = client.get(f'{AKT}/projekte/{projekt}/akteure', headers=auth_headers)
    assert len(r.json) == 0


def test_idor_scoped(client, auth_headers, projekt):
    r = client.post(f'{AKT}/projekte/{projekt}/akteure', headers=auth_headers,
                    json={'rolle': 'importeur', 'name': 'X'})
    aid = r.json['id']
    # falsches Projekt → 404
    r = client.get(f'{AKT}/projekte/fremd-projekt/akteure/{aid}', headers=auth_headers)
    assert r.status_code == 404
    r = client.put(f'{AKT}/projekte/fremd-projekt/akteure/{aid}', headers=auth_headers,
                   json={'status': 'konform'})
    assert r.status_code == 404
