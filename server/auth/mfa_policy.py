"""MFA-Policy + Enforcement (Sprint ε, Phase D).

MFA (TOTP oder Passkey) ist für jeden Benutzer als Option verfügbar. Zusätzlich
kann ein Administrator MFA verpflichtend machen — global oder pro Rolle — mit
einer Grace-Period, innerhalb derer betroffene User die Einrichtung nachholen.

Policy wird in der Suite-Config (`ai_compliance_suite.config`) unter
`auth.mfa_policy` gespeichert:

    {
      "mode": "optional" | "required_all" | "required_roles",
      "required_roles": ["admin", ...],   # nur bei mode=required_roles
      "grace_days": 7
    }

Enforcement-Strategie (lockout-sicher): Nach Ablauf der Grace-Period wird der
Login NICHT blockiert (sonst käme der User nie zur Einrichtungsseite), sondern
mit `mfa_setup_required=True` markiert. Das Frontend erzwingt dann die
Einrichtung (Route-Guard auf /account/security).
"""

from __future__ import annotations

import time
from typing import Any

DEFAULT_POLICY = {
    'mode': 'optional',
    'required_roles': [],
    'grace_days': 7,
}

VALID_MODES = ('optional', 'required_all', 'required_roles')


def get_policy() -> dict[str, Any]:
    """Liest die MFA-Policy aus der Suite-Config (mit Defaults)."""
    try:
        from ai_compliance_suite.config import load_config
        cfg = load_config()
        raw = ((cfg.get('auth') or {}).get('mfa_policy') or {})
    except Exception:
        raw = {}
    policy = dict(DEFAULT_POLICY)
    if isinstance(raw, dict):
        if raw.get('mode') in VALID_MODES:
            policy['mode'] = raw['mode']
        if isinstance(raw.get('required_roles'), list):
            policy['required_roles'] = [str(r) for r in raw['required_roles']]
        try:
            policy['grace_days'] = max(0, int(raw.get('grace_days', DEFAULT_POLICY['grace_days'])))
        except (ValueError, TypeError):
            pass
    return policy


def save_policy(mode: str, required_roles: list[str] | None, grace_days: int) -> dict[str, Any]:
    """Persistiert die MFA-Policy in der Suite-Config. Returns die gespeicherte Policy."""
    if mode not in VALID_MODES:
        raise ValueError(f'Ungültiger mode: {mode}')
    policy = {
        'mode': mode,
        'required_roles': [str(r) for r in (required_roles or [])],
        'grace_days': max(0, int(grace_days)),
    }
    from ai_compliance_suite.config import load_config, save_config
    cfg = load_config()
    cfg.setdefault('auth', {})
    cfg['auth']['mfa_policy'] = policy
    save_config(cfg)
    return policy


def is_mfa_required_for(roles: list[str], policy: dict[str, Any] | None = None) -> bool:
    """Ob MFA für einen User mit diesen Rollen verpflichtend ist."""
    policy = policy or get_policy()
    mode = policy.get('mode', 'optional')
    if mode == 'required_all':
        return True
    if mode == 'required_roles':
        required = set(policy.get('required_roles', []))
        return bool(required & set(roles or []))
    return False


def evaluate_enforcement(user: dict[str, Any], *, db_path=None) -> dict[str, Any]:
    """Bewertet den MFA-Enforcement-Status für einen User beim Login.

    Setzt bei erstmaliger Betroffenheit das Grace-Ende. Returns:
      {
        'required': bool,           # Policy verlangt MFA für diesen User
        'satisfied': bool,          # User hat bereits MFA
        'grace_until': int,         # Unix-ts (0 wenn n/a)
        'grace_expired': bool,      # Grace abgelaufen und nicht satisfied
        'setup_required': bool,     # Frontend muss Einrichtung erzwingen
        'recommended': bool,        # innerhalb Grace: Einrichtung empfohlen
      }
    """
    from server.auth import users_db
    if db_path is None:
        db_path = users_db.DEFAULT_DB_PATH

    policy = get_policy()
    required = is_mfa_required_for(user.get('roles', []), policy)
    has_mfa = users_db.user_has_mfa(user['id'], db_path=db_path)

    result = {
        'required': required,
        'satisfied': has_mfa,
        'grace_until': 0,
        'grace_expired': False,
        'setup_required': False,
        'recommended': False,
    }
    if not required or has_mfa:
        return result

    now = int(time.time())
    grace_until = users_db.get_mfa_grace_until(user['id'], db_path=db_path)
    if grace_until <= 0:
        # Erstmalige Betroffenheit → Grace-Fenster setzen
        grace_until = now + policy['grace_days'] * 86400
        users_db.set_mfa_grace_until(user['id'], grace_until, db_path=db_path)

    result['grace_until'] = grace_until
    if now >= grace_until:
        result['grace_expired'] = True
        result['setup_required'] = True
    else:
        result['recommended'] = True
    return result
