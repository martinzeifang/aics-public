"""Audit-Logging für sicherheitsrelevante Aktionen.

Ziel: Nachvollziehbarkeit (wer/was/wann) ohne sensitive Daten in Logs zu leaken.

Hinweis: Dies ist kein SIEM. Es ist eine lokale, rotierende Audit-Spur.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


_SENSITIVE_KEYS = {
    "password",
    "passwort",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
}


def _truncate(s: str, max_len: int = 500) -> str:
    s = s or ""
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _sanitize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return _truncate(value)
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list):
        return [_sanitize(v) for v in value[:50]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in list(value.items())[:100]:
            ks = str(k)
            if ks.lower() in _SENSITIVE_KEYS:
                out[ks] = "[REDACTED]"
            else:
                out[ks] = _sanitize(v)
        return out
    return _truncate(str(value))


def audit_event(
    action: str,
    *,
    module: str,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    """Schreibt ein strukturiertes Audit-Event.

    Args:
        action: Kurzname der Aktion (z.B. "issue.create", "cra.ci_import")
        module: Modul/Komponente (z.B. "vcs", "cra")
        outcome: success|fail|start|cancel
        details: Zusatzinfos (werden sanitisiert)
    """
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": str(action),
        "module": str(module),
        "outcome": str(outcome),
        "details": _sanitize(details or {}),
    }
    logging.getLogger("audit").info(json.dumps(payload, ensure_ascii=False))


# ── HTTP Request Logging (für Web-API) ──────────────────────────────────────

def log_http_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: str | None = None,
    user_email: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Schreibe ein HTTP-Request-Audit-Event.

    Args:
        method: HTTP-Methode (GET, POST, PUT, DELETE, etc.)
        path: Request-Pfad (/api/cra/controls, etc.)
        status_code: HTTP-Status-Code (200, 400, 403, 500, etc.)
        duration_ms: Request-Dauer in Millisekunden
        user_id: User-ID aus JWT (optional)
        user_email: User-Email aus JWT (optional)
        ip_address: Client-IP-Adresse
        user_agent: Client User-Agent Header
    """
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event_type": "http_request",
        "method": str(method).upper(),
        "path": str(path),
        "status_code": int(status_code),
        "duration_ms": float(duration_ms),
        "user_id": str(user_id) if user_id else None,
        "user_email": str(user_email) if user_email else None,
        "ip_address": str(ip_address) if ip_address else None,
        "user_agent": _truncate(str(user_agent)) if user_agent else None,
    }
    logging.getLogger("audit").info(json.dumps(payload, ensure_ascii=False))
