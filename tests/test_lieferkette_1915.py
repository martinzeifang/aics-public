"""Die Lieferkette bleibt festgenagelt und beobachtet (#1915).

Drei Zusagen aus ``docs/cra/lieferkette.md``, die sich ohne Prüfer still
auflösen — jede einzelne ist eine Zeile, die jemand beim nächsten Umbau
„vereinfacht":

1. **Basis-Abbilder tragen einen Digest.** Ohne ihn können zwei Bauläufe mit
   demselben Quellstand verschiedene Abbilder ergeben, und die
   EU-Konformitätserklärung bezeichnet seit #1884 genau diesen Digest als
   Gegenstand (Anhang V Nr. 4).
2. **Dependabot deckt alle vier Ökosysteme ab.** Ein Digest-Pin ohne
   automatische Anhebung ist eine Einbahnstraße: Er friert ein Basis-Abbild
   ein, und niemand erfährt, wenn es eine Lücke bekommt. Bis #1915 stand dort
   **nur** ``pip``.
3. **Herkunft und Signatur sind zwei Prüfungen.** Die eine liest ein Label,
   die andere bindet das Abbild an die signierende Identität. Sie
   zusammenzuführen wäre genau die Verwechslung, die Art. 13 Abs. 5 teuer
   macht.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

WURZEL = Path(__file__).resolve().parent.parent

#: Jedes Abbild, das in das ausgelieferte Produkt eingeht.
#: Fremd-Dienste des Betriebsverbunds (Datenbank, PDF-Wandler, Zwischen-
#: speicher) stehen hier **nicht**: Sie sind nicht Teil unseres Artefakts und
#: nicht in seiner Stückliste. Sie sind auf Fassungen festgelegt (#1188), und
#: ein Digest-Pin dort wäre eine Betriebsentscheidung mit eigener Abwägung.
BAU_DATEIEN = ("Dockerfile", "docker/nginx.Dockerfile")

FROM_ZEILE = re.compile(r"^FROM\s+(\S+)", re.M)


@pytest.mark.parametrize("datei", BAU_DATEIEN)
def test_jedes_basis_abbild_traegt_einen_digest(datei: str):
    text = (WURZEL / datei).read_text(encoding="utf-8")
    ohne = [ref for ref in FROM_ZEILE.findall(text)
            if "@sha256:" not in ref and not ref.startswith("$")]
    assert not ohne, (
        f"{datei}: FROM ohne Digest: {ohne}. Ein beweglicher Tag macht den "
        "Baulauf nicht wiederholbar — und die EU-Konformitätserklärung nennt "
        "den Digest des Ergebnisses als Gegenstand. Digest ermitteln: "
        "`docker buildx imagetools inspect <ref>` oder die Registry-API.")


@pytest.mark.parametrize("datei", BAU_DATEIEN)
def test_der_tag_bleibt_neben_dem_digest_stehen(datei: str):
    """Ein reiner Digest ist nicht lesbar.

    ``FROM python@sha256:673719…`` sagt niemandem, dass es 3.11-slim ist. Der
    Tag sagt, **was** gemeint ist, der Digest, **welches** Abbild es war.
    """
    text = (WURZEL / datei).read_text(encoding="utf-8")
    for ref in FROM_ZEILE.findall(text):
        if ref.startswith("$"):
            continue
        vor_digest = ref.split("@", 1)[0]
        assert ":" in vor_digest, (
            f"{datei}: {ref} nennt keinen Tag. Form: name:tag@sha256:…")


def _dependabot() -> dict:
    return yaml.safe_load((WURZEL / ".github/dependabot.yml").read_text(encoding="utf-8"))


def test_dependabot_deckt_die_vier_oekosysteme():
    """pip, npm, docker, github-actions.

    ``npm`` fehlte, obwohl das Frontend eigene Abhängigkeiten hat und der
    Typprüfer aus #1858 im Bau hängt. ``docker`` fehlte, womit die Digest-Pins
    aus diesem Vorgang nie angehoben worden wären. ``github-actions`` fehlte,
    obwohl diese Abläufe mit Schreibrechten auf das Paketverzeichnis laufen
    und die Release-Abbilder signieren.
    """
    cfg = _dependabot()
    ist = {str(u.get("package-ecosystem")) for u in cfg.get("updates") or []}
    for erwartet in ("pip", "npm", "docker", "github-actions"):
        assert erwartet in ist, (
            f"Dependabot deckt '{erwartet}' nicht ab (vorhanden: {sorted(ist)})")


def test_dependabot_sieht_beide_bau_verzeichnisse():
    """``docker/nginx.Dockerfile`` liegt nicht im Wurzelverzeichnis.

    Ein ``docker``-Eintrag mit ``directory: "/"`` findet nur das obere
    Dockerfile — der Webserver-Pin wäre stumm geblieben, und das wäre nicht
    aufgefallen, weil der Eintrag ja existiert.
    """
    cfg = _dependabot()
    docker = [u for u in cfg.get("updates") or []
              if str(u.get("package-ecosystem")) == "docker"]
    assert docker, "kein docker-Eintrag"
    verzeichnisse = set()
    for u in docker:
        if u.get("directories"):
            verzeichnisse.update(str(d) for d in u["directories"])
        if u.get("directory"):
            verzeichnisse.add(str(u["directory"]))
    assert {"/", "/docker"} <= verzeichnisse, (
        f"docker-Eintrag deckt nicht beide Bau-Verzeichnisse ab: {sorted(verzeichnisse)}")


def test_herkunft_und_signatur_sind_zwei_pruefungen():
    """Nicht zusammenführen — das ist der Kern von #1915.

    ``pruefe_quelle`` liest ``org.opencontainers.image.source`` aus dem
    Abbild. Dieses Label wird beim Bau gesetzt; wer ein Abbild baut, kann es
    hineinschreiben. ``pruefe_signatur`` prüft, dass eine benannte Identität
    das Abbild signiert hat. Wer die zweite durch die erste ersetzt, hat eine
    Prüfung verloren und es sieht aus wie zwei.
    """
    from shared.deploy import portainer

    assert callable(portainer.pruefe_quelle)
    assert callable(portainer.pruefe_signatur)
    assert portainer.SIGNATUR_ISSUER == "https://token.actions.githubusercontent.com"
    assert "aics-public" in portainer.SIGNATUR_IDENTITAET, (
        "Die Signatur muss gegen den öffentlichen Quellbaum geprüft werden — "
        "er ist der, den ein Kunde selbst nachlesen kann (#1738)")


def test_das_ops_skript_prueft_die_signatur_standardmaessig():
    """Fail-closed dort, wo ein Mensch steht.

    Im Webdienst ist die Prüfung aus, weil im Abbild kein cosign liegt — ein
    Update-Knopf, der immer mit einem Werkzeugfehler endet, ist schlechter als
    eine benannte Lücke (#1830). Auf der Befehlszeile steht jemand, der
    cosign installieren oder bewusst ``--signatur aus`` setzen kann; dort ist
    Fail-Open die falsche Richtung (#1751).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_ops_redeploy", WURZEL / "scripts/ops/portainer_redeploy.py")
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    quelle = Path(WURZEL / "scripts/ops/portainer_redeploy.py").read_text(encoding="utf-8")
    assert 'default="pruefen"' in quelle, (
        "Das Ops-Skript muss die Signatur standardmäßig prüfen")
    assert 'signatur=(a.signatur == "pruefen")' in quelle, (
        "Der Schalter muss an redeploy() weitergereicht werden — sonst ist er "
        "ein Argument ohne Wirkung (#1840)")

    import inspect

    from shared.deploy.portainer import redeploy
    assert inspect.signature(redeploy).parameters["signatur"].default is False, (
        "Im Webdienst bleibt die Prüfung aus — siehe Docstring von redeploy()")
