"""User-Datenbank mit SQLite — ersetzt MOCK_USERS.

Schema:
- users(id, email UNIQUE, password_hash, roles_json, active, created_at, updated_at)
- revoked_tokens(jti, user_id, revoked_at, expires_at)

Default-Demo-Users werden nur angelegt wenn ENABLE_DEMO_USERS=true (DEV-Modus).
In Production müssen User über die Admin-API explizit angelegt werden.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from werkzeug.security import generate_password_hash, check_password_hash

from shared import db as _sdb
from shared.crypto_at_rest import decrypt_field, encrypt_field, is_encrypted_field

log = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path('data/db/users.sqlite')


def _connect(db_path: Path = DEFAULT_DB_PATH) -> Any:
    """Postgres-Verbindung (Schema "users") über den zentralen Kompat-Layer (#15)."""
    return _sdb.connect(db_path)


def _add_column_if_missing(cur, table: str, column: str, ddl: str) -> None:
    """Fügt eine Spalte idempotent + race-tolerant hinzu (Postgres: IF NOT EXISTS)."""
    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {ddl}")


_ENSURED_PATHS: set[str] = set()


def ensure_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Tabellen anlegen + ggf. Demo-Users (einmalig je Pfad gecacht, #15).

    is_token_revoked/get_token_version rufen ensure_db auf JEDEM Request auf; ohne
    Cache würde das (bei ENABLE_DEMO_USERS) je Request 2× scrypt rechnen → Test-Timeouts.
    """
    key = str(db_path)
    if key in _ENSURED_PATHS:
        return
    con = _connect(db_path)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            roles_json TEXT DEFAULT '[]',
            allowed_modules_json TEXT DEFAULT 'null',
            extra_permissions_json TEXT DEFAULT '[]',
            display_name TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT aics_now(),
            updated_at TEXT DEFAULT aics_now(),
            last_login TEXT
        )
    """)
    # Migration: alte DB ohne neue Spalten. Race-tolerant (#837): mehrere
    # gunicorn-Worker booten parallel; _add_column_if_missing fängt das
    # erwartete "duplicate column name" ab statt den Worker crashen zu lassen.
    _add_column_if_missing(cur, 'users', 'allowed_modules_json', "allowed_modules_json TEXT DEFAULT 'null'")
    _add_column_if_missing(cur, 'users', 'extra_permissions_json', "extra_permissions_json TEXT DEFAULT '[]'")
    _add_column_if_missing(cur, 'users', 'display_name', "display_name TEXT DEFAULT ''")
    # Phase 6.2: Account-Lockout
    _add_column_if_missing(cur, 'users', 'failed_login_count', "failed_login_count INTEGER DEFAULT 0")
    _add_column_if_missing(cur, 'users', 'locked_until', "locked_until INTEGER DEFAULT 0")
    _add_column_if_missing(cur, 'users', 'last_failed_login', "last_failed_login TEXT")
    # Phase 7.3: 2FA (TOTP)
    _add_column_if_missing(cur, 'users', 'totp_secret', "totp_secret TEXT")
    _add_column_if_missing(cur, 'users', 'totp_enabled', "totp_enabled INTEGER DEFAULT 0")
    _add_column_if_missing(cur, 'users', 'totp_backup_codes_json', "totp_backup_codes_json TEXT DEFAULT '[]'")
    # #738 (AUTH-13): Token-Version für sofortige Revocation bei Deaktivierung/
    # Rollenänderung. Tokens tragen 'tv'; weicht es vom DB-Wert ab → ungültig.
    # (NOT NULL ist bei ADD COLUMN mit DEFAULT zulässig.)
    _add_column_if_missing(cur, 'users', 'token_version', "token_version INTEGER NOT NULL DEFAULT 0")
    # Sprint ε (Phase A): MFA-Enforcement-Grace (Policy-Auswertung in Phase D)
    _add_column_if_missing(cur, 'users', 'mfa_grace_until', "mfa_grace_until INTEGER DEFAULT 0")

    # Sprint ε (Phase A): WebAuthn/Passkey-Credentials
    cur.execute("""
        CREATE TABLE IF NOT EXISTS webauthn_credentials (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id TEXT NOT NULL,
            credential_id TEXT NOT NULL UNIQUE,
            public_key TEXT NOT NULL,
            sign_count INTEGER NOT NULL DEFAULT 0,
            transports_json TEXT DEFAULT '[]',
            aaguid TEXT DEFAULT '',
            nickname TEXT DEFAULT '',
            backup_eligible INTEGER DEFAULT 0,
            backup_state INTEGER DEFAULT 0,
            created_at TEXT DEFAULT aics_now(),
            last_used_at TEXT
        )
    """)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_webauthn_user ON webauthn_credentials(user_id)')

    # Sprint ε (Phase A): ephemere WebAuthn-Challenges (Registrierung + Login)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS webauthn_challenges (
            challenge_id TEXT PRIMARY KEY,
            user_id TEXT,
            challenge TEXT NOT NULL,
            typ TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_webauthn_chal_expires ON webauthn_challenges(expires_at)')

    cur.execute("""
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            jti TEXT PRIMARY KEY,
            user_id TEXT,
            revoked_at TEXT DEFAULT aics_now(),
            expires_at INTEGER
        )
    """)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_revoked_expires ON revoked_tokens(expires_at)')

    # #407: Passwort-Reset-Tokens (Single-Use)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            used_at INTEGER
        )
    """)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_reset_user ON password_reset_tokens(user_id)')

    con.commit()

    # Test-/DEV-Modus: Demo-User. Wenn ENABLE_DEMO_USERS aktiv ist, werden die
    # Testuser IDEMPOTENT sichergestellt — auch wenn die DB bereits (andere) User
    # enthält. Sonst verschwinden die Testuser, sobald einmal ein echter/Initial-
    # Admin angelegt wurde (Seeding lief früher nur bei leerer DB).
    enable_demo = os.getenv('ENABLE_DEMO_USERS', 'false').lower() in ('true', '1', 'yes')
    # #744 (WP-11, OWASP A07): Fail-closed in Produktion. Demo-User haben
    # bekannte Klartext-Passwörter und dürfen in einer Produktivumgebung NIEMALS
    # angelegt werden — selbst wenn ENABLE_DEMO_USERS=true (Fehlkonfiguration /
    # geerbte ENV). Tests laufen mit FLASK_ENV=testing und behalten das Seeding.
    is_production = os.getenv('FLASK_ENV', '').lower() == 'production'
    if enable_demo and is_production:
        import logging
        logging.getLogger('aics.auth').warning(
            'ENABLE_DEMO_USERS=true wird in FLASK_ENV=production IGNORIERT '
            '(fail-closed): keine Demo-User angelegt.'
        )
        enable_demo = False
    cur.execute('SELECT COUNT(*) FROM users')
    user_count = cur.fetchone()[0]
    if enable_demo:
        _create_demo_users(con)
    elif user_count == 0:
        _create_initial_admin(con, db_path)

    con.close()
    _ENSURED_PATHS.add(key)


def _create_demo_users(con: Any) -> None:
    """Stellt die Testuser admin@example.com + editor@example.com sicher (idempotent).

    ON CONFLICT(email) DO NOTHING → mehrfacher Aufruf / nicht-leere DB sind
    unkritisch; bestehende (echte) User bleiben unangetastet.
    """
    demo_users = [
        ('user-001', 'admin@example.com', 'admin-password', ['admin']),
        ('user-002', 'editor@example.com', 'editor-password', ['cra_editor']),
    ]
    for uid, email, pw, roles in demo_users:
        con.execute(
            'INSERT INTO users (id, email, password_hash, roles_json, active) '
            'VALUES (?, ?, ?, ?, 1) ON CONFLICT(email) DO NOTHING',
            (uid, email, generate_password_hash(pw), json.dumps(roles)),
        )
    con.commit()


def _create_initial_admin(con: Any, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Production-Bootstrap: bei leerer DB und ohne DEMO-Modus wird ein
    Initial-Admin angelegt. Passwort wird zufällig generiert und prominent
    ins stdout-Log geschrieben (im Container-Log sichtbar) — der einzige
    Moment, in dem das Klartextpasswort verfügbar ist.

    Konfigurierbar via:
        INITIAL_ADMIN_EMAIL  — Default: 'admin@aics.local' (muss EMAIL_REGEX
                                in server/api/auth.py erfüllen: *@*.tld).
    """
    import secrets

    email = (os.getenv('INITIAL_ADMIN_EMAIL', '') or 'admin@aics.local').strip().lower()
    # token_urlsafe(18) → 24 chars [A-Za-z0-9_-]: erfüllt Default-Policy
    # (min_length=12, require_letter, require_digit).
    password = secrets.token_urlsafe(18)
    user_id = f'admin-{uuid.uuid4().hex[:8]}'

    try:
        con.execute(
            'INSERT INTO users (id, email, password_hash, roles_json, active, display_name) '
            'VALUES (?, ?, ?, ?, 1, ?)',
            (user_id, email, generate_password_hash(password), json.dumps(['admin']), 'Initial Admin'),
        )
        con.commit()
    except Exception:
        # Race mit parallelem Worker (gunicorn): ein anderer hat den Admin bereits
        # angelegt und das Passwort geloggt. Silent skip — kein doppeltes Logging.
        return

    # #737: Initial-Passwort NICHT ins stdout/Log (landet sonst dauerhaft in
    # Container-/Log-Aggregatoren). Stattdessen in eine 0600-Datei im Datenvolume
    # schreiben; das Log enthält nur den Pfad-Hinweis, kein Geheimnis.
    cred_path = db_path.parent / 'INITIAL_ADMIN_CREDENTIALS.txt'
    try:
        cred_path.write_text(
            f'Initial-Admin (DB war leer beim Start)\n'
            f'Email:    {email}\n'
            f'Password: {password}\n\n'
            f'WICHTIG: Nach erstem Login Passwort ändern und diese Datei löschen.\n',
            encoding='utf-8',
        )
        os.chmod(cred_path, 0o600)
        location = str(cred_path)
    except OSError:
        location = '(Datei konnte nicht geschrieben werden — Admin-Reset nötig)'

    bar = '=' * 64
    print('', flush=True)
    print(bar, flush=True)
    print('🔐 INITIAL ADMIN USER ANGELEGT (DB war leer beim Start)', flush=True)
    print(f'   Email:        {email}', flush=True)
    print(f'   Passwort in:  {location}  (Rechte 0600)', flush=True)
    print('   ⚠️  Nach erstem Login Passwort ändern + Datei löschen.', flush=True)
    print(bar, flush=True)
    print('', flush=True)


# ============================================================
# User-CRUD
# ============================================================

def _row_to_user(row: dict | Any) -> dict[str, Any]:
    """Helper: SQLite-Row → User-Dict mit ge-parsten JSON-Feldern."""
    user = dict(row)
    try:
        user['roles'] = json.loads(user.get('roles_json') or '[]')
    except Exception:
        user['roles'] = []
    try:
        am = json.loads(user.get('allowed_modules_json') or 'null')
        user['allowed_modules'] = am if isinstance(am, list) else None
    except Exception:
        user['allowed_modules'] = None
    try:
        user['extra_permissions'] = json.loads(user.get('extra_permissions_json') or '[]')
    except Exception:
        user['extra_permissions'] = []
    return user


def get_token_version(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Aktuelle Token-Version eines Users (für Revocation-Check, #738)."""
    ensure_db(db_path)
    con = _connect(db_path)
    row = con.execute('SELECT token_version FROM users WHERE id=?', (user_id,)).fetchone()
    con.close()
    if not row:
        return -1  # User existiert nicht → jeder Token ungültig
    try:
        return int(row['token_version'] or 0)
    except (KeyError, TypeError, ValueError):
        return 0


def bump_token_version(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Erhöht die Token-Version → alle bestehenden Tokens des Users werden ungültig.
    Aufrufen bei Deaktivierung, Löschung, Rollen-/Rechteänderung (#738 / AUTH-13)."""
    ensure_db(db_path)
    con = _connect(db_path)
    con.execute(
        'UPDATE users SET token_version = COALESCE(token_version,0) + 1, '
        'updated_at=aics_now() WHERE id=?', (user_id,))
    con.commit()
    con.close()


def get_user_by_email(email: str, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    row = con.execute(
        # active-Cast: aus alten Backups kann 'null' (String) eingespielt sein
        "SELECT * FROM users WHERE email=? AND CAST(active AS INTEGER) = 1", (email,)
    ).fetchone()
    con.close()
    if not row:
        return None
    return _row_to_user(row)


def get_user_by_id(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    row = con.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    con.close()
    if not row:
        return None
    return _row_to_user(row)


def list_users(db_path: Path = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    rows = con.execute(
        'SELECT * FROM users ORDER BY created_at DESC'
    ).fetchall()
    con.close()
    return [_row_to_user(r) for r in rows]


def create_user(
    *,
    email: str,
    password: str,
    roles: list[str],
    allowed_modules: list[str] | None = None,
    extra_permissions: list[str] | None = None,
    display_name: str = '',
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    ensure_db(db_path)
    con = _connect(db_path)
    uid = str(uuid.uuid4())
    con.execute(
        '''INSERT INTO users (id, email, password_hash, roles_json,
                              allowed_modules_json, extra_permissions_json, display_name)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (uid, email, generate_password_hash(password),
         json.dumps(roles),
         json.dumps(allowed_modules) if allowed_modules is not None else 'null',
         json.dumps(extra_permissions or []),
         display_name or ''),
    )
    con.commit()
    con.close()
    return {
        'id': uid, 'email': email, 'roles': roles, 'active': 1,
        'allowed_modules': allowed_modules,
        'extra_permissions': extra_permissions or [],
        'display_name': display_name,
    }


def update_user(
    user_id: str,
    *,
    email: str | None = None,
    password: str | None = None,
    roles: list[str] | None = None,
    allowed_modules: list[str] | None | object = ...,
    extra_permissions: list[str] | None = None,
    display_name: str | None = None,
    active: bool | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    ensure_db(db_path)
    fields: list[str] = []
    params: list[Any] = []
    if email is not None:
        fields.append('email=?')
        params.append(email)
    if password is not None:
        fields.append('password_hash=?')
        params.append(generate_password_hash(password))
    if roles is not None:
        fields.append('roles_json=?')
        params.append(json.dumps(roles))
    if allowed_modules is not ...:
        fields.append('allowed_modules_json=?')
        params.append(json.dumps(allowed_modules) if allowed_modules is not None else 'null')
    if extra_permissions is not None:
        fields.append('extra_permissions_json=?')
        params.append(json.dumps(extra_permissions))
    if display_name is not None:
        fields.append('display_name=?')
        params.append(display_name)
    if active is not None:
        fields.append('active=?')
        params.append(1 if active else 0)
    if not fields:
        return False
    fields.append('updated_at=aics_now()')
    params.append(user_id)

    con = _connect(db_path)
    con.execute(f'UPDATE users SET {", ".join(fields)} WHERE id=?', params)
    con.commit()
    con.close()
    return True


def update_last_login(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    ensure_db(db_path)
    # #1340: Verbindung MUSS zurück in den Pool (with → commit + close). Fehlte hier
    # → Connection-Leak bei jedem erfolgreichen Login (Pool-Erschöpfung, PoolTimeout).
    with _connect(db_path) as con:
        # Erfolgreicher Login → Counter zurücksetzen
        con.execute(
            'UPDATE users SET last_login=aics_now(), failed_login_count=0, locked_until=0 WHERE id=?',
            (user_id,),
        )


# ============================================================
# Account-Lockout (Phase 6.2)
# ============================================================

LOCKOUT_THRESHOLD = int(os.getenv('ACCOUNT_LOCKOUT_THRESHOLD', '5'))
LOCKOUT_DURATION_SECONDS = int(os.getenv('ACCOUNT_LOCKOUT_SECONDS', '900'))  # 15 min


def is_account_locked(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> tuple[bool, int]:
    """Prüft ob Account gesperrt ist. Gibt (locked, seconds_remaining) zurück."""
    ensure_db(db_path)
    import time
    con = _connect(db_path)
    row = con.execute(
        'SELECT locked_until FROM users WHERE id=?', (user_id,),
    ).fetchone()
    con.close()
    if not row:
        return False, 0
    locked_until = int(row['locked_until'] or 0)
    now = int(time.time())
    if locked_until > now:
        return True, locked_until - now
    return False, 0


def record_failed_login(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> tuple[int, int]:
    """Erhöht den Failed-Login-Counter. Bei Schwelle: Account sperren.

    Returns: (new_count, locked_for_seconds_or_0)
    """
    ensure_db(db_path)
    import time
    con = _connect(db_path)
    row = con.execute(
        'SELECT failed_login_count FROM users WHERE id=?', (user_id,),
    ).fetchone()
    if not row:
        con.close()
        return 0, 0
    new_count = int(row['failed_login_count'] or 0) + 1
    locked_for = 0
    if new_count >= LOCKOUT_THRESHOLD:
        locked_until = int(time.time()) + LOCKOUT_DURATION_SECONDS
        locked_for = LOCKOUT_DURATION_SECONDS
        con.execute(
            'UPDATE users SET failed_login_count=?, locked_until=?, last_failed_login=aics_now() WHERE id=?',
            (new_count, locked_until, user_id),
        )
    else:
        con.execute(
            'UPDATE users SET failed_login_count=?, last_failed_login=aics_now() WHERE id=?',
            (new_count, user_id),
        )
    con.commit()
    con.close()
    return new_count, locked_for


def unlock_account(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Admin-Funktion: Account-Sperre aufheben + Counter zurücksetzen."""
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.execute(
        'UPDATE users SET failed_login_count=0, locked_until=0 WHERE id=?',
        (user_id,),
    )
    con.commit()
    affected = cur.rowcount
    con.close()
    return affected > 0
    con.close()


def delete_user(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.execute('DELETE FROM users WHERE id=?', (user_id,))
    deleted = cur.rowcount > 0
    con.commit()
    con.close()
    return deleted


def verify_password(user: dict[str, Any], password: str) -> bool:
    if not user or not user.get('password_hash'):
        return False
    return check_password_hash(user['password_hash'], password)


# ============================================================
# Token-Blacklist
# ============================================================

def revoke_token(jti: str, user_id: str = '', expires_at: int = 0,
                 db_path: Path = DEFAULT_DB_PATH) -> None:
    """Token-JTI als revoked markieren."""
    if not jti:
        return
    ensure_db(db_path)
    # #1394: 'INSERT OR REPLACE' ist SQLite-Syntax → unter Postgres SyntaxError
    # (Logout/Token-Revocation crashte mit 'syntax error at or near "OR"').
    # Portabel via ON CONFLICT auf dem PK (jti).
    with _connect(db_path) as con:
        con.execute(
            'INSERT INTO revoked_tokens (jti, user_id, expires_at) VALUES (?, ?, ?) '
            'ON CONFLICT (jti) DO UPDATE SET user_id=EXCLUDED.user_id, '
            'expires_at=EXCLUDED.expires_at',
            (jti, user_id, expires_at),
        )


def is_token_revoked(jti: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Prüft ob JTI in der Blacklist ist."""
    if not jti:
        return False
    ensure_db(db_path)
    con = _connect(db_path)
    row = con.execute('SELECT jti FROM revoked_tokens WHERE jti=?', (jti,)).fetchone()
    con.close()
    return row is not None


# ============================================================
# 2FA / TOTP (Phase 7.3)
# ============================================================

def get_totp_state(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """Liest TOTP-Status eines Users (secret, enabled, backup_code_hashes)."""
    ensure_db(db_path)
    con = _connect(db_path)
    row = con.execute(
        'SELECT totp_secret, totp_enabled, totp_backup_codes_json FROM users WHERE id=?',
        (user_id,),
    ).fetchone()
    con.close()
    if not row:
        return {'secret': None, 'enabled': False, 'backup_code_hashes': []}
    try:
        codes = json.loads(row['totp_backup_codes_json'] or '[]')
        if not isinstance(codes, list):
            codes = []
    except Exception:
        codes = []
    # At-rest entschlüsseln (#742). Bestandsdaten im Klartext bleiben lesbar
    # (decrypt_field gibt nicht-präfixierte Werte unverändert zurück).
    stored_secret = row['totp_secret']
    if stored_secret:
        try:
            secret = decrypt_field(stored_secret)
        except Exception:
            log.warning("TOTP-Secret-Entschlüsselung fehlgeschlagen für User %s — "
                        "Rohwert wird verwendet", user_id, exc_info=True)
            secret = stored_secret  # defensiv: niemals Login hart blockieren
        # Transparente Migration: Klartext-Secret beim Lesen verschlüsselt
        # zurückschreiben, damit Bestandsdaten nicht dauerhaft im Klartext liegen.
        if not is_encrypted_field(stored_secret):
            mcon = None
            try:
                mcon = _connect(db_path)
                mcon.execute(
                    'UPDATE users SET totp_secret=? WHERE id=?',
                    (encrypt_field(secret), user_id),
                )
                mcon.commit()
            except Exception:
                # best-effort: Migration darf den Lesepfad nicht brechen
                log.warning("Transparente TOTP-Secret-Migration für User %s "
                            "fehlgeschlagen", user_id, exc_info=True)
            finally:
                if mcon is not None:
                    mcon.close()
    else:
        secret = None
    return {
        'secret': secret,
        'enabled': bool(int(row['totp_enabled'] or 0)),
        'backup_code_hashes': codes,
    }


def set_totp_secret(user_id: str, secret: str | None,
                    db_path: Path = DEFAULT_DB_PATH) -> None:
    """Setzt das TOTP-Secret (noch nicht aktiviert) — at-rest verschlüsselt (#742)."""
    ensure_db(db_path)
    enc = encrypt_field(secret) if secret else None
    con = _connect(db_path)
    con.execute(
        'UPDATE users SET totp_secret=?, updated_at=aics_now() WHERE id=?',
        (enc, user_id),
    )
    con.commit()
    con.close()


def enable_totp(user_id: str, backup_code_hashes: list[str],
                db_path: Path = DEFAULT_DB_PATH) -> None:
    """Aktiviert TOTP nach erfolgreicher Verifizierung + speichert Backup-Codes."""
    ensure_db(db_path)
    con = _connect(db_path)
    con.execute(
        '''UPDATE users SET totp_enabled=1, totp_backup_codes_json=?,
                            updated_at=aics_now() WHERE id=?''',
        (json.dumps(backup_code_hashes), user_id),
    )
    con.commit()
    con.close()


def disable_totp(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Deaktiviert TOTP, löscht Secret + Backup-Codes."""
    ensure_db(db_path)
    con = _connect(db_path)
    con.execute(
        '''UPDATE users SET totp_enabled=0, totp_secret=NULL,
                            totp_backup_codes_json='[]',
                            updated_at=aics_now() WHERE id=?''',
        (user_id,),
    )
    con.commit()
    con.close()


def update_totp_backup_codes(user_id: str, backup_code_hashes: list[str],
                              db_path: Path = DEFAULT_DB_PATH) -> None:
    """Schreibt eine neue Liste an Backup-Code-Hashes (z.B. nach Consume)."""
    ensure_db(db_path)
    con = _connect(db_path)
    con.execute(
        'UPDATE users SET totp_backup_codes_json=?, updated_at=aics_now() WHERE id=?',
        (json.dumps(backup_code_hashes), user_id),
    )
    con.commit()
    con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Passwort-Reset-Tokens (#407)
# ─────────────────────────────────────────────────────────────────────────────


def create_password_reset_token(
    user_id: str, ttl_seconds: int = 3600, db_path: Path = DEFAULT_DB_PATH,
) -> str:
    """Erzeugt einen Single-Use Reset-Token, gültig ttl_seconds (default 1h)."""
    import secrets

    ensure_db(db_path)
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    con = _connect(db_path)
    con.execute(
        'INSERT INTO password_reset_tokens (token, user_id, created_at, expires_at) '
        'VALUES (?, ?, ?, ?)',
        (token, user_id, now, now + ttl_seconds),
    )
    con.commit()
    con.close()
    return token


def consume_password_reset_token(
    token: str, new_password: str, db_path: Path = DEFAULT_DB_PATH,
) -> tuple[bool, str | None, str | None]:
    """Verbraucht Token und setzt neues Passwort.

    Returns (ok, user_id, error). error ist gesetzt wenn ok=False.
    """
    ensure_db(db_path)
    now = int(time.time())
    con = _connect(db_path)
    row = con.execute(
        'SELECT user_id, expires_at, used_at FROM password_reset_tokens WHERE token=?',
        (token,),
    ).fetchone()
    if not row:
        con.close()
        return False, None, 'Token ungültig'
    if row['used_at'] is not None:
        con.close()
        return False, None, 'Token bereits verwendet'
    if row['expires_at'] < now:
        con.close()
        return False, None, 'Token abgelaufen'

    user_id = row['user_id']
    con.execute(
        'UPDATE users SET password_hash=?, failed_login_count=0, locked_until=0, '
        'updated_at=aics_now() WHERE id=?',
        (generate_password_hash(new_password), user_id),
    )
    con.execute(
        'UPDATE password_reset_tokens SET used_at=? WHERE token=?',
        (now, token),
    )
    con.commit()
    con.close()
    return True, user_id, None


def cleanup_expired_revocations(db_path: Path = DEFAULT_DB_PATH) -> int:
    """Entfernt revoked_tokens deren expires_at überschritten ist."""
    ensure_db(db_path)
    now = int(time.time())
    con = _connect(db_path)
    cur = con.execute('DELETE FROM revoked_tokens WHERE expires_at > 0 AND expires_at < ?', (now,))
    deleted = cur.rowcount
    con.commit()
    con.close()
    return deleted


# ─────────────────────────────────────────────────────────────────────────────
# WebAuthn / Passkeys (Sprint ε, Phase A)
# ─────────────────────────────────────────────────────────────────────────────


def add_webauthn_credential(
    user_id: str,
    credential_id: str,
    public_key: str,
    sign_count: int = 0,
    transports: list[str] | None = None,
    aaguid: str = '',
    nickname: str = '',
    backup_eligible: bool = False,
    backup_state: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """Speichert eine neue Passkey-Credential. credential_id/public_key base64url."""
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.execute(
        '''INSERT INTO webauthn_credentials
             (user_id, credential_id, public_key, sign_count, transports_json,
              aaguid, nickname, backup_eligible, backup_state)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_id, credential_id, public_key, sign_count,
         json.dumps(transports or []), aaguid, nickname,
         1 if backup_eligible else 0, 1 if backup_state else 0),
    )
    cred_db_id = cur.lastrowid
    con.commit()
    con.close()
    return int(cred_db_id)


def _row_to_credential(row: Any) -> dict[str, Any]:
    return {
        'id': row['id'],
        'user_id': row['user_id'],
        'credential_id': row['credential_id'],
        'public_key': row['public_key'],
        'sign_count': int(row['sign_count'] or 0),
        'transports': json.loads(row['transports_json'] or '[]'),
        'aaguid': row['aaguid'] or '',
        'nickname': row['nickname'] or '',
        'backup_eligible': bool(int(row['backup_eligible'] or 0)),
        'backup_state': bool(int(row['backup_state'] or 0)),
        'created_at': row['created_at'],
        'last_used_at': row['last_used_at'],
    }


def list_webauthn_credentials(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    rows = con.execute(
        'SELECT * FROM webauthn_credentials WHERE user_id=? ORDER BY created_at ASC', (user_id,),
    ).fetchall()
    con.close()
    return [_row_to_credential(r) for r in rows]


def get_webauthn_credential_by_cred_id(
    credential_id: str, db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    row = con.execute(
        'SELECT * FROM webauthn_credentials WHERE credential_id=?', (credential_id,),
    ).fetchone()
    con.close()
    return _row_to_credential(row) if row else None


def count_webauthn_credentials(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    n = con.execute(
        'SELECT COUNT(*) FROM webauthn_credentials WHERE user_id=?', (user_id,),
    ).fetchone()[0]
    con.close()
    return int(n)


def update_webauthn_sign_count(
    credential_id: str, sign_count: int, db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """Aktualisiert sign_count + last_used_at nach erfolgreicher Authentifizierung."""
    ensure_db(db_path)
    con = _connect(db_path)
    con.execute(
        'UPDATE webauthn_credentials SET sign_count=?, last_used_at=aics_now() '
        'WHERE credential_id=?',
        (sign_count, credential_id),
    )
    con.commit()
    con.close()


def rename_webauthn_credential(
    cred_db_id: int, user_id: str, nickname: str, db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    """Benennt eine Credential um (nur Eigentümer)."""
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.execute(
        'UPDATE webauthn_credentials SET nickname=? WHERE id=? AND user_id=?',
        (nickname[:120], cred_db_id, user_id),
    )
    changed = cur.rowcount
    con.commit()
    con.close()
    return changed > 0


def delete_webauthn_credential(
    cred_db_id: int, user_id: str, db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    """Löscht eine Credential (nur Eigentümer)."""
    ensure_db(db_path)
    con = _connect(db_path)
    cur = con.execute(
        'DELETE FROM webauthn_credentials WHERE id=? AND user_id=?',
        (cred_db_id, user_id),
    )
    changed = cur.rowcount
    con.commit()
    con.close()
    return changed > 0


# --- ephemere Challenges -------------------------------------------------------


def store_webauthn_challenge(
    challenge: str, typ: str, user_id: str | None = None,
    ttl_seconds: int = 300, db_path: Path = DEFAULT_DB_PATH,
) -> str:
    """Legt eine ephemere Challenge ab (typ: 'register' | 'authenticate').

    Liefert eine challenge_id, die das Frontend zurückgibt. Challenge selbst
    (base64url) wird serverseitig gehalten — kein Vertrauen auf Client-Echo.
    """
    import secrets
    ensure_db(db_path)
    challenge_id = secrets.token_urlsafe(24)
    now = int(time.time())
    con = _connect(db_path)
    con.execute(
        '''INSERT INTO webauthn_challenges
             (challenge_id, user_id, challenge, typ, created_at, expires_at)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (challenge_id, user_id, challenge, typ, now, now + ttl_seconds),
    )
    con.commit()
    con.close()
    return challenge_id


def consume_webauthn_challenge(
    challenge_id: str, typ: str, db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    """Liest + löscht eine Challenge (Single-Use). None wenn fehlend/abgelaufen/Typ-Mismatch."""
    ensure_db(db_path)
    now = int(time.time())
    con = _connect(db_path)
    row = con.execute(
        'SELECT challenge_id, user_id, challenge, typ, expires_at '
        'FROM webauthn_challenges WHERE challenge_id=?',
        (challenge_id,),
    ).fetchone()
    if row:
        con.execute('DELETE FROM webauthn_challenges WHERE challenge_id=?', (challenge_id,))
        con.commit()
    con.close()
    if not row:
        return None
    if row['typ'] != typ or int(row['expires_at']) < now:
        return None
    return {
        'challenge_id': row['challenge_id'],
        'user_id': row['user_id'],
        'challenge': row['challenge'],
        'typ': row['typ'],
    }


def cleanup_expired_webauthn_challenges(db_path: Path = DEFAULT_DB_PATH) -> int:
    ensure_db(db_path)
    now = int(time.time())
    con = _connect(db_path)
    cur = con.execute('DELETE FROM webauthn_challenges WHERE expires_at < ?', (now,))
    deleted = cur.rowcount
    con.commit()
    con.close()
    return deleted


# ─────────────────────────────────────────────────────────────────────────────
# MFA-Enforcement-Grace (Sprint ε, Phase D)
# ─────────────────────────────────────────────────────────────────────────────


def get_mfa_grace_until(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Liefert den Unix-Timestamp, bis zu dem MFA-Einrichtung aufgeschoben ist (0 = unset)."""
    ensure_db(db_path)
    con = _connect(db_path)
    row = con.execute('SELECT mfa_grace_until FROM users WHERE id=?', (user_id,)).fetchone()
    con.close()
    return int(row['mfa_grace_until'] or 0) if row else 0


def set_mfa_grace_until(user_id: str, until_ts: int, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Setzt das Grace-Ende (einmalig beim ersten Login unter Policy)."""
    ensure_db(db_path)
    con = _connect(db_path)
    con.execute(
        'UPDATE users SET mfa_grace_until=?, updated_at=aics_now() WHERE id=?',
        (int(until_ts), user_id),
    )
    con.commit()
    con.close()


def user_has_mfa(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """True, wenn der User TOTP aktiviert hat ODER mindestens einen Passkey besitzt."""
    state = get_totp_state(user_id, db_path=db_path)
    if state['enabled']:
        return True
    return count_webauthn_credentials(user_id, db_path=db_path) > 0
