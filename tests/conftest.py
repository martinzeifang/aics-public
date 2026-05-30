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
