"""In-App-Scheduler für den SOC-PULL-Sync (#1262).

Opt-in über ``soc.config.json → sync``:
- ``scheduler_enabled``: true
- entweder ``interval_minutes`` (einfaches Intervall) ODER
  ``schedule``: ``[{"connection": "default", "cron": "*/10 * * * *"}]``

Die Parse-Logik ist von APScheduler unabhängig (testbar). Registrierung wird vom
geteilten ``shared.scheduler`` aufgerufen (guarded).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def load_soc_cfg() -> dict[str, Any]:
    p = Path("soc.config.json")
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            log.warning("soc.config.json nicht lesbar — Scheduler-Defaults")
    return {}


def soc_scheduler_enabled(cfg: dict | None = None) -> bool:
    cfg = cfg if cfg is not None else load_soc_cfg()
    sync = cfg.get("sync") or {}
    # Alarm-Pull ODER Schwachstellen-Sync (#1343) aktiviert den In-App-Scheduler.
    return bool(sync.get("scheduler_enabled") or sync.get("vuln_scheduler_enabled"))


def parse_soc_schedule(cfg: dict | None = None) -> list[dict[str, Any]]:
    """Normalisiert die Konfiguration zu Job-Specs ``[{connection, trigger, value}]``."""
    cfg = cfg if cfg is not None else load_soc_cfg()
    sync = cfg.get("sync") or {}
    if not sync.get("scheduler_enabled"):
        return []
    specs: list[dict[str, Any]] = []
    schedule = sync.get("schedule") or []
    if isinstance(schedule, list) and schedule:
        for i, s in enumerate(schedule):
            if not isinstance(s, dict) or not s.get("cron"):
                log.warning("soc sync.schedule[%d] ungültig — übersprungen", i)
                continue
            cron = str(s["cron"]).split()
            if len(cron) != 5:
                log.warning("soc sync.schedule[%d] cron kein 5-Feld-Crontab — übersprungen", i)
                continue
            specs.append({"connection": s.get("connection", "default"),
                          "trigger": "cron", "value": s["cron"]})
    elif sync.get("interval_minutes"):
        try:
            mins = int(sync["interval_minutes"])
            if mins > 0:
                specs.append({"connection": sync.get("connection", "default"),
                              "trigger": "interval", "value": mins})
        except (TypeError, ValueError):
            log.warning("soc sync.interval_minutes ungültig")
    return specs


def parse_soc_vuln_schedule(cfg: dict | None = None) -> list[dict[str, Any]]:
    """Schwachstellen-Sync-Schedule (#1343) — eigener, seltenerer Job (Default täglich).

    Opt-in über ``sync.vuln_scheduler_enabled``. Konfigurierbar über
    ``sync.vuln_schedule`` (``[{connection, cron}]``) ODER ``sync.vuln_cron``
    (einzelner 5-Feld-Crontab). Fällt ohne Angabe auf täglich 04:30 UTC zurück.
    """
    cfg = cfg if cfg is not None else load_soc_cfg()
    sync = cfg.get("sync") or {}
    if not sync.get("vuln_scheduler_enabled"):
        return []
    specs: list[dict[str, Any]] = []
    schedule = sync.get("vuln_schedule") or []
    if isinstance(schedule, list) and schedule:
        for i, s in enumerate(schedule):
            if not isinstance(s, dict) or not s.get("cron"):
                log.warning("soc sync.vuln_schedule[%d] ungültig — übersprungen", i)
                continue
            if len(str(s["cron"]).split()) != 5:
                log.warning("soc sync.vuln_schedule[%d] cron kein 5-Feld-Crontab — übersprungen", i)
                continue
            specs.append({"connection": s.get("connection", "default"), "cron": s["cron"]})
    else:
        cron = str(sync.get("vuln_cron") or "30 4 * * *")
        if len(cron.split()) != 5:
            log.warning("soc sync.vuln_cron kein 5-Feld-Crontab — Default 04:30 UTC")
            cron = "30 4 * * *"
        specs.append({"connection": sync.get("connection", "default"), "cron": cron})
    return specs


def run_soc_pull(app, connection_name: str = "default") -> None:
    from soc import ingest
    try:
        with app.app_context():
            res = ingest.run_pull(Path("data/db/soc.sqlite"), connection_name)
        log.info("SOC-Scheduler-Pull '%s': %s", connection_name, res)
    except Exception:  # noqa: BLE001
        log.exception("SOC-Scheduler-Pull '%s' fehlgeschlagen", connection_name)


def run_soc_vuln_sync(app, connection_name: str = "default") -> None:
    """Eigener, seltenerer Schwachstellen-Sync-Lauf (#1343) — getrennt vom Alarm-Pull."""
    from soc import ingest
    try:
        with app.app_context():
            res = ingest.run_vuln_sync(Path("data/db/soc.sqlite"), connection_name)
        log.info("SOC-Scheduler-Vuln-Sync '%s': %s", connection_name, res)
    except Exception:  # noqa: BLE001
        log.exception("SOC-Scheduler-Vuln-Sync '%s' fehlgeschlagen", connection_name)


def register_soc_sync_jobs(scheduler, app, cfg: dict | None = None) -> int:
    """Registriert die SOC-Pull- + Vuln-Sync-Jobs am übergebenen APScheduler. Returns #Jobs."""
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    specs = parse_soc_schedule(cfg)
    n = 0
    for spec in specs:
        conn = spec["connection"]
        if spec["trigger"] == "cron":
            trig = CronTrigger.from_crontab(spec["value"], timezone="UTC")
        else:
            trig = IntervalTrigger(minutes=int(spec["value"]))
        scheduler.add_job(run_soc_pull, trig, args=[app, conn],
                          id=f"soc_pull_{conn}", replace_existing=True)
        n += 1
    # Schwachstellen-Sync: eigener, seltenerer Job (#1343)
    for spec in parse_soc_vuln_schedule(cfg):
        conn = spec["connection"]
        trig = CronTrigger.from_crontab(spec["cron"], timezone="UTC")
        scheduler.add_job(run_soc_vuln_sync, trig, args=[app, conn],
                          id=f"soc_vuln_sync_{conn}", replace_existing=True)
        n += 1
    if n:
        log.info("SOC-Scheduler: %d Job(s) registriert", n)
    return n
