"""#1008 — CRA-Risiko-Issue-Sync: Status-Refresh + Auto-Resolve des Risikos.

sync_github_issue gemockt (kein Netz).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from server.api.cra import DB_PATH
from cra.db import ensure_db, save_projekt, delete_projekt
from risikobewertung.db import save_projekt as rb_save, save_risiko, load_risiken
from shared.issue_links import add_link, ensure_tables, list_links
from shared.issue_sync import SyncedIssue

CRA_PROJ = "RiskSync1008-CRA"
RB_PROJ = "RiskSync1008-RB"
RB_DB = "data/db/risikobewertung.sqlite"


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
    ensure_db(DB_PATH)
    rb_save(Path(RB_DB), RB_PROJ, framework="STRIDE", beschreibung="")
    rid = save_risiko(Path(RB_DB), {
        "projekt_name": RB_PROJ, "nr": 1, "risk_name": "XSS in Suche",
        "beschreibung": "Reflektiertes XSS", "framework": "STRIDE",
        "risikowert": 12, "risiko_label": "mittel",
    })
    save_projekt(DB_PATH, name=CRA_PROJ, unternehmen="ACME", produkt="Widget",
                 meta={"linked_risk_projekt": RB_PROJ})
    yield rid
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


def _sync_url(risk_id):
    return f"/api/cra/projekte/{CRA_PROJ}/risiken/{risk_id}/issues/sync"


def test_sync_closed_issue_marks_risk_resolved(client, auth_headers, monkeypatch, risk_id):
    # Vorhandenen Link anlegen (als wäre Issue zuvor erstellt worden).
    ensure_tables(DB_PATH)
    add_link(DB_PATH, projekt_name=CRA_PROJ, object_kind="risk", object_id=str(risk_id),
             provider="github", repo="acme/app", url="https://github.com/acme/app/issues/5",
             issue_number=5, title="XSS")

    def _fake_sync(*, repo, number):
        return SyncedIssue(provider="github", repo=repo, number=number, iid=None,
                           url=f"https://github.com/{repo}/issues/{number}", title="XSS",
                           state="closed", state_reason="completed", labels=["done"])

    monkeypatch.setattr("shared.issue_sync.sync_github_issue", _fake_sync)

    r = client.post(_sync_url(risk_id), headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["synced"] == 1
    assert body["resolved"] is True

    # Link-State aktualisiert
    links = list_links(DB_PATH, projekt_name=CRA_PROJ, object_kind="risk", object_id=str(risk_id))
    assert links and links[0].state == "closed"

    # Risiko in der RB-DB ist als behoben markiert
    risks = {str(r["id"]): r for r in load_risiken(Path(RB_DB), RB_PROJ)}
    assert risks[str(risk_id)].get("is_resolved") in (1, True)


def test_sync_without_links_returns_zero(client, auth_headers, risk_id):
    r = client.post(_sync_url(risk_id), headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()["synced"] == 0
