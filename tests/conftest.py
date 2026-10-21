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


@pytest.fixture(scope='session', autouse=True)
def _ensure_data_dirs():
    """#1395: Einige Tests schreiben Hilfsdateien direkt unter data/<modul>/ (z. B.
    data/gutachten/_footer_in.docx). data/ ist gitignored und im CI leer → sonst
    FileNotFoundError. Die gängigen Zielverzeichnisse idempotent anlegen."""
    for d in ('data/db', 'data/gutachten', 'data/cra', 'data/dsgvo', 'data/nis2',
              'data/aiact', 'data/ai_act', 'data/wiba', 'data/risikobewertung',
              'data/evidence', 'data/soc', 'data/pentest', 'data/cra/konformitaet'):
        try:
            Path(d).mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            pass
    yield


@pytest.fixture(scope='session', autouse=True)
def _license_wildcard():
    """#1546: Standard-Lizenz für die Test-Session = alle Module erlaubt.

    Ohne das greift das Modul-Lizenz-Gate (server/app.py, 423 'module-not-licensed')
    bei Tests gegen /api/<modul>-dokumente u. a., weil der Default-License-State leere
    Module hat. Tests, die das Gate gezielt prüfen, überschreiben _current selbst und
    stellen danach wieder her — das bleibt unberührt (prev = ['*'] → sauber).
    """
    try:
        from server import license_state
        cur = license_state._current
        cur.state, cur.modules = 'ok', ['*']
    except Exception:  # noqa: BLE001 — License-Modul optional
        pass
    yield


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
def _purge_test_users(_postgres_session):
    """#1530: Test-erzeugte User (alle außer den 3 Demo-Usern) vor jedem Test aus der
    geteilten ``public.users`` entfernen. Die Tabelle liegt im ``public``-Schema (App-State)
    und wird von der Per-Test-Schema-Isolation NICHT gedroppt — dadurch überlebten
    Test-User (z. B. ``alice@test.com``) zwischen Läufen/Tests und lösten beim erneuten
    ``create_user`` eine ``UniqueViolation`` auf ``users_email_key`` aus."""
    if PG_AVAILABLE:
        try:
            from server.auth import users_db as _udb
            _demo = {'admin@example.com', 'editor@example.com', 'soc@example.com'}
            for u in _udb.list_users():
                if u.get('email') not in _demo:
                    _udb.delete_user(u['id'])
            # Auth-Nebentabellen (public, keine FK) leeren → Isolation für webauthn/token-Tests,
            # die pro Test frische Credentials/Tokens erwarten (früher SQLite-Datei pro Test).
            con = _udb._connect(_udb.DEFAULT_DB_PATH)
            try:
                for tbl in ('webauthn_credentials', 'webauthn_challenges',
                            'revoked_tokens', 'password_reset_tokens'):
                    try:
                        con.execute(f'DELETE FROM {tbl}')
                    except Exception:
                        pass
                try:
                    con.commit()
                except Exception:
                    pass
            finally:
                con.close()
        except Exception:
            pass
    yield


@pytest.fixture(scope='session', autouse=True)
def _pg_frischer_start(_postgres_session):
    """Einmalig zu Sessionbeginn: Altbestand aus vorherigen Läufen entfernen (#1706).

    Die Per-Test-Isolation (:func:`_pg_isolate`) leert bei aktivem
    ``AICS_TRACK_SCHEMAS`` nur die **berührten** Schemata — das ist aus Geschwindigkeit
    so gewollt (#1340). Zu Beginn eines Prozesses ist diese Liste aber leer, also
    überlebt alles, was ein **vorheriger Lauf** liegen gelassen hat.

    Im CI fällt das nicht auf: Dort startet je Job eine frische Datenbank. Gegen eine
    dauerhafte Entwicklungs-Datenbank schlugen Tests dagegen je nach Vorgeschichte
    fehl — ``test_cra_vuln_sync_937`` etwa mit ``assert 3 == 1``, weil ``CVE-A``/``CVE-B``
    aus dem Vorlauf noch im Schema lagen.

    Erschwerend: **65 Testdateien** räumen per ``Path.unlink()`` auf. Unter dem
    Postgres-Kompat-Layer ist der Pfad nur ein Schema-Selektor, es gibt keine Datei —
    der Teardown ist ein No-op, sieht aber wie echtes Aufräumen aus. Genau dieser
    Altzustand hat in #1704 zu einer Fehldiagnose geführt (eine unschuldige Datei
    schien zu hängen). Deshalb wird hier zentral geleert, statt 65 Teardowns zu
    reparieren.
    """
    import os as _os
    if not (PG_AVAILABLE and _os.environ.get("AICS_PG_ISOLATE", "1") == "1"):
        yield
        return

    from shared import db as _sdb

    # Hausmeister: Jeder Lauf legt NEUE Wegwerf-Schemata an (tmp_path-/uuid-Namen).
    # Lokal hatten sich 1048 Schemata mit 7157 Tabellen angesammelt — ein TRUNCATE
    # darüber sprengt `max_locks_per_transaction` ("out of shared memory"), und genau
    # diese Ausnahme wurde früher verschluckt. Oberhalb der Schwelle wird deshalb
    # zuerst gelöscht; im CI (frische DB je Job) greift das nie.
    try:
        pool = _sdb.get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM information_schema.schemata")
                anzahl = cur.fetchone()[0]
            conn.commit()
        finally:
            pool.putconn(conn)
        if anzahl > 300:
            n = _sdb.drop_stale_test_schemas()
            print(f'[conftest] {anzahl} Schemata vorgefunden — {n} Altschemata '
                  f'geloescht (#1706).')
    except Exception:  # noqa: BLE001 — Hausmeister darf die Session nie verhindern
        pass

    # Datenbestand aus vorherigen Laeufen leeren. Truncate statt Drop: Die Tabellen
    # bleiben, also ist das nachgelagerte ensure_db ein Cache-Treffer (#1396) und die
    # DDL-Kosten je Testdatei bleiben aus.
    try:
        _sdb.drop_test_schemas(alle_schemata=True)
    except Exception:  # noqa: BLE001
        pass
    yield


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
