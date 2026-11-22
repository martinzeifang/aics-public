"""Gemeinsame Typen für die AI-Act Auto-Fill-Vorschläge (#1020/#1021)."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class FieldSuggestion:
    """Ein Vorschlag für ein einzelnes Pflicht-Doku-Feld."""
    field: str            # z.B. 'intended_purpose'
    value: str            # extrahierter Text
    source_path: str      # z.B. 'README.md' oder 'https://…'
    confidence: float = 0.5  # 0.0–1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def suggestions_to_dict(suggestions: dict[str, FieldSuggestion]) -> dict[str, dict]:
    """Mapping field→FieldSuggestion in ein JSON-fähiges Dict wandeln."""
    return {k: (v.to_dict() if isinstance(v, FieldSuggestion) else v)
            for k, v in (suggestions or {}).items()}
