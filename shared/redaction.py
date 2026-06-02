"""Best-effort secret redaction for text.

Goal: prevent accidental persistence/logging of credentials embedded in issue bodies/comments.
This is heuristic and not a substitute for proper secrets management.
"""

from __future__ import annotations

import re


_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # GitHub tokens
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"), "ghp_[REDACTED]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "github_pat_[REDACTED]"),
    # GitLab tokens
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"), "glpat-[REDACTED]"),
    # OpenAI-style keys
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "sk-[REDACTED]"),
    # Google API key
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"), "AIza[REDACTED]"),
    # Bearer tokens
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-\._~\+\/]+=*\b"), "Bearer [REDACTED]"),
    # Generic long hex (very conservative to avoid too many false positives)
    (re.compile(r"\b[0-9a-f]{64}\b", re.IGNORECASE), "[REDACTED_HEX_64]"),
]


def redact_secrets(text: str) -> str:
    if not text:
        return ""
    out = text
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    return out
