"""N-AUD (#1204) — NIS2 Art. 32 Audit-/Konformitätsbewertungs-Register + CAPA.

Self-contained, additiver DB-Layer auf ``data/db/nis2.sqlite`` (via
``nis2.db._connect``). Modelliert je Projekt mehrere Audits (``nis2_audit``,
3-Jahres-Zyklus) mit verknüpften Findings/CAPA (``nis2_audit_finding``):

- Art. 32: KRITIS/wesentliche Einrichtungen weisen die Umsetzung im 3-Jahres-
  Zyklus durch Audits/Prüfungen/Zertifizierungen nach.
- Findings dienen zugleich als CAPA-Register (Art. 21 Abs. 4): Maßnahme,
  Verantwortlicher, Frist, Status; optionale Verknüpfung zu Anforderung/Risiko.

Die 3-Jahres-Wiedervorlage (``naechster_audit_soll``) wird über
``shared.deadlines.add_months_iso`` (36 Monate) aus ``durchgefuehrt_am``
abgeleitet, sofern nicht manuell gesetzt.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from nis2.db import _connect

DB_PATH = Path("data/db/nis2.sqlite")

AUDIT_TYPEN = ("intern", "extern", "zertifizierung", "behoerdlich")
AUDIT_ERGEBNIS = ("offen", "bestanden", "bestanden_mit_auflagen", "nicht_bestanden")
FINDING_SCHWEREGRADE = ("niedrig", "mittel", "hoch", "kritisch")
FINDING_STATUS = ("offen", "in_bearbeitung", "behoben", "akzeptiert")
# CAPA-Verknüpfungsziele.
FINDING_OBJEKT = ("", "anforderung", "risiko")

AUDIT_ZYKLUS_MONATE = 36  # 3-Jahres-Zyklus Art. 32.

SCHEMA = """
CREATE TABLE IF NOT EXISTS nis2_audit (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name        TEXT NOT NULL,
    titel               TEXT NOT NULL DEFAULT '',
    audit_typ           TEXT NOT NULL DEFAULT 'intern',
    scope               TEXT NOT NULL DEFAULT '',
    pruefer             TEXT NOT NULL DEFAULT '',
    durchgefuehrt_am    TEXT NOT NULL DEFAULT '',
    naechster_audit_soll TEXT NOT NULL DEFAULT '',
    zertifikat_url      TEXT NOT NULL DEFAULT '',
    zertifikat_ablauf   TEXT NOT NULL DEFAULT '',
    ergebnis            TEXT NOT NULL DEFAULT 'offen',
    notizen             TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_nis2_audit_projekt ON nis2_audit(projekt_name);

CREATE TABLE IF NOT EXISTS nis2_audit_finding (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id        INTEGER NOT NULL,
    projekt_name    TEXT NOT NULL,
    beschreibung    TEXT NOT NULL DEFAULT '',
    schweregrad     TEXT NOT NULL DEFAULT 'mittel',
    massnahme       TEXT NOT NULL DEFAULT '',
    verantwortlich  TEXT NOT NULL DEFAULT '',
    frist           TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'offen',
    objekt_typ      TEXT NOT NULL DEFAULT '',
    objekt_ref      TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_nis2_audit_finding_audit
    ON nis2_audit_finding(audit_id);
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


def _derive_naechster_soll(durchgefuehrt_am: str, manual: str) -> str:
    """3-Jahres-Wiedervorlage: 36 Monate ab Durchführung (sofern nicht manuell)."""
    if manual and manual.strip():
        return manual.strip()
    if durchgefuehrt_am and durchgefuehrt_am.strip():
        from shared import deadlines as dl
        return dl.add_months_iso(durchgefuehrt_am.strip(), AUDIT_ZYKLUS_MONATE)
    return ""


# ── Audits ──────────────────────────────────────────────────────────────────

def _list_findings(con: sqlite3.Connection, audit_id: int) -> list[dict[str, Any]]:
    rows = con.execute(
        "SELECT * FROM nis2_audit_finding WHERE audit_id=? ORDER BY id",
        (int(audit_id),)).fetchall()
    return [dict(r) for r in rows]


def list_audits(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM nis2_audit WHERE projekt_name=? "
            "ORDER BY durchgefuehrt_am DESC, id DESC", (projekt_name,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["findings"] = _list_findings(con, d["id"])
            out.append(d)
        return out
    finally:
        con.close()


def get_audit(db_path: Path, projekt_name: str, pk: int) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        d = _row(con.execute(
            "SELECT * FROM nis2_audit WHERE id=? AND projekt_name=?",
            (int(pk), projekt_name)).fetchone())
        if d:
            d["findings"] = _list_findings(con, d["id"])
        return d
    finally:
        con.close()


def save_audit(db_path: Path, projekt_name: str, data: dict) -> int:
    """Insert/Update eines Audits (Update bei mitgegebenem ``id``)."""
    ensure_table(db_path)
    typ = data.get("audit_typ", "intern")
    if typ not in AUDIT_TYPEN:
        typ = "intern"
    ergebnis = data.get("ergebnis", "offen")
    if ergebnis not in AUDIT_ERGEBNIS:
        ergebnis = "offen"
    durchgefuehrt = str(data.get("durchgefuehrt_am", "") or "")
    naechster = _derive_naechster_soll(
        durchgefuehrt, str(data.get("naechster_audit_soll", "") or ""))
    con = _connect(Path(db_path))
    try:
        pk = data.get("id")
        if pk:
            row = con.execute(
                "SELECT id FROM nis2_audit WHERE id=? AND projekt_name=?",
                (int(pk), projekt_name)).fetchone()
            if not row:
                raise ValueError("Audit nicht gefunden")
            con.execute(
                """UPDATE nis2_audit SET titel=?, audit_typ=?, scope=?, pruefer=?,
                     durchgefuehrt_am=?, naechster_audit_soll=?, zertifikat_url=?,
                     zertifikat_ablauf=?, ergebnis=?, notizen=?,
                     updated_at=datetime('now')
                   WHERE id=? AND projekt_name=?""",
                (data.get("titel", ""), typ, data.get("scope", ""),
                 data.get("pruefer", ""), durchgefuehrt, naechster,
                 data.get("zertifikat_url", ""), data.get("zertifikat_ablauf", ""),
                 ergebnis, data.get("notizen", ""), int(pk), projekt_name))
            con.commit()
            return int(pk)
        cur = con.execute(
            """INSERT INTO nis2_audit
                 (projekt_name, titel, audit_typ, scope, pruefer, durchgefuehrt_am,
                  naechster_audit_soll, zertifikat_url, zertifikat_ablauf,
                  ergebnis, notizen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (projekt_name, data.get("titel", ""), typ, data.get("scope", ""),
             data.get("pruefer", ""), durchgefuehrt, naechster,
             data.get("zertifikat_url", ""), data.get("zertifikat_ablauf", ""),
             ergebnis, data.get("notizen", "")))
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def delete_audit(db_path: Path, projekt_name: str, pk: int) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        row = con.execute(
            "SELECT id FROM nis2_audit WHERE id=? AND projekt_name=?",
            (int(pk), projekt_name)).fetchone()
        if not row:
            return False
        con.execute("DELETE FROM nis2_audit_finding WHERE audit_id=?", (int(pk),))
        con.execute("DELETE FROM nis2_audit WHERE id=?", (int(pk),))
        con.commit()
        return True
    finally:
        con.close()


# ── Findings (CAPA) ──────────────────────────────────────────────────────────

def save_finding(db_path: Path, projekt_name: str, audit_id: int, data: dict) -> int:
    ensure_table(db_path)
    schwere = data.get("schweregrad", "mittel")
    if schwere not in FINDING_SCHWEREGRADE:
        schwere = "mittel"
    status = data.get("status", "offen")
    if status not in FINDING_STATUS:
        status = "offen"
    objekt_typ = data.get("objekt_typ", "")
    if objekt_typ not in FINDING_OBJEKT:
        objekt_typ = ""
    con = _connect(Path(db_path))
    try:
        fid = data.get("id")
        if fid:
            row = con.execute(
                "SELECT id FROM nis2_audit_finding WHERE id=? AND audit_id=? "
                "AND projekt_name=?", (int(fid), int(audit_id), projekt_name)
            ).fetchone()
            if not row:
                raise ValueError("Finding nicht gefunden")
            con.execute(
                """UPDATE nis2_audit_finding SET beschreibung=?, schweregrad=?,
                     massnahme=?, verantwortlich=?, frist=?, status=?,
                     objekt_typ=?, objekt_ref=?, updated_at=datetime('now')
                   WHERE id=?""",
                (data.get("beschreibung", ""), schwere, data.get("massnahme", ""),
                 data.get("verantwortlich", ""), data.get("frist", ""), status,
                 objekt_typ, data.get("objekt_ref", ""), int(fid)))
            con.commit()
            return int(fid)
        cur = con.execute(
            """INSERT INTO nis2_audit_finding
                 (audit_id, projekt_name, beschreibung, schweregrad, massnahme,
                  verantwortlich, frist, status, objekt_typ, objekt_ref)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (int(audit_id), projekt_name, data.get("beschreibung", ""), schwere,
             data.get("massnahme", ""), data.get("verantwortlich", ""),
             data.get("frist", ""), status, objekt_typ, data.get("objekt_ref", "")))
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def delete_finding(db_path: Path, projekt_name: str, audit_id: int,
                   finding_id: int) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        row = con.execute(
            "SELECT id FROM nis2_audit_finding WHERE id=? AND audit_id=? "
            "AND projekt_name=?",
            (int(finding_id), int(audit_id), projekt_name)).fetchone()
        if not row:
            return False
        con.execute("DELETE FROM nis2_audit_finding WHERE id=?", (int(finding_id),))
        con.commit()
        return True
    finally:
        con.close()
