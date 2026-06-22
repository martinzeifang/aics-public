"""Verknüpfung von Risikobewertungs-Risiken mit CRA-Anforderungen (#884/#885).

Speichert n:m-Verknüpfungen zwischen einem Risiko (aus dem Risikobewertung-Modul)
und einer CRA-Anforderung (stabile String-ID wie ``AI1-01``). Die Tabelle liegt in
der **Risikobewertung-DB**, weil dort die Risiko-IDs leben; die CRA-Anforderungs-ID
ist ein stabiler String und braucht keinen FK.

Fachlich: Die Verknüpfung dient der **Nachweisbarkeit** der CRA-Risikoabschätzung
(AI1-01, Annex I) — sie blendet niemals Anforderungen aus.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from shared import db as _sdb

_DDL = """
CREATE TABLE IF NOT EXISTS risk_requirement_links (
  id              TEXT PRIMARY KEY,
  rb_projekt_name TEXT NOT NULL,        -- Risikobewertungs-Projekt
  risk_id         INTEGER NOT NULL,     -- rb_risiken.id
  cra_projekt_name TEXT NOT NULL DEFAULT '',  -- verknüpftes CRA-Projekt (Kontext)
  anforderung_id  TEXT NOT NULL,        -- CRA-Anforderung, z.B. 'AI1-01'
  created_at      INTEGER NOT NULL,
  UNIQUE(rb_projekt_name, risk_id, anforderung_id)
);

CREATE INDEX IF NOT EXISTS idx_rrl_risk ON risk_requirement_links(rb_projekt_name, risk_id);
CREATE INDEX IF NOT EXISTS idx_rrl_anf  ON risk_requirement_links(rb_projekt_name, anforderung_id);
"""


@dataclass(frozen=True)
class RiskReqLink:
    id: str
    rb_projekt_name: str
    risk_id: int
    cra_projekt_name: str
    anforderung_id: str
    created_at: int


def ensure_tables(db_path: Path) -> None:
    with _sdb.connect(db_path) as con:
        con.executescript(_DDL)


def _row(r) -> RiskReqLink:
    return RiskReqLink(
        id=str(r["id"]),
        rb_projekt_name=str(r["rb_projekt_name"]),
        risk_id=int(r["risk_id"]),
        cra_projekt_name=str(r["cra_projekt_name"] or ""),
        anforderung_id=str(r["anforderung_id"]),
        created_at=int(r["created_at"]),
    )


def add_link(db_path: Path, *, rb_projekt_name: str, risk_id: int,
             anforderung_id: str, cra_projekt_name: str = "") -> str:
    """Verknüpfung anlegen (idempotent über UNIQUE). Gibt die id zurück."""
    ensure_tables(db_path)
    lid = uuid.uuid4().hex
    now = int(time.time())
    with _sdb.connect(db_path) as con:
        con.execute(
            "INSERT INTO risk_requirement_links"
            "(id, rb_projekt_name, risk_id, cra_projekt_name, anforderung_id, created_at)"
            " VALUES(?,?,?,?,?,?) ON CONFLICT DO NOTHING",
            (lid, rb_projekt_name, int(risk_id), cra_projekt_name, anforderung_id, now),
        )
    return lid


def delete_link(db_path: Path, *, rb_projekt_name: str, risk_id: int,
                anforderung_id: str) -> None:
    ensure_tables(db_path)
    with _sdb.connect(db_path) as con:
        con.execute(
            "DELETE FROM risk_requirement_links WHERE rb_projekt_name=? AND risk_id=? AND anforderung_id=?",
            (rb_projekt_name, int(risk_id), anforderung_id),
        )


def list_for_risk(db_path: Path, *, rb_projekt_name: str, risk_id: int) -> list[RiskReqLink]:
    """Alle CRA-Anforderungen, die einem Risiko zugeordnet sind."""
    ensure_tables(db_path)
    with _sdb.connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM risk_requirement_links WHERE rb_projekt_name=? AND risk_id=? "
            "ORDER BY anforderung_id",
            (rb_projekt_name, int(risk_id)),
        ).fetchall()
    return [_row(r) for r in rows]


def list_for_requirement(db_path: Path, *, rb_projekt_name: str,
                         anforderung_id: str) -> list[RiskReqLink]:
    """Alle Risiken, die eine CRA-Anforderung adressieren."""
    ensure_tables(db_path)
    with _sdb.connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM risk_requirement_links WHERE rb_projekt_name=? AND anforderung_id=? "
            "ORDER BY risk_id",
            (rb_projekt_name, anforderung_id),
        ).fetchall()
    return [_row(r) for r in rows]


def list_for_project(db_path: Path, *, rb_projekt_name: str) -> list[RiskReqLink]:
    """Alle Verknüpfungen eines RB-Projekts (für Abdeckungs-Sicht)."""
    ensure_tables(db_path)
    with _sdb.connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM risk_requirement_links WHERE rb_projekt_name=? "
            "ORDER BY anforderung_id, risk_id",
            (rb_projekt_name,),
        ).fetchall()
    return [_row(r) for r in rows]
