from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from .textnorm import normalize_text


@dataclass(frozen=True)
class Match:
    score: float
    payload: dict


def top_matches(query: str, candidates: list[dict], *, text_key: str, top_k: int = 5) -> list[Match]:
    qn = normalize_text(query)
    scored: list[Match] = []
    if not qn:
        return []
    for c in candidates:
        t = c.get(text_key) or ""
        tn = normalize_text(t)
        if not tn:
            continue
        score = float(fuzz.token_set_ratio(qn, tn))
        scored.append(Match(score=score, payload=c))
    scored.sort(key=lambda m: m.score, reverse=True)
    return scored[:top_k]
