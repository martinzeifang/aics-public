"""Password-Policy (Phase 6.2 Account-Sicherheit).

Validiert Passwörter gegen konfigurierbare Mindestanforderungen:
- Mindestlänge (default: 12)
- Mindestens 1 Buchstabe + 1 Ziffer
- Optional: Sonderzeichen + Groß-/Kleinbuchstabe
- Blacklist gängiger Passwörter

Kann via ENV überschrieben werden:
- PASSWORD_MIN_LENGTH=12
- PASSWORD_REQUIRE_DIGIT=true
- PASSWORD_REQUIRE_SPECIAL=false
- PASSWORD_REQUIRE_MIXED_CASE=false
"""

from __future__ import annotations
import os
import re

# 100 häufigste Passwörter (verkürzt) — sofortiger Reject
COMMON_PASSWORDS = {
    'password', 'passwort', '12345678', '123456789', '1234567890', 'qwerty123',
    'qwertz123', 'admin123', 'password1', 'password123', 'welcome1', 'letmein1',
    'monkey123', 'dragon123', '12345abc', 'abc12345', 'iloveyou', 'admin@123',
    'sunshine', 'football', 'baseball', 'master12', 'shadow12', 'superman',
    'starwars', 'whatever', 'butterfly', 'iloveyou1', 'changeme', 'changeme1',
    'admin-password', 'editor-password',  # die Demo-Passwörter
}


class PasswordPolicyError(ValueError):
    """Passwort verletzt die Policy."""


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in ('true', '1', 'yes')


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_policy() -> dict:
    """Aktuelle Policy-Konfiguration aus ENV."""
    return {
        'min_length': _env_int('PASSWORD_MIN_LENGTH', 12),
        'require_digit': _env_bool('PASSWORD_REQUIRE_DIGIT', True),
        'require_letter': _env_bool('PASSWORD_REQUIRE_LETTER', True),
        'require_special': _env_bool('PASSWORD_REQUIRE_SPECIAL', False),
        'require_mixed_case': _env_bool('PASSWORD_REQUIRE_MIXED_CASE', False),
        'block_common': _env_bool('PASSWORD_BLOCK_COMMON', True),
    }


def validate_password(password: str, *, email: str = '') -> None:
    """Wirft PasswordPolicyError wenn Passwort die Policy verletzt.

    Bei DEMO-Mode (ENABLE_DEMO_USERS=true) wird die Policy gelockert,
    damit die Demo-User funktionieren.
    """
    p = password or ''
    policy = get_policy()

    # Demo-Mode: nur Mindestlänge 8
    if os.getenv('ENABLE_DEMO_USERS', '').lower() in ('true', '1', 'yes'):
        if len(p) < 8:
            raise PasswordPolicyError('Passwort muss mind. 8 Zeichen haben (DEMO-Mode).')
        return

    if len(p) < policy['min_length']:
        raise PasswordPolicyError(
            f'Passwort muss mindestens {policy["min_length"]} Zeichen haben.'
        )

    if policy['require_letter'] and not re.search(r'[A-Za-zÄÖÜäöüß]', p):
        raise PasswordPolicyError('Passwort muss mindestens einen Buchstaben enthalten.')

    if policy['require_digit'] and not re.search(r'\d', p):
        raise PasswordPolicyError('Passwort muss mindestens eine Ziffer enthalten.')

    if policy['require_special'] and not re.search(r'[^A-Za-z0-9ÄÖÜäöüß]', p):
        raise PasswordPolicyError(
            'Passwort muss mindestens ein Sonderzeichen enthalten (z.B. ! @ # $ %).'
        )

    if policy['require_mixed_case']:
        if not re.search(r'[A-ZÄÖÜ]', p) or not re.search(r'[a-zäöüß]', p):
            raise PasswordPolicyError(
                'Passwort muss Groß- UND Kleinbuchstaben enthalten.'
            )

    if policy['block_common'] and p.lower() in COMMON_PASSWORDS:
        raise PasswordPolicyError(
            'Passwort steht auf der Liste häufiger Passwörter — bitte komplexer wählen.'
        )

    # E-Mail darf nicht im Passwort stehen
    if email:
        local = email.split('@', 1)[0].lower()
        if len(local) >= 4 and local in p.lower():
            raise PasswordPolicyError(
                'Passwort darf den E-Mail-Namen nicht enthalten.'
            )
