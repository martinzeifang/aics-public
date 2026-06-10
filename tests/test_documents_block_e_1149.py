"""Sprint #24 (#1149) Block E — Report/Template-Kontext (S14) + Migration (S15).

Hermetisch: jeder Test nutzt eine eigene Temp-SQLite-DB. Es wird nichts an der
echten ``data/db/*``-DB verändert.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Frischer DB-Pfad im tmp-Verzeichnis (für reine sqlite-/Doc-Operationen)."""
    return tmp_path / "block_e.sqlite"


@pytest.fixture
def repo_db():
    """Frischer DB-Pfad **innerhalb** des Repos.

    Die Modul-``ensure_db``-Funktionen erzwingen über ``security_utils`` einen
    Pfad innerhalb des Workspace-Roots; tmp_path scheitert daran. Daher liegt die
    Test-DB unter ``data/db/`` und wird vor/nach dem Test aufgeräumt.
    """
    repo_root = Path(__file__).resolve().parent.parent
    db = repo_root / "data" / "db" / "pytest_block_e_1149.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)

    def _clean():
        for e in ("", "-wal", "-shm"):
            p = Path(str(db) + e)
            if p.exists():
                p.unlink()

    _clean()
    yield db
    _clean()


# ── S14: dokumente-Kontext je Modul ─────────────────────────────────────────────

# (modul-key, build-funktion-import, variablen-liste-import, db-modul-für-docs)
_MODULES = [
    ("ai_act", "ai_act.template_context", "build_aiact_context", "AIACT_VARIABLES", "ai_act"),
    ("cra", "cra.template_context", "build_cra_context", "CRA_VARIABLES", "cra"),
    ("nis2", "nis2.template_context", "build_nis2_context", "NIS2_VARIABLES", "nis2"),
    ("dsgvo", "dsgvo.template_context", "build_dsgvo_context", "DSGVO_VARIABLES", "dsgvo"),
    ("wiba", "wiba.template_context", "build_wiba_context", "WIBA_VARIABLES", "wiba"),
]


def _load(modname, build_name, vars_name):
    import importlib
    mod = importlib.import_module(modname)
    return getattr(mod, build_name), getattr(mod, vars_name)


def _ensure_module_db(db_modul, db_path):
    """Modul-Schema anlegen, falls vorhanden (CRA ruft kein ensure_db im Builder)."""
    import importlib
    pkg = "ai_act" if db_modul == "ai_act" else db_modul
    try:
        mdb = importlib.import_module(f"{pkg}.db")
        if hasattr(mdb, "ensure_db"):
            mdb.ensure_db(db_path)
    except Exception:
        pass


@pytest.mark.parametrize("modul,modname,build_name,vars_name,db_modul", _MODULES)
def test_variables_contain_dokumente(modul, modname, build_name, vars_name, db_modul):
    _, variables = _load(modname, build_name, vars_name)
    keys = {v.get("key") for v in variables}
    assert "dokumente" in keys, f"{modul}: dokumente fehlt in {vars_name}"


@pytest.mark.parametrize("modul,modname,build_name,vars_name,db_modul", _MODULES)
def test_context_has_dokumente_list_empty(modul, modname, build_name, vars_name, db_modul, repo_db):
    _ensure_module_db(db_modul, repo_db)
    build, _ = _load(modname, build_name, vars_name)
    ctx = build(repo_db, "NichtExistierendesProjekt")
    assert "dokumente" in ctx
    assert isinstance(ctx["dokumente"], list)
    assert ctx["dokumente"] == []


@pytest.mark.parametrize("modul,modname,build_name,vars_name,db_modul", _MODULES)
def test_context_dokumente_only_finalized(modul, modname, build_name, vars_name, db_modul, repo_db):
    from shared.documents import db as ddb
    _ensure_module_db(db_modul, repo_db)
    projekt = "P-Block-E"
    # entwurf → darf NICHT erscheinen
    ddb.create_document(repo_db, db_modul, projekt=projekt, doc_type="x_entwurf",
                        titel="Entwurf-Doc", content_html="<p>e</p>")
    # final → erscheint
    fid = ddb.create_document(repo_db, db_modul, projekt=projekt, doc_type="x_final",
                              titel="Final-Doc", content_html="<p>f</p>")
    ddb.set_status(repo_db, db_modul, fid, "final")
    # freigegeben → erscheint
    gid = ddb.create_document(repo_db, db_modul, projekt=projekt, doc_type="x_frei",
                              titel="Freigegeben-Doc", content_html="<p>g</p>")
    ddb.set_status(repo_db, db_modul, gid, "freigegeben")

    build, _ = _load(modname, build_name, vars_name)
    ctx = build(repo_db, projekt)
    titels = {d["titel"] for d in ctx["dokumente"]}
    assert "Final-Doc" in titels
    assert "Freigegeben-Doc" in titels
    assert "Entwurf-Doc" not in titels
    # Form prüfen
    for d in ctx["dokumente"]:
        assert set(d) >= {"titel", "doc_type", "rechtsgrundlage", "status", "version", "stand"}


def test_context_dokumente_uses_catalog_rechtsgrundlage(repo_db):
    from shared.documents import db as ddb
    from ai_act.template_context import build_aiact_context
    projekt = "P-Kat"
    did = ddb.create_document(repo_db, "ai_act", projekt=projekt,
                              doc_type="konformitaetserklaerung",
                              titel="KE", content_html="<p>x</p>")
    ddb.set_status(repo_db, "ai_act", did, "final")
    ctx = build_aiact_context(repo_db, projekt)
    doc = next(d for d in ctx["dokumente"] if d["doc_type"] == "konformitaetserklaerung")
    assert "Art. 47" in doc["rechtsgrundlage"]


# ── S15: Migration AI-Act ────────────────────────────────────────────────────────

def _seed_aiact_system_doku(db_path: Path, projekt: str, notizen: str):
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS aiact_system_doku (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_name TEXT, notizen TEXT)"""
        )
        con.execute("INSERT INTO aiact_system_doku (projekt_name, notizen) VALUES (?,?)",
                    (projekt, notizen))
        con.commit()
    finally:
        con.close()


def test_migrate_aiact_a8_marker(tmp_db):
    from shared.documents import migrate
    from shared.documents import db as ddb
    projekt = "MigA8"
    notizen = ("Allgemeine Notiz.\n\n"
               "--- EU-Konformitätserklärung ---\n"
               "Hiermit erklären wir die Konformität.\n")
    _seed_aiact_system_doku(tmp_db, projekt, notizen)

    res = migrate.migrate_aiact(tmp_db)
    assert res["migrated"] >= 1

    docs = ddb.list_documents(tmp_db, "ai_act", projekt)
    imported = [d for d in docs if d["source"] == "import"]
    assert imported, "kein Import-Dokument angelegt"
    assert any(d["doc_type"] == "konformitaetserklaerung" for d in imported)

    # idempotent: zweiter Lauf legt nichts Neues an
    res2 = migrate.migrate_aiact(tmp_db)
    assert res2["migrated"] == 0
    assert res2["skipped"] >= 1
    assert len([d for d in ddb.list_documents(tmp_db, "ai_act", projekt)
                if d["source"] == "import"]) == len(imported)


def test_migrate_aiact_raw_fallback(tmp_db):
    from shared.documents import migrate
    from shared.documents import db as ddb
    projekt = "MigRaw"
    _seed_aiact_system_doku(tmp_db, projekt, "Reiner Freitext ohne Marker.")
    res = migrate.migrate_aiact(tmp_db)
    assert res["migrated"] == 1
    imported = [d for d in ddb.list_documents(tmp_db, "ai_act", projekt)
                if d["source"] == "import"]
    assert len(imported) == 1
    assert "<pre>" in imported[0]["content_html"]


def test_migrate_aiact_missing_table(tmp_db):
    from shared.documents import migrate
    # keine aiact_system_doku-Tabelle → robust
    assert migrate.migrate_aiact(tmp_db) == {"migrated": 0, "skipped": 0}


# ── S15: Migration NIS2 ──────────────────────────────────────────────────────────

def _seed_nis2_incident(db_path: Path, projekt: str, plan: str):
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS nis2_incident_response (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_name TEXT, kommunikationsplan TEXT)"""
        )
        con.execute(
            "INSERT INTO nis2_incident_response (projekt_name, kommunikationsplan) VALUES (?,?)",
            (projekt, plan))
        con.commit()
    finally:
        con.close()


def test_migrate_nis2_kommunikationsplan(tmp_db):
    from shared.documents import migrate
    from shared.documents import db as ddb
    projekt = "MigNis2"
    _seed_nis2_incident(tmp_db, projekt, "24h-Meldung an CSIRT, dann 72h-Update.")
    res = migrate.migrate_nis2(tmp_db)
    assert res["migrated"] == 1
    imported = [d for d in ddb.list_documents(tmp_db, "nis2", projekt)
                if d["source"] == "import"]
    assert imported and imported[0]["doc_type"] == "incident_meldung"
    # idempotent
    res2 = migrate.migrate_nis2(tmp_db)
    assert res2["migrated"] == 0 and res2["skipped"] >= 1


def test_migrate_nis2_missing_table(tmp_db):
    from shared.documents import migrate
    assert migrate.migrate_nis2(tmp_db) == {"migrated": 0, "skipped": 0}


def test_migrate_nis2_empty_plan_skipped(tmp_db):
    from shared.documents import migrate
    from shared.documents import db as ddb
    projekt = "MigEmpty"
    _seed_nis2_incident(tmp_db, projekt, "   ")
    res = migrate.migrate_nis2(tmp_db)
    assert res == {"migrated": 0, "skipped": 0}
    assert ddb.list_documents(tmp_db, "nis2", projekt) == []
