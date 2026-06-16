"""Tests für pro-Projekt-Repo-Konfiguration + Issue-Erstellung (DSGVO, #862).

Deckt ab:
- repo-config Roundtrip (GET/PUT)
- Token wird verschlüsselt gespeichert und NIE ausgeliefert (has_token)
- Partial-Update bewahrt bestehenden Token
- Bulk-Create nutzt gespeichertes Repo OHNE 'repo' im Request (GitHub gemockt)
- Bulk-Create ohne Repo-Konfig → 400

Kein Netz: vcs.github_issues.create_issue wird gemockt.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from dsgvo.db import (
    save_projekt,
    delete_projekt,
    save_bewertung,
    load_projekt,
)
from dsgvo.requirements import load_merged_anforderungen
from server.api.dsgvo import DB_PATH

PROJEKT = "ZZ-Test-Repo-862-DSGVO"


@pytest.fixture
def base(app):
    """Ermittelt das registrierte URL-Präfix der DSGVO-repo-config-Route."""
    target = "/projekte/<projekt_name>/repo-config"
    for rule in app.url_map.iter_rules():
        s = str(rule)
        if s.endswith(target) and "dsgvo" in s:
            return s[: -len(target)]  # z.B. '/api/dsgvo'
    return "/api/dsgvo"


@pytest.fixture(autouse=True)
def _license_ok(monkeypatch):
    """Gültige Lizenz (state='ok', modules=['*']) — defensiv, falls Routen gegated."""
    fake = {"state": "ok", "modules": ["*"]}
    for mod in ("server.license_state",):
        try:
            m = __import__(mod, fromlist=["get_state"])
        except Exception:
            continue
        if hasattr(m, "get_state"):
            monkeypatch.setattr(m, "get_state", lambda: dict(fake), raising=False)
    yield


@pytest.fixture
def projekt():
    """Legt ein DSGVO-Testprojekt an und räumt am Ende inkl. Issue-Links auf."""
    # sauberer Start
    try:
        delete_projekt(DB_PATH, PROJEKT)
    except Exception:
        pass
    save_projekt(DB_PATH, name=PROJEKT, unternehmen="Test GmbH")
    yield PROJEKT
    # Aufräumen: linked_issues leeren + Projekt löschen
    try:
        from shared.issue_links import list_project_links, delete_link
        for link in list_project_links(DB_PATH, projekt_name=PROJEKT):
            delete_link(DB_PATH, link.id)
    except Exception:
        pass
    try:
        delete_projekt(DB_PATH, PROJEKT)
    except Exception:
        pass


def _put_repo(client, headers, base, name, payload):
    return client.put(
        f"{base}/projekte/{name}/repo-config",
        json={"vcs_publish": payload},
        headers=headers,
    )


# ── Repo-Config Roundtrip + Token-Geheimhaltung ─────────────────────

def test_repo_config_roundtrip(client, auth_headers, projekt, base):
    # Initial leer
    r = client.get(f"{base}/projekte/{projekt}/repo-config", headers=auth_headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    vcs = r.get_json()["vcs_publish"]
    assert vcs.get("has_token") is False
    assert "token_enc" not in vcs and "token" not in vcs

    # Speichern inkl. Token
    r = _put_repo(client, auth_headers, base, projekt,
                  {"provider": "github", "repo": "owner/repo", "token": "geheim-123"})
    assert r.status_code == 200, r.get_data(as_text=True)
    vcs = r.get_json()["vcs_publish"]
    assert vcs["repo"] == "owner/repo"
    assert vcs["has_token"] is True
    assert "token" not in vcs and "token_enc" not in vcs

    # Erneutes GET: Repo da, aber kein Klartext-Token
    r = client.get(f"{base}/projekte/{projekt}/repo-config", headers=auth_headers)
    vcs = r.get_json()["vcs_publish"]
    assert vcs["repo"] == "owner/repo"
    assert vcs["has_token"] is True
    assert "token" not in vcs and "token_enc" not in vcs


def test_token_encrypted_at_rest(client, auth_headers, projekt, base):
    _put_repo(client, auth_headers, base, projekt,
              {"provider": "github", "repo": "owner/repo", "token": "klartext-geheim"})
    p = load_projekt(DB_PATH, projekt)
    meta = p.get("meta") if isinstance(p.get("meta"), dict) else {}
    stored = (meta.get("vcs_publish") or {}).get("token_enc", "")
    assert stored, "Token muss als token_enc gespeichert sein"
    assert "klartext-geheim" not in stored


def test_partial_update_preserves_token(client, auth_headers, projekt, base):
    _put_repo(client, auth_headers, base, projekt,
              {"provider": "github", "repo": "owner/repo", "token": "erstes-token"})
    # Update ohne neuen Token → Token bewahrt
    r = _put_repo(client, auth_headers, base, projekt,
                  {"provider": "github", "repo": "owner/neu", "token": ""})
    assert r.status_code == 200
    vcs = r.get_json()["vcs_publish"]
    assert vcs["repo"] == "owner/neu"
    assert vcs["has_token"] is True


# ── Bulk-Create nutzt gespeichertes Repo OHNE 'repo' im Request ──────

def test_bulk_create_uses_stored_repo(client, auth_headers, projekt, base, monkeypatch):
    # Repo + Token speichern
    _put_repo(client, auth_headers, base, projekt,
              {"provider": "github", "repo": "owner/repo", "token": "tok"})

    # Mindestens eine Gap-Bewertung (Bewertung < 5) setzen
    reqs = load_merged_anforderungen(DB_PATH)
    assert reqs, "DSGVO-Anforderungskatalog darf nicht leer sein"
    gap_id = str(reqs[0]["id"])
    save_bewertung(DB_PATH, projekt, gap_id, 2, "Lücke", "beheben")

    # GitHub-create_issue mocken (KEIN Netz)
    from vcs.github_issues import CreatedIssue
    calls = []

    def fake_create_issue(*, repo, title, body):
        calls.append({"repo": repo, "title": title})
        return CreatedIssue(number=len(calls), url=f"https://github.com/{repo}/issues/{len(calls)}")

    monkeypatch.setattr("vcs.github_issues.create_issue", fake_create_issue)

    # Bulk OHNE repo im Request → gespeichertes Repo wird genutzt
    r = client.post(
        f"{base}/projekte/{projekt}/issues/bulk",
        json={},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data["created"] >= 1
    assert calls, "create_issue muss aufgerufen worden sein"
    assert all(c["repo"] == "owner/repo" for c in calls)
    assert any(c["title"].startswith("AICS · DSGVO-Gap [") for c in calls)


def test_bulk_create_without_repo_config_returns_400(client, auth_headers, projekt, base):
    r = client.post(
        f"{base}/projekte/{projekt}/issues/bulk",
        json={},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "Repository" in r.get_json().get("error", "")
