"""Import CI artifacts (SBOM/OSV/Evidence Pack) into Evidence DB.

Current implementation targets GitHub Actions via `gh` CLI.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile

logger = logging.getLogger(__name__)
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.audit import audit_event


@dataclass(frozen=True)
class IngestedArtifact:
    kind: str
    local_path: Path
    run_id: int
    head_sha: str


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


def _latest_success_run_id(repo: str, workflow: str, branch: str) -> tuple[int, str] | None:
    runs = _gh_json(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow,
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


def _download_artifact(repo: str, run_id: int, artifact_name: str, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(
        [
            "gh",
            "run",
            "download",
            str(run_id),
            "--repo",
            repo,
            "--name",
            artifact_name,
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
    firmen_id: str = "",
) -> list[str]:
    """Download latest successful CI artifacts and add them to Evidence DB.

    Returns list of evidence document IDs.
    """
    from evidence import db as ev_db
    from evidence.chunking import chunk_text
    from evidence.extract import extract_text

    workflows = [
        # workflow file, artifact name, kind
        ("cra-sbom.yml", "cra-sbom-cyclonedx", "sbom"),
        ("cra-osv-scan.yml", "cra-osv-results", "osv"),
        ("cra-evidence-pack.yml", "cra-evidence-pack", "evidence_pack"),
    ]

    doc_ids: list[str] = []
    audit_event(
        "cra.ci_ingest",
        module="cra",
        outcome="start",
        details={"repo": repo, "branch": branch, "evidence_db": str(evidence_db_path), "firmen_id": firmen_id},
    )
    try:
        with tempfile.TemporaryDirectory(prefix="cra-ci-ingest-") as td:
            base = Path(td)
            for wf, artifact, kind in workflows:
                run = _latest_success_run_id(repo, wf, branch)
                if not run:
                    continue
                run_id, head_sha = run
                files = _download_artifact(repo, run_id, artifact, base / f"{kind}_{run_id}")
                for f in files:
                    # Keep the original file name in the evidence library.
                    ev = ev_db.add_document(
                        evidence_db_path,
                        f,
                        doc_type="ci-artifact",
                        owner=repo,
                        version=head_sha,
                        tags=["cra", "ci", "github", kind],
                        firmen_id=firmen_id,
                    )
                    # Extract + chunk immediately so the prefill/mapping UI can cite it.
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
                    except Exception as exc:
                        logger.warning("Failed to ingest CI artifact %s: %s", ev.id, exc)
                    doc_ids.append(ev.id)
    except Exception as exc:
        audit_event(
            "cra.ci_ingest",
            module="cra",
            outcome="fail",
            details={"repo": repo, "error": str(exc)},
        )
        raise

    audit_event(
        "cra.ci_ingest",
        module="cra",
        outcome="success",
        details={"repo": repo, "documents": len(doc_ids)},
    )
    return doc_ids
