"""Deterministic repository signals for AI Act module.

Currently supports GitHub via `gh api`.
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
from typing import Any


def parse_github_repo(repo_url: str) -> tuple[str, str] | None:
    s = (repo_url or "").strip()
    if not s:
        return None

    # Accept https://github.com/owner/repo(.git) or owner/repo
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", s, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)

    m = re.match(r"^([^/]+)/([^/]+)$", s)
    if m:
        return m.group(1), m.group(2)

    return None


def _gh_api_json(path: str) -> Any:
    p = subprocess.run(
        ["gh", "api", path],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "gh api failed").strip())
    out = (p.stdout or "").strip()
    return json.loads(out) if out else None


def github_path_exists(owner: str, repo: str, path: str, branch: str = "") -> tuple[bool, dict[str, Any] | None]:
    """Check whether a path exists in a GitHub repo.

    branch is URL-encoded automatically so names like 'ai-act/ai-main' work.
    When branch is empty, the repo's default branch is used.
    """
    api = f"repos/{owner}/{repo}/contents/{path.lstrip('/')}"
    if branch:
        api += f"?ref={urllib.parse.quote(branch, safe='')}"
    try:
        data = _gh_api_json(api)
    except Exception:
        return False, None

    ref_slug = urllib.parse.quote(branch, safe="") if branch else "HEAD"
    if isinstance(data, dict) and data.get("type") in ("file", "dir"):
        url = data.get("html_url") or (
            f"https://github.com/{owner}/{repo}/blob/{ref_slug}/{path.lstrip('/')}"
        )
        return True, {"provider": "github", "owner": owner, "repo": repo, "path": path, "url": url}
    if isinstance(data, list):
        return True, {
            "provider": "github",
            "owner": owner,
            "repo": repo,
            "path": path,
            "url": f"https://github.com/{owner}/{repo}/tree/{ref_slug}/{path.lstrip('/')}" ,
        }
    return False, None
