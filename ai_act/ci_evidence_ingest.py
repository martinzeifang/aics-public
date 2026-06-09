"""Import CI artifacts into Evidence DB (AI Act module).

Uses GitHub Actions via `gh` CLI.

Design note:
- Evidence DB currently supports scoping via `firmen_id`. For AI Act we scope by project name.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def _gh_json(args: list[str]) -> Any:
    p = subprocess.run(
        ["gh", *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "gh failed").strip())
    out = (p.stdout or "").strip()
    return json.loads(out) if out else None


def _latest_success_run(repo: str, branch: str) -> tuple[int, str] | None:
    runs = _gh_json(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--branch",
            branch,
            "--limit",
            "20",
            "--json",
            "databaseId,conclusion,headSha",
        ]
    )
    if not isinstance(runs, list):
        return None
    for r in runs:
        if isinstance(r, dict) and r.get("conclusion") == "success":
            try:
                return int(r.get("databaseId")), str(r.get("headSha") or "")
            except Exception:
                continue
    return None


def _download_all_artifacts(repo: str, run_id: int, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(
        [
            "gh",
            "run",
            "download",
            str(run_id),
            "--repo",
            repo,
            "--dir",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "gh run download failed").strip())
    return [p for p in out_dir.rglob("*") if p.is_file()]


def ingest_latest_github_ci_artifacts(
    *,
    repo: str,
    branch: str,
    evidence_db_path: Path,
    projekt_name: str,
) -> list[str]:
    """Download latest successful run artifacts and add them to Evidence DB.

    Returns list of evidence document IDs.
    """
    from evidence import db as ev_db
    from evidence.chunking import chunk_text
    from evidence.extract import extract_text

    run = _latest_success_run(repo, branch)
    if not run:
        return []
    run_id, head_sha = run

    doc_ids: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ai-act-ci-ingest-") as td:
        base = Path(td)
        files = _download_all_artifacts(repo, run_id, base / f"run_{run_id}")
        for f in files:
            name_l = f.name.lower()
            kind = ""
            if "sbom" in name_l or name_l.endswith(".cdx.json") or name_l.endswith(".cyclonedx.json"):
                kind = "sbom"
            elif "osv" in name_l or "osv-results" in name_l or "osv_scanner" in name_l:
                kind = "osv"
            elif "evidence" in name_l or "evidence-pack" in name_l:
                kind = "evidence_pack"

            ev = ev_db.add_document(
                evidence_db_path,
                f,
                doc_type="ci-artifact",
                owner=repo,
                version=head_sha,
                tags=["ai-act", "ci", "github"] + ([kind] if kind else []),
                firmen_id=projekt_name,
            )
            try:
                text = extract_text(Path(ev.stored_path))
                ev_db.upsert_extracted_text(evidence_db_path, ev.id, text)
                chunks = chunk_text(text)
                ev_db.replace_chunks(
                    evidence_db_path,
                    ev.id,
                    [(c.idx, c.text) for c in chunks],
                    citation_kind="ci",
                )
            except Exception:
                pass
            doc_ids.append(ev.id)

    return doc_ids
