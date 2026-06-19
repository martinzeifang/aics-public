"""Fristen-/Deadline-Engine (Phase 0, Milestone #28 · Sprint #26).

Modul-übergreifende, deklarative Berechnung gestufter gesetzlicher Meldefristen
und SLA-Fristen. Eine Stufe (``Stage``) ist ein benannter Fristtyp mit Offset ab
einem Basis-Zeitpunkt (z.B. „72h ab Erkennung"). ``evaluate`` liefert je Stufe
``due_at`` + Ampel (``gruen``/``gelb``/``rot``/``overdue``) + verbleibende Stunden.

Pure Python (stdlib only). Keine DB, keine Flask-Abhängigkeit — daher überall
(API, Reports, Cockpit) wiederverwendbar und einfach testbar.

Verwendung::

    import cra.deadlines as dl
    res = dl.evaluate("2026-09-12T08:00:00", "cra_art14")
    res["stages"][0]  # -> {"key":"early_warning","due_at":..., "ampel":"rot", ...}

CRA Art. 14 (#1192): Frühwarnung 24h, Notification 72h, Abschluss 14d
(Schwachstelle) bzw. 1 Monat (Vorfall). Die 1-Monats-Frist läuft konventions-
gemäß ab dem 72h-Meldezeitpunkt; hier konservativ ab Basis modelliert und über
``override`` je Stufe anpassbar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


# ── Stufen-Definition ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Stage:
    """Eine Meldestufe/SLA-Stufe mit Offset ab Basiszeitpunkt."""
    key: str
    label: str
    offset_hours: float


# Vordefinierte Stufen-Sets (STAGE_SET). Erweiterbar pro Compliance-Regime.
STAGE_SET: dict[str, list[Stage]] = {
    # CRA Art. 14 — aktiv ausgenutzte Schwachstelle (Abschluss 14 Tage).
    "cra_art14": [
        Stage("early_warning", "Frühwarnung (24h)", 24),
        Stage("notification", "Meldung (72h)", 72),
        Stage("final_report", "Abschlussbericht (14 Tage)", 14 * 24),
    ],
    # CRA Art. 14 — schwerwiegender Vorfall (Abschluss 1 Monat).
    "cra_art14_incident": [
        Stage("early_warning", "Frühwarnung (24h)", 24),
        Stage("notification", "Meldung (72h)", 72),
        Stage("final_report", "Abschlussbericht (1 Monat)", 30 * 24),
    ],
}

# Ampel-Schwellen (Anteil verbleibender Zeit zum Gesamtfenster der Stufe).
_AMPEL_GELB = 0.5   # < 50 % Restzeit → gelb
_AMPEL_ROT = 0.1    # < 10 % Restzeit → rot


def _parse_iso(value: str) -> datetime:
    """ISO-8601 robust parsen; naive Zeit als UTC interpretieren."""
    s = str(value or "").strip()
    if not s:
        raise ValueError("Leerer Zeitstempel")
    # 'Z'-Suffix für fromisoformat (< 3.11) ersetzen.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # 'YYYY-MM-DD HH:MM:SS' (SQLite datetime('now')) → ISO mit 'T'.
    if " " in s and "T" not in s:
        s = s.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Nur Datum?
        dt = datetime.fromisoformat(s[:10])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _ampel(hours_left: float, window_hours: float) -> str:
    if hours_left < 0:
        return "overdue"
    if window_hours <= 0:
        return "rot"
    frac = hours_left / window_hours
    if frac < _AMPEL_ROT:
        return "rot"
    if frac < _AMPEL_GELB:
        return "gelb"
    return "gruen"


def evaluate(base_iso: str, stage_set: str,
             *, now: Optional[datetime] = None,
             overrides: Optional[dict[str, float]] = None) -> dict[str, Any]:
    """Stufen eines STAGE_SET ab ``base_iso`` auswerten.

    Args:
        base_iso: Basiszeitpunkt (z.B. ``erkannt_am``), ISO-8601.
        stage_set: Schlüssel in ``STAGE_SET`` (z.B. ``"cra_art14"``).
        now: Vergleichszeitpunkt (Default: jetzt, UTC) — für Tests setzbar.
        overrides: ``{stage_key: offset_hours}`` zum Überschreiben einzelner Offsets
            (z.B. 1-Monats-Frist ab 72h-Meldung).

    Returns:
        ``{"base","stage_set","now","stages":[…],"next_due":…,"any_overdue":bool}``.
        Jede Stufe: ``{key,label,due_at,hours_left,ampel,overdue}``.
    """
    stages = STAGE_SET.get(stage_set)
    if stages is None:
        raise ValueError(f"Unbekanntes Stage-Set: {stage_set!r}")
    base = _parse_iso(base_iso)
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    ov = overrides or {}

    out_stages: list[dict[str, Any]] = []
    prev_offset = 0.0
    next_due: Optional[str] = None
    any_overdue = False
    for st in stages:
        offset = float(ov.get(st.key, st.offset_hours))
        due = base + timedelta(hours=offset)
        hours_left = (due - ref).total_seconds() / 3600.0
        window = max(offset - prev_offset, 1.0)
        ampel = _ampel(hours_left, window)
        overdue = hours_left < 0
        any_overdue = any_overdue or overdue
        out_stages.append({
            "key": st.key,
            "label": st.label,
            "offset_hours": offset,
            "due_at": due.isoformat(),
            "hours_left": round(hours_left, 2),
            "ampel": ampel,
            "overdue": overdue,
        })
        if next_due is None and not overdue:
            next_due = due.isoformat()
        prev_offset = offset

    return {
        "base": base.isoformat(),
        "stage_set": stage_set,
        "now": ref.isoformat(),
        "stages": out_stages,
        "next_due": next_due,
        "any_overdue": any_overdue,
    }


# ── SLA-Dauer-Parser (#1207) ────────────────────────────────────────────────────

_UNIT_HOURS = {
    "h": 1.0, "hour": 1.0, "hours": 1.0, "stunde": 1.0, "stunden": 1.0, "std": 1.0,
    "d": 24.0, "day": 24.0, "days": 24.0, "tag": 24.0, "tage": 24.0, "t": 24.0,
    "w": 168.0, "week": 168.0, "weeks": 168.0, "woche": 168.0, "wochen": 168.0,
    "m": 720.0, "month": 720.0, "months": 720.0, "monat": 720.0, "monate": 720.0,
}


def parse_duration_hours(text: str) -> Optional[float]:
    """Freitext-SLA (z.B. ``"7 Tage"``, ``"24h"``, ``"2 Wochen"``) → Stunden.

    Liefert ``None``, wenn keine Dauer erkannt wird.
    """
    import re
    s = str(text or "").strip().lower()
    if not s:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*([a-zäöü]+)", s)
    if not m:
        # nur eine Zahl → als Tage interpretieren (häufigste SLA-Einheit)
        m2 = re.search(r"(\d+(?:[.,]\d+)?)", s)
        if m2:
            return float(m2.group(1).replace(",", ".")) * 24.0
        return None
    value = float(m.group(1).replace(",", "."))
    unit = m.group(2)
    factor = _UNIT_HOURS.get(unit)
    if factor is None:
        # Präfix-Match (z.B. 'stund...')
        for k, v in _UNIT_HOURS.items():
            if unit.startswith(k):
                factor = v
                break
    if factor is None:
        return None
    return value * factor


def sla_status(base_iso: str, duration_text: str,
               *, now: Optional[datetime] = None) -> dict[str, Any]:
    """SLA-Soll-Datum + on-track/fällig/überfällig-Status berechnen (#1207).

    Returns ``{"due_at","hours_left","status","sla_hours"}``;
    ``status`` ∈ ``on_track|faellig|ueberfaellig|unbekannt``.
    """
    hours = parse_duration_hours(duration_text)
    if hours is None:
        return {"due_at": None, "hours_left": None, "status": "unbekannt",
                "sla_hours": None}
    base = _parse_iso(base_iso)
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    due = base + timedelta(hours=hours)
    hours_left = (due - ref).total_seconds() / 3600.0
    if hours_left < 0:
        status = "ueberfaellig"
    elif hours_left < (hours * _AMPEL_GELB):
        status = "faellig"
    else:
        status = "on_track"
    return {"due_at": due.isoformat(), "hours_left": round(hours_left, 2),
            "status": status, "sla_hours": hours}
