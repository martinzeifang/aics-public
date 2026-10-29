"""Prüfhinweise am KI-Entwurf (#1862).

Geprüft wird vor allem die **Schweigsamkeit**: Ein Hinweis, der immer erscheint,
ist keiner (#1774). Der Normalfall muss leer bleiben, und ein Weg ohne
Nachweis-Mechanismus darf keinen Beleg-Hinweis erzeugen — sonst stünde er bei
jeder positiven OWASP-Bewertung da und die Liste wäre nach einem Tag
Hintergrundrauschen.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from shared.ki_pruefhinweise import (ANSEHEN, ERFUELLUNG_AB, NACHARBEIT,
                                     als_liste, erfuellung_behauptet, hinweise,
                                     schwerstes_gewicht)

WURZEL = Path(__file__).resolve().parents[1]


# ── Die Schwelle ────────────────────────────────────────────────────────────

def test_schwelle_folgt_dem_konformitaets_gate():
    """``shared`` darf nicht von einem Fachmodul abhängen — also steht die
    Schwelle zweimal da. Damit daraus keine stille Drift wird (#1731/#1735),
    hält dieser Test beide Werte gegeneinander.
    """
    quelle = (WURZEL / "cra" / "konformitaet_gate.py").read_text(encoding="utf-8")
    m = re.search(r"^_ERFUELLT_AB\s*=\s*(\d+)", quelle, re.MULTILINE)
    assert m, "`_ERFUELLT_AB` nicht mehr in cra/konformitaet_gate.py gefunden"
    assert int(m.group(1)) == ERFUELLUNG_AB, (
        f"Das Gate rechnet mit ≥ {m.group(1)}, die Prüfhinweise mit "
        f"≥ {ERFUELLUNG_AB}. Dann meldet die Oberfläche „ohne Beleg“ für "
        "Bewertungen, die das Gate als erfüllt zählt (oder umgekehrt).")


# ── Behauptet der Entwurf Erfüllung? ────────────────────────────────────────

@pytest.mark.parametrize("score,erwartet", [
    (5, True), (4, True), (3, False), (0, False), (None, None),
])
def test_erfuellung_nach_score(score, erwartet):
    assert erfuellung_behauptet(score=score) is erwartet


@pytest.mark.parametrize("status,erwartet", [
    ("ja", True),
    # `nicht_relevant` ist eine Aussage über das Produkt und braucht ihren
    # eigenen Beleg — deshalb wie „ja“ behandelt.
    ("nicht_relevant", True),
    ("nein", False),
    ("offen", None),
    ("", None),
])
def test_erfuellung_nach_wiba_antwort(status, erwartet):
    assert erfuellung_behauptet(wiba_status=status) is erwartet


def test_erfuellung_nach_risikostufe():
    assert erfuellung_behauptet(risiko_label="niedrig") is True
    assert erfuellung_behauptet(risiko_label="hoch") is False
    assert erfuellung_behauptet() is None


# ── Schweigsamkeit ──────────────────────────────────────────────────────────

def test_normalfall_erzeugt_keinen_hinweis():
    """Beleg vorhanden, angerechnet, Läufe einig → nichts. Kein „alles gut“."""
    assert hinweise(nachweise_im_prompt=["doc:1"], genutzte_nachweise=["doc:1"],
                    behauptet_erfuellung=True, einig=True) == []


def test_ohne_nachweis_mechanismus_kein_beleg_hinweis():
    """``None`` ≠ ``[]`` — die Unterscheidung trägt die ganze Funktion.

    Ein Weg, der keine Nachweise kennt (OWASP-Kontrollen), liefert ``None``.
    Würde er stattdessen ``[]`` liefern, stünde „ohne Beleg“ an **jeder**
    positiven Bewertung dieses Moduls.
    """
    assert hinweise(behauptet_erfuellung=True) == []
    assert hinweise(nachweise_im_prompt=None, behauptet_erfuellung=True) == []

    gesucht = hinweise(nachweise_im_prompt=[], behauptet_erfuellung=True)
    assert [h.art for h in gesucht] == ["erfuellung_ohne_beleg"]
    assert gesucht[0].gewicht == NACHARBEIT


def test_nur_bei_behaupteter_erfuellung():
    """Eine 2/5 ohne Beleg ist kein Befund — sie behauptet ja nichts."""
    assert hinweise(nachweise_im_prompt=[], behauptet_erfuellung=False) == []
    assert hinweise(nachweise_im_prompt=[], behauptet_erfuellung=None) == []


def test_beleg_vorhanden_aber_nicht_angerechnet():
    hs = hinweise(nachweise_im_prompt=["doc:1", "doc:2"], genutzte_nachweise=[],
                  behauptet_erfuellung=True)
    assert [h.art for h in hs] == ["beleg_nicht_angerechnet"]
    assert "2 Nachweis" in hs[0].text
    # Schwächer als „ohne Beleg“: Das Modell kann sie für unpassend gehalten haben.
    assert hs[0].gewicht == ANSEHEN


def test_ein_lauf_ist_keine_abweichung():
    """``einig=None`` heißt „nicht geprüft“, nicht „uneinig“."""
    assert hinweise(einig=None) == []
    assert [h.art for h in hinweise(einig=False)] == ["streuung"]
    assert hinweise(einig=True) == []


def test_technische_hinweise():
    hs = hinweise(abgeschnitten=True, nicht_abbildbar=["force_json"])
    arten = [h.art for h in hs]
    assert arten == ["abgeschnitten", "nicht_abbildbar"]
    # Die Reihenfolge ist Absicht: schwerste zuerst, der Mensch liest von oben.
    assert hs[0].gewicht > hs[1].gewicht


def test_schwerste_zuerst():
    hs = hinweise(nachweise_im_prompt=[], behauptet_erfuellung=True, einig=False,
                  nicht_abbildbar=["force_json"])
    gewichte = [h.gewicht for h in hs]
    assert gewichte == sorted(gewichte, reverse=True), hs
    assert schwerstes_gewicht(hs) == NACHARBEIT
    assert schwerstes_gewicht([]) == 0


def test_als_liste_ist_json_fertig():
    hs = hinweise(nachweise_im_prompt=[], behauptet_erfuellung=True)
    assert als_liste(hs) == [{"art": "erfuellung_ohne_beleg",
                             "text": hs[0].text, "gewicht": NACHARBEIT}]
    assert als_liste([]) == []


# ── Verdrahtung ─────────────────────────────────────────────────────────────

ANFORDERUNGS_STREAMS = [
    "server/api/cra/__init__.py",
    "server/api/nis2.py",
    "server/api/aiact.py",
    "server/api/dsgvo.py",
]


@pytest.mark.parametrize("pfad", ANFORDERUNGS_STREAMS)
def test_streams_verwerfen_die_nachweisliste_nicht_mehr(pfad: str):
    """Vorher stand dort ``block, _sources = …`` — die Angabe wurde geholt und
    weggeworfen. Ohne sie kann der wichtigste Hinweis nicht entstehen.
    """
    text = (WURZEL / pfad).read_text(encoding="utf-8")
    assert "block, _sources = _anf_evidence_block" not in text, (
        f"{pfad}: `sources` wird wieder verworfen (#1862).")
    assert "nachweise=sources" in text, (
        f"{pfad}: der Bewertungs-Stream gibt die Nachweisliste nicht weiter.")


def test_auto_bewertung_liefert_die_hinweise():
    """Beide Wege — synchron und streamend — müssen das Feld führen."""
    text = (WURZEL / "server" / "services" / "auto_bewertung.py").read_text(encoding="utf-8")
    assert text.count('"pruefhinweise"') >= 2, (
        "`pruefhinweise` fehlt in einem der beiden Wege (evaluate_prompt / "
        "stream_auto_bewertung).")


def test_die_anzeige_rechnet_nicht_selbst():
    """Die Regel gehört einmal in den Server, nicht zweimal.

    Die Oberfläche darf die Hinweise **anzeigen**, aber nicht ableiten — sonst
    gibt es die Schwelle und die Beleg-Logik im Frontend ein zweites Mal
    (#1703/S9).
    """
    for datei in ("AutoBewertungErgebnis.vue", "AutoMassBewertungModal.vue"):
        inhalt = (WURZEL / "frontend" / "src" / "components" / "shared"
                  / datei).read_text(encoding="utf-8")
        assert "pruefhinweise" in inhalt, f"{datei}: zeigt die Hinweise nicht"
        assert f">= {ERFUELLUNG_AB}" not in inhalt, (
            f"{datei}: leitet die Erfüllungsschwelle selbst ab — die Regel "
            "steht in shared/ki_pruefhinweise.")
