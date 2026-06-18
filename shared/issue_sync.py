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

from shared.net_validation import safe_get  # #1171: SSRF-sicherer GET


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
    # #1171: SSRF-Schutz — base_url ist anwender-konfiguriert (self-hosted GitLab).
    r = safe_get(url, headers=headers, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"GitLab issue fetch failed: HTTP {r.status_code}")
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

    # #1171: SSRF-Schutz — base_url ist anwender-konfiguriert (self-hosted GitLab).
    r = safe_get(
        _gl_api(base_url, f"projects/{proj_id}/issues/{int(iid)}"),
        headers=headers, timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"GitLab issue fetch failed: HTTP {r.status_code}")
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}

    rn = safe_get(
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


# ── Projektweiter Sync aller verlinkten Issues (#788) ──────────────────────────

def _parse_issue_url(url: str):
    """(provider, owner_repo_or_path, number, iid, base_url) aus einer Issue-URL."""
    import re
    s = (url or "").strip()
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)", s, re.IGNORECASE)
    if m:
        return ("github", f"{m.group(1)}/{m.group(2)}", int(m.group(3)), None, None)
    m = re.match(r"^https?://([^/]+)/(.+?)/-/issues/(\d+)", s)
    if m:
        return ("gitlab", m.group(2), None, int(m.group(3)), f"https://{m.group(1)}")
    return (None, None, None, None, None)


def build_combined_issue_text(details: dict) -> str:
    """Baut aus einem Issue-Detail-Dict (fetch_*_issue_details) einen
    zusammenhängenden Markdown-Text aus Titel, Status, Body und Kommentaren.
    Modul-agnostisch — von CRA/NIS2/AI-Act/Risikobewertung gleichermaßen nutzbar.
    """
    title = str(details.get("title", "") or "").strip()
    body = str(details.get("body", "") or "").strip()
    state = str(details.get("state", "") or "").strip()
    reason = str(details.get("state_reason", "") or "").strip()
    comments = details.get("comments") or []

    parts: list[str] = []
    if title:
        parts.append(f"# {title}")
    status_line = state + (f" ({reason})" if reason else "")
    if status_line:
        parts.append(f"**Status:** {status_line}")
    if body:
        parts.append(body)
    if comments:
        rendered = []
        for c in comments:
            if isinstance(c, dict):
                author = str(c.get("author", "") or "").strip()
                cbody = str(c.get("body", "") or "").strip()
            else:
                author, cbody = "", str(c).strip()
            if cbody:
                rendered.append((f"**{author}:** " if author else "") + cbody)
        if rendered:
            parts.append("## Kommentare\n\n" + "\n\n---\n\n".join(rendered))
    return "\n\n".join(parts)


def fetch_issue_content_by_url(url: str, *, gitlab_token_env: str = "GITLAB_TOKEN") -> dict:
    """Holt Titel+Body+Status+Kommentare einer GitHub-/GitLab-Issue-URL und
    liefert ein Dict inkl. ``combined`` (Markdown). Wirft ValueError bei
    nicht erkannter URL, RuntimeError/Exception bei Abruf-Fehlern.
    """
    provider, path, number, iid, base_url = _parse_issue_url(url)
    if provider == "github":
        details = fetch_github_issue_details(repo=path, number=int(number))
    elif provider == "gitlab":
        details = fetch_gitlab_issue_details(
            base_url=base_url, token_env=gitlab_token_env, project=path, iid=int(iid),
        )
    else:
        raise ValueError("Keine gültige GitHub-/GitLab-Issue-URL")
    details["combined"] = build_combined_issue_text(details)
    return details


def sync_project_links(db_path, projekt_name: str, *, gitlab_token_env: str = "GITLAB_TOKEN") -> dict:
    """Holt für ALLE im Projekt verlinkten Issues den Live-Status (GitHub/GitLab)
    und schreibt ihn persistent nach `linked_issues` zurück (#788).

    Returns: {synced, errors, total, items:[{object_kind, object_id, url, provider,
    title, state, state_reason, ok, error?}]}.
    """
    from shared import db as _sdb
    from shared.issue_links import add_link, ensure_tables
    from pathlib import Path

    ensure_tables(Path(db_path))
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM linked_issues WHERE projekt_name=? ORDER BY object_id",
            (projekt_name,),
        ).fetchall()
    except Exception:
        rows = []
    finally:
        con.close()

    items: list[dict] = []
    synced = 0
    errors = 0
    for r in rows:
        url = r["url"] or ""
        provider = r["provider"] or ""
        repo = r["repo"] or ""
        number = r["issue_number"]
        iid = r["issue_iid"]
        item = {
            "object_kind": r["object_kind"], "object_id": r["object_id"], "url": url,
            "provider": provider, "title": r["title"] or "", "state": r["state"] or "", "ok": True,
        }
        try:
            p2, repo2, num2, iid2, base = _parse_issue_url(url)
            prov = provider or p2 or ""
            if prov == "github":
                s = sync_github_issue(repo=(repo or repo2 or ""), number=int(number or num2 or 0))
            elif prov == "gitlab":
                s = sync_gitlab_issue(base_url=(base or ""), token_env=gitlab_token_env,
                                      project=(repo2 or repo or ""), iid=int(iid or iid2 or 0))
            else:
                raise ValueError("Unbekannter Provider/URL für Sync")
            add_link(
                Path(db_path), projekt_name=projekt_name,
                object_kind=r["object_kind"], object_id=r["object_id"],
                provider=prov, repo=(s.repo or repo), url=url,
                issue_number=(s.number or number), issue_iid=(s.iid or iid),
                title=s.title, state=s.state, state_reason=s.state_reason,
            )
            item.update(title=s.title, state=s.state, state_reason=s.state_reason)
            synced += 1
        except Exception as e:  # noqa: BLE001 - pro Issue tolerant, Fehler sammeln
            item["ok"] = False
            item["error"] = f"{type(e).__name__}: {e}"
            errors += 1
        items.append(item)

    return {"synced": synced, "errors": errors, "total": len(rows), "items": items}
