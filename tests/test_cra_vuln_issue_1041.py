"""#1041 — CRA-Schwachstelle (CVE) → GitHub-Issue per Endpoint + Sync.

VCS/Sync gemockt (kein Netz). Muster: test_cra_risk_issue_*.py (#1008).
"""
from __future__ import annotations

import sqlite3

import pytest

from server.api.cra import DB_PATH
from cra.db import ensure_db, save_projekt, delete_projekt, upsert_vuln, list_vuln
from shared.issue_links import add_link, ensure_tables, list_links
from shared.issue_sync import SyncedIssue

CRA_PROJ = "Vuln1041-CRA"


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
def vuln_id():
    ensure_db(DB_PATH)
    save_projekt(DB_PATH, name=CRA_PROJ, unternehmen="ACME", produkt="Widget",
                 produktklasse="default", beschreibung="", berater="")
    upsert_vuln(DB_PATH, CRA_PROJ, {
        'cve_id': 'CVE-2026-4242', 'titel': 'RCE in libfoo', 'schwere': 'critical',
        'cvss_score': 9.8, 'affected_component': 'libfoo', 'fixed_in_version': '2.1.0',
        'advisory_url': 'https://example/advisory', 'status': 'open',
    })
    vid = next(v['id'] for v in list_vuln(DB_PATH, CRA_PROJ) if v['cve_id'] == 'CVE-2026-4242')
    yield vid
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (CRA_PROJ,))
        con.execute("DELETE FROM cra_vuln WHERE projekt_name=?", (CRA_PROJ,))
        con.commit(); con.close()
    except Exception:
        pass
    delete_projekt(DB_PATH, CRA_PROJ)


def _u(vid, sfx=""):
    return f"/api/cra/projekte/{CRA_PROJ}/vulns/{vid}/issues{sfx}"


def test_create_vuln_issue(client, auth_headers, monkeypatch, vuln_id):
    client.put(f"/api/cra/projekte/{CRA_PROJ}/repo-config",
               json={"vcs_publish": {"provider": "github", "repo": "acme/app"}}, headers=auth_headers)
    calls = {}

    def _fake_create(*, repo, title, body):
        calls['repo'] = repo; calls['title'] = title; calls['body'] = body
        return _FakeCreated(number=88, url=f"https://github.com/{repo}/issues/88")
    monkeypatch.setattr("vcs.github_issues.create_issue", _fake_create)

    r = client.post(_u(vuln_id), json={}, headers=auth_headers)
    assert r.status_code == 201, r.get_json()
    assert r.get_json()['issue_number'] == 88
    assert calls['repo'] == 'acme/app'
    assert 'CVE-2026-4242' in calls['title'] and 'critical' in calls['title']
    assert 'libfoo' in calls['body']

    g = client.get(_u(vuln_id), headers=auth_headers)
    assert g.status_code == 200 and len(g.get_json()) == 1


def test_create_vuln_issue_no_repo_400(client, auth_headers, vuln_id):
    r = client.post(_u(vuln_id), json={}, headers=auth_headers)
    assert r.status_code == 400


def test_create_vuln_issue_unknown_404(client, auth_headers, vuln_id):
    client.put(f"/api/cra/projekte/{CRA_PROJ}/repo-config",
               json={"vcs_publish": {"provider": "github", "repo": "acme/app"}}, headers=auth_headers)
    r = client.post(_u(999999), json={}, headers=auth_headers)
    assert r.status_code == 404


def test_sync_marks_vuln_fixed(client, auth_headers, monkeypatch, vuln_id):
    ensure_tables(DB_PATH)
    add_link(DB_PATH, projekt_name=CRA_PROJ, object_kind="vuln", object_id=str(vuln_id),
             provider="github", repo="acme/app", url="https://github.com/acme/app/issues/7",
             issue_number=7, title="CVE")

    def _fake_sync(*, repo, number):
        return SyncedIssue(provider="github", repo=repo, number=number, iid=None,
                           url=f"https://github.com/{repo}/issues/{number}", title="CVE",
                           state="closed", state_reason="completed", labels=["fixed"])
    monkeypatch.setattr("shared.issue_sync.sync_github_issue", _fake_sync)

    r = client.post(_u(vuln_id, "/sync"), headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['resolved'] is True

    v = next(v for v in list_vuln(DB_PATH, CRA_PROJ) if str(v['id']) == str(vuln_id))
    assert v['status'] == 'fixed'
    # Bestehende Felder NICHT verloren (kein Wipe durch upsert)
    assert v['titel'] == 'RCE in libfoo' and v['affected_component'] == 'libfoo'


def test_unlink_vuln_issue(client, auth_headers, vuln_id):
    ensure_tables(DB_PATH)
    lid = add_link(DB_PATH, projekt_name=CRA_PROJ, object_kind="vuln", object_id=str(vuln_id),
                   provider="github", repo="acme/app", url="https://github.com/acme/app/issues/9",
                   issue_number=9, title="CVE")
    r = client.delete(f"/api/cra/projekte/{CRA_PROJ}/vulns/issues/{lid}", headers=auth_headers)
    assert r.status_code == 200
    assert len(list_links(DB_PATH, projekt_name=CRA_PROJ, object_kind="vuln", object_id=str(vuln_id))) == 0
