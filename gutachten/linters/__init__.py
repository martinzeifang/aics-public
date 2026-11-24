"""G0-2 — Geteilte Linter-Module für beide Gutachten-Typen."""
from __future__ import annotations

from typing import Any

from . import sprache as _sprache
from . import cross_ref as _cross_ref
from . import anonymisierung as _anonym


def lint(text: str, context: str = "gerichts", kind: str = "sprache") -> list[dict[str, Any]]:
    """Universal-Linter-Einstiegspunkt.

    context: 'audit' | 'gerichts' — beeinflusst Strenge des Sprach-Linters.
    kind:    'sprache' | 'cross_ref' | 'anonym' | 'alle'
    """
    text = text or ""
    out: list[dict[str, Any]] = []
    kinds = ["sprache", "cross_ref", "anonym"] if kind == "alle" else [kind]

    if "sprache" in kinds:
        out.extend(_sprache.lint(text, context=context))
    if "anonym" in kinds:
        out.extend(_anonym.lint(text))
    if "cross_ref" in kinds:
        # cross_ref braucht strukturierten Kontext, hier nur Text → kein Hint
        pass
    return out


__all__ = ["lint", "_sprache", "_cross_ref", "_anonym"]
