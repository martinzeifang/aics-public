"""Versions-Änderungen aus GitHub/GitLab importieren (#1248).

Liest Releases, Tags und Compare-Diffs (Commits / Datei-Änderungen) aus dem
verknüpften Repository — als Datenbasis für die KI-Zusammenfassung „Wesentliche
Änderungen je Version" (#1249) in der EU-Konformitätserklärung / technischen Doku.

Sicherheit:
- GitHub läuft über den festen Host ``api.github.com`` (kein SSRF-Vektor) mit den
  bestehenden Token-/Fallback-Helfern aus ``cra.repo_alignment`` bzw.
  ``shared.github_config``.
- GitLab nutzt eine konfigurierbare ``base_url`` → JEDER Request wird über
  ``shared.net_validation.safe_get`` SSRF-validiert (Loopback/RFC1918/Metadata).

Reine Lesepfade — keine Schreiboperationen am Repo. Token kommt aus der
pro-Projekt-vcs_publish-Konfiguration (vom Aufrufer via ENV bereitgestellt).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus


class RepoChangesError(RuntimeError):
    """Erwarteter, dem Nutzer anzeigbarer Fehler (kein Repo/Token, API-Fehler)."""


@dataclass
class VersionRef:
    """Eine auswählbare Version (Release oder Tag)."""
    name: str                      # Tag-/Release-Name (z.B. "v1.2.0")
    typ: str                       # 'release' | 'tag'
    title: str = ''                # Release-Titel (falls vorhanden)
    published_at: str = ''         # ISO-Datum (falls vorhanden)
    url: str = ''                  # html_url / web_url

    def as_dict(self) -> dict[str, Any]:
        return {'name': self.name, 'typ': self.typ, 'title': self.title,
                'published_at': self.published_at, 'url': self.url}


@dataclass
class VersionDiff:
    """Strukturierte Änderungsliste zwischen zwei Versionen."""
    base: str
    head: str
    provider: str
    commits: list[dict[str, str]] = field(default_factory=list)   # {sha, message, author}
    changed_files: list[str] = field(default_factory=list)
    changelog: str = ''            # optionaler CHANGELOG.md-Auszug

    def as_dict(self) -> dict[str, Any]:
        return {
            'base': self.base, 'head': self.head, 'provider': self.provider,
            'commits': self.commits, 'changed_files': self.changed_files,
            'changelog': self.changelog,
            'commit_count': len(self.commits),
            'file_count': len(self.changed_files),
        }


def _parse_github_repo(repo: str) -> tuple[str, str]:
    s = (repo or '').strip()
    m = re.match(r'^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$', s, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r'^([^/]+)/([^/]+)$', s)
    if m:
        return m.group(1), m.group(2).split('/')[0]
    raise RepoChangesError('GitHub-Repo ungültig. Erwartet "owner/name".')


# ════════════════════════════════════════════════════════════════════
# GitHub
# ════════════════════════════════════════════════════════════════════

def _github_list_versions(owner: str, repo: str, *, limit: int = 50) -> list[VersionRef]:
    from cra.repo_alignment import _gh_api_json
    out: list[VersionRef] = []
    seen: set[str] = set()
    try:
        releases = _gh_api_json(f'repos/{owner}/{repo}/releases?per_page={limit}') or []
    except Exception:  # noqa: BLE001 — Tags-Fallback unten
        releases = []
    for rel in releases:
        tag = str(rel.get('tag_name') or '').strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(VersionRef(
            name=tag, typ='release', title=str(rel.get('name') or ''),
            published_at=str(rel.get('published_at') or rel.get('created_at') or ''),
            url=str(rel.get('html_url') or ''),
        ))
    try:
        tags = _gh_api_json(f'repos/{owner}/{repo}/tags?per_page={limit}') or []
    except Exception:  # noqa: BLE001
        tags = []
    for t in tags:
        name = str(t.get('name') or '').strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(VersionRef(name=name, typ='tag'))
    if not out:
        raise RepoChangesError(
            'Keine Releases/Tags im GitHub-Repo gefunden (oder kein Zugriff).')
    return out


def _github_diff(owner: str, repo: str, base: str, head: str) -> VersionDiff:
    from cra.repo_alignment import _gh_api_json
    data = _gh_api_json(f'repos/{owner}/{repo}/compare/{quote_plus(base)}...{quote_plus(head)}')
    commits = []
    for c in (data.get('commits') or []):
        commit = c.get('commit') or {}
        commits.append({
            'sha': str(c.get('sha', ''))[:10],
            'message': str(commit.get('message') or '').strip(),
            'author': str((commit.get('author') or {}).get('name') or ''),
        })
    files = [str(f.get('filename') or '') for f in (data.get('files') or []) if f.get('filename')]
    return VersionDiff(base=base, head=head, provider='github',
                       commits=commits, changed_files=files,
                       changelog=_github_changelog(owner, repo))


def _github_changelog(owner: str, repo: str) -> str:
    """Optionaler CHANGELOG.md-Auszug (best-effort, nie hart fehlschlagend)."""
    import base64
    from cra.repo_alignment import _gh_api_json
    for path in ('CHANGELOG.md', 'CHANGELOG', 'docs/CHANGELOG.md'):
        try:
            data = _gh_api_json(f'repos/{owner}/{repo}/contents/{path}')
        except Exception:  # noqa: BLE001
            continue
        if isinstance(data, dict) and data.get('content'):
            try:
                raw = base64.b64decode(data['content']).decode('utf-8', 'replace')
                return raw[:8000]
            except Exception:  # noqa: BLE001
                return ''
    return ''


# ════════════════════════════════════════════════════════════════════
# GitLab (SSRF-validiert)
# ════════════════════════════════════════════════════════════════════

def _gl_project_id(project: str) -> str:
    s = (project or '').strip()
    m = re.match(r'^https?://[^/]+/(.+?)(?:\.git)?/?$', s)
    if m:
        s = m.group(1)
    return s if s.isdigit() else quote_plus(s)


def _gl_get_json(base_url: str, path: str, token: str | None) -> Any:
    from shared.net_validation import safe_get, SSRFError
    base = (base_url or 'https://gitlab.com').rstrip('/')
    url = f'{base}/api/v4/{path.lstrip("/")}'
    headers = {'Accept': 'application/json'}
    if token:
        headers['PRIVATE-TOKEN'] = token
    try:
        r = safe_get(url, headers=headers, timeout=30)
    except SSRFError as e:
        raise RepoChangesError(f'GitLab-URL nicht erlaubt: {e}') from e
    if r.status_code >= 300:
        raise RepoChangesError(f'GitLab API {r.status_code}: {r.text[:200]}')
    return r.json()


def _gitlab_list_versions(base_url: str, project: str, token: str | None,
                          *, limit: int = 50) -> list[VersionRef]:
    pid = _gl_project_id(project)
    out: list[VersionRef] = []
    seen: set[str] = set()
    try:
        releases = _gl_get_json(base_url, f'projects/{pid}/releases?per_page={limit}', token) or []
    except RepoChangesError:
        releases = []
    for rel in releases:
        tag = str(rel.get('tag_name') or '').strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(VersionRef(
            name=tag, typ='release', title=str(rel.get('name') or ''),
            published_at=str(rel.get('released_at') or rel.get('created_at') or ''),
            url=str((rel.get('_links') or {}).get('self') or ''),
        ))
    tags = _gl_get_json(base_url, f'projects/{pid}/repository/tags?per_page={limit}', token) or []
    for t in tags:
        name = str(t.get('name') or '').strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(VersionRef(name=name, typ='tag'))
    if not out:
        raise RepoChangesError(
            'Keine Releases/Tags im GitLab-Repo gefunden (oder kein Zugriff).')
    return out


def _gitlab_diff(base_url: str, project: str, token: str | None,
                 base: str, head: str) -> VersionDiff:
    pid = _gl_project_id(project)
    data = _gl_get_json(
        base_url,
        f'projects/{pid}/repository/compare?from={quote_plus(base)}&to={quote_plus(head)}',
        token,
    )
    commits = []
    for c in (data.get('commits') or []):
        commits.append({
            'sha': str(c.get('short_id') or c.get('id', ''))[:10],
            'message': str(c.get('message') or c.get('title') or '').strip(),
            'author': str(c.get('author_name') or ''),
        })
    files = []
    for d in (data.get('diffs') or []):
        fn = d.get('new_path') or d.get('old_path')
        if fn:
            files.append(str(fn))
    return VersionDiff(base=base, head=head, provider='gitlab',
                       commits=commits, changed_files=files)


# ════════════════════════════════════════════════════════════════════
# Öffentliche API
# ════════════════════════════════════════════════════════════════════

def list_versions(provider: str, repo: str, *, base_url: str = '',
                  token: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Release-/Tag-Liste des verknüpften Repos. Raises RepoChangesError bei
    fehlendem Repo / Zugriffsproblemen (vom Aufrufer als 400/502 zu melden)."""
    if not (repo or '').strip():
        raise RepoChangesError('Kein Repository verknüpft.')
    if provider == 'gitlab':
        refs = _gitlab_list_versions(base_url, repo, token, limit=limit)
    else:
        owner, name = _parse_github_repo(repo)
        refs = _github_list_versions(owner, name, limit=limit)
    return [r.as_dict() for r in refs]


def version_diff(provider: str, repo: str, base: str, head: str, *,
                 base_url: str = '', token: str | None = None) -> dict[str, Any]:
    """Strukturierte Änderungsliste zwischen ``base`` und ``head``."""
    if not (repo or '').strip():
        raise RepoChangesError('Kein Repository verknüpft.')
    if not (base or '').strip() or not (head or '').strip():
        raise RepoChangesError('„base" und „head" sind Pflicht.')
    if provider == 'gitlab':
        diff = _gitlab_diff(base_url, repo, token, base, head)
    else:
        owner, name = _parse_github_repo(repo)
        diff = _github_diff(owner, name, base, head)
    return diff.as_dict()
