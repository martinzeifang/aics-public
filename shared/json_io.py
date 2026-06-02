"""Safe JSON import helpers for manual answer pasting.

Risk #195 mitigation goals:
- bound input size
- reject non-JSON / wrong root types
- basic schema/type validation utilities
- audit logging for parse failures (without leaking content)
"""

from __future__ import annotations

import json
import re
from typing import Any

from shared.audit import audit_event
from shared.redaction import redact_secrets
from security_utils import sanitize_untrusted_text


MAX_JSON_CHARS_DEFAULT = 2 * 1024 * 1024  # 2MB


def safe_read_json_file(path: str | Any, *, context: str, max_bytes: int = 2 * 1024 * 1024) -> Any:
    """Read JSON file with size bounds and safe parsing."""
    from pathlib import Path

    p = Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(str(p))
    if p.stat().st_size > max_bytes:
        audit_event(
            "json.import",
            module="json_io",
            outcome="fail",
            details={"context": context, "reason": "file_too_large", "path": str(p), "bytes": int(p.stat().st_size)},
        )
        raise ValueError(f"JSON-Datei zu groß: {p.stat().st_size} Bytes (max {max_bytes})")
    raw = p.read_text(encoding="utf-8", errors="replace")
    return safe_json_loads(raw, context=context, max_chars=max_bytes)


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    # remove ```json ... ``` wrappers
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"```\s*$", "", t)
    return t.strip()


def safe_json_loads(
    raw: str,
    *,
    context: str,
    max_chars: int = MAX_JSON_CHARS_DEFAULT,
) -> Any:
    """Parse JSON from untrusted string with size bounds and audit logging."""
    if raw is None:
        raise ValueError("JSON fehlt")
    if len(raw) > max_chars:
        audit_event(
            "json.import",
            module="json_io",
            outcome="fail",
            details={"context": context, "reason": "too_large", "chars": len(raw)},
        )
        raise ValueError(f"JSON zu groß: {len(raw)} Zeichen (max {max_chars})")

    text = _strip_code_fences(raw)
    try:
        return json.loads(text)
    except Exception as exc:
        # Log only a redacted/truncated excerpt
        excerpt = sanitize_untrusted_text(redact_secrets(text), max_len=300)
        audit_event(
            "json.import",
            module="json_io",
            outcome="fail",
            details={"context": context, "reason": "parse_error", "error": str(exc), "excerpt": excerpt},
        )
        raise ValueError(f"JSON Parsing fehlgeschlagen: {exc}") from exc


def require_object(v: Any, *, what: str = "JSON") -> dict[str, Any]:
    if not isinstance(v, dict):
        raise ValueError(f"{what} muss ein JSON-Objekt sein")
    return v


def require_array(v: Any, *, what: str = "JSON") -> list[Any]:
    if not isinstance(v, list):
        raise ValueError(f"{what} muss ein JSON-Array sein")
    return v
