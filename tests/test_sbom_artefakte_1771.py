"""Mehrere SBOMs je Release — ein Produkt, mehrere Artefakte (#1771).

Aus der Rückfrage des Anwenders: „Wenn ich für eine Anwendung mehrere SBOMs
habe, wie ich jetzt — muss das auch erkannt bzw. hinterlegt werden können."

Es ging **nicht**, und zwar dreifach:

1. ``UNIQUE(projekt_name, release_version, sbom_format)`` — zwei SPDX-SBOMs zur
   selben Version kollidierten; die zweite ließ sich nicht speichern.
2. ``vorgaenger_sbom`` wählte die zuletzt erfasste SBOM **irgendeiner** anderen
   Version, unabhängig vom Artefakt. Die Webserver-SBOM wurde damit gegen die
   der Anwendung verglichen — eine plausibel aussehende und völlig falsche
   Zahl. Das ist der gefährlichste der drei Punkte: Er liefert ein Ergebnis,
   statt zu scheitern.
3. ``befund`` nahm die neueste SBOM der Version und ließ die übrigen liegen —
   der Prüfpunkt hätte eine Teilmenge des Produkts bewertet und das Ergebnis
   für das Ganze ausgegeben.
"""
from __future__ import annotations

import json

import pytest

CRA = '/api/cra'
FIRMA = 'pytest-firma-1771'
PROJ = 'pytest-cra-1771'


def _sbom_json(komponenten):
    return json.dumps({'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'components': [
        {'name': n, 'version': v, 'purl': f'pkg:pypi/{n}@{v}',
         'licenses': [{'license': {'id': 'MIT'}}]} for n, v in komponenten]})


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


def _anlege(client, auth_headers, version, artefakt, komponenten, datum):
    r = client.post(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers,
                    json={'release_version': version, 'artefakt': artefakt,
                          'sbom_format': 'cyclonedx', 'sbom_datum': datum})
    assert r.status_code == 201, r.json
    sid = r.json['id']
    client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten', headers=auth_headers,
                json={'sbom': _sbom_json(komponenten)})
    return sid


def test_zwei_sboms_gleicher_version_und_format(client, auth_headers, projekt):
    """Der Fall des Anwenders: Anwendung und Webserver, beide SPDX, beide 8.0.1."""
    a = _anlege(client, auth_headers, '8.0.1', 'anwendung',
                [('requests', '2.32.3'), ('jinja2', '3.1.4')], '2026-10-22')
    b = _anlege(client, auth_headers, '8.0.1', 'webserver',
                [('nginx', '1.27.2')], '2026-10-22')
    assert a != b

    zeilen = [s for s in client.get(f'{CRA}/projekte/{PROJ}/sbom',
                                    headers=auth_headers).json
              if s['release_version'] == '8.0.1']
    assert len(zeilen) == 2
    assert {s['artefakt'] for s in zeilen} == {'anwendung', 'webserver'}
    assert {s['liste_anzahl'] for s in zeilen} == {2, 1}


def test_vergleich_bleibt_beim_selben_artefakt(client, auth_headers, projekt):
    """Der gefährlichste der drei Punkte: Ohne diese Regel wird verglichen, was
    nicht zusammengehört — und es kommt eine Zahl heraus, die stimmig aussieht."""
    from cra.sbom_komponenten import befund
    from pathlib import Path

    db = Path('data/db/cra.sqlite')
    _anlege(client, auth_headers, '1.0.0', 'anwendung',
            [('requests', '2.31.0'), ('jinja2', '3.1.3')], '2026-01-01')
    _anlege(client, auth_headers, '1.0.0', 'webserver',
            [('nginx', '1.26.0')], '2026-01-01')
    _anlege(client, auth_headers, '2.0.0', 'anwendung',
            [('requests', '2.32.3'), ('jinja2', '3.1.3')], '2026-06-01')
    _anlege(client, auth_headers, '2.0.0', 'webserver',
            [('nginx', '1.27.2')], '2026-06-01')

    b = befund(db, PROJ, '2.0.0')
    je = {t['artefakt']: t for t in b['artefakte']}
    assert set(je) == {'anwendung', 'webserver'}

    # Anwendung: requests angehoben, jinja2 unverändert — NICHT gegen nginx.
    anw = je['anwendung']
    assert anw['vorgaenger_version'] == '1.0.0'
    assert [k['name'] for k in anw['vergleich']['angehoben']] == ['requests']
    assert anw['vergleich']['neu'] == []
    assert anw['vergleich']['unveraendert'] == 1

    # Webserver: nginx angehoben, nichts neu, nichts entfallen.
    web = je['webserver']
    assert [k['name'] for k in web['vergleich']['angehoben']] == ['nginx']
    assert web['vergleich']['neu'] == []
    assert web['vergleich']['entfallen'] == []


def test_befund_zaehlt_ueber_alle_artefakte(client, auth_headers, projekt):
    """Der Prüfpunkt gilt dem Release, nicht einem seiner Teile."""
    from pathlib import Path

    from cra.sbom_komponenten import befund

    db = Path('data/db/cra.sqlite')
    _anlege(client, auth_headers, '3.0.0', 'anwendung',
            [('requests', '2.32.3'), ('jinja2', '3.1.4')], '2026-07-01')
    _anlege(client, auth_headers, '3.0.0', 'webserver',
            [('nginx', '1.27.2')], '2026-07-01')

    b = befund(db, PROJ, '3.0.0')
    assert b['komponenten'] == 3            # 2 + 1, nicht nur eines der beiden
    assert b['pflichtig'] == 3              # Erstbewertung: alles neu
    assert len(b['unbewertet']) == 3
    assert len(b['artefakte']) == 2


def test_fehlende_liste_eines_artefakts_schlaegt_durch(client, auth_headers, projekt):
    """„Teilweise belegbar" gibt es nicht: Fehlt einem Artefakt die Liste, ist
    die Sorgfaltspflicht für das Release nicht belegt."""
    from pathlib import Path

    from cra.sbom_komponenten import befund

    db = Path('data/db/cra.sqlite')
    _anlege(client, auth_headers, '4.0.0', 'anwendung',
            [('requests', '2.32.3')], '2026-08-01')
    # Zweites Artefakt ohne Komponentenliste
    client.post(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers,
                json={'release_version': '4.0.0', 'artefakt': 'webserver',
                      'sbom_format': 'cyclonedx', 'sbom_datum': '2026-08-01'})

    b = befund(db, PROJ, '4.0.0')
    assert b['liste_fehlt'] is True


def test_bestand_ohne_artefakt_verhaelt_sich_wie_vorher(client, auth_headers, projekt):
    """Altdaten tragen kein Artefakt. Sie müssen sich untereinander vergleichen
    wie bisher — sonst hätte die Erweiterung den Bestand verändert."""
    from pathlib import Path

    from cra.sbom_komponenten import befund

    db = Path('data/db/cra.sqlite')
    _anlege(client, auth_headers, '5.0.0', '', [('requests', '2.31.0')], '2026-02-01')
    _anlege(client, auth_headers, '6.0.0', '', [('requests', '2.32.3')], '2026-03-01')

    b = befund(db, PROJ, '6.0.0')
    assert b['vorgaenger_version'] == '5.0.0'
    assert [k['name'] for k in b['vergleich']['angehoben']] == ['requests']


def test_teil_update_loescht_das_artefakt_nicht(client, auth_headers, projekt):
    """Jeder Aufrufer, der ``artefakt`` nicht nennt, hätte es sonst gelöscht.

    Genau das ist beim Komponenten-Import passiert: Er zieht
    ``komponenten_count`` nach und schickt dabei ein Teil-Dict ohne
    ``artefakt``. Dieselbe Falle wie der `meta_json`-Verlust in #1540 — der
    Schutz gehört deshalb in `save_sbom` und nicht in den Aufrufer.
    """
    from pathlib import Path

    from cra.db import list_sbom, save_sbom

    db = Path('data/db/cra.sqlite')
    r = client.post(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers,
                    json={'release_version': '7.0.0', 'artefakt': 'anwendung',
                          'sbom_format': 'cyclonedx'})
    sid = r.json['id']

    # Teil-Update ohne 'artefakt' — wie der Komponenten-Import es schickt.
    save_sbom(db, PROJ, {'id': sid, 'release_version': '7.0.0',
                         'sbom_format': 'cyclonedx', 'komponenten_count': 42})
    zeile = next(s for s in list_sbom(db, PROJ) if int(s['id']) == int(sid))
    assert zeile['artefakt'] == 'anwendung'
    assert zeile['komponenten_count'] == 42

    # Ausdrücklich leeren bleibt möglich.
    save_sbom(db, PROJ, {'id': sid, 'release_version': '7.0.0',
                         'sbom_format': 'cyclonedx', 'artefakt': ''})
    zeile = next(s for s in list_sbom(db, PROJ) if int(s['id']) == int(sid))
    assert zeile['artefakt'] == ''


def test_artefakt_aus_dem_dateinamen(tmp_path):
    """Im Ablageort benennt der Teil vor der Version das Artefakt."""
    from cra.sbom_quellen import finde_lokal

    ordner = tmp_path / PROJ
    ordner.mkdir(parents=True)
    (ordner / 'webserver-1.9.0.cdx.json').write_text(
        _sbom_json([('nginx', '1.27.2')]), encoding='utf-8')
    (ordner / 'anwendung-1.9.0.cdx.json').write_text(
        _sbom_json([('requests', '2.32.3')]), encoding='utf-8')

    funde = finde_lokal(PROJ, basis=tmp_path)
    assert {f['artefakt'] for f in funde} == {'webserver', 'anwendung'}
    assert {f['release_version'] for f in funde} == {'1.9.0'}
