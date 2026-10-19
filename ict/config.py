from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.config_io import safe_load_json_config, safe_save_json_config


DEFAULT_CONFIG_PATH = Path("ict.config.json")


def default_config() -> dict[str, Any]:
    return {
        "paths": {
            "source_dir": "data/ict/quelle",
            "new_dir": "data/ict/neu",
            "reports_dir": "data/compliance/berichte",
            "sikos_dir": "data/shared/sikos",
            "db_path": "data/db/ict.sqlite",
            "prompts_dir": "out/ict/prompts",
            "answers_dir": "out/ict/answers",
            "filled_dir": "out/ict/filled",
        },
        "ui": {
            "top_k": 3,
            "batch_size": 10,
            "test_mode": False,
        },
        "prompt": {
            "header": (
                "Du bist ein Informationssicherheits-Assistent. Beantworte ICT-Fragebogenpunkte kurz, "
                "konkret und fachlich. Nutze die bereitgestellten Kontexte (bereits beantwortete Beispiele "
                "+ Sicherheitskonzepte) und orientiere dich stilistisch an den bisherigen Antworten."
            ),
            "answer_values": ["Ja", "Nein"],
            "maturity_values": [1, 2, 3, 4],
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


def _deep_update(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_update(dst[k], v)  # type: ignore[index]
        else:
            dst[k] = v


def save_config(cfg: dict[str, Any], path: Path | None = None) -> None:
    path = path or DEFAULT_CONFIG_PATH
    safe_save_json_config(path, cfg)


def cfg_get(cfg: dict[str, Any], dotted: str, default: Any) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
