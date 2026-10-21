"""Sprint #19 — #955 Stammdaten (Gutachter + Hilfspersonen).

DB-CRUD + Projekt-Verknüpfung + Export-Integration (Kap. III) + REST.
"""
from pathlib import Path

import pytest

from gutachten import gerichts_db as gdb
from gutachten import gerichtsgutachten_gen as gen

GUT = '/api/gutachten'


@pytest.fixture
def db():
    repo_root = Path(__file__).resolve().parent.parent
    p = repo_root / 'data' / 'db' / 'pytest_stammdaten_955.sqlite'
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.unlink()
    gdb.ensure_db(p)
    yield p
    if p.exists():
        p.unlink()


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['gutachten']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ── DB-Schicht ─────────────────────────────────────────────────────────────

def test_gutachter_crud(db):
    gid = gdb.save_gutachter(db, name='Dr. Max SV', zertifizierung='BISG', email='m@x.de')
    rows = gdb.list_gutachter(db)
    assert len(rows) == 1 and rows[0]['name'] == 'Dr. Max SV' and rows[0]['email'] == 'm@x.de'
    gdb.save_gutachter(db, id=gid, name='Dr. Max SV', email='neu@x.de')
    assert gdb.list_gutachter(db)[0]['email'] == 'neu@x.de'
    gdb.delete_gutachter(db, gid)
    assert gdb.list_gutachter(db) == []


def test_gutachter_name_required(db):
    with pytest.raises(ValueError):
        gdb.save_gutachter(db, name='')


def test_hilfsperson_link_and_list(db):
    gdb.save_gerichts_projekt(db, name='GG-955', gutachten_art='gericht',
                              gericht='LG', aktenzeichen='1/26', sv_name='S')
    h1 = gdb.save_hilfsperson(db, name='Anna Forensik', rolle='Forensikerin')
    h2 = gdb.save_hilfsperson(db, name='Ben Recherche', rolle='Recherche')
    gdb.link_hilfspersonen(db, 'GG-955', [
        {'hilfsperson_id': h1, 'aufgabe': 'Datenträger-Imaging'},
        {'hilfsperson_id': h2, 'aufgabe': 'Quellenrecherche'},
    ])
    linked = gdb.list_hilfspersonen_for_projekt(db, 'GG-955')
    assert {x['name'] for x in linked} == {'Anna Forensik', 'Ben Recherche'}
    assert any(x['aufgabe'] == 'Datenträger-Imaging' for x in linked)
    # Re-Link ersetzt
    gdb.link_hilfspersonen(db, 'GG-955', [{'hilfsperson_id': h1, 'aufgabe': 'nur Imaging'}])
    linked2 = gdb.list_hilfspersonen_for_projekt(db, 'GG-955')
    assert len(linked2) == 1 and linked2[0]['aufgabe'] == 'nur Imaging'


def test_export_renders_hilfspersonen_in_kap3(db):
    gdb.save_gerichts_projekt(db, name='GG-955b', gutachten_art='gericht',
                              gericht='LG', aktenzeichen='2/26', sv_name='S')
    gdb.save_beweisfrage(db, projekt_name='GG-955b', nr=1, frage_text='F?')
    h1 = gdb.save_hilfsperson(db, name='Anna Forensik', rolle='Forensikerin')
    gdb.link_hilfspersonen(db, 'GG-955b', [{'hilfsperson_id': h1, 'aufgabe': 'Imaging'}])
    doc = gen.build_gerichtsgutachten_docx('GG-955b', db)
    txt = "\n".join(p.text for p in doc.paragraphs)
    assert 'Hinzugezogene Hilfspersonen' in txt
    assert 'Anna Forensik' in txt and 'Imaging' in txt


# ── REST ───────────────────────────────────────────────────────────────────

def test_gutachter_api_crud(client, auth_headers):
    # cleanup vorab
    for g in client.get(f'{GUT}/gutachter', headers=auth_headers).get_json().get('gutachter', []):
        if g['name'] == 'API-Gutachter-955':
            client.delete(f"{GUT}/gutachter/{g['id']}", headers=auth_headers)
    r = client.post(f'{GUT}/gutachter', headers=auth_headers,
                    json={'name': 'API-Gutachter-955', 'zertifizierung': 'BISG'})
    assert r.status_code == 201, r.get_json()
    gid = r.get_json()['id']
    names = [g['name'] for g in client.get(f'{GUT}/gutachter', headers=auth_headers).get_json()['gutachter']]
    assert 'API-Gutachter-955' in names
    assert client.delete(f'{GUT}/gutachter/{gid}', headers=auth_headers).status_code == 204


def test_gutachter_api_name_required(client, auth_headers):
    r = client.post(f'{GUT}/gutachter', headers=auth_headers, json={'name': ''})
    assert r.status_code == 400
