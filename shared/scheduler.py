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

_scheduler = None        # APScheduler-Instanz (oder None)
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
    if not sync_cfg.get('scheduler_enabled'):
        log.info("In-App-Scheduler deaktiviert (sync.scheduler_enabled=false)")
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

    try:
        _JOBSTORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        jobstores = {'default': SQLAlchemyJobStore(url=f'sqlite:///{_JOBSTORE_PATH}')}
        sched = BackgroundScheduler(jobstores=jobstores, timezone='UTC')

        from cra.sync_scheduler import register_cra_sync_jobs
        n = register_cra_sync_jobs(sched, app, cfg)

        sched.start()
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
