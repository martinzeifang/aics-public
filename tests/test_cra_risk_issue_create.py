"""#1008 — CRA-Risiko → GitHub-Issue per Endpoint (Create + List).

VCS-Erstellung gemockt (kein Netz). Muster: test_per_project_repo_cra_862.py.
"""
from __future__ import annotations

import sqlite3

import pytest

from server.api.cra import DB_PATH
from cra.db import ensure_db, save_projekt, delete_projekt
from risikobewertung.db import save_projekt as rb_save, save_risiko, load_risiken

CRA_PROJ = "Risk1008-CRA"
RB_PROJ = "Risk1008-RB"
RB_DB = "data/db/risikobewertung.sqlite"


class _FakeCreated:
    def __init__(self, number, url):
        self.number = number
        self.url = url


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def risk_id():
    """CRA-Projekt + verknüpfte RB mit einem Risiko; gibt die Risk-ID zurück."""
    ensure_db(DB_PATH)
    from pathlib import Path
    rb_save(Path(RB_DB), RB_PROJ, framework="STRIDE", beschreibung="")
    rid = save_risiko(Path(RB_DB), {
        "projekt_name": RB_PROJ, "nr": 1, "risk_name": "SQL-Injection im Login",
        "beschreibung": "Ungeprüfte Eingaben", "framework": "STRIDE",
        "risikowert": 16, "risiko_label": "hoch",
    })
    save_projekt(DB_PATH, name=CRA_PROJ, unternehmen="ACME", produkt="Widget",
                 meta={"linked_risk_projekt": RB_PROJ})
    yield rid
    # Cleanup
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (CRA_PROJ,))
        con.commit(); con.close()
    except Exception:
        pass
    delete_projekt(DB_PATH, CRA_PROJ)
    try:
        con = sqlite3.connect(RB_DB)
        con.execute("DELETE FROM rb_risiken WHERE projekt_name=?", (RB_PROJ,))
        con.execute("DELETE FROM rb_projekte WHERE name=?", (RB_PROJ,))
        con.commit(); con.close()
    except Exception:
        pass


def _url(risk_id, suffix=""):
    return f"/api/cra/projekte/{CRA_PROJ}/risiken/{risk_id}/issues{suffix}"


def test_create_risk_issue_uses_saved_repo(client, auth_headers, monkeypatch, risk_id):
    client.put(f"/api/cra/projekte/{CRA_PROJ}/repo-config",
               json={"vcs_publish": {"provider": "github", "repo": "acme/app"}},
               headers=auth_headers)

    calls = {}

    def _fake_create_issue(*, repo, title, body):
        calls["repo"] = repo
        calls["title"] = title
        calls["body"] = body
        return _FakeCreated(number=77, url=f"https://github.com/{repo}/issues/77")

    monkeypatch.setattr("vcs.github_issues.create_issue", _fake_create_issue)

    r = client.post(_url(risk_id), json={}, headers=auth_headers)
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["created"] is True
    assert body["issue_number"] == 77
    assert calls["repo"] == "acme/app"
    # Default-Title enthält Risiko-Name + Label
    assert "SQL-Injection im Login" in calls["title"]
    assert "hoch" in calls["title"]
    assert "STRIDE" in calls["body"]

    # List zeigt den neuen Link
    g = client.get(_url(risk_id), headers=auth_headers)
    assert g.status_code == 200
    links = g.get_json()
    assert len(links) == 1
    assert links[0]["issue_number"] == 77
    assert links[0]["provider"] == "github"


def test_create_risk_issue_no_repo_returns_400(client, auth_headers, risk_id):
    r = client.post(_url(risk_id), json={}, headers=auth_headers)
    assert r.status_code == 400
    assert "Repository" in r.get_json()["error"]


def test_create_risk_issue_unknown_risk_404(client, auth_headers, risk_id):
    client.put(f"/api/cra/projekte/{CRA_PROJ}/repo-config",
               json={"vcs_publish": {"provider": "github", "repo": "acme/app"}},
               headers=auth_headers)
    r = client.post(_url(999999), json={}, headers=auth_headers)
    assert r.status_code == 404
