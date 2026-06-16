#!/usr/bin/env python3
"""Datenmigration SQLite → PostgreSQL (#894).

Kopiert die Daten jeder Modul-SQLite-Datei in das passende Postgres-Schema
(Schema = Datei-Stem, identisch zu ``shared.db.schema_for``). Idempotent über
``TRUNCATE`` je Tabelle vor dem Einspielen; verifiziert per Zeilenzahl.

Arbeitet bewusst mit **rohem psycopg** (nicht dem Kompat-Layer), weil:
- ``id``-Spalten sind ``GENERATED ALWAYS AS IDENTITY`` → expliziter Insert braucht
  ``OVERRIDING SYSTEM VALUE`` (FK-Beziehungen innerhalb eines Schemas erfordern die
  Erhaltung der Original-IDs);
- nach dem Einspielen wird die IDENTITY-Sequenz auf ``max(id)`` gesetzt, damit
  künftige App-Inserts nicht kollidieren.

Voraussetzung: Die Ziel-Tabellen existieren (vorher ``scripts/ensure_all_pg.py``
laufen lassen; App-Boot legt nur einen Teil an). ``DATABASE_URL`` gesetzt.

Usage:
  DATABASE_URL=postgresql://aics:pw@host:5432/aics PYTHONPATH=/app \
    python scripts/migrate_sqlite_to_pg.py --src data/db [--only soc,cra] [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import psycopg

from shared.db import database_url, schema_for

# Schemata, die NICHT aus einer .sqlite-Datei migriert werden.
# compliance_db = Tkinter-only Ollama-RAG-Index (nicht web-bedient) → bleibt SQLite.
SKIP_STEMS = {"scheduler", "compliance_db"}


def _sqlite_tables(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'").fetchall()
    return [r[0] for r in rows]


def migrate_file(sqlite_path: Path, *, dry_run: bool = False) -> dict:
    schema = schema_for(sqlite_path)
    scon = sqlite3.connect(str(sqlite_path))
    scon.row_factory = sqlite3.Row
    pcon = psycopg.connect(database_url(), autocommit=False)
    report = {"schema": schema, "tables": {}, "skipped": [], "errors": []}
    try:
        with pcon.cursor() as c:
            c.execute(f'SET search_path TO "{schema}"')
            # FK-Prüfung während Bulk-Load aus (Tabellen-Reihenfolge irrelevant).
            # Benötigt Superuser; POSTGRES_USER des offiziellen Images ist Superuser.
            try:
                c.execute("SET session_replication_role = replica")
            except Exception:
                pcon.rollback()
        pcon.commit()
        for table in _sqlite_tables(scon):
            try:
                _migrate_table(scon, pcon, schema, table, report, dry_run)
            except Exception as exc:  # eine Tabelle darf den Rest nicht killen
                pcon.rollback()
                report["errors"].append(f"{table}: {exc!r}"[:200])
    finally:
        scon.close()
        pcon.close()
    return report


def _migrate_table(scon, pcon, schema, table, report, dry_run):
    with pcon.cursor() as c:
        c.execute("SELECT to_regclass(%s)", (f'"{schema}"."{table}"',))
        if c.fetchone()[0] is None:
            report["skipped"].append(f"{table} (kein PG-Pendant)")
            return
        c.execute(
            "SELECT column_name, is_identity FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
            (schema, table))
        meta = c.fetchall()
    pg_cols = {r[0] for r in meta}
    id_cols = {r[0] for r in meta if r[1] == "YES"}

    src_rows = scon.execute(f'SELECT * FROM "{table}"').fetchall()
    if not src_rows:
        report["tables"][table] = 0
        return
    cols = [col for col in src_rows[0].keys() if col in pg_cols]
    if not cols:
        report["skipped"].append(f"{table} (keine gemeinsamen Spalten)")
        return
    if dry_run:
        report["tables"][table] = len(src_rows)
        return

    collist = ", ".join(f'"{col}"' for col in cols)
    ph = ", ".join("%s" for _ in cols)
    overriding = " OVERRIDING SYSTEM VALUE" if (id_cols & set(cols)) else ""
    data = [tuple(r[col] for col in cols) for r in src_rows]
    with pcon.cursor() as c:
        c.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')
        c.executemany(
            f'INSERT INTO "{table}" ({collist}){overriding} VALUES ({ph})', data)
        # IDENTITY-Sequenzen auf max(id) heben, damit App-Inserts nicht kollidieren
        for idc in (id_cols & set(cols)):
            c.execute(
                f'SELECT setval(pg_get_serial_sequence(%s, %s), '
                f'GREATEST((SELECT COALESCE(MAX("{idc}"), 0) FROM "{table}"), 1))',
                (f"{schema}.{table}", idc))
        c.execute(f'SELECT COUNT(*) FROM "{table}"')
        n_pg = c.fetchone()[0]
    pcon.commit()
    report["tables"][table] = n_pg
    if n_pg != len(src_rows):
        report["errors"].append(f"{table}: SQLite {len(src_rows)} != PG {n_pg}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/db", help="Verzeichnis mit *.sqlite")
    ap.add_argument("--only", default="", help="Komma-Liste von Datei-Stems")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = Path(args.src)
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    files = sorted(p for p in src.glob("*.sqlite")
                   if schema_for(p) not in SKIP_STEMS
                   and not p.stem.startswith(("pytest", "_pytest", "_smoke")))
    if only:
        files = [p for p in files if schema_for(p) in only]

    total_rows = total_err = total_skip = 0
    for p in files:
        rep = migrate_file(p, dry_run=args.dry_run)
        rows = sum(rep["tables"].values())
        total_rows += rows
        total_err += len(rep["errors"])
        total_skip += len(rep["skipped"])
        flag = " DRY" if args.dry_run else ""
        print(f"[{rep['schema']}]{flag} {len(rep['tables'])} Tabellen, {rows} Zeilen"
              + (f", {len(rep['skipped'])} übersprungen" if rep["skipped"] else ""))
        for s in rep["skipped"]:
            print(f"   – übersprungen: {s}")
        for e in rep["errors"]:
            print(f"   ⚠ {e}")
    print(f"\n=== Gesamt: {total_rows} Zeilen, {total_skip} übersprungen, "
          f"{total_err} Fehler ===")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
