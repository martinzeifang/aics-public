"""GitLab publisher via REST API (no paid services).

Publishes files into a GitLab repository path by creating/updating files on a branch.

Auth:
- Token is read from an env var (default: GITLAB_TOKEN) or a caller-provided env var name.
"""

from __future__ import annotations

import base64
import os
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import requests


def _read_bytes_win_safe(p: Path) -> bytes:
    """Read bytes while avoiding WinError 206 on long paths."""

    path = Path(p)
    try:
        return path.read_bytes()
    except OSError as e:
        s = str(path)
        if getattr(e, "winerror", None) == 206 and (path.is_absolute() or re.match(r"^[A-Za-z]:\\", s)):
            if not s.startswith("\\\\?\\"):
                s2 = "\\\\?\\" + s
            else:
                s2 = s
            with open(s2, "rb") as f:
                return f.read()
        raise


@dataclass(frozen=True)
class PublishResult:
    path: str
    url: str
    action: str  # created|updated


def _parse_project(project: str) -> str:
    s = (project or "").strip()
    if not s:
        raise ValueError("GitLab Projekt fehlt (z.B. group/project oder URL)")

    # Accept https://gitlab.example.com/group/project(.git)
    m = re.match(r"^https?://[^/]+/(.+?)(?:\.git)?/?$", s)
    if m:
        s = m.group(1)

    # If numeric id, keep.
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


def publish_file_to_gitlab(
    *,
    base_url: str,
    token_env: str,
    project: str,
    branch: str,
    dest_path: str,
    local_path: Path,
    message: str,
) -> PublishResult:
    proj_id = _parse_project(project)
    dest_path = dest_path.strip().lstrip("/")
    file_path = urllib.parse.quote_plus(dest_path)

    headers = {"PRIVATE-TOKEN": _token(token_env)}
    content_b64 = base64.b64encode(_read_bytes_win_safe(Path(local_path))).decode("ascii")

    # Check if file exists
    get_url = _api(base_url, f"projects/{proj_id}/repository/files/{file_path}")
    r = requests.get(get_url, headers=headers, params={"ref": branch}, timeout=30)
    exists = r.status_code == 200

    url = _api(base_url, f"projects/{proj_id}/repository/files/{file_path}")
    data = {
        "branch": branch,
        "commit_message": message,
        "content": content_b64,
        "encoding": "base64",
    }
    if exists:
        r2 = requests.put(url, headers=headers, data=data, timeout=60)
        if r2.status_code not in (200, 201):
            raise RuntimeError(f"GitLab update failed: HTTP {r2.status_code}: {r2.text}")
        action = "updated"
    else:
        r2 = requests.post(url, headers=headers, data=data, timeout=60)
        if r2.status_code not in (200, 201):
            raise RuntimeError(f"GitLab create failed: HTTP {r2.status_code}: {r2.text}")
        action = "created"

    # Best-effort web URL
    web = (base_url or "https://gitlab.com").rstrip("/")
    if proj_id.isdigit():
        # unknown path -> keep API url
        file_url = f"{web}/-/project/{proj_id}/-/blob/{branch}/{dest_path}"
    else:
        # proj_id is URL-encoded path
        file_url = f"{web}/{urllib.parse.unquote_plus(proj_id)}/-/blob/{branch}/{dest_path}"

    return PublishResult(path=dest_path, url=file_url, action=action)
