"""In-App-Scheduler für automatische SOC-Berichte (Quartal/Jahr) (#1350).

Opt-in über ``soc.config.json → berichte``:

    {
      "berichte": {
        "scheduler_enabled": true,
        "schedule": [
          {"typ": "alle_incidents", "periode": "quartal", "cron": "0 6 1 1,4,7,10 *", "format": "docx"},
          {"typ": "incident_gesamt", "periode": "jahr",    "cron": "0 7 1 1 *",       "format": "pdf"}
        ]
      }
    }

Pro Eintrag wird ein Cron-Job registriert, der den jeweiligen Bericht über den
*zuletzt abgeschlossenen* Quartals- bzw. Jahres-Zeitraum erzeugt und unter
``data/soc/berichte/`` ablegt (Lauf-Historie in ``soc_bericht_runs``).

Muster (guarded Import, File-Lock-Singleton, opt-in) wie ``cra/sync_scheduler.py``
und ``soc/sync_scheduler.py``. Die Spec-Parse-Logik ist von APScheduler unabhängig
(testbar); die Registrierung braucht einen Scheduler.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DB_PATH = Path("data/db/soc.sqlite")

_VALID_PERIODEN = ("quartal", "jahr")


def load_soc_cfg() -> dict[str, Any]:
    p = Path("soc.config.json")
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            log.warning("soc.config.json nicht lesbar — Berichts-Scheduler-Defaults")
    return {}


def _db_active_schedules() -> list[dict[str, Any]]:
    """Aktive GUI-Zeitpläne aus der DB (#1405). Robust: leere Liste bei Fehler."""
    try:
        from soc.berichte import list_schedules
        return [s for s in list_schedules(DB_PATH) if s.get("aktiv")]
    except Exception:  # noqa: BLE001
        return []


def bericht_scheduler_enabled(cfg: dict | None = None) -> bool:
    cfg = cfg if cfg is not None else load_soc_cfg()
    if bool((cfg.get("berichte") or {}).get("scheduler_enabled")):
        return True
    # #1405: auch aktiv, wenn in der GUI Zeitpläne hinterlegt sind.
    return bool(_db_active_schedules())


def parse_bericht_schedule(cfg: dict | None = None) -> list[dict[str, Any]]:
    """Validiert + normalisiert ``berichte.schedule`` zu Job-Specs.

    Pro Eintrag: ``typ`` (Pflicht, gültiger Berichtstyp-Key), ``periode``
    (``quartal``|``jahr``, Default ``quartal``), ``cron`` (5-Feld-Crontab,
    Default '0 6 1 1,4,7,10 *' für quartalsweise), ``format`` (docx|pdf).
    Ungültige Einträge werden übersprungen (geloggt), nie geworfen.
    """
    cfg = cfg if cfg is not None else load_soc_cfg()
    ber = cfg.get("berichte") or {}
    from soc.berichte import BERICHT_TYPEN
    # Config-Schedule nur, wenn per Config aktiviert; GUI-DB-Schedules (#1405) immer.
    raw = (ber.get("schedule") or []) if ber.get("scheduler_enabled") else []
    if not isinstance(raw, list):
        raw = []
    specs: list[dict[str, Any]] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            log.warning("berichte.schedule[%d] ist kein Objekt — übersprungen", i)
            continue
        typ = (entry.get("typ") or "").strip()
        if typ not in BERICHT_TYPEN:
            log.warning("berichte.schedule[%d] unbekannter typ '%s' — übersprungen", i, typ)
            continue
        periode = (entry.get("periode") or "quartal").lower()
        if periode not in _VALID_PERIODEN:
            periode = "quartal"
        default_cron = "0 6 1 1,4,7,10 *" if periode == "quartal" else "0 7 1 1 *"
        cron = (entry.get("cron") or default_cron).strip()
        if len(cron.split()) != 5:
            log.warning("berichte.schedule[%d] cron '%s' kein 5-Feld-Crontab — übersprungen", i, cron)
            continue
        fmt = (entry.get("format") or "docx").lower()
        if fmt not in ("docx", "pdf"):
            fmt = "docx"
        specs.append({"typ": typ, "periode": periode, "cron": cron, "format": fmt,
                      "job_id": f"soc-bericht:{typ}:{periode}"})

    # #1405: GUI-Zeitpläne aus der DB (einfache Presets → Cron aus periode).
    from soc.berichte import BERICHT_TYPEN as _BT, PERIODE_CRON
    seen = {s["job_id"] for s in specs}
    for s in _db_active_schedules():
        typ = (s.get("typ") or "").strip()
        if typ not in _BT:
            continue
        periode = (s.get("periode") or "quartal").lower()
        if periode not in _VALID_PERIODEN:
            periode = "quartal"
        fmt = (s.get("format") or "docx").lower()
        if fmt not in ("docx", "pdf"):
            fmt = "docx"
        job_id = f"soc-bericht:{typ}:{periode}"
        if job_id in seen:
            continue
        seen.add(job_id)
        specs.append({"typ": typ, "periode": periode,
                      "cron": PERIODE_CRON.get(periode, "0 6 1 1,4,7,10 *"),
                      "format": fmt, "job_id": job_id})
    return specs


def run_scheduled_bericht(app, typ: str, periode: str, fmt: str) -> None:
    """Job-Callback: erzeugt + speichert den periodischen Bericht im App-Context."""
    from soc import berichte
    with app.app_context():
        if periode == "jahr":
            von, bis, label = berichte.year_range()
        else:
            von, bis, label = berichte.quarter_range()
        res = berichte.generate_and_store(
            DB_PATH, typ, von=von, bis=bis, fmt=fmt, periode=label, erzeugt_von="scheduler")
        if res.get("ok"):
            log.info("SOC-Bericht '%s' (%s) erzeugt: %s", typ, label, res.get("dateiname"))
        else:
            log.error("SOC-Bericht '%s' (%s) fehlgeschlagen: %s", typ, label, res.get("error"))


def register_soc_bericht_jobs(scheduler, app, cfg: dict | None = None) -> int:
    """Registriert die Berichts-Cron-Jobs am übergebenen APScheduler. Returns #Jobs."""
    from apscheduler.triggers.cron import CronTrigger
    specs = parse_bericht_schedule(cfg)
    n = 0
    for spec in specs:
        scheduler.add_job(
            run_scheduled_bericht,
            trigger=CronTrigger.from_crontab(spec["cron"], timezone="UTC"),
            args=[app, spec["typ"], spec["periode"], spec["format"]],
            id=spec["job_id"],
            replace_existing=True,
            misfire_grace_time=6 * 3600,
        )
        n += 1
        log.info("SOC-Berichts-Job registriert: %s/%s (%s)", spec["typ"], spec["periode"], spec["cron"])
    if n:
        log.info("SOC-Berichts-Scheduler: %d Job(s) registriert", n)
    return n
