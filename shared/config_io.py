"""Sicheres Laden/Speichern von JSON-Konfigurationen.

Ziele (Risk #201):
- restriktive Dateirechte (best-effort, plattformabhängig)
- atomisches Schreiben (tmp + replace)
- Audit-Logging über Änderungen (Hash)
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
import os
import stat
import time
from pathlib import Path
from typing import Any

from shared.audit import audit_event

log = logging.getLogger(__name__)

# fcntl ist POSIX-only — Windows-Dev: kein Lock (Container immer POSIX)
try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore


@contextlib.contextmanager
def _file_lock(lock_path: Path, exclusive: bool = True, timeout: float = 5.0):
    """Inter-process Lock via fcntl.flock auf einem dedizierten Lock-File.

    Verhindert dass mehrere Gunicorn-Worker gleichzeitig Config-File und
    Sidecar in inkonsistente Zustände bringen (#357 reopen).
    """
    if fcntl is None:
        yield  # Windows / no-op
        return
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flag = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    deadline = time.time() + timeout
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        while True:
            try:
                fcntl.flock(fd, flag | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() >= deadline:
                    raise TimeoutError(f"Could not acquire config lock within {timeout}s: {lock_path}")
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# #742: HMAC-basierte Integritätssicherung (keyed) statt nacktem SHA-256.
# Ein Angreifer mit Schreibzugriff auf Config + Sidecar kann ohne den Schlüssel
# keinen gültigen Sidecar-Wert fälschen. Schlüssel: AICS_CONFIG_HMAC_KEY →
# AICS_AT_REST_KEY → JWT_SECRET_KEY (eine davon ist im Betrieb gesetzt).
_HMAC_PREFIX = "hmac-sha256:"


def _integrity_key() -> bytes | None:
    for name in ("AICS_CONFIG_HMAC_KEY", "AICS_AT_REST_KEY", "JWT_SECRET_KEY"):
        v = (os.environ.get(name) or "").strip()
        if v:
            return v.encode("utf-8")
    return None


def _compute_sidecar_value(payload: bytes) -> str:
    """Bevorzugt HMAC (wenn Schlüssel vorhanden), sonst plain SHA-256 (Fallback)."""
    key = _integrity_key()
    if key:
        return _HMAC_PREFIX + hmac.new(key, payload, hashlib.sha256).hexdigest()
    return _sha256_bytes(payload)


def _verify_sidecar_value(payload: bytes, stored: str) -> bool:
    """Prüft `payload` gegen einen gespeicherten Sidecar-Wert (HMAC oder SHA-256).

    HMAC-Sidecars erfordern den korrekten Schlüssel (Tamper-/Forge-Schutz).
    Bare SHA-256-Sidecars werden für Bestandsdaten weiterhin akzeptiert
    (Migration) und beim nächsten Save automatisch auf HMAC angehoben.
    """
    stored = (stored or "").strip()
    if stored.startswith(_HMAC_PREFIX):
        key = _integrity_key()
        if not key:
            return False  # HMAC-Sidecar, aber kein Schlüssel → kann nicht verifizieren
        expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, stored[len(_HMAC_PREFIX):])
    # Legacy plain-SHA256-Sidecar (Bestand) — konstantzeit-Vergleich.
    return hmac.compare_digest(_sha256_bytes(payload), stored)


def _best_effort_chmod_0600(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        log.warning("Konnte restriktive Dateirechte (0600) nicht setzen für %s", path,
                    exc_info=True)


def _is_posix() -> bool:
    return os.name == "posix"


def _best_effort_reject_insecure_permissions(path: Path) -> None:
    """Handle group/world-writable config files (POSIX only).

    Default behavior: try to auto-fix to 0600 (best-effort) and continue.
    Fail-closed behavior can be enabled via env var AICS_CONFIG_ENFORCE_PERMS=1.
    """
    if not _is_posix():
        return
    try:
        mode = path.stat().st_mode
    except OSError:
        return
    if (mode & stat.S_IWGRP) or (mode & stat.S_IWOTH):
        # Try to auto-fix
        _best_effort_chmod_0600(path)
        try:
            mode2 = path.stat().st_mode
        except OSError:
            mode2 = mode
        still_insecure = (mode2 & stat.S_IWGRP) or (mode2 & stat.S_IWOTH)
        if still_insecure and os.environ.get("AICS_CONFIG_ENFORCE_PERMS", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise PermissionError(f"Insecure config permissions (group/world-writable): {path}")
        if still_insecure:
            audit_event(
                "config.perms",
                module="config",
                outcome="warn",
                details={"path": str(path), "note": "config is group/world-writable; could not auto-fix"},
            )


def _sidecar_path(cfg_path: Path) -> Path:
    return cfg_path.with_suffix(cfg_path.suffix + ".sha256")


def _read_sidecar_sha256(sidecar: Path) -> str:
    return sidecar.read_text(encoding="utf-8").strip().split()[0]


def safe_load_json_config(path: Path) -> dict[str, Any]:
    """Load config as dict and emit audit event.

    Raises ValueError if root is not a JSON object.

    #357 reopen: Lese-Lock (shared) verhindert TOCTOU mit gleichzeitigen Saves.
    """
    _best_effort_reject_insecure_permissions(path)

    lock_path = path.with_suffix(path.suffix + ".lock")
    with _file_lock(lock_path, exclusive=False):
        raw = path.read_bytes()
        h = _sha256_bytes(raw)

        sidecar = _sidecar_path(path)
        if sidecar.exists():
            expected = _read_sidecar_sha256(sidecar)
            if not _verify_sidecar_value(raw, expected):
                # #742: Standardmäßig FAIL-CLOSED. Bei Manipulation der Config
                # (oder des HMAC-Sidecars) wird das Laden verweigert, statt das
                # Sidecar still nachzuziehen. Auto-Repair ist nur noch ein
                # explizites Opt-IN (z.B. nach legitimem Backup-Restore).
                env_raw = os.environ.get("AICS_CONFIG_AUTO_REPAIR_SIDECAR", "").strip().lower()
                auto_repair = env_raw in {"1", "true", "yes", "on"}
                if auto_repair:
                    try:
                        sidecar.write_text(_compute_sidecar_value(raw) + "\n", encoding="utf-8")
                        _best_effort_chmod_0600(sidecar)
                        audit_event(
                            "config.load",
                            module="config",
                            outcome="repaired",
                            details={
                                "path": str(path),
                                "sha256": h,
                                "stale_expected": expected,
                                "note": "sidecar regenerated due to mismatch (auto-repair opt-in)",
                            },
                        )
                    except OSError as exc:
                        audit_event(
                            "config.load",
                            module="config",
                            outcome="fail",
                            details={"path": str(path), "error": f"sidecar-rewrite: {exc}"},
                        )
                        raise ValueError(
                            f"Config integrity check failed and sidecar repair failed: {path}\n"
                            f"OS error: {exc}\n"
                            f"Hilfe: Bitte die Schreibrechte auf das Sidecar prüfen oder die Datei "
                            f"{sidecar.name} manuell löschen — sie wird beim nächsten Start neu erzeugt."
                        ) from exc
                else:
                    audit_event(
                        "config.load",
                        module="config",
                        outcome="fail",
                        details={"path": str(path), "sha256": h, "expected_sidecar": expected},
                    )
                    raise ValueError(
                        f"Config integrity check failed (sidecar mismatch): {path}\n"
                        f"Die Config (oder ihr Integritäts-Sidecar) wurde außerhalb der Anwendung verändert.\n"
                        f"Die Suite startet aus Sicherheitsgründen NICHT (fail-closed).\n"
                        f"Hilfe: Bei legitimer Änderung (z.B. Backup-Restore) "
                        f"AICS_CONFIG_AUTO_REPAIR_SIDECAR=1 setzen oder {sidecar.name} löschen "
                        f"— das Sidecar wird dann beim nächsten Start neu erzeugt."
                    )

    audit_event("config.load", module="config", outcome="success", details={"path": str(path), "sha256": h})

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        audit_event("config.load", module="config", outcome="fail", details={"path": str(path), "error": str(exc)})
        raise

    if not isinstance(data, dict):
        raise ValueError("Config root must be a JSON object")
    return data


def safe_save_json_config(path: Path, cfg: dict[str, Any]) -> None:
    """Atomisch speichern + restriktive Rechte.

    #357 reopen: Exklusiver Lock + Sidecar-FIRST-Reihenfolge verhindert
    TOCTOU-Window zwischen file und sidecar. Vorher konnte ein Reader die
    NEUE file lesen während noch der ALTE sidecar daneben stand → sha256-Mismatch.

    Neuer Ablauf unter Lock:
      1. Sidecar atomic schreiben (alter Reader sieht alten file + alten sidecar = ok)
      2. File atomic schreiben (neuer Reader sieht neuen file + neuen sidecar = ok)
      Window collapsed: kein konsistenter "neuer file + alter sidecar"-Zustand.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = (json.dumps(cfg, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    h = _sha256_bytes(payload)
    sidecar_value = _compute_sidecar_value(payload)  # #742: HMAC wenn Schlüssel da

    lock_path = path.with_suffix(path.suffix + ".lock")
    tmp = path.with_suffix(path.suffix + ".tmp")
    sidecar = _sidecar_path(path)
    sidecar_tmp = sidecar.with_suffix(sidecar.suffix + ".tmp")

    # #357/#742: Reader nehmen einen SHARED-Lock und sehen daher nie einen
    # Zwischenzustand. Unter dem exklusiven Write-Lock schreiben wir erst die
    # Datei, dann das Sidecar — beide atomar via tmp+replace.
    with _file_lock(lock_path, exclusive=True):
        # 1) File atomar schreiben
        old_mask = os.umask(0o077)
        try:
            tmp.write_bytes(payload)
        finally:
            os.umask(old_mask)
        _best_effort_chmod_0600(tmp)
        tmp.replace(path)
        _best_effort_chmod_0600(path)

        # 2) Sidecar atomar schreiben (passend zum neuen File)
        old_mask = os.umask(0o077)
        try:
            sidecar_tmp.write_text(sidecar_value + "\n", encoding="utf-8")
        finally:
            os.umask(old_mask)
        _best_effort_chmod_0600(sidecar_tmp)
        sidecar_tmp.replace(sidecar)
        _best_effort_chmod_0600(sidecar)

    audit_event("config.save", module="config", outcome="success", details={"path": str(path), "sha256": h})
