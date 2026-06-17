from __future__ import annotations
from pathlib import Path
import json

from shared.config_io import safe_load_json_config, safe_save_json_config

DEFAULT_CONFIG_PATH = Path("risikobewertung.config.json")

_DEFAULTS: dict = {
    "paths": {
        "db": "data/db/risikobewertung.sqlite",
        "export_dir": "out/risikobewertung/",
    },
    "ui": {
        "projekt_name": "Demoprojekt",
    },
    "llm": {
        "model": "llama3.1",
        "base_url": "http://localhost:11434",
        "timeout_s": 120,
    },
}


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    if path.exists():
        try:
            data = safe_load_json_config(path)
            merged = json.loads(json.dumps(_DEFAULTS))
            _deep_update(merged, data)
            return merged
        except Exception:
            pass
    return json.loads(json.dumps(_DEFAULTS))


def save_config(cfg: dict, path: Path = DEFAULT_CONFIG_PATH) -> None:
    safe_save_json_config(path, cfg)


def cfg_get(cfg: dict, key: str, default=None):
    parts = key.split(".")
    node = cfg
    for p in parts:
        if not isinstance(node, dict) or p not in node:
            return default
        node = node[p]
    return node


def _deep_update(dst: dict, src: dict) -> None:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_update(dst[key], value)
        else:
            dst[key] = value
