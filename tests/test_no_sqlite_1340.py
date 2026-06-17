"""Anti-SQLite-Garantie (#1340): statischer + Laufzeit-Guard.

Stellt sicher, dass nach der PostgreSQL-Migration (#15) **kein** ausgelieferter
App-Code mehr SQLite öffnet oder SQLite-spezifisches SQL nutzt.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# App-Module, die portiert sein MÜSSEN.
APP_DIRS = [
    "soc", "cra", "nis2", "dsgvo", "ai_act", "wiba", "risikobewertung", "gutachten",
    "firmen", "evidence", "baso", "ict", "compliance", "dora", "prefill",
    "shared", "server",
]

# Dateien/Verzeichnisse, in denen SQLite-Bezug erlaubt ist (Layer/Tooling/nicht deployt).
ALLOWLIST = {
    "shared/db.py",            # der Kompat-Layer selbst (Doku/Errors)
    "shared/db_security.py",   # Legacy-SQLite-Helfer (nicht mehr im App-Pfad genutzt)
    "shared/db_viewer.py",     # CLI-Tool
}

# Aktive (nicht-Kommentar-)Code-Muster, die SQLite verraten.
FORBIDDEN = [
    re.compile(r"\bimport sqlite3\b"),
    re.compile(r"\bsqlite3\.connect\("),
    re.compile(r"\bconnect_sqlite\("),
    re.compile(r"datetime\('now'\)"),
    re.compile(r"\bAUTOINCREMENT\b"),
    re.compile(r"\bjulianday\("),
    re.compile(r"\bPRAGMA\s+\w"),
    re.compile(r"COLLATE NOCASE", re.I),  # SQLite-only Collation (#15)
    re.compile(r"\bAUTOINCREMENT\b"),
    re.compile(r"INSERT\s+OR\s+(REPLACE|IGNORE|ROLLBACK|ABORT|FAIL)", re.I),  # #1394: SQLite-Upsert
]


def _code_lines(path: Path):
    """Zeilen ohne reine Kommentarzeilen (vermeidet Kommentar-False-Positives)."""
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            continue
        yield i, raw


def _iter_py():
    for d in APP_DIRS:
        for p in (ROOT / d).rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if rel in ALLOWLIST:
                continue
            yield p, rel


def test_no_sqlite_in_app_code():
    """Statischer Guard: kein SQLite-Idiom in aktivem App-Code."""
    hits = []
    for path, rel in _iter_py():
        for lineno, line in _code_lines(path):
            for rx in FORBIDDEN:
                if rx.search(line):
                    hits.append(f"{rel}:{lineno}: {rx.pattern} -> {line.strip()[:80]}")
    assert not hits, "SQLite-Reste im App-Code:\n" + "\n".join(hits)


def test_runtime_guard_soc_uses_no_sqlite(pg, monkeypatch):
    """Laufzeit-Guard: SOC-Operationen öffnen kein SQLite."""
    import sqlite3

    def _boom(*a, **k):
        raise AssertionError("sqlite3.connect aufgerufen — SQLite-Rest!")

    monkeypatch.setattr(sqlite3, "connect", _boom)
    from soc import db as sdb
    dbp = Path("data/db/pytest_guard.sqlite")
    pg.drop_schema(dbp)
    sdb.ensure_db(dbp)
    iid = sdb.create_incident(dbp, titel="Guard", severity="high", actor="t")
    sdb.set_incident_status(dbp, iid, "in_review", actor="t")
    assert sdb.get_incident(dbp, iid)["status"] == "in_review"
