"""Step-up-Authentifizierung für sensible Account-Security-Aktionen (#1183).

Ein gültiges Bearer-Token allein darf nicht ausreichen, um MFA-Faktoren anzulegen,
zu entfernen oder Passkeys zu verwalten — bei Token-Diebstahl könnte ein Angreifer
sonst Persistenz aufbauen oder legitime Faktoren löschen. Diese Helfer verlangen einen
frischen Re-Auth-Nachweis (aktuelles Passwort ODER gültiger TOTP-Code).
"""

from __future__ import annotations

from typing import Any

from server.auth import totp
from server.auth.users_db import get_user_by_id, get_totp_state, verify_password


def verify_step_up(user_id: str, data: dict[str, Any] | None) -> tuple[bool, str | None]:
    """Prüft den Re-Auth-Nachweis im Request-Body.

    Akzeptiert ``current_password``/``password`` ODER ``totp_code``/``code``.

    Rückgabe ``(ok, error)``. Passkey-only-Accounts (weder Passwort noch TOTP) können
    keinen klassischen Step-up erbringen → werden best-effort durchgelassen (das Token
    ist dann der einzige verfügbare Faktor; dokumentierte Rest-Risikoentscheidung).
    """
    user = get_user_by_id(user_id)
    if not user:
        return False, 'Benutzer nicht gefunden'
    data = data or {}
    pw = str(data.get('current_password') or data.get('password') or '')
    code = str(data.get('totp_code') or data.get('code') or '').strip()

    has_pw = bool(user.get('password_hash'))
    state = get_totp_state(user_id)
    has_totp = bool(state.get('enabled'))

    if pw and has_pw:
        return (True, None) if verify_password(user, pw) else (False, 'Passwort ist nicht korrekt')
    if code and has_totp:
        if totp.verify_code(state.get('secret') or '', code):
            return True, None
        return False, 'TOTP-Code ist ungültig'
    if not has_pw and not has_totp:
        return True, None  # kein Step-up-Faktor verfügbar (z. B. reiner Passkey-Account)
    return False, 'Re-Authentifizierung erforderlich: aktuelles Passwort oder TOTP-Code angeben.'


def step_up_or_403(user_id: str, data: dict[str, Any] | None):
    """Bequemer Guard: liefert ``None`` bei Erfolg, sonst ein Flask-(body, 403)-Tupel."""
    ok, err = verify_step_up(user_id, data)
    if ok:
        return None
    return {'error': err, 'step_up_required': True}, 403
