"""Regressionstest #944: Gutachten-Name mit Schrägstrich.

Symptom: Ein Gutachten mit '/' im Namen wurde gespeichert, erschien in der
Liste, war aber nicht mehr auswählbar/löschbar → 404 "Not Found", weil der
Default-String-Converter der Route '/' nicht matcht.

Fix:
- save_gerichts_projekt lehnt '/' und '\\' im Namen ab (400).
- Leaf-Routen nutzen <path:projekt_name>, damit bestehende "Orphans" mit '/'
  geöffnet + gelöscht werden können (Recovery).
"""
import sqlite3
from urllib.parse import quote

import pytest

GUT = '/api/gutachten'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    # '*' schließt gutachten bewusst aus (#413) → Modul explizit lizenzieren.
    cur.state, cur.modules = 'ok', ['gutachten', 'cra', 'risikobewertung']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _create(client, auth_headers, name):
    return client.post(f'{GUT}/gerichts', headers=auth_headers, json={
        'name': name, 'gutachten_art': 'privat',
        'auftraggeber': 'ACME', 'auftrags_art': 'Schaden-Gutachten', 'sv_name': 'Max SV',
    })


def test_slash_name_rejected(client, auth_headers):
    r = _create(client, auth_headers, 'PG-2026/007')
    assert r.status_code == 400
    assert 'Schrägstrich' in (r.get_json() or {}).get('error', '')


def test_backslash_name_rejected(client, auth_headers):
    r = _create(client, auth_headers, 'PG\\007')
    assert r.status_code == 400


def test_normal_name_roundtrip(client, auth_headers):
    name = 'PG-REGR-944'
    client.delete(f'{GUT}/gerichts/{name}', headers=auth_headers)
    assert _create(client, auth_headers, name).status_code == 201
    # auswählen + zentrale Sub-Ressourcen müssen erreichbar bleiben (kein Routing-Regress)
    assert client.get(f'{GUT}/gerichts/{name}', headers=auth_headers).status_code == 200
    for sub in ('beweisfragen', 'befunde', 'assets', 'verfahren', 'audit-source'):
        assert client.get(f'{GUT}/gerichts/{name}/{sub}', headers=auth_headers).status_code == 200, sub
    assert client.delete(f'{GUT}/gerichts/{name}', headers=auth_headers).status_code == 204


def test_existing_slash_orphan_recoverable(client, auth_headers):
    """Ein vor dem Fix gespeicherter Orphan mit '/' muss geöffnet + gelöscht werden können."""
    from server.api.gutachten import DB_PATH
    from gutachten import gerichts_db as gdb
    orphan = 'PG-2026/REKO'
    gdb.ensure_db(DB_PATH)
    con = sqlite3.connect(str(DB_PATH))
    con.execute("INSERT OR REPLACE INTO gerichtsgutachten (name, gutachten_art) VALUES (?, 'privat')", (orphan,))
    con.commit()
    con.close()
    enc = quote(orphan, safe='')
    assert client.get(f'{GUT}/gerichts/{enc}', headers=auth_headers).status_code == 200
    assert client.delete(f'{GUT}/gerichts/{enc}', headers=auth_headers).status_code == 204
    assert client.get(f'{GUT}/gerichts/{enc}', headers=auth_headers).status_code == 404
