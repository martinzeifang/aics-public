"""SBOM dort einlesen, wo sie liegt (#1769).

Aus der Rückmeldung des Anwenders: „Ich finde die Software sollte das auch
finden, wenn es an der richtigen Stelle liegt." Bis v8.0.1 fand der Autodetect
nur den **Ort** einer SBOM und trug `komponenten_count: 0`, `lizenzen: []` ein —
Format, Anzahl und Lizenzen waren Handarbeit, und die Komponentenliste (#1761)
blieb leer, weil ihr die Datei fehlte.

Die Abgrenzung gegen #1761 ist der Kern dieser Tests: Dort wurde ein Abruf aus
`blob_path` **ausgeschlossen** (eine eingetippte URL, beliebiger Host). Hier
wird über die Asset-ID an einen festen Host gesprochen. Diese Grenze wird
geprüft, nicht nur beschrieben.
"""
from __future__ import annotations

import json

import pytest

CRA = '/api/cra'
FIRMA = 'pytest-firma-1769'
PROJ = 'pytest-cra-1769'

CYCLONEDX = json.dumps({
    'bomFormat': 'CycloneDX', 'specVersion': '1.5',
    'components': [
        {'name': 'requests', 'version': '2.32.3', 'publisher': 'PSF',
         'purl': 'pkg:pypi/requests@2.32.3',
         'licenses': [{'license': {'id': 'Apache-2.0'}}]},
        {'name': 'jinja2', 'version': '3.1.4', 'publisher': 'Pallets',
         'purl': 'pkg:pypi/jinja2@3.1.4',
         'licenses': [{'license': {'id': 'BSD-3-Clause'}}]},
    ],
})


# ── Auswerten: aus der Datei werden die Felder ──────────────────────────────

def test_auswerten_liefert_was_sonst_getippt_wird():
    from cra.sbom_quellen import auswerten

    r = auswerten(CYCLONEDX)
    assert r is not None
    assert r['sbom_format'] == 'cyclonedx'
    assert r['komponenten_count'] == 2
    assert r['lizenzen'] == ['Apache-2.0', 'BSD-3-Clause']
    assert {k['name'] for k in r['komponenten']} == {'requests', 'jinja2'}


def test_unlesbares_liefert_nichts_statt_halber_liste():
    """Eine halb verstandene Datei ergäbe eine halbe Komponentenliste — und die
    sähe aus wie eine vollständige (gleiche Regel wie beim Import, #1761)."""
    from cra.sbom_quellen import auswerten

    assert auswerten('kein json') is None
    assert auswerten('{}') is None
    assert auswerten(json.dumps({'bomFormat': 'CycloneDX', 'components': []})) is None


# ── Der Ablageort im Dateisystem ────────────────────────────────────────────

def test_ablageort_wird_gelesen(tmp_path):
    from cra.sbom_quellen import finde_lokal

    ordner = tmp_path / PROJ
    ordner.mkdir(parents=True)
    (ordner / 'gateway-1.9.0.cdx.json').write_text(CYCLONEDX, encoding='utf-8')

    funde = finde_lokal(PROJ, basis=tmp_path)
    assert len(funde) == 1
    f = funde[0]
    assert f['release_version'] == '1.9.0'       # aus dem Dateinamen
    assert f['sbom_format'] == 'cyclonedx'       # aus dem Inhalt, nicht aus der Endung
    assert f['komponenten_count'] == 2
    assert f['quelle'].startswith('auto:lokal:')
    assert len(f['komponenten']) == 2


def test_ablageort_ohne_verzeichnis_ist_kein_fehler(tmp_path):
    from cra.sbom_quellen import finde_lokal

    assert finde_lokal('gibt-es-nicht', basis=tmp_path) == []


def test_projektname_wird_nicht_zum_pfad(tmp_path):
    """Ein Projektname ist eine Eingabe. `../` darin darf nicht aus dem
    Ablageort herausführen."""
    from cra.sbom_quellen import finde_lokal

    (tmp_path / 'geheim').mkdir()
    (tmp_path / 'geheim' / 'x.json').write_text(CYCLONEDX, encoding='utf-8')
    assert finde_lokal('../geheim', basis=tmp_path) == []


def test_zu_grosse_datei_wird_uebersprungen(tmp_path, monkeypatch):
    from cra import sbom_quellen

    ordner = tmp_path / PROJ
    ordner.mkdir(parents=True)
    (ordner / 'gross-2.0.0.cdx.json').write_text(CYCLONEDX, encoding='utf-8')
    monkeypatch.setattr(sbom_quellen, 'MAX_BYTES', 10)
    assert sbom_quellen.finde_lokal(PROJ, basis=tmp_path) == []


# ── Die Grenze gegen #1761: fester Host, keine eingetippte URL ──────────────

def test_asset_wird_ueber_die_id_geholt_nicht_ueber_eine_url(monkeypatch):
    """Der Pfad ist unserer; aus der Antwort kommt nur die Nummer.

    Das ist der Unterschied zu dem Abruf, den #1761 ausgeschlossen hat: Dort
    hätte eine vom Anwender eingetippte `blob_path`-URL den Host bestimmt.
    """
    from cra import sbom_quellen

    gerufen = {}

    class _Antwort:
        status_code = 200

        def iter_content(self, chunk_size=0):
            yield CYCLONEDX.encode('utf-8')

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_get(url, headers=None, timeout=0, stream=False):
        gerufen['url'] = url
        gerufen['accept'] = (headers or {}).get('Accept')
        return _Antwort()

    import requests
    monkeypatch.setattr(requests, 'get', fake_get)
    monkeypatch.setattr('shared.github_config.get_github_token', lambda: 'tok')
    monkeypatch.setattr('shared.github_config.github_headers', lambda: {'Authorization': 'Bearer tok'})

    inhalt = sbom_quellen.lade_release_asset('martinzeifang', 'aics-public', 4711)
    assert inhalt and 'CycloneDX' in inhalt
    assert gerufen['url'] == (
        'https://api.github.com/repos/martinzeifang/aics-public/releases/assets/4711')
    assert gerufen['accept'] == 'application/octet-stream'


@pytest.mark.parametrize('owner,repo', [
    ('../evil', 'repo'), ('owner', 'a/b'), ('owner', ''), ('ev il', 'repo'),
    ('owner@host', 'repo'),
])
def test_unzulaessige_repo_bestandteile_fuehren_zu_keinem_abruf(monkeypatch, owner, repo):
    from cra import sbom_quellen

    def fake_get(*a, **kw):  # pragma: no cover — darf nicht laufen
        raise AssertionError('Es darf kein Abruf stattfinden')

    import requests
    monkeypatch.setattr(requests, 'get', fake_get)
    monkeypatch.setattr('shared.github_config.get_github_token', lambda: 'tok')
    monkeypatch.setattr('shared.github_config.github_headers', lambda: {})
    assert sbom_quellen.lade_release_asset(owner, repo, 1) is None


def test_ohne_token_kein_abruf(monkeypatch):
    """Die Asset-API verlangt Authentifizierung; ein anonymer Umweg über eine
    Download-URL wäre genau der Abruf, den wir nicht wollen."""
    from cra import sbom_quellen

    import requests
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError('kein Abruf ohne Token')))
    monkeypatch.setattr('shared.github_config.get_github_token', lambda: '')
    assert sbom_quellen.lade_release_asset('owner', 'repo', 1) is None


def test_zu_grosses_asset_wird_abgebrochen(monkeypatch):
    from cra import sbom_quellen

    class _Antwort:
        status_code = 200

        def iter_content(self, chunk_size=0):
            for _ in range(5):
                yield b'x' * 4096

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import requests
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: _Antwort())
    monkeypatch.setattr('shared.github_config.get_github_token', lambda: 'tok')
    monkeypatch.setattr('shared.github_config.github_headers', lambda: {})
    monkeypatch.setattr(sbom_quellen, 'MAX_BYTES', 4096)
    assert sbom_quellen.lade_release_asset('owner', 'repo', 1) is None


# ── Endpunkt: Ablageort übernehmen ──────────────────────────────────────────

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


def test_einlesen_legt_an_und_fuellt_die_liste(client, auth_headers, projekt, tmp_path, monkeypatch):
    from cra import sbom_quellen

    ordner = tmp_path / PROJ
    ordner.mkdir(parents=True)
    (ordner / 'produkt-4.2.0.cdx.json').write_text(CYCLONEDX, encoding='utf-8')
    monkeypatch.setattr(sbom_quellen, 'LOKAL_BASIS', tmp_path)

    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/einlesen', headers=auth_headers)
    assert r.status_code == 200, r.json
    assert r.json['gefunden'] == 1
    assert r.json['angelegt'][0]['release_version'] == '4.2.0'
    assert r.json['angelegt'][0]['komponenten'] == 2

    # Die Zeile trägt die Zahlen aus der Datei — nicht aus einem Formular.
    sboms = client.get(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers).json
    zeile = next(s for s in sboms if s['release_version'] == '4.2.0')
    assert zeile['sbom_format'] == 'cyclonedx'
    assert zeile['komponenten_count'] == 2
    assert zeile['lizenzen'] == ['Apache-2.0', 'BSD-3-Clause']
    assert zeile['liste_anzahl'] == 2          # #1761: Liste ist wirklich da


def test_einlesen_ueberschreibt_handarbeit_nicht(client, auth_headers, projekt, tmp_path, monkeypatch):
    """Eine von Hand gepflegte Zeile ist eine Aussage. Ein Verzeichnis-Scan
    darf sie nicht stillschweigend ersetzen."""
    from cra import sbom_quellen

    client.post(f'{CRA}/projekte/{PROJ}/sbom', headers=auth_headers,
                json={'release_version': '4.2.0', 'sbom_format': 'cyclonedx',
                      'komponenten_count': 99, 'notizen': 'von Hand'})
    ordner = tmp_path / PROJ
    ordner.mkdir(parents=True)
    (ordner / 'produkt-4.2.0.cdx.json').write_text(CYCLONEDX, encoding='utf-8')
    monkeypatch.setattr(sbom_quellen, 'LOKAL_BASIS', tmp_path)

    r = client.post(f'{CRA}/projekte/{PROJ}/sbom/einlesen', headers=auth_headers)
    assert r.status_code == 200
    assert r.json['angelegt'] == []
    assert r.json['uebersprungen'] == ['4.2.0']
    zeile = next(s for s in client.get(f'{CRA}/projekte/{PROJ}/sbom',
                                       headers=auth_headers).json
                 if s['release_version'] == '4.2.0')
    assert zeile['komponenten_count'] == 99    # unangetastet
