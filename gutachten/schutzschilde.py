"""G3 — Methodische Schutzschilde.

G3-1 Jura-Sperre — bereits in linters/sprache.py (lint_beurteilung)
G3-2 Symmetrie-Protokollierer + Check
G3-3 Non-liquet-Marker — bereits in DB-Schema (non_liquet/non_liquet_grund)
G3-4 § 407a-KI-Akzeptanz-Log
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared import db as _sdb

from gutachten import gerichts_db as _gdb


_SCHEMA = """
CREATE TABLE IF NOT EXISTS gerichtsgutachten_ki_akzeptanz (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    vorschlag_typ   TEXT NOT NULL DEFAULT '',
    vorschlag_text  TEXT NOT NULL DEFAULT '',
    akzeptiert_von  TEXT NOT NULL DEFAULT '',
    akzeptiert_am   TEXT NOT NULL DEFAULT (aics_now()),
    akzeptiert      INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_kiakz_projekt ON gerichtsgutachten_ki_akzeptanz(projekt_name);
"""


def _ensure(db_path: Path) -> None:
    con = _sdb.connect(db_path)
    try:
        con.executescript(_SCHEMA)
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# G3-2 Symmetrie-Protokollierer + Check
# ─────────────────────────────────────────────────────────

PARTEI_TAGS = ("klaeger", "beklagter", "gericht")


def log_parteikommunikation(
    db_path: Path,
    projekt_name: str,
    titel: str,
    beschreibung: str,
    empfaenger: list[str],
    ereignis_datum: str | None = None,
) -> int:
    """Speichert eine Parteikommunikation als Verfahrensereignis."""
    return _gdb.save_verfahrensereignis(
        db_path,
        projekt_name=projekt_name,
        ereignis_typ="parteikommunikation",
        titel=titel,
        beschreibung=beschreibung,
        empfaenger=empfaenger,
        ereignis_datum=ereignis_datum,
    )


def check_symmetrie(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Prüft, ob jede Parteikommunikation symmetrisch ist (Kläger + Beklagter beide adressiert).

    Liefert {ok, verletzungen: [{ereignis_id, datum, titel, fehlend}]}.
    """
    ereignisse = _gdb.list_verfahrensereignisse(db_path, projekt_name)
    verletzungen: list[dict[str, Any]] = []
    kommunikationen = 0
    for e in ereignisse:
        if e.get("ereignis_typ") != "parteikommunikation":
            continue
        kommunikationen += 1
        emp = [s.lower() for s in (e.get("empfaenger") or [])]
        hat_klaeger = any("kläger" in x or "klaeger" in x for x in emp)
        hat_beklagter = any("beklagt" in x for x in emp)
        fehlend: list[str] = []
        if not hat_klaeger:
            fehlend.append("Kläger")
        if not hat_beklagter:
            fehlend.append("Beklagter")
        if fehlend:
            verletzungen.append({
                "ereignis_id": e.get("id"),
                "datum": e.get("ereignis_datum"),
                "titel": e.get("titel"),
                "fehlend": fehlend,
                "empfaenger_ist": e.get("empfaenger"),
            })
    return {
        "ok": not verletzungen,
        "kommunikationen_anzahl": kommunikationen,
        "verletzungen": verletzungen,
    }


# ─────────────────────────────────────────────────────────
# G3-3 Non-liquet-Helper (Schema bereits in G1)
# ─────────────────────────────────────────────────────────

def mark_non_liquet_befund(db_path: Path, befund_id: int, grund: str) -> None:
    con = _sdb.connect(db_path)
    try:
        con.execute(
            "UPDATE gerichtsgutachten_befunde SET non_liquet=1, non_liquet_grund=? WHERE id=?",
            (grund, befund_id),
        )
        con.commit()
    finally:
        con.close()


def mark_non_liquet_beurteilung(db_path: Path, beurteilung_id: int, grund: str) -> None:
    con = _sdb.connect(db_path)
    try:
        con.execute(
            "UPDATE gerichtsgutachten_beurteilungen SET non_liquet=1, non_liquet_grund=? WHERE id=?",
            (grund, beurteilung_id),
        )
        con.commit()
    finally:
        con.close()


def list_non_liquet(db_path: Path, projekt_name: str) -> dict[str, list[dict[str, Any]]]:
    befunde = [b for b in _gdb.list_befunde(db_path, projekt_name) if b.get("non_liquet")]
    beurteilungen = [u for u in _gdb.list_beurteilungen(db_path, projekt_name) if u.get("non_liquet")]
    return {"befunde": befunde, "beurteilungen": beurteilungen,
            "anzahl_befunde": len(befunde), "anzahl_beurteilungen": len(beurteilungen)}


# ─────────────────────────────────────────────────────────
# G3-4 KI-Akzeptanz-Log (§ 407a)
# ─────────────────────────────────────────────────────────

DISCLAIMER_407A = (
    "⚠ KI-Vorschlag — finale Beurteilung erfolgt durch den Sachverständigen "
    "persönlich (§ 407a Abs. 2 ZPO)."
)


def log_ki_akzeptanz(
    db_path: Path,
    projekt_name: str,
    vorschlag_typ: str,
    vorschlag_text: str,
    akzeptiert_von: str,
    akzeptiert: bool = True,
) -> int:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_ki_akzeptanz
                 (projekt_name, vorschlag_typ, vorschlag_text, akzeptiert_von, akzeptiert)
               VALUES (?, ?, ?, ?, ?) RETURNING id""",
            (projekt_name, vorschlag_typ, vorschlag_text[:5000],
             akzeptiert_von, 1 if akzeptiert else 0),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def list_ki_akzeptanz(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            """SELECT * FROM gerichtsgutachten_ki_akzeptanz
               WHERE projekt_name=? ORDER BY akzeptiert_am DESC""",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
