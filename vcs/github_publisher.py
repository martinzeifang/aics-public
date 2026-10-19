"""GitHub publisher via `gh api`.

Used to publish risk exports into a repository path (commits to a branch).

Auth:
- Relies on `gh` authentication OR `GH_TOKEN` env var.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _read_bytes_win_safe(p: Path) -> bytes:
    """Read bytes while avoiding WinError 206 on long paths.

    On Windows, some environments still enforce MAX_PATH unless the path is in
    extended-length form. Prefixing with "\\\\?\\" for absolute paths avoids that.
    """

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


def _parse_repo(repo: str) -> tuple[str, str]:
    s = (repo or "").strip()
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", s, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^([^/]+)/([^/]+)$", s)
    if m:
        return m.group(1), m.group(2)
    raise ValueError("Repo ungültig. Erwartet org/repo oder https://github.com/org/repo")


def _gh_api(path: str, *, method: str = "GET", fields: dict[str, str] | None = None) -> str:
    args = ["gh", "api", "-X", method, path]
    # Avoid Windows CreateProcess/command-line limits (WinError 206) for large payloads
    # by sending the request body via stdin as JSON.
    payload: dict[str, Any] = {}
    for k, v in (fields or {}).items():
        payload[k] = v

    inp = None
    if payload:
        args += ["--input", "-"]
        inp = json.dumps(payload)

    p = subprocess.run(args, input=inp, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "gh api failed").strip())
    return p.stdout


def _get_existing_sha(owner: str, repo: str, path: str, branch: str) -> str | None:
    api = f"repos/{owner}/{repo}/contents/{path.lstrip('/')}?ref={branch}"
    try:
        raw = _gh_api(api)
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("sha"):
            return str(data["sha"])
    except Exception:
        return None
    return None


def publish_file_to_repo(
    *,
    repo: str,
    branch: str,
    dest_path: str,
    local_path: Path,
    message: str,
) -> PublishResult:
    owner, name = _parse_repo(repo)
    dest_path = dest_path.strip().lstrip("/")

    content = base64.b64encode(_read_bytes_win_safe(Path(local_path))).decode("ascii")
    sha = _get_existing_sha(owner, name, dest_path, branch)
    fields = {
        "message": message,
        "content": content,
        "branch": branch,
    }
    if sha:
        fields["sha"] = sha

    api = f"repos/{owner}/{name}/contents/{dest_path}"
    raw = _gh_api(api, method="PUT", fields=fields)
    data = json.loads(raw)
    url = ""
    if isinstance(data, dict):
        c = data.get("content")
        if isinstance(c, dict):
            url = str(c.get("html_url") or "")

    action = "updated" if sha else "created"
    if not url:
        url = f"https://github.com/{owner}/{name}/blob/{branch}/{dest_path}"
    return PublishResult(path=dest_path, url=url, action=action)
