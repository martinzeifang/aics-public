"""Client-Side Lizenz-Konfiguration mit eingebettetem Public-Key.

Der Server-Public-Key ist als Konstante embedded — wer eine andere Lizenz-
Quelle benutzen will, muss den Code patchen + neu deployen. Override via
ENV ist nicht vorgesehen (Anti-Tampering).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────────
# Server Public Key v1 (Ed25519, embedded)
# Ed25519-Public-Key. Wer den austauschen will, muss den Source neu bauen.
SERVER_PUBLIC_KEY_PEM_V1 = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEANHH9NakfbmqV+3KihPTyIq9Cw/HBOPy8IlBCkWisc3o=
-----END PUBLIC KEY-----
"""

KNOWN_PUBLIC_KEYS: dict[str, bytes] = {
    'v1': SERVER_PUBLIC_KEY_PEM_V1,
}
# ───────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LicenseClientConfig:
    server_url: str            # https://lic.example.de:8444
    request_timeout: int       # Sekunden für HTTP-Calls
    heartbeat_interval: int    # Sekunden zwischen Heartbeats
    verify_tls: bool | str     # True/False oder CA-Bundle-Pfad (#1172)
    cache_path: Path           # wo der Token persistent abgelegt wird
    app_version: str
    public_keys: dict[str, bytes] = field(default_factory=lambda: dict(KNOWN_PUBLIC_KEYS))


_DEFAULT_SERVER_URL = 'https://licensing.example.com:8444'


def _settings_file() -> Path:
    """Persistenter Speicherort der License-Server-URL-Override-Datei."""
    data_dir = Path('/app/data') if Path('/app/data').exists() else Path('data')
    return data_dir / 'license_server.json'


def load_settings() -> dict:
    """Liest data/license_server.json. Liefert {} wenn nicht vorhanden/kaputt."""
    p = _settings_file()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text('utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        log.warning('license_server.json kaputt: %s', e)
        return {}


def save_settings(server_url: str, *, verify_tls: bool = True,
                  request_timeout: int = 15) -> Path:
    """Schreibt die License-Server-URL persistent. Wirft bei IO-Fehler."""
    p = _settings_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'server_url': server_url.rstrip('/'),
        'verify_tls': bool(verify_tls),
        'request_timeout': int(request_timeout),
    }
    tmp = p.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    tmp.replace(p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p



def get_client_config(
    *,
    server_url: str | None = None,
    cache_path_override: Path | None = None,
    app_version: str = 'aics-web 1.0',
) -> LicenseClientConfig:
    """Erstellt eine Client-Config.

    Reihenfolge: explizites Argument > data/license_server.json > ENV > Default.
    """
    file_settings = load_settings()

    url = (
        server_url
        or file_settings.get('server_url')
        or os.environ.get('AICS_LICENSE_SERVER_URL')
        or _DEFAULT_SERVER_URL
    )
    timeout = int(
        file_settings.get('request_timeout')
        or os.environ.get('AICS_LICENSE_TIMEOUT', '15')
    )
    heartbeat = int(os.environ.get('AICS_LICENSE_HEARTBEAT_INTERVAL', str(6 * 3600)))
    if 'verify_tls' in file_settings:
        verify_tls = bool(file_settings['verify_tls'])
    else:
        # #742: secure-by-default für öffentliche Hosts.
        # #1146: private/Intranet-Lizenzserver (RFC1918, localhost, .local…)
        # default AUS — laufen typ. mit self-signed Cert; Authentizität ist
        # ohnehin durch den Ed25519-signierten Token gesichert.
        # #1172: TLS-Verifikation secure-by-default für ALLE Hosts (auch Intranet/
        # RFC1918). Self-Signed-Intranet-Server: expliziter Opt-out via
        # AICS_LICENSE_VERIFY_TLS=false ODER besser CA-Pinning via
        # AICS_LICENSE_CA_BUNDLE=<pem>. Kein attacker-beeinflussbarer Hostname-Carve-out.
        env_raw = os.environ.get('AICS_LICENSE_VERIFY_TLS', '').strip().lower()
        if env_raw in {'0', 'false', 'no', 'off'}:
            verify_tls = False
        else:
            verify_tls = True

    ca_bundle = (file_settings.get('ca_bundle')
                 or os.environ.get('AICS_LICENSE_CA_BUNDLE', '').strip())
    if ca_bundle and Path(ca_bundle).is_file():
        verify_tls = ca_bundle  # requests akzeptiert einen CA-Bundle-Pfad als verify=

    if cache_path_override is not None:
        cache = cache_path_override
    else:
        cache_env = os.environ.get('AICS_LICENSE_CACHE_PATH', '').strip()
        if cache_env:
            cache = Path(cache_env)
        else:
            # Default: /app/data/license.token im Docker, sonst data/license.token
            data_dir = Path('/app/data') if Path('/app/data').exists() else Path('data')
            cache = data_dir / 'license.token'

    return LicenseClientConfig(
        server_url=url.rstrip('/'),
        request_timeout=timeout,
        heartbeat_interval=heartbeat,
        verify_tls=verify_tls,
        cache_path=cache,
        app_version=app_version,
    )
