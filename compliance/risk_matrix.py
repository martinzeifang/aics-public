from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Fixed risk matrix as provided (4x4 -> 1..7)
LIKELIHOOD_LEVELS = [
    "Unwahrscheinlich",
    "Möglich",
    "Wahrscheinlich",
    "Sehr wahrscheinlich",
]

IMPACT_LEVELS = [
    "niedrig",
    "mittel",
    "hoch",
    "sehr hoch",
]

# Legend / interpretation
RISK_LABELS = {
    1: "Nicht relevant",
    2: "Nicht relevant",
    3: "Vernachlässigbar",
    4: "Gering",
    5: "Relevant",
    6: "Äußerst relevant",
    7: "existenzbedrohend",
}


def _norm(s: str) -> str:
    return (s or "").strip().casefold()


def _map_likelihood(s: str) -> Optional[int]:
    n = _norm(s)
    if not n:
        return None
    # Accept minor variants/umlauts
    synonyms = {
        "unwahrscheinlich": 1,
        "moeglich": 2,
        "möglich": 2,
        "wahrscheinlich": 3,
        "sehr wahrscheinlich": 4,
        "sehr-wahrscheinlich": 4,
    }
    if n in synonyms:
        return synonyms[n]
    return None


def _map_impact(s: str) -> Optional[int]:
    n = _norm(s)
    if not n:
        return None
    synonyms = {
        "niedrig": 1,
        "mittel": 2,
        "hoch": 3,
        "sehr hoch": 4,
        "sehr-hoch": 4,
    }
    if n in synonyms:
        return synonyms[n]
    return None


def compute_risk_score(likelihood: str, impact: str) -> Optional[int]:
    """Compute risk score 1..7 from fixed 4x4 matrix.

    Matrix is effectively (x_index + y_index - 1) where both indices are 1..4.
    """
    x = _map_likelihood(likelihood)
    y = _map_impact(impact)
    if x is None or y is None:
        return None
    return int(x + y - 1)


def risk_label(score: int) -> str:
    return RISK_LABELS.get(int(score), "")
