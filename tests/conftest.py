"""Pytest-Konfiguration + Shared Fixtures."""

import os
import secrets
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope='session', autouse=True)
def setup_env():
    """ENV-Variablen für Test-Session setzen."""
    os.environ.setdefault('JWT_SECRET_KEY', secrets.token_hex(32))
    os.environ.setdefault('ENABLE_DEMO_USERS', 'true')
    os.environ.setdefault('FLASK_ENV', 'testing')


@pytest.fixture(scope='session')
def app():
    """Flask-App für Tests (single instance pro Session)."""
    from server.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def client(app):
    """Flask-Test-Client."""
    return app.test_client()


@pytest.fixture
def auth_token(client):
    """Liefert einen gültigen JWT-Token via Login (admin@example.com)."""
    response = client.post(
        '/api/auth/login',
        json={'email': 'admin@example.com', 'password': 'admin-password'},
    )
    assert response.status_code == 200, f'Login failed: {response.json}'
    return response.json['access_token']


@pytest.fixture
def auth_headers(auth_token):
    """Headers mit Bearer-Token."""
    return {'Authorization': f'Bearer {auth_token}'}


@pytest.fixture
def temp_db_dir(tmp_path):
    """Temp-Verzeichnis für isolierte DB-Tests."""
    db_dir = tmp_path / 'db'
    db_dir.mkdir()
    return db_dir


# ── PostgreSQL-Test-Harness (#1341) ─────────────────────────────────────────
# Stellt eine echte Postgres-DB für die portierten Module bereit:
#  - Ist DATABASE_URL gesetzt (CI-Service-Container), wird diese genutzt.
#  - Sonst wird via testcontainers ein ephemerer Wegwerf-Postgres gestartet
#    (Windows Docker-Desktop/WSL2 + Linux). Ohne Docker → PG_AVAILABLE=False,
#    Postgres-abhängige Tests werden übersprungen (SQLite-Tests laufen weiter).

PG_AVAILABLE = False
_PG_CONTAINER = None


@pytest.fixture(scope='session', autouse=True)
def _postgres_session():
    """Session-weit eine Postgres-DB bereitstellen (DATABASE_URL setzen)."""
    global PG_AVAILABLE, _PG_CONTAINER
    if os.environ.get('DATABASE_URL'):
        PG_AVAILABLE = True
        yield
        return
    try:
        from testcontainers.postgres import PostgresContainer
        _PG_CONTAINER = PostgresContainer('postgres:16-alpine')
        _PG_CONTAINER.start()
        url = _PG_CONTAINER.get_connection_url()
        for prefix in ('postgresql+psycopg2://', 'postgresql+psycopg://'):
            url = url.replace(prefix, 'postgresql://')
        os.environ['DATABASE_URL'] = url
        PG_AVAILABLE = True
    except Exception as exc:  # kein Docker / testcontainers nicht installiert
        PG_AVAILABLE = False
        print(f'[conftest] Postgres-Harness nicht verfügbar ({exc!r}) — '
              'PG-Tests werden übersprungen.')
    if PG_AVAILABLE:
        # #1340: Per-Test-Isolation auf berührte Schemata beschränken (Speed).
        try:
            from shared.db import enable_schema_tracking
            enable_schema_tracking()
        except Exception:
            pass
    yield
    if _PG_CONTAINER is not None:
        try:
            from shared.db import reset_pool
            reset_pool()
            _PG_CONTAINER.stop()
        except Exception:
            pass


@pytest.fixture
def pg(_postgres_session):
    """Fixture für Postgres-abhängige Tests; überspringt ohne verfügbares Postgres."""
    if not PG_AVAILABLE:
        pytest.skip('Postgres nicht verfügbar (kein DATABASE_URL / kein Docker)')
    from shared import db as _sdb
    return _sdb


@pytest.fixture(autouse=True)
def _pg_isolate(_postgres_session):
    """Per-Test-Isolation: vor jedem Test alle Modul-/Test-Schemata droppen (#1341).

    Läuft vor den modul-spezifischen DB-Fixtures (autouse), sodass deren ``ensure_db``
    in ein frisches Schema schreibt. App-State (users/audit/scheduler) bleibt erhalten.
    """
    import os as _os
    if PG_AVAILABLE and _os.environ.get("AICS_PG_ISOLATE", "1") == "1":
        from shared import db as _sdb
        try:
            _sdb.drop_test_schemas()
        except Exception:
            pass
    yield
