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


_BEKANNT = ("reifegrad", "offene", "modul", "projekt")


def _offene_zeile(o: dict[str, Any]) -> str:
    """Eine offene Position — Bewertung nur, wenn das Modul eine 0–5-Skala führt.

    Compliance-Audit und WiBA bewerten nicht numerisch; ein hart gesetztes
    ``(Bewertung 0/5)`` hätte dort jede Lücke als Nullbewertung ausgewiesen.
    """
    kopf = f"- {o.get('id', '')}: {o.get('titel', '')}".rstrip(": ")
    if o.get("bewertung") is not None:
        return f"{kopf} (Bewertung {o['bewertung']}/5)"
    if o.get("status"):
        return f"{kopf} (Status: {o['status']})"
    return kopf


def build_summary_prompt(modul_label: str, projekt: str, ctx: dict[str, Any]) -> str:
    """Baut den Prompt aus dem modul-gelieferten Kennzahlen-Kontext.

    ``reifegrad``/``offene`` sind der gewachsene Vertrag (CRA/NIS2/AI-Act/DSGVO).
    Alle **weiteren** Schlüssel werden mitgegeben statt verworfen (#1725): Module
    mit eigenem Zuschnitt — Compliance-Audit (Stand/Lücken), Firmen-Überblick
    (Module/Risiken) — lieferten Daten, die der Prompt nie sah; die KI antwortete
    daraufhin wahrheitsgemäß, es lägen keine Daten vor.
    """
    reifegrad = ctx.get("reifegrad") or {}
    offene = ctx.get("offene") or []
    weitere = {k: v for k, v in ctx.items()
               if k not in _BEKANNT and v not in (None, "", [], {})}

    lines = [f"Modul: {modul_label}", f"Projekt/Firma: {projekt}"]
    if reifegrad:
        lines += ["", "Reifegrad-Kennzahlen (JSON):",
                  json.dumps(reifegrad, ensure_ascii=False, default=str)[:2500]]
    if offene:
        lines += ["", f"Offene/unzureichend bewertete Punkte ({len(offene)}):"]
        lines += [_offene_zeile(o) for o in offene[:40]]
    if weitere:
        lines += ["", "Weitere Kennzahlen des Moduls (JSON):",
                  json.dumps(weitere, ensure_ascii=False, default=str)[:6000]]
    if not (reifegrad or offene or weitere):
        # Nur hier ist "keine Daten" die Wahrheit — sonst nie behaupten.
        lines += ["", "Datenlage: (keine Kennzahlen erfasst)"]
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
                             max_output_tokens=2048)  # #1588
    except Exception as e:  # noqa: BLE001
        raise SummaryError(f"KI-Aufruf fehlgeschlagen: {e}") from e
    return {"text": (getattr(resp, "text", None) or "").strip(),
            "provider": current_provider_name()}
