"""DS-LIA (#1205) — LIA-Register (Legitimate Interest Assessment, Art. 6(1)(f)).

Eigenständiges DSMS-Vertikal: Tabelle ``dsgvo_lia`` in der geteilten
``data/db/dsgvo.sqlite`` (``dsgvo.db._connect``). Geführter Drei-Stufen-Test je
Verarbeitung (verknüpft mit einem VVT-Eintrag):

1. Zweck-/Legitimitäts-Test (purpose test): Gibt es ein berechtigtes Interesse?
2. Erforderlichkeit (necessity test): Mildere Mittel geprüft?
3. Abwägung (balancing test): Interessen/Grundrechte der Betroffenen, vernünftige
   Erwartung, Garantien/Opt-out.

Ergebnis: ``ueberwiegt`` (Interesse überwiegt → tragfähig) / ``ueberwiegt_nicht``
(neue Rechtsgrundlage nötig) + Reviewer/Datum + Review-Zyklus.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")

STAGE = ("zweck", "erforderlichkeit", "abwaegung", "ergebnis")
ERGEBNIS = ("offen", "ueberwiegt", "ueberwiegt_nicht")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_lia (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name         TEXT NOT NULL,
    lia_id               TEXT NOT NULL,
    vvt_ref              TEXT NOT NULL DEFAULT '',
    verarbeitung         TEXT NOT NULL DEFAULT '',
    stage                TEXT NOT NULL DEFAULT 'zweck',
    -- 1) Zweck-/Legitimitäts-Test
    zweck                TEXT NOT NULL DEFAULT '',
    berechtigtes_interesse TEXT NOT NULL DEFAULT '',
    legitim              INTEGER NOT NULL DEFAULT 0,
    -- 2) Erforderlichkeit
    erforderlichkeit     TEXT NOT NULL DEFAULT '',
    mildere_mittel_geprueft INTEGER NOT NULL DEFAULT 0,
    mildere_mittel_ergebnis TEXT NOT NULL DEFAULT '',
    -- 3) Abwägung
    interessen_betroffener TEXT NOT NULL DEFAULT '',
    vernuenftige_erwartung TEXT NOT NULL DEFAULT '',
    garantien_optout     TEXT NOT NULL DEFAULT '',
    -- Ergebnis + Review
    ergebnis             TEXT NOT NULL DEFAULT 'offen',
    ergebnis_begruendung TEXT NOT NULL DEFAULT '',
    reviewer             TEXT NOT NULL DEFAULT '',
    review_datum         TEXT NOT NULL DEFAULT '',
    review_zyklus_monate INTEGER NOT NULL DEFAULT 12,
    naechstes_review     TEXT NOT NULL DEFAULT '',
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(projekt_name, lia_id)
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_lia_projekt ON dsgvo_lia(projekt_name);
"""

# Felder, die per Upsert gesetzt werden dürfen (kein projekt_name/lia_id/Timestamps).
_ALLOWED = (
    "vvt_ref", "verarbeitung", "stage", "zweck", "berechtigtes_interesse",
    "legitim", "erforderlichkeit", "mildere_mittel_geprueft",
    "mildere_mittel_ergebnis", "interessen_betroffener", "vernuenftige_erwartung",
    "garantien_optout", "ergebnis", "ergebnis_begruendung", "reviewer",
    "review_datum", "review_zyklus_monate",
)
_BOOL = ("legitim", "mildere_mittel_geprueft")
_INT = ("review_zyklus_monate",)


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _add_months(d: date, months: int) -> date:
    mi = d.month - 1 + months
    year = d.year + mi // 12
    month = mi % 12 + 1
    last = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(d.day, last[month - 1]))


def _parse(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _compute_review(review_datum: str, zyklus: int) -> str:
    d = _parse(review_datum)
    if d is None or not zyklus:
        return ""
    return _add_months(d, int(zyklus)).isoformat()


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    for b in _BOOL:
        d[b] = int(d.get(b) or 0)
    return d


# ── CRUD ─────────────────────────────────────────────────────────────────────

def list_lia(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM dsgvo_lia WHERE projekt_name=? ORDER BY lia_id",
            (projekt_name,)).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()


def get_lia(db_path: Path, pk: int, projekt_name: str | None = None) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if projekt_name is not None:
            r = con.execute("SELECT * FROM dsgvo_lia WHERE id=? AND projekt_name=?",
                            (int(pk), projekt_name)).fetchone()
        else:
            r = con.execute("SELECT * FROM dsgvo_lia WHERE id=?", (int(pk),)).fetchone()
        return _row(r) if r is not None else None
    finally:
        con.close()


def save_lia(db_path: Path, projekt_name: str, data: dict) -> int:
    """Upsert anhand (projekt_name, lia_id)."""
    ensure_table(db_path)
    lia_id = data.get("lia_id")
    if not lia_id:
        raise ValueError("'lia_id' ist Pflicht")
    if data.get("ergebnis") and data["ergebnis"] not in ERGEBNIS:
        raise ValueError(f"Ungültiges Ergebnis: {data['ergebnis']}")
    if data.get("stage") and data["stage"] not in STAGE:
        raise ValueError(f"Ungültige Stufe: {data['stage']}")

    values = {k: data.get(k) for k in _ALLOWED if k in data}
    for b in _BOOL:
        if b in values:
            values[b] = int(bool(values[b]))
    for i in _INT:
        if i in values:
            values[i] = int(values[i] or 0)
    # naechstes_review aus review_datum + zyklus ableiten.
    if "review_datum" in values or "review_zyklus_monate" in values:
        rd = values.get("review_datum", data.get("review_datum", ""))
        zk = values.get("review_zyklus_monate", data.get("review_zyklus_monate", 12))
        values["naechstes_review"] = _compute_review(rd, zk)

    con = _connect(Path(db_path))
    try:
        existing = con.execute(
            "SELECT id FROM dsgvo_lia WHERE projekt_name=? AND lia_id=?",
            (projekt_name, lia_id)).fetchone()
        if existing:
            if values:
                sets = ", ".join(f"{k}=?" for k in values)
                con.execute(
                    f"UPDATE dsgvo_lia SET {sets}, updated_at=datetime('now') WHERE id=?",
                    list(values.values()) + [int(existing["id"])])
            pk = int(existing["id"])
        else:
            cols = ["lia_id"] + list(values.keys())
            vals = [lia_id] + list(values.values())
            ph = ",".join("?" for _ in cols)
            cur = con.execute(
                f"INSERT INTO dsgvo_lia (projekt_name, {','.join(cols)}) VALUES (?, {ph})",
                [projekt_name] + vals)
            pk = int(cur.lastrowid)
        con.commit()
        return pk
    finally:
        con.close()


def delete_lia(db_path: Path, pk: int, projekt_name: str | None = None) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if projekt_name is not None:
            cur = con.execute("DELETE FROM dsgvo_lia WHERE id=? AND projekt_name=?",
                              (int(pk), projekt_name))
        else:
            cur = con.execute("DELETE FROM dsgvo_lia WHERE id=?", (int(pk),))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def ensure_for_vvt(db_path: Path, projekt_name: str, *, vvt_ref: str,
                   verarbeitung: str = "", zweck: str = "") -> int:
    """Auto-Trigger (#1205): legt — falls noch keine LIA für diesen VVT-Eintrag
    existiert — eine offene LIA an. Idempotent über (projekt, lia_id)."""
    ensure_table(db_path)
    lia_id = f"LIA-{vvt_ref}" if vvt_ref else "LIA-AUTO"
    for row in list_lia(db_path, projekt_name):
        if row.get("vvt_ref") == vvt_ref and vvt_ref:
            return int(row["id"])
    return save_lia(db_path, projekt_name, {
        "lia_id": lia_id, "vvt_ref": vvt_ref, "verarbeitung": verarbeitung,
        "zweck": zweck, "stage": "zweck", "ergebnis": "offen",
    })
