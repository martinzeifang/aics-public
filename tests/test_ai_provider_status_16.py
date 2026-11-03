"""Tests für den KI-Provider-Status-Endpoint (Sprint #16, #867/#877).

Prüft:
- GET /api/ai/provider-status liefert das erwartete Schema.
- Der Endpoint ist JWT-geschützt (401 ohne Token).
- Es werden KEINE Secrets ausgeliefert (#737).
- allow_data_egress wird korrekt aus der Config abgeleitet.

Nutzt die Projekt-Fixtures aus ``tests/conftest.py`` (``client`` +
echtes Admin-Login über ``auth_headers``). Der Provider-Status wird über
eine echte temporäre Konfigurationsdatei (``AICS_CONFIG_PATH``) gesteuert —
genau den Pfad, den ``ai_compliance_suite.config.load_config`` auswertet.
"""

from __future__ import annotations

import json


def _write_config(tmp_path, ai_section: dict) -> str:
    cfg_path = tmp_path / "ai_compliance_suite.config.json"
    cfg_path.write_text(json.dumps({"ai": ai_section}), encoding="utf-8")
    return str(cfg_path)


def _get(client, headers):
    return client.get("/api/ai/provider-status", headers=headers)


def test_requires_jwt(client):
    """Ohne Token: 401."""
    resp = client.get("/api/ai/provider-status")
    assert resp.status_code == 401


def test_returns_expected_schema(client, auth_headers, monkeypatch, tmp_path):
    """Mit Token: 200 + erwartetes Schema (on_prem konfiguriert)."""
    monkeypatch.setenv(
        "AICS_CONFIG_PATH",
        _write_config(
            tmp_path,
            {
                "provider": "on_prem",
                "on_prem": {"model": "llama3.1:latest", "base_url": "http://127.0.0.1:11434"},
                "cloud": {"allow_data_egress": False, "model": "", "api_key_env": "AI_CLOUD_API_KEY"},
            },
        ),
    )

    resp = _get(client, auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()

    assert set(data.keys()) == {"provider", "label", "configured", "allow_data_egress"}
    assert data["provider"] == "on_prem"
    assert data["label"] == "Lokal (Ollama)"
    assert data["configured"] is True
    assert data["allow_data_egress"] is False


def test_on_prem_unconfigured_when_no_model(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setenv(
        "AICS_CONFIG_PATH",
        _write_config(tmp_path, {"provider": "on_prem", "on_prem": {"model": ""}, "cloud": {}}),
    )

    resp = _get(client, auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["provider"] == "on_prem"
    assert data["configured"] is False
    assert data["allow_data_egress"] is False


def test_cloud_egress_and_configured(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setenv(
        "AICS_CONFIG_PATH",
        _write_config(
            tmp_path,
            {
                "provider": "cloud",
                "on_prem": {"model": ""},
                "cloud": {
                    "allow_data_egress": True,
                    "model": "gpt-4.1-mini",
                    "api_key_env": "AI_CLOUD_API_KEY",
                    "base_url": "https://api.openai.com/v1",
                },
            },
        ),
    )

    resp = _get(client, auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["provider"] == "cloud"
    assert data["label"] == "Cloud"
    assert data["allow_data_egress"] is True
    assert data["configured"] is True


def test_cloud_blocked_when_egress_false(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setenv(
        "AICS_CONFIG_PATH",
        _write_config(
            tmp_path,
            {
                "provider": "cloud",
                "on_prem": {"model": ""},
                "cloud": {"allow_data_egress": False, "model": "gpt-4.1-mini"},
            },
        ),
    )

    resp = _get(client, auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["provider"] == "cloud"
    assert data["allow_data_egress"] is False
    # Egress blockiert ⇒ nicht einsatzbereit.
    assert data["configured"] is False


def test_no_secrets_in_response(client, auth_headers, monkeypatch, tmp_path):
    """Antwort darf keine Secrets/Token/Keys/URLs enthalten (#737)."""
    monkeypatch.setenv("AI_CLOUD_API_KEY", "sk-supersecret-value-1234567890")
    monkeypatch.setenv(
        "AICS_CONFIG_PATH",
        _write_config(
            tmp_path,
            {
                "provider": "cloud",
                "on_prem": {"model": "", "base_url": "http://127.0.0.1:11434"},
                "cloud": {
                    "allow_data_egress": True,
                    "model": "gpt-4.1-mini",
                    "api_key_env": "AI_CLOUD_API_KEY",
                    "base_url": "https://api.openai.com/v1",
                },
            },
        ),
    )

    resp = _get(client, auth_headers)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # Keine Secrets, keine internen URLs, kein ENV-Var-Name des Keys.
    assert "sk-supersecret" not in body
    assert "api.openai.com" not in body
    assert "127.0.0.1" not in body
    assert "AI_CLOUD_API_KEY" not in body
    # Es dürfen auch keine generischen Key/URL-Felder auftauchen.
    data = resp.get_json()
    for forbidden in ("api_key", "api_key_env", "base_url", "token", "model"):
        assert forbidden not in data
