"""Die Seitenleiste sieht überall gleich aus (#1856).

DER BEFUND
Suche, Sortierung und Filter gab es in CRA und der Risikobewertung (#1764);
AI Act, WiBA, NIS2 und DSGVO hatten **nur** eine Suche — und die erst ab
**acht** Einträgen. Praktisch heißt das: Auf einer Installation mit drei bis
sieben Mandanten gab es dort kein einziges Bedienelement. Im Funktionstest war
genau das zu sehen: die WiBA-Leiste mit drei Projekten, ohne Suchfeld.

Die Schwelle 8 stammt aus #1703/S7; CRA und die Risikobewertung sind mit #1764
auf 5 gegangen. Die übrigen blieben zurück — nicht entschieden, sondern
übersehen. Das ist die Spiegel-Liste aus #1731/#1735 in ihrer stillen Form:
Niemand merkt es, weil nichts fehlschlägt.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
SRC = WURZEL / "frontend" / "src"
LEISTEN = SRC / "components" / "sidebars"
BAUSTEIN = "SidebarWerkzeuge.vue"

#: Die Leisten, die die gemeinsamen Werkzeuge tragen müssen.
MIT_WERKZEUGEN = [
    "CRASidebar.vue",
    "RisikobewertungSidebar.vue",
    "AIActSidebar.vue",
    "WiBASidebar.vue",
    "FirmenSidebarModul.vue",   # NIS2 + DSGVO
    "ProjektSidebar.vue",       # Firmen, Gutachten, SOC, Compliance-Audit
]


def _text(name: str) -> str:
    return (LEISTEN / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", MIT_WERKZEUGEN)
def test_jede_leiste_nutzt_den_gemeinsamen_baustein(name: str):
    assert "SidebarWerkzeuge" in _text(name), (
        f"{name}: stellt Suche/Sortierung wieder selbst zusammen. Der Baustein "
        f"steht in {BAUSTEIN}.")


@pytest.mark.parametrize("name", MIT_WERKZEUGEN)
def test_keine_leiste_bindet_die_teile_selbst_ein(name: str):
    """Sonst gibt es die Zusammenstellung wieder sechsmal.

    `SidebarSearch` und `SidebarSortFilter` bleiben als Teile bestehen — sie
    sind bewusst „dumm" und werden vom Baustein zusammengesetzt. Eine Leiste,
    die sie direkt einbindet, baut die Leiste ein zweites Mal.
    """
    inhalt = _text(name)
    for teil in ("SidebarSearch", "SidebarSortFilter"):
        assert teil not in inhalt, (
            f"{name}: bindet {teil} direkt ein — das gehört in "
            f"{BAUSTEIN}.")


def test_die_schwelle_steht_an_einer_stelle():
    """Fünf in CRA, acht anderswo — genau so entsteht der Unterschied."""
    composable = (SRC / "composables" / "useSidebarFilter.ts").read_text(encoding="utf-8")
    assert "export const SIDEBAR_WERKZEUGE_AB = 2" in composable, (
        "Die Schwelle muss einen Ort haben — und ab zwei Einträgen greifen, "
        "sonst sieht die Leiste je nach Projektzahl in jedem Modul anders aus.")
    hart: list[str] = []
    for name in MIT_WERKZEUGEN + [BAUSTEIN]:
        inhalt = _text(name)
        # Eine eigene Zahl als Schwelle ist der Weg zurück zu 5 ≠ 8.
        for m in re.finditer(r"(?:schwelle|searchThreshold|MIN_WERKZEUGE)\s*[:=]\s*(\d+)",
                             inhalt):
            hart.append(f"{name}: {m.group(0)}")
    assert not hart, (
        "Eigene Schwellenwerte statt `SIDEBAR_WERKZEUGE_AB`:\n  "
        + "\n  ".join(hart))


def test_der_baustein_zeigt_keinen_filter_ohne_auswahl():
    """Ein Auswahlfeld mit einer Option grenzt nichts ein.

    Das ist #1805/#1830 in seiner harmlosen Form: ein Bedienelement, das
    aussieht, als könne es etwas, und nichts kann. Deshalb baut der Baustein
    die Auswahlfelder aus den **vorhandenen** Werten und lässt ein Feld mit
    weniger als zwei davon weg.
    """
    inhalt = _text(BAUSTEIN)
    assert "werte.size < 2" in inhalt, (
        "Der Baustein muss Felder ohne echte Auswahl weglassen.")


def test_die_filter_kommen_aus_vorhandenen_feldern():
    """Erfunden wird nichts.

    Die vier nachgezogenen Leisten filtern nur über Felder, die die
    Projektliste wirklich liefert: `einrichtungsklasse` (NIS2),
    `organisationstyp` (DSGVO), `scope` (AI Act) und `berater`. Ein
    Zustandsfilter („offene Punkte") bräuchte Kennzahlen, die dort nicht
    stehen — und sie je Projekt nachzuladen wären Dutzende Requests für eine
    Seitenleiste.
    """
    erwartet = {
        "FirmenSidebarModul.vue": ("einrichtungsklasse", "organisationstyp", "berater"),
        "AIActSidebar.vue": ("scope",),
        "WiBASidebar.vue": ("berater",),
    }
    for name, felder in erwartet.items():
        inhalt = _text(name)
        for feld in felder:
            assert f"'{feld}'" in inhalt or f'"{feld}"' in inhalt, (
                f"{name}: Filterfeld „{feld}“ fehlt")
