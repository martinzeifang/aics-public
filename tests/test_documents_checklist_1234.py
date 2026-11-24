"""Sprint #28 (#1234) — Konformitäts-Checkliste (Soll-Ist + Persistenz + Prompt)."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def docs_db(tmp_path):
    db = tmp_path / "checklist_1234.sqlite"
    yield db
    for e in ("", "-wal", "-shm"):
        p = Path(str(db) + e)
        if p.exists():
            p.unlink()


# ── Katalog (Soll) ──────────────────────────────────────────────────────────

def test_catalog_checklists_present():
    from shared.documents import catalog as dcat
    cra_tech = dcat.get_checklist("cra", "technische_doku_annex_vii")
    cra_info = dcat.get_checklist("cra", "benutzeranleitung_annex_ii")
    ai_tech = dcat.get_checklist("ai_act", "technische_doku_annex_iv")
    assert cra_tech and cra_info and ai_tech
    # Items haben stabile IDs + Rechtsbezug
    for cl in (cra_tech, cra_info, ai_tech):
        for it in cl:
            assert it["id"] and it["label"] and it["rechtsbezug"]
    # Dokumente ohne Checkliste → leer (Panel wird nicht angezeigt)
    assert dcat.get_checklist("cra", "konformitaetserklaerung") == []
    assert dcat.get_checklist("wiba", "nachweis_dokument") == []


def test_docspec_to_dict_includes_checklist():
    from shared.documents import catalog as dcat
    spec = dcat.get_doc_spec("cra", "technische_doku_annex_vii")
    assert isinstance(spec["checklist"], list) and len(spec["checklist"]) >= 5


# ── DB-Persistenz (eigene Tabelle) ──────────────────────────────────────────

def test_checklist_status_upsert(docs_db):
    from shared.documents import db as ddb
    did = ddb.create_document(docs_db, "cra", projekt="P",
                              doc_type="technische_doku_annex_vii")
    assert ddb.get_checklist_status(docs_db, "cra", did) == {}
    ddb.set_checklist_status(docs_db, "cra", did,
                             {"beschreibung": {"erfuellt": True, "kommentar": "ok"}},
                             updated_by="u")
    st = ddb.get_checklist_status(docs_db, "cra", did)
    assert st["beschreibung"]["erfuellt"] is True and st["beschreibung"]["kommentar"] == "ok"
    # Upsert überschreibt
    ddb.set_checklist_status(docs_db, "cra", did,
                             {"beschreibung": {"erfuellt": False}}, updated_by="u2")
    st2 = ddb.get_checklist_status(docs_db, "cra", did)
    assert st2["beschreibung"]["erfuellt"] is False


def test_checklist_toggle_does_not_bump_version(docs_db):
    """Entscheidung #1234: Checklisten-Häkchen in eigener Tabelle → keine Versionserhöhung."""
    from shared.documents import db as ddb
    did = ddb.create_document(docs_db, "cra", projekt="P",
                              doc_type="technische_doku_annex_vii")
    v0 = ddb.get_document(docs_db, "cra", did)["version"]
    ddb.set_checklist_status(docs_db, "cra", did, {"beschreibung": {"erfuellt": True}})
    assert ddb.get_document(docs_db, "cra", did)["version"] == v0


# ── API ──────────────────────────────────────────────────────────────────────

PROJ = "ZZ-Checklist-1234"


def test_api_checklist_roundtrip_and_progress(client, auth_headers):
    base = "/api/cra-dokumente"
    r = client.post(f"{base}/{PROJ}",
                    json={"doc_type": "technische_doku_annex_vii"}, headers=auth_headers)
    did = r.get_json()["id"]
    cl = client.get(f"{base}/{PROJ}/{did}/checklist", headers=auth_headers).get_json()
    assert cl["items"] and cl["fortschritt"]["erfuellt"] == 0
    first_id = cl["items"][0]["id"]
    # abhaken
    put = client.put(f"{base}/{PROJ}/{did}/checklist",
                     json={"items": {first_id: {"erfuellt": True}}}, headers=auth_headers)
    assert put.status_code == 200
    cl2 = client.get(f"{base}/{PROJ}/{did}/checklist", headers=auth_headers).get_json()
    assert cl2["fortschritt"]["erfuellt"] == 1
    item = next(i for i in cl2["items"] if i["id"] == first_id)
    assert item["erfuellt"] is True
    # Prompt
    pr = client.get(f"{base}/{PROJ}/{did}/checklist/prompt", headers=auth_headers)
    assert pr.status_code == 200 and "PFLICHTINHALTE" in pr.get_json()["prompt"]
    client.delete(f"{base}/{PROJ}/{did}", headers=auth_headers)


def test_api_checklist_empty_for_doc_without_spec(client, auth_headers):
    base = "/api/cra-dokumente"
    r = client.post(f"{base}/{PROJ}",
                    json={"doc_type": "konformitaetserklaerung"}, headers=auth_headers)
    did = r.get_json()["id"]
    cl = client.get(f"{base}/{PROJ}/{did}/checklist", headers=auth_headers).get_json()
    assert cl["items"] == []  # kein Panel
    pr = client.get(f"{base}/{PROJ}/{did}/checklist/prompt", headers=auth_headers)
    assert pr.status_code == 404  # keine Checkliste → kein Prompt
    client.delete(f"{base}/{PROJ}/{did}", headers=auth_headers)
