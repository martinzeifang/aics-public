"""Auto-Prefill Engine: bewertet Compliance-Anforderungen anhand von Evidence-Chunks."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


# ── Typen ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PrefillField:
    """Eine Compliance-Anforderung, die vorausgefüllt werden soll."""
    id: str
    titel: str
    beschreibung: str = ""
    kapitel: str = ""


@dataclass
class PrefillSuggestion:
    """Ergebnis eines KI-Vorschlags für eine Anforderung."""
    field_id: str
    score: int              # 0–5
    kommentar: str
    confidence: float       # 0.0–1.0
    rationale: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    suggested_at: int = field(default_factory=lambda: int(time.time()))
    suggestion_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class PrefillError(RuntimeError):
    pass


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM = (
    "Du bist ein Compliance-Analyst. "
    "Bewertige Compliance-Anforderungen AUSSCHLIESSLICH auf Basis der bereitgestellten "
    "Nachweise (EVIDENCE). Erfinde keine Fakten. "
    "Antworte immer auf Deutsch."
)

_BEWERTUNG_SKALA = {
    0: "Nicht bewertet",
    1: "Nicht vorhanden",
    2: "In Planung",
    3: "Teilweise umgesetzt",
    4: "Überwiegend umgesetzt",
    5: "Vollständig umgesetzt",
}


def _build_prompt(
    field: PrefillField,
    evidence_chunks: list[dict[str, Any]],
) -> str:
    skala_text = "\n".join(f"  {k} = {v}" for k, v in _BEWERTUNG_SKALA.items())

    ctx_lines: list[str] = []
    for c in evidence_chunks[:300]:
        doc_id = str(c.get("doc_id", ""))
        chunk_idx = int(c.get("chunk_idx", 0) or 0)
        text = str(c.get("text", "")).strip()
        if doc_id and text:
            ctx_lines.append(f"[doc={doc_id} chunk={chunk_idx}]\n{text}")

    evidence_block = "\n\n".join(ctx_lines) if ctx_lines else "(keine Nachweise vorhanden)"

    schema = json.dumps({
        "field_id": field.id,
        "score": 0,
        "kommentar": "Kurze Begründung auf Deutsch (max. 3 Sätze)",
        "confidence": 0.0,
        "rationale": "Welche Nachweise belegen den Score",
        "citations": [{"doc_id": "string", "chunk_idx": 0}],
    }, ensure_ascii=False, indent=2)

    return (
        f"ANFORDERUNG\n"
        f"ID: {field.id}\n"
        f"Titel: {field.titel}\n"
        f"Beschreibung: {field.beschreibung}\n"
        f"Kapitel: {field.kapitel}\n\n"
        f"BEWERTUNGSSKALA\n{skala_text}\n\n"
        f"NACHWEISE\n{evidence_block}\n\n"
        f"AUFGABE\n"
        f"Bewerte diese Anforderung auf der Skala 0–5 basierend auf den Nachweisen.\n"
        f"Antworte AUSSCHLIESSLICH mit einem JSON-Objekt exakt in dieser Form:\n"
        f"{schema}"
    )


# ── Engine ────────────────────────────────────────────────────────────────────

def run_prefill(
    suite_cfg: dict[str, Any],
    fields: list[PrefillField],
    evidence_chunks: list[dict[str, Any]],
    *,
    on_progress: Any = None,  # Callable[[int, int, str], None] | None
) -> list[PrefillSuggestion]:
    """Bewerte Compliance-Anforderungen mit KI anhand von Evidence-Chunks.

    Args:
        suite_cfg:       Suite-Konfiguration (für AI-Provider-Auswahl).
        fields:          Liste der zu bewertenden Anforderungen.
        evidence_chunks: Liste von {'doc_id', 'chunk_idx', 'text'}.
        on_progress:     Optionaler Callback(done, total, field_id).

    Returns:
        Liste von PrefillSuggestion (nur für erfolgreich bewertete Felder).
    """
    from ai_compliance_suite.ai.provider import AITextRequest, provider_from_config

    if not fields or not evidence_chunks:
        return []

    try:
        provider = provider_from_config(suite_cfg)
    except Exception as exc:
        raise PrefillError(f"KI-Provider konnte nicht initialisiert werden: {exc}") from exc

    results: list[PrefillSuggestion] = []

    for i, f in enumerate(fields):
        if on_progress:
            on_progress(i, len(fields), f.id)

        prompt = _build_prompt(f, evidence_chunks)
        req = AITextRequest(system=_SYSTEM, prompt=prompt)

        try:
            resp = provider.generate_text(req)
            raw = resp.text.strip()
        except Exception as exc:
            continue  # Skip field on provider error

        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(
                l for l in lines
                if not l.strip().startswith("```")
            )

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON object from response
            import re
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                continue
            try:
                data = json.loads(m.group(0))
            except Exception:
                continue

        score = int(data.get("score", 0))
        if not 0 <= score <= 5:
            score = 0

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        citations = data.get("citations", [])
        if not isinstance(citations, list):
            citations = []

        results.append(PrefillSuggestion(
            field_id=f.id,
            score=score,
            kommentar=str(data.get("kommentar", ""))[:500],
            confidence=confidence,
            rationale=str(data.get("rationale", ""))[:500],
            citations=[
                {"doc_id": str(c.get("doc_id", "")), "chunk_idx": int(c.get("chunk_idx", 0))}
                for c in citations
                if isinstance(c, dict)
            ],
        ))

    return results
