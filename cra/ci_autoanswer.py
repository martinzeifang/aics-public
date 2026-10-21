"""Deterministic CRA auto-answer rules from CI evidence.

This is intentionally conservative: we only infer what CI artifacts can support.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CRAAutoSuggestion:
    field_id: str
    score: int
    kommentar: str
    confidence: float
    rationale: str
    citations: list[dict]


def _first_chunk_citation(evidence_db_path: Path, doc_id: str) -> list[dict]:
    from evidence import db as ev_db

    chunks = ev_db.list_chunks(evidence_db_path, doc_id)
    if not chunks:
        return []
    return [{"doc_id": doc_id, "chunk_idx": int(chunks[0].chunk_idx)}]


def _load_osv_stats(doc_path: Path) -> tuple[int, int]:
    """Return (vuln_count, affected_packages_count) from osv results json.

    We only use simple counting heuristics to avoid coupling to a specific schema.
    """
    try:
        data = json.loads(doc_path.read_text(encoding="utf-8"))
    except Exception:
        return 0, 0

    # Common shapes:
    # - {"results": [{"packages": [...], "vulnerabilities": [...]}, ...]}
    # - {"vulnerabilities": [...]}
    vuln = 0
    pkgs = 0

    if isinstance(data, dict):
        if isinstance(data.get("vulnerabilities"), list):
            vuln += len(data.get("vulnerabilities"))
        if isinstance(data.get("results"), list):
            for r in data["results"]:
                if isinstance(r, dict):
                    vs = r.get("vulnerabilities")
                    if isinstance(vs, list):
                        vuln += len(vs)
                    ps = r.get("packages")
                    if isinstance(ps, list):
                        pkgs += len(ps)

    return int(vuln), int(pkgs)


def suggest_from_ci_evidence(
    *,
    repo: str,
    evidence_db_path: Path,
) -> list[CRAAutoSuggestion]:
    from evidence import db as ev_db

    docs = ev_db.list_documents(evidence_db_path)
    # Find newest docs by kind for this repo.
    by_kind: dict[str, object] = {}
    for d in docs:
        if d.doc_type != "ci-artifact":
            continue
        if (d.owner or "") != repo:
            continue
        tags = set(d.tags or [])
        if "cra" not in tags or "ci" not in tags:
            continue
        kind = ""
        for k in ("sbom", "osv", "evidence_pack"):
            if k in tags:
                kind = k
                break
        if not kind:
            continue
        prev = by_kind.get(kind)
        if not prev or getattr(prev, "updated_at", 0) < d.updated_at:
            by_kind[kind] = d

    out: list[CRAAutoSuggestion] = []

    sbom = by_kind.get("sbom")
    if sbom:
        cit = _first_chunk_citation(evidence_db_path, sbom.id)  # type: ignore[attr-defined]
        out.append(
            CRAAutoSuggestion(
                field_id="AI2-02",
                score=4,
                kommentar="CI erzeugt eine CycloneDX-SBOM als Build-Artefakt.",
                confidence=1.0,
                rationale="SBOM-Artifact (CycloneDX) im CI gefunden.",
                citations=cit,
            )
        )

    osv = by_kind.get("osv")
    if osv:
        p = Path(getattr(osv, "stored_path", ""))
        vuln_count, pkg_count = _load_osv_stats(p) if p.exists() else (0, 0)
        cit = _first_chunk_citation(evidence_db_path, osv.id)  # type: ignore[attr-defined]
        out.append(
            CRAAutoSuggestion(
                field_id="AI2-01",
                score=3,
                kommentar="CI fuehrt OSV-Scanning auf Abhaengigkeiten aus.",
                confidence=1.0,
                rationale="OSV-Scan Ergebnis als CI-Artifact vorhanden.",
                citations=cit,
            )
        )
        out.append(
            CRAAutoSuggestion(
                field_id="AI2-04",
                score=3,
                kommentar="Automatisierter SCA/Vulnerability-Scan ist in der CI vorhanden (OSV).",
                confidence=1.0,
                rationale="OSV-Scan im CI vorhanden.",
                citations=cit,
            )
        )
        if vuln_count == 0:
            ai1_score = 3
            ai1_txt = "OSV-Scan meldet keine Findings in `requirements.txt` (nur Abhaengigkeiten)."
        else:
            ai1_score = 2
            ai1_txt = f"OSV-Scan meldet {vuln_count} Finding(s) (Pakete: {pkg_count})."
        out.append(
            CRAAutoSuggestion(
                field_id="AI1-02",
                score=ai1_score,
                kommentar=ai1_txt,
                confidence=0.8,
                rationale="Ableitung aus Dependency-Vulnerability-Scan (SCA).",
                citations=cit,
            )
        )

    return out
