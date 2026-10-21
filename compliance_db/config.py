from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from shared.config_io import safe_load_json_config, safe_save_json_config

DEFAULT_CONFIG_PATH = Path("compliance_db.config.json")


def load_config(path: Path | None = None) -> Dict[str, Any]:
    p = path or DEFAULT_CONFIG_PATH
    if not p.exists():
        return default_config()
    try:
        data = safe_load_json_config(p)
        # merge with defaults to keep backward compatibility
        cfg = default_config()
        cfg.update(data)
        return cfg
    except Exception:
        return default_config()


def save_config(cfg: Dict[str, Any], path: Path | None = None) -> None:
    p = path or DEFAULT_CONFIG_PATH
    safe_save_json_config(p, dict(cfg))


def default_config() -> Dict[str, Any]:
    return {
        "paths": {
            # Read regulations from Gutachten DB by default.
            "gutachten_db_path": "data/db/gutachten.sqlite",
            # Separate index DB (FTS5). Stored in data/ so it stays local.
            "index_db_path": "data/db/compliance_db.sqlite",
            "debug_log_path": "out/compliance_db/debug.log",
        },
        "llm": {
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "model": "llama3.1",
            "timeout_s": 120,
            "top_k": 8,
        },
        "ui": {
            "test_mode": False,
            "debug_mode": False,
        },
    }
