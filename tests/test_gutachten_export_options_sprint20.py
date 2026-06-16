"""Sprint #20 Block A — Export-Optionen (#967/#968) + Vertraulichkeits-Lock (#966)."""
from pathlib import Path

import pytest

from gutachten import gerichts_db as gdb
from gutachten import gerichtsgutachten_gen as gen

GUT = '/api/gutachten'


@pytest.fixture
def db():
    p = Path(__file__).resolve().parent.parent / 'data' / 'db' / 'pytest_exportopts_20.sqlite'
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


def _all_text(doc):
    return "\n".join(p.text for p in doc.paragraphs)


def _seed(db, name='GG-OPT', status='in_bearbeitung'):
    gdb.save_gerichts_projekt(db, name=name, gutachten_art='gericht', gericht='LG',
                              aktenzeichen='1/26', sv_name='Dr. SV', status=status,
                              vertraulichkeit='STRENG VERTRAULICH')
    gdb.save_beweisfrage(db, projekt_name=name, nr=1, frage_text='F?')
    gdb.save_befund(db, projekt_name=name, nr='4.1', titel='Befund A',
                    methode='statisch', werkzeug_name='Tool', beschreibung_text='x')
    gdb.save_beurteilung(db, projekt_name=name, nr='5.1', titel='Beurteilung A',
                         soll_text='soll', ist_text='ist', bewertung_text='wert')


# ── #967/#968 Export-Optionen ──────────────────────────────────────────────

def test_default_export_has_methode_and_subheadings(db):
    _seed(db)
    txt = _all_text(gen.build_gerichtsgutachten_docx('GG-OPT', db))
    assert 'Methode' in txt and 'Werkzeug' in txt
    assert 'Soll (Stand der Technik):' in txt


def test_toggle_off_methode_werkzeug(db):
    _seed(db)
    txt = _all_text(gen.build_gerichtsgutachten_docx(
        'GG-OPT', db, export_options={'include_methode_werkzeug': False}))
    # Methode-/Werkzeug-WERTE des Befunds dürfen nicht erscheinen (Labels „Werkzeug"
    # kommen im KI-Hinweis/ToC vor → auf Werte prüfen).
    assert 'statisch' not in txt  # methode-Wert
    assert 'Tool' not in txt      # werkzeug_name-Wert
    assert 'Befund A' in txt      # Befund selbst bleibt


def test_default_keeps_methode_values(db):
    _seed(db)
    txt = _all_text(gen.build_gerichtsgutachten_docx('GG-OPT', db))
    assert 'statisch' in txt and 'Tool' in txt


def test_toggle_off_beurteilung_subheadings(db):
    _seed(db)
    txt = _all_text(gen.build_gerichtsgutachten_docx(
        'GG-OPT', db, export_options={'include_beurteilung_subheadings': False}))
    assert 'Soll (Stand der Technik):' not in txt
    assert 'Ist (Befund-Vergleich):' not in txt
    # Texte selbst bleiben erhalten
    assert 'soll' in txt and 'ist' in txt


def test_anhang_toggle_via_options(db):
    _seed(db)
    txt = _all_text(gen.build_gerichtsgutachten_docx(
        'GG-OPT', db, export_options={'include_anhang': False}))
    assert 'VIII. Anhang' not in txt


# ── #966 Vertraulichkeits-Lock (API) ───────────────────────────────────────

PROJ = 'pytest-vlock-966'


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{GUT}/gerichts/{PROJ}', headers=auth_headers)
    client.post(f'{GUT}/gerichts', headers=auth_headers, json={
        'name': PROJ, 'gutachten_art': 'gericht', 'gericht': 'LG', 'aktenzeichen': '9/26',
        'sv_name': 'Dr. SV', 'vertraulichkeit': 'STRENG VERTRAULICH'})
    yield PROJ
    client.delete(f'{GUT}/gerichts/{PROJ}', headers=auth_headers)


def test_vertraulichkeit_editable_in_bearbeitung(client, auth_headers, projekt):
    r = client.put(f'{GUT}/gerichts/{projekt}', headers=auth_headers,
                   json={'vertraulichkeit': 'INTERN'})
    assert r.status_code == 200, r.get_json()


# Voll-Body wie das Frontend (sonst setzt save_gerichts_projekt Felder zurück).
def _full(status, vertraulichkeit='STRENG VERTRAULICH'):
    return {'status': status, 'vertraulichkeit': vertraulichkeit, 'gutachten_art': 'gericht',
            'gericht': 'LG', 'aktenzeichen': '9/26', 'sv_name': 'Dr. SV'}


def test_vertraulichkeit_locked_after_finalisiert(client, auth_headers, projekt):
    assert client.put(f'{GUT}/gerichts/{projekt}', headers=auth_headers,
                      json=_full('finalisiert')).status_code == 200
    # jetzt Vertraulichkeit ändern → 409
    r = client.put(f'{GUT}/gerichts/{projekt}', headers=auth_headers,
                   json=_full('finalisiert', 'ÖFFENTLICH'))
    assert r.status_code == 409
    assert r.get_json()['current_status'] == 'finalisiert'


def test_same_vertraulichkeit_after_final_ok(client, auth_headers, projekt):
    client.put(f'{GUT}/gerichts/{projekt}', headers=auth_headers, json=_full('finalisiert'))
    # unveränderter Wert → kein 409 (nur echte Änderung ist gesperrt)
    r = client.put(f'{GUT}/gerichts/{projekt}', headers=auth_headers, json=_full('finalisiert'))
    assert r.status_code == 200
