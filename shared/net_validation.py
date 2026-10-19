"""Network safety validation helpers.

Risk #199 mitigation (local LLM):
- prevent accidental usage of non-local Ollama endpoints unless explicitly allowed.

#741 (WP-08, SSRF / OWASP A10):
- validate every outbound URL before fetching (block loopback / RFC1918 /
  link-local / reserved / cloud-metadata 169.254.169.254 etc.)
- re-validate on EVERY redirect hop (no DNS-rebinding via redirect)
- cloud LLM base-url against a provider allowlist
"""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urljoin, urlparse


class SSRFError(ValueError):
    """Raised when an outbound URL targets a forbidden / private destination."""


# Erlaubte Schemata für ausgehende Web-Requests (Crawler/Fetch).
_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})

# Provider-Allowlist für Cloud-LLM-Base-URLs (#741). Nur diese Hosts (oder
# Subdomains davon) dürfen als Cloud-Endpoint konfiguriert werden.
_CLOUD_LLM_HOST_ALLOWLIST = frozenset({
    "api.openai.com",
    "api.anthropic.com",
    "api.mistral.ai",
    "generativelanguage.googleapis.com",
    "api.groq.com",
    "openrouter.ai",
})


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


# ============================================================
# SSRF-Schutz für ausgehende Web-Requests (#741 / OWASP A10)
# ============================================================

def _ip_is_forbidden(ip: ipaddress._BaseAddress) -> bool:
    """True, wenn die IP auf ein nicht-öffentliches/reserviertes Ziel zeigt.

    Deckt Loopback (127/8, ::1), private (RFC1918, fc00::/7), Link-Local
    (169.254/16 inkl. Cloud-Metadata 169.254.169.254, fe80::/10), Multicast,
    reservierte und 'unspecified' (0.0.0.0/::) Adressen ab.
    """
    # IPv4-mapped IPv6 (::ffff:a.b.c.d) auf die eingebettete IPv4 reduzieren.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_host_ips(host: str) -> list[ipaddress._BaseAddress]:
    """Alle A/AAAA-Records eines Hosts auflösen. Leere Liste bei Fehler."""
    # Host kann bereits eine IP sein → direkt parsen (kein DNS).
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        return []
    ips: list[ipaddress._BaseAddress] = []
    for info in infos:
        addr = info[4][0]
        # IPv6-Scope-ID (z.B. 'fe80::1%eth0') abschneiden.
        addr = addr.split("%")[0]
        try:
            ips.append(ipaddress.ip_address(addr))
        except ValueError:
            continue
    return ips


def validate_outbound_url(url: str) -> str:
    """Validiert eine URL für einen ausgehenden Request (SSRF-Schutz, #741).

    Prüft Schema (nur http/https), löst den Host per DNS auf und lehnt ab,
    sobald *irgendeine* aufgelöste IP auf ein privates/reserviertes/loopback/
    link-local-Ziel (inkl. 169.254.169.254 Cloud-Metadata) zeigt.

    Returns die normalisierte URL; raises SSRFError bei Verstoß.
    """
    u = urlparse((url or "").strip())
    if u.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        raise SSRFError(f"Nicht erlaubtes URL-Schema: {u.scheme!r} (nur http/https)")
    host = (u.hostname or "").strip()
    if not host:
        raise SSRFError(f"URL ohne Host: {url!r}")

    ips = _resolve_host_ips(host)
    if not ips:
        raise SSRFError(f"Host nicht auflösbar oder ungültig: {host!r}")
    for ip in ips:
        if _ip_is_forbidden(ip):
            raise SSRFError(
                f"Ziel-Adresse nicht erlaubt (privat/reserviert/Loopback/"
                f"Link-Local): {host} → {ip}"
            )
    return u.geturl()


# HTTP-Statuscodes, bei denen requests einem Location-Header folgen würde.
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


def safe_get(url: str, *, max_redirects: int = 5, **kwargs):
    """SSRF-sicherer Ersatz für requests.get mit manueller Redirect-Kette.

    Validiert die Start-URL UND jeden Redirect-Hop neu (DNS-Rebinding-/
    Redirect-zu-intern-Schutz). ``allow_redirects`` wird ignoriert — die
    Umleitung wird hier kontrolliert nachverfolgt.
    """
    import requests  # lokal, damit das Modul ohne requests importierbar bleibt

    kwargs.pop("allow_redirects", None)
    current = validate_outbound_url(url)
    resp = None
    for _ in range(max_redirects + 1):
        resp = requests.get(current, allow_redirects=False, **kwargs)
        if resp.status_code in _REDIRECT_CODES and resp.headers.get("Location"):
            nxt = urljoin(current, resp.headers["Location"])
            current = validate_outbound_url(nxt)  # JEDER Hop neu geprüft
            resp.close()
            continue
        return resp
    raise SSRFError(f"Zu viele Redirects (> {max_redirects}) ab {url}")


def is_allowed_cloud_llm_host(base_url: str) -> bool:
    """True, wenn der Host der Cloud-LLM-Base-URL auf der Allowlist steht (#741)."""
    host = (urlparse((base_url or "").strip()).hostname or "").strip().lower()
    if not host:
        return False
    return any(host == a or host.endswith("." + a) for a in _CLOUD_LLM_HOST_ALLOWLIST)


def enforce_cloud_llm_base_url(base_url: str, *, context: str) -> None:
    """Raise ValueError, wenn die Cloud-LLM-Base-URL nicht auf der Allowlist ist."""
    u = urlparse((base_url or "").strip())
    if u.scheme.lower() != "https":
        raise ValueError(
            f"Cloud-LLM-Base-URL muss HTTPS sein ({context}): {base_url!r}"
        )
    if not is_allowed_cloud_llm_host(base_url):
        raise ValueError(
            f"Cloud-LLM-Host nicht in der Allowlist ({context}): {base_url!r}\n"
            f"Erlaubt: {sorted(_CLOUD_LLM_HOST_ALLOWLIST)}"
        )
