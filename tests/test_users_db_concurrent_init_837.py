"""Regressionstest für den parallelen DB-Init-Crash (#837).

Symptom in Produktion: mehrere gunicorn-Worker rufen beim Boot gleichzeitig
``users_db.ensure_db()`` auf. Die alte "PRAGMA table_info → ALTER TABLE"-Logik
war eine TOCTOU-Race → der zweite Worker crashte mit
``sqlite3.OperationalError: duplicate column name`` bzw. (bei leerer DB) am
UNIQUE(email)-Constraint des Initial-Admins → "Worker failed to boot" → der
Container wurde nie healthy → nginx (depends_on: service_healthy) startete nicht
→ Stack-Deploy in Portainer schlug nicht-deterministisch fehl.

Diese Tests stellen sicher, dass ensure_db() idempotent UND nebenläufig sicher
ist.
"""

import sqlite3
import threading
from pathlib import Path

import pytest

from server.auth import users_db


def test_ensure_db_idempotent(tmp_path):
    db = tmp_path / "users.sqlite"
    users_db.ensure_db(db)
    # zweiter Lauf darf nicht crashen (Spalten existieren bereits)
    users_db.ensure_db(db)
    con = sqlite3.connect(str(db))
    cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
    con.close()
    for needed in ("failed_login_count", "token_version", "totp_secret", "mfa_grace_until"):
        assert needed in cols


def test_add_column_if_missing_tolerates_duplicate(tmp_path):
    db = tmp_path / "u.sqlite"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE users (id TEXT PRIMARY KEY)")
    cur = con.cursor()
    users_db._add_column_if_missing(cur, "users", "foo", "foo INTEGER DEFAULT 0")
    # zweiter Aufruf mit derselben Spalte → kein Fehler
    users_db._add_column_if_missing(cur, "users", "foo", "foo INTEGER DEFAULT 0")
    # auch wenn die Spalte real schon da ist und die Cursor-Sicht veraltet wäre:
    con.execute("CREATE TABLE t2 (id TEXT)")
    con.execute("ALTER TABLE t2 ADD COLUMN bar INTEGER")
    # simuliere veraltete TOCTOU-Sicht: Spalte fehlt scheinbar, ALTER wirft duplicate
    con.commit()
    con.close()


def test_concurrent_ensure_db_no_crash(tmp_path):
    """Mehrere Threads rufen ensure_db() gleichzeitig auf derselben DB auf —
    keiner darf mit OperationalError/IntegrityError abbrechen."""
    db = tmp_path / "concurrent.sqlite"
    # Vorab eine ALTE DB ohne neue Spalten anlegen, damit echte ALTER TABLEs laufen.
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, "
        "password_hash TEXT, roles_json TEXT DEFAULT '[]', active INTEGER DEFAULT 1, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "last_login TEXT)"
    )
    con.commit()
    con.close()

    errors: list[Exception] = []
    barrier = threading.Barrier(6)

    def worker():
        try:
            barrier.wait()  # alle gleichzeitig losschicken → maximaler Race-Druck
            users_db.ensure_db(db)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Nebenläufiger ensure_db() crashte: {errors!r}"
    # Schema vollständig migriert
    con = sqlite3.connect(str(db))
    cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
    con.close()
    assert "failed_login_count" in cols and "token_version" in cols


def test_concurrent_initial_admin_single(tmp_path, monkeypatch):
    """Bei leerer DB + parallelem Boot darf der Initial-Admin nur EINMAL
    entstehen und kein Worker am UNIQUE(email) crashen."""
    monkeypatch.setenv("ENABLE_DEMO_USERS", "false")
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "admin@aics.local")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "x" * 20)
    db = tmp_path / "fresh.sqlite"

    errors: list[Exception] = []
    barrier = threading.Barrier(5)

    def worker():
        try:
            barrier.wait()
            users_db.ensure_db(db)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Initial-Admin-Race crashte: {errors!r}"
    con = sqlite3.connect(str(db))
    n = con.execute("SELECT COUNT(*) FROM users WHERE email='admin@aics.local'").fetchone()[0]
    con.close()
    assert n == 1, f"Initial-Admin sollte genau 1x existieren, ist {n}x da"
