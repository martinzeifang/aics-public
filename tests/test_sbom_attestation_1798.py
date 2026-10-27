"""SBOM am Image finden — und mehrere je Release behalten (#1798).

Zwei Fehler an derselben Kette. Der erste war eine Lücke: Der Autodetect
suchte Release-Assets, CI-Artefakte und Workflows — für ein Container-Produkt
liegt die SBOM an keiner dieser Stellen, sondern als signierte Attestation am
Image. Der zweite war eine Regression gegen #1771: ``apply_findings``
deduplizierte auf ``(version, format)`` und verwarf damit jedes weitere
Artefakt derselben Version. Beide zusammen ergaben „keine SBOM gefunden" bei
einem Produkt mit zwei SBOMs.

Ohne Netz geprüft: Die Registry wird über ``hole_sbom`` angesprochen, und das
ist hier gepatcht. Was diese Tests festhalten, ist die Logik davor und danach
— welche Images befragt werden und was von den Funden in der Akte landet.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cra import db as cdb
from cra import sbom_quellen as sq

CRA_DB = Path("data/db/cra.sqlite")
PROJ = "pytest-sbom-attestation-1798"

# Der Ausschnitt, auf den es ankommt: zwei eigene Images mit
# Compose-Variablen, drei fremde, eines ohne Vorgabewert.
COMPOSE = """
services:
  web:
    image: ${AICS_IMAGE:-ghcr.io/martinzeifang/ai_compliance_suite}:${AICS_IMAGE_TAG:-latest}
  nginx:
    image: ${AICS_NGINX_IMAGE:-ghcr.io/martinzeifang/aics-nginx}:${AICS_IMAGE_TAG:-latest}
  postgres:
    image: postgres:16-alpine
  gotenberg:
    image: gotenberg/gotenberg:8
  ollama:
    image: ${AICS_OLLAMA_IMAGE:-ollama/ollama:0.40.7}
  eigen_ohne_default:
    image: ${NUR_VARIABLE}
"""

SPDX = """{"spdxVersion":"SPDX-2.3","name":"x","packages":[
  {"name":"requests","versionInfo":"2.32.0","licenseConcluded":"Apache-2.0",
   "externalRefs":[{"referenceCategory":"PACKAGE-MANAGER","referenceLocator":"pkg:pypi/requests@2.32.0"}]}]}"""


@pytest.fixture
def projekt():
    cdb.ensure_db(CRA_DB)
    cdb.delete_projekt(CRA_DB, PROJ)
    cdb.save_projekt(CRA_DB, PROJ, unternehmen="pytest-firma-1798", produkt="Testprodukt")
    yield PROJ
    cdb.delete_projekt(CRA_DB, PROJ)


# ── Welche Images befragt werden ─────────────────────────────────────────────

def test_nur_eigene_images_werden_befragt():
    """Die SBOM eines Produkts hängt an den Images des Hauses. `postgres` als
    eigene SBOM zu führen, wäre eine Falschaussage über den Liefergegenstand."""
    refs = sq.image_referenzen("martinzeifang", COMPOSE)
    assert refs == ["ghcr.io/martinzeifang/ai_compliance_suite",
                    "ghcr.io/martinzeifang/aics-nginx"]


def test_variable_ohne_vorgabewert_erzeugt_keine_referenz():
    """Eine geratene Adresse wäre schlechter als keine."""
    assert sq.image_referenzen("someone", "    image: ${NUR_VARIABLE}\n") == []


def test_owner_vergleich_ignoriert_gross_schreibung():
    refs = sq.image_referenzen("MartinZeifang", "    image: ghcr.io/martinzeifang/app:1.0\n")
    assert refs == ["ghcr.io/martinzeifang/app"]


def test_digest_und_tag_fallen_weg():
    inhalt = "    image: ghcr.io/o/app@sha256:" + "a" * 64 + "\n    image: ghcr.io/o/b:9.9\n"
    assert sq.image_referenzen("o", inhalt) == ["ghcr.io/o/app", "ghcr.io/o/b"]


# ── Was die Attestation-Suche liefert ────────────────────────────────────────

def test_jedes_image_wird_ein_eigenes_artefakt(monkeypatch):
    """Der Kern von #1771: zwei Artefakte derselben Version, unterscheidbar."""
    gerufen: list[str] = []

    def _hole(ref):
        gerufen.append(ref)
        return {"inhalt": SPDX, "referenz": f"{ref}-aufgeloest"}

    monkeypatch.setattr("cra.sbom_registry.hole_sbom", _hole)
    funde = sq.finde_attestationen(
        "martinzeifang", "repo", "v8.0.7",
        lade_datei=lambda o, r, p: COMPOSE if p == "docker-compose.yml" else None,
        datum="2026-10-23")

    assert gerufen == ["ghcr.io/martinzeifang/ai_compliance_suite:8.0.7",
                       "ghcr.io/martinzeifang/aics-nginx:8.0.7"]
    assert [f["artefakt"] for f in funde] == ["ai_compliance_suite", "aics-nginx"]
    assert {f["release_version"] for f in funde} == {"8.0.7"}
    # Gelesen, nicht nur gefunden (#1769)
    assert all(f["komponenten_count"] == 1 and f["sbom_format"] == "spdx" for f in funde)
    assert all(f["quelle"].startswith("auto:attestation:") for f in funde)


def test_image_ohne_attestation_erzeugt_keinen_eintrag(monkeypatch):
    """Die meisten Produkte haben keine. Eine Zeile „SBOM: vorhanden" ohne
    Inhalt wäre genau die Scheinvollständigkeit, die der Prüfpunkt aufdecken
    soll."""
    def _hole(ref):
        raise RuntimeError("keine Attestation")

    monkeypatch.setattr("cra.sbom_registry.hole_sbom", _hole)
    assert sq.finde_attestationen("o", "r", "1.0.0", lade_datei=lambda *a: COMPOSE,
                                  images=["ghcr.io/o/app"]) == []


def test_mehr_als_der_deckel_wird_nicht_befragt(monkeypatch):
    """Ein Compose mit zwanzig Diensten darf den Lauf nicht in eine
    Registry-Tour verwandeln."""
    gerufen: list[str] = []
    monkeypatch.setattr("cra.sbom_registry.hole_sbom",
                        lambda ref: (gerufen.append(ref), {"inhalt": SPDX})[1])
    sq.finde_attestationen("o", "r", "1.0.0", lade_datei=lambda *a: None,
                           images=[f"ghcr.io/o/app{i}" for i in range(10)])
    assert len(gerufen) == sq.MAX_ATTESTATION_IMAGES


def test_ohne_version_wird_nichts_abgerufen(monkeypatch):
    """Ohne Image-Tag gibt es nichts zu holen — und ein Abruf gegen `:` wäre
    ein Griff ins Leere mit einer Fehlermeldung aus der Registry."""
    monkeypatch.setattr("cra.sbom_registry.hole_sbom",
                        lambda ref: pytest.fail(f"nicht erwarteter Abruf: {ref}"))
    assert sq.finde_attestationen("o", "r", "", lade_datei=lambda *a: COMPOSE) == []


# ── Was in der Akte landet ───────────────────────────────────────────────────

def test_beide_artefakte_werden_uebernommen(projekt):
    """Der Regressionstest zu #1771 im Apply-Pfad: Vor #1798 kam nur das erste
    Artefakt in die Akte, das zweite galt als „schon vorhanden"."""
    from cra.pflicht_doku_autodetect import apply_findings

    funde = {"sbom": [
        {"release_version": "8.0.7", "sbom_format": "spdx", "artefakt": "app",
         "komponenten_count": 1, "lizenzen": ["Apache-2.0"]},
        {"release_version": "8.0.7", "sbom_format": "spdx", "artefakt": "nginx",
         "komponenten_count": 1, "lizenzen": ["BSD-2-Clause"]},
    ]}
    counts = apply_findings(CRA_DB, projekt, funde)
    assert counts["sbom"] == 2
    zeilen = [s for s in cdb.list_sbom(CRA_DB, projekt) if s["release_version"] == "8.0.7"]
    assert sorted(z.get("artefakt") or "" for z in zeilen) == ["app", "nginx"]


def test_zweiter_lauf_legt_nichts_doppelt_an(projekt):
    """Idempotenz — der Autodetect läuft wiederholt."""
    from cra.pflicht_doku_autodetect import apply_findings

    funde = {"sbom": [{"release_version": "8.0.7", "sbom_format": "spdx",
                       "artefakt": "app", "komponenten_count": 1}]}
    apply_findings(CRA_DB, projekt, funde)
    assert apply_findings(CRA_DB, projekt, funde)["sbom"] == 0
    zeilen = [s for s in cdb.list_sbom(CRA_DB, projekt) if s["release_version"] == "8.0.7"]
    assert len(zeilen) == 1


# ── Welcher Release ist der neueste? ─────────────────────────────────────────

def test_entwurf_gilt_nicht_als_neuester_release():
    """Die GitHub-API listet **Entwürfe zuerst**. Im Repo dieser Suite steht ein
    Draft von Juni 2026 vorn — der Autodetect trug dadurch `v6.25.0` als
    Release-Version ein, während v8.0.7 aktuell war."""
    from cra.pflicht_doku_autodetect import neuester_release

    releases = [
        {"tag_name": "v6.25.0", "draft": True, "published_at": "2026-06-22T11:46:55Z"},
        {"tag_name": "v8.0.7", "draft": False, "published_at": "2026-10-23T14:55:15Z"},
        {"tag_name": "v8.0.6", "draft": False, "published_at": "2026-10-23T10:35:37Z"},
    ]
    assert neuester_release(releases).get("tag_name") == "v8.0.7"


def test_vorabversion_ist_nachrangig():
    """Veröffentlicht, aber ein Release-Nachweis meint die reguläre Fassung."""
    from cra.pflicht_doku_autodetect import neuester_release

    releases = [
        {"tag_name": "v9.0.0-rc1", "draft": False, "prerelease": True,
         "published_at": "2026-10-24T08:00:00Z"},
        {"tag_name": "v8.0.7", "draft": False, "prerelease": False,
         "published_at": "2026-10-23T14:55:15Z"},
    ]
    assert neuester_release(releases).get("tag_name") == "v8.0.7"


def test_ohne_veroeffentlichten_release_kein_tag():
    """Nur Entwürfe heißt: nichts in Verkehr — und kein geratener Tag."""
    from cra.pflicht_doku_autodetect import neuester_release

    assert neuester_release([{"tag_name": "v1.0.0", "draft": True}]) == {}
    assert neuester_release([]) == {}


# ── Dieselbe SBOM zweimal erfassen (#1800) ───────────────────────────────────

def test_zweites_erfassen_aktualisiert_statt_abzustuerzen(projekt):
    """Vorher: `UniqueViolation` bis zum Anwender durch, HTTP 500 für eine
    gewöhnliche Korrektur an einer erfassten Zeile."""
    erst = cdb.save_sbom(CRA_DB, projekt, {
        "release_version": "9.9.9", "sbom_format": "spdx", "artefakt": "app",
        "komponenten_count": 5, "lizenzen": ["MIT"]})
    zweit = cdb.save_sbom(CRA_DB, projekt, {
        "release_version": "9.9.9", "sbom_format": "spdx", "artefakt": "app",
        "komponenten_count": 42, "lizenzen": ["MIT", "Apache-2.0"],
        "notizen": "korrigiert"})
    assert zweit == erst, "Upsert muss dieselbe Zeile treffen, nicht eine zweite anlegen"
    zeilen = [s for s in cdb.list_sbom(CRA_DB, projekt)
              if s["release_version"] == "9.9.9" and (s.get("artefakt") or "") == "app"]
    assert len(zeilen) == 1
    assert zeilen[0]["komponenten_count"] == 42
    assert zeilen[0]["notizen"] == "korrigiert"


def test_anderes_artefakt_bleibt_eine_eigene_zeile(projekt):
    """Die Gegenprobe zum Upsert: Der Schlüssel ist vierteilig (#1771)."""
    cdb.save_sbom(CRA_DB, projekt, {"release_version": "9.9.9", "sbom_format": "spdx",
                                    "artefakt": "app", "komponenten_count": 5})
    cdb.save_sbom(CRA_DB, projekt, {"release_version": "9.9.9", "sbom_format": "spdx",
                                    "artefakt": "nginx", "komponenten_count": 9})
    zeilen = [s for s in cdb.list_sbom(CRA_DB, projekt) if s["release_version"] == "9.9.9"]
    assert sorted((s.get("artefakt") or "") for s in zeilen) == ["app", "nginx"]
