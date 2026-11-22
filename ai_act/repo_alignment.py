"""Deterministic repository signals for AI Act module.

Currently supports GitHub via `gh api`.
"""

from __future__ import annotations

import re
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


def _gh_api_json(path: str, token: str | None = None) -> Any:
    """GitHub-API-JSON für ein API-Pfad.

    #1064: Bevorzugt die HTTP-API mit Token (containertauglich — im Web-Server/
    Container ist kein authentifiziertes `gh`-CLI verfügbar). Delegiert an
    ``vcs.repo_reader._github_api``, das ohne Token auf das `gh`-CLI zurückfällt
    (Desktop nutzt so seine gh-Auth)."""
    from vcs.repo_reader import _github_api, _resolve_github_token
    return _github_api(path, token=_resolve_github_token(token))


def github_path_exists(owner: str, repo: str, path: str, branch: str = "",
                       token: str | None = None) -> tuple[bool, dict[str, Any] | None]:
    """Check whether a path exists in a GitHub repo.

    branch is URL-encoded automatically so names like 'ai-act/ai-main' work.
    When branch is empty, the repo's default branch is used.
    """
    api = f"repos/{owner}/{repo}/contents/{path.lstrip('/')}"
    if branch:
        api += f"?ref={urllib.parse.quote(branch, safe='')}"
    try:
        data = _gh_api_json(api, token=token)
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


def github_fetch_text(owner: str, repo: str, path: str, branch: str = "",
                      max_bytes: int = 200_000, token: str | None = None) -> str | None:
    """Lädt den Klartext einer Repo-Datei via GitHub Contents-API (#1020/#1021).

    Gibt None zurück, wenn die Datei fehlt/kein File ist/zu groß. base64-Inhalt
    wird dekodiert. ``token`` (#1064) ermöglicht den Zugriff auf private Repos im
    Container (HTTP-API), wo kein authentifiziertes `gh`-CLI verfügbar ist.
    """
    import base64
    api = f"repos/{owner}/{repo}/contents/{path.lstrip('/')}"
    if branch:
        api += f"?ref={urllib.parse.quote(branch, safe='')}"
    try:
        data = _gh_api_json(api, token=token)
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("type") != "file":
        return None
    if int(data.get("size") or 0) > max_bytes:
        return None
    content = data.get("content") or ""
    enc = data.get("encoding") or "base64"
    if enc != "base64":
        return content if isinstance(content, str) else None
    try:
        return base64.b64decode(content).decode("utf-8", "replace")
    except Exception:
        return None
