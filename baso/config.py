from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.config_io import safe_load_json_config, safe_save_json_config


DEFAULT_CONFIG_PATH = Path("baso.config.json")


def default_config() -> dict[str, Any]:
    # Keep this user-editable. UTF-8 is expected.
    return {
        "paths": {
            "source_dir": "data/baso/quelle",
            "new_dir": "data/baso/neu",
            "sikos_dir": "data/shared/sikos",
            "db_path": "data/db/baso.sqlite",
            "prompts_dir": "out/baso/prompts",
            "answers_dir": "out/baso/answers",
            "filled_dir": "out/baso/filled",
        },
        "ui": {
            "evaluated_by": "",
            "top_k": 3,
            "batch_size": 10,
            "test_mode": False,
            "debug_mode": False,
        },
        "prompt": {
            "header": (
                "Du bist ein Informationssicherheits-Assistent. Beantworte die Sollmaßnahmen kurz, "
                "konkret und fachlich. Nutze die bereitgestellten Kontexte (Sicherheitskonzepte + "
                "bereits beantwortete Beispiele) und triff plausible Annahmen wie in den bestehenden "
                "Antworten. Schreibe NICHT, dass etwas 'nicht ableitbar' ist. Formuliere mutig, aber "
                "bei Unsicherheit bevorzuge 'Teilweise' statt 'Nein'."
            ),
            "style_system": "Stil: kurze Feststellungssätze; kein 'nicht ableitbar', kein 'kann nicht beurteilt werden'",
            "style_service": "Stil: kurze Feststellungssätze; kein 'nicht ableitbar'; bei Unklarheit lieber 'teilweise umgesetzt'",

            "system_statuses": [
                "vollständig umgesetzt",
                "teilweise umgesetzt",
                "nicht umgesetzt",
                "unbearbeitet",
            ],
            "service_contract_values": [
                "Ja",
                "Nein",
                "Nicht anwendbar",
            ],
            "service_ops_values": [
                "Ja",
                "Nein",
                "teilweise umgesetzt",
                "Nicht anwendbar",
            ],
        },
    }


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        cfg = default_config()
        save_config(cfg, path)
        return cfg

    data = safe_load_json_config(path)

    # Shallow merge with defaults so new keys appear automatically.
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
