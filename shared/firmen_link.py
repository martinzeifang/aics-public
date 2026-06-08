"""S1 (#1071): Logischer ``firmen_id``-FK für die Modul-Projekttabellen.

Die Projekt↔Firma-Verknüpfung existierte bisher nur über die TEXT-Spalte
``unternehmen``. Für ein zuverlässiges Risiko-Cockpit (Filter „alle Risiken der
Firma X", #1078) und die DSFA-Verknüpfung (#1084) wird eine ``firmen_id``-Spalte
ergänzt.

Wichtig: Die Modul-DBs (``rb.sqlite``/``nis2.sqlite``/…) sind **separate**
SQLite-Dateien getrennt von ``firmen.sqlite``. SQLite kann keine Cross-Database-
Foreign-Keys erzwingen — ``firmen_id`` ist daher eine **logische** Referenz
(INTEGER, NULL = nicht zugeordnet), die per Name-Match (``unternehmen`` ↔
``firmen.name``) befüllt wird. ``firmen.sqlite`` liegt neben der Modul-DB.

Vorbild: ``evidence/db.py`` (firmen_id-Härtung aus #1003).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Modul-DB-Dateiname → (Projekt-Tabelle, Firmen-Namensspalte).
# Achtung: AI-Act nutzt ``organisation`` statt ``unternehmen``.
MODULE_PROJECT_TABLES: dict[str, tuple[str, str]] = {
    "risikobewertung.sqlite": ("rb_projekte", "unternehmen"),
    "nis2.sqlite": ("nis2_projekte", "unternehmen"),
    "ai_act.sqlite": ("ai_act_projekte", "organisation"),
    "dsgvo.sqlite": ("dsgvo_projekte", "unternehmen"),
    "cra.sqlite": ("cra_projekte", "unternehmen"),
}


def firmen_db_path(module_db: Path) -> Path:
    """``firmen.sqlite`` neben der Modul-DB."""
    return Path(module_db).parent / "firmen.sqlite"


def firmen_name_to_id(firmen_db: Path) -> dict[str, int]:
    """Map ``name.casefold()`` → ``firmen.id`` (nur nicht gelöschte Firmen)."""
    out: dict[str, int] = {}
    try:
        con = sqlite3.connect(str(firmen_db))
        try:
            for fid, name in con.execute(
                "SELECT id, name FROM firmen WHERE COALESCE(is_deleted, 0) = 0"
            ):
                if name and str(name).strip():
                    out[str(name).strip().casefold()] = int(fid)
        finally:
            con.close()
    except Exception:
        pass
    return out


def ensure_firmen_id_column(con: sqlite3.Connection, table: str) -> None:
    """Idempotent: ``firmen_id INTEGER`` + Index ergänzen, falls noch nicht vorhanden."""
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    if not cols:
        return  # Tabelle existiert (noch) nicht
    if "firmen_id" not in cols:
        con.execute(f"ALTER TABLE {table} ADD COLUMN firmen_id INTEGER")
    con.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{table}_firmen ON {table}(firmen_id)"
    )
    con.commit()


def backfill_firmen_ids(module_db: Path, table: str,
                        name_col: str = "unternehmen",
                        firmen_db: Path | None = None) -> dict:
    """``firmen_id`` per Name-Match befüllen — nur dort, wo noch leer.

    Liefert ``{matched, unmatched: [namen]}``. ``unmatched`` = Projekte mit
    nicht-leerem ``unternehmen``, für die keine Firma gefunden wurde (→ Admin-UI
    zur manuellen Zuordnung, #1071). ``firmen_db`` überschreibt die Standard-
    Sibling-Auflösung (für Tests).
    """
    name2id = firmen_name_to_id(firmen_db or firmen_db_path(Path(module_db)))
    con = sqlite3.connect(str(module_db))
    try:
        ensure_firmen_id_column(con, table)
        rows = con.execute(
            f"SELECT rowid, {name_col} FROM {table} WHERE firmen_id IS NULL"
        ).fetchall()
        matched, unmatched = 0, []
        for rowid, name in rows:
            fid = name2id.get(str(name or "").strip().casefold())
            if fid:
                con.execute(
                    f"UPDATE {table} SET firmen_id=? WHERE rowid=?", (fid, rowid)
                )
                matched += 1
            elif str(name or "").strip():
                unmatched.append(str(name).strip())
        con.commit()
        return {"matched": matched, "unmatched": sorted(set(unmatched))}
    finally:
        con.close()
