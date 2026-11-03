"""CLI-Validierung (OWASP / Risk #206).

Diese Utilities validieren Eingaben für CLI-Kommandos (Pfade, Integer-Grenzen,
Strings) und nutzen sicherheitsrelevante Helfer aus security_utils.
"""

from __future__ import annotations

from pathlib import Path

from security_utils import safe_generated_dir, safe_generated_file, workspace_root_from


def _root(anchor: Path) -> Path:
    return workspace_root_from(anchor)


def require_existing_dir(path: Path, *, field: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ValueError(f"{field} ist kein existierender Ordner: {p}")
    return p


def require_existing_file(path: Path, *, field: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise ValueError(f"{field} ist keine existierende Datei: {p}")
    return p


def require_safe_out_dir(path: Path, *, field: str, anchor: Path) -> Path:
    r = _root(anchor)
    p = Path(path).expanduser()
    safe = safe_generated_dir(p, r)
    safe.mkdir(parents=True, exist_ok=True)
    return safe


def require_safe_file(path: Path, *, field: str, anchor: Path) -> Path:
    r = _root(anchor)
    p = Path(path).expanduser()
    safe = safe_generated_file(p, r)
    safe.parent.mkdir(parents=True, exist_ok=True)
    return safe


def require_int_range(value: int, *, field: str, min_val: int, max_val: int) -> int:
    try:
        v = int(value)
    except Exception:
        raise ValueError(f"{field} muss eine ganze Zahl sein.")
    if v < min_val or v > max_val:
        raise ValueError(f"{field} muss zwischen {min_val} und {max_val} liegen.")
    return v


def require_nonempty_str(value: str, *, field: str, max_len: int = 120) -> str:
    s = str(value or "").strip()
    if not s:
        raise ValueError(f"{field} darf nicht leer sein.")
    if len(s) > max_len:
        raise ValueError(f"{field} ist zu lang (max {max_len}).")
    return s
