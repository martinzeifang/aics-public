"""Shared persistence for linking requirements/risks to tracker issues.

We store links in the module DB (per-project) so they survive restarts and can be
synced later.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from shared import db as _sdb


_DDL = """
CREATE TABLE IF NOT EXISTS linked_issues (
  id              TEXT PRIMARY KEY,
  projekt_name    TEXT NOT NULL,
  object_kind     TEXT NOT NULL,          -- 'requirement' | 'risk'
  object_id       TEXT NOT NULL,          -- requirement_id or risk_id
  provider        TEXT NOT NULL,          -- 'github' | 'gitlab'
  repo            TEXT NOT NULL DEFAULT '',
  issue_number    INTEGER,                -- GitHub: number
  issue_iid       INTEGER,                -- GitLab: iid
  url             TEXT NOT NULL,
  title           TEXT NOT NULL DEFAULT '',
  state           TEXT NOT NULL DEFAULT '',
  state_reason    TEXT NOT NULL DEFAULT '',
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL,
  UNIQUE(projekt_name, object_kind, object_id, provider, url)
);

-- #1850: Woran der Abgleich erkennt, dass sich am Issue etwas getan hat.
-- `comments` ist die Kommentarzahl der Gegenstelle (GitHub `comments`,
-- GitLab `user_notes_count`), `remote_updated_at` ihr Änderungszeitpunkt.
-- Beide liegen im Issue-Objekt, das der Abgleich ohnehin holt — es braucht
-- KEINEN zusätzlichen API-Aufruf, sie wurden bisher nur nicht gelesen.
-- NULL heißt „noch nie erhoben": Der erste Abgleich lernt den Wert und
-- markiert NICHT (sonst meldete er jedes Objekt mit Kommentaren als neu zu
-- bewerten, und eine Markierung, die alle trifft, trifft niemanden).
ALTER TABLE linked_issues ADD COLUMN IF NOT EXISTS comments INTEGER;
ALTER TABLE linked_issues ADD COLUMN IF NOT EXISTS remote_updated_at TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_li_proj_obj ON linked_issues(projekt_name, object_kind, object_id);
CREATE INDEX IF NOT EXISTS idx_li_proj_provider ON linked_issues(projekt_name, provider, updated_at DESC);
"""


@dataclass(frozen=True)
class LinkedIssue:
    id: str
    projekt_name: str
    object_kind: str
    object_id: str
    provider: str
    repo: str
    issue_number: int | None
    issue_iid: int | None
    url: str
    title: str
    state: str
    state_reason: str
    created_at: int
    updated_at: int
    #: #1850 — Kommentarzahl der Gegenstelle beim letzten Abgleich.
    #: ``None`` heißt **noch nie erhoben**; der nächste Abgleich lernt sie nur
    #: und markiert nicht.
    comments: int | None = None
    #: Änderungszeitpunkt der Gegenstelle beim letzten Abgleich.
    remote_updated_at: str = ""


def ensure_tables(db_path: Path) -> None:
    with _sdb.connect(db_path) as con:
        con.executescript(_DDL)


def add_link(
    db_path: Path,
    *,
    projekt_name: str,
    object_kind: str,
    object_id: str,
    provider: str,
    repo: str,
    url: str,
    issue_number: int | None = None,
    issue_iid: int | None = None,
    title: str = "",
    state: str = "",
    state_reason: str = "",
    comments: int | None = None,
    remote_updated_at: str = "",
) -> str:
    ensure_tables(db_path)
    ts = int(time.time())
    lid = str(uuid.uuid4())
    with _sdb.connect(db_path) as con:
        # If exists, update
        row = con.execute(
            "SELECT id FROM linked_issues WHERE projekt_name=? AND object_kind=? AND object_id=? AND provider=? AND url=?",
            (projekt_name, object_kind, object_id, provider, url),
        ).fetchone()
        if row:
            lid = str(row[0])
            con.execute(
                # #1850: `comments` nur schreiben, wenn der Aufrufer es nennt
                # (COALESCE) — sonst löschte jedes Teil-Update die gelernte
                # Kommentarzahl, und der nächste Abgleich meldete wieder
                # „Erstabgleich". Dieselbe Falle wie `artefakt` in #1771 und
                # `meta_json` in #1540: Der Schutz gehört in die
                # Speicherfunktion, nicht in den Aufrufer.
                """UPDATE linked_issues SET repo=?, issue_number=?, issue_iid=?,
                          title=?, state=?, state_reason=?,
                          comments=COALESCE(?, comments),
                          remote_updated_at=CASE WHEN ?='' THEN remote_updated_at ELSE ? END,
                          updated_at=?
                   WHERE id=?""",
                (repo or "", issue_number, issue_iid, title or "", state or "",
                 state_reason or "", comments, remote_updated_at or "",
                 remote_updated_at or "", ts, lid),
            )
        else:
            con.execute(
                """INSERT INTO linked_issues(
                     id, projekt_name, object_kind, object_id, provider, repo,
                     issue_number, issue_iid, url, title, state, state_reason,
                     comments, remote_updated_at, created_at, updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    lid,
                    projekt_name,
                    object_kind,
                    object_id,
                    provider,
                    repo or "",
                    issue_number,
                    issue_iid,
                    url,
                    title or "",
                    state or "",
                    state_reason or "",
                    comments,
                    remote_updated_at or "",
                    ts,
                    ts,
                ),
            )
    return lid


def list_links(db_path: Path, *, projekt_name: str, object_kind: str, object_id: str) -> list[LinkedIssue]:
    ensure_tables(db_path)
    with _sdb.connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM linked_issues WHERE projekt_name=? AND object_kind=? AND object_id=? ORDER BY updated_at DESC",
            (projekt_name, object_kind, object_id),
        ).fetchall()
    out: list[LinkedIssue] = []
    for r in rows:
        out.append(
            LinkedIssue(
                id=str(r["id"]),
                projekt_name=str(r["projekt_name"]),
                object_kind=str(r["object_kind"]),
                object_id=str(r["object_id"]),
                provider=str(r["provider"]),
                repo=str(r["repo"] or ""),
                issue_number=int(r["issue_number"]) if r["issue_number"] is not None else None,
                issue_iid=int(r["issue_iid"]) if r["issue_iid"] is not None else None,
                url=str(r["url"]),
                title=str(r["title"] or ""),
                state=str(r["state"] or ""),
                state_reason=str(r["state_reason"] or ""),
                created_at=int(r["created_at"]),
                updated_at=int(r["updated_at"]),
                comments=(int(r["comments"]) if _hat(r, "comments")
                          and r["comments"] is not None else None),
                remote_updated_at=(str(r["remote_updated_at"] or "")
                                   if _hat(r, "remote_updated_at") else ""),
            )
        )
    return out


def _hat(row, feld: str) -> bool:
    """Hat die Zeile diese Spalte?

    Die beiden Spalten aus #1850 kommen per ``ADD COLUMN IF NOT EXISTS`` dazu.
    Eine Installation, deren ``ensure_tables`` noch nicht lief, liefert sie
    nicht — und ein ``KeyError`` beim Lesen wäre ein harter Fehler für etwas,
    das nur eine Zusatzangabe ist.
    """
    try:
        row[feld]
        return True
    except Exception:  # noqa: BLE001
        return False


def _row_to_link(r) -> LinkedIssue:
    return LinkedIssue(
        id=str(r["id"]),
        projekt_name=str(r["projekt_name"]),
        object_kind=str(r["object_kind"]),
        object_id=str(r["object_id"]),
        provider=str(r["provider"]),
        repo=str(r["repo"] or ""),
        issue_number=int(r["issue_number"]) if r["issue_number"] is not None else None,
        issue_iid=int(r["issue_iid"]) if r["issue_iid"] is not None else None,
        url=str(r["url"]),
        title=str(r["title"] or ""),
        state=str(r["state"] or ""),
        state_reason=str(r["state_reason"] or ""),
        created_at=int(r["created_at"]),
        updated_at=int(r["updated_at"]),
    )


def list_project_links(
    db_path: Path, *, projekt_name: str, object_kind: str | None = None
) -> list[LinkedIssue]:
    """Alle verknüpften Issues eines Projekts (optional nach object_kind gefiltert)."""
    ensure_tables(db_path)
    with _sdb.connect(db_path) as con:
        if object_kind:
            rows = con.execute(
                "SELECT * FROM linked_issues WHERE projekt_name=? AND object_kind=? "
                "ORDER BY object_id, updated_at DESC",
                (projekt_name, object_kind),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM linked_issues WHERE projekt_name=? "
                "ORDER BY object_id, updated_at DESC",
                (projekt_name,),
            ).fetchall()
    return [_row_to_link(r) for r in rows]


def delete_link(db_path: Path, link_id: str) -> None:
    ensure_tables(db_path)
    with _sdb.connect(db_path) as con:
        con.execute("DELETE FROM linked_issues WHERE id=?", (link_id,))


def update_issue_state(
    db_path: Path,
    link_id: str,
    *,
    state: str,
    state_reason: str = "",
    title: str | None = None,
) -> None:
    ensure_tables(db_path)
    ts = int(time.time())
    with _sdb.connect(db_path) as con:
        if title is None:
            con.execute(
                "UPDATE linked_issues SET state=?, state_reason=?, updated_at=? WHERE id=?",
                (state or "", state_reason or "", ts, link_id),
            )
        else:
            con.execute(
                "UPDATE linked_issues SET state=?, state_reason=?, title=?, updated_at=? WHERE id=?",
                (state or "", state_reason or "", title or "", ts, link_id),
            )
