"""Fremdkomponenten in Klassen bewerten + eigene Befunde ausweisen (#1773/#1774).

Ausgangslage: Eine echte SBOM dieser Anwendung führt 184 Komponenten; beim
Erst-Release gilt jede als neu, also verlangte der gerechnete Prüfpunkt
``fremdkomponenten_bewertet`` (Art. 13 Abs. 5) 184 begründete Einzelaussagen.
Genau an dieser Stelle wird ein Prüfpunkt umgangen statt beantwortet.

Zwei Dinge werden hier festgehalten:

* **Die Gruppierung ist deterministisch** und erfindet nichts. Was die SBOM
  nicht sagt (Ökosystem), heißt ``unbestimmt`` und nicht „Anwendung".
* **Ein offener eigener Befund hat Vorrang.** Eine Komponente, gegen die etwas
  vorliegt, verschwindet in keiner Sammelbegründung — das ist der Fall, auf den
  es ankommt, und er darf nicht derjenige sein, der mitläuft.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

CRA = '/api/cra'
FIRMA = 'pytest-firma-1773'
PROJ = 'pytest-cra-1773'
DB = Path('data/db/cra.sqlite')


# ── Reine Funktionen: Einordnung und Gruppierung ─────────────────────────────

def test_purl_typ_liest_oekosystem():
    from cra.komponenten_klassen import purl_typ

    assert purl_typ('pkg:pypi/flask@3.0.0') == 'pypi'
    assert purl_typ('pkg:deb/debian/libc6@2.36-9?arch=amd64') == 'deb'
    assert purl_typ('pkg:npm/%40babel/core@7.0.0') == 'npm'
    # Ohne purl kein Typ — und damit später kein geratenes Ökosystem.
    assert purl_typ('') == ''
    assert purl_typ('libc6-2.36') == ''


def test_klassen_sind_aus_den_daten_bestimmt_nicht_geraten():
    from cra.komponenten_klassen import klasse_fuer

    assert klasse_fuer({'purl': 'pkg:deb/debian/libc6@2.36'}) == ('betriebssystem', 'deb')
    assert klasse_fuer({'purl': 'pkg:apk/alpine/musl@1.2.5'}) == ('betriebssystem', 'apk')
    assert klasse_fuer({'purl': 'pkg:pypi/flask@3.0.0'}) == ('anwendung', 'pypi')
    assert klasse_fuer({'purl': 'pkg:oci/python@sha256:abc'}) == ('basisimage', 'oci')
    # Der Typ aus der SBOM trägt nur, wo er eindeutig ist.
    assert klasse_fuer({'purl': '', 'typ': 'operating-system'}) == ('betriebssystem', '')
    assert klasse_fuer({'purl': '', 'typ': 'container'}) == ('basisimage', '')
    # Eine „library" ohne purl bleibt unbestimmt: Ohne Ökosystem ist nicht
    # sagbar, wie sie überwacht wird — und genau das soll die Klasse sagen.
    assert klasse_fuer({'purl': '', 'typ': 'library'})[0] == 'unbestimmt'
    assert klasse_fuer({'purl': 'pkg:exotisch/dings@1.0'})[0] == 'unbestimmt'


def test_offener_befund_hat_vorrang_vor_der_klasse():
    """Der Kern von #1774: Diese Komponente ist kein gleichartiger Fall mehr."""
    from cra.komponenten_klassen import klasse_fuer

    k = {'purl': 'pkg:pypi/flask@3.0.0'}
    assert klasse_fuer(k) == ('anwendung', 'pypi')
    assert klasse_fuer(k, hat_offenen_befund=True) == ('einzelpruefung', '')


def test_gruppiere_macht_aus_vielen_entscheidungen_wenige():
    from cra.komponenten_klassen import gruppiere

    komponenten = (
        [{'id': i, 'komponent_key': f'pkg:deb/libx{i}', 'name': f'libx{i}',
          'version': '1.0', 'purl': f'pkg:deb/debian/libx{i}@1.0',
          'lizenz': 'GPL-2.0'} for i in range(1, 41)]
        + [{'id': 100 + i, 'komponent_key': f'pkg:pypi/p{i}', 'name': f'p{i}',
            'version': '2.0', 'purl': f'pkg:pypi/p{i}@2.0', 'lizenz': 'MIT'}
           for i in range(1, 31)]
        + [{'id': 900, 'komponent_key': 'pkg:oci/python', 'name': 'python',
            'version': '3.12', 'purl': 'pkg:oci/python@3.12', 'lizenz': ''}]
    )
    gruppen = gruppiere(komponenten)
    assert len(gruppen) == 3, [g['key'] for g in gruppen]
    je = {g['key']: g for g in gruppen}
    assert je['betriebssystem:deb']['anzahl'] == 40
    assert je['anwendung:pypi']['anzahl'] == 30
    assert je['basisimage:oci']['anzahl'] == 1
    # Lizenzlücke wird gezählt, nicht zur eigenen Gruppe gemacht — zwei
    # Gruppierungsachsen gleichzeitig wären in der Bedienung nicht lesbar.
    assert je['basisimage:oci']['ohne_lizenz'] == 1
    assert je['betriebssystem:deb']['ohne_lizenz'] == 0
    assert je['betriebssystem:deb']['lizenzen'] == ['GPL-2.0']
    assert len(je['anwendung:pypi']['beispiele']) == 10   # Vorschau, nicht Liste


def test_einzelpruefung_steht_oben_und_ist_keine_sammelgruppe():
    from cra.komponenten_klassen import gruppiere

    komponenten = [
        {'id': 1, 'komponent_key': 'pkg:pypi/flask', 'name': 'flask',
         'version': '3.0', 'purl': 'pkg:pypi/flask@3.0'},
        {'id': 2, 'komponent_key': 'pkg:pypi/jinja2', 'name': 'jinja2',
         'version': '3.1', 'purl': 'pkg:pypi/jinja2@3.1'},
    ]
    befunde = {'pkg:pypi/flask': [{'cve_id': 'CVE-2026-1', 'offen': True,
                                   'schwere': 'high'}]}
    gruppen = gruppiere(komponenten, befunde=befunde)
    assert gruppen[0]['klasse'] == 'einzelpruefung'
    assert gruppen[0]['sammel'] is False
    assert gruppen[0]['ids'] == [1]
    assert gruppen[1]['key'] == 'anwendung:pypi'
    assert gruppen[1]['ids'] == [2]


def test_behobener_befund_holt_die_komponente_zurueck_in_die_gruppe():
    """``fixed`` ist behandelt — die Komponente ist wieder ein Normalfall."""
    from cra.komponenten_klassen import gruppiere

    komponenten = [{'id': 1, 'komponent_key': 'pkg:pypi/flask', 'name': 'flask',
                    'version': '3.0', 'purl': 'pkg:pypi/flask@3.0'}]
    befunde = {'pkg:pypi/flask': [{'cve_id': 'CVE-2026-1', 'offen': False,
                                   'schwere': 'high'}]}
    gruppen = gruppiere(komponenten, befunde=befunde)
    assert [g['klasse'] for g in gruppen] == ['anwendung']
    assert gruppen[0]['mit_befund'] == 1   # sichtbar bleibt er trotzdem


def test_ids_der_gruppe_laesst_bewertete_in_ruhe():
    from cra.komponenten_klassen import ids_der_gruppe

    komponenten = [
        {'id': 1, 'komponent_key': 'pkg:pypi/a', 'purl': 'pkg:pypi/a@1',
         'bewertung_status': 'offen'},
        {'id': 2, 'komponent_key': 'pkg:pypi/b', 'purl': 'pkg:pypi/b@1',
         'bewertung_status': 'geprueft'},
    ]
    assert ids_der_gruppe(komponenten, 'anwendung:pypi') == [1, 2]
    assert ids_der_gruppe(komponenten, 'anwendung:pypi', nur_offene=True) == [1]


def test_prompt_erfindet_keine_ueberwachung():
    """Ohne Nachweise darf der Prompt keine behaupten — sonst tut es die KI."""
    from cra.komponenten_klassen import build_gruppen_prompt, gruppiere

    gruppe = gruppiere([{'id': 1, 'komponent_key': 'pkg:pypi/a', 'name': 'a',
                         'version': '1', 'purl': 'pkg:pypi/a@1'}])[0]
    ohne = build_gruppen_prompt({'name': PROJ, 'produkt': 'Gateway'}, '1.0.0', gruppe)
    assert 'keine — zum Überwachungsweg liegt in der Akte nichts vor' in ohne
    assert 'Dependabot' not in ohne

    mit = build_gruppen_prompt({'name': PROJ, 'produkt': 'Gateway'}, '1.0.0', gruppe,
                               nachweise=['Automatischer Abgleich eingerichtet '
                                          '(Quelle: github).'])
    assert 'Quelle: github' in mit
    # Der Auftrag bleibt eng: ein Text, kein Status, keine Komponentenliste.
    assert 'Gib **nur** den Begründungstext zurück' in mit
    assert 'Art. 13 Abs. 5' in mit


def test_nachweise_nennen_nur_was_in_der_akte_steht():
    from cra.komponenten_klassen import nachweise_aus_projekt

    assert nachweise_aus_projekt(None, None) == []
    assert nachweise_aus_projekt({}, {'support_jahre': 0, 'update_kanal': ''}) == []
    zeilen = nachweise_aus_projekt(
        {'source': 'github', 'last_sync_at': '2026-10-22T04:00:00'},
        {'support_jahre': 7, 'sicherheitsupdate_kanal': 'GHCR',
         'sicherheitsupdates_kostenlos': 1},
        repo='owner/repo')
    text = ' '.join(zeilen)
    assert 'owner/repo' in text and 'github' in text
    assert '7 Jahre' in text and 'GHCR' in text and 'kostenlos' in text


# ── Zuordnung Befund → Komponente (#1774) ────────────────────────────────────

def test_zuordnung_bleibt_exakt():
    """``requests-oauthlib`` ist nicht ``requests`` — eine Teilstring-Suche
    hängte den Befund an die falsche Abhängigkeit."""
    from cra.komponenten_befunde import je_komponente

    komponenten = [
        {'komponent_key': 'pkg:pypi/requests', 'name': 'requests'},
        {'komponent_key': 'pkg:pypi/requests-oauthlib', 'name': 'requests-oauthlib'},
    ]
    treffer = je_komponente(
        [{'id': 1, 'cve_id': 'CVE-2026-9', 'affected_component': 'requests-oauthlib',
          'schwere': 'high', 'status': 'open', 'source': 'manual'}],
        komponenten)
    assert list(treffer) == ['pkg:pypi/requests-oauthlib']
    assert treffer['pkg:pypi/requests-oauthlib'][0]['offen'] is True


def test_befund_ohne_komponente_erscheint_nicht():
    from cra.komponenten_befunde import je_komponente

    treffer = je_komponente(
        [{'id': 1, 'cve_id': 'CVE-2026-9', 'affected_component': 'server/app.py',
          'schwere': 'high', 'status': 'open', 'source': 'pentest'}],
        [{'komponent_key': 'pkg:pypi/flask', 'name': 'flask'}])
    assert treffer == {}


def test_pentest_befund_wird_zugeordnet_wenn_er_das_paket_nennt():
    """Pentest-Befunde tragen meist das System — nennt der Prüfer aber das
    Paket, gehört der Befund an die Komponente."""
    from cra.komponenten_befunde import je_komponente

    treffer = je_komponente(
        [{'id': 7, 'cve_id': 'PT-3-F1', 'affected_component': 'jinja2',
          'schwere': 'medium', 'status': 'open', 'source': 'pentest'}],
        [{'komponent_key': 'pkg:pypi/jinja2', 'name': 'jinja2'}])
    assert treffer['pkg:pypi/jinja2'][0]['quelle_label'] == 'Pentest'


def test_widerspruch_nur_bei_nicht_relevant():
    """``geprueft`` mit offenem Befund ist der normale Lauf — ein Prüfpunkt,
    der dabei anschlägt, wird abgeschaltet."""
    from cra.komponenten_befunde import widersprueche

    befunde = {'pkg:pypi/a': [{'cve_id': 'CVE-1', 'offen': True, 'schwere': 'high'}],
               'pkg:pypi/b': [{'cve_id': 'CVE-2', 'offen': False, 'schwere': 'high'}]}
    komponenten = [
        {'id': 1, 'komponent_key': 'pkg:pypi/a', 'name': 'a', 'version': '1',
         'bewertung_status': 'nicht_relevant'},
        {'id': 2, 'komponent_key': 'pkg:pypi/a', 'name': 'a2', 'version': '1',
         'bewertung_status': 'geprueft'},
        {'id': 3, 'komponent_key': 'pkg:pypi/b', 'name': 'b', 'version': '1',
         'bewertung_status': 'nicht_relevant'},
    ]
    wid = widersprueche(komponenten, befunde)
    assert [w['id'] for w in wid] == [1]
    assert wid[0]['befunde'] == ['CVE-1']


def test_anreichern_bleibt_additiv():
    from cra.komponenten_befunde import anreichern

    zeilen = anreichern(
        [{'id': 1, 'komponent_key': 'pkg:pypi/a', 'name': 'a', 'lizenz': 'MIT'}],
        {'pkg:pypi/a': [{'cve_id': 'CVE-1', 'offen': True, 'schwere': 'critical'},
                        {'cve_id': 'CVE-2', 'offen': False, 'schwere': 'high'}]})
    assert zeilen[0]['lizenz'] == 'MIT'        # vorhandene Felder unberührt
    assert zeilen[0]['befunde_offen'] == 1
    assert zeilen[0]['befund_schwere'] == 'critical'


# ── Durch die REST-Schicht ───────────────────────────────────────────────────

def _sbom_json(eintraege):
    return json.dumps({'bomFormat': 'CycloneDX', 'specVersion': '1.5',
                       'components': [
                           {'name': n, 'version': v, 'purl': p,
                            'licenses': [{'license': {'id': 'MIT'}}]}
                           for n, v, p in eintraege]})


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


def _sbom_mit_komponenten(client, auth_headers, version='1.0.0'):
    r = client.post(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers,
                    json={'release_version': version, 'artefakt': 'anwendung',
                          'sbom_format': 'cyclonedx', 'sbom_datum': '2026-10-22'})
    assert r.status_code == 201, r.json
    sid = r.json['id']
    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten',
                    headers=auth_headers,
                    json={'sbom': _sbom_json([
                        ('flask', '3.0.0', 'pkg:pypi/flask@3.0.0'),
                        ('jinja2', '3.1.4', 'pkg:pypi/jinja2@3.1.4'),
                        ('libc6', '2.36', 'pkg:deb/debian/libc6@2.36'),
                        ('musl', '1.2.5', 'pkg:apk/alpine/musl@1.2.5'),
                    ])})
    assert r.status_code == 201, r.json
    return sid


def test_klassen_endpunkt_liefert_gruppen(client, auth_headers, projekt):
    sid = _sbom_mit_komponenten(client, auth_headers)
    r = client.get(f'{CRA}/projekte/{PROJ}/sbom/{sid}/klassen?version=1.0.0',
                   headers=auth_headers)
    assert r.status_code == 200, r.json
    keys = {g['key'] for g in r.json['gruppen']}
    assert keys == {'anwendung:pypi', 'betriebssystem:deb', 'betriebssystem:apk'}
    assert r.json['komponenten'] == 4


def test_prompt_endpunkt_kennt_die_gruppe(client, auth_headers, projekt):
    sid = _sbom_mit_komponenten(client, auth_headers)
    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/klassen/prompt',
                    headers=auth_headers, json={'gruppe': 'anwendung:pypi'})
    assert r.status_code == 200, r.json
    assert 'Art. 13 Abs. 5' in r.json['prompt']
    assert 'pypi' in r.json['prompt']
    assert r.json['gruppe']['anzahl'] == 2

    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/klassen/prompt',
                    headers=auth_headers, json={'gruppe': 'gibt-es-nicht'})
    assert r.status_code == 404


def test_uebernahme_wirkt_auf_die_gruppe_und_vermerkt_die_herkunft(
        client, auth_headers, projekt):
    sid = _sbom_mit_komponenten(client, auth_headers)
    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/klassen/uebernehmen',
                    headers=auth_headers,
                    json={'gruppe': 'betriebssystem:deb', 'status': 'geprueft',
                          'notiz': 'Pakete der Distribution, versorgt über den '
                                   'Image-Rebuild bei jedem Release.',
                          'ki_entwurf': True, 'provider': 'ollama'})
    assert r.status_code == 200, r.json
    assert r.json['geaendert'] == 1
    assert r.json['ki_vermerkt'] == 1

    rows = client.get(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten',
                      headers=auth_headers).json
    je = {k['name']: k for k in rows}
    assert je['libc6']['bewertung_status'] == 'geprueft'
    assert je['musl']['bewertung_status'] == 'offen'     # andere Gruppe
    assert je['flask']['bewertung_status'] == 'offen'

    # Die Herkunft steht im Register — und gilt als geprüft, weil ein Mensch
    # den Entwurf für die Gruppe übernommen hat (#1765/#1773).
    from shared.ki_herkunft import fuer_projekt
    eintraege = fuer_projekt('cra', PROJ, 'sbom_komponente')
    assert str(je['libc6']['id']) in eintraege
    eintrag = eintraege[str(je['libc6']['id'])]
    assert eintrag['ki'] is True
    assert eintrag['geprueft'] is True
    assert eintrag['provider'] == 'ollama'
    assert eintrag['geprueft_von']


def test_uebernahme_ersetzt_keine_vorhandene_bewertung(client, auth_headers, projekt):
    """Eine gesetzte Bewertung ist die Aussage eines Menschen."""
    sid = _sbom_mit_komponenten(client, auth_headers)
    rows = client.get(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten',
                      headers=auth_headers).json
    flask_id = next(k['id'] for k in rows if k['name'] == 'flask')
    client.put(f'{CRA}/projekte/{PROJ}/sbom/komponenten/bewertung',
               headers=auth_headers,
               json={'ids': [flask_id], 'status': 'nicht_relevant',
                     'notiz': 'Nur im Entwicklungsbild enthalten, nicht ausgeliefert.'})

    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/klassen/uebernehmen',
                    headers=auth_headers,
                    json={'gruppe': 'anwendung:pypi', 'status': 'geprueft',
                          'notiz': 'Abhängigkeiten der Anwendung, überwacht über '
                                   'den Abhängigkeits-Scan.'})
    assert r.status_code == 200, r.json
    assert r.json['geaendert'] == 1 and flask_id not in r.json['ids']
    rows = {k['id']: k for k in client.get(
        f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten', headers=auth_headers).json}
    assert rows[flask_id]['bewertung_status'] == 'nicht_relevant'


def test_einzelpruefung_braucht_bestaetigung(client, auth_headers, projekt):
    sid = _sbom_mit_komponenten(client, auth_headers)
    r = client.post(f'{CRA}/projekte/{PROJ}/vuln', headers=auth_headers,
                    json={'cve_id': 'CVE-2026-1773', 'titel': 'Fund in flask',
                          'schwere': 'high', 'affected_component': 'flask',
                          'status': 'open', 'source': 'manual'})
    assert r.status_code in (200, 201), r.json

    gruppen = client.get(f'{CRA}/projekte/{PROJ}/sbom/{sid}/klassen?version=1.0.0',
                         headers=auth_headers).json['gruppen']
    assert gruppen[0]['klasse'] == 'einzelpruefung'
    assert gruppen[0]['anzahl'] == 1

    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/klassen/uebernehmen',
                    headers=auth_headers,
                    json={'gruppe': 'einzelpruefung', 'status': 'geprueft',
                          'notiz': 'Befund wird in C3 behandelt, Fix eingeplant.'})
    assert r.status_code == 428
    assert r.json['error'] == 'einzelpruefung_confirm'

    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/klassen/uebernehmen',
                    headers=auth_headers,
                    json={'gruppe': 'einzelpruefung', 'status': 'geprueft',
                          'notiz': 'Befund wird in C3 behandelt, Fix eingeplant.',
                          'confirm_einzel': True})
    assert r.status_code == 200, r.json
    assert r.json['geaendert'] == 1


def test_komponentenliste_zeigt_den_befund(client, auth_headers, projekt):
    """Die Quelle steht mit dabei: Ein Dependabot-Befund ist kein eigener Fund
    (Art. 13 Abs. 6), ein Pentest-Befund schon — das muss am Befund ablesbar
    sein, nicht nur im C3-Reiter."""
    from cra.db import upsert_vuln

    sid = _sbom_mit_komponenten(client, auth_headers)
    # Über ``upsert_vuln``, weil ``POST /vuln`` die Quelle bewusst nicht setzt:
    # Was ein Mensch hier einträgt, ist ein manueller Befund.
    upsert_vuln(DB, PROJ, {'cve_id': 'CVE-2026-1774', 'titel': 'Fund in jinja2',
                           'schwere': 'critical',
                           'affected_component': 'jinja2@3.1.4',
                           'status': 'open', 'source': 'github_dependabot'})
    rows = {k['name']: k for k in client.get(
        f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten', headers=auth_headers).json}
    assert rows['jinja2']['befunde_offen'] == 1
    assert rows['jinja2']['befund_schwere'] == 'critical'
    assert rows['jinja2']['befunde'][0]['quelle_label'] == 'Dependabot'
    assert rows['flask']['befunde_offen'] == 0


def test_gate_meldet_den_widerspruch(client, auth_headers, projekt):
    """Die Akte widerspricht sich: „nicht relevant" trotz offenem Befund."""
    from cra.konformitaet_gate import evaluate

    sid = _sbom_mit_komponenten(client, auth_headers)
    client.post(f'{CRA}/projekte/{PROJ}/vuln', headers=auth_headers,
                json={'cve_id': 'CVE-2026-1775', 'titel': 'Fund in libc6',
                      'schwere': 'medium', 'affected_component': 'libc6',
                      'status': 'open', 'source': 'github_advisory'})
    rows = client.get(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten',
                      headers=auth_headers).json
    libc = next(k['id'] for k in rows if k['name'] == 'libc6')
    client.put(f'{CRA}/projekte/{PROJ}/sbom/komponenten/bewertung',
               headers=auth_headers,
               json={'ids': [libc], 'status': 'nicht_relevant',
                     'notiz': 'Berührt die Sicherheitseigenschaften nicht.'})

    erg = evaluate(PROJ, version='1.0.0')
    assert erg['release_befunde']['komponenten_befund_widerspruch'] == ['libc6 2.36']
    # Flach **und** im Befund-Block: Der Release-Bericht liest die ``quelle``
    # des Katalog-Eintrags flach; fehlte sie dort, stünde im Bericht „nicht
    # geprüft", obwohl gerechnet wurde (die Lehre aus #1762).
    assert erg['komponenten_befund_widerspruch'] == ['libc6 2.36']
    punkt = next(p for p in erg['offene_punkte'] if p['typ'] == 'komponenten_befunde')
    assert punkt['ampel_wirkung'] == 'bedingt'   # Mangel in der Akte, nicht rot
    assert 'nicht relevant' in punkt['titel']

    # Und der Katalog-Eintrag kommt im Bericht als gerechnetes Ergebnis an.
    from cra.release_bericht import gerechnetes_ergebnis
    from cra.release_checkliste import KATALOG
    item = next(i for i in KATALOG if i.id == 'komponenten_befunde_konsistent')
    ergebnis, text = gerechnetes_ergebnis(item.quelle, erg)
    assert ergebnis != 'ungeprueft', text
    assert 'nicht relevant' in text


def test_jeder_gerechnete_punkt_ist_dreifach_verdrahtet():
    """Ein gerechneter Prüfpunkt steht an **drei** Stellen — und nur zusammen
    ergeben sie eine Aussage.

    Der flache Schlüssel in ``evaluate()``, die Auswertung im Bericht und der
    Fall im Releases-Panel. Fehlt einer, rechnet die Anwendung richtig und zeigt
    „nicht bestimmbar — Grundlage fehlt" — eine Behauptung über die Akte, die
    aus einer vergessenen Zeile Code stammt. Genau das ist bei #1774 passiert
    und im Firefox-Durchlauf aufgefallen, nicht im grünen Testlauf. Dieselbe
    Fehlerklasse wie die Spiegel-Listen aus #1731/#1735.
    """
    import re
    from pathlib import Path

    from cra.release_bericht import _GERECHNET_AUSWERTUNG
    from cra.release_checkliste import KATALOG

    panel = Path('frontend/src/views/cra/ReleasesPanel.vue').read_text(encoding='utf-8')
    faelle = set(re.findall(r"case '([a-z_]+)'", panel))
    block = re.search(r"const TYP: Record<string, string> = \{(.*?)\n  \}", panel, re.S)
    assert block, 'TYP-Zuordnung im Releases-Panel nicht gefunden'
    typ_map = dict(re.findall(r"([a-z_]+):\s*'([a-z_]+)'", block.group(1)))

    fehlend: list[str] = []
    for item in KATALOG:
        if item.art != 'gerechnet' or not item.quelle:
            continue
        if item.quelle not in _GERECHNET_AUSWERTUNG:
            fehlend.append(f'{item.id}: keine Auswertung im Bericht')
        if item.quelle not in faelle:
            fehlend.append(f'{item.id}: kein Fall im Releases-Panel')
        elif item.quelle not in typ_map:
            fehlend.append(f'{item.id}: kein Punkt-Typ im Releases-Panel')
    assert not fehlend, '\n'.join(fehlend)


def test_gate_ohne_komponentenliste_sagt_ungeprueft(client, auth_headers, projekt):
    """``None`` heißt „nicht geprüft". Eine 0 wäre die Aussage, es sei sauber."""
    from cra.komponenten_befunde import befund_fuer_release

    client.post(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers,
                json={'release_version': '2.0.0', 'sbom_format': 'spdx',
                      'sbom_datum': '2026-10-22'})
    b = befund_fuer_release(DB, PROJ, '2.0.0')
    assert b['ohne_komponentenliste'] is True

    from cra.konformitaet_gate import evaluate
    erg = evaluate(PROJ, version='2.0.0')
    assert erg['release_befunde']['komponenten_befund_widerspruch'] is None
    assert erg['komponenten_befund_widerspruch'] is None
