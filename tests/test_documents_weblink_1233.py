"""Sprint #28 (#1233) — Web-Verknüpfung: doc_mode/external_url + SSRF + Check.

DB-Schicht hermetisch (tmp-DB), API-Schicht über den Test-Client.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def docs_db(tmp_path):
    db = tmp_path / "weblink_1233.sqlite"
    yield db
    for e in ("", "-wal", "-shm"):
        p = Path(str(db) + e)
        if p.exists():
            p.unlink()


# ── DB-Schicht ────────────────────────────────────────────────────────────────

def test_migration_adds_columns_idempotent(docs_db):
    from shared.documents import db as ddb
    import sqlite3
    ddb.ensure_documents_table(docs_db, "cra")
    ddb.ensure_documents_table(docs_db, "cra")  # idempotent
    con = sqlite3.connect(str(docs_db))
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(cra_managed_docs)")}
    finally:
        con.close()
    assert {"doc_mode", "external_url", "external_label",
            "external_checked_at", "external_reachable"} <= cols


def test_migration_on_legacy_table(docs_db):
    """Bestands-DB ohne neue Spalten wird per ALTER TABLE nachgezogen."""
    import sqlite3
    from shared.documents import db as ddb
    table = ddb.table_name("cra")
    con = sqlite3.connect(str(docs_db))
    try:
        con.execute(f"""CREATE TABLE {table} (
            id INTEGER PRIMARY KEY AUTOINCREMENT, projekt TEXT NOT NULL,
            firmen_id INTEGER, doc_type TEXT, titel TEXT, status TEXT DEFAULT 'entwurf',
            content_html TEXT, content_format TEXT DEFAULT 'html', version INTEGER DEFAULT 1,
            source TEXT DEFAULT 'manuell', assistant_key TEXT, sha256 TEXT,
            meta_json TEXT DEFAULT '{{}}', created_at TEXT, created_by TEXT,
            updated_at TEXT, updated_by TEXT, deleted_at TEXT, deleted_by TEXT)""")
        con.execute(f"INSERT INTO {table}(projekt, doc_type, titel) VALUES('P','x','Alt')")
        con.commit()
    finally:
        con.close()
    ddb.ensure_documents_table(docs_db, "cra")  # migriert
    docs = ddb.list_documents(docs_db, "cra", "P")
    assert len(docs) == 1 and docs[0]["doc_mode"] == "inapp"  # Default rückwärtskompat.


def test_default_mode_is_inapp(docs_db):
    from shared.documents import db as ddb
    did = ddb.create_document(docs_db, "cra", projekt="P", doc_type="x")
    d = ddb.get_document(docs_db, "cra", did)
    assert d["doc_mode"] == "inapp" and d["external_url"] is None


def test_create_extern_and_switch_invalidates_check(docs_db):
    from shared.documents import db as ddb
    did = ddb.create_document(docs_db, "cra", projekt="P", doc_type="x",
                              doc_mode="extern", external_url="https://example.com/d",
                              external_label="Doku")
    ddb.record_reachability(docs_db, "cra", did, reachable=True)
    d = ddb.get_document(docs_db, "cra", did)
    assert d["doc_mode"] == "extern" and d["external_reachable"] == 1
    # URL ändern → Erreichbarkeits-Cache wird invalidiert
    d2 = ddb.update_document(docs_db, "cra", did,
                             external_url="https://example.org/neu")
    assert d2["external_reachable"] is None and d2["external_checked_at"] is None
    # Moduswechsel zurück auf inapp invalidiert ebenfalls
    ddb.record_reachability(docs_db, "cra", did, reachable=True)
    d3 = ddb.update_document(docs_db, "cra", did, doc_mode="inapp")
    assert d3["external_reachable"] is None


# ── API-Schicht ───────────────────────────────────────────────────────────────

PROJ = "ZZ-WebLink-1233"


def test_api_extern_crud_and_ssrf(client, auth_headers):
    base = "/api/cra-dokumente"
    # extern anlegen mit öffentlicher URL
    r = client.post(f"{base}/{PROJ}", json={
        "doc_type": "technische_doku_annex_vii",
        "doc_mode": "extern",
        "external_url": "https://example.com/tech-doku",
        "external_label": "Tech-Doku"}, headers=auth_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    did = r.get_json()["id"]
    doc = client.get(f"{base}/{PROJ}/{did}", headers=auth_headers).get_json()
    assert doc["doc_mode"] == "extern" and doc["external_url"].startswith("https://example.com")
    # interne URL wird abgelehnt (SSRF)
    bad = client.put(f"{base}/{PROJ}/{did}", json={
        "doc_mode": "extern", "external_url": "http://127.0.0.1:8080/x"},
        headers=auth_headers)
    assert bad.status_code == 400
    # file://-Schema abgelehnt
    bad2 = client.put(f"{base}/{PROJ}/{did}", json={
        "doc_mode": "extern", "external_url": "file:///etc/passwd"},
        headers=auth_headers)
    assert bad2.status_code == 400
    # Status-Workflow auch im Extern-Modus
    st = client.post(f"{base}/{PROJ}/{did}/status", json={"status": "freigegeben"},
                     headers=auth_headers)
    assert st.status_code == 200 and st.get_json()["dokument"]["status"] == "freigegeben"
    # aufräumen
    client.delete(f"{base}/{PROJ}/{did}", headers=auth_headers)


def test_api_catalog_surfaces_doc_mode(client, auth_headers):
    base = "/api/aiact-dokumente"
    r = client.post(f"{base}/{PROJ}", json={
        "doc_type": "technische_doku_annex_iv", "doc_mode": "extern",
        "external_url": "https://example.com/ai-doku"}, headers=auth_headers)
    did = r.get_json()["id"]
    cat = client.get(f"{base}/{PROJ}/catalog", headers=auth_headers).get_json()
    entry = next(e for e in cat["katalog"] if e["doc_type"] == "technische_doku_annex_iv")
    assert entry["doc_mode"] == "extern" and entry["external_url"]
    client.delete(f"{base}/{PROJ}/{did}", headers=auth_headers)


def test_api_check_link_requires_extern(client, auth_headers):
    base = "/api/cra-dokumente"
    r = client.post(f"{base}/{PROJ}", json={"doc_type": "update_policy"},
                    headers=auth_headers)
    did = r.get_json()["id"]
    # inapp-Dokument hat keine URL → 400
    chk = client.post(f"{base}/{PROJ}/{did}/check-link", headers=auth_headers)
    assert chk.status_code == 400
    client.delete(f"{base}/{PROJ}/{did}", headers=auth_headers)
