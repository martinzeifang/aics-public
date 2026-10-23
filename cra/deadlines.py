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
(Schwachstelle) bzw. 1 Monat (Vorfall).

Fristbeginn der Abschlussstufe (#1760): Die Abschlussfrist läuft **nicht** ab
Erkennung. Bei einer aktiv ausgenutzten Schwachstelle beginnt sie, sobald eine
Korrektur- oder Minderungsmaßnahme verfügbar ist; bei einem schwerwiegenden
Vorfall ab Einreichung der 72-Stunden-Meldung. Die ``offset_hours`` in
``STAGE_SET`` sind deshalb nur der Rohwert der gesetzlichen Dauer — den
Fristbeginn setzt ``art14_fristen()``, das auch die Stufe als ``unbestimmt``
ausweist, solange der Anker fehlt. Vorher rechnete jeder Aufrufer ab Erkennung
und die Ampel konnte Wochen zu früh rot zeigen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional


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
             overrides: Optional[dict[str, float]] = None,
             unbestimmt: Optional[Iterable[str]] = None,
             hinweise: Optional[dict[str, str]] = None,
             erfuellt: Optional[dict[str, str]] = None) -> dict[str, Any]:
    """Stufen eines STAGE_SET ab ``base_iso`` auswerten.

    Args:
        base_iso: Basiszeitpunkt (z.B. ``erkannt_am``), ISO-8601.
        stage_set: Schlüssel in ``STAGE_SET`` (z.B. ``"cra_art14"``).
        now: Vergleichszeitpunkt (Default: jetzt, UTC) — für Tests setzbar.
        overrides: ``{stage_key: offset_hours}`` zum Überschreiben einzelner Offsets
            (z.B. 1-Monats-Frist ab 72h-Meldung).
        unbestimmt: Stufen, deren Frist noch nicht läuft, weil der Fristbeginn
            fehlt (#1760). Sie bekommen ``due_at=None`` und die Ampel
            ``unbestimmt`` — nicht ``rot``. Eine Frist, die noch nicht begonnen
            hat, kann nicht überfällig sein.
        hinweise: ``{stage_key: Text}`` — Begründung/Fristbeginn je Stufe, wird
            als ``hinweis`` mitgegeben (z.B. „14 Tage ab Verfügbarkeit …").
        erfuellt: ``{stage_key: ISO-Zeitpunkt}`` der tatsächlichen Meldung. Eine
            gemeldete Stufe ist erledigt und wird nicht mehr als überfällig
            geführt; verspätete Meldung bleibt als ``verspaetet`` sichtbar.

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
    offen = set(unbestimmt or ())
    hints = hinweise or {}
    done = erfuellt or {}

    out_stages: list[dict[str, Any]] = []
    prev_offset = 0.0
    next_due: Optional[str] = None
    any_overdue = False
    for st in stages:
        offset = float(ov.get(st.key, st.offset_hours))
        hinweis = hints.get(st.key, "")
        if st.key in offen:
            # Fristbeginn nicht bestimmbar → keine Frist, keine Ampel-Panik.
            out_stages.append({
                "key": st.key,
                "label": st.label,
                "offset_hours": offset,
                "due_at": None,
                "hours_left": None,
                "ampel": "unbestimmt",
                "overdue": False,
                "unbestimmt": True,
                "hinweis": hinweis,
            })
            prev_offset = offset
            continue
        due = base + timedelta(hours=offset)
        hours_left = (due - ref).total_seconds() / 3600.0
        window = max(offset - prev_offset, 1.0)
        eintrag: dict[str, Any] = {
            "key": st.key,
            "label": st.label,
            "offset_hours": offset,
            "due_at": due.isoformat(),
            "hours_left": round(hours_left, 2),
            "unbestimmt": False,
            "hinweis": hinweis,
        }
        gemeldet = str(done.get(st.key) or "").strip()
        if gemeldet:
            try:
                gem_dt = _parse_iso(gemeldet)
            except ValueError:
                gem_dt = None
            verspaetet = bool(gem_dt and gem_dt > due)
            eintrag.update({
                "ampel": "erfuellt_verspaetet" if verspaetet else "erfuellt",
                "overdue": False,
                "erfuellt_am": gemeldet,
                "verspaetet": verspaetet,
            })
        else:
            overdue = hours_left < 0
            any_overdue = any_overdue or overdue
            eintrag.update({
                "ampel": _ampel(hours_left, window),
                "overdue": overdue,
                "erfuellt_am": None,
                "verspaetet": False,
            })
            if next_due is None and not overdue:
                next_due = due.isoformat()
        out_stages.append(eintrag)
        prev_offset = offset

    return {
        "base": base.isoformat(),
        "stage_set": stage_set,
        "now": ref.isoformat(),
        "stages": out_stages,
        "next_due": next_due,
        "any_overdue": any_overdue,
    }


# ── Fristbeginn CRA Art. 14 (#1760) ────────────────────────────────────────────

# Gesetzliche Dauer der Abschlussstufe je Stage-Set und ihr Anker.
#   cra_art14           — aktiv ausgenutzte Schwachstelle: Abschlussbericht
#                         14 Tage ab Verfügbarkeit einer Korrektur- oder
#                         Minderungsmaßnahme (Art. 14 Abs. 2 lit. c).
#   cra_art14_incident  — schwerwiegender Vorfall: Abschlussbericht 1 Monat ab
#                         Einreichung der Meldung nach Art. 14 Abs. 4 lit. b
#                         (also ab dem 72-Stunden-Meldezeitpunkt).
# Hinweis: Die Buchstaben-Untergliederung (lit. b/c) ist nach dem Verordnungs-
# text von 2024/2847 gesetzt; sie ist hier nur Fundstellen-Angabe für den
# Nachweis. Maßgeblich für die Rechnung sind Dauer und Anker, nicht das Zitat —
# im Repo sind schon widersprüchliche Artikelzitate aufgefallen (#1763), daher
# wird hier nichts hinzuerfunden, was nicht geprüft ist.
FINAL_REPORT_ANKER = {
    "cra_art14": {
        "feld": "massnahme_verfuegbar_ab",
        "label": "Verfügbarkeit einer Korrektur-/Minderungsmaßnahme",
        "dauer_tage": 14,
        "dauer_monate": 0,
        "fundstelle": "Art. 14 Abs. 2 lit. c",
    },
    "cra_art14_incident": {
        "feld": "notification_gemeldet_am",
        "label": "Einreichung der 72-Stunden-Meldung",
        "dauer_tage": 0,
        "dauer_monate": 1,
        "fundstelle": "Art. 14 Abs. 4 lit. c",
    },
}


def _add_months_dt(dt: datetime, months: int) -> datetime:
    """Ganze Kalendermonate auf einen Zeitstempel addieren (Monatsende-sicher).

    Nutzt ``shared.deadlines.add_months`` (eine Quelle für die Monatslogik) und
    hängt die Uhrzeit wieder an — 30·24 Stunden wären kein Monat.
    """
    from shared.deadlines import add_months
    d = add_months(dt.date(), months)
    return dt.replace(year=d.year, month=d.month, day=d.day)


def art14_fristen(base_iso: str, stage_set: str, *,
                  massnahme_verfuegbar_ab: Optional[str] = None,
                  notification_gemeldet_am: Optional[str] = None,
                  erfuellt: Optional[dict[str, str]] = None,
                  now: Optional[datetime] = None) -> dict[str, Any]:
    """Art.-14-Fristen mit korrektem Fristbeginn der Abschlussstufe (#1760).

    24h/72h laufen ab Erkennung (``base_iso``). Die Abschlussstufe läuft ab
    ihrem Anker (siehe ``FINAL_REPORT_ANKER``). Fehlt der Anker, ist die Frist
    ``unbestimmt`` statt überfällig — sie hat noch nicht begonnen.

    Das Ergebnis trägt zusätzlich ``abschlussfrist`` mit Anker, Fundstelle und
    Fristbeginn, damit der Nachweis die Rechnung offenlegt.
    """
    anker = FINAL_REPORT_ANKER.get(stage_set)
    if anker is None:
        return evaluate(base_iso, stage_set, now=now, erfuellt=erfuellt)

    roh = {"massnahme_verfuegbar_ab": massnahme_verfuegbar_ab,
           "notification_gemeldet_am": notification_gemeldet_am}
    anker_wert = str(roh.get(anker["feld"]) or "").strip()
    base = _parse_iso(base_iso)

    overrides: dict[str, float] = {}
    unbestimmt: list[str] = []
    dauer = (f"{anker['dauer_monate']} Monat" if anker["dauer_monate"]
             else f"{anker['dauer_tage']} Tage")
    info: dict[str, Any] = {
        "anker_feld": anker["feld"],
        "anker_label": anker["label"],
        "fundstelle": anker["fundstelle"],
        "dauer": dauer,
        "anker_am": anker_wert or None,
        "beginn": None,
        "bestimmt": False,
    }
    if anker_wert:
        try:
            start = _parse_iso(anker_wert)
        except ValueError:
            start = None
        if start is not None:
            if anker["dauer_monate"]:
                due = _add_months_dt(start, int(anker["dauer_monate"]))
            else:
                due = start + timedelta(days=int(anker["dauer_tage"]))
            overrides["final_report"] = (due - base).total_seconds() / 3600.0
            info.update({"beginn": start.isoformat(), "bestimmt": True,
                         "faellig_am": due.isoformat()})
    if not info["bestimmt"]:
        unbestimmt.append("final_report")

    hinweis = (f"{dauer} ab {anker['label']} ({anker['fundstelle']})"
               if info["bestimmt"] else
               f"Frist läuft noch nicht — {anker['label']} nicht erfasst "
               f"({dauer} ab diesem Zeitpunkt, {anker['fundstelle']})")
    res = evaluate(base_iso, stage_set, now=now, overrides=overrides,
                   unbestimmt=unbestimmt, hinweise={"final_report": hinweis},
                   erfuellt=erfuellt)
    res["abschlussfrist"] = info
    return res


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
