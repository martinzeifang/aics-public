"""CRA Art. 19-22 — Wirtschaftsakteure-Register (#1200).

Register weiterer Wirtschaftsakteure (Importeur/Händler/Bevollmächtigter) je
Projekt mit rollen-spezifischer Pflicht-Checkliste:

- Importeur (Art. 19): CE/DoC/Annex-II vorhanden, eigene Kontaktdaten angebracht,
  DoC 10 Jahre vorhalten.
- Händler (Art. 20): CE + Annex-II-Sorgfaltsprüfung.
- Bevollmächtigter (Art. 17/22): schriftliches Mandat, Aufgabenumfang.

Tabelle ``cra_akteure`` (projekt-scoped). Mandats-/Nachweis-Referenz + Status.
Reines ``sqlite3``, kein ORM. ``ensure_table`` idempotent.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path("data/db/cra.sqlite")

# Rollen weiterer Wirtschaftsakteure (Single Source of Truth fürs Frontend).
ROLLEN = ("importeur", "haendler", "bevollmaechtigter")

# Status je Akteur.
STATUS = ("offen", "in_pruefung", "konform", "nicht_konform")

# Rollen-spezifische Pflicht-Checkliste (Soll-Nachweise je Rolle).
CHECKLISTE: dict[str, list[str]] = {
    "importeur": [
        "ce_kennzeichnung_geprueft",
        "doc_vorhanden_geprueft",
        "annex_ii_informationen_geprueft",
        "eigene_kontaktdaten_angebracht",
        "doc_aufbewahrung_10_jahre",
    ],
    "haendler": [
        "ce_kennzeichnung_geprueft",
        "annex_ii_sorgfaltspruefung",
        "lager_transport_bedingungen_geprueft",
    ],
    "bevollmaechtigter": [
        "schriftliches_mandat_vorhanden",
        "aufgabenumfang_festgelegt",
        "doc_technische_doku_vorhalten",
    ],
}


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_akteure (
                id              INTEGER PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                rolle           TEXT NOT NULL DEFAULT 'importeur',
                name            TEXT NOT NULL DEFAULT '',
                anschrift       TEXT NOT NULL DEFAULT '',
                kontakt         TEXT NOT NULL DEFAULT '',
                produkt         TEXT NOT NULL DEFAULT '',
                checkliste_json TEXT NOT NULL DEFAULT '{}',   -- {nachweis: bool}
                mandat_ref      TEXT NOT NULL DEFAULT '',      -- Mandats-/Nachweis-Upload-Referenz
                aufgabenumfang  TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'offen',
                notizen         TEXT NOT NULL DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_cra_akteure_projekt
                ON cra_akteure(projekt_name);
            """
        )
        con.commit()
    finally:
        con.close()


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    try:
        d["checkliste"] = json.loads(d.get("checkliste_json") or "{}")
    except Exception:
        d["checkliste"] = {}
    rolle = d.get("rolle", "importeur")
    d["soll_nachweise"] = CHECKLISTE.get(rolle, [])
    # Vollständigkeit der Pflicht-Checkliste (alle Soll-Nachweise = True).
    soll = CHECKLISTE.get(rolle, [])
    d["checkliste_vollstaendig"] = bool(soll) and all(
        d["checkliste"].get(n) for n in soll
    )
    return d


def list_akteure(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_akteure WHERE projekt_name=? ORDER BY rolle, name, id",
            (projekt_name,),
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()


def get_akteur(db_path: Path, akteur_id: int,
               projekt_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    """IDOR-sicher: optional auf projekt_name scopen."""
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        if projekt_name is not None:
            r = con.execute(
                "SELECT * FROM cra_akteure WHERE id=? AND projekt_name=?",
                (akteur_id, projekt_name),
            ).fetchone()
        else:
            r = con.execute(
                "SELECT * FROM cra_akteure WHERE id=?", (akteur_id,)
            ).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def create_akteur(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_table(db_path)
    rolle = data.get("rolle") or "importeur"
    if rolle not in ROLLEN:
        raise ValueError(f"Ungültige Rolle: {rolle}")
    status = data.get("status") or "offen"
    if status not in STATUS:
        raise ValueError(f"Ungültiger Status: {status}")
    con = _connect(db_path)
    try:
        cur = con.execute(
            """
            INSERT INTO cra_akteure
                (projekt_name, rolle, name, anschrift, kontakt, produkt,
                 checkliste_json, mandat_ref, aufgabenumfang, status, notizen,
                 updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (projekt_name, rolle, data.get("name", ""), data.get("anschrift", ""),
             data.get("kontakt", ""), data.get("produkt", ""),
             json.dumps(data.get("checkliste") or {}, ensure_ascii=False),
             data.get("mandat_ref", ""), data.get("aufgabenumfang", ""),
             status, data.get("notizen", "")),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def update_akteur(db_path: Path, akteur_id: int, projekt_name: str,
                  data: dict) -> Optional[dict[str, Any]]:
    ensure_table(db_path)
    if "rolle" in data and data["rolle"] not in ROLLEN:
        raise ValueError(f"Ungültige Rolle: {data['rolle']}")
    if "status" in data and data["status"] not in STATUS:
        raise ValueError(f"Ungültiger Status: {data['status']}")
    sets, vals = [], []
    for f in ("rolle", "name", "anschrift", "kontakt", "produkt",
              "mandat_ref", "aufgabenumfang", "status", "notizen"):
        if f in data:
            sets.append(f"{f}=?")
            vals.append(data[f])
    if "checkliste" in data:
        sets.append("checkliste_json=?")
        vals.append(json.dumps(data.get("checkliste") or {}, ensure_ascii=False))
    if not sets:
        return get_akteur(db_path, akteur_id, projekt_name)
    vals += [akteur_id, projekt_name]
    con = _connect(db_path)
    try:
        cur = con.execute(
            f"UPDATE cra_akteure SET {', '.join(sets)}, updated_at=datetime('now') "
            "WHERE id=? AND projekt_name=?",
            vals,
        )
        con.commit()
        if cur.rowcount == 0:
            return None
    finally:
        con.close()
    return get_akteur(db_path, akteur_id, projekt_name)


def delete_akteur(db_path: Path, akteur_id: int, projekt_name: str) -> bool:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            "DELETE FROM cra_akteure WHERE id=? AND projekt_name=?",
            (akteur_id, projekt_name),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()
