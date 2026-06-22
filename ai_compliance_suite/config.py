from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from shared.config_io import safe_load_json_config, safe_save_json_config


def _default_config_path() -> Path:
    """Konfig-Pfad — über AICS_CONFIG_PATH überschreibbar.

    Im Docker-Container schreibt der Web-User nur in /app/data (Named Volume).
    Daher wird AICS_CONFIG_PATH auf /app/data/ai_compliance_suite.config.json
    gesetzt, damit Einstellungs-Updates persistieren und nicht an
    'Permission denied' auf root-owned /app scheitern.
    """
    env = os.getenv('AICS_CONFIG_PATH')
    if env:
        return Path(env)
    return Path("ai_compliance_suite.config.json")


DEFAULT_CONFIG_PATH = _default_config_path()


def default_config() -> Dict[str, Any]:
    return {
        "security": {
            # Optional at-rest encryption for backups/evidence.
            # Live SQLite encryption is NOT enabled (requires SQLCipher/SEE).
            "at_rest_encryption": {
                "enabled": False,
                "key_env": "AICS_AT_REST_KEY",
                "encrypt_backups": True,
                "encrypt_evidence": False,
            }
        },
        "appearance": {
            "dark_mode": False,
        },
        # #1474 (SOC-Portal S8): Admin-Schalter, ob das SOC-Operations-Portal nutzbar ist.
        # Greift nur auf einer Portal-Instanz (AICS_PORTAL=soc); die Suite ist unberührt.
        "soc_portal": {
            "enabled": True,
        },
        "ai": {
            # Default is on-prem (no cloud connectivity required).
            "provider": "on_prem",
            "on_prem": {
                # Ollama default (local service): https://ollama.com
                "base_url": "http://127.0.0.1:11434",
                # Configure to an installed model, e.g. "llama3.1:latest".
                "model": "",
                "timeout_s": 60,
                # Security default: only allow loopback URLs unless explicitly enabled.
                "allow_nonlocal_base_url": False,
            },
            "cloud": {
                # Explicit consent required before any data is sent to a cloud provider.
                "allow_data_egress": False,
                # When enabled, redact obvious secrets/PII patterns before sending.
                # (Real redaction implementation is added with the cloud provider.)
                "redact": True,
                # Name of the environment variable that holds the API key.
                "api_key_env": "AI_CLOUD_API_KEY",
                # OpenAI-compatible endpoint base URL.
                "base_url": "https://api.openai.com/v1",
                # Configure to a supported model, e.g. "gpt-4.1-mini" (cloud) or your provider's model name.
                "model": "",
                "timeout_s": 60,
            },
        },
        "modules": {
            "order": [],
            "disabled": [],
        },
        "windows": {
            # Tk geometry strings: "<width>x<height>"
            "main_geometry": "1500x1100",
            "main_minsize": [1280, 820],
            "report_geometry": "1500x1100",
            "report_minsize": [1100, 860],
        },
        "backup": {
            "backup_on_exit": False,
            "backup_retention_count": 5,
        },
        "integrations": {
            "github": {
                # Personal Access Token (Scopes: repo). Wird nicht im Log
                # ausgegeben. Im Frontend nur masked dargestellt.
                "token": "",
                # Optionale Anzeigedaten
                "username": "",
                # Default org/repo für Issue-Erstellung (z.B. "owner/repo").
                "default_repo": "",
            }
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
