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
    ensure_ai_available()

    # Import lokal, damit der App-Start auch ohne Provider-Abhängigkeiten klappt.
    from ai_compliance_suite.ai.dispatch import current_provider_name, generate_text

    try:
        resp = generate_text(
            system=_SYSTEM_PROMPT,
            prompt=prompt,
            temperature=0.2,
            max_output_tokens=2048,  # #1419 — reicheres Format braucht mehr Platz (sonst abgeschnitten)
        )
    except Exception as e:  # CloudProviderError, Netzfehler, …
        raise AutoBewertungError(f"KI-Aufruf fehlgeschlagen: {e}") from e

    raw = getattr(resp, "text", None) or ""
    try:
        parsed = parse_chatgpt_json(raw)
    except ValueError as e:
        raise AutoBewertungError(f"KI-Antwort nicht verwertbar: {e}") from e

    n = normalize_eval_parsed(parsed)  # #1419 — reiche Struktur (Maßnahmen-Liste, Normbezug)

    return {
        "score": n["score"],
        "kommentar": n["kommentar"],
        "massnahme": n["massnahme"],
        "massnahmen": n["massnahmen"],
        "normbezug": n["normbezug"],
        "genutzte_nachweise": n.get("genutzte_nachweise", []),  # #1485 Provenienz
        "parsed": parsed,
        "provider": current_provider_name(),
    }


def stream_auto_bewertung(prompt: str, *, save):
    """Live-Streaming-Variante (#1408): streamt die KI-Antwort als SSE und parst/
    speichert am Ende. ``save(score, kommentar, massnahme)`` persistiert das Ergebnis.

    Returns eine Flask-SSE-Response (Token-für-Token + finales ``done`` mit Score).
    """
    from shared.sse import stream_ai_sse

    def _finalize(full_text: str) -> dict:
        n = normalize_eval_parsed(parse_chatgpt_json(full_text))  # #1419
        save(n["score"], n["kommentar"], n["massnahme"])
        return {"bewertung": n["score"], "score": n["score"], "kommentar": n["kommentar"],
                "massnahme": n["massnahme"], "massnahmen": n["massnahmen"],
                "normbezug": n["normbezug"],
                "genutzte_nachweise": n.get("genutzte_nachweise", []),  # #1485 Provenienz
                "saved": True}

    return stream_ai_sse(_SYSTEM_PROMPT, prompt, finalize=_finalize, force_json=True,
                         temperature=0.2, num_predict=2048)  # #1419 — sonst Antwort abgeschnitten


__all__ = [
    "AutoBewertungError",
    "AutoBewertungUnavailable",
    "ensure_ai_available",
    "evaluate_prompt",
    "stream_auto_bewertung",
]
