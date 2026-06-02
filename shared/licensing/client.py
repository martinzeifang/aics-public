"""HTTP-Client für aics-licensing-Server: activate / heartbeat / deactivate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from shared.licensing.config import LicenseClientConfig
from shared.licensing.fingerprint import compute_fingerprint, machine_label


class LicenseClientError(Exception):
    """Wrapper für HTTP/Network-Fehler bei Lizenz-Calls."""

    def __init__(self, message: str, *, code: str = '', http_status: int = 0,
                 detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.detail = detail or {}


@dataclass
class LicenseClient:
    cfg: LicenseClientConfig

    # ── Aktivierung ─────────────────────────────────────────────────────

    def activate(self, license_key: str = '') -> dict[str, Any]:
        """Aktiviert eine Lizenz beim Server. Returnt {token, plan, modules, ...}.

        Wenn license_key leer ist und der Server eine Auto-Demo erlaubt,
        bekommt der Client eine 30-Tage-Demo zurück.
        """
        body = {
            'license_key': (license_key or '').strip(),
            'fingerprint': compute_fingerprint(),
            'hostname': machine_label(),
            'app_version': self.cfg.app_version,
        }
        return self._post('/api/v1/activate', body)

    def heartbeat(
        self,
        token: str,
        *,
        user_count: int | None = None,
        admin_count: int | None = None,
    ) -> dict[str, Any]:
        """Heartbeat. Antwortet `{ok, modules, over_limit, [token]}`."""
        body: dict[str, Any] = {
            'token': token,
            'fingerprint': compute_fingerprint(),
        }
        if user_count is not None:
            body['user_count'] = int(user_count)
        if admin_count is not None:
            body['admin_count'] = int(admin_count)
        return self._post('/api/v1/heartbeat', body)

    def deactivate(self, token: str) -> dict[str, Any]:
        body = {'token': token, 'fingerprint': compute_fingerprint()}
        return self._post('/api/v1/deactivate', body)

    # ── Health/Pubkey ───────────────────────────────────────────────────

    def health(self) -> bool:
        try:
            r = requests.get(
                f'{self.cfg.server_url}/health',
                timeout=5, verify=self.cfg.verify_tls,
            )
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def fetch_server_pubkey(self) -> bytes:
        """Bootstrap-Hilfsfunktion — eigentlich verwenden wir den embedded Key."""
        r = requests.get(
            f'{self.cfg.server_url}/api/v1/pubkey',
            timeout=self.cfg.request_timeout, verify=self.cfg.verify_tls,
        )
        r.raise_for_status()
        return r.content

    # ── Offline-File-Generierung (Phase C3) ─────────────────────────────

    def build_offline_request(self, license_key: str, nonce: str = '') -> dict[str, Any]:
        """Erzeugt eine `.aics-request.json`-Payload, die der Admin im
        Lizenzserver-UI hochlädt → signed License-File zurück.
        """
        import secrets
        return {
            'version': 1,
            'license_key': license_key.strip(),
            'fingerprint': compute_fingerprint(),
            'hostname': machine_label(),
            'app_version': self.cfg.app_version,
            'nonce': nonce or secrets.token_hex(16),
            'requested_at': __import__('time').time(),
        }

    # ── Internals ───────────────────────────────────────────────────────

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f'{self.cfg.server_url}{path}'
        try:
            r = requests.post(
                url, json=body,
                timeout=self.cfg.request_timeout,
                verify=self.cfg.verify_tls,
            )
        except requests.RequestException as e:
            raise LicenseClientError(
                f'Lizenzserver nicht erreichbar ({self.cfg.server_url}): {e}',
                code='network-error',
            ) from e
        try:
            data = r.json()
        except json.JSONDecodeError:
            data = {'error': r.text[:200]}
        if r.status_code >= 300:
            raise LicenseClientError(
                data.get('message') or data.get('error') or f'HTTP {r.status_code}',
                code=str(data.get('error') or ''),
                http_status=r.status_code,
                detail=data,
            )
        return data
