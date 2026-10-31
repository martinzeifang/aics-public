"""Release-Kanäle: stable · beta · dev (#1908).

DER WUNSCH, UND WARUM DER NAHELIEGENDE SCHALTER FALSCH WÄRE
-----------------------------------------------------------
Aus dem Betrieb: „Ich will in den Einstellungen sagen, ob ich meine Releases
von Public bekomme … oder von privat, dann will ich auch unreleased Versionen.
Hintergrund: Vor der CRA-Veröffentlichung muss ein Beta-Test möglich sein."

Der Wunsch ist richtig, der Hebel „public gegen privat" nicht. Er koppelt zwei
Fragen, die heute nur **zufällig** zusammenfallen:

* Wie **reif** ist der Stand? (Release ↔ Vorabfassung) — das ist der Beta-Test.
* Aus welchem **Quellbaum** ist das Image gebaut? — das ist die Nachweisfrage
  aus #1738 (cosign-Identität + SLSA-Provenance zeigen auf einen Baum, den der
  Kunde lesen kann).

Sie fallen zusammen, weil bisher nur ``aics-public`` Release-Tags baut. Wer sie
in **einen** Schalter legt, verbindet „ich will beta testen" mit „ich gebe die
Herkunftsprüfung auf" — und zwar für den **Kunden**, nicht nur für uns.

Dazu ist ein unveröffentlichtes Image für einen Beta-Test das falsche
Artefakt: ``sha-89bff28`` hat keinen nennbaren Namen, keine Release-Notes, und
``APP_VERSION`` trägt dort die Zahl aus ``frontend/package.json`` — die
Installation gibt also einen Stand an, den sie nicht trägt. Bei v8.2.1 war das
live so (Prod und Demo fuhren ein Dev-Image, die Oberfläche zeigte eine
Release-Nummer). In einem Werkzeug, dessen Konformitätsnachweis eine Version
bezeichnet, ist das kein Schönheitsfehler.

Deshalb: **Der Kanal beschreibt die Reife, die Herkunft bleibt geprüft.**
``beta`` ist eine *veröffentlichte* Vorabfassung aus ``aics-public`` — gleicher
Workflow, gleiche Signatur, gleiche Provenance, nur als GitHub-Prerelease und
**nicht** auf ``latest``/``<major.minor>`` gelegt. ``dev`` ist der Nothilfe-Weg
aus #1738 und bleibt es: nicht wählbar in der Oberfläche, nur über eine
Umgebungsvariable.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

#: Label, das die Herkunft am Artefakt belegt (identisch zu
#: ``scripts/ops/portainer_redeploy``; die Konstante lebt hier, damit Skript und
#: Webdienst **eine** Quelle haben — #1731/#1735).
QUELL_LABEL = "org.opencontainers.image.source"

#: Der öffentliche Quellbaum. Release **und** Beta kommen von hier.
OEFFENTLICHE_QUELLE = "https://github.com/martinzeifang/aics-public"

#: Umgebungsvariable, die den internen Kanal überhaupt erst anbietet. Bewusst
#: keine Einstellung in der Oberfläche: Ein Klick, der die Herkunftsprüfung
#: abschaltet, wäre ein Angebot — der Nothilfe-Weg soll einer bleiben.
DEV_FREIGABE_ENV = "AICS_UPDATE_CHANNEL_DEV"


@dataclass(frozen=True)
class Kanal:
    """Ein Release-Kanal."""

    name: str
    titel: str
    beschreibung: str
    #: Erwartete Herkunft der Images — ``None`` heißt „nicht geprüft".
    quelle: str | None
    #: Darf die Oberfläche ihn anbieten?
    waehlbar: bool
    #: Nimmt er Vorabfassungen (``8.3.0-beta.1``) als Kandidaten?
    vorabfassungen: bool


KANAELE: dict[str, Kanal] = {
    "stable": Kanal(
        name="stable",
        titel="Freigegeben",
        beschreibung="Nur veröffentlichte Releases. Vorgabe.",
        quelle=OEFFENTLICHE_QUELLE,
        waehlbar=True,
        vorabfassungen=False,
    ),
    "beta": Kanal(
        name="beta",
        titel="Vorabfassung (Beta)",
        beschreibung=(
            "Veröffentlichte Vorabfassungen für einen Test vor der Freigabe. "
            "Gebaut und signiert wie ein Release — nur als Prerelease "
            "gekennzeichnet."),
        quelle=OEFFENTLICHE_QUELLE,
        waehlbar=True,
        vorabfassungen=True,
    ),
    "dev": Kanal(
        name="dev",
        titel="Entwicklung (intern)",
        beschreibung=(
            "Unveröffentlichte Stände (main, sha-…). Ohne Herkunftsprüfung, "
            "ohne Release-Notes, und die angezeigte Version entspricht nicht "
            "dem Stand. Nur zur Nothilfe."),
        quelle=None,
        waehlbar=False,
        vorabfassungen=True,
    ),
}

VORGABE = "stable"


def dev_freigegeben() -> bool:
    """Ist der interne Kanal in dieser Installation überhaupt angeboten?"""
    return (os.environ.get(DEV_FREIGABE_ENV) or "").strip().lower() in (
        "1", "true", "yes", "ja")


def kanal(name: str | None) -> Kanal:
    """Kanal nach Namen — unbekannt oder gesperrt fällt auf ``stable`` zurück.

    **Fail-closed in die sichere Richtung:** Ein Tippfehler in der
    Konfiguration darf nicht dazu führen, dass eine Installation unversehens
    ohne Herkunftsprüfung aktualisiert. Der strengste Kanal ist die Vorgabe.
    """
    k = KANAELE.get((name or "").strip().lower())
    if k is None:
        return KANAELE[VORGABE]
    if k.name == "dev" and not dev_freigegeben():
        return KANAELE[VORGABE]
    return k


def waehlbare_kanaele() -> list[Kanal]:
    """Was die Oberfläche anbieten darf (``dev`` nur mit Freigabe)."""
    return [k for k in KANAELE.values()
            if k.waehlbar or (k.name == "dev" and dev_freigegeben())]


# ── Versionen vergleichen ───────────────────────────────────────────────

#: ``8.3.0``, ``v8.3.0``, ``8.3.0-beta.1``, ``8.3`` …
_SEMVER = re.compile(
    r"^[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.\-]+))?(?:\+[0-9A-Za-z.\-]+)?$")


def parse_version(v: str) -> tuple[tuple[int, int, int], tuple] | None:
    """Zerlegt eine Version in ``((major, minor, patch), prerelease)``.

    Die Vorabfassung wird **mitgenommen**, weil sie die Ordnung bestimmt:
    ``8.3.0-beta.1`` ist nach Semver **kleiner** als ``8.3.0``. Der frühere
    ``_parse_semver`` in ``server/api/admin.py`` schnitt alles nach dem ``-``
    weg — damit galt eine Beta als **gleich** ihrem Release und „Update
    verfügbar" blieb aus, obwohl die Freigabe längst da war.
    """
    t = _SEMVER.match(str(v or "").strip())
    if not t:
        return None
    kern = (int(t.group(1)), int(t.group(2) or 0), int(t.group(3) or 0))
    roh = t.group(4)
    if not roh:
        # Kein Prerelease → die höhere Fassung. Leeres Tupel sortiert vor
        # jedem nicht-leeren, deshalb ein Marker, der größer ist.
        return kern, (1,)
    teile: list = [0]  # Marker: kleiner als eine Fassung ohne Prerelease
    for stueck in roh.split("."):
        # Zahlen numerisch, alles andere als Text — so wie Semver es verlangt.
        teile.append((0, int(stueck)) if stueck.isdigit() else (1, stueck))
    return kern, tuple(teile)


def ist_vorabfassung(v: str) -> bool:
    zerlegt = parse_version(v)
    return bool(zerlegt and zerlegt[1] and zerlegt[1][0] == 0)


def _vergleichbar(zerlegt: tuple) -> tuple:
    """Flache, vergleichbare Form — Zahlen und Texte nie gegeneinander."""
    kern, vorab = zerlegt
    return kern, tuple(
        t if isinstance(t, tuple) else (0, t) for t in vorab)


def ist_neuer(kandidat: str, laufend: str) -> bool | None:
    """Ist ``kandidat`` neuer als ``laufend``? ``None`` = nicht vergleichbar."""
    a, b = parse_version(kandidat), parse_version(laufend)
    if a is None or b is None:
        return None
    try:
        return _vergleichbar(a) > _vergleichbar(b)
    except TypeError:
        return None


def passt_in_kanal(version: str, k: Kanal) -> bool:
    """Gehört diese Version in den Kanal?

    ``stable`` nimmt **keine** Vorabfassung — sonst würde ein Prerelease, das
    höher zählt als das letzte Release, einer freigegebenen Installation als
    Update angeboten. ``beta`` nimmt beides: Wer Beta testet, soll nicht auf
    einer alten Vorabfassung sitzen bleiben, wenn die Freigabe erscheint.
    """
    if parse_version(version) is None:
        return False
    if ist_vorabfassung(version):
        return k.vorabfassungen
    return True
