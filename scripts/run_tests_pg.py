"""Lokaler Test-Runner gegen eingebettetes PostgreSQL (Docker-frei).

Startet eine dedizierte, eingebettete Test-PG (über ``shared.dev_postgres``) IM
SELBEN PROZESS wie pytest — so bleibt die Instanz für den gesamten Lauf am Leben
(ein Wegwerf-Subprozess würde sie per atexit sofort wieder stoppen → PoolTimeout
bei der Collection, weil Module wie ``server.api.firmen`` schon beim Import
``ensure_db`` aufrufen).

Nutzt ein eigenes Datenverzeichnis (NICHT ``data/pg-dev`` des Dev-Servers), damit
lokale Demo-/Testdaten nicht angefasst werden.

    python scripts/run_tests_pg.py [pytest-args…]
    python scripts/run_tests_pg.py tests/test_firmen_url_evidence_1025.py -q
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

# Repo-Root in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    os.environ.setdefault("AICS_DEV_PGDATA", "/tmp/aics-test-pg")
    os.environ.setdefault("JWT_SECRET_KEY", secrets.token_hex(32))
    os.environ.setdefault("ENABLE_DEMO_USERS", "true")
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("DB_POOL_MAX", "20")
    os.environ.setdefault("DB_POOL_MIN", "2")
    os.environ.setdefault("AICS_CONFIG_AUTO_REPAIR_SIDECAR", "1")
    # #1340: Test-Isolation nur berührte Schemata leeren (sonst ~5 s/Test).
    os.environ.setdefault("AICS_TRACK_SCHEMAS", "1")

    from shared.dev_postgres import ensure_dev_database_url

    url = ensure_dev_database_url()
    if not url:
        print("FEHLER: kein eingebettetes Postgres möglich (pgserver fehlt?)")
        return 2
    print(f"[run_tests_pg] DATABASE_URL gesetzt (Test-PG, {os.environ['AICS_DEV_PGDATA']})")

    import pytest

    return pytest.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
