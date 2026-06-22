#!/usr/bin/env python3
"""Alle Modul-Tabellen in Postgres anlegen (Cutover-Hilfe, #894).

Importiert je Modul-Paket alle ``*_db``/``db``-Submodule und ruft deren
``ensure_db``/``ensure_database``/``ensure_table`` mit dem kanonischen
SQLite-Pfad (``data/db/<stem>.sqlite``) auf. ``shared.db.schema_for`` leitet
daraus das Schema ab, sodass die kanonische App-DDL (inkl. ``IDENTITY``) in das
richtige Postgres-Schema geschrieben wird. Idempotent (``CREATE TABLE IF NOT
EXISTS``). Erforderlich vor der Datenmigration, damit kein Tabellen-Pendant fehlt.

Usage:  DATABASE_URL=... PYTHONPATH=/app python scripts/ensure_all_pg.py
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

# Paket -> SQLite-Stem (== Schema). shared.templates -> templates.
PKG_STEM = {
    "soc": "soc",
    "wiba": "wiba",
    "risikobewertung": "risikobewertung",
    "cra": "cra",
    "dsgvo": "dsgvo",
    "nis2": "nis2",
    "ai_act": "ai_act",
    "gutachten": "gutachten",
    "firmen": "firmen",
    "ict": "ict",
    "baso": "baso",
    "compliance": "compliance",
    "shared.templates": "templates",
}
# Hinweis: compliance_db ist ein Tkinter-only Ollama-RAG-Index (nicht web-bedient,
# nutzt weiter sqlite3) → bewusst NICHT in Postgres migriert.


def _call_ensure(fn, path: Path) -> None:
    try:
        fn(path)
    except TypeError:
        fn()  # Funktion ohne Pfad-Parameter -> nutzt eigenen Default (gleicher Stem)


# Module mit geteilter linked_issues-Tabelle (shared.issue_links, je Schema).
ISSUE_LINK_STEMS = ["cra", "nis2", "ai_act", "dsgvo", "soc", "wiba", "risikobewertung"]
# Module mit geteilter <modul>_managed_docs-Tabelle (shared.documents).
DOC_MODULES = ["cra", "nis2", "ai_act", "dsgvo", "wiba"]


def main() -> int:
    src = Path("data/db")
    ok = fail = 0

    def _try(label, thunk):
        nonlocal ok, fail
        try:
            thunk()
            ok += 1
        except Exception as exc:
            fail += 1
            print(f"  [ensure-fail] {label}: {exc!r}"[:160])

    # 1) Generische public ensure_db/database/table je Modul-Submodul
    for pkg, stem in PKG_STEM.items():
        path = src / f"{stem}.sqlite"
        try:
            P = importlib.import_module(pkg)
        except Exception as exc:
            print(f"[skip] {pkg}: {exc!r}")
            continue
        names = [pkg]
        if hasattr(P, "__path__"):
            names += [n for _, n, _ in pkgutil.iter_modules(P.__path__, pkg + ".")]
        for name in names:
            try:
                m = importlib.import_module(name)
            except Exception:
                continue
            for attr in ("ensure_db", "ensure_database", "ensure_table"):
                fn = getattr(m, attr, None)
                if callable(fn):
                    _try(f"{name}.{attr}", lambda fn=fn, p=path: _call_ensure(fn, p))
                    break

    # 2) risikobewertung legt Tabellen als _connect-Seiteneffekt an (kein ensure_db)
    def _rb():
        from risikobewertung import db as rbdb
        rbdb._connect(src / "risikobewertung.sqlite").close()
    _try("risikobewertung.db._connect", _rb)

    # 3) Geteilte linked_issues-Tabelle je Modul-Schema
    from shared import issue_links as _il
    for stem in ISSUE_LINK_STEMS:
        _try(f"issue_links[{stem}]",
             lambda s=stem: _il.ensure_tables(src / f"{s}.sqlite"))

    # 4) Geteilte <modul>_managed_docs + Checklist je Doc-Modul
    from shared.documents import db as _ddb
    for modul in DOC_MODULES:
        p = src / f"{modul}.sqlite"
        _try(f"managed_docs[{modul}]",
             lambda p=p, m=modul: _ddb.ensure_documents_table(p, m))
        if hasattr(_ddb, "ensure_checklist_table"):
            _try(f"checklist[{modul}]",
                 lambda p=p, m=modul: _ddb.ensure_checklist_table(p, m))

    # 5) gutachten: private _ensure*-Funktionen (befangenheit/forensik/honorar/…)
    gpath = src / "gutachten.sqlite"
    try:
        import gutachten as _G
        for _, gname, _ in pkgutil.iter_modules(_G.__path__, "gutachten."):
            try:
                gm = importlib.import_module(gname)
            except Exception:
                continue
            for attr in dir(gm):
                if attr.startswith("_ensure") and callable(getattr(gm, attr)):
                    _try(f"{gname}.{attr}",
                         lambda f=getattr(gm, attr): _call_ensure(f, gpath))
    except Exception as exc:
        print(f"[skip] gutachten _ensure*: {exc!r}")

    print(f"=== ensure_all: {ok} ok, {fail} fehlgeschlagen ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
