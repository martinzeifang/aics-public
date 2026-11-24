"""SBOM aus der Container-Registry holen (#1770).

Aus der Rückfrage des Anwenders: „Wie kann das System die SBOM dann extrahieren,
um sie auszulesen/vergleichen?" — #1769 liest Release-Assets und Dateien aus
einem Verzeichnis, beides setzt eine **Datei** voraus. Für ein Container-Produkt
hängt die SBOM aber als signierte Attestation am Image; die Suite selbst macht
es genau so.

Der Schwerpunkt dieser Tests liegt auf der Positivliste. Die Registry steht in
einer **Eingabe** — ohne Liste wäre der Abruf gegen einen frei wählbaren Host
genau der Weg, den #1761 ausgeschlossen und #1769 umgangen hat.
"""
from __future__ import annotations

import base64
import json

import pytest

SPDX = {
    'spdxVersion': 'SPDX-2.3', 'name': 'beispiel',
    'packages': [
        {'name': 'requests', 'versionInfo': '2.32.3', 'licenseConcluded': 'Apache-2.0'},
        {'name': 'jinja2', 'versionInfo': '3.1.4', 'licenseConcluded': 'BSD-3-Clause'},
    ],
}
DIGEST = 'a' * 64


# ── Referenz erkennen und zerlegen ──────────────────────────────────────────

@pytest.mark.parametrize('wert,erwartet', [
    ('ghcr.io/owner/name:1.2.3', True),
    ('ghcr.io/owner/name@sha256:' + DIGEST, True),
    ('https://github.com/owner/name/releases/download/x/sbom.json', False),
    ('/data/cra/sbom/projekt/datei.json', False),
    ('', False),
    ('nurtext', False),
])
def test_image_referenz_erkennen(wert, erwartet):
    from cra.sbom_registry import ist_image_referenz
    assert ist_image_referenz(wert) is erwartet


def test_fremde_registry_wird_abgewiesen():
    """Die Registry kommt aus einer Eingabe — ohne Positivliste wäre das der
    Abruf gegen einen frei wählbaren Host."""
    from cra.sbom_registry import RegistryFehler, zerlege

    for schlecht in ('evil.example.com/x/y:1', '127.0.0.1:5000/a/b:1',
                     'docker.io/library/nginx:1', 'localhost:5000/a/b:1'):
        with pytest.raises(RegistryFehler) as e:
            zerlege(schlecht)
        assert 'Positivliste' in str(e.value)


def test_ghcr_wird_zerlegt():
    from cra.sbom_registry import zerlege

    t = zerlege('ghcr.io/martinzeifang/ai_compliance_suite:8.0.1')
    assert t == {'host': 'ghcr.io', 'repo': 'martinzeifang/ai_compliance_suite',
                 'tag': '8.0.1', 'digest': ''}


# ── Umleitungen: der eigentliche Angriffspunkt ──────────────────────────────

def test_blob_speicher_der_registry_ist_erlaubt():
    """GHCR legt Blobs auf einem eigenen Host ab und leitet dorthin um. Dieser
    Host gehört in die Liste — die Prüfung deswegen aufzuweichen wäre der
    falsche Ausweg."""
    from cra.sbom_registry import erlaubte_hosts

    h = erlaubte_hosts('ghcr.io')
    assert 'ghcr.io' in h
    assert 'pkg-containers.githubusercontent.com' in h


def test_umleitung_auf_fremden_host_wird_abgewiesen():
    from cra.sbom_registry import RegistryFehler, _pruefe_url

    with pytest.raises(RegistryFehler) as e:
        _pruefe_url('https://evil.example.com/blob', 'ghcr.io')
    assert 'nicht erlaubten Host' in str(e.value)


def test_nur_https():
    from cra.sbom_registry import RegistryFehler, _pruefe_url

    with pytest.raises(RegistryFehler):
        _pruefe_url('http://ghcr.io/v2/x/manifests/1', 'ghcr.io')


def test_subdomain_des_erlaubten_hosts_ist_erlaubt():
    from cra.sbom_registry import _pruefe_url

    _pruefe_url('https://cdn.pkg-containers.githubusercontent.com/x', 'ghcr.io')


# ── Der Abruf selbst (ohne Netz) ────────────────────────────────────────────

def _envelope(predicate_type='https://spdx.dev/Document', predicate=None):
    aussage = {'predicateType': predicate_type,
               'predicate': predicate if predicate is not None else SPDX}
    return json.dumps({'payload': base64.b64encode(
        json.dumps(aussage).encode()).decode()}).encode()


def test_abruf_liefert_das_spdx_dokument(monkeypatch):
    from cra import sbom_registry as sr

    monkeypatch.setattr(sr, '_token', lambda h, r: 'tok')

    class _Kopf:
        status_code = 200
        headers = {'docker-content-digest': 'sha256:' + DIGEST}

    monkeypatch.setattr('requests.head', lambda *a, **kw: _Kopf())

    def fake_hole(url, host, token, accept=None):
        if url.endswith('.att'):
            return json.dumps({'layers': [{'digest': 'sha256:' + 'b' * 64}]}).encode()
        return _envelope()

    monkeypatch.setattr(sr, '_hole', fake_hole)
    r = sr.hole_sbom('ghcr.io/owner/name:1.0.0')
    assert r['digest'] == 'sha256:' + DIGEST
    assert json.loads(r['inhalt'])['packages'][0]['name'] == 'requests'


def test_attestation_ohne_spdx_wird_benannt(monkeypatch):
    """Eine Provenance-Attestation ist keine SBOM. Der Fehler muss das sagen,
    statt eine leere Liste zu liefern."""
    from cra import sbom_registry as sr

    monkeypatch.setattr(sr, '_token', lambda h, r: 'tok')

    class _Kopf:
        status_code = 200
        headers = {'docker-content-digest': 'sha256:' + DIGEST}

    monkeypatch.setattr('requests.head', lambda *a, **kw: _Kopf())
    monkeypatch.setattr(sr, '_hole', lambda url, host, token, accept=None: (
        json.dumps({'layers': [{'digest': 'sha256:' + 'b' * 64}]}).encode()
        if url.endswith('.att')
        else _envelope('https://slsa.dev/provenance/v1', {'builder': {}})))

    with pytest.raises(sr.RegistryFehler) as e:
        sr.hole_sbom('ghcr.io/owner/name:1.0.0')
    assert 'kein SPDX' in str(e.value)


def test_ergebnis_passt_durch_den_parser(monkeypatch):
    """Was die Registry liefert, muss derselbe Parser lesen können wie eine
    hochgeladene Datei — sonst hätte der Weg zwei Wahrheiten."""
    from cra import sbom_registry as sr
    from cra.sbom_komponenten import parse_sbom

    monkeypatch.setattr(sr, '_token', lambda h, r: 'tok')

    class _Kopf:
        status_code = 200
        headers = {'docker-content-digest': 'sha256:' + DIGEST}

    monkeypatch.setattr('requests.head', lambda *a, **kw: _Kopf())
    monkeypatch.setattr(sr, '_hole', lambda url, host, token, accept=None: (
        json.dumps({'layers': [{'digest': 'sha256:' + 'b' * 64}]}).encode()
        if url.endswith('.att') else _envelope()))

    komponenten, fmt = parse_sbom(sr.hole_sbom('ghcr.io/owner/name:1.0.0')['inhalt'])
    assert fmt == 'spdx'
    assert {k['name'] for k in komponenten} == {'requests', 'jinja2'}


def test_zeile_nennt_die_gespeicherte_zahl_nicht_die_der_datei(client, auth_headers, monkeypatch):
    """Mehrfach genannte Pakete fallen unter die Eindeutigkeitsregel (#1761).

    Stünde in der Zeile die Zahl aus der Datei, zeigte sie 189 und die Liste
    daneben 184 — und die Differenz sähe aus wie eine Falschangabe der SBOM,
    obwohl sie aus unserer eigenen Zusammenfassung stammt. Beobachtet beim
    Abruf der echten AICS-Attestation.
    """
    from cra import sbom_registry as sr
    from server import license_state

    cur = license_state._current
    merk = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    proj = 'pytest-cra-1770'
    try:
        client.delete(f'/api/cra/projekte/{proj}', headers=auth_headers)
        client.post('/api/cra/projekte', headers=auth_headers,
                    json={'name': proj, 'unternehmen': 'pytest-firma-1770'})
        r = client.post(f'/api/cra/projekte/{proj}/sbom', headers=auth_headers,
                        json={'release_version': '1.0.0', 'sbom_format': 'spdx',
                              'blob_path': 'ghcr.io/owner/name:1.0.0'})
        sid = r.json['id']

        # Dieselbe Komponente zweimal — die Datei zählt drei, speicherbar sind zwei.
        doppelt = {'spdxVersion': 'SPDX-2.3', 'name': 'x', 'packages': [
            {'name': 'requests', 'versionInfo': '2.32.3', 'licenseConcluded': 'Apache-2.0'},
            {'name': 'requests', 'versionInfo': '2.32.3', 'licenseConcluded': 'Apache-2.0'},
            {'name': 'jinja2', 'versionInfo': '3.1.4', 'licenseConcluded': 'BSD-3-Clause'},
        ]}
        monkeypatch.setattr(sr, 'hole_sbom', lambda ref: {
            'inhalt': json.dumps(doppelt), 'digest': 'sha256:' + DIGEST,
            'referenz': 'ghcr.io/owner/name@sha256:' + DIGEST})

        a = client.post(f'/api/cra/projekte/{proj}/sbom/{sid}/aus-registry',
                        headers=auth_headers)
        assert a.status_code == 200, a.json
        assert a.json['in_datei'] == 3
        assert a.json['komponenten'] == 2
        assert a.json['zusammengefasst'] == 1

        zeile = next(x for x in client.get(f'/api/cra/projekte/{proj}/sbom',
                                           headers=auth_headers).json
                     if x['id'] == sid)
        # Beide Zahlen in der Oberfläche stimmen jetzt überein.
        assert zeile['komponenten_count'] == 2
        assert zeile['liste_anzahl'] == 2
    finally:
        client.delete(f'/api/cra/projekte/{proj}', headers=auth_headers)
        cur.state, cur.modules = merk[0], merk[1]


def test_kein_image_pfad_wird_erklaert(client, auth_headers):
    """Steht im Feld eine URL statt einer Referenz, muss die Meldung sagen,
    was erwartet wird — nicht nur, dass es nicht ging."""
    from server import license_state

    cur = license_state._current
    merk = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    proj = 'pytest-cra-1770b'
    try:
        client.delete(f'/api/cra/projekte/{proj}', headers=auth_headers)
        client.post('/api/cra/projekte', headers=auth_headers,
                    json={'name': proj, 'unternehmen': 'pytest-firma-1770'})
        r = client.post(f'/api/cra/projekte/{proj}/sbom', headers=auth_headers,
                        json={'release_version': '1.0.0', 'sbom_format': 'spdx',
                              'blob_path': 'https://example.com/sbom.json'})
        a = client.post(f'/api/cra/projekte/{proj}/sbom/{r.json["id"]}/aus-registry',
                        headers=auth_headers)
        assert a.status_code == 400
        assert 'ghcr.io/owner/name' in a.json['error']
    finally:
        client.delete(f'/api/cra/projekte/{proj}', headers=auth_headers)
        cur.state, cur.modules = merk[0], merk[1]
