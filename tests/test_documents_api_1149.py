"""Sprint #24 (#1153) — Dokumenten-REST je Modul (Smoke + Export)."""
from __future__ import annotations

import pytest

PROJ = "ZZ-DocTest-1149"
URLMODS = ["aiact", "cra", "nis2", "dsgvo", "wiba"]


def _cleanup(modul_db, modul):
    from pathlib import Path
    from shared.documents import db as ddb
    try:
        for d in ddb.list_documents(Path(f"data/db/{modul_db}"), modul, PROJ, include_deleted=True):
            pass  # Records bleiben (Soft-Delete-Semantik); Testprojekt ist isoliert
    except Exception:
        pass


def test_catalog_endpoints_all_modules(client, auth_headers):
    for um in URLMODS:
        r = client.get(f"/api/{um}-dokumente/{PROJ}/catalog", headers=auth_headers)
        assert r.status_code == 200, f"{um}: {r.get_data(as_text=True)}"
        body = r.get_json()
        assert "katalog" in body
        if um != "wiba":
            assert len(body["katalog"]) >= 5


def test_document_crud_and_export(client, auth_headers):
    base = "/api/cra-dokumente"
    # anlegen
    r = client.post(f"{base}/{PROJ}", json={
        "doc_type": "vuln_disclosure_policy",
        "content_html": "<h1>CVD</h1><p>Melden an <strong>security@x</strong>.</p>",
        "source": "manuell"}, headers=auth_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    did = r.get_json()["id"]
    # Katalog zeigt jetzt vorhanden/entwurf
    cat = client.get(f"{base}/{PROJ}/catalog", headers=auth_headers).get_json()
    cvd = next(e for e in cat["katalog"] if e["doc_type"] == "vuln_disclosure_policy")
    assert cvd["vorhanden"] and cvd["status"] == "entwurf"
    # Status → final
    r2 = client.post(f"{base}/{PROJ}/{did}/status", json={"status": "final"}, headers=auth_headers)
    assert r2.status_code == 200 and r2.get_json()["dokument"]["status"] == "final"
    # PUT erhöht Version
    r3 = client.put(f"{base}/{PROJ}/{did}", json={"content_html": "<h1>CVD v2</h1>"}, headers=auth_headers)
    assert r3.get_json()["dokument"]["version"] == 2
    # Export DOCX
    r4 = client.post(f"{base}/{PROJ}/{did}/export?format=docx", headers=auth_headers)
    assert r4.status_code == 200 and r4.data[:2] == b"PK"
    # Soft-Delete
    assert client.delete(f"{base}/{PROJ}/{did}", headers=auth_headers).status_code == 200
    assert client.get(f"{base}/{PROJ}/{did}", headers=auth_headers).status_code == 404
