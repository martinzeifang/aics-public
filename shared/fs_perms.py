"""Best-effort filesystem permission hardening helpers (POSIX).

Used for export artifacts (Risk #207) and other generated files.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path


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


def ensure_private_dirs(paths: list[Path]) -> None:
    """Ensure a set of directories exist with private perms (best-effort)."""
    for p in paths:
        try:
            ensure_private_dir(Path(p))
        except Exception:
            # best-effort: never break app startup
            pass
