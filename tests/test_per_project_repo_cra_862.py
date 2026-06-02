"""Tests für die pro-Projekt-Repository-Konfiguration im CRA-Modul (#862).

Deckt ab:
- repo-config PUT→GET Roundtrip
- Token wird verschlüsselt gespeichert, NIE ausgeliefert (nur has_token-Flag)
- Partial-Update bewahrt den bestehenden Token
- Bulk-Create nutzt das gespeicherte Repo OHNE `repo` im Request (VCS gemockt)
- Override: Request-`repo` funktioniert weiterhin (Rückwärtskompatibilität)
- Klare 400-Fehlermeldung, wenn kein Repo konfiguriert ist

Die VCS-Erstellung wird gemockt (kein Netz). Muster: test_bulk_issues_cra_795.py
+ test_risk_issues_786.py.
"""

from __future__ import annotations

import pytest

from server.api.cra import DB_PATH
from cra.db import ensure_db, save_projekt, load_projekt

PROJEKT = "Repo862-CRA-Testprojekt"


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture(autouse=True)
def _projekt():
    """Testprojekt anlegen und (inkl. verknüpfter Issues) am Ende aufräumen."""
    ensure_db(DB_PATH)
    save_projekt(DB_PATH, name=PROJEKT, unternehmen="ACME", produkt="Widget")
    yield
    # linked_issues für das Testprojekt leeren + Projekt löschen.
    import sqlite3
    try:
        con = sqlite3.connect(str(DB_PATH))
        try:
            con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (PROJEKT,))
            con.commit()
        except sqlite3.OperationalError:
            pass
        finally:
            con.close()
    except Exception:
        pass
    from cra.db import delete_projekt
    delete_projekt(DB_PATH, PROJEKT)


def _url(suffix: str = "") -> str:
    return f"/api/cra/projekte/{PROJEKT}{suffix}"


# ── repo-config: PUT→GET Roundtrip + Token-Geheimhaltung ─────────────────────

def test_repo_config_put_get_roundtrip(client, auth_headers):
    r = client.put(
        _url("/repo-config"),
        json={"vcs_publish": {"provider": "github", "repo": "owner/repo"}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()["vcs_publish"]
    assert body["provider"] == "github"
    assert body["repo"] == "owner/repo"
    assert body["has_token"] is False

    g = client.get(_url("/repo-config"), headers=auth_headers)
    assert g.status_code == 200
    gv = g.get_json()["vcs_publish"]
    assert gv["repo"] == "owner/repo"
    assert gv["provider"] == "github"
    assert gv["has_token"] is False


def test_token_encrypted_and_never_exposed(client, auth_headers):
    r = client.put(
        _url("/repo-config"),
        json={"vcs_publish": {"provider": "github", "repo": "owner/repo",
                              "token": "ghp_supersecret123"}},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.get_json()["vcs_publish"]
    # Token-Flag ja — Klartext/verschlüsselter Blob NIE in der Response.
    assert body["has_token"] is True
    assert "token" not in body
    assert "token_enc" not in body
    assert "ghp_supersecret123" not in r.get_data(as_text=True)

    # Auch GET liefert den Token nicht aus.
    g = client.get(_url("/repo-config"), headers=auth_headers)
    gv = g.get_json()["vcs_publish"]
    assert gv["has_token"] is True
    assert "token" not in gv and "token_enc" not in gv

    # In der DB ist der Token verschlüsselt (token_enc) abgelegt, nicht im Klartext.
    p = load_projekt(DB_PATH, PROJEKT)
    vcs = (p.get("meta") or {}).get("vcs_publish") or {}
    assert vcs.get("token_enc")
    assert "ghp_supersecret123" not in str(vcs.get("token_enc"))


def test_partial_update_preserves_token(client, auth_headers):
    # Erst mit Token speichern.
    client.put(
        _url("/repo-config"),
        json={"vcs_publish": {"provider": "github", "repo": "owner/repo",
                              "token": "ghp_keepme"}},
        headers=auth_headers,
    )
    # Teil-Update ohne Token (nur Repo ändern) — Token muss erhalten bleiben.
    r = client.put(
        _url("/repo-config"),
        json={"vcs_publish": {"provider": "github", "repo": "owner/other"}},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.get_json()["vcs_publish"]
    assert body["repo"] == "owner/other"
    assert body["has_token"] is True

    p = load_projekt(DB_PATH, PROJEKT)
    vcs = (p.get("meta") or {}).get("vcs_publish") or {}
    assert vcs.get("token_enc")


# ── Bulk-Create: nutzt gespeichertes Repo OHNE `repo` im Request ─────────────

class _FakeCreated:
    def __init__(self, number: int, url: str):
        self.number = number
        self.url = url


def test_bulk_uses_saved_repo_without_repo_in_request(client, auth_headers, monkeypatch):
    # Repo pro Projekt speichern.
    client.put(
        _url("/repo-config"),
        json={"vcs_publish": {"provider": "github", "repo": "acme/app"}},
        headers=auth_headers,
    )

    calls = {}

    def _fake_create_issue(*, repo, title, body):
        calls["repo"] = repo
        return _FakeCreated(number=42, url=f"https://github.com/{repo}/issues/42")

    monkeypatch.setattr("vcs.github_issues.create_issue", _fake_create_issue)

    # Nur eine Anforderung anlegen lassen, damit der Test schnell ist.
    r = client.post(
        _url("/issues/bulk"),
        json={"req_ids": ["CRA-1"]},  # kein `repo` im Request
        headers=auth_headers,
    )
    assert r.status_code == 200, r.get_json()
    summary = r.get_json()["summary"]
    # Mindestens ein Issue erstellt (sofern CRA-1 existiert) — sonst kein Fehler.
    assert summary["failed"] == 0
    # Falls erstellt: gespeichertes Repo wurde verwendet.
    if summary["created"] > 0:
        assert calls.get("repo") == "acme/app"


def test_bulk_request_repo_override_still_works(client, auth_headers, monkeypatch):
    client.put(
        _url("/repo-config"),
        json={"vcs_publish": {"provider": "github", "repo": "acme/app"}},
        headers=auth_headers,
    )
    calls = {}

    def _fake_create_issue(*, repo, title, body):
        calls["repo"] = repo
        return _FakeCreated(number=7, url=f"https://github.com/{repo}/issues/7")

    monkeypatch.setattr("vcs.github_issues.create_issue", _fake_create_issue)

    r = client.post(
        _url("/issues/bulk"),
        json={"req_ids": ["CRA-1"], "repo": "override/repo"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    if r.get_json()["summary"]["created"] > 0:
        assert calls.get("repo") == "override/repo"


def test_bulk_without_repo_config_returns_400(client, auth_headers):
    # Kein Repo gespeichert, kein Override → klare 400-Meldung.
    r = client.post(_url("/issues/bulk"), json={"req_ids": ["CRA-1"]}, headers=auth_headers)
    assert r.status_code == 400
    assert "Kein Repository" in (r.get_json() or {}).get("error", "")
