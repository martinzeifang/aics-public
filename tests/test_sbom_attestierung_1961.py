"""Signiert ohne Stückliste darf kein stiller Zustand sein (#1961).

Beim Release **v8.6.1** war `aics-nginx:8.6.1` gepusht und keyless signiert,
trug aber **keine** SPDX-Attestierung: Der Build scheiterte nach `push` und
`sign` an `Generate SBOM`, beim Neustart schon an `Install cosign` (``curl``
Exit 22 beim Laden der Binärdatei aus den GitHub-Releases).

Warum das mehr ist als ein roter Lauf:

* Anhang VII Nr. 1 der Verordnung (EU) 2024/2847 verlangt die Stückliste als
  Pflichtinhalt; für dieses Produkt liegt sie **als Attestierung am Digest**
  und nicht als Release-Asset (so mit #1770 entschieden).
* `cra/sbom_registry.py` holt sie genau dort — die eigene Anwendung fand für
  das nginx-Abbild also nichts, und `hole_sbom()` kann „nicht vorhanden" nicht
  von „kein Zugriff" unterscheiden (#1823).
* Ein Kunde mit `cosign verify-attestation` bekommt eine **Signatur** und
  keine Stückliste. Das ist die unangenehmste Kombination: Es sieht geprüft
  aus, und der Nachweis fehlt.

Dieser Wächter hält die drei Maßnahmen fest. Er prüft **Vorlagen**, nicht den
öffentlichen Baum: Gespiegelt wird bei `release: published`, und was dort
ankommt, entsteht hier.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

WURZEL = Path(__file__).resolve().parents[1]
VORLAGEN = WURZEL / ".public-templates" / ".github-workflows-public"
BUILD = VORLAGEN / "docker-publish.yml"
NACHZIEHEN = VORLAGEN / "sbom-nachziehen.yml"


def _schritte(datei: Path, job: str) -> list[dict]:
    daten = yaml.safe_load(datei.read_text(encoding="utf-8"))
    return daten["jobs"][job]["steps"]


def _namen(schritte: list[dict]) -> list[str]:
    return [s.get("name", s.get("uses", "")) for s in schritte]


# ── Der Build macht den Zustand benennbar ───────────────────────────────────

def test_der_build_ruft_die_attestierung_wieder_ab():
    """Dass ein Schritt grün war, sagt nichts darüber, ob am Digest etwas liegt.

    Das ist die Lehre aus #1961 in einem Satz — und dieselbe wie bei der
    Sicherung (#1785): geprüft wird der Rundlauf, nicht die Behauptung.
    """
    schritte = _schritte(BUILD, "build")
    namen = _namen(schritte)
    assert "Attestierung nachweisen" in namen, (
        "Der Build ruft die SPDX-Attestierung nicht wieder ab. Ohne diesen "
        "Schritt endet ein Lauf rot, ohne zu sagen, ob gepusht, signiert oder "
        "attestiert wurde — genau der Zustand, in dem v8.6.1 ausgeliefert "
        "wurde.")
    schritt = schritte[namen.index("Attestierung nachweisen")]
    programm = schritt.get("run", "")
    assert "verify-attestation" in programm and "--type spdxjson" in programm, (
        "Der Schritt prüft nicht mit `cosign verify-attestation --type "
        "spdxjson` — eine andere Prüfung belegt die Stückliste nicht.")
    assert "exit 1" in programm, (
        "Ein Hinweis ohne Abbruch ist eine Meldung, die niemand liest "
        "(#1805/#1830). Der Lauf muss rot werden.")


def test_der_build_nennt_den_weg_heraus():
    """Eine Fehlermeldung ohne Ausweg ist eine Sackgasse (#1783/#1805).

    Und sie muss ausdrücklich vom Neubau abraten: Ein Neubau erzeugt einen
    anderen Digest und tauscht damit den Gegenstand aus, den die Erklärung
    bezeichnet.
    """
    schritte = _schritte(BUILD, "build")
    programm = schritte[_namen(schritte).index("Attestierung nachweisen")]["run"]
    assert "SBOM nachziehen" in programm, "der Weg heraus wird nicht genannt"
    assert re.search(r"NICHT neu bauen", programm), (
        "Der Hinweis muss vom Neubau abraten — er aendert den Digest.")


@pytest.mark.parametrize("erster,zweiter", [
    ("Install cosign", "Install cosign (zweiter Anlauf)"),
    ("Generate SBOM", "Generate SBOM (zweiter Anlauf)"),
])
def test_die_beiden_fragilen_schritte_haben_zwei_anlaeufe(erster, zweiter):
    """Beide Fehlschläge von v8.6.1 waren Downloads aus fremden Verzeichnissen.

    Ein Ausfall davon ist hinzunehmen; dass er den Integritätsnachweis eines
    Releases kostet, nicht.
    """
    schritte = _schritte(BUILD, "build")
    namen = _namen(schritte)
    assert erster in namen and zweiter in namen, f"{zweiter} fehlt"
    assert schritte[namen.index(erster)].get("continue-on-error") is True, (
        f"„{erster}“ ist nicht auf `continue-on-error` gesetzt — der zweite "
        "Anlauf wird dann nie erreicht.")


# ── Nachziehen, ohne den Gegenstand auszutauschen ───────────────────────────

def test_das_nachziehen_baut_nichts():
    """**Die tragende Eigenschaft dieses Workflows.**

    Ein Neubau erzeugt einen anderen Digest (schon
    ``org.opencontainers.image.created`` unterscheidet sich). Der Tag zeigte
    danach auf ein anderes Artefakt als das, was auf den Instanzen läuft — und
    als das, was in ``cra_sbom.image_digest`` steht und die
    EU-Konformitätserklärung unter Anhang V Nr. 4 als Gegenstand bezeichnet
    (#1884). Eine Stückliste nachzutragen darf den Gegenstand nicht
    austauschen, den sie beschreibt.
    """
    roh = NACHZIEHEN.read_text(encoding="utf-8")
    ohne_kommentar = re.sub(r"(?m)^\s*#.*$", "", roh)
    for verboten in ("build-push-action", "docker build", "buildx build",
                     "setup-buildx-action"):
        assert verboten not in ohne_kommentar, (
            f"`{verboten}` im Nachzieh-Workflow — er darf nicht bauen, sonst "
            "wechselt der Digest und die Erklärung bezeichnet ein anderes "
            "Artefakt.")


def test_das_nachziehen_laeuft_nur_auf_zuruf():
    """Kein Zeitplan, kein Push-Auslöser: Es ist eine Reparatur, kein Lauf."""
    daten = yaml.safe_load(NACHZIEHEN.read_text(encoding="utf-8"))
    # PyYAML liest das unquotierte `on:` als Boolean True.
    ausloeser = daten.get("on", daten.get(True))
    assert set(ausloeser) == {"workflow_dispatch"}, (
        f"Auslöser sind {sorted(ausloeser)} — erwartet nur workflow_dispatch.")
    for pflicht in ("image", "tag"):
        assert pflicht in ausloeser["workflow_dispatch"]["inputs"], (
            f"Eingabe `{pflicht}` fehlt")


def test_das_nachziehen_weigert_sich_bei_vorhandener_attestierung():
    """Zwei Stücklisten zu einem Artefakt sind zwei Wahrheiten.

    Und die jüngere ist nicht automatisch die richtige — deshalb fail-closed
    statt „überschreibt halt".
    """
    schritte = _schritte(NACHZIEHEN, "nachziehen")
    namen = _namen(schritte)
    treffer = [n for n in namen if "schon eine Attestierung" in n]
    assert treffer, "der Workflow prüft nicht, ob schon eine vorliegt"
    programm = schritte[namen.index(treffer[0])]["run"]
    assert "verify-attestation" in programm and "exit 1" in programm


def test_das_nachziehen_weist_das_ergebnis_nach():
    schritte = _schritte(NACHZIEHEN, "nachziehen")
    namen = _namen(schritte)
    assert "Attestierung nachweisen" in namen, (
        "Ohne Abruf am Ende ist auch das Nachziehen nur eine Behauptung.")


def test_beide_workflows_teilen_die_sperre():
    """Build und Nachziehen schreiben an denselben Digest.

    Zwei gleichzeitige Läufe hinterlassen zwei Aussagen zu einem Artefakt,
    deshalb dieselbe `concurrency`-Gruppe.
    """
    gruppen = {
        f.name: yaml.safe_load(f.read_text(encoding="utf-8"))["concurrency"]["group"]
        for f in (BUILD, NACHZIEHEN)
    }
    assert len(set(gruppen.values())) == 1, gruppen
