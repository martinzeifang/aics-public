"""C3 In-App-Scheduler — Job-Registrierung für den Vulnerability-Sync (#949, Story C).

Liest ``cra.config.json → sync.schedule`` und registriert pro Eintrag einen
Cron-Job, der :func:`cra.vuln_sync.sync_vulns` ausführt. Die reine Spec-Parsing-
Logik (:func:`parse_schedule_config`) ist von APScheduler unabhängig und damit
testbar; die Registrierung (:func:`register_cra_sync_jobs`) braucht einen
Scheduler.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def parse_schedule_config(cfg: dict | None) -> list[dict[str, Any]]:
    """Validiert + normalisiert ``sync.schedule`` zu Job-Specs.

    Akzeptiert pro Eintrag: ``projekt`` (Pflicht), ``cron`` (5-Felder-Crontab,
    Default '0 4 * * *'), ``source`` (github|gitlab|all, Default 'all').
    Ungültige Einträge werden übersprungen (geloggt), nie geworfen.
    """
    sync = ((cfg or {}).get('sync') or {})
    raw = sync.get('schedule') or []
    if not isinstance(raw, list):
        return []
    specs: list[dict[str, Any]] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            log.warning("sync.schedule[%d] ist kein Objekt — übersprungen", i)
            continue
        projekt = (entry.get('projekt') or '').strip()
        if not projekt:
            log.warning("sync.schedule[%d] ohne 'projekt' — übersprungen", i)
            continue
        cron = (entry.get('cron') or '0 4 * * *').strip()
        if len(cron.split()) != 5:
            log.warning("sync.schedule[%d] cron '%s' ist kein 5-Feld-Crontab — übersprungen", i, cron)
            continue
        source = (entry.get('source') or 'all').lower()
        if source not in ('github', 'gitlab', 'all'):
            source = 'all'
        specs.append({'projekt': projekt, 'cron': cron, 'source': source,
                      'job_id': f'cra-vuln-sync:{projekt}'})
    return specs


def run_scheduled_sync(app, projekt: str, source: str) -> None:
    """Job-Callback: führt den Sync im App-Context aus (#949)."""
    from cra.vuln_sync import sync_vulns
    from cra.db import start_sync_run, finish_sync_run, get_running_sync_run
    db_path = Path('data/db/cra.sqlite')
    with app.app_context():
        if get_running_sync_run(db_path, projekt):
            log.info("Scheduler: Sync für %s läuft bereits — übersprungen", projekt)
            return
        run_id = start_sync_run(db_path, projekt)
        try:
            sources = ('github', 'gitlab') if source == 'all' else (source,)
            report = sync_vulns(db_path, projekt, sources=sources)
            finish_sync_run(db_path, run_id, 'finished', report)
            log.info("Scheduler-Sync %s fertig: %s", projekt, report)
        except Exception as e:  # noqa: BLE001
            finish_sync_run(db_path, run_id, 'failed', {'error': str(e)})
            log.exception("Scheduler-Sync %s fehlgeschlagen", projekt)


def register_cra_sync_jobs(scheduler, app, cfg: dict | None) -> int:
    """Registriert die Cron-Jobs am Scheduler. Liefert die Anzahl Jobs."""
    from apscheduler.triggers.cron import CronTrigger
    specs = parse_schedule_config(cfg)
    count = 0
    for spec in specs:
        scheduler.add_job(
            run_scheduled_sync,
            trigger=CronTrigger.from_crontab(spec['cron']),
            args=[app, spec['projekt'], spec['source']],
            id=spec['job_id'],
            replace_existing=True,
            misfire_grace_time=3600,
        )
        count += 1
        log.info("CRA-Sync-Job registriert: %s (%s)", spec['projekt'], spec['cron'])
    return count
