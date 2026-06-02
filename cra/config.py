"""CRA-Modul – Konfigurationsverwaltung."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.config_io import safe_load_json_config, safe_save_json_config

DEFAULT_CONFIG_PATH = Path("cra.config.json")


def default_config() -> dict[str, Any]:
    return {
        "paths": {
            "db_path": "data/db/cra.sqlite",
            "cra_resources_dir": "data/cra_resources",
            "fragebogen_dir": "out/cra/fragebogen",
            "berichte_dir": "out/cra/berichte",
        },
        "ui": {
            "projekt_name": "Mein-CRA-Projekt",
            "debug_mode": False,
        },
        "bericht": {
            "berater_name": "",
            "organisation": "",
            "version": "1.0",
            "vertraulichkeit": "Vertraulich",
        },
        # C3 Vulnerability-Auto-Sync (#937)
        "sync": {
            "gitlab_base_url": "https://gitlab.com",
            "gitlab_token_env": "GITLAB_TOKEN",
            "auto_promote_to_risk": False,
            # C3 In-App-Scheduler (#949, Story C) — opt-in, Default aus.
            "scheduler_enabled": False,
            # Pro Eintrag: {"projekt": "...", "cron": "0 4 * * *", "source": "all"}
            "schedule": [],
        },
        # C5 Threat-Model (#938)
        "threatmodel": {
            "framework_locked_to_risk": True,
        },
    }


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        cfg = default_config()
        save_config(cfg, path)
        return cfg
    data = safe_load_json_config(path)
    merged = default_config()
    _deep_update(merged, data)
    return merged


def save_config(cfg: dict[str, Any], path: Path | None = None) -> None:
    path = path or DEFAULT_CONFIG_PATH
    safe_save_json_config(path, cfg)


def _deep_update(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_update(dst[k], v)
        else:
            dst[k] = v


def cfg_get(cfg: dict[str, Any], dotted: str, default: Any = None) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
