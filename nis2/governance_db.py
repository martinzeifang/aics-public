"""N-GOV (#1212) — NIS2 Art. 20 Governance-Nachweis-Register.

Self-contained, additiver DB-Layer auf ``data/db/nis2.sqlite`` (via
``nis2.db._connect``). Harte Nachweispflichten der Leitungsorgane (Art. 20):

- **Billigungsbeschluss** der RM-Maßnahmen (Geschäftsleitung)
- **Management-Review** (Überwachungs-/Reporting-Protokolle)
- **Schulungsnachweis** (Pflicht-Schulung der Leitungsorgane + Mitarbeiter)

Je Nachweis (``nis2_governance_nachweis``) Datum, Gremium/Teilnehmer, Gegenstand
(RM-Maßnahmen-Version), Dokument-Referenz, ``naechster_review`` (Wiedervorlage)
und für Schulungen eine **Teilnehmerliste** (``nis2_governance_teilnehmer``,
Status absolviert/offen, optionale Verknüpfung zum N16-Cyberhygiene-Quiz-Ergebnis).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from nis2.db import _connect

DB_PATH = Path("data/db/nis2.sqlite")

NACHWEIS_TYPEN = ("billigungsbeschluss", "management_review", "schulung")
TEILNEHMER_STATUS = ("offen", "absolviert")

SCHEMA = """
CREATE TABLE IF NOT EXISTS nis2_governance_nachweis (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name    TEXT NOT NULL,
    typ             TEXT NOT NULL DEFAULT 'billigungsbeschluss',
    datum           TEXT NOT NULL DEFAULT '',
    gremium         TEXT NOT NULL DEFAULT '',
    gegenstand      TEXT NOT NULL DEFAULT '',
    rm_version      TEXT NOT NULL DEFAULT '',
    dokument_url    TEXT NOT NULL DEFAULT '',
    naechster_review TEXT NOT NULL DEFAULT '',
    quiz_referenz   TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_nis2_gov_nachweis_projekt
    ON nis2_governance_nachweis(projekt_name);

CREATE TABLE IF NOT EXISTS nis2_governance_teilnehmer (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nachweis_id     INTEGER NOT NULL,
    name            TEXT NOT NULL DEFAULT '',
    rolle           TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'offen',
    quiz_score      TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_nis2_gov_teilnehmer_nachweis
    ON nis2_governance_teilnehmer(nachweis_id);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r else None


def _list_teilnehmer(con: sqlite3.Connection, nachweis_id: int) -> list[dict[str, Any]]:
    rows = con.execute(
        "SELECT * FROM nis2_governance_teilnehmer WHERE nachweis_id=? ORDER BY id",
        (int(nachweis_id),)).fetchall()
    return [dict(r) for r in rows]


# ── Nachweise ─────────────────────────────────────────────────────────────────

def list_nachweise(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM nis2_governance_nachweis WHERE projekt_name=? "
            "ORDER BY datum DESC, id DESC", (projekt_name,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["teilnehmer"] = _list_teilnehmer(con, d["id"])
            out.append(d)
        return out
    finally:
        con.close()


def get_nachweis(db_path: Path, projekt_name: str, pk: int) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        d = _row(con.execute(
            "SELECT * FROM nis2_governance_nachweis WHERE id=? AND projekt_name=?",
            (int(pk), projekt_name)).fetchone())
        if d:
            d["teilnehmer"] = _list_teilnehmer(con, d["id"])
        return d
    finally:
        con.close()


def save_nachweis(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_table(db_path)
    typ = data.get("typ", "billigungsbeschluss")
    if typ not in NACHWEIS_TYPEN:
        raise ValueError(f"'typ' muss eines von {NACHWEIS_TYPEN} sein")
    con = _connect(Path(db_path))
    try:
        pk = data.get("id")
        if pk:
            row = con.execute(
                "SELECT id FROM nis2_governance_nachweis WHERE id=? AND projekt_name=?",
                (int(pk), projekt_name)).fetchone()
            if not row:
                raise ValueError("Nachweis nicht gefunden")
            con.execute(
                """UPDATE nis2_governance_nachweis SET typ=?, datum=?, gremium=?,
                     gegenstand=?, rm_version=?, dokument_url=?, naechster_review=?,
                     quiz_referenz=?, notizen=?, updated_at=datetime('now')
                   WHERE id=? AND projekt_name=?""",
                (typ, data.get("datum", ""), data.get("gremium", ""),
                 data.get("gegenstand", ""), data.get("rm_version", ""),
                 data.get("dokument_url", ""), data.get("naechster_review", ""),
                 data.get("quiz_referenz", ""), data.get("notizen", ""),
                 int(pk), projekt_name))
            con.commit()
            return int(pk)
        cur = con.execute(
            """INSERT INTO nis2_governance_nachweis
                 (projekt_name, typ, datum, gremium, gegenstand, rm_version,
                  dokument_url, naechster_review, quiz_referenz, notizen)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (projekt_name, typ, data.get("datum", ""), data.get("gremium", ""),
             data.get("gegenstand", ""), data.get("rm_version", ""),
             data.get("dokument_url", ""), data.get("naechster_review", ""),
             data.get("quiz_referenz", ""), data.get("notizen", "")))
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def delete_nachweis(db_path: Path, projekt_name: str, pk: int) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        row = con.execute(
            "SELECT id FROM nis2_governance_nachweis WHERE id=? AND projekt_name=?",
            (int(pk), projekt_name)).fetchone()
        if not row:
            return False
        con.execute("DELETE FROM nis2_governance_teilnehmer WHERE nachweis_id=?", (int(pk),))
        con.execute("DELETE FROM nis2_governance_nachweis WHERE id=?", (int(pk),))
        con.commit()
        return True
    finally:
        con.close()


# ── Teilnehmer (Schulung) ─────────────────────────────────────────────────────

def save_teilnehmer(db_path: Path, nachweis_id: int, data: dict) -> int:
    ensure_table(db_path)
    status = data.get("status", "offen")
    if status not in TEILNEHMER_STATUS:
        status = "offen"
    con = _connect(Path(db_path))
    try:
        tid = data.get("id")
        if tid:
            con.execute(
                """UPDATE nis2_governance_teilnehmer SET name=?, rolle=?, status=?,
                     quiz_score=?, updated_at=datetime('now')
                   WHERE id=? AND nachweis_id=?""",
                (data.get("name", ""), data.get("rolle", ""), status,
                 data.get("quiz_score", ""), int(tid), int(nachweis_id)))
            con.commit()
            return int(tid)
        cur = con.execute(
            """INSERT INTO nis2_governance_teilnehmer
                 (nachweis_id, name, rolle, status, quiz_score)
               VALUES (?,?,?,?,?)""",
            (int(nachweis_id), data.get("name", ""), data.get("rolle", ""),
             status, data.get("quiz_score", "")))
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def delete_teilnehmer(db_path: Path, nachweis_id: int, teilnehmer_id: int) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        row = con.execute(
            "SELECT id FROM nis2_governance_teilnehmer WHERE id=? AND nachweis_id=?",
            (int(teilnehmer_id), int(nachweis_id))).fetchone()
        if not row:
            return False
        con.execute("DELETE FROM nis2_governance_teilnehmer WHERE id=?",
                    (int(teilnehmer_id),))
        con.commit()
        return True
    finally:
        con.close()
