"""SQLite File Security Helpers.

Risk #208 baseline mitigations:
- Best-effort restrictive permissions for DB directories/files (POSIX)
- Optional path containment (workspace root) when DB path is app-controlled
- Audit logging for DB open operations

Note: This does not encrypt SQLite at rest.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path

from shared.audit import audit_event
from security_utils import safe_generated_file, workspace_root_from


def _is_posix() -> bool:
    return os.name == "posix"


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if not _is_posix():
        return
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    except OSError:
        pass


def ensure_private_file(path: Path) -> None:
    if not _is_posix():
        return
    try:
        if path.exists():
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _harden_sqlite_sidecars(db_path: Path) -> None:
    # WAL/SHM created depending on journal_mode.
    for suffix in ("-wal", "-shm"):
        ensure_private_file(Path(str(db_path) + suffix))


def connect_sqlite(
    db_path: Path,
    *,
    timeout: int = 30,
    anchor: Path | None = None,
    read_only: bool = False,
    harden_fs: bool = True,
) -> sqlite3.Connection:
    """Open sqlite connection with best-effort file hardening.

    If anchor is provided, db_path is treated as app-generated output and
    is restricted to the workspace root.
    """
    db_path = Path(db_path)
    if anchor is not None:
        db_path = safe_generated_file(db_path, workspace_root_from(anchor))

    if harden_fs:
        ensure_private_dir(db_path.parent)

    # Best-effort: create/connect with restrictive umask
    old_mask = os.umask(0o077)
    try:
        if read_only:
            uri = f"file:{db_path.as_posix()}?mode=ro"
            con = sqlite3.connect(uri, timeout=timeout, uri=True)
        else:
            con = sqlite3.connect(str(db_path), timeout=timeout)
    finally:
        os.umask(old_mask)

    if harden_fs:
        ensure_private_file(db_path)
        _harden_sqlite_sidecars(db_path)

    audit_event(
        "db.open",
        module="db",
        outcome="success",
        details={"path": str(db_path), "read_only": bool(read_only)},
    )
    return con
