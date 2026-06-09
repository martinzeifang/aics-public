"""GitHub Issues helper.

Bevorzugt direkt die REST-API mit Token aus ENV (`GH_TOKEN` / `GITHUB_TOKEN`)
— funktioniert im Docker-Container, wo `gh` CLI fehlt (Issue #390).
Fallback auf `gh api` wenn CLI installiert ist (lokale Dev-Umgebung).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CreatedIssue:
    number: int
    url: str


def _parse_repo(repo: str) -> tuple[str, str]:
    s = (repo or "").strip()
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", s, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^([^/]+)/([^/]+)$", s)
    if m:
        return m.group(1), m.group(2)
    raise ValueError("Repo ungültig. Erwartet org/repo oder https://github.com/org/repo")


def _token() -> str:
    from shared.github_config import get_github_token
    return get_github_token()


def _via_rest(owner: str, name: str, *, title: str, body: str) -> dict:
    import requests
    from shared.github_config import github_headers

    r = requests.post(
        f"https://api.github.com/repos/{owner}/{name}/issues",
        headers=github_headers(),
        json={"title": title.strip(), "body": body.strip()},
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"GitHub API {r.status_code}: {r.text[:300]}")
    return r.json()


def _via_gh_cli(owner: str, name: str, *, title: str, body: str) -> dict:
    args = [
        "gh", "api", "-X", "POST", f"repos/{owner}/{name}/issues",
        "-f", f"title={title.strip()}",
        "-f", f"body={body.strip()}",
    ]
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "gh api failed").strip())
    return json.loads(p.stdout)


def create_issue(*, repo: str, title: str, body: str) -> CreatedIssue:
    owner, name = _parse_repo(repo)
    # Reihenfolge: REST (Token vorhanden) → gh CLI (lokal) → klare Fehlermeldung.
    if _token():
        data = _via_rest(owner, name, title=title, body=body)
    elif shutil.which("gh"):
        data = _via_gh_cli(owner, name, title=title, body=body)
    else:
        raise RuntimeError(
            "Kein Issue-Backend verfügbar: weder GH_TOKEN/GITHUB_TOKEN gesetzt "
            "noch `gh` CLI installiert."
        )
    return CreatedIssue(number=int(data.get("number") or 0), url=str(data.get("html_url") or ""))
