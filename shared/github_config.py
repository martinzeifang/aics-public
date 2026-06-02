"""Zentrale GitHub-Token-Konfiguration.

Reihenfolge (#416 — analog zu #410 für Ollama):
  1. `ai_compliance_suite.config.json` → `integrations.github.token` (UI-Wert ist authoritativ)
  2. ENV `GH_TOKEN` / `GITHUB_TOKEN` (Bootstrap-Default für Docker)
  3. Leer → Aufrufer muss Fehler zeigen

Damit ist GitHub-Integration im UI dauerhaft konfigurierbar; ENV-Vars dienen
nur als Initial-Befüllung wenn die Config leer ist.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GitHubConfig:
    token: str
    username: str
    default_repo: str
    source: str  # 'env' / 'config' / 'unset'


def get_github_config() -> GitHubConfig:
    """Config gewinnt — ENV ist nur Fallback (#416)."""
    # 1) UI-Config zuerst
    try:
        from ai_compliance_suite.config import load_config

        cfg = load_config()
        gh = (cfg.get("integrations") or {}).get("github") or {}
        token = str(gh.get("token") or "").strip()
        if token:
            return GitHubConfig(
                token=token,
                username=str(gh.get("username") or "").strip(),
                default_repo=str(gh.get("default_repo") or "").strip(),
                source="config",
            )
    except Exception:
        pass

    # 2) ENV als Bootstrap-Default
    env_token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if env_token:
        return GitHubConfig(
            token=env_token,
            username=os.environ.get("GH_USERNAME", "").strip(),
            default_repo=os.environ.get("GH_DEFAULT_REPO", "").strip(),
            source="env",
        )

    return GitHubConfig(token="", username="", default_repo="", source="unset")


def get_github_token() -> str:
    return get_github_config().token


def github_headers() -> dict[str, str]:
    """Standard-Headers für GitHub-REST-API. Wirft RuntimeError wenn kein Token."""
    token = get_github_token()
    if not token:
        raise RuntimeError(
            "Kein GitHub-Token konfiguriert. Bitte in den Einstellungen "
            "unter 'GitHub' einen Personal Access Token hinterlegen — "
            "oder ENV GH_TOKEN setzen."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "aics-compliance-suite",
    }
