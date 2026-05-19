"""Network safety validation helpers.

Risk #199 mitigation (local LLM):
- prevent accidental usage of non-local Ollama endpoints unless explicitly allowed.
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse


def is_loopback_host(host: str) -> bool:
    h = (host or "").strip().lower()
    if h in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_loopback


def enforce_loopback_base_url(
    base_url: str,
    *,
    context: str,
    allow_nonlocal: bool = False,
) -> None:
    """Raise ValueError if base_url is not loopback and nonlocal isn't allowed."""
    allow_env = os.environ.get("AICS_ALLOW_NONLOCAL_LLM", "").strip().lower() in {"1", "true", "yes", "on"}
    if allow_nonlocal or allow_env:
        return

    u = urlparse((base_url or "").strip())
    host = (u.hostname or "").strip()
    if not host:
        raise ValueError(f"Ungültige LLM Base-URL ({context}): {base_url!r}")
    if not is_loopback_host(host):
        raise ValueError(
            "Lokales LLM darf standardmäßig nur über Loopback erreichbar sein (localhost/127.0.0.1).\n"
            f"Kontext: {context}\nURL: {base_url}\n\n"
            "Wenn du bewusst ein nicht-lokales Endpoint nutzen willst, setze:\n"
            "- Config: allow_nonlocal_base_url=true (pro Provider) oder\n"
            "- Env: AICS_ALLOW_NONLOCAL_LLM=1"
        )
