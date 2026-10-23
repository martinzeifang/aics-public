"""S1 (#1150) — Generische Dokument-Persistenz je Modul-DB.

Analog zum ``shared/firmen_link``-Muster: jedes Modul nutzt seine eigene SQLite-
Datei; die Tabelle ``<modul>_dokumente`` wird idempotent angelegt. Keine
Cross-DB-FKs — ``firmen_id`` ist eine logische Referenz.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from shared import db as _sdb

MODULES = ("ai_act", "cra", "nis2", "dsgvo", "wiba")
STATUS = ("entwurf", "final", "freigegeben")
SOURCES = ("manuell", "assistent", "import")
DOC_MODES = ("inapp", "extern")  # #1233: In-App-Editor vs. externe Web-Doku

# #1235: Frontend sendet teils das engl. 'assistant' — auf den DB-Kanon mappen,
# damit die Assistenten-Provenienz nicht still zu 'manuell' degradiert.
_SOURCE_ALIASES = {"assistant": "assistent"}


def normalize_source(source: str | None) -> str:
    s = _SOURCE_ALIASES.get((source or "").strip(), (source or "").strip())
    return s if s in SOURCES else "manuell"


def table_name(modul: str) -> str:
    # NICHT '<modul>_dokumente' — kollidiert mit Legacy-Tabellen (ai_act/cra/nis2/
    # dsgvo haben bereits eine alte '<modul>_dokumente'). Eigener Name (#1149).
    if modul not in MODULES:
        raise ValueError(f"Unbekanntes Modul: {modul}")
    return f"{modul}_managed_docs"


def checklist_table_name(modul: str) -> str:
    """#1234: Abhak-Status der Konformitäts-Checkliste (eigene Tabelle).

    Entscheidung (im Issue gefordert): eigene Tabelle statt meta_json — damit
    Checklisten-Häkchen die Dokument-Version NICHT erhöhen, einzeln auditierbar
    bleiben und unabhängig von In-App-/Extern-Modus persistieren.
    """
    if modul not in MODULES:
        raise ValueError(f"Unbekanntes Modul: {modul}")
    return f"{modul}_doc_checklist"


def _connect(db_path: Path) -> Any:
    return _sdb.connect(db_path)


def _schema(table: str) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {table} (
        id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
        doc_mode            TEXT NOT NULL DEFAULT 'inapp',
        external_url        TEXT,
        external_label      TEXT,
        external_checked_at TEXT,
        external_reachable  INTEGER,
        meta_json     TEXT NOT NULL DEFAULT '{{}}',
        created_at    TEXT NOT NULL DEFAULT (aics_now()),
        created_by    TEXT NOT NULL DEFAULT '',
        updated_at    TEXT NOT NULL DEFAULT (aics_now()),
        updated_by    TEXT NOT NULL DEFAULT '',
        deleted_at    TEXT,
        deleted_by    TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_{table}_projekt ON {table}(projekt);
    CREATE INDEX IF NOT EXISTS idx_{table}_doctype ON {table}(projekt, doc_type);
    """


# #1233: Web-Verknüpfung — nachzurüstende Spalten für Bestands-DBs (idempotent).
_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("doc_mode", "TEXT NOT NULL DEFAULT 'inapp'"),
    ("external_url", "TEXT"),
    ("external_label", "TEXT"),
    ("external_checked_at", "TEXT"),
    ("external_reachable", "INTEGER"),
)


def _migrate(con: Any, table: str) -> None:
    """Fügt fehlende Spalten via ALTER TABLE hinzu (idempotent, Bestands-DBs)."""
    for col, decl in _MIGRATIONS:
        con.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {decl}")


def ensure_documents_table(db_path: Path, modul: str) -> None:
    """Idempotent: Tabelle ``<modul>_managed_docs`` + Indizes + Migrationen."""
    table = table_name(modul)
    con = _connect(Path(db_path))
    try:
        con.executescript(_schema(table))
        _migrate(con, table)
        con.commit()
    finally:
        con.close()


def _row_to_dict(r: Any | None) -> dict[str, Any] | None:
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
                    meta: dict | None = None, created_by: str = "",
                    doc_mode: str = "inapp", external_url: str | None = None,
                    external_label: str | None = None) -> int:
    ensure_documents_table(db_path, modul)
    table = table_name(modul)
    source = normalize_source(source)
    if doc_mode not in DOC_MODES:
        doc_mode = "inapp"
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            f"""INSERT INTO {table}
                (projekt, firmen_id, doc_type, titel, content_html, source,
                 assistant_key, doc_mode, external_url, external_label,
                 meta_json, created_by, updated_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (projekt, firmen_id, doc_type, titel, content_html, source,
             assistant_key, doc_mode, external_url, external_label,
             json.dumps(meta or {}, ensure_ascii=False),
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
                    meta: dict | None = None, updated_by: str = "",
                    doc_mode: str | None = None, external_url: str | None = None,
                    external_label: str | None = None) -> dict[str, Any] | None:
    """Inhaltliche Änderung → version+1. sha256 wird neu gesetzt, falls freigegeben.

    #1233: ``doc_mode``/``external_url``/``external_label`` sind additiv. Ein
    Moduswechsel oder eine neue URL setzt den Erreichbarkeits-Cache zurück
    (``external_checked_at``/``external_reachable`` → NULL), da der manuelle Check
    erneut laufen muss.
    """
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

    new_mode = cur.get("doc_mode", "inapp") if doc_mode is None else doc_mode
    if new_mode not in DOC_MODES:
        new_mode = "inapp"
    new_url = cur.get("external_url") if external_url is None else external_url
    new_label = cur.get("external_label") if external_label is None else external_label
    # Erreichbarkeits-Cache invalidieren, wenn Modus oder URL sich ändern.
    checked_at = cur.get("external_checked_at")
    reachable = cur.get("external_reachable")
    if new_mode != cur.get("doc_mode", "inapp") or new_url != cur.get("external_url"):
        checked_at = None
        reachable = None

    con = _connect(Path(db_path))
    try:
        con.execute(
            f"""UPDATE {table} SET titel=?, content_html=?, meta_json=?, version=?,
                sha256=?, doc_mode=?, external_url=?, external_label=?,
                external_checked_at=?, external_reachable=?,
                updated_at=aics_now(), updated_by=? WHERE id=?""",
            (new_titel, new_html, json.dumps(new_meta or {}, ensure_ascii=False),
             new_version, new_sha, new_mode, new_url, new_label,
             checked_at, reachable, updated_by, int(doc_id)))
        con.commit()
    finally:
        con.close()
    return get_document(db_path, modul, doc_id)


def record_reachability(db_path: Path, modul: str, doc_id: int, *,
                        reachable: bool, updated_by: str = "") -> dict[str, Any] | None:
    """Speichert das Ergebnis eines manuellen Erreichbarkeits-Checks (#1233)."""
    ensure_documents_table(db_path, modul)
    table = table_name(modul)
    if not get_document(db_path, modul, doc_id):
        return None
    con = _connect(Path(db_path))
    try:
        con.execute(
            f"""UPDATE {table} SET external_checked_at=aics_now(),
                external_reachable=?, updated_by=? WHERE id=?""",
            (1 if reachable else 0, updated_by, int(doc_id)))
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
            f"UPDATE {table} SET status=?, sha256=?, updated_at=aics_now(), "
            f"updated_by=? WHERE id=?", (status, sha, updated_by, int(doc_id)))
        con.commit()
    finally:
        con.close()
    return get_document(db_path, modul, doc_id)


# ── Konformitäts-Checkliste (#1234) ─────────────────────────────────────────────

def _checklist_schema(table: str) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {table} (
        doc_id     INTEGER NOT NULL,
        item_id    TEXT NOT NULL,
        erfuellt   INTEGER NOT NULL DEFAULT 0,
        kommentar  TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (aics_now()),
        updated_by TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (doc_id, item_id)
    );
    """


def ensure_checklist_table(db_path: Path, modul: str) -> None:
    """Idempotent: Tabelle ``<modul>_doc_checklist`` (Ist-Status je Item)."""
    table = checklist_table_name(modul)
    con = _connect(Path(db_path))
    try:
        con.executescript(_checklist_schema(table))
        con.commit()
    finally:
        con.close()


def get_checklist_status(db_path: Path, modul: str, doc_id: int) -> dict[str, dict[str, Any]]:
    """Liefert {item_id: {erfuellt, kommentar, updated_at, updated_by}} (Ist)."""
    ensure_checklist_table(db_path, modul)
    table = checklist_table_name(modul)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            f"SELECT item_id, erfuellt, kommentar, updated_at, updated_by "
            f"FROM {table} WHERE doc_id=?", (int(doc_id),)).fetchall()
        return {r["item_id"]: {"erfuellt": bool(r["erfuellt"]),
                               "kommentar": r["kommentar"],
                               "updated_at": r["updated_at"],
                               "updated_by": r["updated_by"]} for r in rows}
    finally:
        con.close()


def set_checklist_status(db_path: Path, modul: str, doc_id: int,
                         items: dict[str, dict[str, Any]], *, updated_by: str = "") -> dict[str, dict[str, Any]]:
    """Upsert mehrerer Items. ``items`` = {item_id: {erfuellt: bool, kommentar?: str}}."""
    ensure_checklist_table(db_path, modul)
    table = checklist_table_name(modul)
    con = _connect(Path(db_path))
    try:
        for item_id, val in (items or {}).items():
            erfuellt = 1 if (val or {}).get("erfuellt") else 0
            kommentar = str((val or {}).get("kommentar") or "")
            con.execute(
                f"""INSERT INTO {table} (doc_id, item_id, erfuellt, kommentar, updated_by)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(doc_id, item_id) DO UPDATE SET
                        erfuellt=excluded.erfuellt, kommentar=excluded.kommentar,
                        updated_at=aics_now(), updated_by=excluded.updated_by""",
                (int(doc_id), str(item_id), erfuellt, kommentar, updated_by))
        con.commit()
    finally:
        con.close()
    return get_checklist_status(db_path, modul, doc_id)


def soft_delete_document(db_path: Path, modul: str, doc_id: int, *, deleted_by: str = "") -> bool:
    ensure_documents_table(db_path, modul)
    table = table_name(modul)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            f"UPDATE {table} SET deleted_at=aics_now(), deleted_by=? "
            f"WHERE id=? AND deleted_at IS NULL", (deleted_by, int(doc_id)))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()
