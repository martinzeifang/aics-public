"""Sprint #26 Phase 0 — Wiederverwendbare Fristen-Engine.

Einheitliche Frist-/Countdown-Logik für gesetzliche Meldefristen (z. B. DSGVO
Art. 33 72h, NIS2 24h/72h). Module registrieren eine Fristen-Spezifikation als
``STAGE_SET``-Eintrag und werten sie über :func:`evaluate` aus.

``evaluate(base_iso, set_key)`` liefert ein status-armes Dict::

    {
      "due_at":     ISO-Timestamp der Frist (oder ""),
      "hours_left": float | None,
      "overdue":    bool,
      "ampel":      "gruen" | "gelb" | "rot" | "grau",
      "label":      Menschliche Frist-Bezeichnung,
      "deadline_hours": int,
    }

Die Engine ist zeit-injizierbar (``now`` Parameter) und damit deterministisch
testbar. Sie kennt keine Datenbank — reine Berechnung.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class DeadlineSpec:
    """Spezifikation einer gesetzlichen Frist.

    deadline_hours: Frist ab Basiszeitpunkt in Stunden.
    warn_ratio:     Anteil der Frist, ab dem die Ampel auf "gelb" springt
                    (z. B. 0.5 = ab Hälfte der Restzeit aufgebraucht).
    label:          Anzeige-Label.
    """

    deadline_hours: int
    label: str
    warn_ratio: float = 0.5


# Registrierte Fristen-Sets (Single Source of Truth).
STAGE_SET: dict[str, DeadlineSpec] = {
    # DSGVO Art. 33(1): Meldung an die Aufsichtsbehörde binnen 72 h nach Bekanntwerden.
    "dsgvo_art33": DeadlineSpec(deadline_hours=72, label="Meldung an Aufsichtsbehörde (Art. 33 — 72 h)"),
}


def _parse(value: Any) -> datetime | None:
    """Parst ISO-Datum/-Timestamp (mit/ohne Zeit, mit/ohne TZ) → aware UTC."""
    if not value:
        return None
    s = str(value).strip()
    try:
        if len(s) <= 10:  # reines Datum → Tagesbeginn
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        else:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def evaluate(base_iso: Any, set_key: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Wertet eine Frist gegen die aktuelle (oder injizierte) Zeit aus.

    base_iso: Basiszeitpunkt (z. B. ``festgestellt_am``) als ISO-String.
    set_key:  Schlüssel in :data:`STAGE_SET`.
    """
    spec = STAGE_SET.get(set_key)
    if spec is None:
        raise ValueError(f"Unbekanntes Fristen-Set: {set_key}")

    base = _parse(base_iso)
    if base is None:
        return {
            "due_at": "",
            "hours_left": None,
            "overdue": False,
            "ampel": "grau",
            "label": spec.label,
            "deadline_hours": spec.deadline_hours,
        }

    due = base + timedelta(hours=spec.deadline_hours)
    current = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    delta = due - current
    hours_left = round(delta.total_seconds() / 3600.0, 2)
    overdue = delta.total_seconds() < 0

    if overdue:
        ampel = "rot"
    elif hours_left <= spec.deadline_hours * spec.warn_ratio:
        ampel = "gelb"
    else:
        ampel = "gruen"

    return {
        "due_at": due.isoformat(),
        "hours_left": hours_left,
        "overdue": overdue,
        "ampel": ampel,
        "label": spec.label,
        "deadline_hours": spec.deadline_hours,
    }


def is_terminal(status: str, terminal: tuple[str, ...]) -> bool:
    """Hilfsfunktion: True, wenn ``status`` ein Abschluss-Status ist
    (dann ist kein Frist-Alarm mehr nötig)."""
    return status in terminal
