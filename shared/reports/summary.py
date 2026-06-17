"""KI-Management-Zusammenfassung fürs Berichts-Center (Sprint #35, #1393).

Generalisiert den SOC-Lagebericht: aus den Kennzahlen eines Moduls (Reifegrad +
offene Punkte) erzeugt die zentrale KI-Dispatch-Schicht eine prägnante
Management-Zusammenfassung (Fließtext). Datenübermittlung wird im Frontend wie beim
Prompt/Auto-Bewertungs-Flow bestätigt (#1380).
"""
from __future__ import annotations

import json
from typing import Any

_SYSTEM = (
    "Du bist ein erfahrener Compliance-/Sicherheits-Berater. Schreibe eine prägnante, "
    "sachliche Management-Zusammenfassung auf Deutsch (Fließtext, keine Markdown-Tabellen). "
    "Struktur: 1) Gesamtlage/Reifegrad, 2) wichtigste offene Punkte/Risiken, "
    "3) konkrete nächste Schritte. Max. ~250 Wörter. Keine Erfindungen — nur die Daten."
)


class SummaryUnavailable(RuntimeError):
    """KI-Provider nicht verfügbar (→ HTTP 409)."""


class SummaryError(RuntimeError):
    """KI-Aufruf fehlgeschlagen (→ HTTP 502)."""


def build_summary_prompt(modul_label: str, projekt: str, ctx: dict[str, Any]) -> str:
    """Baut den Prompt aus dem modul-gelieferten Kennzahlen-Kontext."""
    reifegrad = ctx.get("reifegrad") or {}
    offene = ctx.get("offene") or []
    lines = [
        f"Modul: {modul_label}",
        f"Projekt/Firma: {projekt}",
        "",
        "Reifegrad-Kennzahlen (JSON):",
        json.dumps(reifegrad, ensure_ascii=False, default=str)[:2500],
        "",
        f"Offene/unzureichend bewertete Punkte ({len(offene)}):",
    ]
    for o in offene[:40]:
        lines.append(f"- {o.get('id', '')}: {o.get('titel', '')} (Bewertung {o.get('bewertung', 0)}/5)")
    if not offene:
        lines.append("- (keine offenen Punkte erfasst)")
    lines += ["", "Erstelle daraus die Management-Zusammenfassung."]
    return "\n".join(lines)


def generate_summary(modul_label: str, projekt: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Ruft die zentrale KI-Dispatch-Schicht auf. Raises Summary(Unavailable|Error)."""
    from server.services.prefill import is_ai_available
    available, reason = is_ai_available()
    if not available:
        raise SummaryUnavailable(reason or "KI-Provider nicht verfügbar.")
    from ai_compliance_suite.ai.dispatch import current_provider_name, generate_text
    prompt = build_summary_prompt(modul_label, projekt, ctx)
    try:
        resp = generate_text(system=_SYSTEM, prompt=prompt, temperature=0.3,
                             max_output_tokens=900)
    except Exception as e:  # noqa: BLE001
        raise SummaryError(f"KI-Aufruf fehlgeschlagen: {e}") from e
    return {"text": (getattr(resp, "text", None) or "").strip(),
            "provider": current_provider_name()}
