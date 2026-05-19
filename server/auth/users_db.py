"""User-Datenbank mit SQLite — ersetzt MOCK_USERS.

Schema:
- users(id, email UNIQUE, password_hash, roles_json, active, created_at, updated_at)
- revoked_tokens(jti, user_id, revoked_at, expires_at)

Default-Demo-Users werden nur angelegt wenn ENABLE_DEMO_USERS=true (DEV-Modus).
In Production müssen User über die Admin-API explizit angelegt werden.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from werkzeug.security import generate_password_hash, check_password_hash

DEFAULT_DB_PATH = Path('data/db/users.sqlite')


def _connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA foreign_keys=ON')
    return con


def ensure_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Tabellen anlegen + ggf. Demo-Users."""
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )
    """)
    # Migration: alte DB ohne neue Spalten
    cur.execute("PRAGMA table_info(users)")
    cols = {r[1] for r in cur.fetchall()}
    if 'allowed_modules_json' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN allowed_modules_json TEXT DEFAULT 'null'")
    if 'extra_permissions_json' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN extra_permissions_json TEXT DEFAULT '[]'")
    if 'display_name' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''")
    # Phase 6.2: Account-Lockout
    if 'failed_login_count' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN failed_login_count INTEGER DEFAULT 0")
    if 'locked_until' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN locked_until INTEGER DEFAULT 0")
    if 'last_failed_login' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN last_failed_login TEXT")
    # Phase 7.3: 2FA (TOTP)
    if 'totp_secret' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT")
    if 'totp_enabled' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN totp_enabled INTEGER DEFAULT 0")
    if 'totp_backup_codes_json' not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN totp_backup_codes_json TEXT DEFAULT '[]'")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            jti TEXT PRIMARY KEY,
            user_id TEXT,
            revoked_at TEXT DEFAULT CURRENT_TIMESTAMP,
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

    # Default-Users nur in DEV-Modus
    enable_demo = os.getenv('ENABLE_DEMO_USERS', 'false').lower() in ('true', '1', 'yes')
    cur.execute('SELECT COUNT(*) FROM users')
    user_count = cur.fetchone()[0]
    if enable_demo and user_count == 0:
        _create_demo_users(con)
    elif user_count == 0:
        _create_initial_admin(con)

    con.close()


def _create_demo_users(con: sqlite3.Connection) -> None:
    """Legt admin@example.com und editor@example.com an (DEV-Modus)."""
    demo_users = [
        ('user-001', 'admin@example.com', 'admin-password', ['admin']),
        ('user-002', 'editor@example.com', 'editor-password', ['cra_editor']),
    ]
    for uid, email, pw, roles in demo_users:
        con.execute(
            'INSERT INTO users (id, email, password_hash, roles_json, active) VALUES (?, ?, ?, ?, 1)',
            (uid, email, generate_password_hash(pw), json.dumps(roles)),
        )
    con.commit()


def _create_initial_admin(con: sqlite3.Connection) -> None:
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
    except sqlite3.IntegrityError:
        # Race mit parallelem Worker (gunicorn): ein anderer hat den Admin bereits
        # angelegt und das Passwort geloggt. Silent skip — kein doppeltes Logging.
        return

    bar = '=' * 64
    print('', flush=True)
    print(bar, flush=True)
    print('🔐 INITIAL ADMIN USER ANGELEGT (DB war leer beim Start)', flush=True)
    print(bar, flush=True)
    print(f'   Email:    {email}', flush=True)
    print(f'   Password: {password}', flush=True)
    print(bar, flush=True)
    print('   ⚠️  Passwort jetzt notieren — es wird NICHT erneut angezeigt.', flush=True)
    print('   ⚠️  Nach erstem Login: Profil → Passwort ändern.', flush=True)
    print(bar, flush=True)
    print('', flush=True)


# ============================================================
# User-CRUD
# ============================================================

def _row_to_user(row: dict | sqlite3.Row) -> dict[str, Any]:
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
    fields.append('updated_at=CURRENT_TIMESTAMP')
    params.append(user_id)

    con = _connect(db_path)
    con.execute(f'UPDATE users SET {", ".join(fields)} WHERE id=?', params)
    con.commit()
    con.close()
    return True


def update_last_login(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    # Erfolgreicher Login → Counter zurücksetzen
    con.execute(
        'UPDATE users SET last_login=CURRENT_TIMESTAMP, failed_login_count=0, locked_until=0 WHERE id=?',
        (user_id,),
    )
    con.commit()


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
            'UPDATE users SET failed_login_count=?, locked_until=?, last_failed_login=CURRENT_TIMESTAMP WHERE id=?',
            (new_count, locked_until, user_id),
        )
    else:
        con.execute(
            'UPDATE users SET failed_login_count=?, last_failed_login=CURRENT_TIMESTAMP WHERE id=?',
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
    con = _connect(db_path)
    con.execute(
        'INSERT OR REPLACE INTO revoked_tokens (jti, user_id, expires_at) VALUES (?, ?, ?)',
        (jti, user_id, expires_at),
    )
    con.commit()
    con.close()


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
    return {
        'secret': row['totp_secret'],
        'enabled': bool(int(row['totp_enabled'] or 0)),
        'backup_code_hashes': codes,
    }


def set_totp_secret(user_id: str, secret: str | None,
                    db_path: Path = DEFAULT_DB_PATH) -> None:
    """Setzt das TOTP-Secret (noch nicht aktiviert)."""
    ensure_db(db_path)
    con = _connect(db_path)
    con.execute(
        'UPDATE users SET totp_secret=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
        (secret, user_id),
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
                            updated_at=CURRENT_TIMESTAMP WHERE id=?''',
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
                            updated_at=CURRENT_TIMESTAMP WHERE id=?''',
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
        'UPDATE users SET totp_backup_codes_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
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
        'updated_at=CURRENT_TIMESTAMP WHERE id=?',
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
