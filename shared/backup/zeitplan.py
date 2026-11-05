"""Sicherung nach Zeitplan (#1785).

WARUM DAS DAZUGEHÖRT
Eine Backup-Funktion, die nur auf Knopfdruck läuft, ist nach kurzer Zeit keine
Sicherung mehr. Der Befund, der dieses Paket ausgelöst hat, sah auf der
Produktivinstallation so aus: letzte Sicherung 11. Mai, Prüfzeitpunkt 23.
Oktober — fünfeinhalb Monate, in denen niemand den Knopf gedrückt hat. Das ist
kein Versäumnis einzelner Personen, sondern die erwartbare Folge einer Aufgabe
ohne Termin.

Der Zeitplan ist bewusst **an**, sobald der Scheduler läuft, und muss nicht
eingeschaltet werden: Eine abgeschaltete Sicherung ist der Normalfall, den man
später bereut. Abschalten geht über ``backup.schedule_enabled = false``.

AUFBEWAHRUNG
``backup.backup_retention_count`` (Standard 5) gilt für die turnusmäßigen
Sicherungen. Sicherheitskopien vor einer Wiederherstellung zählen nicht mit —
sie sind der Rückweg aus einem misslungenen Restore und dürfen nicht von der
nächsten Nachtsicherung verdrängt werden.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

#: Nachts um 2, wenn niemand arbeitet und die Datenbank ruhig ist.
STANDARD_CRON = "0 2 * * *"

BACKUP_DIR = Path("out/backup")


def zeitplan_aktiv(cfg: dict | None = None) -> bool:
    cfg = cfg if cfg is not None else _config()
    bk = (cfg or {}).get("backup") or {}
    return bool(bk.get("schedule_enabled", True))


def cron_ausdruck(cfg: dict | None = None) -> str:
    cfg = cfg if cfg is not None else _config()
    roh = str(((cfg or {}).get("backup") or {}).get("schedule_cron") or "").strip()
    if len(roh.split()) == 5:
        return roh
    if roh:
        log.warning("backup.schedule_cron '%s' ist kein 5-Feld-Crontab — Standard greift", roh)
    return STANDARD_CRON


def _config() -> dict[str, Any]:
    try:
        from ai_compliance_suite.config import load_config

        return load_config() or {}
    except Exception:  # noqa: BLE001
        return {}


def sicherung_ausfuehren(app: Any = None) -> dict[str, Any] | None:
    """Eine turnusmäßige Sicherung schreiben. Wirft nie — der Job darf nicht sterben.

    ``app`` ist optional und wird vom Zeitplan **nicht** mitgegeben: Der Jobstore
    liegt in Postgres und pickelt die Argumente, eine Flask-App übersteht das
    nicht (#1787). Gebraucht wird sie hier ohnehin nicht — die Sicherung läuft
    über ``shared.db`` und die Konfigurationsdatei, beides ohne Flask.
    """
    from shared.backup import erstelle_backup

    ziel = BACKUP_DIR / f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}_auto.zip'
    try:
        if app is not None:
            with app.app_context():
                manifest = erstelle_backup(ziel, erstellt_von="Zeitplan")
        else:
            manifest = erstelle_backup(ziel, erstellt_von="Zeitplan")
    except Exception:  # noqa: BLE001
        log.exception("Geplante Sicherung fehlgeschlagen")
        _melde("admin.backup.schedule_failed", {})
        return None

    _aufraeumen()
    log.info("Geplante Sicherung: %s (%d Tabellen, %d Zeilen, %d Dateien, %d Bytes)",
             ziel.name, manifest["datenbank"]["tabellen"], manifest["datenbank"]["zeilen"],
             manifest["dateien"]["anzahl"], manifest.get("groesse_bytes", 0))
    _melde("admin.backup.created", {
        "backup_id": ziel.stem,
        "quelle": "zeitplan",
        "tabellen": manifest["datenbank"]["tabellen"],
        "zeilen": manifest["datenbank"]["zeilen"],
        "dateien": manifest["dateien"]["anzahl"],
        "size_bytes": manifest.get("groesse_bytes", 0),
        "user_id": "system",
    })
    return manifest


def _melde(aktion: str, details: dict[str, Any]) -> None:
    try:
        from shared.audit import audit_event

        audit_event(aktion, module="admin", details={"user_id": "system", **details})
    except Exception:  # noqa: BLE001
        pass


def _aufraeumen() -> None:
    """Nur die turnusmäßigen Sicherungen nach Anzahl begrenzen."""
    cfg = _config()
    try:
        behalten = int((cfg.get("backup") or {}).get("backup_retention_count", 5))
    except (TypeError, ValueError):
        return
    if behalten <= 0:
        return
    archive = sorted(
        (p for p in BACKUP_DIR.glob("backup_*.zip")),
        key=lambda p: p.stat().st_mtime, reverse=True)
    for alt in archive[behalten:]:
        try:
            alt.unlink()
            log.info("Alte Sicherung entfernt: %s", alt.name)
        except OSError:
            pass


def register_backup_job(sched: Any, app: Any, cfg: dict | None = None) -> int:
    """Den Sicherungs-Job beim Scheduler anmelden. Liefert die Zahl der Jobs."""
    if not zeitplan_aktiv(cfg):
        log.info("Geplante Sicherung ist abgeschaltet (backup.schedule_enabled=false)")
        return 0
    from apscheduler.triggers.cron import CronTrigger

    cron = cron_ausdruck(cfg)
    sched.add_job(
        sicherung_ausfuehren,
        CronTrigger.from_crontab(cron, timezone="UTC"),
        args=[],  # #1787: die App ist nicht picklebar
        id="backup_vollsicherung",
        name="Vollständige Sicherung",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
        coalesce=True,
    )
    log.info("Geplante Sicherung angemeldet: %s (UTC)", cron)
    return 1
