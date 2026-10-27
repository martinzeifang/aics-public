"""Die SBOM lässt sich herunterladen, egal wo sie liegt (#1823).

**Der Befund aus dem Betrieb:** „Das Herunterladen der SBOM funktioniert nicht,
wenn ich den Pfad so angebe wie auf aics-test für 8.0.11."

Dort steht im Feld „Pfad zur SBOM-Datei" eine **Image-Referenz**
(``ghcr.io/…/ai_compliance_suite:8.0.11``) — so ist es seit #1770 vorgesehen,
und der Abruf funktioniert auch: Die Attestation kommt in Sekunden. Nur
*herunterladen* ließ sie sich nicht. Die Zeile verlinkt ausschließlich
``http(s)``-Pfade (#1422, richtig — eine OCI-Referenz ist kein Hyperlink), und
der Knopf „SBOM vom Image holen" füllte die Komponentenliste, gab die Datei
aber nicht heraus. Damit fehlte genau das Dokument, das nach Anhang VII in die
Akte gehört.

Die Trennlinie, die hier **nicht** verschoben wird: Eine eingetippte
http(s)-Adresse ruft der Server weiterhin nicht ab. Das ist der Weg, den #1761
ausgeschlossen hat.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

CRA = '/api/cra'
FIRMA = 'pytest-firma-1823'
PROJ = 'pytest-cra-1823'


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


def _sbom(client, auth_headers, projekt, blob_path: str) -> int:
    r = client.post(f'{CRA}/projekte/{projekt}/sbom', headers=auth_headers,
                    json={'release_version': '8.0.11', 'sbom_format': 'spdx',
                          'blob_path': blob_path})
    assert r.status_code in (200, 201), r.json
    return int(r.json['id'])


# ── Externe Adresse: weiterhin kein serverseitiger Abruf ────────────────────

def test_http_adresse_wird_nicht_vom_server_geholt(client, auth_headers, projekt):
    """Die URL ist eine freie Eingabe. Sie hier zu holen wäre SSRF (#1761).

    Statt eines stillen Fehlschlags sagt die Antwort, was Sache ist, und nennt
    die Adresse — das Frontend öffnet sie dann direkt.
    """
    sid = _sbom(client, auth_headers, projekt, 'https://example.com/sbom.json')
    r = client.get(f'{CRA}/projekte/{projekt}/sbom/{sid}/download',
                   headers=auth_headers)
    assert r.status_code == 409, r.json
    assert r.json['error'] == 'url-extern'
    assert r.json['url'] == 'https://example.com/sbom.json'


def test_kein_serverseitiger_abruf_eingetippter_adressen():
    """Wächter: Der Download-Endpunkt darf ``blob_path`` niemals als URL holen."""
    quelle = Path('server/api/cra/__init__.py').read_text(encoding='utf-8')
    stelle = quelle[quelle.index("def sbom_download"):]
    stelle = stelle[:stelle.index("@cra_bp.post")]
    assert 'url-extern' in stelle
    assert 'requests.get' not in stelle, \
        'Eine eingetippte Adresse wird nicht serverseitig abgerufen (#1761)'


# ── Ablageort ───────────────────────────────────────────────────────────────

def test_datei_aus_dem_ablageort(client, auth_headers, projekt, tmp_path,
                                 monkeypatch):
    from cra import sbom_quellen

    basis = tmp_path / 'sbom'
    (basis / projekt).mkdir(parents=True)
    datei = basis / projekt / 'aics-8.0.11.spdx.json'
    inhalt = {'spdxVersion': 'SPDX-2.3', 'packages': []}
    datei.write_text(json.dumps(inhalt), encoding='utf-8')
    monkeypatch.setattr(sbom_quellen, 'LOKAL_BASIS', basis)

    sid = _sbom(client, auth_headers, projekt, str(datei))
    r = client.get(f'{CRA}/projekte/{projekt}/sbom/{sid}/download',
                   headers=auth_headers)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert json.loads(r.get_data())['spdxVersion'] == 'SPDX-2.3'
    assert 'attachment' in r.headers.get('Content-Disposition', '')


def test_datei_ausserhalb_des_ablageorts_wird_abgelehnt(client, auth_headers,
                                                        projekt, tmp_path,
                                                        monkeypatch):
    """``blob_path`` steht in der Datenbank, kann aber von Hand gesetzt worden
    sein. Der Pfadvergleich gegen die Basis ist der doppelte Boden — dieselbe
    Vorsicht wie bei ``_backup_pfad`` in #1784."""
    from cra import sbom_quellen

    fremd = tmp_path / 'geheim.json'
    fremd.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sbom_quellen, 'LOKAL_BASIS', tmp_path / 'sbom')

    sid = _sbom(client, auth_headers, projekt, str(fremd))
    r = client.get(f'{CRA}/projekte/{projekt}/sbom/{sid}/download',
                   headers=auth_headers)
    assert r.status_code == 404, r.json


# ── Image-Referenz ──────────────────────────────────────────────────────────

def test_image_referenz_liefert_das_dokument(client, auth_headers, projekt,
                                             monkeypatch):
    """Der gemeldete Fall. Geholt wird über ``hole_sbom`` — hier ersetzt,
    damit der Test ohne Netz läuft."""
    from cra import sbom_registry

    monkeypatch.setattr(sbom_registry, 'hole_sbom', lambda ref: {
        'inhalt': json.dumps({'spdxVersion': 'SPDX-2.3', 'name': ref}),
        'digest': 'sha256:' + '0' * 64,
        'referenz': ref,
    })
    sid = _sbom(client, auth_headers, projekt,
                'ghcr.io/martinzeifang/ai_compliance_suite:8.0.11')
    r = client.get(f'{CRA}/projekte/{projekt}/sbom/{sid}/download',
                   headers=auth_headers)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert json.loads(r.get_data())['spdxVersion'] == 'SPDX-2.3'
    assert '8.0.11' in r.headers.get('Content-Disposition', '')


def test_registryfehler_kommt_im_klartext_zurueck(client, auth_headers, projekt,
                                                  monkeypatch):
    from cra import sbom_registry

    def werfen(_ref):
        raise sbom_registry.RegistryFehler('Zugriff verweigert (HTTP 401)')

    monkeypatch.setattr(sbom_registry, 'hole_sbom', werfen)
    sid = _sbom(client, auth_headers, projekt, 'ghcr.io/owner/name:1.0')
    r = client.get(f'{CRA}/projekte/{projekt}/sbom/{sid}/download',
                   headers=auth_headers)
    assert r.status_code == 400
    assert '401' in r.json['error']


# ── Die Meldung bei 401 ─────────────────────────────────────────────────────

def test_401_behauptet_weder_das_eine_noch_das_andere():
    """Bei 401/403 steht nicht fest, woran es liegt — und die Meldung sagt das.

    Eine Registry verrät nicht, ob ein nicht zugängliches Paket existiert;
    sonst ließen sich private Paketnamen abfragen. „Nicht gefunden" war
    deshalb eine Behauptung, die die Suche in die falsche Richtung schickt —
    und „nicht öffentlich" wäre dieselbe Behauptung mit umgekehrtem Vorzeichen.
    Der echte Fall war ein **Paketname, den es nicht gibt**.
    """
    quelle = Path('cra/sbom_registry.py').read_text(encoding='utf-8')
    stelle = quelle[quelle.index('def hole_sbom'):]
    assert 'status_code in (401, 403)' in stelle
    assert 'nicht heraus' in stelle and 'oder es ist nicht öffentlich' in stelle
