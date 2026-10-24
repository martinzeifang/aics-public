"""Zentrale Frist-/Deadline-Engine (Sprint #26, Milestone #28, Phase 0, #1221).

Wiederverwendbar für alle fristgebundenen Melde-/Vorfall-Workflows:
- CRA Art. 14 (24h Frühwarnung / 72h Meldung / 14d / 1M Abschluss, ENISA-SRP)
- NIS2 Art. 23 (24h Frühwarnung / 72h Meldung / 1M Abschluss)
- AI-Act Art. 73 (2 / 10 / 15 Tage)
- DSGVO Art. 33 (72h Aufsichtsmeldung)

Kernidee: aus einem **Basis-Zeitpunkt** (Kenntniserlangung/Eintritt) + Stufen-
Offsets werden Soll-Fristen berechnet; je Stufe liefert die Engine Status
(on_track / due_soon / overdue / met), Restzeit und eine Ampel (green/amber/red).

Einheit ist standardmäßig **Stunden** (Tage = 24h); für Aufbewahrungs-/Monatsfristen
gibt es ``add_months``. Stdlib-only, keine externen Abhängigkeiten.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# ── Zeit-Parsing ────────────────────────────────────────────────────────────

ISO_FMTS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)


def parse_dt(value: str | datetime | None) -> datetime | None:
    """Parst ISO-Strings (mit/ohne Zeit/TZ) → timezone-aware datetime (UTC).

    Naive Eingaben werden als UTC interpretiert. None/leer/ungültig → None.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        # 'Z'-Suffix normalisieren
        if s.endswith("Z"):
            s = s[:-1] + "+0000"
        # ':' in TZ-Offset entfernen (+02:00 → +0200) für strptime %z
        if len(s) >= 6 and s[-3] == ":" and s[-6] in "+-":
            s = s[:-3] + s[-2:]
        dt = None
        for fmt in ISO_FMTS:
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_date(value: str | date | None) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    dt = parse_dt(value)
    return dt.date() if dt else None


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def add_months(d: date, months: int) -> date:
    """Addiert ganze Monate (Monatsende-sicher: 31.01 + 1M → 28./29.02)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = [31, 29 if _is_leap(year) else 28, 31, 30, 31, 30,
                31, 31, 30, 31, 30, 31]
    return date(year, month, min(d.day, last_day[month - 1]))


def add_months_iso(base: str | date, months: int) -> str:
    d = _parse_date(base)
    return add_months(d, months).isoformat() if d else ""


# ── Stufen-Modell ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DeadlineStage:
    """Eine Meldestufe relativ zum Basis-Zeitpunkt.

    ``offset_hours`` ist die gesetzliche Frist ab Basis (z. B. 72h).
    ``warn_ratio`` bestimmt, ab wann die Ampel auf gelb springt (Default 75 %).
    ``mandatory`` markiert Pflichtstufen (relevant für Vollständigkeits-Gates).
    """
    key: str
    label: str
    offset_hours: float
    warn_ratio: float = 0.75
    mandatory: bool = True


# Vordefinierte gesetzliche Stufen-Sets (Single Source of Truth) ──────────────
H = 1.0
D = 24.0

STAGE_SETS: dict[str, list[DeadlineStage]] = {
    # DSGVO Art. 33 — 72h-Aufsichtsmeldung
    "dsgvo_art33": [
        DeadlineStage("aufsichtsmeldung", "Meldung an Aufsichtsbehörde (72h)", 72 * H),
    ],
    # NIS2 Art. 23 — 24h Frühwarnung / 72h Meldung / 1M Abschlussbericht
    "nis2_art23": [
        DeadlineStage("fruehwarnung", "Frühwarnung (24h)", 24 * H),
        DeadlineStage("meldung", "Meldung (72h)", 72 * H),
        DeadlineStage("abschlussbericht", "Abschlussbericht (1 Monat)", 30 * D),
    ],
    # CRA Art. 14 — 24h Frühwarnung / 72h Meldung / 14d Zwischen / 1M Abschluss
    "cra_art14": [
        DeadlineStage("fruehwarnung", "Frühwarnung (24h)", 24 * H),
        DeadlineStage("meldung", "Meldung (72h)", 72 * H),
        DeadlineStage("zwischenbericht", "Zwischenbericht (14 Tage)", 14 * D, mandatory=False),
        DeadlineStage("abschlussbericht", "Abschlussbericht (1 Monat)", 30 * D),
    ],
    # AI-Act Art. 73 — schwerwiegender Vorfall: 15 Tage Regel, 2 Tage bei
    # weitverbreitetem Verstoß/kritischer Infrastruktur, 10 Tage bei Todesfall
    "aiact_art73": [
        DeadlineStage("sofort", "Sofortmeldung weitverbreitet/KRITIS (2 Tage)", 2 * D, mandatory=False),
        DeadlineStage("todesfall", "Meldung bei Todesfall (10 Tage)", 10 * D, mandatory=False),
        DeadlineStage("regelfrist", "Meldung Regelfrist (15 Tage)", 15 * D),
    ],
    # AI-Act Art. 52 — GPAI mit systemischem Risiko: Notifikation an die
    # Kommission unverzüglich, spätestens binnen 2 Wochen ab Schwellenwert-
    # Erreichung (10^25 FLOP) bzw. Kenntnis.
    "aiact_gpai_systemic": [
        DeadlineStage("kommission_notifikation",
                      "Notifikation an EU-Kommission (2 Wochen)", 14 * D),
    ],
}


def stages_for(stage_set: str) -> list[DeadlineStage]:
    return list(STAGE_SETS.get(stage_set, []))


# ── Status-Berechnung ───────────────────────────────────────────────────────

def stage_status(
    base: str | datetime | None,
    stage: DeadlineStage,
    *,
    fulfilled_at: str | datetime | None = None,
    now: datetime | None = None,
) -> dict:
    """Status einer einzelnen Meldestufe.

    Returns dict mit:
      due_at (ISO|''), status (no_base|met|overdue|due_soon|on_track),
      ampel (grey|green|amber|red), hours_left (float|None),
      hours_overdue (float|None), fulfilled (bool).
    """
    base_dt = parse_dt(base)
    if base_dt is None:
        return {"due_at": "", "status": "no_base", "ampel": "grey",
                "hours_left": None, "hours_overdue": None, "fulfilled": False,
                "key": stage.key, "label": stage.label}

    due = base_dt + timedelta(hours=stage.offset_hours)
    ref = parse_dt(now) or now_utc()
    ff = parse_dt(fulfilled_at)

    if ff is not None:
        on_time = ff <= due
        return {
            "due_at": due.isoformat(), "status": "met",
            "ampel": "green" if on_time else "red",
            "hours_left": None, "hours_overdue": None, "fulfilled": True,
            "fulfilled_at": ff.isoformat(), "on_time": on_time,
            "key": stage.key, "label": stage.label,
        }

    delta_h = (due - ref).total_seconds() / 3600.0
    if delta_h < 0:
        return {"due_at": due.isoformat(), "status": "overdue", "ampel": "red",
                "hours_left": 0.0, "hours_overdue": round(-delta_h, 2),
                "fulfilled": False, "key": stage.key, "label": stage.label}

    warn_threshold = stage.offset_hours * (1.0 - stage.warn_ratio)
    ampel = "amber" if delta_h <= warn_threshold else "green"
    status = "due_soon" if ampel == "amber" else "on_track"
    return {"due_at": due.isoformat(), "status": status, "ampel": ampel,
            "hours_left": round(delta_h, 2), "hours_overdue": None,
            "fulfilled": False, "key": stage.key, "label": stage.label}


def evaluate(
    base: str | datetime | None,
    stage_set: str | list[DeadlineStage],
    *,
    fulfilled: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict:
    """Bewertet alle Stufen eines Vorfalls.

    ``fulfilled`` mappt stage.key → ISO-Zeitpunkt der erfolgten Meldung.
    Returns {stages: [...], overall_ampel, any_overdue, next_due}.
    """
    stages = stage_set if isinstance(stage_set, list) else stages_for(stage_set)
    fulfilled = fulfilled or {}
    results = [
        stage_status(base, st, fulfilled_at=fulfilled.get(st.key), now=now)
        for st in stages
    ]
    any_overdue = any(r["status"] == "overdue" for r in results)
    any_due_soon = any(r["status"] == "due_soon" for r in results)
    # Nächste offene Pflichtstufe (kleinste hours_left, noch nicht erfüllt)
    open_stages = [r for r in results if not r["fulfilled"] and r["due_at"]]
    next_due = None
    if open_stages:
        next_due = sorted(
            open_stages,
            key=lambda r: (r["status"] != "overdue", r.get("hours_left") or 0),
        )[0]
    if any_overdue:
        overall = "red"
    elif any_due_soon:
        overall = "amber"
    elif results and all(r["fulfilled"] for r in results):
        overall = "green"
    elif not any(r["due_at"] for r in results):
        overall = "grey"
    else:
        overall = "green"
    return {"stages": results, "overall_ampel": overall,
            "any_overdue": any_overdue, "next_due": next_due}
