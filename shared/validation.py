"""Zentrale Input-Validierung (OWASP-PC-C5).

Ziel: Konsistente, defensive Validierung für Eingaben wie Repo/Branch/URLs/Env-Var.
Die Suite ist Desktop-lokal, aber Eingaben steuern Dateizugriffe und externe CLI/API-Aufrufe.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse


_RE_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_RE_ENV = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")
_RE_REPO_PATH = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def validate_branch_ref(value: str, *, field: str = "Branch/Ref") -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError(f"{field} fehlt.")
    if " " in v or "\t" in v or "\n" in v:
        raise ValueError(f"{field} darf keine Leerzeichen enthalten.")
    if ".." in v:
        raise ValueError(f"{field} enthält ungültige Sequenz '..'.")
    if v.endswith("/"):
        raise ValueError(f"{field} darf nicht mit '/' enden.")
    if not _RE_BRANCH.match(v):
        raise ValueError(f"{field} hat ungültige Zeichen.")
    return v


def validate_env_var_name(value: str, *, field: str = "Token Env") -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError(f"{field} fehlt.")
    if not _RE_ENV.match(v):
        raise ValueError(f"{field} muss wie ENV_VAR aussehen (A-Z, 0-9, _).")
    return v


def validate_http_url(value: str, *, field: str = "URL", allow_http: bool = True) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError(f"{field} fehlt.")
    if any(ch.isspace() for ch in v):
        raise ValueError(f"{field} darf keine Leerzeichen enthalten.")
    if len(v) > 500:
        raise ValueError(f"{field} ist zu lang.")
    p = urlparse(v)
    if p.scheme not in (("https", "http") if allow_http else ("https",)):
        raise ValueError(f"{field} muss mit http(s) beginnen.")
    if not p.netloc:
        raise ValueError(f"{field} ist ungültig.")
    return v.rstrip("/")


def normalize_repo(provider: str, repo: str) -> str:
    """Normalisiert Repo/Projekt-Eingaben.

    - GitHub: akzeptiert org/repo oder https://github.com/org/repo(.git)
    - GitLab: akzeptiert group/project oder https://gitlab.com/group/project
    """
    prov = (provider or "").strip().lower() or "github"
    raw = (repo or "").strip()
    if not raw:
        raise ValueError("Repo / Projekt fehlt.")
    if any(ch.isspace() for ch in raw):
        raise ValueError("Repo / Projekt darf keine Leerzeichen enthalten.")

    if raw.startswith("http://") or raw.startswith("https://"):
        p = urlparse(raw)
        path = (p.path or "").strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        # GitHub URLs sometimes include extra segments; take first two.
        parts = [x for x in path.split("/") if x]
        if prov == "github":
            if len(parts) < 2:
                raise ValueError("GitHub Repo-URL muss /org/repo enthalten.")
            path = f"{parts[0]}/{parts[1]}"
        else:
            # GitLab can be nested groups; keep full path but require at least 2 segments.
            if len(parts) < 2:
                raise ValueError("GitLab Projekt-URL muss /group/project enthalten.")
            path = "/".join(parts)
        raw = path

    if prov == "github":
        if not _RE_REPO_PATH.match(raw):
            raise ValueError("GitHub Repo muss wie org/repo aussehen.")
        return raw

    # GitLab: allow nested groups; validate segments.
    segs = [s for s in raw.split("/") if s]
    if len(segs) < 2:
        raise ValueError("GitLab Projekt muss mindestens group/project enthalten.")
    for s in segs:
        if not re.match(r"^[A-Za-z0-9_.-]+$", s):
            raise ValueError("GitLab Projekt enthält ungültige Zeichen.")
    return "/".join(segs)
