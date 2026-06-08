from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ai_compliance_suite.ai.provider import AITextRequest, provider_from_config


@dataclass(frozen=True)
class Citation:
    doc_id: str
    chunk: int


@dataclass(frozen=True)
class SuggestedMapping:
    claim: str
    citations: list[Citation]
    confidence: float
    rationale: str


class MappingSuggestError(RuntimeError):
    pass


def suggest_mappings(
    *,
    suite_cfg: dict[str, Any],
    requirement_id: str,
    requirement_title: str,
    requirement_text: str,
    evidence_chunks: list[dict[str, Any]],
    max_suggestions: int = 6,
) -> list[SuggestedMapping]:
    """Suggest evidence mappings for a requirement.

    evidence_chunks items must contain:
    - doc_id: str
    - chunk_idx: int
    - text: str

    Returns structured suggestions. Raises MappingSuggestError on invalid output.
    """

    rid = (requirement_id or "").strip()
    if not rid:
        raise MappingSuggestError("requirement_id is required")

    ctx_lines: list[str] = []
    for c in evidence_chunks:
        doc_id = str(c.get("doc_id", "")).strip()
        chunk_idx = int(c.get("chunk_idx", 0) or 0)
        text = str(c.get("text", "")).strip()
        if not doc_id or chunk_idx <= 0 or not text:
            continue
        ctx_lines.append(f"[doc_id={doc_id} chunk={chunk_idx}]\n{text}")

    if not ctx_lines:
        return []

    system = (
        "You are a compliance analyst. Only use the provided EVIDENCE chunks. "
        "Do not invent facts. If evidence is insufficient, return an empty list."
    )

    schema_hint = {
        "requirement_id": rid,
        "suggestions": [
            {
                "claim": "string (one concrete claim that the evidence supports)",
                "citations": [{"doc_id": "string", "chunk": 1}],
                "confidence": 0.0,
                "rationale": "short explanation based on cited chunks",
            }
        ],
    }

    prompt = (
        "EVIDENCE:\n"
        + "\n\n".join(ctx_lines[:60])
        + "\n\nREQUIREMENT:\n"
        + f"ID: {rid}\n"
        + f"TITLE: {(requirement_title or '').strip()}\n"
        + f"TEXT: {(requirement_text or '').strip()}\n\n"
        + f"Return STRICT JSON only (no markdown). Schema example:\n{json.dumps(schema_hint, ensure_ascii=False, indent=2)}\n\n"
        + f"Rules:\n"
        + f"- suggestions must be a JSON array\n"
        + f"- max {int(max_suggestions)} suggestions\n"
        + "- citations must reference doc_id/chunk from EVIDENCE headers\n"
        + "- confidence is 0..1\n"
        + "- if nothing fits, return {\"requirement_id\": ..., \"suggestions\": []}"
    )

    provider = provider_from_config(suite_cfg)
    resp = provider.generate_text(AITextRequest(system=system, prompt=prompt))

    data = _parse_json_strict(resp.text)
    if not isinstance(data, dict):
        raise MappingSuggestError("AI output is not a JSON object")

    if str(data.get("requirement_id", "")).strip() != rid:
        raise MappingSuggestError("AI output requirement_id mismatch")

    suggestions = data.get("suggestions")
    if not isinstance(suggestions, list):
        raise MappingSuggestError("AI output 'suggestions' must be a list")

    out: list[SuggestedMapping] = []
    for s in suggestions[: max(0, int(max_suggestions))]:
        if not isinstance(s, dict):
            continue
        claim = str(s.get("claim", "")).strip()
        rationale = str(s.get("rationale", "")).strip()
        try:
            conf = float(s.get("confidence", 0.0))
        except Exception:
            conf = 0.0
        conf = max(0.0, min(1.0, conf))

        cits_raw = s.get("citations", [])
        citations: list[Citation] = []
        if isinstance(cits_raw, list):
            for c in cits_raw[:8]:
                if not isinstance(c, dict):
                    continue
                doc_id = str(c.get("doc_id", "")).strip()
                try:
                    chunk = int(c.get("chunk", 0) or 0)
                except Exception:
                    chunk = 0
                if doc_id and chunk > 0:
                    citations.append(Citation(doc_id=doc_id, chunk=chunk))

        if claim and citations:
            out.append(
                SuggestedMapping(
                    claim=claim,
                    citations=citations,
                    confidence=conf,
                    rationale=rationale,
                )
            )

    return out


def _parse_json_strict(s: str) -> Any:
    """Parse JSON from AI output.

    We accept either pure JSON or JSON surrounded by whitespace.
    We intentionally do not attempt to parse markdown fences.
    """

    raw = (s or "").strip()
    if not raw:
        raise MappingSuggestError("Empty AI output")
    try:
        return json.loads(raw)
    except Exception as e:
        raise MappingSuggestError("AI output is not valid JSON") from e
