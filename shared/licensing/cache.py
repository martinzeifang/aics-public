"""Persistenter Token-Cache.

Speichert den Lizenz-Token base64-codiert (binär statt Klartext, damit
versehentliches Editieren in einem Editor sofort auffällt). Atomare Writes
mit chmod 0600.
"""

from __future__ import annotations

import base64
import os
import stat
from pathlib import Path

from shared.licensing.config import LicenseClientConfig


_HEADER = b'AICS-LIC-CACHE-v1\n'


def cache_path(cfg: LicenseClientConfig) -> Path:
    return cfg.cache_path


def load_cached_token(cfg: LicenseClientConfig) -> str:
    """Liefert den gecachten Token oder leerer String."""
    p = cfg.cache_path
    if not p.exists():
        return ''
    try:
        raw = p.read_bytes()
    except OSError:
        return ''
    if not raw.startswith(_HEADER):
        return ''
    try:
        decoded = base64.b64decode(raw[len(_HEADER):]).decode('utf-8')
    except Exception:  # noqa: BLE001
        return ''
    return decoded.strip()


def save_cached_token(cfg: LicenseClientConfig, token: str) -> None:
    """Speichert den Token atomisch (write-to-tmp, replace)."""
    p = cfg.cache_path
    p.parent.mkdir(parents=True, exist_ok=True)
    enc = base64.b64encode(token.strip().encode('utf-8'))
    body = _HEADER + enc + b'\n'

    tmp = p.with_suffix(p.suffix + '.tmp')
    old_mask = os.umask(0o077)
    try:
        tmp.write_bytes(body)
    finally:
        os.umask(old_mask)
    try:
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    tmp.replace(p)


def delete_cached_token(cfg: LicenseClientConfig) -> None:
    try:
        cfg.cache_path.unlink()
    except FileNotFoundError:
        pass
