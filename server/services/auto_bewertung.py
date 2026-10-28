"""Gemeinsamer Helfer für die automatische KI-Bewertung von Anforderungen (#1366).

Die Module CRA/NIS2/AI-Act/DSGVO besitzen bereits einen Copy-/Paste-Flow
(`build_*_prompt` + `parse-response`). Dieses Modul ergänzt **additiv** den direkten
LLM-Aufruf: derselbe Prompt geht über die zentrale Provider-Dispatch-Schicht
(`ai_compliance_suite.ai.dispatch.generate_text`, #1342) an Ollama ODER Cloud,
die Antwort wird mit der bestehenden Parse-Logik geparst.

Wiederverwendung statt Duplikation:
- Prompt-Bau: bleibt in den Modulen (`build_*_prompt` / `_build_anforderung_prompt`).
- Parsing: `server.services.anforderung_prompt.parse_chatgpt_json` (reine Funktion).
- Verfügbarkeitscheck: `server.services.prefill.is_ai_available`.
- Speichern: modul-eigene `save_bewertung`.

Kein stiller Fallback: ist KI nicht verfügbar, wird `AutoBewertungUnavailable`
geworfen (Endpoint → 409). Cloud ohne Egress wirft im Dispatch hart.
"""

from __future__ import annotations

from typing import Any, Dict

from server.services.anforderung_prompt import normalize_eval_parsed, parse_chatgpt_json
from server.services.prefill import is_ai_available


_SYSTEM_PROMPT = (
    "Du bist ein erfahrener Compliance-Auditor. Antworte ausschließlich mit "
    "validem JSON im geforderten Format. Verwende keinerlei Erläuterungen "
    "außerhalb des JSON-Objekts."
)


KI_MARKER = "🤖 KI-generiert"


def ki_kennzeichnung(kommentar: str, provider: str) -> str:
    """Gibt den Text **unverändert** zurück (#1765).

    Bis v8.0.0 hängte diese Funktion die Kennzeichnung an den gespeicherten
    Text an. Damit stand sie in jedem Bericht, der ihn druckt — auch in der
    EU-Konformitätserklärung und in der Fassung für den Kunden. Die Pflicht aus
    #1551/#1552 bleibt richtig, sie gilt aber gegenüber denen, die mit dem
    System arbeiten, nicht gegenüber dem Empfänger eines
    Konformitätsdokuments; und „fachlich zu prüfen" in einem freigegebenen
    Dokument nimmt diesem seine Aussage.

    Die Herkunft steht jetzt strukturiert in ``shared/ki_herkunft`` — samt der
    Angabe, wer sie wann geprüft hat, die vorher ganz fehlte. Die Hinweise in
    der Oberfläche bleiben unverändert.

    Die Funktion selbst bleibt bestehen, damit die sechs Aufrufer nicht
    gleichzeitig geändert werden müssen; sie ist jetzt die Identität. Ein Text,
    der den **alten** Marker noch trägt (Bestand), wird dabei bereinigt.
    """
    from shared.ki_herkunft import ohne_marker

    return ohne_marker(kommentar)


class AutoBewertungUnavailable(RuntimeError):
    """KI-Provider ist nicht verfügbar/konfiguriert (→ HTTP 409)."""


class AutoBewertungError(RuntimeError):
    """KI-Aufruf oder Antwort-Parsing ist fehlgeschlagen (→ HTTP 502)."""


def ensure_ai_available() -> None:
    """Wirft :class:`AutoBewertungUnavailable`, falls die KI nicht nutzbar ist."""
    available, reason = is_ai_available()
    if not available:
        raise AutoBewertungUnavailable(reason or "KI-Provider nicht verfügbar.")


def evaluate_prompt(prompt: str) -> Dict[str, Any]:
    """Ruft den konfigurierten LLM-Provider mit ``prompt`` auf und parst die Antwort.

    Returns ein Dict mit ``score`` (0-5, geklemmt), ``kommentar``, ``massnahme``
    sowie ``parsed`` (rohes geparstes JSON) und ``provider`` (genutzter Provider).

    Raises:
      AutoBewertungUnavailable: KI nicht verfügbar (vorab geprüft).
      AutoBewertungError: Provider-Fehler oder unparsebare Antwort.
    """
    # #1841: Der Lauf geht über die gemeinsame Engine. Sie prüft die
    # Verfügbarkeit, setzt die eigenen Hinweise des Bearbeiters ein (#1833),
    # leitet das Budget aus der Aufgabenart ab und schreibt den Revisions-
    # eintrag. Das Budget 4096 aus #1419/#1588 kam auf dem synchronen
    # on-prem-Weg bis #1841 gar nicht an — `generate_text` reichte es nicht
    # durch (verifizierter Defekt aus #1836).
    from shared.ki_engine import (OHNE_OBJEKT, KiAuftrag, KiNichtVerfuegbar,
                                  ki_lauf)

    try:
        erg = ki_lauf(KiAuftrag(
            prompt=prompt,
            # Das Fachobjekt kennt diese Funktion nicht; die Aufrufer
            # vermerken die Herkunft selbst (`vermerke_herkunft`). Beim
            # Streaming-Weg unten steht es richtig.
            herkunft=OHNE_OBJEKT,
            system=_SYSTEM_PROMPT,
            antwortform="json",
            aufgabe="bewertung",
        ))
    except KiNichtVerfuegbar as e:
        raise AutoBewertungUnavailable(str(e)) from e
    if not erg.ok:
        raise AutoBewertungError(erg.fehler or "KI-Aufruf fehlgeschlagen")

    parsed = erg.parsed
    n = normalize_eval_parsed(parsed)  # #1419 — reiche Struktur (Maßnahmen-Liste, Normbezug)

    provider = erg.provider
    return {
        "score": n["score"],
        "kommentar": ki_kennzeichnung(n["kommentar"], provider),
        "massnahme": n["massnahme"],
        "massnahmen": n["massnahmen"],
        "normbezug": n["normbezug"],
        "genutzte_nachweise": n.get("genutzte_nachweise", []),  # #1485 Provenienz
        "parsed": parsed,
        "provider": provider,
    }


def vermerke_herkunft(modul: str, projekt: str, art: str, objekt_id: str) -> None:
    """KI-Herkunft im Register festhalten (#1765) — best effort.

    Die Kennzeichnung steht nicht mehr im Text; ohne diesen Vermerk wüsste
    niemand mehr, dass die Bewertung aus einer KI stammt, und die Oberfläche
    könnte keine Prüfung einfordern. Ein Fehler hier darf aber die gerade
    erzeugte Bewertung nicht verwerfen — deshalb best effort mit Protokoll.
    """
    try:
        from ai_compliance_suite.ai.dispatch import current_provider_name
        from shared.ki_herkunft import vermerken

        vermerken(modul, projekt, art, str(objekt_id),
                  provider=current_provider_name())
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger("aics.ki").warning(
            "KI-Herkunft nicht vermerkt (%s/%s/%s): %s", modul, projekt, objekt_id, e)


def stream_auto_bewertung(prompt: str, *, save, herkunft: tuple | None = None):
    """Live-Streaming-Variante (#1408): streamt die KI-Antwort als SSE und parst/
    speichert am Ende. ``save(score, kommentar, massnahme)`` persistiert das Ergebnis.

    Returns eine Flask-SSE-Response (Token-für-Token + finales ``done`` mit Score).
    """
    from shared.ki_engine import (OHNE_OBJEKT, Herkunft, KiAuftrag, ki_lauf_sse)

    def _finalize(full_text: str) -> dict:
        from ai_compliance_suite.ai.dispatch import current_provider_name
        n = normalize_eval_parsed(parse_chatgpt_json(full_text))  # #1419
        kommentar = ki_kennzeichnung(n["kommentar"], current_provider_name())  # #1551/#1552
        save(n["score"], kommentar, n["massnahme"])
        return {"bewertung": n["score"], "score": n["score"], "kommentar": kommentar,
                "massnahme": n["massnahme"], "massnahmen": n["massnahmen"],
                "normbezug": n["normbezug"],
                "genutzte_nachweise": n.get("genutzte_nachweise", []),  # #1485 Provenienz
                "saved": True}

    # #1841: Die Herkunft wandert in den Auftrag, statt im `finalize` zu
    # stehen. Sie war hier schon richtig gesetzt — in ≥ 36 anderen Wegen
    # fehlte sie, weil jede Aufrufstelle es für sich entscheiden musste.
    modul, projekt, art, objekt_id = (herkunft if herkunft
                                      else ("ai", "", "", ""))
    return ki_lauf_sse(KiAuftrag(
        prompt=prompt,
        herkunft=Herkunft(art, str(objekt_id)) if herkunft else OHNE_OBJEKT,
        system=_SYSTEM_PROMPT,
        antwortform="json",
        aufgabe="bewertung",
        modul=modul,
        projekt=projekt,
        egress_pflicht=True,   # #1836/E2 — der AutoBewertungDialog bestätigt
    ), finalize=_finalize)


__all__ = [
    "KI_MARKER",
    "ki_kennzeichnung",
    "vermerke_herkunft",
    "AutoBewertungError",
    "AutoBewertungUnavailable",
    "ensure_ai_available",
    "evaluate_prompt",
    "stream_auto_bewertung",
]
