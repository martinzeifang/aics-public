"""Fetch repository metadata (description, README, file tree) for use as risk-assessment context.

Supports GitHub (via `gh api` CLI – uses existing authentication) and public GitLab instances
(via plain HTTPS API; pass GITLAB_TOKEN env var for private repos).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RepoContext:
    provider: str        # "github" | "gitlab"
    repo: str            # owner/repo
    url: str             # canonical web URL
    description: str
    readme: str          # first N chars
    file_tree: list[str] # relative paths


def detect_provider(raw: str) -> tuple[str, str, str]:
    """Return (provider, owner/repo, canonical_url) from a raw input string.

    Accepted formats:
      - owner/repo                          → GitHub
      - https://github.com/owner/repo
      - https://gitlab.com/owner/repo
      - https://gitlab.example.com/owner/repo
    """
    raw = raw.strip().rstrip("/")

    # Full URL
    m = re.match(r"^https?://(github\.com)/([^/]+/[^/]+?)(?:\.git)?$", raw, re.IGNORECASE)
    if m:
        owner_repo = m.group(2)
        return "github", owner_repo, f"https://github.com/{owner_repo}"

    m = re.match(r"^https?://([^/]*gitlab[^/]*)/([^/]+(?:/[^/]+)+?)(?:\.git)?$", raw, re.IGNORECASE)
    if m:
        host = m.group(1)
        owner_repo = m.group(2)
        return "gitlab", owner_repo, f"https://{host}/{owner_repo}"

    # Short form owner/repo → assume GitHub
    m = re.match(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)$", raw)
    if m:
        owner_repo = m.group(1)
        return "github", owner_repo, f"https://github.com/{owner_repo}"

    raise ValueError(
        f"Unbekanntes Repository-Format: «{raw}»\n"
        "Erwartet: owner/repo  oder  https://github.com/owner/repo  oder  https://gitlab.com/owner/repo"
    )


# ── GitHub ────────────────────────────────────────────────────────────────────
# Bevorzugt die HTTP-API (api.github.com) — funktioniert auch im Web-Server/
# Container ohne installiertes `gh`-CLI (#777). Das `gh`-CLI wird nur als
# Fallback genutzt, wenn es vorhanden ist (Desktop nutzt so seine gh-Auth).

_GITHUB_API = "https://api.github.com"


def _gh_api(path: str) -> dict | list:
    """GitHub-API via `gh`-CLI (nutzt vorhandene gh-Authentifizierung)."""
    args = ["gh", "api", path]
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=30)  # nosec B603 - feste Argliste, keine Shell
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "gh api fehler").strip()[:300])
    return json.loads(p.stdout)


def _github_http_api(path: str) -> dict | list:
    """GitHub-API via HTTPS (api.github.com). Optionaler Token aus GITHUB_TOKEN.

    Fester Host → SSRF-unkritisch. Öffentliche Repos brauchen keinen Token
    (rate-limited), private/erhöhtes Limit via GITHUB_TOKEN.
    """
    url = f"{_GITHUB_API}/{path.lstrip('/')}"
    req = urllib.request.Request(url)  # nosec B310 - fester https-Host api.github.com
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "AI-Compliance-Suite/1.0")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as resp:  # nosec B310 - https only
        return json.loads(resp.read().decode("utf-8"))


def _github_api(path: str) -> dict | list:
    """Wählt gh-CLI (falls vorhanden) und fällt sonst/­bei Fehler auf HTTP zurück."""
    import shutil

    if shutil.which("gh"):
        try:
            return _gh_api(path)
        except Exception as exc:  # noqa: BLE001 - CLI-Fehler → HTTP-Fallback
            logger.warning("gh CLI fehlgeschlagen (%s), nutze HTTP-API", exc)
    return _github_http_api(path)


def _fetch_github(owner_repo: str, *, max_readme_chars: int = 3000, max_tree_entries: int = 120) -> RepoContext:
    owner, repo = owner_repo.split("/", 1)

    # Repo metadata
    meta = _github_api(f"repos/{owner}/{repo}")
    description = str(meta.get("description") or "")
    default_branch = str(meta.get("default_branch") or "main")

    # README
    readme = ""
    try:
        rm = _github_api(f"repos/{owner}/{repo}/readme")
        content_b64 = str(rm.get("content", "")).replace("\n", "")
        decoded = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        readme = decoded[:max_readme_chars]
    except Exception as exc:
        logger.warning("Failed to fetch GitHub README: %s", exc)

    # File tree (recursive, flat)
    file_tree: list[str] = []
    try:
        tree_data = _github_api(f"repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1")
        entries = tree_data.get("tree", []) if isinstance(tree_data, dict) else []
        file_tree = [
            e["path"] for e in entries
            if e.get("type") == "blob" and not e["path"].startswith(".")
        ][:max_tree_entries]
    except Exception as exc:
        logger.warning("Failed to fetch GitHub file tree: %s", exc)

    return RepoContext(
        provider="github",
        repo=owner_repo,
        url=f"https://github.com/{owner_repo}",
        description=description,
        readme=readme,
        file_tree=file_tree,
    )


# ── GitLab (plain HTTPS) ──────────────────────────────────────────────────────

def _gitlab_get(url: str, token: str | None = None) -> dict | list:
    req = urllib.request.Request(url)
    if token:
        req.add_header("PRIVATE-TOKEN", token)
    req.add_header("User-Agent", "AI-Compliance-Suite/1.0")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_gitlab(owner_repo: str, base_url: str, *, max_readme_chars: int = 3000, max_tree_entries: int = 120) -> RepoContext:
    token = os.environ.get("GITLAB_TOKEN") or os.environ.get("CI_JOB_TOKEN")
    encoded_path = urllib.parse.quote(owner_repo, safe="")

    # Extract host from base_url
    m = re.match(r"^(https?://[^/]+)", base_url)
    host = m.group(1) if m else "https://gitlab.com"
    api_base = f"{host}/api/v4/projects/{encoded_path}"

    # Metadata
    meta = _gitlab_get(api_base, token)
    description = str(meta.get("description") or "")
    default_branch = str(meta.get("default_branch") or "main")

    # README
    readme = ""
    try:
        readme_url = f"{api_base}/repository/files/README.md/raw?ref={default_branch}"
        req = urllib.request.Request(readme_url)
        if token:
            req.add_header("PRIVATE-TOKEN", token)
        req.add_header("User-Agent", "AI-Compliance-Suite/1.0")
        with urllib.request.urlopen(req, timeout=20) as resp:
            readme = resp.read().decode("utf-8", errors="replace")[:max_readme_chars]
    except Exception as exc:
        logger.warning("Failed to fetch GitLab README: %s", exc)

    # File tree (first page only)
    file_tree: list[str] = []
    try:
        tree_url = f"{api_base}/repository/tree?recursive=true&per_page=100&ref={default_branch}"
        tree_data = _gitlab_get(tree_url, token)
        if isinstance(tree_data, list):
            file_tree = [
                e["path"] for e in tree_data
                if e.get("type") == "blob" and not e["path"].startswith(".")
            ][:max_tree_entries]
    except Exception as exc:
        logger.warning("Failed to fetch GitLab file tree: %s", exc)

    return RepoContext(
        provider="gitlab",
        repo=owner_repo,
        url=base_url,
        description=description,
        readme=readme,
        file_tree=file_tree,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_repo_context(raw: str) -> RepoContext:
    """Fetch repository context from GitHub or GitLab.

    Raises ValueError on bad input, RuntimeError on fetch failure.
    """
    provider, owner_repo, canon_url = detect_provider(raw)
    if provider == "github":
        return _fetch_github(owner_repo)
    else:
        return _fetch_gitlab(owner_repo, canon_url)


def format_repo_context(ctx: RepoContext) -> str:
    """Format a RepoContext as a block of text suitable for inclusion in a prompt."""
    lines: list[str] = [
        f"## Repository: {ctx.repo}",
        f"URL: {ctx.url}",
    ]
    if ctx.description:
        lines += [f"Beschreibung: {ctx.description}", ""]

    if ctx.readme.strip():
        readme_excerpt = ctx.readme.strip()[:2500]
        lines += ["### README (Auszug)", readme_excerpt, ""]

    if ctx.file_tree:
        lines += ["### Dateistruktur (Auszug)"]
        lines += ctx.file_tree[:80]
        if len(ctx.file_tree) > 80:
            lines.append(f"… ({len(ctx.file_tree) - 80} weitere Dateien)")
        lines.append("")

    return "\n".join(lines)
