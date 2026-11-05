"""Unveränderliches Archiv des Konformitätsnachweises je Release (#1611).

Nach Freigabe wird die finalisierte PDF mit SHA-256 und Freigeber dauerhaft abgelegt
(wie Gutachten-Final #969 / DSGVO-Jahresbericht #1132). Danach unveränderlich.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from shared import db as _sdb

DB = Path("data/db/cra.sqlite")
STORE = Path("data/cra/konformitaet")


def ensure_table(db_path: Path = DB) -> None:
    con = _sdb.connect(str(db_path))
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS cra_konformitaet_final (
                   id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                   projekt_name TEXT NOT NULL,
                   version TEXT NOT NULL DEFAULT '',
                   pdf_path TEXT NOT NULL DEFAULT '',
                   sha256 TEXT NOT NULL DEFAULT '',
                   ampel TEXT NOT NULL DEFAULT '',
                   freigegeben_von TEXT NOT NULL DEFAULT '',
                   freigegeben_am TEXT DEFAULT (aics_now())
               )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_cra_konf_final_proj "
                    "ON cra_konformitaet_final(projekt_name)")
        con.commit()
    finally:
        con.close()


def add_final(db_path: Path, projekt_name: str, *, version: str, pdf_bytes: bytes,
              ampel: str, freigegeben_von: str) -> dict[str, Any]:
    ensure_table(db_path)
    STORE.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in f"{projekt_name}_{version or 'v'}")
    path = STORE / f"{safe}_{sha[:12]}.pdf"
    path.write_bytes(pdf_bytes)
    con = _sdb.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO cra_konformitaet_final (projekt_name, version, pdf_path, sha256, ampel, freigegeben_von) "
            "VALUES (?,?,?,?,?,?)",
            (projekt_name, version or "", str(path), sha, ampel, freigegeben_von))
        con.commit()
    finally:
        con.close()
    return {"version": version, "sha256": sha, "pdf_path": str(path), "ampel": ampel}


def list_final(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _sdb.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT id, version, sha256, ampel, freigegeben_von, freigegeben_am "
            "FROM cra_konformitaet_final WHERE projekt_name=? ORDER BY freigegeben_am DESC",
            (projekt_name,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_final(db_path: Path, projekt_name: str, final_id: int) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _sdb.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT * FROM cra_konformitaet_final WHERE id=? AND projekt_name=?",
            (int(final_id), projekt_name)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()
