"""DSGVO-Modul – Konfigurationsverwaltung."""
from __future__ import annotations

import logging

import json
from pathlib import Path
from typing import Any

from shared.config_io import safe_load_json_config, safe_save_json_config, module_config_path

_log = logging.getLogger(__name__)

# #1721: neben der Suite-Config (AICS_CONFIG_PATH), nicht CWD-relativ —
# im Container ist /app nicht schreibbar und load_config schreibt beim Lesen.
DEFAULT_CONFIG_PATH = module_config_path("dsgvo.config.json")


def default_config() -> dict[str, Any]:
    return {
        "paths": {
            "db_path": "data/db/dsgvo.sqlite",
            "dsgvo_resources_dir": "data/dsgvo_resources",
            "fragebogen_dir": "out/dsgvo/fragebogen",
            "berichte_dir": "out/dsgvo/berichte",
        },
        "ui": {
            "projekt_name": "Mein-DSGVO-Projekt",
            "debug_mode": False,
        },
        "bericht": {
            "berater_name": "",
            "organisation": "",
            "version": "1.0",
            "vertraulichkeit": "Vertraulich",
        },
    }


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        cfg = default_config()
        # #1721: Lesen darf nicht scheitern, wenn der Ablageort nicht
        # schreibbar ist (Container: /app). Dann gelten die Vorgaben,
        # ohne sie zu persistieren — statt HTTP 500 auf dem Endpunkt.
        try:
            save_config(cfg, path)
        except OSError:
            _log.warning("Konfiguration %s nicht schreibbar — nutze Vorgaben", path)
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
