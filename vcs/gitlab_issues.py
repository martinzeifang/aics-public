"""GitLab Issues helper via REST API.

Auth:
- Token from env var (default: GITLAB_TOKEN)
"""

from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class CreatedIssue:
    iid: int
    url: str


def _parse_project(project: str) -> str:
    s = (project or "").strip()
    if not s:
        raise ValueError("GitLab Projekt fehlt (z.B. group/project oder URL)")
    m = re.match(r"^https?://[^/]+/(.+?)(?:\.git)?/?$", s)
    if m:
        s = m.group(1)
    if s.isdigit():
        return s
    return urllib.parse.quote_plus(s)


def _api(base_url: str, path: str) -> str:
    base = (base_url or "https://gitlab.com").rstrip("/")
    return f"{base}/api/v4/{path.lstrip('/')}"


def _token(env_name: str) -> str:
    name = (env_name or "GITLAB_TOKEN").strip() or "GITLAB_TOKEN"
    tok = (os.getenv(name) or "").strip()
    if not tok:
        raise RuntimeError(f"GitLab Token fehlt. Bitte Env Var '{name}' setzen.")
    return tok


def create_issue(
    *,
    base_url: str,
    token_env: str,
    project: str,
    title: str,
    description: str,
) -> CreatedIssue:
    proj_id = _parse_project(project)
    headers = {"PRIVATE-TOKEN": _token(token_env)}
    url = _api(base_url, f"projects/{proj_id}/issues")
    r = requests.post(
        url,
        headers=headers,
        data={"title": (title or "").strip(), "description": (description or "").strip()},
        timeout=60,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"GitLab issue create failed: HTTP {r.status_code}: {r.text}")
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    return CreatedIssue(iid=int(data.get("iid") or 0), url=str(data.get("web_url") or ""))
