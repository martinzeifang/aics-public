"""Tests für #744 (WP-11): Deployment-/Container-Härtung & Supply-Chain.

Deckt ab:
  - Health-Endpoint liefert weiterhin 200 + JSON mit status-Feld (minimal).
  - Demo-User werden in FLASK_ENV=production NICHT geseedet (fail-closed),
    selbst wenn ENABLE_DEMO_USERS=true gesetzt ist.
  - Swagger/OpenAPI-UI wird in Produktion nicht ausgeliefert.

Die Tests vermeiden eine Re-Konfiguration der Session-App; demo/swagger-Logik
wird über frisch erzeugte App-Instanzen bzw. die Seeding-Helper direkt geprüft.
"""

import sqlite3

import pytest


@pytest.fixture(autouse=True)
def _full_license():
    """Schreibzugriffe auf lizenzierte Module sollen in CI nicht 423 liefern."""
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


class TestHealthEndpoint:
    def test_health_200_json_status(self, client):
        """/health: 200 + JSON mit status-Feld (Docker/Nginx-Healthcheck)."""
        r = client.get('/health')
        assert r.status_code == 200
        assert r.is_json
        assert 'status' in r.json

    def test_api_health_200_json_status(self, client):
        r = client.get('/api/health')
        assert r.status_code == 200
        assert 'status' in r.json

    def test_health_body_is_minimal(self, client):
        """Kein internes Detail (Service-Name) mehr im Body preisgeben."""
        r = client.get('/health')
        assert 'service' not in r.json


def _count_users(db_path):
    con = sqlite3.connect(db_path)
    try:
        return con.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    finally:
        con.close()


def _demo_user_exists(db_path, email='admin@example.com'):
    con = sqlite3.connect(db_path)
    try:
        row = con.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone()
        return row is not None
    finally:
        con.close()


class TestDemoUserFailClosed:
    def test_demo_users_seeded_in_testing(self, tmp_path, monkeypatch):
        """Testing/Dev: ENABLE_DEMO_USERS=true → Demo-User werden angelegt."""
        from server.auth.users_db import ensure_db
        monkeypatch.setenv('ENABLE_DEMO_USERS', 'true')
        monkeypatch.setenv('FLASK_ENV', 'testing')
        db = tmp_path / 'users_testing.sqlite'
        ensure_db(db)
        assert _demo_user_exists(db), 'Demo-User müssen in testing existieren (Login muss klappen)'

    def test_demo_users_refused_in_production(self, tmp_path, monkeypatch):
        """Production: ENABLE_DEMO_USERS=true wird ignoriert (fail-closed)."""
        from server.auth.users_db import ensure_db
        monkeypatch.setenv('ENABLE_DEMO_USERS', 'true')
        monkeypatch.setenv('FLASK_ENV', 'production')
        # INITIAL_ADMIN_* nicht setzen → es entsteht höchstens ein Initial-Admin,
        # aber KEINE Demo-User mit bekannten Klartext-Passwörtern.
        db = tmp_path / 'users_prod.sqlite'
        ensure_db(db)
        assert not _demo_user_exists(db, 'admin@example.com'), \
            'Demo-User admin@example.com darf in production NICHT existieren'
        assert not _demo_user_exists(db, 'editor@example.com'), \
            'Demo-User editor@example.com darf in production NICHT existieren'


class TestSwaggerGating:
    def test_swagger_available_outside_production(self, client):
        """Session-App läuft in testing → Swagger-UI muss erreichbar bleiben."""
        r = client.get('/api/docs/')
        assert r.status_code == 200

    def test_swagger_not_registered_in_production(self, monkeypatch):
        """Production: Swagger/OpenAPI-UI wird nicht registriert (404)."""
        monkeypatch.setenv('FLASK_ENV', 'production')
        # Demo aus, damit kein Demo-Seeding in den frisch erzeugten Prod-App-Lauf
        # gerät; JWT-Secret ist via conftest gesetzt.
        monkeypatch.setenv('ENABLE_DEMO_USERS', 'false')
        from server.app import create_app
        prod_app = create_app()
        prod_app.config['TESTING'] = True
        c = prod_app.test_client()
        assert c.get('/api/docs/').status_code == 404
        assert c.get('/api/apispec.json').status_code == 404
        # Health bleibt trotzdem verfügbar.
        assert c.get('/health').status_code == 200


class TestCorsProductionFailClosed:
    def test_cors_drops_http_origins_in_production(self, monkeypatch):
        """Production: explizit gesetzte http://-Origins werden verworfen."""
        monkeypatch.setenv('FLASK_ENV', 'production')
        monkeypatch.setenv('ENABLE_DEMO_USERS', 'false')
        monkeypatch.setenv('CORS_ORIGINS', 'http://evil.example,https://app.example')
        from server.app import create_app
        prod_app = create_app()
        # Flask-CORS speichert die aufgelöste Origin-Liste nicht direkt; wir prüfen
        # das Verhalten am gefilterten Default-Resultat über einen Preflight.
        c = prod_app.test_client()
        # HTTPS-Origin erlaubt:
        ok = c.open('/api/health', method='OPTIONS', headers={
            'Origin': 'https://app.example',
            'Access-Control-Request-Method': 'GET',
        })
        assert ok.headers.get('Access-Control-Allow-Origin') == 'https://app.example'
        # HTTP-Origin NICHT erlaubt (kein ACAO-Header für diese Origin):
        bad = c.open('/api/health', method='OPTIONS', headers={
            'Origin': 'http://evil.example',
            'Access-Control-Request-Method': 'GET',
        })
        assert bad.headers.get('Access-Control-Allow-Origin') != 'http://evil.example'
