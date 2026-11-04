"""Versions-/Tag-Historie aus dem verknüpften Repo abrufen (#1662).

Liest die Versionen (Git-Tags bzw. GitHub-Releases / GitLab-Tags) des pro Projekt
konfigurierten Repos, damit die Release-Version aus der tatsächlichen Historie
gewählt werden kann. Best effort; Fehler → leere Liste (kein harter Abbruch).
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

from shared.vcs_repo_config import vcs_token


def list_versions(provider: str, repo: str, vcs: dict[str, Any] | None,
                  *, limit: int = 50, timeout_s: int = 10) -> list[str]:
    """Liste von Versions-/Tag-Namen (neueste zuerst). Leer, wenn nicht abrufbar."""
    provider = (provider or "github").strip().lower()
    repo = (repo or "").strip()
    if not repo:
        return []
    token = vcs_token(vcs)
    try:
        if provider == "gitlab":
            base = str((vcs or {}).get("base_url") or "https://gitlab.com").rstrip("/")
            pid = quote(repo, safe="")
            headers = {"PRIVATE-TOKEN": token} if token else {}
            r = requests.get(f"{base}/api/v4/projects/{pid}/repository/tags",
                             headers=headers, params={"per_page": limit}, timeout=timeout_s)
            if r.status_code >= 400:
                return []
            return [str(t.get("name")) for t in (r.json() or []) if t.get("name")]
        # GitHub (inkl. Enterprise via base_url)
        base = str((vcs or {}).get("base_url") or "https://api.github.com").rstrip("/")
        if "api" not in base.split("//", 1)[-1].split("/", 1)[0]:
            base = base + "/api/v3"  # GitHub-Enterprise-Host
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # Releases bevorzugt (semantische Versionen), Tags als Fallback.
        versions: list[str] = []
        rr = requests.get(f"{base}/repos/{repo}/releases",
                          headers=headers, params={"per_page": limit}, timeout=timeout_s)
        if rr.status_code < 400:
            versions = [str(x.get("tag_name") or x.get("name")) for x in (rr.json() or [])
                        if (x.get("tag_name") or x.get("name"))]
        if not versions:
            rt = requests.get(f"{base}/repos/{repo}/tags",
                              headers=headers, params={"per_page": limit}, timeout=timeout_s)
            if rt.status_code < 400:
                versions = [str(t.get("name")) for t in (rt.json() or []) if t.get("name")]
        return versions
    except Exception:  # noqa: BLE001 — best effort
        return []
