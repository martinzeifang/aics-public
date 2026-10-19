from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from shared.config_io import safe_load_json_config, safe_save_json_config


DEFAULT_CONFIG_PATH = Path("compliance.config.json")


def default_config() -> Dict[str, Any]:
    return {
        "paths": {
            "reports_dir": "data/compliance/berichte",
            "sikos_dir": "data/shared/sikos",
            "db_path": "data/db/compliance.sqlite",
            "prompts_dir": "out/compliance/prompts",
            "answers_dir": "out/compliance/answers",
            "output_dir": "out/compliance/output",
        },
        "ui": {
            "test_mode": False,
            "top_k_examples": 3,
        },
        "prompt": {
            "header": (
                "Du bist ein Informationssicherheits-Assistent und erstellst Sicherheitsbewertungen auf Deutsch. "
                "Bewerte die beschriebene Schwachstelle/Beobachtung anhand der Kriterien aus den Sicherheitskonzepten "
                "(Eintrittswahrscheinlichkeit, Schadenspotenzial, Risiko, betroffene Schutzziele, Maßnahmen). "
                "Schreibe im Stil der bestehenden Quartalsberichte (kurz, konkret, nachvollziehbar)."
            ),
            # Note: risk matrix is fixed in code; these are informational only.
            "likelihood_scale": ["Unwahrscheinlich", "Möglich", "Wahrscheinlich", "Sehr wahrscheinlich"],
            "impact_scale": ["niedrig", "mittel", "hoch", "sehr hoch"],
            "risk_scale": ["1", "2", "3", "4", "5", "6", "7"],
            "output_schema_hint": True,
        },
    }


def load_config(path: Path | None = None) -> Dict[str, Any]:
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        cfg = default_config()
        save_config(cfg, path)
        return cfg

    data = safe_load_json_config(path)

    merged = default_config()
    _deep_update(merged, data)
    return merged


def save_config(cfg: Dict[str, Any], path: Path | None = None) -> None:
    path = path or DEFAULT_CONFIG_PATH
    safe_save_json_config(path, dict(cfg))


def _deep_update(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_update(dst[k], v)  # type: ignore[index]
        else:
            dst[k] = v


def cfg_get(cfg: Dict[str, Any], dotted: str, default: Any) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
