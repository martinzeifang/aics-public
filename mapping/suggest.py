"""Anforderung → passende Nachweis-Abschnitte vorschlagen (Desktop-Richtung).

Dieses Modul fragt **je Anforderung**, welche Abschnitte sie stützen; es bedient
die Tkinter-Oberflächen (`ai_compliance_suite/gui.py`, `cra/gui_module.py`,
`dsgvo/gui_module.py`). Die Web-Anwendung geht seit #1861 die andere Richtung —
**je Dokument gegen den Katalog** (`evidence/erschliessung.py`), weil ein
Dokument gegen 130 Anforderungen ein Lauf ist und nicht 130. Beide schreiben in
dasselbe Register (`evidence_mappings_*`).

#1861: Der Transport läuft jetzt über die gemeinsame Engine (#1841). Vorher
sprach dieses Modul direkt mit dem Provider — ohne Ausgabebudget, ohne
Temperatur, ohne `format=json`, ohne Egress-Bestätigung, ohne Audit-Eintrag.
Es stand mit genau diesem Grund auf der Warteliste des Engine-Wächters.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


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

    # #1861/#1841: über die Engine statt am Provider vorbei. `suite_cfg` bleibt
    # in der Signatur, damit die vier Tkinter-Aufrufer unverändert laufen — die
    # Provider-Wahl trifft jetzt die zentrale Dispatch-Schicht.
    from shared.ki_engine import (OHNE_OBJEKT, KiAuftrag, KiNichtVerfuegbar,
                                  ki_lauf)
    try:
        erg = ki_lauf(KiAuftrag(
            prompt=prompt,
            # Der Lauf macht Vorschläge, die ein Mensch freigibt — er erzeugt
            # keinen Inhalt an einem Fachobjekt.
            herkunft=OHNE_OBJEKT,
            system=system,
            antwortform="json",
            aufgabe="erschliessung",
            menge=len(ctx_lines),
            vertraulichkeit="sensibel",   # Kundenunterlagen
            kontext=f"mapping-vorschlag:{rid}",
        ))
    except KiNichtVerfuegbar as e:
        raise MappingSuggestError(str(e)) from e
    if not erg.ok:
        raise MappingSuggestError(erg.fehler or "KI-Aufruf fehlgeschlagen")

    data = erg.parsed if isinstance(erg.parsed, dict) else _parse_json_strict(erg.text)
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
