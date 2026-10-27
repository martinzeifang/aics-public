"""In-Process-Scheduler für die AI Compliance Suite (#949, Story C).

Dünner Wrapper um APScheduler mit zwei Sicherheitsmechanismen:

1. **Guarded Import** — fehlt ``apscheduler``, wird der Scheduler still
   deaktiviert (App startet trotzdem).
2. **Singleton-File-Lock** — bei Multi-Worker-Setups (gunicorn) startet nur der
   Worker den Scheduler, der den exklusiven File-Lock bekommt. Die anderen
   no-op'en, damit Cron-Jobs nicht n-fach feuern.

Aktivierung ist **opt-in** über ``cra.config.json → sync.scheduler_enabled``.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

_scheduler = None

#: Die Flask-App für die Job-Funktionen.
#:
#: Sie darf NICHT als Job-Argument übergeben werden: Der Jobstore liegt seit
#: Migration #15 in Postgres, und SQLAlchemyJobStore **pickled** die Argumente.
#: Eine Flask-App enthält lokale Lambdas und ist nicht picklebar — der Versuch
#: endet in ``Can't pickle local object 'Flask.__init__.<locals>.<lambda>'``.
#: Das betraf jeden Job dieses Schedulers (#1787); aufgefallen ist es erst, als
#: mit der geplanten Sicherung zum ersten Mal überhaupt einer registriert wurde.
_job_app = None


def job_app():
    """Die App für eine laufende Job-Funktion (statt sie mitzupickeln)."""
    return _job_app        # APScheduler-Instanz (oder None)
_lock_fd = None          # offener Lock-FD (für Prozess-Lebensdauer gehalten)

_LOCK_PATH = Path('data/db/scheduler.lock')
_JOBSTORE_PATH = Path('data/db/scheduler.sqlite')


def _acquire_singleton_lock() -> bool:
    """Exklusiver, nicht-blockierender File-Lock. True = dieser Prozess führt.

    Nutzt ``fcntl.flock`` (POSIX). Auf Plattformen ohne fcntl (Windows) wird
    optimistisch True zurückgegeben (Einzelprozess-Annahme im Dev-Setup).
    """
    global _lock_fd
    try:
        import fcntl
    except ImportError:
        return True
    try:
        _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd = open(_LOCK_PATH, 'w')
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd = fd  # offen halten → Lock bleibt bis Prozessende
        return True
    except (OSError, BlockingIOError):
        return False


def start_scheduler(app, cfg: dict | None = None):
    """Startet den Scheduler, falls aktiviert + Lock erworben. Liefert die
    Instanz oder None."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    sync_cfg = ((cfg or {}).get('sync') or {})
    cra_enabled = bool(sync_cfg.get('scheduler_enabled'))
    soc_enabled = False
    try:
        from soc.sync_scheduler import soc_scheduler_enabled
        soc_enabled = soc_scheduler_enabled()
    except Exception:  # noqa: BLE001
        soc_enabled = False
    soc_bericht_enabled = False
    try:
        from soc.bericht_scheduler import bericht_scheduler_enabled
        soc_bericht_enabled = bericht_scheduler_enabled()
    except Exception:  # noqa: BLE001
        soc_bericht_enabled = False
    report_enabled = False  # #1391: generalisierte Modul-Berichts-Zeitpläne
    try:
        from shared.reports.scheduler import report_scheduler_enabled
        report_enabled = report_scheduler_enabled()
    except Exception:  # noqa: BLE001
        report_enabled = False
    # #1785: Die geplante Vollsicherung ist standardmäßig AN. Eine Sicherung,
    # die man erst einschalten muss, bleibt aus — auf der Produktivinstallation
    # lag zwischen der letzten Sicherung und ihrer Entdeckung ein halbes Jahr.
    # Damit startet der Scheduler künftig auf jeder Installation; abschalten
    # geht über backup.schedule_enabled=false.
    backup_enabled = False
    try:
        from shared.backup.zeitplan import zeitplan_aktiv
        backup_enabled = zeitplan_aktiv(cfg)
    except Exception:  # noqa: BLE001
        backup_enabled = False
    if not (cra_enabled or soc_enabled or soc_bericht_enabled or report_enabled
            or backup_enabled):
        log.info("In-App-Scheduler deaktiviert (CRA + SOC + Modul-Berichte + Sicherung aus)")
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    except ImportError:
        log.warning("apscheduler nicht installiert — In-App-Scheduler deaktiviert")
        return None

    if not _acquire_singleton_lock():
        log.info("Scheduler-Lock von anderem Worker gehalten — dieser Worker startet keinen Scheduler")
        return None

    global _job_app
    _job_app = app

    try:
        # Jobstore in Postgres (Migration #15), Schema "scheduler".
        from shared.db import connect as _pgc, database_url
        _pgc('scheduler').close()  # legt Schema "scheduler" idempotent an
        _pg_url = database_url().replace("postgresql://", "postgresql+psycopg://", 1)
        jobstores = {'default': SQLAlchemyJobStore(
            url=_pg_url, tableschema='scheduler', engine_options={'pool_pre_ping': True})}
        sched = BackgroundScheduler(jobstores=jobstores, timezone='UTC')
        # Angehalten starten, BEVOR Jobs angemeldet werden: Sonst sammelt
        # APScheduler sie und fügt sie erst beim ``start()`` in den Jobstore —
        # ein einziger nicht speicherbarer Job reißt dann den ganzen Start mit,
        # und mit ihm alle anderen Zeitpläne. So scheitert jeder Job für sich
        # in seinem eigenen ``try`` (#1787).
        sched.start(paused=True)

        from cra.sync_scheduler import register_cra_sync_jobs
        n = register_cra_sync_jobs(sched, app, cfg)
        try:
            from soc.sync_scheduler import register_soc_sync_jobs
            n += register_soc_sync_jobs(sched, app)
        except Exception:  # noqa: BLE001
            log.exception("SOC-Scheduler-Registrierung fehlgeschlagen")
        try:
            from soc.bericht_scheduler import register_soc_bericht_jobs
            n += register_soc_bericht_jobs(sched, app)
        except Exception:  # noqa: BLE001
            log.exception("SOC-Berichts-Scheduler-Registrierung fehlgeschlagen")
        try:
            from shared.reports.scheduler import register_report_jobs
            n += register_report_jobs(sched, app)  # #1391: CRA/NIS2/AI-Act/DSGVO/RB
        except Exception:  # noqa: BLE001
            log.exception("Generalisierter Berichts-Scheduler-Registrierung fehlgeschlagen")
        try:
            from shared.backup.zeitplan import register_backup_job
            n += register_backup_job(sched, app, cfg)  # #1785: Vollsicherung
        except Exception:  # noqa: BLE001
            log.exception("Registrierung der geplanten Sicherung fehlgeschlagen")

        sched.resume()
        _scheduler = sched
        log.info("In-App-Scheduler gestartet mit %d Job(s)", n)
        return sched
    except Exception:
        log.exception("Scheduler-Start fehlgeschlagen")
        return None


def stop_scheduler() -> None:
    global _scheduler, _lock_fd
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            log.exception("Scheduler-Shutdown fehlgeschlagen")
        _scheduler = None
    if _lock_fd is not None:
        try:
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None
