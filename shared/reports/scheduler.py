"""Generalisierter In-App-Scheduler für automatische Berichte je Modul (#1391).

Verallgemeinert den SOC-Berichts-Scheduler (``soc/bericht_scheduler.py``) auf alle
Module mit einem Berichts-Center (CRA, NIS2, AI-Act, DSGVO, Risikobewertung). Opt-in
pro Modul über ``<modul>.config.json → berichte``:

    {
      "berichte": {
        "scheduler_enabled": true,
        "schedule": [
          {"typ": "gesamt", "projekt": "Mein Produkt", "periode": "quartal",
           "cron": "0 6 1 1,4,7,10 *", "format": "pdf"}
        ]
      }
    }

Pro Eintrag wird ein Cron-Job registriert, der den Bericht über den *zuletzt
abgeschlossenen* Quartals- bzw. Jahres-Zeitraum erzeugt und über
``shared.reports.core.generate_and_store`` unter ``data/<modul>/berichte/`` ablegt
(Lauf-Historie wie bei manuellen Berichten). PDF fällt bei fehlendem Konverter auf
DOCX zurück (in ``generate_and_store`` gekapselt).

Muster (guarded Import, opt-in, von APScheduler unabhängige Parse-Logik)
übernommen vom SOC-Berichts-Scheduler, aus dem dieser hier hervorgegangen ist.
Das SOC-Modul selbst ist mit #1905 entfernt; dieser Scheduler bedient alle
übrigen Module.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

_VALID_PERIODEN = ("quartal", "jahr")
_VALID_FORMATE = ("docx", "pdf")

#: Modul-Key → (config-Dateiname, DB-Datei, berichte_provider-Importpfad).
#: DB-Datei ist der Schema-Selektor für die Historie (schema-per-Modul in PG).
MODULE_REPORTS: dict[str, tuple[str, str, str]] = {
    "cra": ("cra.config.json", "data/db/cra.sqlite", "cra.berichte_provider"),
    "nis2": ("nis2.config.json", "data/db/nis2.sqlite", "nis2.berichte_provider"),
    "aiact": ("ai_act.config.json", "data/db/ai_act.sqlite", "ai_act.berichte_provider"),
    "dsgvo": ("dsgvo.config.json", "data/db/dsgvo.sqlite", "dsgvo.berichte_provider"),
    "risikobewertung": ("risikobewertung.config.json", "data/db/risikobewertung.sqlite",
                         "risikobewertung.berichte_provider"),
}


def _load_cfg(cfg_file: str) -> dict[str, Any]:
    p = Path(cfg_file)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            log.warning("%s nicht lesbar — Berichts-Scheduler-Defaults", cfg_file)
    return {}


def _provider(import_path: str):
    import importlib
    return importlib.import_module(import_path)


def _valid_typen(provider) -> set[str]:
    try:
        cat = provider.catalog() if callable(getattr(provider, "catalog", None)) else []
        return {s.key for s in cat}
    except Exception:  # noqa: BLE001 — project-scoped Kataloge brauchen evtl. ein Projekt
        return set()


def report_scheduler_enabled() -> bool:
    """True, wenn mindestens ein Modul ``berichte.scheduler_enabled`` gesetzt hat."""
    for cfg_file, _db, _imp in MODULE_REPORTS.values():
        ber = (_load_cfg(cfg_file).get("berichte") or {})
        if bool(ber.get("scheduler_enabled")):
            return True
    return False


def parse_report_schedule() -> list[dict[str, Any]]:
    """Validiert + normalisiert alle Modul-Zeitpläne zu Job-Specs.

    Ungültige Einträge werden übersprungen (geloggt), nie geworfen.
    """
    specs: list[dict[str, Any]] = []
    for modul, (cfg_file, db_file, imp) in MODULE_REPORTS.items():
        ber = (_load_cfg(cfg_file).get("berichte") or {})
        if not ber.get("scheduler_enabled"):
            continue
        raw = ber.get("schedule") or []
        if not isinstance(raw, list):
            continue
        try:
            provider = _provider(imp)
        except Exception:  # noqa: BLE001
            log.warning("Berichts-Provider %s nicht importierbar — Modul %s übersprungen", imp, modul)
            continue
        typen = _valid_typen(provider)
        for i, entry in enumerate(raw):
            if not isinstance(entry, dict):
                log.warning("%s berichte.schedule[%d] kein Objekt — übersprungen", modul, i)
                continue
            typ = (entry.get("typ") or "").strip()
            if not typ or (typen and typ not in typen):
                log.warning("%s berichte.schedule[%d] unbekannter typ %r — übersprungen", modul, i, typ)
                continue
            periode = (entry.get("periode") or "quartal").lower()
            if periode not in _VALID_PERIODEN:
                periode = "quartal"
            default_cron = "0 6 1 1,4,7,10 *" if periode == "quartal" else "0 7 1 1 *"
            cron = (entry.get("cron") or default_cron).strip()
            if len(cron.split()) != 5:
                log.warning("%s berichte.schedule[%d] cron %r kein 5-Feld-Crontab — übersprungen",
                            modul, i, cron)
                continue
            fmt = (entry.get("format") or "docx").lower()
            if fmt not in _VALID_FORMATE:
                fmt = "docx"
            projekt = (entry.get("projekt") or "").strip()
            specs.append({
                "modul": modul, "db_file": db_file, "import_path": imp,
                "typ": typ, "projekt": projekt, "periode": periode, "cron": cron,
                "format": fmt,
                "job_id": f"report:{modul}:{typ}:{projekt or '-'}:{periode}",
            })
    return specs


def run_scheduled_report(app, *, modul: str, db_file: str, import_path: str,
                         typ: str, projekt: str, periode: str, fmt: str) -> None:
    """Job-Callback: erzeugt + speichert den periodischen Bericht im App-Context."""
    if app is None:
        from shared.scheduler import job_app
        app = job_app()
    from shared.reports import core
    with app.app_context():
        if periode == "jahr":
            von, bis, label = core.year_range()
        else:
            von, bis, label = core.quarter_range()
        try:
            render: Callable[..., bytes] = _provider(import_path).render
        except Exception:  # noqa: BLE001
            log.error("Berichts-Provider %s/%s ohne render — Job übersprungen", modul, typ)
            return
        res = core.generate_and_store(
            db_file, modul, typ, render, projekt=projekt, fmt=fmt,
            von=von, bis=bis, periode=label, erzeugt_von="scheduler")
        if res.get("ok"):
            log.info("Bericht %s/%s (%s) erzeugt: %s", modul, typ, label, res.get("dateiname"))
        else:
            log.error("Bericht %s/%s (%s) fehlgeschlagen: %s", modul, typ, label, res.get("error"))


def register_report_jobs(scheduler, app) -> int:
    """Registriert die generalisierten Berichts-Cron-Jobs. Returns #Jobs."""
    from apscheduler.triggers.cron import CronTrigger
    n = 0
    for spec in parse_report_schedule():
        scheduler.add_job(
            run_scheduled_report,
            trigger=CronTrigger.from_crontab(spec["cron"], timezone="UTC"),
            kwargs={
                # #1787: keine App in den Jobstore (nicht picklebar)
                "app": None, "modul": spec["modul"], "db_file": spec["db_file"],
                "import_path": spec["import_path"], "typ": spec["typ"],
                "projekt": spec["projekt"], "periode": spec["periode"], "fmt": spec["format"],
            },
            id=spec["job_id"],
            replace_existing=True,
            misfire_grace_time=6 * 3600,
        )
        n += 1
        log.info("Berichts-Job registriert: %s/%s/%s (%s)",
                 spec["modul"], spec["typ"], spec["periode"], spec["cron"])
    if n:
        log.info("Generalisierter Berichts-Scheduler: %d Job(s) registriert", n)
    return n
