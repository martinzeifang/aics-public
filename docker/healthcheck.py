#!/usr/bin/env python3
"""Container-Healthcheck ohne curl (#1593 — curl aus dem Runtime-Image entfernt).

gunicorn lauscht intern als Klartext-HTTP auf :5000 (TLS terminiert nginx).
HTTP zuerst, HTTPS als Fallback (HTTPS_ENABLED=true). Harte Timeouts, damit der
Check nie bis ins Docker-Timeout hängt.
"""
import ssl
import sys
import urllib.request

_URLS = ("http://127.0.0.1:5000/health", "https://127.0.0.1:5000/health")
_CTX = ssl._create_unverified_context()

for url in _URLS:
    try:
        ctx = _CTX if url.startswith("https") else None
        with urllib.request.urlopen(url, timeout=5, context=ctx) as resp:
            if 200 <= resp.status < 400:
                sys.exit(0)
    except Exception:  # noqa: BLE001 — nächster Kandidat / am Ende exit 1
        continue
sys.exit(1)
