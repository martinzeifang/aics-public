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
    """AI Act Art. 13/14/50 (#1551/#1552): automatisch gespeicherte KI-Bewertungen
    bleiben als solche erkennbar — Kennzeichnung mit Provider + Datum am Kommentarende.
    Idempotent: eine bereits vorhandene Kennzeichnung wird ersetzt, nicht gedoppelt."""
    from datetime import date
    text = str(kommentar or "").rstrip()
    if f"— {KI_MARKER}" in text:
        text = text.split(f"— {KI_MARKER}", 1)[0].rstrip()
    zeile = f"— {KI_MARKER} ({provider or 'KI'}, {date.today().isoformat()}) — fachlich zu prüfen."
    return f"{text}\n\n{zeile}" if text else zeile


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
            max_output_tokens=4096,  # #1419/#1588 — reicheres Format braucht mehr Platz (sonst abgeschnitten)
        )
    except Exception as e:  # CloudProviderError, Netzfehler, …
        raise AutoBewertungError(f"KI-Aufruf fehlgeschlagen: {e}") from e

    raw = getattr(resp, "text", None) or ""
    try:
        parsed = parse_chatgpt_json(raw)
    except ValueError as e:
        raise AutoBewertungError(f"KI-Antwort nicht verwertbar: {e}") from e

    n = normalize_eval_parsed(parsed)  # #1419 — reiche Struktur (Maßnahmen-Liste, Normbezug)

    provider = current_provider_name()
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


def stream_auto_bewertung(prompt: str, *, save):
    """Live-Streaming-Variante (#1408): streamt die KI-Antwort als SSE und parst/
    speichert am Ende. ``save(score, kommentar, massnahme)`` persistiert das Ergebnis.

    Returns eine Flask-SSE-Response (Token-für-Token + finales ``done`` mit Score).
    """
    from shared.sse import stream_ai_sse

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

    return stream_ai_sse(_SYSTEM_PROMPT, prompt, finalize=_finalize, force_json=True,
                         temperature=0.2, num_predict=4096)  # #1419/#1588 — sonst Antwort abgeschnitten


__all__ = [
    "KI_MARKER",
    "ki_kennzeichnung",
    "AutoBewertungError",
    "AutoBewertungUnavailable",
    "ensure_ai_available",
    "evaluate_prompt",
    "stream_auto_bewertung",
]
