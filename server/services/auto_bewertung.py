"""Gemeinsamer Helfer für die automatische KI-Bewertung von Anforderungen (#1366).

Die Module CRA/NIS2/AI-Act/DSGVO/DORA besitzen bereits einen Copy-/Paste-Flow
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

from server.services.anforderung_prompt import parse_chatgpt_json
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
            max_output_tokens=1200,
        )
    except Exception as e:  # CloudProviderError, Netzfehler, …
        raise AutoBewertungError(f"KI-Aufruf fehlgeschlagen: {e}") from e

    raw = getattr(resp, "text", None) or ""
    try:
        parsed = parse_chatgpt_json(raw)
    except ValueError as e:
        raise AutoBewertungError(f"KI-Antwort nicht verwertbar: {e}") from e

    try:
        score = int(parsed.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(5, score))

    return {
        "score": score,
        "kommentar": parsed.get("kommentar", "") or "",
        "massnahme": parsed.get("massnahme", "") or "",
        "parsed": parsed,
        "provider": current_provider_name(),
    }


__all__ = [
    "AutoBewertungError",
    "AutoBewertungUnavailable",
    "ensure_ai_available",
    "evaluate_prompt",
]
