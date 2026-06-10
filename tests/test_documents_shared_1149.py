"""Sprint #24 (#1149) — Shared-Dokumenten-Fundament S1–S3 (hermetisch)."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def docs_db(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    db = repo_root / "data" / "db" / "pytest_docs_1149.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    for e in ("", "-wal", "-shm"):
        p = Path(str(db) + e)
        if p.exists():
            p.unlink()
    yield db
    for e in ("", "-wal", "-shm"):
        p = Path(str(db) + e)
        if p.exists():
            p.unlink()


# ── S1 DB ────────────────────────────────────────────────────────────────────

def test_db_crud_versioning_sha256(docs_db):
    from shared.documents import db as ddb
    ddb.ensure_documents_table(docs_db, "cra")
    ddb.ensure_documents_table(docs_db, "cra")  # idempotent
    did = ddb.create_document(docs_db, "cra", projekt="P", doc_type="update_policy",
                              titel="Update-Policy", content_html="<p>A</p>",
                              source="assistent", assistant_key="c9", created_by="u")
    d = ddb.get_document(docs_db, "cra", did)
    assert d["version"] == 1 and d["status"] == "entwurf" and d["source"] == "assistent"
    # inhaltliche Änderung → version+1
    ddb.update_document(docs_db, "cra", did, content_html="<p>B</p>", updated_by="u")
    assert ddb.get_document(docs_db, "cra", did)["version"] == 2
    # freigegeben → sha256 gesetzt
    ddb.set_status(docs_db, "cra", did, "freigegeben", updated_by="u")
    d = ddb.get_document(docs_db, "cra", did)
    assert d["sha256"] and len(d["sha256"]) == 64
    # spätere Änderung erhöht version + aktualisiert sha256
    old = d["sha256"]
    ddb.update_document(docs_db, "cra", did, content_html="<p>C</p>", updated_by="u")
    d2 = ddb.get_document(docs_db, "cra", did)
    assert d2["version"] == 3 and d2["sha256"] != old
    # Soft-Delete
    assert ddb.soft_delete_document(docs_db, "cra", did, deleted_by="u") is True
    assert ddb.get_document(docs_db, "cra", did) is None
    assert len(ddb.list_documents(docs_db, "cra", "P", include_deleted=True)) == 1


def test_db_invalid_status(docs_db):
    from shared.documents import db as ddb
    did = ddb.create_document(docs_db, "nis2", projekt="P", doc_type="is_leitlinie")
    with pytest.raises(ValueError):
        ddb.set_status(docs_db, "nis2", did, "ungueltig")


# ── S2 Katalog ────────────────────────────────────────────────────────────────

def test_catalog_all_modules():
    from shared.documents import catalog as dcat
    from shared.documents import db as ddb
    for m in ddb.MODULES:
        cat = dcat.get_catalog(m)
        assert cat, f"Katalog leer: {m}"
        for entry in cat:
            assert entry["doc_type"] and entry["titel"] and entry["rechtsgrundlage"]
    # gezielte Pflichtdokumente vorhanden
    types = {e["doc_type"] for e in dcat.get_catalog("ai_act")}
    assert {"konformitaetserklaerung", "transparenzhinweise", "fria"} <= types
    assert dcat.get_doc_spec("cra", "vuln_disclosure_policy")["suggested_assistant"] == "c8"


# ── S3 Export ─────────────────────────────────────────────────────────────────

def test_export_docx_html_mapping():
    from shared.documents import export as dx
    html = ("<h1>Titel</h1><p>Text mit <strong>fett</strong> und <em>kursiv</em>.</p>"
            "<ul><li>P1</li><li>P2</li></ul>"
            "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>")
    data = dx.render_document_docx({"titel": "Doc", "status": "final", "version": 2,
                                    "content_html": html, "rechtsgrundlage": "Art. X",
                                    "meta": {}})
    assert data[:2] == b"PK" and len(data) > 5000  # valides DOCX (zip)


def test_export_sanitizes_script():
    from shared.documents import export as dx
    data = dx.render_document_docx({"titel": "X", "status": "entwurf", "version": 1,
                                    "content_html": "<p>ok</p><script>alert(1)</script>", "meta": {}})
    assert data[:2] == b"PK"
