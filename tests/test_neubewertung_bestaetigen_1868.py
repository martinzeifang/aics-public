"""Die Markierung hat einen Ausgang (#1868).

Seit #1526 bewertet der Abgleich nicht mehr selbst — er **markiert**
score-neutral mit „⚠️ Neubewertung erforderlich". Das war richtig, nur hatte
die Markierung keinen Ausgang: `setze_marker` schrieb sie, `hat_marker` las
sie, und entfernt wurde sie allein beim Übernehmen einer **neuen** Bewertung
(`issue_completion.clear_markers`). Der häufigste Fall — angesehen, passt
weiterhin — zwang damit zu einer der beiden falschen Handlungen: eine Bewertung
neu abschicken (ein Vorgang, den es nicht gab) oder die Zeile von Hand aus dem
Freitext löschen (ohne jede Spur).

WARUM DAS EIN TEST IST
Die Behauptung „die Bestätigung ersetzt die Markierung" lässt sich am
Quelltext nicht ablesen — nur am Rundlauf. Dieselbe Lehre wie bei #1785 und
#1808: Setzen und Zurücknehmen gegeneinander laufen lassen, nicht die
Erzählung prüfen.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from shared import issue_abgleich as ia

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend" / "src"


# ── Der Rundlauf: setzen, bestätigen, nichts bleibt übrig ───────────────────

def test_bestaetigung_nimmt_die_markierung_weg():
    text, geaendert = ia.setze_marker("Bewertet am 01.10.", [ia.ANLASS_GESCHLOSSEN],
                                      ["#101"])
    assert geaendert and ia.hat_marker(text)

    neu, geaendert2 = ia.bestaetige_marker(text, von="Martin Zeifang",
                                           am="29.10.2026")
    assert geaendert2
    assert not ia.hat_marker(neu), "die Markierung steht noch da"
    assert ia.ist_bestaetigt(neu)
    # Der Bestand bleibt — bestätigt wird die Bewertung, nicht ihr Text.
    assert "Bewertet am 01.10." in neu


def test_person_und_datum_stehen_in_der_zeile():
    neu, _ = ia.bestaetige_marker(ia.marker_text([ia.ANLASS_GESCHLOSSEN]),
                                  von="Dr. Beispiel", am="29.10.2026")
    assert "Dr. Beispiel" in neu and "29.10.2026" in neu


def test_notiz_kommt_mit():
    neu, _ = ia.bestaetige_marker(ia.marker_text([ia.ANLASS_GESCHLOSSEN]),
                                  von="P", am="01.01.2026",
                                  notiz="Maßnahme war schon vorher wirksam.")
    assert "Maßnahme war schon vorher wirksam." in neu


def test_ohne_person_keine_bestaetigung():
    """Eine Bestätigung ohne Urheber ist keine (Muster `ki_herkunft.pruefen`)."""
    with pytest.raises(ValueError):
        ia.bestaetige_marker("⚠️ Neubewertung erforderlich – x", von="  ",
                             am="01.01.2026")


def test_zweimal_bestaetigen_stapelt_nicht():
    """Zwei Bestätigungen untereinander sagen nicht mehr als eine."""
    erst, _ = ia.bestaetige_marker(ia.marker_text([ia.ANLASS_GESCHLOSSEN]),
                                   von="A", am="01.01.2026")
    zweit, _ = ia.bestaetige_marker(erst, von="B", am="02.01.2026")
    assert zweit.count(ia.BESTAETIGT) == 1
    assert "B" in zweit and "02.01.2026" in zweit


def test_erneuter_marker_nach_bestaetigung_ersetzt_sie():
    """Tut sich am Issue wieder etwas, gilt die alte Bestätigung nicht mehr.

    `setze_marker` räumt die Bestätigungszeile mit weg — sonst stünde
    „bestätigt" über „neu zu bewerten", und der Leser müsste raten, welche
    Zeile die jüngere ist.
    """
    bestaetigt, _ = ia.bestaetige_marker(ia.marker_text([ia.ANLASS_GESCHLOSSEN]),
                                         von="A", am="01.01.2026")
    wieder, geaendert = ia.setze_marker(bestaetigt, [ia.ANLASS_GEOEFFNET], ["#7"])
    assert geaendert and ia.hat_marker(wieder)
    assert not ia.ist_bestaetigt(wieder), \
        "die überholte Bestätigung steht noch im Text"


def test_leerzeilen_wachsen_nicht():
    """Die Falle aus `setze_marker`: `strip()`, nicht `rstrip()`."""
    text = ia.setze_marker("Grundtext", [ia.ANLASS_GESCHLOSSEN])[0]
    einmal, _ = ia.bestaetige_marker(text, von="A", am="01.01.2026")
    nochmal, geaendert = ia.bestaetige_marker(einmal, von="A", am="01.01.2026")
    assert not geaendert, "derselbe Klick verändert den Text ein zweites Mal"
    assert nochmal == einmal


# ── Der Wert bleibt unberührt ──────────────────────────────────────────────

def test_bestaetigen_ruehrt_den_wert_nicht_an():
    """#1526 gilt in beide Richtungen.

    Der Abgleich darf nicht bewerten — und die Bestätigung auch nicht. Sie
    sagt, dass die Bewertung **weiter gilt**, nicht welche sie ist. Deshalb
    nimmt `bestaetige_marker` nur Text und gibt nur Text zurück.
    """
    quelle = inspect.getsource(ia.bestaetige_marker)
    for verboten in ("score", "bewertung =", "antwort =", "risikowert"):
        assert verboten not in quelle, \
            f"`bestaetige_marker` fasst {verboten!r} an — das ist eine Bewertung"


# ── Jede Objektart hat die Route (die Falle aus #1731) ─────────────────────

ERWARTET = {
    "cra": "/api/cra",
    "nis2": "/api/nis2",
    "aiact": "/api/aiact",
    "dsgvo": "/api/dsgvo",
    "wiba": "/api/wiba",
    "risikobewertung": "/api/risikobewertung",
}


def test_jede_objektart_kann_bestaetigt_werden(app):
    """Zehn Objektarten in sechs Modulen — ohne Ausnahme.

    Die Route kommt aus `shared.issue_api.register_routes`, also aus derselben
    Fabrik wie der Abgleich. Fehlt sie bei einer Art, ist das kein
    Schreibfehler, sondern ein Loch in der Bedienung: Dort bleibt die
    Markierung für immer stehen.
    """
    from shared.issue_api import arten_fuer

    regeln = {f"{sorted(r.methods - {'HEAD', 'OPTIONS'})[0]} {r.rule}"
              for r in app.url_map.iter_rules()}
    for modul, prefix in ERWARTET.items():
        arten = list(arten_fuer(modul))
        assert arten, f"{modul}: keine Objektarten"
        for a in arten:
            erwartet = (f"POST {prefix}/projekte/<projekt_name>/{a.pfad}/"
                        f"{a.param}/neubewertung/bestaetigen")
            assert erwartet in regeln, f"{modul}/{a.art}: {erwartet} fehlt"


# ── Die Oberfläche: ein Knopf, nicht neun ──────────────────────────────────

def test_nur_das_abzeichen_bestaetigt():
    """Der Aufruf steht in **einer** Komponente.

    `NeubewertungBadge` ist an neun Stellen eingebaut. Stünde der POST in
    jedem Einbauort, fehlte er beim zehnten — und zwar ohne dass etwas
    fehlschlägt (die Spiegel-Liste aus #1731/#1735).
    """
    treffer = sorted(
        str(p.relative_to(FRONTEND))
        for p in FRONTEND.rglob("*.vue")
        if "neubewertung/bestaetigen" in p.read_text(encoding="utf-8"))
    assert treffer == ["components/shared/NeubewertungBadge.vue"], \
        f"der Aufruf steht an mehreren Stellen: {treffer}"


def test_jeder_einbauort_uebergibt_die_koordinaten():
    """Ohne Modul, Projekt, Pfad und ID kann das Abzeichen nicht bestätigen.

    Es zeigt dann nur die Markierung — richtig, aber der Knopf fehlt. Diese
    Liste hält fest, wo das **bewusst** so ist; ohne Begründung wird rot,
    damit die Ausnahme nicht zum Teppich wird (Lehre aus #1805).
    """
    # Leer — und das ist die Aussage: Jeder Einbauort kann bestätigen.
    # Ein Eintrag hier braucht einen Grund, sonst wird die Liste zum Teppich
    # (die Lehre aus #1805).
    OHNE_KNOPF: dict[str, str] = {}
    fehler: list[str] = []
    for p in sorted(FRONTEND.rglob("*.vue")):
        rel = str(p.relative_to(FRONTEND))
        if rel == "components/shared/NeubewertungBadge.vue":
            continue
        text = p.read_text(encoding="utf-8")
        for tag in re.findall(r"<NeubewertungBadge\b[\s\S]*?/?>", text):
            if ":objekt-id" in tag or ":objektId" in tag:
                continue
            if rel in OHNE_KNOPF:
                continue
            fehler.append(rel)
    assert not fehler, (
        "Abzeichen ohne Objekt-Koordinaten (kein Bestätigen möglich): "
        + ", ".join(sorted(set(fehler))))
