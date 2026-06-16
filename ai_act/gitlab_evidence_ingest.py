"""Ingest GitLab repository evidence into the shared Evidence DB.

We ingest a small set of well-known files (policies, CI config, docs) by fetching
their raw content via the GitLab API and storing them as web evidence documents.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path

import requests


def _token(env_name: str) -> str:
    name = (env_name or "GITLAB_TOKEN").strip() or "GITLAB_TOKEN"
    tok = (os.getenv(name) or "").strip()
    if not tok:
        raise RuntimeError(f"GitLab Token fehlt. Bitte Env Var '{name}' setzen.")
    return tok


def _api(base_url: str, path: str) -> str:
    base = (base_url or "https://gitlab.com").rstrip("/")
    return f"{base}/api/v4/{path.lstrip('/')}"


def _parse_project(project: str) -> str:
    s = (project or "").strip()
    if not s:
        raise ValueError("GitLab Projekt fehlt (group/project oder URL)")
    m = re.match(r"^https?://[^/]+/(.+?)(?:\.git)?/?$", s)
    if m:
        s = m.group(1)
    if s.isdigit():
        return s
    return urllib.parse.quote_plus(s)


def _file_raw_url(base_url: str, project: str, file_path: str, ref: str) -> str:
    proj = _parse_project(project)
    fp = urllib.parse.quote(file_path.lstrip("/"), safe="")
    rf = urllib.parse.quote(ref or "", safe="")
    return _api(base_url, f"projects/{proj}/repository/files/{fp}/raw?ref={rf}")


def ingest_gitlab_repo_files(
    *,
    base_url: str,
    token_env: str,
    project: str,
    ref: str,
    evidence_db_path: Path,
    projekt_name: str,
) -> list[str]:
    """Fetch raw text for common files and ingest as web evidence documents.

    Returns list of evidence doc IDs.
    """
    from evidence import db as ev_db
    from evidence.chunking import chunk_text

    headers = {"PRIVATE-TOKEN": _token(token_env)}
    candidates = [
        "README.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        ".gitlab-ci.yml",
        "CHANGELOG.md",
        "MODEL_CARD.md",
        "model_card.md",
        "THREAT_MODEL.md",
        "threat_model.md",
        "RISK_REGISTER.md",
        "risk_register.md",
        "RUNBOOK.md",
        "INCIDENT_RESPONSE.md",
        "docs/index.md",
    ]

    doc_ids: list[str] = []
    for fp in candidates:
        url = _file_raw_url(base_url, project, fp, ref)
        r = requests.get(url, headers=headers, timeout=60)
        if r.status_code == 404:
            continue
        if r.status_code != 200:
            # Keep going; ingest is best-effort.
            continue
        text = r.text or ""
        if not text.strip():
            continue
        doc = ev_db.add_web_document(
            evidence_db_path,
            url=url,
            title=fp,
            text=text,
            doc_type="repo-file",
            owner=str(project),
            version=str(ref or ""),
            tags=["ai-act", "repo", "gitlab", "file"],
            firmen_id=projekt_name,
        )
        try:
            chunks = chunk_text(text)
            ev_db.replace_chunks(
                evidence_db_path,
                doc.id,
                [(c.idx, c.text) for c in chunks],
                citation_kind="web",
            )
        except Exception:
            pass
        doc_ids.append(doc.id)

    return doc_ids
