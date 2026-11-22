"""#1873: OWASP SbD und OWASP-LLM können über den Sammel-Prompt bewertet werden.

Meldung aus dem Betrieb: „OWASP SbD kann nicht wie die anderen über
Massenbewertung bewertet werden, bzw. es geht nicht über Prompt."

Der Adapter `owaspAutoAdapter` wies `prompt`, `preview` und `apply` hart ab
(„Sammel-Prompt für OWASP-Kontrollen nicht verfügbar"), weil die Endpunkte
`mass-prompt`/`mass-preview` fehlten. Damit war OWASP das einzige Register ohne
den Weg über EINEN Sammel-Prompt — und wer ohne lokale KI arbeitet oder den
Datenausgang nicht freigibt, hatte dort gar keinen Massenweg. Seit #1573 sollen
sich die Register genau nicht mehr so unterscheiden.
"""
from __future__ import annotations

from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent


# ── Die Übersetzung in die Form der geteilten Helfer ────────────────────────

def test_owasp_kontrolle_wird_zur_anforderungsform():
    """Die Helfer sprechen von `titel`/`bewertung`, OWASP von `title`/`status`.

    Diese Übersetzung ist der ganze Unterschied. Ein zweiter Prompt-Bauer wäre
    eine zweite Wahrheit über dieselbe Bewertungsskala (#1726/#1727).
    """
    from server.api.cra import _owasp_als_anforderung, _owasp_als_stand

    req = _owasp_als_anforderung({
        "id": "OWASP-PC-C1", "title": "Define Security Requirements",
        "description": "Beschreibung", "cra_articles": ["Anhang I Teil I"],
        "evidence_hint": "Hinweis"})
    assert req["id"] == "OWASP-PC-C1"
    assert req["titel"] == "Define Security Requirements"
    assert req["beschreibung"] == "Beschreibung"
    assert "Anhang I Teil I" in req["ref"]
    assert req["hinweise"] == "Hinweis"

    assert _owasp_als_stand({"status": 3, "kommentar": "K"}) == {
        "bewertung": 3, "kommentar": "K"}
    # Unlesbarer Status darf nicht hochschlagen — sonst fällt die ganze Auswahl aus.
    assert _owasp_als_stand({"status": "kaputt"})["bewertung"] == 0
    assert _owasp_als_stand(None)["bewertung"] == 0


def test_llm_eintrag_wird_zur_anforderungsform():
    from server.api.aiact import _llm_als_anforderung, _llm_als_stand

    req = _llm_als_anforderung({"id": "LLM01", "title": "Prompt Injection",
                                "maps_to": ["AIA-HR-07", "AIA-HR-05"]})
    assert req["id"] == "LLM01" and req["titel"] == "Prompt Injection"
    assert "AIA-HR-07" in req["ref"]
    # `maps_to` kommt in manchen Einträgen als Zeichenkette — nicht abstürzen.
    assert "X" in _llm_als_anforderung({"id": "L", "title": "T", "maps_to": "X"})["ref"]
    assert _llm_als_stand({"status": 5})["bewertung"] == 5


def test_auswahl_und_prompt_laufen_fuer_echte_kataloge():
    """Gegen die echten Kataloge, nicht gegen erfundene Einträge.

    Ein Test, der seine Daten selbst mitbringt, prüft nur sich selbst — das
    war die Lehre aus #1870.
    """
    from cra.owasp_proactive_controls import OWASP_PC_V3
    from server.api.cra import _owasp_als_anforderung, _owasp_als_stand
    from server.services.anforderung_prompt import (build_mass_anforderung_prompt,
                                                    select_for_mass)

    katalog = [_owasp_als_anforderung(c) for c in OWASP_PC_V3]
    assert len(katalog) == 10
    stand = {katalog[0]["id"]: _owasp_als_stand({"status": 5, "kommentar": ""})}
    offen = select_for_mass(katalog, stand, only_open=True)
    assert len(offen) == 9, "die vollständig bewertete Kontrolle muss entfallen"

    prompt = build_mass_anforderung_prompt(
        "CRA / OWASP Proactive Controls", "OWASP Proactive Controls v3",
        offen, {"name": "P", "unternehmen": "U"})
    assert katalog[1]["titel"] in prompt
    assert len(prompt) > 500


# ── Der Adapter darf nicht wieder abweisen ──────────────────────────────────

def test_adapter_weist_den_sammelprompt_nicht_mehr_ab():
    """Ein Adapter, der in einer Maske mit dem Knopf „🧮 Massenbewertung"
    steckt und `prompt` ablehnt, ist ein Knopf ohne Wirkung (#1805/#1830)."""
    quelle = (WURZEL / "frontend" / "src" / "utils" / "massAdapters.ts").read_text(
        encoding="utf-8")
    ohne_kommentare = "\n".join(
        z for z in quelle.splitlines()
        if not z.lstrip().startswith(("*", "//", "/*")))
    assert "nicht verfügbar" not in ohne_kommentare, (
        "owaspAutoAdapter weist den Sammel-Prompt wieder ab — #1873")
    # Der Adapter muss alle drei Fähigkeiten wirklich haben.
    abschnitt = ohne_kommentare.split("export function owaspAutoAdapter", 1)[1]
    for faehigkeit in ("async prompt(", "async preview(", "apply:"):
        assert faehigkeit in abschnitt, f"owaspAutoAdapter fehlt {faehigkeit}"


@pytest.mark.parametrize("pfad", ["owasp", "owasp-llm"])
def test_adapter_ruft_die_passenden_endpunkte(pfad):
    quelle = (WURZEL / "frontend" / "src" / "utils" / "massAdapters.ts").read_text(
        encoding="utf-8")
    abschnitt = quelle.split("export function owaspAutoAdapter", 1)[1]
    assert "/mass-prompt" in abschnitt and "/mass-preview" in abschnitt
    # Der Schlüssel heißt je Register anders — eine Fabrik, die ihn ableitet,
    # bräche genau dort (dieselbe Falle wie owasp_llm vs. owasp-llm in #1846).
    assert "owasp_ids" in abschnitt and "llm_ids" in abschnitt
