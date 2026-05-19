"""License-State-Service.

Lädt Token aus dem Cache, verifiziert ihn offline, startet einen Background-
Heartbeat-Thread. Exponiert den aktuellen State an Flask via app.config['LICENSE'].

Issues #365 (C1-1: Boot + Heartbeat) und #370 (C1-6: Modul-Whitelist).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class LicenseState:
    state: str = 'no-license'   # ok / demo / read-only / no-license / grace-offline
    modules: list[str] = field(default_factory=list)
    max_users: int = 0
    expires_at: int = 0
    license_key: str = ''
    plan: str = ''
    customer: str = ''
    last_heartbeat: int = 0
    over_limit: bool = False
    reason: str = ''
    token: str = ''             # nur intern

    def to_dict(self) -> dict[str, Any]:
        return {
            'state': self.state,
            'modules': self.modules,
            'max_users': self.max_users,
            'expires_at': self.expires_at,
            'license_key': self.license_key,
            'plan': self.plan,
            'customer': self.customer,
            'last_heartbeat': self.last_heartbeat,
            'over_limit': self.over_limit,
            'reason': self.reason,
            'has_token': bool(self.token),
        }

    @property
    def is_read_only(self) -> bool:
        return self.state == 'read-only'

    @property
    def is_module_allowed(self) -> 'set[str] | None':
        """None = alle erlaubt, sonst Set der erlaubten Module."""
        if not self.modules:
            return set()
        if '*' in self.modules:
            return None
        return set(self.modules)


_current = LicenseState()
_lock = threading.Lock()
_heartbeat_thread: threading.Thread | None = None
_stop = threading.Event()


def get_state() -> LicenseState:
    return _current


def _apply_token(token: str) -> None:
    """Token verifizieren + State aktualisieren."""
    from shared.licensing import verify_token, compute_fingerprint, LicenseState as ResultState

    if not token:
        with _lock:
            _current.state = 'no-license'
            _current.reason = 'kein-token'
            _current.token = ''
        return

    fp = compute_fingerprint()
    result = verify_token(token, fingerprint=fp)
    with _lock:
        _current.token = token if result.valid else ''
        if not result.valid:
            _current.state = 'read-only' if result.state == ResultState.READ_ONLY else 'no-license'
            _current.reason = result.reason
            _current.modules = []
            return
        p = result.payload
        _current.state = 'demo' if p.get('plan') == 'demo' else 'ok'
        _current.modules = list(p.get('mods') or [])
        _current.max_users = int(p.get('usr') or 0)
        _current.expires_at = int(p.get('exp') or 0)
        _current.license_key = str(p.get('key') or '')
        _current.plan = str(p.get('plan') or '')
        _current.customer = str(p.get('cust') or '')
        _current.reason = ''


def _heartbeat_loop() -> None:
    """Background-Heartbeat. Schickt user_count zum Lizenzserver."""
    from shared.licensing import (
        get_client_config, LicenseClient, save_cached_token,
    )

    cfg = get_client_config(app_version='aics-web 1.0')
    client = LicenseClient(cfg=cfg)
    interval = cfg.heartbeat_interval

    while not _stop.is_set():
        try:
            if _current.token:
                # User-Count aus DB
                user_count, admin_count = _count_users()
                resp = client.heartbeat(
                    _current.token,
                    user_count=user_count, admin_count=admin_count,
                )
                with _lock:
                    _current.last_heartbeat = int(time.time())
                    _current.over_limit = bool(resp.get('over_limit'))
                new_token = resp.get('token')
                if new_token:
                    save_cached_token(cfg, new_token)
                    _apply_token(new_token)
                    log.info('License token renewed via heartbeat')
        except Exception as e:  # noqa: BLE001
            log.warning('Heartbeat fehlgeschlagen: %s', e)
        _stop.wait(interval)


def _count_users() -> tuple[int, int]:
    """Zählt aktive Non-Admin-User und Admins. Fehler → (0, 0)."""
    try:
        from server.auth.users_db import list_users
        users = list_users()
        active = [u for u in users if u.get('active')]
        admins = [u for u in active if 'admin' in (u.get('roles') or [])]
        non_admins = [u for u in active if 'admin' not in (u.get('roles') or [])]
        return len(non_admins), len(admins)
    except Exception:
        return 0, 0


def init_app(app) -> None:
    """Beim App-Start aufrufen — lädt Cache + startet Heartbeat-Thread."""
    global _heartbeat_thread
    try:
        from shared.licensing import get_client_config, load_cached_token
        cfg = get_client_config(app_version='aics-web 1.0')
        token = load_cached_token(cfg)
        _apply_token(token)
        log.info('License-State initial: %s (modules=%s)', _current.state, _current.modules)
    except Exception as e:  # noqa: BLE001
        log.warning('License-State init fehlgeschlagen: %s', e)

    if _heartbeat_thread is None or not _heartbeat_thread.is_alive():
        _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True, name='aics-license-heartbeat')
        _heartbeat_thread.start()


def shutdown() -> None:
    _stop.set()


def is_module_allowed(module_id: str) -> bool:
    """True wenn das Modul gemäß aktueller Lizenz erlaubt ist (oder keine Lizenz)."""
    allowed = _current.is_module_allowed
    if allowed is None:
        return True  # ['*'] oder noch keine Lizenz → durchlassen
    if not allowed:
        return True  # leer = noch keine Lizenz aktiv → nicht blockieren
    return module_id in allowed
