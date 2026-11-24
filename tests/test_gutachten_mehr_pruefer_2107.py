"""#2107 — Mehr-Prüfer-Verfahren im Gutachten + Privatgutachten-Normen.

Deckt ab:
- #2108 Prüfer-Register (Rollen-Invariante: genau ein Hauptgutachter)
- #2109 Autorenschaft (Teil-Update erhält den Autor)
- #2110 Gegenseitiges Review (Vier-Augen: kein Review des eigenen Inhalts)
- #2111 Mehrfach-Selbstprüfung (Vier-Augen: keine Selbst-Bestätigung)
- #2112 Projekt-Normen (ISO/BSI aus der Bibliothek hinterlegbar)
- #2113 Privatgutachten: Methodische Grundlage statt ZPO
"""
from pathlib import Path

import pytest

from gutachten import gerichts_db as gdb
from gutachten import gerichtsgutachten_gen as gen
from gutachten import normen as _normen

GUT = '/api/gutachten'


@pytest.fixture
def db():
    p = Path(__file__).resolve().parent.parent / 'data' / 'db' / 'pytest_mehr_pruefer_2107.sqlite'
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


def _seed_privat(db, name):
    gdb.save_gerichts_projekt(db, name=name, gutachten_art='privat',
                              auftraggeber='Firma X', auftrags_art='Schaden-Gutachten',
                              sv_name='Dr. Haupt', thema='Thema')


def _alltext(doc):
    parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


# ── #2108 Prüfer-Register ───────────────────────────────────────────────────

def test_pruefer_rollen_invariante(db):
    _seed_privat(db, 'P1')
    h = gdb.save_pruefer(db, projekt_name='P1', name='Dr. Haupt', rolle='hauptgutachter')
    z = gdb.save_pruefer(db, projekt_name='P1', name='Ing. Zwei', rolle='zweitpruefer')
    # Zweiter Hauptgutachter stuft den ersten auf 'weiterer' zurück (genau einer)
    h2 = gdb.save_pruefer(db, projekt_name='P1', name='Dr. Neu', rolle='hauptgutachter')
    rollen = {p['id']: p['rolle'] for p in gdb.list_pruefer(db, 'P1')}
    haupt = [pid for pid, r in rollen.items() if r == 'hauptgutachter']
    assert haupt == [h2]
    assert rollen[h] == 'weiterer'
    assert rollen[z] == 'zweitpruefer'


def test_pruefer_name_aus_profil(db):
    _seed_privat(db, 'P2')
    pid = gdb.save_gutachter(db, name='Prof. Aus Profil', zertifizierung='zert')
    p = gdb.save_pruefer(db, projekt_name='P2', gutachter_profil_id=pid, rolle='zweitpruefer')
    row = gdb.get_pruefer(db, p)
    assert row['name'] == 'Prof. Aus Profil'


# ── #2109 Autorenschaft ─────────────────────────────────────────────────────

def test_autor_bleibt_bei_teilupdate_befund(db):
    _seed_privat(db, 'A1')
    h = gdb.save_pruefer(db, projekt_name='A1', name='Dr. Haupt', rolle='hauptgutachter')
    bid = gdb.save_befund(db, projekt_name='A1', nr='4.1', titel='B', autor_pruefer_id=h)
    # Update OHNE autor_pruefer_id darf den Autor NICHT leeren (Lehre #1771/#1805)
    gdb.save_befund(db, id=bid, projekt_name='A1', nr='4.1', titel='B neu')
    row = [b for b in gdb.list_befunde(db, 'A1') if b['id'] == bid][0]
    assert row['autor_pruefer_id'] == h


def test_autor_bleibt_bei_teilupdate_beurteilung(db):
    _seed_privat(db, 'A2')
    z = gdb.save_pruefer(db, projekt_name='A2', name='Ing', rolle='zweitpruefer')
    uid = gdb.save_beurteilung(db, projekt_name='A2', nr='5.1', titel='U', autor_pruefer_id=z)
    gdb.save_beurteilung(db, id=uid, projekt_name='A2', nr='5.1', titel='U neu')
    row = [u for u in gdb.list_beurteilungen(db, 'A2') if u['id'] == uid][0]
    assert row['autor_pruefer_id'] == z


# ── #2110 Gegenseitiges Review (Vier-Augen) über die REST-Schicht ───────────

def _api_seed(client, auth_headers, name):
    rp = client.post(f'{GUT}/gerichts', json={'name': name, 'gutachten_art': 'privat',
                     'auftraggeber': 'X', 'auftrags_art': 'Schaden-Gutachten',
                     'sv_name': 'Dr'}, headers=auth_headers)
    assert rp.status_code == 201, (rp.status_code, rp.json)
    rh = client.post(f'{GUT}/gerichts/{name}/pruefer',
                     json={'name': 'Dr. Haupt', 'rolle': 'hauptgutachter'},
                     headers=auth_headers)
    assert rh.status_code == 201, (rh.status_code, rh.json)
    rz = client.post(f'{GUT}/gerichts/{name}/pruefer',
                     json={'name': 'Ing. Zwei', 'rolle': 'zweitpruefer'},
                     headers=auth_headers)
    assert rz.status_code == 201, (rz.status_code, rz.json)
    return rh.json['id'], rz.json['id']


def test_itemreview_vier_augen(client, auth_headers):
    name = 'REV1'
    h, z = _api_seed(client, auth_headers, name)
    bid = client.post(f'{GUT}/gerichts/{name}/befunde',
                      json={'nr': '4.1', 'titel': 'B', 'autor_pruefer_id': h},
                      headers=auth_headers).json['id']
    # Autor (h) reviewt seinen eigenen Befund -> 409
    r = client.post(f'{GUT}/gerichts/{name}/itemreviews',
                    json={'objekt_art': 'befund', 'objekt_id': bid,
                          'reviewer_pruefer_id': h, 'status': 'ok'},
                    headers=auth_headers)
    assert r.status_code == 409, r.json
    assert r.json.get('code') == 'vier_augen'
    # Zweitprüfer (z) reviewt den Befund -> 201
    r2 = client.post(f'{GUT}/gerichts/{name}/itemreviews',
                     json={'objekt_art': 'befund', 'objekt_id': bid,
                           'reviewer_pruefer_id': z, 'status': 'ok',
                           'kommentar': 'Nachvollziehbar.'},
                     headers=auth_headers)
    assert r2.status_code == 201, r2.json
    lst = client.get(f'{GUT}/gerichts/{name}/itemreviews', headers=auth_headers).json['itemreviews']
    assert len(lst) == 1 and lst[0]['status'] == 'ok'


# ── #2111 Mehrfach-Selbstprüfung (Vier-Augen) ───────────────────────────────

def test_selbstpruefung_bestaetigen_vier_augen(client, auth_headers):
    name = 'SP1'
    h, z = _api_seed(client, auth_headers, name)
    sid = client.post(f'{GUT}/gerichts/{name}/selbstpruefung',
                      json={'pruefer_id': h, 'status': 'bestanden',
                            'headline': 'Keine Befangenheit'},
                      headers=auth_headers).json['id']
    # Eigene Selbstprüfung bestätigen -> 409
    r = client.post(f'{GUT}/gerichts/selbstpruefung/{sid}/bestaetigen',
                    json={'pruefer_id': h}, headers=auth_headers)
    assert r.status_code == 409, r.json
    # Anderer Prüfer bestätigt -> 200
    r2 = client.post(f'{GUT}/gerichts/selbstpruefung/{sid}/bestaetigen',
                     json={'pruefer_id': z}, headers=auth_headers)
    assert r2.status_code == 200, r2.json
    lst = client.get(f'{GUT}/gerichts/{name}/selbstpruefung', headers=auth_headers).json['selbstpruefung']
    best = [s for s in lst if s['id'] == sid][0]['bestaetigt']
    assert any(int(b['pruefer_id']) == int(z) for b in best)


# ── #2112 Projekt-Normen ────────────────────────────────────────────────────

def test_bibliothek_enthaelt_iso_und_bsi():
    ids = {n['id'] for n in _normen.list_normen()}
    for need in ('iso-17025', 'iso-27001', 'iso-27041', 'iso-9001',
                 'bsi-200-1', 'bsi-200-2', 'bsi-grundschutz'):
        assert need in ids, need


def test_projekt_normen_crud(db):
    _seed_privat(db, 'N1')
    nid = gdb.save_projekt_norm(db, projekt_name='N1', norm_id='din-en-16775',
                                norm_titel='DIN EN 16775', version='2016')
    gdb.save_projekt_norm(db, projekt_name='N1', norm_id='bsi-200-2',
                          norm_titel='BSI-Standard 200-2')
    lst = gdb.list_projekt_normen(db, 'N1')
    assert {n['norm_id'] for n in lst} == {'din-en-16775', 'bsi-200-2'}
    gdb.delete_projekt_norm(db, nid)
    assert {n['norm_id'] for n in gdb.list_projekt_normen(db, 'N1')} == {'bsi-200-2'}


# ── #2113 Privatgutachten-Rechtsgrundlage ───────────────────────────────────

def test_privat_hat_methodische_grundlage_ohne_zpo(db):
    _seed_privat(db, 'PG1')
    gdb.save_pruefer(db, projekt_name='PG1', name='Dr. Haupt', rolle='hauptgutachter')
    gdb.save_projekt_norm(db, projekt_name='PG1', norm_id='din-en-16775',
                          norm_titel='DIN EN 16775', version='2016')
    txt = _alltext(gen.build_gerichtsgutachten_docx('PG1', db))
    assert 'Methodische Grundlage' in txt
    assert 'DIN EN 16775' in txt
    assert '§ 407a' not in txt and '§ 406 ZPO' not in txt


def test_gericht_behaelt_zpo(db):
    gdb.save_gerichts_projekt(db, name='GG1', gutachten_art='gericht', gericht='LG',
                              aktenzeichen='1 O 2/26', sv_name='Dr')
    gdb.save_verfahrensereignis(db, projekt_name='GG1', ereignis_typ='selbstcheck',
                                titel='Selbstcheck', beschreibung='Keine Vorbefassung.')
    txt = _alltext(gen.build_gerichtsgutachten_docx('GG1', db))
    assert '§ 406 ZPO' in txt or '§ 407a' in txt


def test_verfasser_im_report_bei_mehreren_pruefern(db):
    _seed_privat(db, 'VF1')
    gdb.save_pruefer(db, projekt_name="VF1", name="Dr. Haupt", rolle="hauptgutachter")
    z = gdb.save_pruefer(db, projekt_name='VF1', name='Ing. Zwei', rolle='zweitpruefer')
    gdb.save_befund(db, projekt_name='VF1', nr='4.1', titel='B', autor_pruefer_id=z)
    txt = _alltext(gen.build_gerichtsgutachten_docx('VF1', db))
    assert 'Verfasser' in txt and 'Ing. Zwei' in txt
