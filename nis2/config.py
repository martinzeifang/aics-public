"""NIS2-Modul – Konfigurationsverwaltung."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.config_io import safe_load_json_config, safe_save_json_config

DEFAULT_CONFIG_PATH = Path("nis2.config.json")

_DEFAULTS: dict[str, Any] = {
    "db_path": "data/db/nis2.sqlite",
    "fragebogen_dir": "out/nis2/fragebogen",
    "bericht_dir": "out/nis2/berichte",
}


def default_config() -> dict[str, Any]:
    return dict(_DEFAULTS)


def load_config(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_CONFIG_PATH
    if p.exists():
        try:
            data = safe_load_json_config(p)
            cfg = default_config()
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return default_config()


def save_config(cfg: dict[str, Any], path: Path | None = None) -> None:
    p = path or DEFAULT_CONFIG_PATH
    safe_save_json_config(p, cfg)


def cfg_get(cfg: dict[str, Any], key: str, default: Any = None) -> Any:
    return cfg.get(key, default)
