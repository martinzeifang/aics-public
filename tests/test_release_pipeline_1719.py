"""Release-Pipeline: Image-Namen und Publisher-Umstellung (#1719).

Hintergrund: Die Docker-Images sollen künftig aus dem **öffentlichen** Repo
(`aics-public`) veröffentlicht werden, nicht aus dem privaten. Grund ist nicht
Bequemlichkeit, sondern Überprüfbarkeit — cosign-Identität und SLSA-Provenance
zeigen dann auf einen Quellbaum, den der Kunde lesen kann.

Dabei gibt es eine Falle, die beim Umzug alles bricht: Der Image-Name wurde aus
dem Repo-Namen abgeleitet (``${{ github.repository }}``). Im öffentlichen Repo
ergibt das ``martinzeifang/aics-public`` — jeder Portainer-Stack und jede
Kunden-Compose zeigt dann auf einen Namen, den niemand mehr pusht. Der Name muss
an das **Produkt** gebunden sein, nicht an das Repository.

Diese Tests halten das fest. Sie prüfen Workflow-Dateien als Text; dafür braucht
es weder Netz noch Datenbank.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PRIVAT = REPO / '.github/workflows/docker-publish.yml'
VORLAGE = REPO / '.public-templates/.github-workflows-public/docker-publish.yml'

#: Der Produktname, unter dem die Images veröffentlicht werden.
WEB_IMAGE = 'ai_compliance_suite'
NGINX_IMAGE = 'aics-nginx'


def _matrix_images(pfad: Path) -> dict[str, str]:
    """``name:`` → ``image:`` aus der Build-Matrix."""
    text = pfad.read_text()
    out: dict[str, str] = {}
    aktuell: str | None = None
    for zeile in text.splitlines():
        m = re.match(r'\s*-\s*name:\s*(\S+)', zeile)
        if m:
            aktuell = m.group(1)
            continue
        m = re.match(r'\s*image:\s*(.+?)\s*$', zeile)
        if m and aktuell:
            out[aktuell] = m.group(1)
            aktuell = None
    return out


@pytest.mark.parametrize('pfad', [PRIVAT, VORLAGE], ids=['privat', 'public-vorlage'])
def test_image_name_nicht_vom_repo_abgeleitet(pfad: Path):
    """``github.repository`` als Image-Name ist der Umzugs-Stolperstein."""
    images = _matrix_images(pfad)
    assert images, f'keine Build-Matrix in {pfad.name} gefunden'
    kaputt = {n: i for n, i in images.items() if 'github.repository }}' in i
              or i.strip() == '${{ github.repository }}'}
    assert not kaputt, (
        f'{pfad.relative_to(REPO)} leitet den Image-Namen aus dem Repo ab: {kaputt}. '
        'Im öffentlichen Repo würde daraus `aics-public` und jede Compose zeigt ins '
        f'Leere. Fest auf `{WEB_IMAGE}` setzen.')


@pytest.mark.parametrize('pfad', [PRIVAT, VORLAGE], ids=['privat', 'public-vorlage'])
def test_beide_workflows_nutzen_dieselben_image_namen(pfad: Path):
    """Privat und öffentlich müssen auf dasselbe Paket zeigen."""
    images = _matrix_images(pfad)
    assert images.get('aics-web', '').endswith(WEB_IMAGE), \
        f'{pfad.name}: aics-web zeigt auf {images.get("aics-web")!r}, erwartet …/{WEB_IMAGE}'
    assert images.get('aics-nginx', '').endswith(NGINX_IMAGE), \
        f'{pfad.name}: aics-nginx zeigt auf {images.get("aics-nginx")!r}'


def test_public_vorlage_veroeffentlicht_nur_mit_schalter():
    """Ohne gesetzten Schalter bleibt die Vorlage ein Sanity-Build.

    GHCR-Pakete hängen am Repo, das sie zuerst veröffentlicht hat. Bis
    `aics-public` dort Schreibrechte bekommt (einmalig über die GitHub-
    Oberfläche), würde ein bedingungsloses ``push: true`` bei jedem Release
    fehlschlagen.
    """
    text = VORLAGE.read_text()
    assert "push: ${{ vars.PUBLISH_IMAGES == 'true' }}" in text, \
        'Die Vorlage muss den Push an die Variable PUBLISH_IMAGES binden.'
    # Die Signatur-/SBOM-Schritte dürfen nur beim Veröffentlichen laufen —
    # ohne gepushten Digest haben sie nichts zu signieren.
    for schritt in ('Sign image (keyless)', 'Attest SBOM (keyless)', 'Generate SBOM'):
        block = text.split(f'name: {schritt}', 1)
        assert len(block) == 2, f'Schritt "{schritt}" fehlt in der Vorlage'
        assert "vars.PUBLISH_IMAGES == 'true'" in block[0].rsplit('- ', 1)[-1] \
            or "vars.PUBLISH_IMAGES == 'true'" in block[1][:200], \
            f'Schritt "{schritt}" ist nicht an PUBLISH_IMAGES gebunden'


def test_public_vorlage_signiert_und_haengt_sbom_an():
    """Die Überprüfbarkeit ist der Zweck der Umstellung — sie muss drin sein."""
    text = VORLAGE.read_text()
    assert 'cosign sign --yes' in text, 'keine Signatur in der öffentlichen Vorlage'
    assert 'cosign attest --yes' in text, 'keine SBOM-Attestation'
    assert 'provenance: mode=max' in text, 'keine SLSA-Provenance'
    assert 'id-token: write' in text, 'cosign keyless braucht id-token: write'
    assert 'packages: write' in text, 'GHCR-Push braucht packages: write'


def test_semver_tag_bleibt_erhalten():
    """Der Semver-Image-Tag ist der Rückrollweg (AICS_IMAGE_TAG=7.4.1).

    Ohne ihn gibt es nur `latest` und SHA — und damit kein geordnetes Zurück,
    das beim v7.4.0-Ausfall den Dienst gerettet hat.
    """
    for pfad in (PRIVAT, VORLAGE):
        text = pfad.read_text()
        assert 'type=semver,pattern={{version}}' in text, \
            f'{pfad.name}: Semver-Tag fehlt'


def test_sync_spiegelt_tag_ins_public_repo():
    """Der öffentliche Build braucht den Tag, um den Semver-Tag zu erzeugen."""
    sync = (REPO / '.github/workflows/sync-to-public.yml').read_text()
    assert 'git tag "${{ steps.tag.outputs.tag }}"' in sync
    assert 'git push --force origin "${{ steps.tag.outputs.tag }}"' in sync


def test_kundenanleitung_zur_echtheitspruefung_vorhanden():
    """Eine Signatur, die niemand prüft, wirkt nicht (#1719/E5)."""
    readme = (REPO / '.public-templates/README.public.md').read_text()
    assert 'cosign verify' in readme, 'keine Anleitung zur Signaturprüfung im Public-README'
    assert 'cosign download attestation' in readme, 'kein Hinweis zum SBOM-Abruf'
    assert '--certificate-oidc-issuer' in readme, \
        'Keyless-Prüfung braucht den OIDC-Issuer in der Anleitung'
