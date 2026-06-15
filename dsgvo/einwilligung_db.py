"""DS11 (#1111) — Einwilligungs-Management (Art. 7 DSGVO).

Self-contained, additive Daten-Layer (kein Eingriff in das zentrale
``dsgvo/db.py``-SCHEMA). Tabelle ``dsgvo_einwilligung`` deckt die
Nachweisbarkeit der Einwilligung (Art. 7 Abs. 1) sowie deren jederzeitigen
Widerruf (Art. 7 Abs. 3) inkl. Text-Versionierung ab.

Verbindung wird über ``dsgvo.db._connect`` wiederverwendet
(``con.row_factory = Row`` ist bereits gesetzt). ``ensure_table`` ist idempotent
und wird am Anfang jeder Lese-/Schreiboperation aufgerufen — analog zu
``shared/templates/db.py``.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")

# Erlaubte Status-Werte (Lebenszyklus einer Einwilligung)
STATUS_WERTE = ("aktiv", "widerrufen", "abgelaufen")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_einwilligung (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name        TEXT NOT NULL,
    einwilligung_id     TEXT NOT NULL,
    zweck               TEXT NOT NULL DEFAULT '',
    text_version        TEXT NOT NULL DEFAULT '1',
    einwilligung_text   TEXT NOT NULL DEFAULT '',
    zeitpunkt           TEXT NOT NULL DEFAULT '',
    kanal               TEXT NOT NULL DEFAULT '',
    betroffener_quelle  TEXT NOT NULL DEFAULT '',
    widerruf_zeitpunkt  TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'aktiv',
    created_at          TEXT NOT NULL DEFAULT (aics_now()),
    updated_at          TEXT NOT NULL DEFAULT (aics_now()),
    UNIQUE(projekt_name, einwilligung_id)
);
CREATE INDEX IF NOT EXISTS idx_einwilligung_projekt
    ON dsgvo_einwilligung(projekt_name);
CREATE INDEX IF NOT EXISTS idx_einwilligung_status
    ON dsgvo_einwilligung(projekt_name, status);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    """Legt Tabelle + Indizes an (idempotent)."""
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row_to_dict(r: Any) -> dict[str, Any] | None:
    return dict(r) if r is not None else None


# ============================================================
# CRUD
# ============================================================

def list_einwilligungen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM dsgvo_einwilligung WHERE projekt_name=? "
            "ORDER BY zeitpunkt DESC, id DESC",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_einwilligung(
    db_path: Path, projekt_name: str, einwilligung_id: str
) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        row = con.execute(
            "SELECT * FROM dsgvo_einwilligung "
            "WHERE projekt_name=? AND einwilligung_id=?",
            (projekt_name, einwilligung_id),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        con.close()


def save_einwilligung(
    db_path: Path,
    *,
    projekt_name: str,
    einwilligung_id: str,
    zweck: str = "",
    text_version: str = "1",
    einwilligung_text: str = "",
    zeitpunkt: str = "",
    kanal: str = "",
    betroffener_quelle: str = "",
    widerruf_zeitpunkt: str = "",
    status: str = "aktiv",
) -> dict[str, Any]:
    """Upsert per (projekt_name, einwilligung_id) — Nachweisbarkeit Art. 7(1)."""
    ensure_table(db_path)
    if status not in STATUS_WERTE:
        status = "aktiv"
    con = _connect(Path(db_path))
    try:
        con.execute(
            """
            INSERT INTO dsgvo_einwilligung (
                projekt_name, einwilligung_id, zweck, text_version,
                einwilligung_text, zeitpunkt, kanal, betroffener_quelle,
                widerruf_zeitpunkt, status, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?, aics_now())
            ON CONFLICT(projekt_name, einwilligung_id) DO UPDATE SET
                zweck=excluded.zweck,
                text_version=excluded.text_version,
                einwilligung_text=excluded.einwilligung_text,
                zeitpunkt=excluded.zeitpunkt,
                kanal=excluded.kanal,
                betroffener_quelle=excluded.betroffener_quelle,
                widerruf_zeitpunkt=excluded.widerruf_zeitpunkt,
                status=excluded.status,
                updated_at=aics_now()
            """,
            (
                projekt_name, einwilligung_id, zweck, text_version,
                einwilligung_text, zeitpunkt, kanal, betroffener_quelle,
                widerruf_zeitpunkt, status,
            ),
        )
        con.commit()
    finally:
        con.close()
    return get_einwilligung(db_path, projekt_name, einwilligung_id)  # type: ignore[return-value]


def delete_einwilligung(
    db_path: Path, projekt_name: str, einwilligung_id: str
) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "DELETE FROM dsgvo_einwilligung "
            "WHERE projekt_name=? AND einwilligung_id=?",
            (projekt_name, einwilligung_id),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def widerruf_einwilligung(
    db_path: Path,
    projekt_name: str,
    einwilligung_id: str,
    *,
    widerruf_zeitpunkt: str = "",
) -> dict[str, Any] | None:
    """Widerruf der Einwilligung (Art. 7 Abs. 3) — setzt Status + Zeitpunkt."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            """
            UPDATE dsgvo_einwilligung
            SET status='widerrufen',
                widerruf_zeitpunkt=CASE
                    WHEN ?='' THEN aics_now() ELSE ? END,
                updated_at=aics_now()
            WHERE projekt_name=? AND einwilligung_id=?
            """,
            (widerruf_zeitpunkt, widerruf_zeitpunkt, projekt_name, einwilligung_id),
        )
        con.commit()
        if cur.rowcount == 0:
            return None
    finally:
        con.close()
    return get_einwilligung(db_path, projekt_name, einwilligung_id)


def import_csv(db_path: Path, projekt_name: str, csv_text: str) -> dict[str, Any]:
    """CSV-Import-Stub: liest Header-basierte Zeilen und upsertet sie.

    Erwartete Spalten (Header, Reihenfolge egal): ``einwilligung_id``, ``zweck``,
    ``text_version``, ``einwilligung_text``, ``zeitpunkt``, ``kanal``,
    ``betroffener_quelle``, ``status``. Zeilen ohne ``einwilligung_id`` werden
    übersprungen. Gibt Anzahl importierter / übersprungener Zeilen zurück.
    """
    ensure_table(db_path)
    imported = 0
    skipped = 0
    errors: list[str] = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for idx, raw in enumerate(reader, start=2):  # Zeile 1 = Header
        row = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
        eid = row.get("einwilligung_id", "")
        if not eid:
            skipped += 1
            continue
        try:
            save_einwilligung(
                db_path,
                projekt_name=projekt_name,
                einwilligung_id=eid,
                zweck=row.get("zweck", ""),
                text_version=row.get("text_version", "1") or "1",
                einwilligung_text=row.get("einwilligung_text", ""),
                zeitpunkt=row.get("zeitpunkt", ""),
                kanal=row.get("kanal", ""),
                betroffener_quelle=row.get("betroffener_quelle", ""),
                status=row.get("status", "aktiv") or "aktiv",
            )
            imported += 1
        except Exception as e:  # pragma: no cover - defensiv
            skipped += 1
            errors.append(f"Zeile {idx}: {type(e).__name__}")
    return {"imported": imported, "skipped": skipped, "errors": errors}
