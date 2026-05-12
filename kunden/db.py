"""Zentrale Kunden/Projekt-Verwaltung – SQLite-Datenzugriff."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from security_utils import safe_generated_file, workspace_root_from
from shared.sql import quote_ident
from shared.db_security import connect_sqlite
from shared.db_security import connect_sqlite

DEFAULT_DB_PATH = Path("data/db/kunden.sqlite")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-32000;

CREATE TABLE IF NOT EXISTS kunden (
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
    kunden_id     INTEGER NOT NULL REFERENCES kunden(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    beschreibung  TEXT NOT NULL DEFAULT '',
    produktklasse TEXT NOT NULL DEFAULT 'default',
    is_default    INTEGER NOT NULL DEFAULT 0,
    is_deleted    INTEGER NOT NULL DEFAULT 0,
    deleted_at    TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(kunden_id, name)
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


def ensure_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        # Migrate: add columns that may not exist in older DBs
        for col, default in [("module_dsgvo", 1), ("module_nis2", 1), ("module_ai_act", 1)]:
            try:
                # Identifiers cannot be parameter-bound; keep strictly quoted.
                con.execute(
                    f"ALTER TABLE kunden ADD COLUMN {quote_ident(col)} INTEGER NOT NULL DEFAULT {int(default)}"
                )
                con.commit()
            except Exception:
                pass
        for stmt in [
            "ALTER TABLE kunden ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE kunden ADD COLUMN deleted_at TEXT",
        ]:
            try:
                con.execute(stmt)
                con.commit()
            except Exception:
                pass
        con.commit()
        # Migrate: für jeden Kunden mit gesetztem produkt-Feld ein Default-Produkt anlegen
        _migrate_default_produkte(con)
        con.commit()
    finally:
        con.close()


def _migrate_default_produkte(con: sqlite3.Connection) -> None:
    """Legt für jeden Kunden, der noch kein Produkt hat, ein Default-Produkt an."""
    rows = con.execute(
        "SELECT id, name, produkt, produktklasse FROM kunden WHERE is_deleted = 0"
    ).fetchall()
    for row in rows:
        kunden_id = row["id"]
        existing = con.execute(
            "SELECT id FROM produkte WHERE kunden_id = ?", (kunden_id,)
        ).fetchone()
        if existing:
            continue
        # Default-Name = Kundenname für Backwards-Compatibility
        # (CRA/RB-Daten sind unter dem Kundennamen gespeichert)
        prod_name = row["name"]
        prod_klasse = row["produktklasse"] or "default"
        try:
            con.execute(
                "INSERT OR IGNORE INTO produkte (kunden_id, name, produktklasse, is_default) "
                "VALUES (?, ?, ?, 1)",
                (kunden_id, prod_name, prod_klasse),
            )
        except Exception:
            pass


def list_produkte_for_module(db_path: Path, module: str) -> list[dict[str, Any]]:
    """Gibt alle aktiven Produkte zurück, deren Kunde das Modul aktiviert hat.

    Rückgabe: Liste von Dicts mit Feldern:
      - produkt_name: str   (Projekt-Schlüssel, rückwärtskompatibel)
      - kunden_name:  str
      - display:      str   ("Kunden / Produkt" wenn Kunde >1 Produkt, sonst nur Kundenname)
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
            "SELECT k.name AS kunden_name, p.name AS produkt_name, "
            "p.id AS produkt_id, p.is_default, "
            "COUNT(p2.id) AS prod_count "
            "FROM kunden k "
            "JOIN produkte p ON p.kunden_id = k.id AND p.is_deleted = 0 "
            "JOIN produkte p2 ON p2.kunden_id = k.id AND p2.is_deleted = 0 "
            f"WHERE k.{quote_ident(col)} = 1 AND k.is_deleted = 0 "
            "GROUP BY p.id "
            "ORDER BY k.updated_at DESC, k.name COLLATE NOCASE, "
            "p.is_default DESC, p.name COLLATE NOCASE",
        ).fetchall()
        result = []
        for r in rows:
            prod_count = r["prod_count"]
            kunden_name = r["kunden_name"]
            produkt_name = r["produkt_name"]
            if prod_count > 1 or produkt_name != kunden_name:
                display = f"{kunden_name} / {produkt_name}"
            else:
                display = kunden_name
            result.append({
                "produkt_name": produkt_name,
                "kunden_name":  kunden_name,
                "display":      display,
                "is_default":   r["is_default"],
                "produkt_id":   r["produkt_id"],
            })
        return result
    finally:
        con.close()


def list_kunden(db_path: Path = DEFAULT_DB_PATH) -> list[str]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT name FROM kunden WHERE is_deleted = 0 ORDER BY updated_at DESC, name COLLATE NOCASE"
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        con.close()


def list_deleted_kunden(db_path: Path = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    """Gibt alle als gelöscht markierten Kunden zurück."""
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT name, unternehmen, deleted_at FROM kunden WHERE is_deleted = 1 ORDER BY deleted_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def list_kunden_for_module(db_path: Path, module: str) -> list[str]:
    """Projektliste für ein Modul (nur aktive Kunden)."""
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
            f"SELECT name FROM kunden WHERE {quote_ident(col)} = 1 AND is_deleted = 0 ORDER BY updated_at DESC, name COLLATE NOCASE"
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        con.close()


def load_kunde(db_path: Path, name: str) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM kunden WHERE name = ?", (name,)).fetchone()
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


def save_kunde(db_path: Path, name: str, **fields: Any) -> None:
    """Kunden-Datensatz anlegen oder aktualisieren (upsert)."""
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
        existing = con.execute("SELECT id FROM kunden WHERE name = ?", (name,)).fetchone()
        if existing:
            if safe:
                sets = ", ".join(f"{k} = ?" for k in safe)
                vals = list(safe.values()) + [name]
                con.execute(
                    f"UPDATE kunden SET {sets}, updated_at = datetime('now') WHERE name = ?",
                    vals,
                )
        else:
            cols = ["name"] + list(safe.keys())
            placeholders = ", ".join("?" for _ in cols)
            vals = [name] + list(safe.values())
            con.execute(
                f"INSERT INTO kunden ({', '.join(cols)}) VALUES ({placeholders})",
                vals,
            )
            # Neuer Kunde: sofort ein Default-Produkt anlegen
            pk = safe.get("produktklasse", "default")
            kunden_id = con.execute("SELECT id FROM kunden WHERE name = ?", (name,)).fetchone()["id"]
            con.execute(
                "INSERT OR IGNORE INTO produkte (kunden_id, name, produktklasse, is_default) "
                "VALUES (?, ?, ?, 1)",
                (kunden_id, name, pk),
            )
        con.commit()
    finally:
        con.close()


def delete_kunde(db_path: Path, name: str) -> None:
    """Kunden-Datensatz als gelöscht markieren (Soft-Delete)."""
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE kunden SET is_deleted = 1, deleted_at = datetime('now'), updated_at = datetime('now') WHERE name = ?",
            (name,),
        )
        con.commit()
    finally:
        con.close()


def restore_kunde(db_path: Path, name: str) -> None:
    """Soft-gelöschten Kunden reaktivieren."""
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE kunden SET is_deleted = 0, deleted_at = NULL, updated_at = datetime('now') WHERE name = ?",
            (name,),
        )
        con.commit()
    finally:
        con.close()


def hard_delete_kunde(db_path: Path, name: str) -> None:
    """Kunden-Datensatz unwiderruflich löschen."""
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM kunden WHERE name = ?", (name,))
        con.commit()
    finally:
        con.close()


def disable_module(db_path: Path, name: str, module: str) -> None:
    """Modul-Flag für einen Kunden deaktivieren."""
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
            f"UPDATE kunden SET {col} = 0, updated_at = datetime('now') WHERE name = ?",
            (name,),
        )
        con.commit()
    finally:
        con.close()


def migrate_from_module_dbs(
    kunden_db_path: Path,
    rb_db_path: Path | None = None,
    gutachten_db_path: Path | None = None,
    cra_db_path: Path | None = None,
) -> int:
    """Bestehende Projekte aus Modul-DBs in die zentrale Kunden-DB importieren.

    Gibt die Anzahl neu importierter Datensätze zurück.
    """
    ensure_db(kunden_db_path)
    existing = set(list_kunden(kunden_db_path))
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
            save_kunde(kunden_db_path, name, **fields)
            imported += 1

    return imported


# ── Produkte ──────────────────────────────────────────────────────────────────

def list_produkte(db_path: Path, kunden_name: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
    """Gibt alle Produkte eines Kunden zurück."""
    con = _connect(db_path)
    try:
        row = con.execute("SELECT id FROM kunden WHERE name = ?", (kunden_name,)).fetchone()
        if not row:
            return []
        where = "" if include_deleted else "AND p.is_deleted = 0"
        rows = con.execute(
            f"SELECT p.* FROM produkte p WHERE p.kunden_id = ? {where} "
            "ORDER BY p.is_default DESC, p.name COLLATE NOCASE",
            (row["id"],),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_produkt(
    db_path: Path,
    kunden_name: str,
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
        kunden_row = con.execute("SELECT id FROM kunden WHERE name = ?", (kunden_name,)).fetchone()
        if not kunden_row:
            raise ValueError(f"Kunde nicht gefunden: {kunden_name}")
        kunden_id = kunden_row["id"]

        if is_default:
            con.execute(
                "UPDATE produkte SET is_default = 0, updated_at = datetime('now') WHERE kunden_id = ?",
                (kunden_id,),
            )

        if produkt_id is not None:
            con.execute(
                "UPDATE produkte SET name = ?, beschreibung = ?, produktklasse = ?, "
                "is_default = ?, updated_at = datetime('now') WHERE id = ? AND kunden_id = ?",
                (name, beschreibung, produktklasse, int(is_default), produkt_id, kunden_id),
            )
            con.commit()
            return produkt_id
        else:
            cur = con.execute(
                "INSERT OR IGNORE INTO produkte (kunden_id, name, beschreibung, produktklasse, is_default) "
                "VALUES (?, ?, ?, ?, ?)",
                (kunden_id, name, beschreibung, produktklasse, int(is_default)),
            )
            if cur.rowcount == 0:
                # Name conflict – update existing
                con.execute(
                    "UPDATE produkte SET beschreibung = ?, produktklasse = ?, is_default = ?, "
                    "updated_at = datetime('now') WHERE kunden_id = ? AND name = ?",
                    (beschreibung, produktklasse, int(is_default), kunden_id, name),
                )
            con.commit()
            row = con.execute(
                "SELECT id FROM produkte WHERE kunden_id = ? AND name = ?", (kunden_id, name)
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


def set_default_produkt(db_path: Path, kunden_name: str, produkt_id: int) -> None:
    """Setzt ein Produkt als Standard für den Kunden."""
    con = _connect(db_path)
    try:
        kunden_row = con.execute("SELECT id FROM kunden WHERE name = ?", (kunden_name,)).fetchone()
        if not kunden_row:
            return
        kunden_id = kunden_row["id"]
        con.execute(
            "UPDATE produkte SET is_default = 0, updated_at = datetime('now') WHERE kunden_id = ?",
            (kunden_id,),
        )
        con.execute(
            "UPDATE produkte SET is_default = 1, updated_at = datetime('now') WHERE id = ? AND kunden_id = ?",
            (produkt_id, kunden_id),
        )
        con.commit()
    finally:
        con.close()
