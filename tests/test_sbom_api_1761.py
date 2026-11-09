"""REST-Schicht der Komponentenliste und der Upstream-Meldung (#1761).

Geprüft wird hier, was nur über die Endpunkte sichtbar ist: der Weg vom
Datei-Upload zur gerechneten Aussage, die Ablehnungen, und die beiden Stellen,
an denen die REST-Schicht eigene Entscheidungen trifft:

* ``komponenten_count`` der SBOM-Zeile wird nach dem Import **nachgezogen**.
  Stünde die alte Zahl weiter daneben, hätte dieselbe Aussage zwei Werte in der
  Datenbank — und der ältere wäre der falsche.
* Die SBOM wird **nicht** aus ``blob_path`` nachgeladen. Das wäre ein
  serverseitiger Abruf einer vom Anwender bestimmten URL (SSRF); der Inhalt
  kommt über den Endpunkt herein. Der Test hält fest, dass es keinen solchen
  Abruf-Endpunkt gibt.
"""
import json

import pytest

CRA = '/api/cra'
FIRMA = 'pytest-firma-api-1761'
PROJ = 'pytest-cra-api-1761'
VER = '3.1.0'
VOR = '3.0.0'

CYCLONEDX = json.dumps({
    'bomFormat': 'CycloneDX', 'specVersion': '1.5',
    'components': [
        {'name': 'lodash', 'version': '4.17.21', 'purl': 'pkg:npm/lodash@4.17.21',
         'licenses': [{'license': {'id': 'MIT'}}]},
        {'name': 'express', 'version': '4.18.2', 'purl': 'pkg:npm/express@4.18.2',
         'licenses': [{'license': {'id': 'MIT'}}]},
    ],
})

CYCLONEDX_ALT = json.dumps({
    'bomFormat': 'CycloneDX', 'specVersion': '1.5',
    'components': [
        {'name': 'lodash', 'version': '4.17.20', 'purl': 'pkg:npm/lodash@4.17.20'},
    ],
})


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


def _sbom(client, auth_headers, version: str) -> int:
    r = client.post(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers,
                    json={'release_version': version, 'sbom_format': 'cyclonedx',
                          'komponenten_count': 999})
    assert r.status_code == 201, r.json
    return r.json['id']


def test_import_speichert_liste_und_zieht_den_zaehler_nach(client, auth_headers, projekt):
    sid = _sbom(client, auth_headers, VER)
    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten',
                    headers=auth_headers, json={'sbom': CYCLONEDX})
    assert r.status_code == 201, r.json
    assert r.json['format'] == 'cyclonedx' and r.json['gespeichert'] == 2

    liste = client.get(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten',
                       headers=auth_headers)
    assert liste.status_code == 200
    assert {k['name'] for k in liste.json} == {'lodash', 'express'}
    assert all(k['bewertung_status'] == 'offen' for k in liste.json)

    # Die vorgetäuschten 999 Komponenten sind korrigiert — eine Aussage, ein Wert.
    sboms = client.get(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers).json
    zeile = next(s for s in sboms if s['id'] == sid)
    assert zeile['komponenten_count'] == 2
    assert zeile['lizenzen'] == ['MIT']


def test_unlesbare_datei_wird_abgewiesen(client, auth_headers, projekt):
    sid = _sbom(client, auth_headers, VER)
    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten',
                    headers=auth_headers, json={'sbom': 'kein json'})
    assert r.status_code == 400 and 'JSON' in r.json['error']
    r2 = client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten',
                     headers=auth_headers, json={})
    assert r2.status_code == 400


def test_import_in_fremde_sbom_ist_404(client, auth_headers, projekt):
    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/999999/komponenten',
                    headers=auth_headers, json={'sbom': CYCLONEDX})
    assert r.status_code == 404


def test_vergleich_und_bewertung_ueber_die_api(client, auth_headers, projekt):
    alt = _sbom(client, auth_headers, VOR)
    client.post(f'{CRA}/projekte/{PROJ}/sbom/{alt}/komponenten',
                headers=auth_headers, json={'sbom': CYCLONEDX_ALT})
    neu = _sbom(client, auth_headers, VER)
    client.post(f'{CRA}/projekte/{PROJ}/sbom/{neu}/komponenten',
                headers=auth_headers, json={'sbom': CYCLONEDX})

    r = client.get(f'{CRA}/projekte/{PROJ}/sbom/vergleich?version={VER}',
                   headers=auth_headers)
    assert r.status_code == 200, r.json
    b = r.json
    assert b['vorgaenger_version'] == VOR
    assert [z['name'] for z in b['vergleich']['neu']] == ['express']
    assert len(b['vergleich']['angehoben']) == 1
    assert b['pflichtig'] == 2 and len(b['unbewertet']) == 2

    ids = [u['id'] for u in b['unbewertet']]
    ohne_grund = client.put(f'{CRA}/projekte/{PROJ}/sbom/komponenten/bewertung',
                            headers=auth_headers,
                            json={'ids': ids, 'status': 'geprueft', 'notiz': 'ok'})
    assert ohne_grund.status_code == 400 and 'Begründung' in ohne_grund.json['error']

    ok = client.put(f'{CRA}/projekte/{PROJ}/sbom/komponenten/bewertung',
                    headers=auth_headers,
                    json={'ids': ids, 'status': 'geprueft',
                          'notiz': 'Changelog und Advisories geprüft'})
    assert ok.status_code == 200 and ok.json['geaendert'] == 2

    danach = client.get(f'{CRA}/projekte/{PROJ}/sbom/vergleich?version={VER}',
                        headers=auth_headers).json
    assert danach['unbewertet'] == [] and danach['bewertet'] == 2


def test_vergleich_braucht_eine_version(client, auth_headers, projekt):
    """Die Stückliste gehört zur Version, nicht zum Produkt."""
    r = client.get(f'{CRA}/projekte/{PROJ}/sbom/vergleich', headers=auth_headers)
    assert r.status_code == 400 and 'version' in r.json['error']


def test_upstream_status_nennt_pflicht_und_grund(client, auth_headers, projekt):
    sid = _sbom(client, auth_headers, VER)
    client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten',
                headers=auth_headers, json={'sbom': CYCLONEDX})
    eigen = client.post(f'{CRA}/projekte/{PROJ}/vuln', headers=auth_headers,
                        json={'cve_id': 'CVE-2026-9001', 'schwere': 'high',
                              'affected_component': 'lodash'}).json['id']
    client.post(f'{CRA}/projekte/{PROJ}/vuln', headers=auth_headers,
                json={'cve_id': 'CVE-2026-9002', 'schwere': 'low',
                      'affected_component': 'unser-eigener-code'})

    r = client.get(f'{CRA}/projekte/{PROJ}/vuln/upstream', headers=auth_headers)
    assert r.status_code == 200, r.json
    assert r.json['befund']['pflichtig'] == 1
    pflicht = r.json['pflicht']
    assert pflicht[str(eigen)]['pflichtig'] is True
    # Wo keine Pflicht besteht, steht der Grund — sonst sieht „—" in der
    # Oberfläche wie ein Versäumnis aus.
    andere = [v for k, v in pflicht.items() if k != str(eigen)]
    assert andere and all(not v['pflichtig'] and v['grund'] for v in andere)


def test_meldung_braucht_kanal_und_referenz(client, auth_headers, projekt):
    vid = client.post(f'{CRA}/projekte/{PROJ}/vuln', headers=auth_headers,
                      json={'cve_id': 'CVE-2026-9003',
                            'affected_component': 'lodash'}).json['id']
    fehlt = client.put(f'{CRA}/projekte/{PROJ}/vuln/{vid}/upstream',
                       headers=auth_headers, json={'status': 'gemeldet'})
    assert fehlt.status_code == 400 and 'Kanal' in fehlt.json['error']

    ok = client.put(f'{CRA}/projekte/{PROJ}/vuln/{vid}/upstream', headers=auth_headers,
                    json={'status': 'gemeldet', 'kanal': 'security@lodash.test',
                          'referenz': 'UPSTREAM-42'})
    assert ok.status_code == 200, ok.json
    zeile = next(v for v in client.get(f'{CRA}/projekte/{PROJ}/vuln?status=open',
                                       headers=auth_headers).json
                 if v['id'] == vid)
    assert zeile['upstream_status'] == 'gemeldet'
    assert zeile['upstream_referenz'] == 'UPSTREAM-42'
    assert zeile['upstream_gemeldet_am']


def test_es_gibt_keinen_abruf_der_sbom_aus_blob_path(client, auth_headers, projekt):
    """Ein Endpunkt, der ``blob_path`` serverseitig holt, wäre SSRF. Der Inhalt
    kommt über den Import-Endpunkt herein — und nur dort."""
    sid = _sbom(client, auth_headers, VER)
    for pfad in (f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten/fetch',
                 f'{CRA}/projekte/{PROJ}/sbom/{sid}/fetch'):
        assert client.post(pfad, headers=auth_headers, json={}).status_code == 404, pfad


def test_sbom_liste_nennt_die_erfasste_komponentenzahl(client, auth_headers, projekt):
    """Die SBOM-Liste muss selbst sagen, ob eine Komponentenliste vorliegt.

    Im Firefox-Durchlauf zeigte die Oberfläche bei **jeder** SBOM „⚠️ keine
    Liste" — auch dort, wo Komponenten erfasst waren. Grund: Die Warnung las
    den erst beim Aufklappen gefüllten Store, also „noch nicht geladen" statt
    „nicht vorhanden". Für ein Werkzeug, das Nachweisführung verkauft, ist ein
    falsches „nicht belegbar" so schlimm wie ein falsches „belegt".

    ``liste_anzahl`` ist bewusst **nicht** ``komponenten_count``: Letzteres ist
    die Zahl, die die SBOM-Datei nennt, Ersteres die Zahl der tatsächlich
    erfassten Zeilen.
    """
    sid = _sbom(client, auth_headers, '9.9.0')

    vorher = client.get(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers).json
    zeile = next(s for s in vorher if s['id'] == sid)
    assert zeile['liste_anzahl'] == 0          # angelegt, aber nichts importiert
    assert zeile['komponenten_count'] == 999   # die Behauptung der Datei

    client.post(f'{CRA}/projekte/{PROJ}/sbom/{sid}/komponenten',
                headers=auth_headers, json={'sbom': CYCLONEDX})

    nachher = client.get(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers).json
    zeile = next(s for s in nachher if s['id'] == sid)
    assert zeile['liste_anzahl'] == 2
