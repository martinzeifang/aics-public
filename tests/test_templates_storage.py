"""#989 — Template-Storage: Upload, Versionierung, Default, Soft-Delete.

DB-Security erlaubt nur Pfade unterhalb des Repo-Roots → Test-Artefakte unter
data/db/ + data/templates/ mit Cleanup.
"""
import uuid
from pathlib import Path

import pytest
from docx import Document

from shared.templates import storage, db as tdb

_REPO = Path(__file__).resolve().parent.parent


def _make_docx(path: Path, text: str = "{{ projekt.name }}"):
    d = Document(); d.add_paragraph(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(path))


@pytest.fixture
def env(tmp_path):
    tag = uuid.uuid4().hex[:8]
    db = _REPO / "data" / "db" / f"_test_templates_{tag}.sqlite"
    root = _REPO / "data" / "templates" / f"_test_{tag}"
    db.parent.mkdir(parents=True, exist_ok=True)
    tdb.ensure_db(db)
    src = tmp_path / "vorlage.docx"
    _make_docx(src)
    yield db, root, src
    for p in (db, Path(str(db) + "-wal"), Path(str(db) + "-shm")):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    import shutil
    shutil.rmtree(root, ignore_errors=True)


def test_upload_creates_row_and_file(env):
    db, root, src = env
    rec = storage.upload_template(src, modul="cra", name="Standard", db_path=db, storage_root=root)
    assert rec["id"] > 0
    assert rec["modul"] == "cra" and rec["version"] == 1
    assert Path(rec["datei_pfad"]).exists()
    assert len(rec["datei_sha256"]) == 64
    # Variablen extrahiert
    import json
    assert "projekt" in json.loads(rec["variablen_json"])


def test_reupload_bumps_version(env):
    db, root, src = env
    r1 = storage.upload_template(src, modul="cra", name="Standard", db_path=db, storage_root=root)
    r2 = storage.upload_template(src, modul="cra", name="Standard", db_path=db, storage_root=root)
    assert r2["version"] == 2 and r1["version"] == 1
    # beide existieren
    assert len(storage.list_templates(db, "cra")) == 2


def test_set_default_is_atomic(env):
    db, root, src = env
    r1 = storage.upload_template(src, modul="cra", name="A", db_path=db, storage_root=root)
    r2 = storage.upload_template(src, modul="cra", name="B", db_path=db, storage_root=root)
    storage.set_default(db, r1["id"])
    storage.set_default(db, r2["id"])
    recs = {r["id"]: r for r in storage.list_templates(db, "cra")}
    assert recs[r2["id"]]["ist_default"] == 1
    assert recs[r1["id"]]["ist_default"] == 0


def test_soft_delete_removes_file_keeps_row(env):
    db, root, src = env
    rec = storage.upload_template(src, modul="nis2", name="X", db_path=db, storage_root=root)
    path = Path(rec["datei_pfad"])
    storage.soft_delete(db, rec["id"], by="admin", reason="veraltet")
    assert not path.exists()
    # Zeile bleibt, aber inaktiv
    full = tdb.get_template(db, rec["id"])
    assert full["aktiv"] == 0 and full["deletion_reason"] == "veraltet"
    # nicht mehr in aktiver Liste
    assert all(r["id"] != rec["id"] for r in storage.list_templates(db, "nis2"))
