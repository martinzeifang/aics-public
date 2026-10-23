"""Zeitplan-Jobs müssen in den Jobstore passen (#1787).

Der Jobstore liegt seit Migration #15 in PostgreSQL. ``SQLAlchemyJobStore``
**pickelt** jeden Job samt seiner Argumente. Eine Flask-App enthält lokale
Lambdas und übersteht das nicht:

    AttributeError: Can't pickle local object 'Flask.__init__.<locals>.<lambda>'

Jede Job-Registrierung dieses Schedulers übergab die App als Argument — CRA-Sync,
SOC-Pull, SOC-Schwachstellen, SOC-Berichte, Modul-Berichte. Damit war der
In-App-Scheduler seit der Postgres-Migration vollständig funktionsunfähig.
Gemerkt hat es niemand, weil alle Zeitpläne standardmäßig abgeschaltet sind und
nie einer registriert wurde. Erst die geplante Sicherung (#1785) meldete als
erster Job überhaupt einen an — und riss beim Start den ganzen Scheduler mit,
weil APScheduler angemeldete Jobs gesammelt erst in ``start()`` in den Jobstore
schreibt.

Zwei Zusagen hält dieses Modul fest: In den Job-Argumenten steckt nichts
Unpickelbares, und ein einzelner untauglicher Job nimmt die anderen Zeitpläne
nicht mit.
"""
from __future__ import annotations

import pickle

import pytest


class _JobSammler:
    """Nimmt ``add_job``-Aufrufe entgegen, ohne APScheduler zu brauchen."""

    def __init__(self):
        self.jobs = []

    def add_job(self, func, trigger=None, args=None, kwargs=None, **_rest):
        self.jobs.append({"func": func, "args": list(args or []),
                          "kwargs": dict(kwargs or {})})


def _flask_app():
    from flask import Flask

    return Flask(__name__)


def test_flask_app_ist_wirklich_nicht_picklebar():
    """Die Annahme, auf der alles andere beruht."""
    with pytest.raises(Exception):
        pickle.dumps(_flask_app())


def test_sicherungs_job_traegt_nichts_unpickelbares():
    from shared.backup.zeitplan import register_backup_job

    sammler = _JobSammler()
    anzahl = register_backup_job(sammler, _flask_app(), {})

    assert anzahl == 1
    for job in sammler.jobs:
        pickle.dumps(job["args"])
        pickle.dumps(job["kwargs"])


def test_kein_zeitplan_schiebt_die_app_in_den_jobstore():
    """Gegenprobe über alle Registrierungen, die der Scheduler kennt.

    Ein neuer Zeitplan, der die App wieder mitgibt, lässt diesen Test rot
    werden — nicht erst die Produktionsinstallation beim nächsten Neustart.
    """
    app = _flask_app()
    sammler = _JobSammler()

    from cra.sync_scheduler import register_cra_sync_jobs

    cfg = {"sync": {"schedule": [{"projekt": "P", "cron": "0 4 * * *"}]}}
    register_cra_sync_jobs(sammler, app, cfg)

    from shared.backup.zeitplan import register_backup_job
    register_backup_job(sammler, app, {})

    assert sammler.jobs, "Testaufbau meldet keine Jobs an"
    for job in sammler.jobs:
        for wert in list(job["args"]) + list(job["kwargs"].values()):
            assert not _ist_flask(wert), (
                f"{job['func']!r} gibt die Flask-App mit — der Jobstore pickelt sie")
        pickle.dumps(job["args"])
        pickle.dumps(job["kwargs"])


def _ist_flask(wert) -> bool:
    return type(wert).__module__.startswith("flask") or type(wert).__name__ == "Flask"


def test_job_funktionen_holen_die_app_selbst():
    """Mit ``None`` als erstem Argument müssen sie die App finden."""
    import shared.scheduler as sch

    app = _flask_app()
    alt = sch._job_app
    sch._job_app = app
    try:
        assert sch.job_app() is app
    finally:
        sch._job_app = alt
