"""Zentralisiertes Logging-Setup für die AI Compliance Suite."""
from __future__ import annotations

import json
import logging
import os
import stat
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: Path | None = None) -> None:
    """Konfiguriert RotatingFileHandler für strukturiertes Logging.

    Args:
        log_dir: Verzeichnis für log files. Standardwert: logs/ im CWD.
    """
    if log_dir is None:
        log_dir = Path("logs")

    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(log_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    except OSError:
        pass

    app_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=1_000_000,  # 1 MB
        backupCount=3,
        encoding="utf-8"
    )
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    app_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(app_handler)
    logger.setLevel(logging.WARNING)

    # ── Audit Logger (kritische Aktionen, INFO, JSON) ───────────────────────
    # Separater Logger verhindert, dass Audit-Events vom Root-Level (WARNING)
    # unterdrückt werden.
    audit_handler = RotatingFileHandler(
        log_dir / "audit.log",
        maxBytes=2_000_000,  # 2 MB
        backupCount=5,
        encoding="utf-8",
    )

    class _AuditJsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            msg = record.getMessage()
            # If msg already JSON, keep; else wrap.
            try:
                json.loads(msg)
                return msg
            except Exception:
                payload = {
                    "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": msg,
                }
                return json.dumps(payload, ensure_ascii=False)

    audit_handler.setFormatter(_AuditJsonFormatter())

    # Best-effort: restrict log file permissions (may not apply on Windows)
    for p in (log_dir / "app.log", log_dir / "audit.log"):
        try:
            if p.exists():
                os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    # Avoid duplicate handlers if configure_logging() called multiple times.
    if not any(isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "").endswith("audit.log") for h in audit_logger.handlers):
        audit_logger.addHandler(audit_handler)
