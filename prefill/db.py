"""Persistenz für Prefill-Vorschläge und Audit-Trail (je Modul-DB)."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from shared import db as _sdb


_PREFILL_SCHEMA = """
CREATE TABLE IF NOT EXISTS prefill_suggestions (
    id              TEXT PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    field_id        TEXT NOT NULL,
    score           INTEGER NOT NULL DEFAULT 0,
    kommentar       TEXT NOT NULL DEFAULT '',
    confidence      REAL NOT NULL DEFAULT 0.0,
    rationale       TEXT NOT NULL DEFAULT '',
    citations_json  TEXT NOT NULL DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'pending',
    suggested_at    INTEGER NOT NULL,
    UNIQUE(projekt_name, field_id)
);

CREATE TABLE IF NOT EXISTS prefill_decisions (
    id              TEXT PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    field_id        TEXT NOT NULL,
    action          TEXT NOT NULL,
    decided_by      TEXT NOT NULL DEFAULT '',
    decided_at      INTEGER NOT NULL,
    original_score  INTEGER,
    final_score     INTEGER,
    original_kommentar TEXT NOT NULL DEFAULT '',
    final_kommentar    TEXT NOT NULL DEFAULT '',
    citations_json     TEXT NOT NULL DEFAULT '[]',
    rationale          TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_ps_projekt ON prefill_suggestions(projekt_name);
CREATE INDEX IF NOT EXISTS idx_pd_projekt ON prefill_decisions(projekt_name, decided_at DESC);
"""


def ensure_prefill_tables(db_path: Path) -> None:
    with _sdb.connect(db_path) as con:
        con.executescript(_PREFILL_SCHEMA)


def upsert_suggestion(
    db_path: Path,
    projekt_name: str,
    field_id: str,
    score: int,
    kommentar: str,
    confidence: float,
    rationale: str,
    citations: list[dict[str, Any]],
) -> str:
    """Speichert oder aktualisiert einen Vorschlag. Gibt die id zurück."""
    sid = str(uuid.uuid4())
    ts = int(time.time())
    cit_json = json.dumps(citations, ensure_ascii=False)
    with _sdb.connect(db_path) as con:
        # Check if entry exists
        row = con.execute(
            "SELECT id FROM prefill_suggestions WHERE projekt_name=? AND field_id=?",
            (projekt_name, field_id),
        ).fetchone()
        if row:
            sid = row[0]
            con.execute(
                """UPDATE prefill_suggestions SET
                    score=?, kommentar=?, confidence=?, rationale=?,
                    citations_json=?, status='pending', suggested_at=?
                   WHERE id=?""",
                (score, kommentar, confidence, rationale, cit_json, ts, sid),
            )
        else:
            con.execute(
                """INSERT INTO prefill_suggestions
                    (id, projekt_name, field_id, score, kommentar, confidence,
                     rationale, citations_json, status, suggested_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (sid, projekt_name, field_id, score, kommentar,
                 confidence, rationale, cit_json, ts),
            )
    return sid


def load_suggestions(
    db_path: Path, projekt_name: str, status: str | None = None
) -> list[dict[str, Any]]:
    """Lädt Vorschläge für ein Projekt, optional gefiltert nach Status."""
    with _sdb.connect(db_path) as con:
        if status:
            rows = con.execute(
                "SELECT * FROM prefill_suggestions WHERE projekt_name=? AND status=? ORDER BY field_id",
                (projekt_name, status),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM prefill_suggestions WHERE projekt_name=? ORDER BY field_id",
                (projekt_name,),
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["citations"] = json.loads(d.get("citations_json", "[]"))
        except Exception:
            d["citations"] = []
        result.append(d)
    return result


def get_suggestions(
    db_path: Path, projekt_name: str, status: str | None = None
) -> list[dict[str, Any]]:
    """Alias für load_suggestions — von prefill/api.py erwartet (behebt ImportError)."""
    return load_suggestions(db_path, projekt_name, status)


def set_suggestion(
    db_path: Path, projekt_name: str, field_id: str, suggestion: dict[str, Any]
) -> str:
    """Speichert einen Vorschlag aus einem Dict (Wrapper um upsert_suggestion)."""
    return upsert_suggestion(
        db_path, projekt_name, field_id,
        score=int(suggestion.get("score", 0)),
        kommentar=suggestion.get("kommentar", ""),
        confidence=float(suggestion.get("confidence", 0.0)),
        rationale=suggestion.get("rationale", ""),
        citations=suggestion.get("citations", []),
    )


def get_suggestion(
    db_path: Path, projekt_name: str, field_id: str
) -> dict[str, Any] | None:
    with _sdb.connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM prefill_suggestions WHERE projekt_name=? AND field_id=?",
            (projekt_name, field_id),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["citations"] = json.loads(d.get("citations_json", "[]"))
    except Exception:
        d["citations"] = []
    return d


def decide_suggestion(
    db_path: Path,
    projekt_name: str,
    field_id: str,
    action: str,           # 'accepted' | 'rejected'
    decided_by: str,
    final_score: int | None = None,
    final_kommentar: str = "",
) -> None:
    """Entscheide über einen Vorschlag und schreibe den Audit-Trail."""
    ts = int(time.time())
    with _sdb.connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM prefill_suggestions WHERE projekt_name=? AND field_id=?",
            (projekt_name, field_id),
        ).fetchone()
        if not row:
            return

        orig_score = row[3]  # score column
        orig_kommentar = row[4]
        citations_json = row[7]
        rationale = row[6]

        effective_score = final_score if final_score is not None else orig_score
        effective_kommentar = final_kommentar if final_kommentar else orig_kommentar

        con.execute(
            "UPDATE prefill_suggestions SET status=? WHERE projekt_name=? AND field_id=?",
            (action, projekt_name, field_id),
        )
        con.execute(
            """INSERT INTO prefill_decisions
                (id, projekt_name, field_id, action, decided_by, decided_at,
                 original_score, final_score, original_kommentar, final_kommentar,
                 citations_json, rationale)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), projekt_name, field_id, action, decided_by, ts,
             orig_score, effective_score, orig_kommentar, effective_kommentar,
             citations_json, rationale),
        )


def load_decisions(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    with _sdb.connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM prefill_decisions WHERE projekt_name=? ORDER BY decided_at DESC",
            (projekt_name,),
        ).fetchall()
    return [dict(r) for r in rows]
