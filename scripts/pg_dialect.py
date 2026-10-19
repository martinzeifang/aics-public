#!/usr/bin/env python3
"""SQLite→PostgreSQL Dialekt-Audit + sichere Auto-Fixes (#893).

Usage:
  python scripts/pg_dialect.py audit <datei.py> [...]      # listet SQLite-Idiome
  python scripts/pg_dialect.py fix-datetime <datei.py> ... # datetime('now')→aics_now()
  python scripts/pg_dialect.py audit-all                   # alle Modul-db.py

Die **Auto-Fixes** umfassen nur die blanko-sichere Transformation
``datetime('now')`` → ``aics_now()``. Alle übrigen Funde (IDENTITY-PK, .lastrowid→
RETURNING, INSERT OR IGNORE, julianday, GLOB, strftime, PRAGMA, executescript) sind
**urteilsabhängig** und werden nur GEMELDET (per-Modul-Port + Review).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# (Label, Regex, Hinweis)
PATTERNS = [
    ("datetime('now') [AUTO-FIXBAR]", re.compile(r"datetime\('now'"), "→ aics_now()"),
    ("date('now')", re.compile(r"\bdate\('now'"), "→ (aics_now()::date) o.ä."),
    ("strftime() in SQL", re.compile(r"strftime\("), "→ to_char(col::timestamp, …)"),
    ("julianday()", re.compile(r"julianday\("), "→ EXTRACT(EPOCH FROM (a::ts - b::ts))"),
    ("INSERT OR IGNORE/REPLACE", re.compile(r"INSERT\s+OR\s+(IGNORE|REPLACE)", re.I), "→ ON CONFLICT DO NOTHING/UPDATE"),
    ("PRAGMA", re.compile(r"\bPRAGMA\b", re.I), "→ entfernen (PG hat kein PRAGMA)"),
    ("AUTOINCREMENT", re.compile(r"\bAUTOINCREMENT\b", re.I), "→ GENERATED … AS IDENTITY"),
    ("id INTEGER PRIMARY KEY", re.compile(r"\bid\s+INTEGER\s+PRIMARY\s+KEY", re.I), "→ id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY"),
    (".lastrowid", re.compile(r"\.lastrowid\b"), "→ INSERT … RETURNING id (CurWrapper.lastrowid)"),
    ("sqlite3. module", re.compile(r"\bsqlite3\."), "→ shared.db / psycopg-Fehlerklassen"),
    ("executescript()", re.compile(r"\.executescript\("), "→ ConnWrapper.executescript (ok) / SCHEMA prüfen"),
    ("GLOB", re.compile(r"\bGLOB\b"), "→ ~ (regex) oder LIKE"),
    ("connect_sqlite/_connect raw", re.compile(r"connect_sqlite\(|sqlite3\.connect\("), "→ shared.db.connect"),
    (".sqlite path", re.compile(r"\.sqlite\b"), "→ logischer Schema-Selektor (kein Dateipfad)"),
]

DATETIME_NOW = re.compile(r"datetime\('now'\)")


def audit(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    total = 0
    by_label: dict[str, int] = {}
    for i, line in enumerate(lines, 1):
        for label, rx, hint in PATTERNS:
            if rx.search(line):
                by_label[label] = by_label.get(label, 0) + 1
                total += 1
    if total:
        print(f"\n## {path}  ({total} Treffer)")
        for label, _, hint in PATTERNS:
            n = by_label.get(label, 0)
            if n:
                print(f"  {n:>4}×  {label:<34} {hint}")
    else:
        print(f"\n## {path}  — sauber (keine SQLite-Idiome)")
    return total


def fix_datetime(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    new, n = DATETIME_NOW.subn("aics_now()", text)
    if n:
        path.write_text(new, encoding="utf-8")
    print(f"  {path}: {n}× datetime('now')→aics_now()")
    return n


def module_db_files() -> list[Path]:
    root = Path(__file__).resolve().parent.parent
    out: list[Path] = []
    for mod in ("soc", "cra", "nis2", "dsgvo", "ai_act", "wiba", "risikobewertung",
                "gutachten", "baso", "compliance", "ict", "firmen", "evidence",
                "prefill", "shared/templates", "shared/documents"):
        for name in ("db.py",):
            p = root / mod / name
            if p.exists():
                out.append(p)
    # zusätzliche *_db.py
    for sub in ("nis2", "gutachten", "dsgvo", "ai_act", "server/auth"):
        for p in (root / sub).glob("*_db.py"):
            out.append(p)
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "audit-all":
        grand = 0
        for p in module_db_files():
            grand += audit(p)
        print(f"\n=== Gesamt: {grand} SQLite-Idiom-Treffer ===")
        return 0
    files = [Path(a) for a in sys.argv[2:]]
    if cmd == "audit":
        for p in files:
            audit(p)
        return 0
    if cmd == "fix-datetime":
        tot = 0
        for p in files:
            tot += fix_datetime(p)
        print(f"Gesamt {tot} ersetzt.")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
