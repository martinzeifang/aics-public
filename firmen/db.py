"""Zentrale Firmen/Projekt-Verwaltung – SQLite-Datenzugriff."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from security_utils import safe_generated_file, workspace_root_from
from shared.sql import quote_ident
from shared.db_security import connect_sqlite
from shared.db_security import connect_sqlite

DEFAULT_DB_PATH = Path("data/db/firmen.sqlite")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-32000;

CREATE TABLE IF NOT EXISTS firmen (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    unternehmen     TEXT NOT NULL DEFAULT '',
    beschreibung    TEXT NOT NULL DEFAULT '',
    berater         TEXT NOT NULL DEFAULT '',
    frameworks_json TEXT NOT NULL DEFAULT '[]',
    pruefungsfokus  TEXT NOT NULL DEFAULT '',
    rb_framework    TEXT NOT NULL DEFAULT 'STRIDE',
    produkt         TEXT NOT NULL DEFAULT '',
    produktklasse   TEXT NOT NULL DEFAULT 'default',
    module_risikobewertung INTEGER NOT NULL DEFAULT 1,
    module_gutachten       INTEGER NOT NULL DEFAULT 1,
    module_cra             INTEGER NOT NULL DEFAULT 1,
    module_dsgvo           INTEGER NOT NULL DEFAULT 1,
    module_nis2            INTEGER NOT NULL DEFAULT 1,
    module_ai_act          INTEGER NOT NULL DEFAULT 1,
    is_deleted      INTEGER NOT NULL DEFAULT 0,
    deleted_at      TEXT,
    meta_json       TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS produkte (
    id            INTEGER PRIMARY KEY,
    firmen_id     INTEGER NOT NULL REFERENCES firmen(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    beschreibung  TEXT NOT NULL DEFAULT '',
    produktklasse TEXT NOT NULL DEFAULT 'default',
    is_default    INTEGER NOT NULL DEFAULT 0,
    is_deleted    INTEGER NOT NULL DEFAULT 0,
    deleted_at    TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(firmen_id, name)
);
"""

_ALLOWED_FIELDS = frozenset({
    "unternehmen", "beschreibung", "berater",
    "frameworks_json", "pruefungsfokus",
    "rb_framework", "produkt", "produktklasse",
    "module_risikobewertung", "module_gutachten", "module_cra",
    "module_dsgvo", "module_nis2", "module_ai_act",
    "meta_json",
})


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path = safe_generated_file(db_path, workspace_root_from(Path(__file__)))
    con = connect_sqlite(db_path, anchor=Path(__file__))

    con.row_factory = sqlite3.Row
    con.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")
    return con


def _migrate_legacy_db_file(db_path: Path) -> None:
    """#1003: Falls noch die alte ``kunden.sqlite`` existiert und die neue
    ``firmen.sqlite`` fehlt, alte Dateien (inkl. WAL/SHM) umbenennen."""
    db_path = Path(db_path)
    legacy = db_path.with_name("kunden.sqlite")
    if db_path.exists() or not legacy.exists():
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        src = legacy.with_name(legacy.name + suffix)
        if src.exists():
            try:
                src.rename(db_path.with_name(db_path.name + suffix))
            except OSError:
                pass


def _migrate_legacy_tables(con: sqlite3.Connection) -> None:
    """#1003: Tabelle ``kunden`` → ``firmen`` und Spalte ``produkte.kunden_id``
    → ``firmen_id`` umbenennen (idempotent, SQLite ≥ 3.25)."""
    def _has_table(name: str) -> bool:
        return con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    def _has_column(table: str, col: str) -> bool:
        if not _has_table(table):
            return False
        return any(r[1] == col for r in con.execute(f"PRAGMA table_info({quote_ident(table)})"))

    if _has_table("kunden") and not _has_table("firmen"):
        con.execute("ALTER TABLE kunden RENAME TO firmen")
        con.commit()
    if _has_column("produkte", "kunden_id") and not _has_column("produkte", "firmen_id"):
        con.execute("ALTER TABLE produkte RENAME COLUMN kunden_id TO firmen_id")
        con.commit()


def ensure_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    _migrate_legacy_db_file(db_path)
    con = _connect(db_path)
    try:
        _migrate_legacy_tables(con)
        con.executescript(SCHEMA)
        # Migrate: add columns that may not exist in older DBs
        for col, default in [("module_dsgvo", 1), ("module_nis2", 1), ("module_ai_act", 1)]:
            try:
                # Identifiers cannot be parameter-bound; keep strictly quoted.
                con.execute(
                    f"ALTER TABLE firmen ADD COLUMN {quote_ident(col)} INTEGER NOT NULL DEFAULT {int(default)}"
                )
                con.commit()
            except Exception:
                pass
        for stmt in [
            "ALTER TABLE firmen ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE firmen ADD COLUMN deleted_at TEXT",
        ]:
            try:
                con.execute(stmt)
                con.commit()
            except Exception:
                pass
        con.commit()
        # Migrate: für jeden Firmen mit gesetztem produkt-Feld ein Default-Produkt anlegen
        _migrate_default_produkte(con)
        con.commit()
    finally:
        con.close()


def _migrate_default_produkte(con: sqlite3.Connection) -> None:
    """Legt für jeden Firmen, der noch kein Produkt hat, ein Default-Produkt an."""
    rows = con.execute(
        "SELECT id, name, produkt, produktklasse FROM firmen WHERE is_deleted = 0"
    ).fetchall()
    for row in rows:
        firmen_id = row["id"]
        existing = con.execute(
            "SELECT id FROM produkte WHERE firmen_id = ?", (firmen_id,)
        ).fetchone()
        if existing:
            continue
        # Default-Name = Firmenname für Backwards-Compatibility
        # (CRA/RB-Daten sind unter dem Firmennamen gespeichert)
        prod_name = row["name"]
        prod_klasse = row["produktklasse"] or "default"
        try:
            con.execute(
                "INSERT OR IGNORE INTO produkte (firmen_id, name, produktklasse, is_default) "
                "VALUES (?, ?, ?, 1)",
                (firmen_id, prod_name, prod_klasse),
            )
        except Exception:
            pass


def list_produkte_for_module(db_path: Path, module: str) -> list[dict[str, Any]]:
    """Gibt alle aktiven Produkte zurück, deren Firma das Modul aktiviert hat.

    Rückgabe: Liste von Dicts mit Feldern:
      - produkt_name: str   (Projekt-Schlüssel, rückwärtskompatibel)
      - firmen_name:  str
      - display:      str   ("Firmen / Produkt" wenn Firma >1 Produkt, sonst nur Firmenname)
      - is_default:   int
      - produkt_id:   int
    """
    col = f"module_{module}"
    if col not in (
        "module_risikobewertung",
        "module_gutachten",
        "module_cra",
        "module_dsgvo",
        "module_nis2",
        "module_ai_act",
    ):
        return []
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT k.name AS firmen_name, p.name AS produkt_name, "
            "p.id AS produkt_id, p.is_default, "
            "COUNT(p2.id) AS prod_count "
            "FROM firmen k "
            "JOIN produkte p ON p.firmen_id = k.id AND p.is_deleted = 0 "
            "JOIN produkte p2 ON p2.firmen_id = k.id AND p2.is_deleted = 0 "
            f"WHERE k.{quote_ident(col)} = 1 AND k.is_deleted = 0 "
            "GROUP BY p.id "
            "ORDER BY k.updated_at DESC, k.name COLLATE NOCASE, "
            "p.is_default DESC, p.name COLLATE NOCASE",
        ).fetchall()
        result = []
        for r in rows:
            prod_count = r["prod_count"]
            firmen_name = r["firmen_name"]
            produkt_name = r["produkt_name"]
            if prod_count > 1 or produkt_name != firmen_name:
                display = f"{firmen_name} / {produkt_name}"
            else:
                display = firmen_name
            result.append({
                "produkt_name": produkt_name,
                "firmen_name":  firmen_name,
                "display":      display,
                "is_default":   r["is_default"],
                "produkt_id":   r["produkt_id"],
            })
        return result
    finally:
        con.close()


def list_firmen(db_path: Path = DEFAULT_DB_PATH) -> list[str]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT name FROM firmen WHERE is_deleted = 0 ORDER BY updated_at DESC, name COLLATE NOCASE"
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        con.close()


def list_deleted_firmen(db_path: Path = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    """Gibt alle als gelöscht markierten Firmen zurück."""
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT name, unternehmen, deleted_at FROM firmen WHERE is_deleted = 1 ORDER BY deleted_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def list_firmen_for_module(db_path: Path, module: str) -> list[str]:
    """Projektliste für ein Modul (nur aktive Firmen)."""
    col = f"module_{module}"
    if col not in (
        "module_risikobewertung",
        "module_gutachten",
        "module_cra",
        "module_dsgvo",
        "module_nis2",
        "module_ai_act",
    ):
        return []
    con = _connect(db_path)
    try:
        rows = con.execute(
            f"SELECT name FROM firmen WHERE {quote_ident(col)} = 1 AND is_deleted = 0 ORDER BY updated_at DESC, name COLLATE NOCASE"
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        con.close()


def load_firma(db_path: Path, name: str) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM firmen WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["frameworks"] = json.loads(d.get("frameworks_json") or "[]")
        except Exception:
            d["frameworks"] = []
        try:
            d["meta"] = json.loads(d.get("meta_json") or "{}")
        except Exception:
            d["meta"] = {}
        return d
    finally:
        con.close()


def save_firma(db_path: Path, name: str, **fields: Any) -> None:
    """Firmen-Datensatz anlegen oder aktualisieren (upsert)."""
    if "frameworks" in fields and "frameworks_json" not in fields:
        fields["frameworks_json"] = json.dumps(fields.pop("frameworks"), ensure_ascii=False)
    elif "frameworks" in fields:
        del fields["frameworks"]
    if "meta" in fields and "meta_json" not in fields:
        fields["meta_json"] = json.dumps(fields.pop("meta"), ensure_ascii=False)
    elif "meta" in fields:
        del fields["meta"]

    safe = {k: v for k, v in fields.items() if k in _ALLOWED_FIELDS}

    con = _connect(db_path)
    try:
        existing = con.execute("SELECT id FROM firmen WHERE name = ?", (name,)).fetchone()
        if existing:
            if safe:
                sets = ", ".join(f"{k} = ?" for k in safe)
                vals = list(safe.values()) + [name]
                con.execute(
                    f"UPDATE firmen SET {sets}, updated_at = datetime('now') WHERE name = ?",
                    vals,
                )
        else:
            cols = ["name"] + list(safe.keys())
            placeholders = ", ".join("?" for _ in cols)
            vals = [name] + list(safe.values())
            con.execute(
                f"INSERT INTO firmen ({', '.join(cols)}) VALUES ({placeholders})",
                vals,
            )
            # Neuer Firma: sofort ein Default-Produkt anlegen
            pk = safe.get("produktklasse", "default")
            firmen_id = con.execute("SELECT id FROM firmen WHERE name = ?", (name,)).fetchone()["id"]
            con.execute(
                "INSERT OR IGNORE INTO produkte (firmen_id, name, produktklasse, is_default) "
                "VALUES (?, ?, ?, 1)",
                (firmen_id, name, pk),
            )
        con.commit()
    finally:
        con.close()


def delete_firma(db_path: Path, name: str) -> None:
    """Firmen-Datensatz als gelöscht markieren (Soft-Delete)."""
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE firmen SET is_deleted = 1, deleted_at = datetime('now'), updated_at = datetime('now') WHERE name = ?",
            (name,),
        )
        con.commit()
    finally:
        con.close()


def restore_firma(db_path: Path, name: str) -> None:
    """Soft-gelöschten Firmen reaktivieren."""
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE firmen SET is_deleted = 0, deleted_at = NULL, updated_at = datetime('now') WHERE name = ?",
            (name,),
        )
        con.commit()
    finally:
        con.close()


def hard_delete_firma(db_path: Path, name: str) -> None:
    """Firmen-Datensatz unwiderruflich löschen."""
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM firmen WHERE name = ?", (name,))
        con.commit()
    finally:
        con.close()


def disable_module(db_path: Path, name: str, module: str) -> None:
    """Modul-Flag für einen Firmen deaktivieren."""
    col = f"module_{module}"
    if col not in (
        "module_risikobewertung",
        "module_gutachten",
        "module_cra",
        "module_dsgvo",
        "module_nis2",
        "module_ai_act",
    ):
        return
    con = _connect(db_path)
    try:
        con.execute(
            f"UPDATE firmen SET {col} = 0, updated_at = datetime('now') WHERE name = ?",
            (name,),
        )
        con.commit()
    finally:
        con.close()


def migrate_from_module_dbs(
    firmen_db_path: Path,
    rb_db_path: Path | None = None,
    gutachten_db_path: Path | None = None,
    cra_db_path: Path | None = None,
) -> int:
    """Bestehende Projekte aus Modul-DBs in die zentrale Firmen-DB importieren.

    Gibt die Anzahl neu importierter Datensätze zurück.
    """
    ensure_db(firmen_db_path)
    existing = set(list_firmen(firmen_db_path))
    all_projects: dict[str, dict[str, Any]] = {}

    if rb_db_path and rb_db_path.exists():
        try:
            con = connect_sqlite(rb_db_path, read_only=True, harden_fs=False)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT name, framework, beschreibung FROM rb_projekte"
            ).fetchall()
            con.close()
            for r in rows:
                n = r["name"]
                p = all_projects.setdefault(n, {})
                p["rb_framework"] = r["framework"] or "STRIDE"
                if not p.get("beschreibung"):
                    p["beschreibung"] = r["beschreibung"] or ""
                p["module_risikobewertung"] = 1
        except Exception:
            pass

    if gutachten_db_path and gutachten_db_path.exists():
        try:
            con = connect_sqlite(gutachten_db_path, read_only=True, harden_fs=False)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT name, frameworks_json, pruefungsfokus FROM gutachten_projects"
            ).fetchall()
            con.close()
            for r in rows:
                n = r["name"]
                p = all_projects.setdefault(n, {})
                p["frameworks_json"] = r["frameworks_json"] or "[]"
                p["pruefungsfokus"] = r["pruefungsfokus"] or ""
                p["module_gutachten"] = 1
        except Exception:
            pass

    if cra_db_path and cra_db_path.exists():
        try:
            con = connect_sqlite(cra_db_path, read_only=True, harden_fs=False)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT name, unternehmen, produkt, produktklasse, beschreibung, berater "
                "FROM cra_projekte"
            ).fetchall()
            con.close()
            for r in rows:
                n = r["name"]
                p = all_projects.setdefault(n, {})
                p["unternehmen"] = r["unternehmen"] or ""
                p["produkt"] = r["produkt"] or ""
                p["produktklasse"] = r["produktklasse"] or "default"
                if not p.get("beschreibung"):
                    p["beschreibung"] = r["beschreibung"] or ""
                p["berater"] = r["berater"] or ""
                p["module_cra"] = 1
        except Exception:
            pass

    imported = 0
    for name, fields in all_projects.items():
        if name not in existing:
            save_firma(firmen_db_path, name, **fields)
            imported += 1

    return imported


# ── Produkte ──────────────────────────────────────────────────────────────────

def list_produkte(db_path: Path, firmen_name: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
    """Gibt alle Produkte eines Firmen zurück."""
    con = _connect(db_path)
    try:
        row = con.execute("SELECT id FROM firmen WHERE name = ?", (firmen_name,)).fetchone()
        if not row:
            return []
        where = "" if include_deleted else "AND p.is_deleted = 0"
        rows = con.execute(
            f"SELECT p.* FROM produkte p WHERE p.firmen_id = ? {where} "
            "ORDER BY p.is_default DESC, p.name COLLATE NOCASE",
            (row["id"],),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_produkt(
    db_path: Path,
    firmen_name: str,
    name: str,
    *,
    beschreibung: str = "",
    produktklasse: str = "default",
    is_default: bool = False,
    produkt_id: int | None = None,
) -> int:
    """Produkt anlegen oder aktualisieren. Gibt die Produkt-ID zurück."""
    con = _connect(db_path)
    try:
        firmen_row = con.execute("SELECT id FROM firmen WHERE name = ?", (firmen_name,)).fetchone()
        if not firmen_row:
            raise ValueError(f"Firma nicht gefunden: {firmen_name}")
        firmen_id = firmen_row["id"]

        if is_default:
            con.execute(
                "UPDATE produkte SET is_default = 0, updated_at = datetime('now') WHERE firmen_id = ?",
                (firmen_id,),
            )

        if produkt_id is not None:
            con.execute(
                "UPDATE produkte SET name = ?, beschreibung = ?, produktklasse = ?, "
                "is_default = ?, updated_at = datetime('now') WHERE id = ? AND firmen_id = ?",
                (name, beschreibung, produktklasse, int(is_default), produkt_id, firmen_id),
            )
            con.commit()
            return produkt_id
        else:
            cur = con.execute(
                "INSERT OR IGNORE INTO produkte (firmen_id, name, beschreibung, produktklasse, is_default) "
                "VALUES (?, ?, ?, ?, ?)",
                (firmen_id, name, beschreibung, produktklasse, int(is_default)),
            )
            if cur.rowcount == 0:
                # Name conflict – update existing
                con.execute(
                    "UPDATE produkte SET beschreibung = ?, produktklasse = ?, is_default = ?, "
                    "updated_at = datetime('now') WHERE firmen_id = ? AND name = ?",
                    (beschreibung, produktklasse, int(is_default), firmen_id, name),
                )
            con.commit()
            row = con.execute(
                "SELECT id FROM produkte WHERE firmen_id = ? AND name = ?", (firmen_id, name)
            ).fetchone()
            return row["id"] if row else -1
    finally:
        con.close()


def delete_produkt(db_path: Path, produkt_id: int) -> None:
    """Produkt soft-löschen."""
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE produkte SET is_deleted = 1, deleted_at = datetime('now'), "
            "updated_at = datetime('now') WHERE id = ?",
            (produkt_id,),
        )
        con.commit()
    finally:
        con.close()


def restore_produkt(db_path: Path, produkt_id: int) -> None:
    """Soft-gelöschtes Produkt reaktivieren."""
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE produkte SET is_deleted = 0, deleted_at = NULL, "
            "updated_at = datetime('now') WHERE id = ?",
            (produkt_id,),
        )
        con.commit()
    finally:
        con.close()


def hard_delete_produkt(db_path: Path, produkt_id: int) -> None:
    """Produkt unwiderruflich löschen."""
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM produkte WHERE id = ?", (produkt_id,))
        con.commit()
    finally:
        con.close()


def set_default_produkt(db_path: Path, firmen_name: str, produkt_id: int) -> None:
    """Setzt ein Produkt als Standard für den Firmen."""
    con = _connect(db_path)
    try:
        firmen_row = con.execute("SELECT id FROM firmen WHERE name = ?", (firmen_name,)).fetchone()
        if not firmen_row:
            return
        firmen_id = firmen_row["id"]
        con.execute(
            "UPDATE produkte SET is_default = 0, updated_at = datetime('now') WHERE firmen_id = ?",
            (firmen_id,),
        )
        con.execute(
            "UPDATE produkte SET is_default = 1, updated_at = datetime('now') WHERE id = ? AND firmen_id = ?",
            (produkt_id, firmen_id),
        )
        con.commit()
    finally:
        con.close()
