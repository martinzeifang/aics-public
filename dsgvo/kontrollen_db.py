"""DS-K (#1129–#1131) — Jährlicher Datenschutz-Kontrollplan + Anhänge.

Self-contained, additiver DB-Layer (gemeinsame ``data/db/dsgvo.sqlite`` via
``dsgvo.db._connect``). Kontrollen werden geplant → **freigegeben** (GF/DSB) →
durchgeführt/dokumentiert (inkl. Datei-Anhängen) → abgeschlossen.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")
ATTACH_DIR = Path("data/dsgvo/kontroll_anhaenge")

STATUS = ("geplant", "freigegeben", "in_durchfuehrung", "abgeschlossen")
BEREICHE = ("VVT", "TOM", "DSFA", "Löschung", "Betroffenenrechte",
            "Transfer", "Einwilligung", "DSB", "Schulung", "Allgemein")
FREQUENZ = ("jaehrlich", "halbjaehrlich", "quartalsweise", "einmalig")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_kontrollen (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name    TEXT NOT NULL,
    kontroll_id     TEXT NOT NULL,
    titel           TEXT NOT NULL DEFAULT '',
    bereich         TEXT NOT NULL DEFAULT 'Allgemein',
    jahr            INTEGER NOT NULL DEFAULT 0,
    frequenz        TEXT NOT NULL DEFAULT 'jaehrlich',
    verantwortlich  TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'geplant',
    geplant_am      TEXT NOT NULL DEFAULT '',
    durchgefuehrt_am TEXT NOT NULL DEFAULT '',
    durchgefuehrt_von TEXT NOT NULL DEFAULT '',
    ergebnis        TEXT NOT NULL DEFAULT '',
    bezug_ref       TEXT NOT NULL DEFAULT '',
    freigabe_von    TEXT NOT NULL DEFAULT '',
    freigabe_am     TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(projekt_name, kontroll_id)
);
CREATE INDEX IF NOT EXISTS idx_kontrollen_projekt ON dsgvo_kontrollen(projekt_name);
CREATE INDEX IF NOT EXISTS idx_kontrollen_jahr ON dsgvo_kontrollen(projekt_name, jahr);

CREATE TABLE IF NOT EXISTS dsgvo_kontroll_anhaenge (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kontroll_pk   INTEGER NOT NULL,
    filename      TEXT NOT NULL,
    stored_path   TEXT NOT NULL,
    sha256        TEXT NOT NULL DEFAULT '',
    mime          TEXT NOT NULL DEFAULT '',
    size          INTEGER NOT NULL DEFAULT 0,
    uploaded_at   TEXT NOT NULL DEFAULT (datetime('now')),
    uploaded_by   TEXT NOT NULL DEFAULT '',
    deleted_at    TEXT,
    deleted_by    TEXT,
    deleted_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_kontroll_anhaenge_pk ON dsgvo_kontroll_anhaenge(kontroll_pk);
"""

# Standard-Jahreskontrollen (Seed-Vorschlag).
STANDARD_KONTROLLEN = [
    ("VVT-Review", "VVT", "Verzeichnis von Verarbeitungstätigkeiten auf Aktualität prüfen"),
    ("TOM-Wirksamkeit", "TOM", "Wirksamkeit der technisch-organisatorischen Maßnahmen prüfen (Art. 32(1)d)"),
    ("Loeschkonzept-Lauf", "Löschung", "Fristgerechte Löschungen prüfen/durchführen (DIN 66398)"),
    ("Betroffenenrechte-Fristen", "Betroffenenrechte", "Bearbeitung & Fristen der Betroffenenanträge prüfen"),
    ("DSFA-Review", "DSFA", "Bestehende DSFAs auf Aktualität prüfen (Art. 35(11))"),
    ("Transfer-TIA-Review", "Transfer", "Drittlandtransfers + TIA überprüfen (Schrems II)"),
    ("Einwilligungs-Nachweise", "Einwilligung", "Einwilligungs-Nachweise & Widerrufe prüfen (Art. 7)"),
    ("Mitarbeiterschulung", "Schulung", "Datenschutz-Sensibilisierung durchführen/auffrischen"),
    ("DSB-Taetigkeitsbericht", "DSB", "Tätigkeitsbericht der/des Datenschutzbeauftragten erstellen"),
]


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r else None


# ── Kontrollen ────────────────────────────────────────────────────────────────

def list_kontrollen(db_path: Path, projekt_name: str, *, jahr: int | None = None
                    ) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if jahr:
            rows = con.execute(
                "SELECT * FROM dsgvo_kontrollen WHERE projekt_name=? AND jahr=? "
                "ORDER BY bereich, kontroll_id", (projekt_name, int(jahr))).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM dsgvo_kontrollen WHERE projekt_name=? "
                "ORDER BY jahr DESC, bereich, kontroll_id", (projekt_name,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["anhaenge"] = _count_anhaenge(con, d["id"])
            out.append(d)
        return out
    finally:
        con.close()


def get_kontrolle(db_path: Path, pk: int) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        d = _row(con.execute("SELECT * FROM dsgvo_kontrollen WHERE id=?", (int(pk),)).fetchone())
        if d:
            d["anhaenge"] = list_anhaenge(db_path, int(pk))
        return d
    finally:
        con.close()


def save_kontrolle(db_path: Path, projekt_name: str, data: dict) -> int:
    """Upsert anhand (projekt_name, kontroll_id). Stammdaten gesperrt nach Freigabe
    bleibt Aufgabe des Blueprints; hier reiner Datenzugriff."""
    ensure_table(db_path)
    if not data.get("kontroll_id"):
        raise ValueError("'kontroll_id' ist Pflicht")
    con = _connect(Path(db_path))
    try:
        cols = ("kontroll_id", "titel", "bereich", "jahr", "frequenz",
                "verantwortlich", "geplant_am", "bezug_ref")
        vals = [data.get(c, "") for c in cols]
        vals[cols.index("jahr")] = int(data.get("jahr") or 0)
        existing = con.execute(
            "SELECT id FROM dsgvo_kontrollen WHERE projekt_name=? AND kontroll_id=?",
            (projekt_name, data["kontroll_id"])).fetchone()
        if existing:
            sets = ", ".join(f"{c}=?" for c in cols)
            con.execute(
                f"UPDATE dsgvo_kontrollen SET {sets}, updated_at=datetime('now') "
                f"WHERE projekt_name=? AND kontroll_id=?",
                vals + [projekt_name, data["kontroll_id"]])
            pk = int(existing["id"])
        else:
            ph = ",".join("?" for _ in cols)
            cur = con.execute(
                f"INSERT INTO dsgvo_kontrollen (projekt_name, {','.join(cols)}) "
                f"VALUES (?, {ph})", [projekt_name] + vals)
            pk = int(cur.lastrowid)
        con.commit()
        return pk
    finally:
        con.close()


def set_status(db_path: Path, pk: int, status: str, *, freigabe_von: str = "") -> None:
    ensure_table(db_path)
    if status not in STATUS:
        raise ValueError(f"Ungültiger Status: {status}")
    con = _connect(Path(db_path))
    try:
        if status == "freigegeben":
            con.execute(
                "UPDATE dsgvo_kontrollen SET status=?, freigabe_von=?, "
                "freigabe_am=datetime('now'), updated_at=datetime('now') WHERE id=?",
                (status, freigabe_von, int(pk)))
        else:
            con.execute(
                "UPDATE dsgvo_kontrollen SET status=?, updated_at=datetime('now') WHERE id=?",
                (status, int(pk)))
        con.commit()
    finally:
        con.close()


def dokumentieren(db_path: Path, pk: int, *, durchgefuehrt_am: str,
                  durchgefuehrt_von: str, ergebnis: str,
                  abschliessen: bool = False) -> None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        status_clause = ", status='abgeschlossen'" if abschliessen else \
            ", status=CASE WHEN status IN ('geplant','freigegeben') THEN 'in_durchfuehrung' ELSE status END"
        con.execute(
            f"UPDATE dsgvo_kontrollen SET durchgefuehrt_am=?, durchgefuehrt_von=?, "
            f"ergebnis=?{status_clause}, updated_at=datetime('now') WHERE id=?",
            (durchgefuehrt_am, durchgefuehrt_von, ergebnis, int(pk)))
        con.commit()
    finally:
        con.close()


def delete_kontrolle(db_path: Path, pk: int) -> None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        con.execute("DELETE FROM dsgvo_kontroll_anhaenge WHERE kontroll_pk=?", (int(pk),))
        con.execute("DELETE FROM dsgvo_kontrollen WHERE id=?", (int(pk),))
        con.commit()
    finally:
        con.close()


def seed_standard(db_path: Path, projekt_name: str, jahr: int) -> int:
    """Standard-Jahreskontrollen für ein Jahr anlegen (idempotent)."""
    ensure_table(db_path)
    inserted = 0
    for kid, bereich, titel in STANDARD_KONTROLLEN:
        cid = f"{kid}-{jahr}"
        existing = get_kontrolle_by_cid(db_path, projekt_name, cid)
        if existing:
            continue
        save_kontrolle(db_path, projekt_name, {
            "kontroll_id": cid, "titel": titel, "bereich": bereich,
            "jahr": jahr, "frequenz": "jaehrlich"})
        inserted += 1
    return inserted


def get_kontrolle_by_cid(db_path: Path, projekt_name: str, cid: str) -> dict | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        return _row(con.execute(
            "SELECT * FROM dsgvo_kontrollen WHERE projekt_name=? AND kontroll_id=?",
            (projekt_name, cid)).fetchone())
    finally:
        con.close()


# ── Anhänge ───────────────────────────────────────────────────────────────────

def _count_anhaenge(con: sqlite3.Connection, kontroll_pk: int) -> int:
    return int(con.execute(
        "SELECT COUNT(*) FROM dsgvo_kontroll_anhaenge WHERE kontroll_pk=? AND deleted_at IS NULL",
        (int(kontroll_pk),)).fetchone()[0])


def add_anhang(db_path: Path, kontroll_pk: int, *, filename: str, data: bytes,
               mime: str = "", uploaded_by: str = "") -> dict[str, Any]:
    ensure_table(db_path)
    ATTACH_DIR.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(data).hexdigest()
    safe_name = f"{kontroll_pk}_{sha[:12]}_{Path(filename).name}"
    dest = ATTACH_DIR / safe_name
    dest.write_bytes(data)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "INSERT INTO dsgvo_kontroll_anhaenge "
            "(kontroll_pk, filename, stored_path, sha256, mime, size, uploaded_by) "
            "VALUES (?,?,?,?,?,?,?)",
            (int(kontroll_pk), Path(filename).name, str(dest), sha, mime, len(data), uploaded_by))
        con.commit()
        return list_anhaenge(db_path, int(kontroll_pk), _only_id=int(cur.lastrowid))
    finally:
        con.close()


def list_anhaenge(db_path: Path, kontroll_pk: int, *, _only_id: int | None = None
                  ) -> Any:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT id, kontroll_pk, filename, sha256, mime, size, uploaded_at, uploaded_by "
            "FROM dsgvo_kontroll_anhaenge WHERE kontroll_pk=? AND deleted_at IS NULL "
            "ORDER BY uploaded_at DESC", (int(kontroll_pk),)).fetchall()
        items = [dict(r) for r in rows]
        if _only_id is not None:
            return next((i for i in items if i["id"] == _only_id), items[0] if items else None)
        return items
    finally:
        con.close()


def get_anhang(db_path: Path, anhang_id: int) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        return _row(con.execute(
            "SELECT * FROM dsgvo_kontroll_anhaenge WHERE id=? AND deleted_at IS NULL",
            (int(anhang_id),)).fetchone())
    finally:
        con.close()


def soft_delete_anhang(db_path: Path, anhang_id: int, *, by: str, reason: str) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        row = con.execute(
            "SELECT stored_path FROM dsgvo_kontroll_anhaenge WHERE id=? AND deleted_at IS NULL",
            (int(anhang_id),)).fetchone()
        if not row:
            return False
        con.execute(
            "UPDATE dsgvo_kontroll_anhaenge SET deleted_at=datetime('now'), "
            "deleted_by=?, deleted_reason=? WHERE id=?", (by, reason, int(anhang_id)))
        con.commit()
        try:
            Path(row["stored_path"]).unlink(missing_ok=True)
        except OSError:
            pass
        return True
    finally:
        con.close()
