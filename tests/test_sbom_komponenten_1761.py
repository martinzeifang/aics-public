"""Komponentenliste je SBOM, Release-Vergleich, Upstream-Meldung (#1761).

Zwei Pflichten an derselben fehlenden Datenbasis, und der Grund, warum sie
zusammen in einem Issue stecken:

* **Art. 13 Abs. 5** — Der Release-Punkt ``fremdkomponenten_bewertet`` fragte,
  ob neue oder angehobene Fremdkomponenten bewertet wurden. ``cra_sbom`` hielt
  nur eine Komponenten-**Zahl**; beantworten konnte die Frage niemand in der
  Anwendung. Der wichtigste Test hier ist deshalb nicht einer über Komponenten,
  sondern ``test_punkt_ist_gerechnet_und_nicht_abhakbar``: Was die Anwendung
  rechnen kann, darf den Menschen nicht fragen.
* **Art. 13 Abs. 6** — Die Meldung an den Hersteller der Komponente. Ohne
  Komponentenliste hat sie keinen Anknüpfungspunkt; mit ihr wird sie rechenbar.

Geprüft wird an den Stellen, an denen die Regeln falsch liegen können: die
Identität einer Komponente (ohne sie ist jede Anhebung ein Paar aus „entfallen"
und „neu"), die Zuordnung Befund→Komponente (eine Teilstring-Suche würde
Meldepflichten an den falschen Hersteller erfinden), die Erhaltung menschlicher
Bewertungen bei einem erneuten Import und die Ampel-Wirkung der beiden neuen
Prüfpunkte.
"""
from __future__ import annotations

import json

import pytest

from cra import db as cdb
from cra import release_checkliste as rc
from cra import sbom_komponenten as sk
from cra import traceability_db as tdb
from cra import upstream_meldung as um
from cra.konformitaet_gate import evaluate

FIRMA = 'pytest-firma-1761'
VER = '2.0.0'
VOR = '1.9.0'


def _leeren(db_path, projekt: str) -> None:
    """Spuren des Projekts entfernen.

    Unter Postgres leitet ``shared/db.py`` das Schema aus dem **Dateinamen** ab
    (``cra.sqlite`` → Schema ``cra``): Alle CRA-Tests teilen sich dieselben
    Tabellen, ``tmp_path`` ist kein Teardown (#1706).
    """
    con = cdb._connect(db_path)
    try:
        for tbl in ('cra_konformitaet', 'cra_bewertungen', 'cra_dokumente',
                    'cra_managed_docs', 'cra_vuln', 'cra_sbom',
                    'cra_sbom_komponenten'):
            con.try_execute(f'DELETE FROM {tbl} WHERE projekt_name=?', (projekt,))
        con.commit()
    finally:
        con.close()


@pytest.fixture
def umgebung(tmp_path, monkeypatch, request):
    """Eigenes Projekt je Test — sonst hängt das Ergebnis an der Reihenfolge."""
    db_path = tmp_path / 'cra.sqlite'
    monkeypatch.setattr('cra.konformitaet_gate.CRA_DB', db_path)
    projekt = f'pytest-1761-{request.node.name[:50]}'
    cdb.ensure_db(db_path)
    sk.ensure_table(db_path)
    um.ensure_columns(db_path)
    _leeren(db_path, projekt)
    cdb.delete_projekt(db_path, projekt)
    cdb.save_projekt(db_path, name=projekt, unternehmen=FIRMA)
    yield db_path, projekt
    _leeren(db_path, projekt)
    cdb.delete_projekt(db_path, projekt)


def _sbom(db_path, projekt: str, version: str, datum: str) -> int:
    return cdb.save_sbom(db_path, projekt, {
        'release_version': version, 'sbom_format': 'cyclonedx',
        'sbom_datum': datum, 'komponenten_count': 0})


def _k(name: str, version: str, purl: str = '', **extra) -> dict:
    d = {'name': name, 'version': version, 'purl': purl or f'pkg:npm/{name}'}
    d.update(extra)
    return d


# ══ Identität einer Komponente ═══════════════════════════════════════════════

def test_purl_wird_am_letzten_at_getrennt():
    """Scoped npm-Pakete: am ersten ``@`` getrennt hieße jedes Babel-Paket
    ``pkg:npm/``, und der Vergleich fasste sie alle zu einer Komponente zusammen."""
    assert sk.purl_ohne_version('pkg:npm/@babel/core@7.0.0') == 'pkg:npm/@babel/core'
    assert sk.purl_version('pkg:npm/@babel/core@7.0.0') == '7.0.0'
    assert sk.purl_ohne_version('pkg:npm/@babel/core') == 'pkg:npm/@babel/core'
    assert sk.purl_version('pkg:npm/@babel/core') == ''


def test_purl_qualifier_und_subpath_fallen_weg():
    assert sk.purl_ohne_version('pkg:maven/org.x/y@1.0?type=jar#sub') == 'pkg:maven/org.x/y'


def test_schluessel_trennt_gleiche_namen_in_verschiedenen_oekosystemen():
    """``foo`` aus npm und ``foo`` aus PyPI sind nicht dieselbe Komponente —
    der Name allein kann das nicht unterscheiden, die purl schon."""
    assert sk.komponent_key('foo', 'pkg:npm/foo@1') != \
           sk.komponent_key('foo', 'pkg:pypi/foo@1')
    assert sk.komponent_key('  Lodash ', '') == 'lodash'


# ══ SBOM-Dateien lesen ═══════════════════════════════════════════════════════

CYCLONEDX = json.dumps({
    'bomFormat': 'CycloneDX', 'specVersion': '1.5',
    'components': [
        {'name': 'lodash', 'version': '4.17.21', 'purl': 'pkg:npm/lodash@4.17.21',
         'type': 'library', 'supplier': {'name': 'OpenJS Foundation'},
         'licenses': [{'license': {'id': 'MIT'}}],
         'components': [{'name': 'tief', 'version': '0.1', 'purl': 'pkg:npm/tief@0.1'}]},
        {'name': 'express', 'version': '4.18.2', 'purl': 'pkg:npm/express@4.18.2',
         'publisher': 'TJ', 'licenses': [{'expression': 'MIT OR Apache-2.0'}]},
    ],
})

SPDX = json.dumps({
    'spdxVersion': 'SPDX-2.3',
    'packages': [
        {'name': 'openssl', 'versionInfo': '3.0.11',
         'supplier': 'Organization: OpenSSL Project',
         'licenseConcluded': 'Apache-2.0',
         'externalRefs': [{'referenceType': 'purl',
                           'referenceLocator': 'pkg:generic/openssl@3.0.11'}]},
        {'name': 'zlib', 'versionInfo': '1.3', 'supplier': 'NOASSERTION',
         'licenseConcluded': 'NOASSERTION', 'licenseDeclared': 'Zlib'},
    ],
})


def test_cyclonedx_wird_vollstaendig_gelesen():
    komponenten, fmt = sk.parse_sbom(CYCLONEDX)
    assert fmt == 'cyclonedx'
    namen = {k['name'] for k in komponenten}
    # Verschachtelte Komponenten gehören dazu — sie werden mit ausgeliefert.
    assert namen == {'lodash', 'express', 'tief'}
    lodash = next(k for k in komponenten if k['name'] == 'lodash')
    assert lodash['lieferant'] == 'OpenJS Foundation' and lodash['lizenz'] == 'MIT'
    express = next(k for k in komponenten if k['name'] == 'express')
    assert express['lizenz'] == 'MIT OR Apache-2.0' and express['lieferant'] == 'TJ'


def test_spdx_wird_gelesen_und_noassertion_als_leer_behandelt():
    komponenten, fmt = sk.parse_sbom(SPDX)
    assert fmt == 'spdx'
    openssl = next(k for k in komponenten if k['name'] == 'openssl')
    assert openssl['lieferant'] == 'OpenSSL Project'
    assert openssl['purl'] == 'pkg:generic/openssl@3.0.11'
    zlib = next(k for k in komponenten if k['name'] == 'zlib')
    # ``NOASSERTION`` ist keine Angabe und darf nicht wie eine aussehen.
    assert zlib['lieferant'] == '' and zlib['lizenz'] == 'Zlib'


@pytest.mark.parametrize('inhalt, meldung', [
    ('kein json', 'lesbares JSON'),
    (json.dumps({'irgendwas': 1}), 'Unbekanntes SBOM-Format'),
    (json.dumps({'bomFormat': 'CycloneDX', 'components': []}), 'keine Komponenten'),
])
def test_unlesbare_sbom_wirft_statt_leer_zu_speichern(inhalt, meldung):
    """Ein Import, der still eine leere Liste speichert, sähe aus wie eine SBOM
    ohne Fremdkomponenten — gefährlicher als ein Fehler."""
    with pytest.raises(ValueError, match=meldung):
        sk.parse_sbom(inhalt)


# ══ Der Vergleich ════════════════════════════════════════════════════════════

def test_vergleich_nennt_neu_angehoben_entfallen():
    alt = [_k('lodash', '4.17.20'), _k('express', '4.18.2'), _k('alt-paket', '1.0')]
    neu = [_k('lodash', '4.17.21'), _k('express', '4.18.2'), _k('neu-paket', '2.0')]
    v = sk.vergleiche(
        [{**k, 'komponent_key': sk.komponent_key(k['name'], k['purl'])} for k in alt],
        [{**k, 'komponent_key': sk.komponent_key(k['name'], k['purl'])} for k in neu])
    assert [z['name'] for z in v['neu']] == ['neu-paket']
    assert [z['name'] for z in v['entfallen']] == ['alt-paket']
    assert len(v['angehoben']) == 1
    assert v['angehoben'][0]['version_alt'] == '4.17.20'
    assert v['angehoben'][0]['version_neu'] == '4.17.21'
    assert v['unveraendert'] == 1


def test_anhebung_ist_kein_paar_aus_entfallen_und_neu():
    """Der Grund für den versionsunabhängigen Schlüssel: Sonst gäbe es die
    interessanteste Kategorie — dieselbe Komponente in neuer Version — nicht."""
    v = sk.vergleiche([_k('lodash', '4.17.20')], [_k('lodash', '4.17.21')])
    assert not v['neu'] and not v['entfallen'] and len(v['angehoben']) == 1


def test_erstes_release_vergleicht_gegen_die_leere_menge():
    v = sk.vergleiche([], [_k('lodash', '4.17.21'), _k('express', '4.18.2')])
    assert len(v['neu']) == 2 and v['unveraendert'] == 0


def test_vorgaenger_ist_die_zuletzt_davor_erfasste_andere_version():
    """Nach Erfassungsdatum, nicht nach Versionsnummer: ``1.10`` gegen ``1.9``
    lässt sich nicht allgemein ordnen, ein Datum schon."""
    sboms = [
        {'id': 1, 'release_version': '1.8.0', 'sbom_datum': '2026-01-01'},
        {'id': 2, 'release_version': '1.9.0', 'sbom_datum': '2026-02-01'},
        {'id': 3, 'release_version': '2.0.0', 'sbom_datum': '2026-03-01'},
    ]
    gewaehlt = sk.vorgaenger_sbom(sboms, sboms[2])
    assert gewaehlt['release_version'] == '1.9.0'
    # Die älteste SBOM hat keinen Vorgänger.
    assert sk.vorgaenger_sbom(sboms, sboms[0]) is None


# ══ Speichern und Bewerten ═══════════════════════════════════════════════════

def test_erneuter_import_erhaelt_die_menschliche_bewertung(umgebung):
    """Die Komponentenliste ist der maschinelle Befund, die Bewertung die
    menschliche Aussage. Ein zweiter CI-Lauf darf die Aussage nicht löschen."""
    db_path, projekt = umgebung
    sid = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, sid, [_k('lodash', '4.17.21')])
    komp = sk.list_komponenten(db_path, projekt, sid)[0]
    sk.set_bewertung(db_path, projekt, [komp['id']], status='geprueft',
                     notiz='Changelog und Advisories geprüft, keine Befunde',
                     von='dev@example.com')

    res = sk.replace_komponenten(db_path, projekt, sid,
                                 [_k('lodash', '4.17.21'), _k('express', '4.18.2')])
    assert res['bewertungen_uebernommen'] == 1
    nachher = {k['name']: k for k in sk.list_komponenten(db_path, projekt, sid)}
    assert nachher['lodash']['bewertung_status'] == 'geprueft'
    assert nachher['lodash']['bewertet_von'] == 'dev@example.com'
    # Die neue Komponente ist unbewertet — sie ist eine neue Aussage.
    assert nachher['express']['bewertung_status'] == 'offen'


def test_anhebung_setzt_die_bewertung_zurueck(umgebung):
    """Eine andere Version ist eine andere Komponente: Dass 4.17.20 geprüft
    war, sagt nichts über 4.17.21."""
    db_path, projekt = umgebung
    sid = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, sid, [_k('lodash', '4.17.20')])
    komp = sk.list_komponenten(db_path, projekt, sid)[0]
    sk.set_bewertung(db_path, projekt, [komp['id']], status='geprueft',
                     notiz='Version 4.17.20 geprüft, unbedenklich', von='dev')
    sk.replace_komponenten(db_path, projekt, sid, [_k('lodash', '4.17.21')])
    assert sk.list_komponenten(db_path, projekt, sid)[0]['bewertung_status'] == 'offen'


def test_bewertung_braucht_eine_begruendung(umgebung):
    """Auch „nicht relevant": Das ist eine Aussage über das Produkt."""
    db_path, projekt = umgebung
    sid = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, sid, [_k('lodash', '4.17.21')])
    kid = sk.list_komponenten(db_path, projekt, sid)[0]['id']
    for status in ('geprueft', 'nicht_relevant'):
        with pytest.raises(ValueError, match='Begründung'):
            sk.set_bewertung(db_path, projekt, [kid], status=status, notiz='ok',
                             von='dev')


def test_sammelbewertung_erfasst_mehrere_komponenten(umgebung):
    """Ohne Sammelbewertung wäre der Prüfpunkt rechnerisch sauber und in der
    Bedienung unbrauchbar — und ein unbrauchbarer Prüfpunkt wird umgangen."""
    db_path, projekt = umgebung
    sid = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, sid,
                           [_k('a', '1'), _k('b', '1'), _k('c', '1')])
    ids = [k['id'] for k in sk.list_komponenten(db_path, projekt, sid)]
    assert sk.set_bewertung(db_path, projekt, ids, status='nicht_relevant',
                            notiz='Build-Werkzeuge, nicht Teil der Lieferung',
                            von='dev') == 3


def test_bewertung_fremden_projekts_greift_nicht(umgebung):
    """Die ID allein darf nicht reichen — ``projekt_name`` ist der Riegel."""
    db_path, projekt = umgebung
    sid = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, sid, [_k('lodash', '4.17.21')])
    kid = sk.list_komponenten(db_path, projekt, sid)[0]['id']
    assert sk.set_bewertung(db_path, 'pytest-1761-fremd', [kid], status='geprueft',
                            notiz='fremder Zugriff, soll nichts ändern',
                            von='dev') == 0


def test_geloeschte_sbom_nimmt_ihre_komponenten_mit(umgebung):
    """Sonst zählte die Liste beim nächsten Vergleich als Bestand einer SBOM,
    die es nicht mehr gibt — ein Befund aus Resten."""
    db_path, projekt = umgebung
    sid = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, sid, [_k('lodash', '4.17.21')])
    cdb.delete_sbom(db_path, sid)
    assert sk.list_komponenten(db_path, projekt, sid) == []


# ══ Der gerechnete Befund (Art. 13 Abs. 5) ═══════════════════════════════════

def test_befund_ohne_sbom_rechnet_nichts(umgebung):
    db_path, projekt = umgebung
    b = sk.befund(db_path, projekt, VER)
    assert b['sbom_fehlt'] and not b['liste_fehlt']


def test_befund_meldet_fehlende_komponentenliste(umgebung):
    """Der Altbestand: SBOM erfasst, nur als Zahl. Dann ist die
    Sorgfaltspflicht **nicht belegbar** — und genau das sagt der Befund."""
    db_path, projekt = umgebung
    _sbom(db_path, projekt, VER, '2026-03-01')
    b = sk.befund(db_path, projekt, VER)
    assert not b['sbom_fehlt'] and b['liste_fehlt'] and b['komponenten'] == 0


def test_befund_nennt_die_unbewerteten_neuen_komponenten(umgebung):
    db_path, projekt = umgebung
    alt_id = _sbom(db_path, projekt, VOR, '2026-02-01')
    sk.replace_komponenten(db_path, projekt, alt_id,
                           [_k('lodash', '4.17.20'), _k('express', '4.18.2')])
    neu_id = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, neu_id, [
        _k('lodash', '4.17.21'),    # angehoben
        _k('express', '4.18.2'),    # unverändert
        _k('neu-paket', '1.0'),     # neu
    ])
    b = sk.befund(db_path, projekt, VER)
    assert b['vorgaenger_version'] == VOR and not b['erstbewertung']
    assert b['pflichtig'] == 2 and b['bewertet'] == 0
    assert {u['name'] for u in b['unbewertet']} == {'lodash', 'neu-paket'}

    # Bewerten schließt den Befund — und zwar nur die bewerteten.
    ids = [u['id'] for u in b['unbewertet'] if u['name'] == 'lodash']
    sk.set_bewertung(db_path, projekt, ids, status='geprueft',
                     notiz='Patch-Release, Changelog geprüft', von='dev')
    b2 = sk.befund(db_path, projekt, VER)
    assert b2['bewertet'] == 1 and {u['name'] for u in b2['unbewertet']} == {'neu-paket'}


def test_erstes_release_fuehrt_jede_komponente_als_neu(umgebung):
    """Kein Vorgänger heißt nicht „nichts zu prüfen": Beim Erst-Release ist
    jede Komponente neu integriert."""
    db_path, projekt = umgebung
    sid = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, sid,
                           [_k('lodash', '4.17.21'), _k('express', '4.18.2')])
    b = sk.befund(db_path, projekt, VER)
    assert b['erstbewertung'] and b['pflichtig'] == 2 and len(b['unbewertet']) == 2


def test_bezugsversion_kann_benannt_werden(umgebung):
    db_path, projekt = umgebung
    a = _sbom(db_path, projekt, '1.0.0', '2026-01-01')
    sk.replace_komponenten(db_path, projekt, a, [_k('lodash', '4.0.0')])
    b_id = _sbom(db_path, projekt, VOR, '2026-02-01')
    sk.replace_komponenten(db_path, projekt, b_id, [_k('lodash', '4.17.20')])
    c = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, c, [_k('lodash', '4.17.21')])
    assert sk.befund(db_path, projekt, VER)['vorgaenger_version'] == VOR
    assert sk.befund(db_path, projekt, VER,
                     vorgaenger_version='1.0.0')['vorgaenger_version'] == '1.0.0'


# ══ Der Prüfpunkt (die eigentliche Lehre des Issues) ═════════════════════════

def test_punkt_ist_gerechnet_und_nicht_abhakbar(umgebung):
    """Der Kern: ``fremdkomponenten_bewertet`` war eine ``entscheidung``, weil
    die Datenbasis fehlte. Jetzt rechnet die Anwendung — also darf sie nicht
    mehr fragen."""
    from cra import konformitaet_db as kdb

    db_path, projekt = umgebung
    item = rc.item('fremdkomponenten_bewertet')
    assert item is not None and item.art == 'gerechnet'
    assert item.quelle == 'fremdkomponenten_unbewertet'
    assert 'fremdkomponenten_bewertet' in rc.gerechnete_ids()

    kdb.save_konformitaet(db_path, projekt, {'release_version': VER})
    with pytest.raises(ValueError, match='gerechnet'):
        kdb.set_release_checkliste(db_path, projekt, VER, 'fremdkomponenten_bewertet',
                                   status='erledigt', begruendung='alles geprüft',
                                   von='dev@example.com')


def test_upstream_punkt_ist_gerechnet():
    item = rc.item('upstream_meldung')
    assert item is not None and item.art == 'gerechnet'
    assert item.quelle == 'upstream_meldung_offen'
    assert 'Art. 13 Abs. 6' in item.rechtsbezug


def test_jeder_gerechnete_punkt_findet_seinen_befund(umgebung):
    """Invariante zwischen Katalog und Gate: Nennt ein ``gerechnet``-Punkt eine
    ``quelle``, die das Gate nicht liefert, zeigt der Nachweis an dieser Stelle
    dauerhaft „nicht geprüft" — und niemand merkt es."""
    db_path, projekt = umgebung
    gate = evaluate(projekt, version=VER)
    for item in rc.KATALOG:
        if item.art != 'gerechnet' or not item.quelle:
            continue
        assert item.quelle in gate, item.id


# ══ Das Gate (Art. 13 Abs. 5) ════════════════════════════════════════════════

def _punkte(gate: dict, typ: str) -> list[dict]:
    return [p for p in gate['release_punkte'] if p.get('typ') == typ]


def test_gate_meldet_fehlende_komponentenliste_als_bedingt(umgebung):
    db_path, projekt = umgebung
    _sbom(db_path, projekt, VER, '2026-03-01')
    gate = evaluate(projekt, version=VER)
    punkte = _punkte(gate, 'fremdkomponenten')
    assert len(punkte) == 1 and 'Komponentenliste' in punkte[0]['titel']
    assert punkte[0]['ampel_wirkung'] == 'bedingt'
    # ``None`` heißt „nicht geprüft" — nicht „in Ordnung".
    assert gate['fremdkomponenten_unbewertet'] is None


def test_gate_meldet_unbewertete_komponenten_und_schweigt_danach(umgebung):
    db_path, projekt = umgebung
    alt_id = _sbom(db_path, projekt, VOR, '2026-02-01')
    sk.replace_komponenten(db_path, projekt, alt_id, [_k('lodash', '4.17.20')])
    neu_id = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, neu_id, [_k('lodash', '4.17.21')])

    gate = evaluate(projekt, version=VER)
    punkte = _punkte(gate, 'fremdkomponenten')
    assert len(punkte) == 1 and punkte[0]['ampel_wirkung'] == 'bedingt'
    assert 'lodash' in punkte[0]['hinweis']
    assert gate['fremdkomponenten_unbewertet'] == ['lodash 4.17.21']
    assert gate['release_befunde']['fremdkomponenten']['angehoben'] == 1

    kid = sk.list_komponenten(db_path, projekt, neu_id)[0]['id']
    sk.set_bewertung(db_path, projekt, [kid], status='geprueft',
                     notiz='Patch-Release geprüft, keine neuen Befunde', von='dev')
    gate2 = evaluate(projekt, version=VER)
    assert not _punkte(gate2, 'fremdkomponenten')
    # Leere Liste = geprüft und nichts offen. Der Unterschied zu ``None`` ist
    # der ganze Sinn der Unterscheidung.
    assert gate2['fremdkomponenten_unbewertet'] == []


def test_gate_rechnet_ohne_version_nicht(umgebung):
    """Phase 1 ist die Produktsicht; die Stückliste gehört zur Version."""
    db_path, projekt = umgebung
    sid = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, sid, [_k('lodash', '4.17.21')])
    gate = evaluate(projekt)
    assert gate['fremdkomponenten_unbewertet'] is None
    assert gate['release_punkte'] == []


# ══ Art. 13 Abs. 6 — Zuordnung Befund → Fremdkomponente ══════════════════════

def test_zuordnung_ist_exakt_und_erfindet_keine_meldepflicht():
    """Eine Teilstring-Suche würde ``requests`` in ``requests-oauthlib`` finden
    und eine Meldung an den falschen Hersteller verlangen."""
    index = um.komponenten_index([
        {'komponent_key': 'pkg:pypi/requests', 'name': 'requests'}])
    assert um.fremdbezug({'affected_component': 'requests'}, index) == 'pkg:pypi/requests'
    assert um.fremdbezug({'affected_component': 'requests@2.31.0'}, index) == 'pkg:pypi/requests'
    assert um.fremdbezug({'affected_component': 'pkg:pypi/requests'}, index) == 'pkg:pypi/requests'
    assert um.fremdbezug({'affected_component': 'requests-oauthlib'}, index) == ''


def test_befund_aus_upstream_quelle_loest_keine_meldepflicht_aus():
    """Dependabot-Funde hat der Hersteller der Komponente selbst veröffentlicht.
    Eine Meldung an ihn zu verlangen hieße, den Prüfpunkt nach dem ersten
    Abhängigkeits-Scan dauerhaft rot zu stellen — und damit wirkungslos."""
    index = um.komponenten_index([{'komponent_key': 'pkg:npm/lodash', 'name': 'lodash'}])
    p = um.pflicht({'affected_component': 'lodash', 'source': 'github_dependabot'}, index)
    assert not p['pflichtig'] and 'selbst veröffentlicht' in p['grund']


def test_eigener_code_loest_keine_meldepflicht_aus():
    index = um.komponenten_index([{'komponent_key': 'pkg:npm/lodash', 'name': 'lodash'}])
    p = um.pflicht({'affected_component': 'unser-modul', 'source': 'manual'}, index)
    assert not p['pflichtig'] and 'eigener Code' in p['grund']


def test_eigener_fund_in_fremdkomponente_ist_pflichtig():
    index = um.komponenten_index([{'komponent_key': 'pkg:npm/lodash', 'name': 'lodash'}])
    p = um.pflicht({'affected_component': 'lodash', 'source': 'pentest'}, index)
    assert p['pflichtig'] and p['komponent_key'] == 'pkg:npm/lodash'


def test_veroeffentlichter_befund_ohne_meldung_ist_ueberfaellig():
    """Art. 13 Abs. 6 nennt keine Frist — endgültig wird das Versäumnis, wenn
    **wir** mit dem Befund nach außen gehen."""
    index = um.komponenten_index([{'komponent_key': 'pkg:npm/lodash', 'name': 'lodash'}])
    frisch = {'affected_component': 'lodash', 'source': 'manual', 'status': 'open'}
    assert um.pflicht(frisch, index)['ueberfaellig'] is False
    assert um.pflicht({**frisch, 'status': 'disclosed'}, index)['ueberfaellig'] is True
    assert um.pflicht({**frisch, 'advisory_url': 'https://x/advisory'},
                      index)['ueberfaellig'] is True


def test_gemeldet_braucht_kanal_und_referenz(umgebung):
    """„Gemeldet" ohne Angabe, wohin und unter welcher Nummer, ist keine
    Dokumentation der Meldung, sondern ihre Behauptung."""
    db_path, projekt = umgebung
    vid = cdb.save_vuln(db_path, projekt, {
        'cve_id': 'CVE-2026-1761', 'schwere': 'high', 'source': 'manual',
        'affected_component': 'lodash'})
    with pytest.raises(ValueError, match='Kanal'):
        um.set_upstream(db_path, projekt, vid, status='gemeldet')
    with pytest.raises(ValueError, match='Referenz'):
        um.set_upstream(db_path, projekt, vid, status='gemeldet',
                        kanal='GitHub Security Advisory')
    res = um.set_upstream(db_path, projekt, vid, status='gemeldet',
                          kanal='GitHub Security Advisory',
                          referenz='GHSA-xxxx-yyyy', von='dev@example.com')
    assert res['upstream_gemeldet_am']


def test_nicht_erforderlich_braucht_eine_begruendung(umgebung):
    db_path, projekt = umgebung
    vid = cdb.save_vuln(db_path, projekt, {'cve_id': 'CVE-2026-1762',
                                           'affected_component': 'lodash'})
    with pytest.raises(ValueError, match='Begründung'):
        um.set_upstream(db_path, projekt, vid, status='nicht_erforderlich',
                        begruendung='nein')


def test_set_upstream_greift_nur_im_eigenen_projekt(umgebung):
    db_path, projekt = umgebung
    vid = cdb.save_vuln(db_path, projekt, {'cve_id': 'CVE-2026-1763',
                                           'affected_component': 'lodash'})
    with pytest.raises(ValueError, match='nicht gefunden'):
        um.set_upstream(db_path, 'pytest-1761-fremd', vid, status='gemeldet',
                        kanal='mail', referenz='X-1')


# ══ Das Gate (Art. 13 Abs. 6) ════════════════════════════════════════════════

def _mit_fremdkomponente(db_path, projekt: str) -> int:
    """SBOM mit einer Fremdkomponente, alle Komponenten bewertet.

    Bewertet, damit der Art.-13-Abs.-5-Punkt die Messung nicht überlagert:
    Nur gegen eine saubere Null-Linie lässt sich die Wirkung **eines**
    Prüfpunktes ablesen.
    """
    sid = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, sid, [_k('lodash', '4.17.21')])
    ids = [k['id'] for k in sk.list_komponenten(db_path, projekt, sid)]
    sk.set_bewertung(db_path, projekt, ids, status='geprueft',
                     notiz='Lieferant und Advisories geprüft', von='dev')
    return sid


def test_gate_meldet_offene_upstream_meldung_als_bedingt(umgebung):
    db_path, projekt = umgebung
    _mit_fremdkomponente(db_path, projekt)
    cdb.save_vuln(db_path, projekt, {
        'cve_id': 'CVE-2026-1764', 'schwere': 'medium', 'status': 'open',
        'source': 'manual', 'affected_component': 'lodash'})
    gate = evaluate(projekt, version=VER)
    punkte = _punkte(gate, 'upstream_meldung')
    assert len(punkte) == 1 and punkte[0]['ampel_wirkung'] == 'bedingt'
    assert 'CVE-2026-1764' in punkte[0]['hinweis']
    assert gate['upstream_meldung_offen'] == ['CVE-2026-1764']


def test_gate_meldet_veroeffentlichten_befund_ohne_meldung_als_rot(umgebung):
    """Wir haben über eine Schwachstelle in fremdem Code informiert, ohne deren
    Hersteller zu unterrichten — Pflichtverletzung gegenüber einem Dritten."""
    db_path, projekt = umgebung
    _mit_fremdkomponente(db_path, projekt)
    cdb.save_vuln(db_path, projekt, {
        'cve_id': 'CVE-2026-1765', 'schwere': 'medium', 'status': 'disclosed',
        'source': 'manual', 'affected_component': 'lodash',
        'advisory_url': 'https://example.test/advisory/1765',
        'fixed_in_version': VER})
    gate = evaluate(projekt, version=VER)
    punkte = _punkte(gate, 'upstream_meldung')
    assert len(punkte) == 1 and punkte[0]['ampel_wirkung'] == 'rot'
    assert gate['ampel'] == 'rot'


def test_gemeldeter_befund_schliesst_den_punkt(umgebung):
    db_path, projekt = umgebung
    _mit_fremdkomponente(db_path, projekt)
    vid = cdb.save_vuln(db_path, projekt, {
        'cve_id': 'CVE-2026-1766', 'schwere': 'medium', 'status': 'disclosed',
        'source': 'manual', 'affected_component': 'lodash'})
    um.set_upstream(db_path, projekt, vid, status='gemeldet',
                    kanal='security@lodash.test', referenz='UPSTREAM-77', von='dev')
    gate = evaluate(projekt, version=VER)
    assert not _punkte(gate, 'upstream_meldung')
    assert gate['upstream_meldung_offen'] == []
    assert gate['release_befunde']['upstream_meldung']['gemeldet'] == 1


def test_ohne_komponentenliste_behauptet_das_gate_keine_meldepflicht(umgebung):
    """Ohne Komponentenliste lässt sich der Fremdbezug nicht belegen. Dann sagt
    der Befund das — und erfindet keine Pflicht, die er nicht begründen kann.
    Dass die Liste fehlt, meldet der Art.-13-Abs.-5-Punkt; eine zweite Meldung
    wäre Lärm."""
    db_path, projekt = umgebung
    _sbom(db_path, projekt, VER, '2026-03-01')
    cdb.save_vuln(db_path, projekt, {
        'cve_id': 'CVE-2026-1767', 'status': 'disclosed', 'source': 'manual',
        'affected_component': 'lodash'})
    gate = evaluate(projekt, version=VER)
    assert not _punkte(gate, 'upstream_meldung')
    assert gate['upstream_meldung_offen'] is None
    assert len(_punkte(gate, 'fremdkomponenten')) == 1


def test_quellenausfall_bleibt_sichtbar(umgebung, monkeypatch):
    """Ein stilles ``except: pass`` ließe den Punkt verschwinden und die Ampel
    grün werden — in einem Konformitäts-Gate der gefährlichste Fehler, weil er
    wie ein gutes Ergebnis aussieht (#1751)."""
    db_path, projekt = umgebung

    def kaputt(*_a, **_k):
        raise RuntimeError('Datenquelle weg')

    monkeypatch.setattr('cra.sbom_komponenten.befund', kaputt)
    monkeypatch.setattr('cra.upstream_meldung.befund', kaputt)
    gate = evaluate(projekt, version=VER)
    for typ in ('fremdkomponenten', 'upstream_meldung'):
        punkte = _punkte(gate, typ)
        assert len(punkte) == 1 and punkte[0].get('ungeprueft') is True, typ
    assert gate['fremdkomponenten_unbewertet'] is None
    assert gate['upstream_meldung_offen'] is None


# ══ Aufräumen ════════════════════════════════════════════════════════════════

def test_geloeschtes_projekt_laesst_keine_komponenten_zurueck(umgebung):
    """Lieferanten- und Lizenzangaben Dritter gehören mit weg (#1752)."""
    db_path, projekt = umgebung
    sid = _sbom(db_path, projekt, VER, '2026-03-01')
    sk.replace_komponenten(db_path, projekt, sid, [_k('lodash', '4.17.21')])
    cdb.delete_projekt(db_path, projekt)
    assert sk.list_komponenten(db_path, projekt) == []
    assert ('cra_sbom_komponenten', 'projekt_name') in cdb.PROJEKT_TABELLEN
