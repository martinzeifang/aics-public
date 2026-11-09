"""AICS-Licensing-Client SDK.

Bietet Aktivierung, Token-Verifizierung (offline-fähig), Heartbeat und
Read-Only-Mode-Erkennung gegen den aics-licensing-Server.

Architektur: siehe github.com/martinzeifang/aics-licensing/docs/ARCHITECTURE.md.
"""

from shared.licensing.config import LicenseClientConfig, get_client_config
from shared.licensing.fingerprint import compute_fingerprint, machine_label
from shared.licensing.verify import (
    LicenseState,
    VerifyResult,
    verify_token,
)
from shared.licensing.client import (
    LicenseClient,
    LicenseClientError,
)
from shared.licensing.cache import (
    load_cached_token,
    save_cached_token,
    delete_cached_token,
    cache_path,
)

__all__ = [
    'LicenseClientConfig', 'get_client_config',
    'compute_fingerprint', 'machine_label',
    'LicenseState', 'VerifyResult', 'verify_token',
    'LicenseClient', 'LicenseClientError',
    'load_cached_token', 'save_cached_token', 'delete_cached_token', 'cache_path',
]
