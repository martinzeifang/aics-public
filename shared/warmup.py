"""#1471: Schema-/Migrations-Warmup beim Worker-Start.

Hintergrund: Die Modul-``ensure_db``/``ensure_table``-Funktionen führen beim ERSTEN
Aufruf je Worker-Prozess die idempotenten DDL-Migrationen aus (``ALTER TABLE … ADD
COLUMN IF NOT EXISTS`` + ``CREATE INDEX IF NOT EXISTS``). ``shared.db`` (#1396) cached
diese DDL danach prozessweit, sodass Folge-Requests KEINE DB-DDL mehr auslösen.

Problem ohne Warmup: Der erste betroffene Request eines kalten Workers trägt diese
Last — auf Remote-Postgres etliche Round-Trips, und jedes ``ALTER`` nimmt einen
ACCESS-EXCLUSIVE-Lock, der mit parallel laufenden SELECTs (z. B. die gleichzeitigen
Incident-Detail-Reads, #1467) um den Lock konkurriert. Folge: der erste „Endgültig
schließen"-Klick hing lange (Gunicorn-Timeout 1800 s), der zweite war schnell.

Lösung: Alle Modul-Schemata EINMAL beim App-/Worker-Start vorwärmen — also bevor
Requests bedient werden und ohne konkurrierende Live-Reads. Danach sind alle DDL im
#1396-Cache; kein Request läuft mehr in eine Migration. Best-effort: ein
fehlschlagendes Modul (z. B. DB kurz nicht erreichbar) bricht den Start NICHT ab; das
Schema wärmt sich dann beim ersten Zugriff wie bisher selbst.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any


def _db(name: str) -> Path:
    return Path(f"data/db/{name}.sqlite")


# (Modulpfad, Funktionsname, args) — die Hauptschemata mit den umfangreichsten
# Migrationen / heißesten Pfaden. Nicht gelistete (Unter-)Schemata wärmen sich
# weiterhin beim ersten Zugriff selbst (#1396).
_PLAN: list[tuple[str, str, tuple[Any, ...]]] = [
    ("soc.db", "ensure_db", (_db("soc"),)),
    ("cra.db", "ensure_db", (_db("cra"),)),
    ("cra.konformitaet_db", "ensure_table", ()),
    ("cra.traceability_db", "ensure_db", ()),
    ("nis2.db", "ensure_db", (_db("nis2"),)),
    ("dsgvo.db", "ensure_db", (_db("dsgvo"),)),
    ("dsgvo.betroffenenrechte_db", "ensure_table", ()),
    ("evidence.db", "ensure_db", ()),
    ("firmen.db", "ensure_db", ()),
    ("gutachten.db", "ensure_db", (_db("gutachten"),)),
    ("gutachten.gerichts_db", "ensure_db", (_db("gutachten"),)),
    ("ai_act.db", "ensure_db", (_db("ai_act"),)),
    ("wiba.db", "ensure_db", (_db("wiba"),)),
]


def warm_schemas(logger: Any = None) -> dict[str, int]:
    """Migrationen aller Hauptmodule einmalig ausführen. Best-effort, nie raising.

    Über ``AICS_WARM_SCHEMAS=0`` abschaltbar. Returns ``{ok, fail}`` (für Tests/Logs).
    """
    if os.getenv("AICS_WARM_SCHEMAS", "1") == "0":
        return {"ok": 0, "fail": 0, "skipped": 1}

    ok = fail = 0

    def _run(label: str, fn) -> None:
        nonlocal ok, fail
        try:
            fn()
            ok += 1
        except Exception:  # noqa: BLE001 — Warmup darf den Start nie verhindern
            fail += 1
            if logger is not None:
                logger.warning("Schema-Warmup übersprungen: %s", label, exc_info=True)

    for modpath, fnname, args in _PLAN:
        def _call(modpath=modpath, fnname=fnname, args=args):
            getattr(importlib.import_module(modpath), fnname)(*args)
        _run(f"{modpath}.{fnname}", _call)

    # risikobewertung migriert in _connect() (kein ensure_db) → ein Connect wärmt es.
    def _warm_rb():
        from risikobewertung import db as rbdb
        con = rbdb._connect(_db("risikobewertung"))
        con.close()
    _run("risikobewertung._connect", _warm_rb)

    # #1338: Audit-Trail-Tabelle (Schema „audit") vorab anlegen.
    def _warm_audit():
        from shared.audit_db import ensure_audit_db
        ensure_audit_db()
    _run("shared.audit_db", _warm_audit)

    # shared/documents: je Modul Dokumenten- + Checklisten-Tabelle.
    def _warm_docs():
        from shared.documents import db as docdb
        for modul in docdb.MODULES:
            docdb.ensure_documents_table(_db(modul), modul)
            docdb.ensure_checklist_table(_db(modul), modul)
    _run("shared.documents", _warm_docs)

    if logger is not None:
        logger.info("✓ Schema-Warmup: %d ok, %d übersprungen", ok, fail)
    return {"ok": ok, "fail": fail}
