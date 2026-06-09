"""S1 (#1150) — Generische Dokument-Persistenz je Modul-DB.

Analog zum ``shared/firmen_link``-Muster: jedes Modul nutzt seine eigene SQLite-
Datei; die Tabelle ``<modul>_dokumente`` wird idempotent angelegt. Keine
Cross-DB-FKs — ``firmen_id`` ist eine logische Referenz.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

MODULES = ("ai_act", "cra", "nis2", "dsgvo", "wiba")
STATUS = ("entwurf", "final", "freigegeben")
SOURCES = ("manuell", "assistent", "import")


def table_name(modul: str) -> str:
    # NICHT '<modul>_dokumente' — kollidiert mit Legacy-Tabellen (ai_act/cra/nis2/
    # dsgvo haben bereits eine alte '<modul>_dokumente'). Eigener Name (#1149).
    if modul not in MODULES:
        raise ValueError(f"Unbekanntes Modul: {modul}")
    return f"{modul}_managed_docs"


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def _schema(table: str) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {table} (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        projekt       TEXT NOT NULL,
        firmen_id     INTEGER,
        doc_type      TEXT NOT NULL DEFAULT '',
        titel         TEXT NOT NULL DEFAULT '',
        status        TEXT NOT NULL DEFAULT 'entwurf',
        content_html  TEXT NOT NULL DEFAULT '',
        content_format TEXT NOT NULL DEFAULT 'html',
        version       INTEGER NOT NULL DEFAULT 1,
        source        TEXT NOT NULL DEFAULT 'manuell',
        assistant_key TEXT,
        sha256        TEXT,
        meta_json     TEXT NOT NULL DEFAULT '{{}}',
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        created_by    TEXT NOT NULL DEFAULT '',
        updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
        updated_by    TEXT NOT NULL DEFAULT '',
        deleted_at    TEXT,
        deleted_by    TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_{table}_projekt ON {table}(projekt);
    CREATE INDEX IF NOT EXISTS idx_{table}_doctype ON {table}(projekt, doc_type);
    """


def ensure_documents_table(db_path: Path, modul: str) -> None:
    """Idempotent: Tabelle ``<modul>_dokumente`` + Indizes + firmen_id-Spalte."""
    table = table_name(modul)
    con = _connect(Path(db_path))
    try:
        con.executescript(_schema(table))
        con.commit()
    finally:
        con.close()


def _row_to_dict(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if not r:
        return None
    d = dict(r)
    try:
        d["meta"] = json.loads(d.get("meta_json") or "{}")
    except Exception:  # noqa: BLE001
        d["meta"] = {}
    return d


# ── CRUD ──────────────────────────────────────────────────────────────────────

def create_document(db_path: Path, modul: str, *, projekt: str, doc_type: str = "",
                    titel: str = "", content_html: str = "", source: str = "manuell",
                    assistant_key: str | None = None, firmen_id: int | None = None,
                    meta: dict | None = None, created_by: str = "") -> int:
    ensure_documents_table(db_path, modul)
    table = table_name(modul)
    if source not in SOURCES:
        source = "manuell"
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            f"""INSERT INTO {table}
                (projekt, firmen_id, doc_type, titel, content_html, source,
                 assistant_key, meta_json, created_by, updated_by)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (projekt, firmen_id, doc_type, titel, content_html, source,
             assistant_key, json.dumps(meta or {}, ensure_ascii=False),
             created_by, created_by))
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def get_document(db_path: Path, modul: str, doc_id: int) -> dict[str, Any] | None:
    ensure_documents_table(db_path, modul)
    table = table_name(modul)
    con = _connect(Path(db_path))
    try:
        return _row_to_dict(con.execute(
            f"SELECT * FROM {table} WHERE id=? AND deleted_at IS NULL",
            (int(doc_id),)).fetchone())
    finally:
        con.close()


def list_documents(db_path: Path, modul: str, projekt: str,
                   *, include_deleted: bool = False) -> list[dict[str, Any]]:
    ensure_documents_table(db_path, modul)
    table = table_name(modul)
    con = _connect(Path(db_path))
    try:
        sql = f"SELECT * FROM {table} WHERE projekt=?"
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        sql += " ORDER BY doc_type, updated_at DESC"
        return [_row_to_dict(r) for r in con.execute(sql, (projekt,)).fetchall()]
    finally:
        con.close()


def update_document(db_path: Path, modul: str, doc_id: int, *,
                    titel: str | None = None, content_html: str | None = None,
                    meta: dict | None = None, updated_by: str = "") -> dict[str, Any] | None:
    """Inhaltliche Änderung → version+1. sha256 wird neu gesetzt, falls freigegeben."""
    ensure_documents_table(db_path, modul)
    table = table_name(modul)
    cur = get_document(db_path, modul, doc_id)
    if not cur:
        return None
    new_titel = cur["titel"] if titel is None else titel
    new_html = cur["content_html"] if content_html is None else content_html
    content_changed = (content_html is not None and content_html != cur["content_html"])
    new_meta = cur.get("meta") if meta is None else meta
    new_version = cur["version"] + 1 if content_changed else cur["version"]
    new_sha = cur.get("sha256")
    if content_changed and cur["status"] == "freigegeben":
        new_sha = hashlib.sha256(new_html.encode("utf-8")).hexdigest()
    con = _connect(Path(db_path))
    try:
        con.execute(
            f"""UPDATE {table} SET titel=?, content_html=?, meta_json=?, version=?,
                sha256=?, updated_at=datetime('now'), updated_by=? WHERE id=?""",
            (new_titel, new_html, json.dumps(new_meta or {}, ensure_ascii=False),
             new_version, new_sha, updated_by, int(doc_id)))
        con.commit()
    finally:
        con.close()
    return get_document(db_path, modul, doc_id)


def set_status(db_path: Path, modul: str, doc_id: int, status: str,
               *, updated_by: str = "") -> dict[str, Any] | None:
    if status not in STATUS:
        raise ValueError(f"Ungültiger Status: {status}")
    ensure_documents_table(db_path, modul)
    table = table_name(modul)
    cur = get_document(db_path, modul, doc_id)
    if not cur:
        return None
    sha = cur.get("sha256")
    if status == "freigegeben":
        sha = hashlib.sha256((cur["content_html"] or "").encode("utf-8")).hexdigest()
    con = _connect(Path(db_path))
    try:
        con.execute(
            f"UPDATE {table} SET status=?, sha256=?, updated_at=datetime('now'), "
            f"updated_by=? WHERE id=?", (status, sha, updated_by, int(doc_id)))
        con.commit()
    finally:
        con.close()
    return get_document(db_path, modul, doc_id)


def soft_delete_document(db_path: Path, modul: str, doc_id: int, *, deleted_by: str = "") -> bool:
    ensure_documents_table(db_path, modul)
    table = table_name(modul)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            f"UPDATE {table} SET deleted_at=datetime('now'), deleted_by=? "
            f"WHERE id=? AND deleted_at IS NULL", (deleted_by, int(doc_id)))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()
