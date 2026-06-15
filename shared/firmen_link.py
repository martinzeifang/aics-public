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

from pathlib import Path

from shared import db as _sdb

# Modul-DB-Dateiname → (Projekt-Tabelle, Firmen-Namensspalte).
# Achtung: AI-Act nutzt ``organisation`` statt ``unternehmen``.
MODULE_PROJECT_TABLES: dict[str, tuple[str, str]] = {
    "risikobewertung.sqlite": ("rb_projekte", "unternehmen"),
    "nis2.sqlite": ("nis2_projekte", "unternehmen"),
    "ai_act.sqlite": ("ai_act_projekte", "organisation"),
    "dsgvo.sqlite": ("dsgvo_projekte", "unternehmen"),
    "cra.sqlite": ("cra_projekte", "unternehmen"),
    "wiba.sqlite": ("wiba_projekte", "unternehmen"),
    "soc.sqlite": ("soc_assets", "organisation"),  # SOC-Assets → Firma (#1280)
}


def firmen_db_path(module_db: Path) -> Path:
    """``firmen.sqlite`` neben der Modul-DB."""
    return Path(module_db).parent / "firmen.sqlite"


def firmen_name_to_id(firmen_db: Path) -> dict[str, int]:
    """Map ``name.casefold()`` → ``firmen.id`` (nur nicht gelöschte Firmen)."""
    out: dict[str, int] = {}
    try:
        con = _sdb.connect(firmen_db)
        try:
            # WICHTIG: positionsweise über row[0]/row[1] zugreifen — der PG-Kompat-Layer
            # liefert DBRow (dict-Subklasse); Tuple-Unpacking ``for a, b in rows`` würde
            # die KEYS statt der Werte liefern (anders als sqlite3.Row).
            for row in con.execute(
                "SELECT id, name FROM firmen WHERE COALESCE(is_deleted, 0) = 0"
            ).fetchall():
                fid, name = row[0], row[1]
                if name and str(name).strip():
                    out[str(name).strip().casefold()] = int(fid)
        finally:
            con.close()
    except Exception:
        pass
    return out


def ensure_firmen_id_column(con, table: str) -> None:
    """Idempotent: ``firmen_id INTEGER`` + Index ergänzen (Postgres, #1332)."""
    con.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS firmen_id INTEGER")
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
    con = _sdb.connect(module_db)
    try:
        ensure_firmen_id_column(con, table)
        matched = 0
        # Mengen-basiertes UPDATE je Firma (case-insensitiv) — kein Zeilen-Roundtrip,
        # kein ctid-Rückbinden. Nur noch leere firmen_id werden gesetzt.
        for fname, fid in name2id.items():
            cur = con.execute(
                f"UPDATE {table} SET firmen_id=? "
                f"WHERE firmen_id IS NULL AND LOWER(TRIM({name_col}))=?",
                (fid, fname),
            )
            matched += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        # Verbleibende, nicht zugeordnete Projekte mit nicht-leerem Namen sammeln.
        unmatched = []
        for row in con.execute(
            f"SELECT DISTINCT {name_col} FROM {table} "
            f"WHERE firmen_id IS NULL AND TRIM(COALESCE({name_col},'')) <> ''"
        ).fetchall():
            unmatched.append(str(row[0]).strip())
        con.commit()
        return {"matched": matched, "unmatched": sorted(set(unmatched))}
    finally:
        con.close()
