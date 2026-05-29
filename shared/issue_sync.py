"""Shared issue status sync helpers (GitHub/GitLab).

Used to refresh linked issues and derive "successfully resolved" suggestions.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.parse
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class SyncedIssue:
    provider: str
    repo: str
    number: int | None
    iid: int | None
    url: str
    title: str
    state: str
    state_reason: str
    labels: list[str]


def is_successfully_resolved(*, state: str, state_reason: str, labels: list[str]) -> bool:
    """Heuristic default: closed + not 'not_planned'."""
    st = (state or "").lower()
    reason = (state_reason or "").lower()
    labs = {str(l).lower() for l in (labels or [])}
    if st != "closed":
        return False
    if reason in ("not_planned", "wontfix"):
        return False
    # If explicitly marked done/resolved/fixed, treat as success.
    if labs.intersection({"done", "resolved", "fixed", "complete", "completed"}):
        return True
    return True


def _gh_api_json(path: str) -> Any:
    """GitHub-API: REST mit GH_TOKEN aus ENV (Docker), Fallback auf gh-CLI
    für lokale Dev (Issue #406).
    """
    import shutil
    from shared.github_config import get_github_token, github_headers

    if get_github_token():
        import requests

        r = requests.get(
            f"https://api.github.com/{path.lstrip('/')}",
            headers=github_headers(),
            timeout=30,
        )
        if r.status_code == 404:
            return None
        if r.status_code >= 300:
            raise RuntimeError(f"GitHub API {r.status_code}: {r.text[:200]}")
        return r.json()

    if shutil.which("gh"):
        p = subprocess.run(
            ["gh", "api", path],
            check=False, capture_output=True, text=True, encoding="utf-8",
        )
        if p.returncode != 0:
            raise RuntimeError((p.stderr or p.stdout or "gh api failed").strip())
        out = (p.stdout or "").strip()
        return json.loads(out) if out else None

    raise RuntimeError(
        "Kein GitHub-Backend verfügbar: weder GH_TOKEN/GITHUB_TOKEN gesetzt "
        "noch `gh` CLI installiert. Im Container: GH_TOKEN als ENV im "
        "docker-compose unter web → environment setzen."
    )


def _parse_github_repo(repo: str) -> tuple[str, str] | None:
    s = (repo or "").strip()
    if not s:
        return None
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", s, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^([^/]+)/([^/]+)$", s)
    if m:
        return m.group(1), m.group(2)
    return None


def sync_github_issue(*, repo: str, number: int) -> SyncedIssue:
    parsed = _parse_github_repo(repo)
    if not parsed:
        raise ValueError("GitHub Repo ungültig (owner/repo oder URL)")
    owner, name = parsed
    data = _gh_api_json(f"repos/{owner}/{name}/issues/{int(number)}")
    if not isinstance(data, dict):
        raise RuntimeError("GitHub issue response invalid")
    labels = []
    for l in data.get("labels") or []:
        if isinstance(l, dict) and l.get("name"):
            labels.append(str(l.get("name")))
        elif isinstance(l, str):
            labels.append(l)
    return SyncedIssue(
        provider="github",
        repo=f"{owner}/{name}",
        number=int(data.get("number") or number),
        iid=None,
        url=str(data.get("html_url") or ""),
        title=str(data.get("title") or ""),
        state=str(data.get("state") or ""),
        state_reason=str(data.get("state_reason") or ""),
        labels=labels,
    )


def _gl_api(base_url: str, path: str) -> str:
    base = (base_url or "https://gitlab.com").rstrip("/")
    return f"{base}/api/v4/{path.lstrip('/')}"


def _gl_token(token_env: str) -> str:
    name = (token_env or "GITLAB_TOKEN").strip() or "GITLAB_TOKEN"
    tok = (os.getenv(name) or "").strip()
    if not tok:
        raise RuntimeError(f"GitLab Token fehlt. Bitte Env Var '{name}' setzen.")
    return tok


def _parse_gitlab_project(project: str) -> str:
    s = (project or "").strip()
    if not s:
        raise ValueError("GitLab Projekt fehlt (group/project oder URL)")
    m = re.match(r"^https?://[^/]+/(.+?)(?:\.git)?/?$", s)
    if m:
        s = m.group(1)
    if s.isdigit():
        return s
    return urllib.parse.quote_plus(s)


def sync_gitlab_issue(*, base_url: str, token_env: str, project: str, iid: int) -> SyncedIssue:
    proj_id = _parse_gitlab_project(project)
    headers = {"PRIVATE-TOKEN": _gl_token(token_env)}
    url = _gl_api(base_url, f"projects/{proj_id}/issues/{int(iid)}")
    r = requests.get(url, headers=headers, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"GitLab issue fetch failed: HTTP {r.status_code}: {r.text}")
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    labels = [str(x) for x in (data.get("labels") or []) if str(x).strip()]
    return SyncedIssue(
        provider="gitlab",
        repo=str(project),
        number=None,
        iid=int(data.get("iid") or iid),
        url=str(data.get("web_url") or ""),
        title=str(data.get("title") or ""),
        state=str(data.get("state") or ""),
        state_reason=str(data.get("state_reason") or ""),
        labels=labels,
    )


def fetch_github_issue_details(*, repo: str, number: int) -> dict:
    """Fetch full GitHub issue data (body + comments) via gh CLI.

    Returns a dict with keys: title, state, state_reason, body, labels,
    assignees, comments (list of {author, body}), url.
    """
    parsed = _parse_github_repo(repo)
    if not parsed:
        raise ValueError("GitHub Repo ungültig (owner/repo oder URL)")
    owner, name = parsed
    num = int(number)

    data = _gh_api_json(f"repos/{owner}/{name}/issues/{num}") or {}
    comments_raw = _gh_api_json(f"repos/{owner}/{name}/issues/{num}/comments") or []

    labels = [
        str(l.get("name", "")) if isinstance(l, dict) else str(l)
        for l in (data.get("labels") or [])
    ]
    assignees = [
        str(a.get("login", "")) for a in (data.get("assignees") or [])
        if isinstance(a, dict)
    ]
    comments = [
        {
            "author": str((c.get("user") or {}).get("login", "")),
            "body":   str(c.get("body", "") or "").strip(),
        }
        for c in comments_raw if isinstance(c, dict) and (c.get("body") or "").strip()
    ]
    return {
        "title":        str(data.get("title", "") or ""),
        "state":        str(data.get("state", "") or ""),
        "state_reason": str(data.get("state_reason", "") or ""),
        "body":         str(data.get("body", "") or "").strip(),
        "labels":       labels,
        "assignees":    assignees,
        "comments":     comments,
        "url":          str(data.get("html_url", "") or ""),
    }


def fetch_gitlab_issue_details(*, base_url: str, token_env: str, project: str, iid: int) -> dict:
    """Fetch full GitLab issue data (description + notes) via REST API.

    Returns the same dict shape as fetch_github_issue_details.
    """
    proj_id = _parse_gitlab_project(project)
    headers = {"PRIVATE-TOKEN": _gl_token(token_env)}

    r = requests.get(
        _gl_api(base_url, f"projects/{proj_id}/issues/{int(iid)}"),
        headers=headers, timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"GitLab issue fetch failed: HTTP {r.status_code}: {r.text[:200]}")
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}

    rn = requests.get(
        _gl_api(base_url, f"projects/{proj_id}/issues/{int(iid)}/notes?per_page=100&sort=asc"),
        headers=headers, timeout=60,
    )
    comments = []
    if rn.status_code == 200:
        for n in rn.json():
            if isinstance(n, dict) and not n.get("system"):
                body = str(n.get("body", "") or "").strip()
                if body:
                    comments.append({
                        "author": str((n.get("author") or {}).get("name", "")),
                        "body":   body,
                    })

    labels    = [str(x) for x in (data.get("labels") or []) if str(x).strip()]
    assignees = [str((a or {}).get("name", "")) for a in (data.get("assignees") or [])
                 if isinstance(a, dict)]
    return {
        "title":        str(data.get("title", "") or ""),
        "state":        str(data.get("state", "") or ""),
        "state_reason": str(data.get("state_reason", "") or ""),
        "body":         str(data.get("description", "") or "").strip(),
        "labels":       labels,
        "assignees":    assignees,
        "comments":     comments,
        "url":          str(data.get("web_url", "") or ""),
    }
