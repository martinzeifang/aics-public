"""Evidence library shared across modules."""

from .extract import EvidenceExtractError, extract_text

__all__ = [
    "EvidenceExtractError",
    "extract_text",
]
