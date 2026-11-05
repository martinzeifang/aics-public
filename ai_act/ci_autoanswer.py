"""Deterministic AI Act auto-suggestions derived from CI evidence.

Conservative by design: we only infer what CI artifacts can support.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AIActAutoSuggestion:
    field_id: str
    score: int
    kommentar: str
    confidence: float
    rationale: str
    citations: list[dict[str, Any]]


def _first_chunk_citation(evidence_db_path: Path, doc_id: str) -> list[dict[str, Any]]:
    from evidence import db as ev_db

    chunks = ev_db.list_chunks(evidence_db_path, doc_id)
    if not chunks:
        return []
    return [{"doc_id": doc_id, "chunk_idx": int(chunks[0].chunk_idx)}]


def suggest_from_ci_evidence(
    *,
    repo: str,
    branch: str,
    evidence_db_path: Path,
    projekt_name: str,
) -> list[AIActAutoSuggestion]:
    """Create suggestions for AI Act requirements from CI artifacts in evidence DB."""
    from evidence import db as ev_db

    docs = ev_db.list_documents(evidence_db_path, firmen_id=projekt_name)
    by_kind: dict[str, Any] = {}

    def _doc_kind(d: Any) -> str:
        tags = set(getattr(d, "tags", []) or [])
        if "sbom" in tags:
            return "sbom"
        if "osv" in tags:
            return "osv"
        if "evidence_pack" in tags:
            return "evidence_pack"
        # fallback heuristics by filename
        fn = str(getattr(d, "filename", "") or "").lower()
        if "sbom" in fn or fn.endswith(".cdx.json") or fn.endswith(".cyclonedx.json"):
            return "sbom"
        if "osv" in fn:
            return "osv"
        if "evidence" in fn:
            return "evidence_pack"
        return ""

    for d in docs:
        if getattr(d, "doc_type", "") != "ci-artifact":
            continue
        if (getattr(d, "owner", "") or "") != repo:
            continue
        tags = set(getattr(d, "tags", []) or [])
        if "ai-act" not in tags or "ci" not in tags or "github" not in tags:
            continue
        kind = _doc_kind(d)
        if not kind:
            continue
        prev = by_kind.get(kind)
        if not prev or int(getattr(prev, "updated_at", 0) or 0) < int(getattr(d, "updated_at", 0) or 0):
            by_kind[kind] = d

    out: list[AIActAutoSuggestion] = []

    sbom = by_kind.get("sbom")
    if sbom:
        cit = _first_chunk_citation(evidence_db_path, str(getattr(sbom, "id", "")))
        out.append(
            AIActAutoSuggestion(
                field_id="AIA-HR-07",
                score=4,
                kommentar="CI erzeugt eine SBOM (z. B. CycloneDX) als Build-Artefakt.",
                confidence=1.0,
                rationale="SBOM-Artifact im CI vorhanden.",
                citations=cit,
            )
        )

    osv = by_kind.get("osv")
    if osv:
        cit = _first_chunk_citation(evidence_db_path, str(getattr(osv, "id", "")))
        out.append(
            AIActAutoSuggestion(
                field_id="AIA-HR-07",
                score=3,
                kommentar="CI fuehrt automatisierte Vulnerability-/Dependency-Scans (OSV) aus.",
                confidence=1.0,
                rationale="OSV-Scan Ergebnis als CI-Artifact vorhanden.",
                citations=cit,
            )
        )

    evp = by_kind.get("evidence_pack")
    if evp:
        cit = _first_chunk_citation(evidence_db_path, str(getattr(evp, "id", "")))
        out.append(
            AIActAutoSuggestion(
                field_id="AIA-HR-04",
                score=2,
                kommentar="CI erstellt ein Evidence Pack als Artefakt (Hinweis auf Record-Keeping/Logging-Nachweise).",
                confidence=0.85,
                rationale="Evidence-Pack Artifact im CI vorhanden.",
                citations=cit,
            )
        )

    # Keep API stable; currently branch is informational (UI shows it) but not used.
    _ = branch
    return out
