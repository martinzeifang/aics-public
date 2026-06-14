"""Sprint #28 (#1235) — Wizard-Ergebnis → editier-/exportierbares managed_doc."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def docs_db(tmp_path):
    db = tmp_path / "assistant_1235.sqlite"
    yield db
    for e in ("", "-wal", "-shm"):
        p = Path(str(db) + e)
        if p.exists():
            p.unlink()


# ── Source-Normalisierung (Bugfix: 'assistant' → 'assistent') ───────────────

def test_normalize_source_alias():
    from shared.documents import db as ddb
    assert ddb.normalize_source("assistant") == "assistent"
    assert ddb.normalize_source("assistent") == "assistent"
    assert ddb.normalize_source("import") == "import"
    assert ddb.normalize_source("unbekannt") == "manuell"
    assert ddb.normalize_source(None) == "manuell"


def test_create_from_assistant_keeps_provenance(docs_db):
    from shared.documents import db as ddb
    # Frontend-Wert 'assistant' darf NICHT zu 'manuell' degradieren.
    did = ddb.create_document(docs_db, "cra", projekt="P",
                              doc_type="vuln_disclosure_policy",
                              source="assistant", assistant_key="vuln-policy",
                              content_html="<h1>CVD</h1>")
    d = ddb.get_document(docs_db, "cra", did)
    assert d["source"] == "assistent" and d["assistant_key"] == "vuln-policy"


# ── API-Round-Trip: anlegen (assistent) → editieren → freigeben → exportieren ─

PROJ = "ZZ-Assistant-1235"


def test_round_trip_create_edit_release_export(client, auth_headers):
    base = "/api/cra-dokumente"
    # 1) per Assistent anlegen
    r = client.post(f"{base}/{PROJ}", json={
        "doc_type": "update_policy",
        "source": "assistant",
        "assistant_key": "update-policy",
        "content_html": "<h1>Update-Policy</h1><p>Monatlich.</p>"}, headers=auth_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    did = r.get_json()["id"]
    doc = client.get(f"{base}/{PROJ}/{did}", headers=auth_headers).get_json()
    assert doc["source"] == "assistent" and doc["assistant_key"] == "update-policy"
    # 2) editieren → Version steigt
    up = client.put(f"{base}/{PROJ}/{did}",
                    json={"content_html": "<h1>Update-Policy v2</h1>"}, headers=auth_headers)
    assert up.get_json()["dokument"]["version"] == 2
    # 3) freigeben
    st = client.post(f"{base}/{PROJ}/{did}/status",
                     json={"status": "freigegeben"}, headers=auth_headers)
    assert st.status_code == 200 and st.get_json()["dokument"]["sha256"]
    # 4) DOCX-Export
    dx = client.post(f"{base}/{PROJ}/{did}/export?format=docx", headers=auth_headers)
    assert dx.status_code == 200 and dx.data[:2] == b"PK"
    # 5) PDF-Export (Konverter ggf. nicht verfügbar → 503 toleriert)
    pdf = client.post(f"{base}/{PROJ}/{did}/export?format=pdf", headers=auth_headers)
    assert pdf.status_code in (200, 503)
    if pdf.status_code == 200:
        assert pdf.data[:4] == b"%PDF"
    # aufräumen
    client.delete(f"{base}/{PROJ}/{did}", headers=auth_headers)
