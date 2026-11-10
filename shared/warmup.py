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


# (Modulpfad, Funktionsname, args) — die Schemata, deren ``ensure_*`` ein
# Argument **braucht**. Alles Übrige findet :func:`_entdeckte_schemata`
# automatisch (#2094).
#
# #2094: Diese Liste war der ganze Plan und nannte **12** Einträge, während im
# Baum **54** Module ein eigenes ``ensure_db``/``ensure_table``/``ensure_tables``
# haben. Nicht vorgewärmt waren darunter zwei **ganze Modulschemata**
# (``pentest.db``, ``compliance_audit.db``) und vier querschnittliche, die an
# jedem zweiten Klick hängen: ``shared.issue_links`` (jede Issue-Handlung in
# sechs Modulen, #1846), ``shared.ki_herkunft`` (jede KI-Bewertung, #1765),
# ``shared.prompt_hinweise`` (jeder Prompt, #1835) und ``shared.risk_req_links``
# (#1564).
#
# Der Dateikopf sagte dazu „Nicht gelistete (Unter-)Schemata wärmen sich
# weiterhin beim ersten Zugriff selbst" — das stimmt, ist aber genau die Last,
# die #1471 vom Request wegnehmen wollte. Eine handgeführte Positivliste über
# Module, die anderswo entstehen, wächst nicht mit (#1731/#1735/#1870): Seit
# #1471 sind 40 Module dazugekommen und keines in diese Liste.
_PLAN: list[tuple[str, str, tuple[Any, ...]]] = [
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
    # #2094: Drei Schemata, die ein Argument brauchen und deshalb nicht
    # entdeckt werden — und gerade sie hängen an jedem zweiten Klick:
    ("compliance_audit.db", "ensure_db", (_db("gutachten"),)),   # Tabellen historisch (#1713)
    ("pentest.db", "ensure_db", (_db("pentest"),)),
    # `shared.issue_links` und `shared.risk_req_links` liegen je Modul-DB.
    # Gewärmt werden die Module, in denen die Fabrik (#1846) bzw. die
    # Risiko-Verknüpfung (#1564) hängt — je Datei ein eigener Aufruf, weil die
    # Tabelle im jeweiligen Schema liegt.
    *[("shared.issue_links", "ensure_tables", (_db(_m),))
      for _m in ("cra", "nis2", "ai_act", "dsgvo", "wiba", "risikobewertung")],
    *[("shared.risk_req_links", "ensure_tables", (_db(_m),))
      for _m in ("cra", "nis2", "ai_act", "dsgvo", "risikobewertung")],
]


#: Funktionsnamen, die ein Schema idempotent anlegen.
_ENSURE_NAMEN: tuple[str, ...] = ("ensure_db", "ensure_table", "ensure_tables")

#: Verzeichnisse, die der Webdienst nicht lädt (Werkzeuge, Tests, Frontend).
_NICHT_SCANNEN: tuple[str, ...] = (
    "tests", "tools", "scripts", "frontend", "node_modules", ".claude",
    ".git", "data", "out", "docs", "__pycache__", ".github", "venv", ".venv",
)


def _entdeckte_schemata() -> list[tuple[str, str, tuple[Any, ...]]]:
    """Alle Module mit einem **argumentlos aufrufbaren** ``ensure_*`` (#2094).

    Gesucht wird im Quellbaum, nicht in einer Liste: Ein neues Modul ist damit
    von sich aus vorgewärmt. Das ist die Richtung aus #1785 (Ausschlussliste
    statt Positivliste) — bei einer Positivliste merkt man den Fehler erst,
    wenn ein Anwender wartet.

    **Nur argumentlos aufrufbare Funktionen.** Wer einen Pfad braucht, steht in
    :data:`_PLAN`; den Pfad hier zu raten wäre schlimmer als nicht zu wärmen —
    ein falscher Pfad legt ein Schema am falschen Ort an.
    """
    import inspect

    wurzel = Path(__file__).resolve().parents[1]
    gefunden: list[tuple[str, str, tuple[Any, ...]]] = []
    bekannt = {(m, f) for m, f, _ in _PLAN}

    for datei in sorted(wurzel.rglob("*.py")):
        rel = datei.relative_to(wurzel)
        if any(teil in _NICHT_SCANNEN for teil in rel.parts):
            continue
        try:
            quelle = datei.read_text(encoding="utf-8")
        except OSError:
            continue
        if not any(f"def {n}(" in quelle for n in _ENSURE_NAMEN):
            continue
        modpath = ".".join(rel.with_suffix("").parts)
        if modpath.endswith(".__init__"):
            modpath = modpath[: -len(".__init__")]
        try:
            modul = importlib.import_module(modpath)
        except Exception:      # noqa: BLE001 — ein nicht ladbares Modul wärmt nichts
            continue
        for name in _ENSURE_NAMEN:
            fn = getattr(modul, name, None)
            if fn is None or not callable(fn):
                continue
            if (modpath, name) in bekannt:
                continue
            try:
                sig = inspect.signature(fn)
            except (TypeError, ValueError):
                continue
            pflicht = [p for p in sig.parameters.values()
                       if p.default is inspect.Parameter.empty
                       and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
            if pflicht:
                continue          # braucht ein Argument → gehört in _PLAN
            gefunden.append((modpath, name, ()))
    return gefunden


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

    plan = list(_PLAN)
    try:
        plan += _entdeckte_schemata()
    except Exception:  # noqa: BLE001 — ohne Entdeckung bleibt der Bestandsplan
        if logger is not None:
            logger.warning("Schema-Entdeckung übersprungen", exc_info=True)

    for modpath, fnname, args in plan:
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
