"""#1875: Die geplante Maßnahme steht im Text des angelegten Issues.

Meldung aus dem Betrieb: „Die Maßnahmen zur Verbesserung sollten bei der
Issue-Anlage ebenfalls übernommen werden."

Das Issue ist der Arbeitsauftrag an die Entwicklung. Genau die Maßnahme ist
das, was dort getan werden soll; der Kommentar beschreibt nur den Stand. Die
Rückrichtung gab es längst (#1521, „Issue-Feedback übernehmen"), der Hinweg
ließ die Maßnahme liegen — in CRA, NIS2 und AI Act. DSGVO machte es von Anfang
an richtig.

WARUM VERHALTENSTESTS
Ein Wächter, der nach `massnahme_abschnitt` im Quelltext sucht, bleibt grün,
wenn der Aufruf durch eine leere Zeichenkette ersetzt wird — das Wort steht
noch im Kommentar darüber (die Lehre aus #1834). Hier wird der Bauer
aufgerufen und sein Ergebnis gelesen.
"""
from __future__ import annotations

import pytest

from shared.issue_api import massnahme_abschnitt

MASSNAHME = "Signaturpruefung im Update-Kanal nachruesten"


# ── Der geteilte Helfer ─────────────────────────────────────────────────────

def test_block_nur_bei_erfasster_massnahme():
    """Ohne Maßnahme bleibt der Text byte-identisch zu vorher.

    Dieselbe Zusage wie bei `evidence_section` (#1483) und `prompt_zusatz`
    (#1832) — sie macht jeden Bestandstest zum Regressionsschutz.
    """
    assert massnahme_abschnitt(None) == ""
    assert massnahme_abschnitt({}) == ""
    assert massnahme_abschnitt({"massnahme": ""}) == ""
    assert massnahme_abschnitt({"massnahme": "   "}) == ""


def test_block_enthaelt_die_massnahme_mit_ueberschrift():
    block = massnahme_abschnitt({"massnahme": MASSNAHME})
    assert MASSNAHME in block
    assert "### Geplante Maßnahme" in block
    # Kein an den Kommentar gehängter Zusatz, sondern ein eigener Abschnitt.
    assert block.startswith("\n### ")


def test_ueberschrift_ist_waehlbar():
    """DSGVO nutzt Fettschrift statt einer Überschrift — der Helfer muss beides
    können, sonst bekäme ein Modul einen fremden Aufbau aufgezwungen."""
    block = massnahme_abschnitt({"massnahme": MASSNAHME}, "**Geplante Maßnahme:**")
    assert "**Geplante Maßnahme:**" in block and MASSNAHME in block


# ── Die Bauer der Module ────────────────────────────────────────────────────

def _bauer():
    """Die Issue-Text-Bauer, die eine Maßnahmen-Spalte haben.

    CRA-OWASP, WiBA und die Risikobewertung führen **keine** `massnahme` in
    ihren Tabellen (geprüft gegen `information_schema`) — sie gehören deshalb
    nicht in diese Liste. Eine Prüfung, die dort etwas verlangt, was es nicht
    gibt, wäre eine erfundene Anforderung.
    """
    paare = []
    try:
        from server.api.cra import _cra_issue_content
        paare.append(("CRA", _cra_issue_content))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"CRA nicht importierbar: {e}")
    try:
        from server.api.nis2 import _nis2_issue_content
        paare.append(("NIS2", _nis2_issue_content))
    except Exception:  # noqa: BLE001
        pass
    try:
        from server.api.aiact import _aiact_issue_content
        paare.append(("AI Act", _aiact_issue_content))
    except Exception:  # noqa: BLE001
        pass
    try:
        from server.api.dsgvo import _dsgvo_issue_content
        paare.append(("DSGVO", _dsgvo_issue_content))
    except Exception:  # noqa: BLE001
        pass
    return paare


REQ = {"id": "R-1", "titel": "Sichere Aktualisierung", "kapitel": "C3",
       "ref": "Anhang I Teil II Nr. 2", "beschreibung": "Beschreibungstext",
       "hinweise": "Hinweistext", "gewichtung": 1}


def test_jeder_bauer_traegt_die_massnahme():
    paare = _bauer()
    assert paare, "kein Issue-Text-Bauer importierbar"
    for name, fn in paare:
        _titel, body = fn("R-1", dict(REQ),
                          {"bewertung": 2, "kommentar": "Stand", "massnahme": MASSNAHME})
        assert MASSNAHME in body, (
            f"{name}: Die geplante Maßnahme fehlt im Issue-Text — genau der "
            "Defekt aus #1875.")


def test_ohne_massnahme_kein_leerer_abschnitt():
    """Ein leerer Block im Issue sieht aus wie eine vergessene Angabe."""
    for name, fn in _bauer():
        _titel, body = fn("R-1", dict(REQ), {"bewertung": 2, "kommentar": "Stand"})
        assert "Geplante Maßnahme" not in body, (
            f"{name}: leerer Maßnahmen-Abschnitt im Issue-Text")
