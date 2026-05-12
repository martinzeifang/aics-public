from __future__ import annotations

import sqlite3
import os
import stat
from pathlib import Path
from typing import Any

from shared.sql import quote_ident
from security_utils import safe_generated_file, workspace_root_from


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-32000;

CREATE TABLE IF NOT EXISTS gutachten_projects (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    frameworks_json TEXT NOT NULL DEFAULT '[]',
    pruefungsfokus  TEXT NOT NULL DEFAULT '',
    meta_json       TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS framework_sections (
    id          INTEGER PRIMARY KEY,
    framework   TEXT NOT NULL,
    doc_name    TEXT NOT NULL,
    section_ref TEXT,
    title       TEXT,
    text        TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fs_framework ON framework_sections(framework);
CREATE INDEX IF NOT EXISTS idx_fs_doc       ON framework_sections(doc_name);

CREATE TABLE IF NOT EXISTS gutachten_questions (
    id           INTEGER PRIMARY KEY,
    project_name TEXT NOT NULL,
    question_num INTEGER NOT NULL,
    framework    TEXT NOT NULL,
    section_ref  TEXT,
    thema        TEXT,
    frage        TEXT NOT NULL,
    antwort      TEXT,
    bewertung    TEXT,
    kommentar    TEXT,
    source_file  TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gq_project ON gutachten_questions(project_name);

CREATE TABLE IF NOT EXISTS gutachten_assessments (
    id           INTEGER PRIMARY KEY,
    project_name TEXT NOT NULL,
    answer_file  TEXT,
    zusammenfassung TEXT,
    empfehlungen    TEXT,
    raw_json        TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gutachten_drafts (
    id           INTEGER PRIMARY KEY,
    project_name TEXT NOT NULL UNIQUE,
    draft_json   TEXT,
    updated_at   TEXT DEFAULT (datetime('now'))
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path = safe_generated_file(db_path, workspace_root_from(Path(__file__)))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    old_mask = os.umask(0o077)
    try:
        con = sqlite3.connect(str(db_path), timeout=30)
    finally:
        os.umask(old_mask)

    try:
        os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass

    con.row_factory = sqlite3.Row
    con.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA cache_size=-32000;")
    return con


def ensure_db(db_path: Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        _migrate_schema(con)
        con.commit()
    finally:
        con.close()


def _migrate_schema(con: sqlite3.Connection) -> None:
    """Best-effort migration for existing DBs."""
    try:
        cur = con.execute("PRAGMA table_info(gutachten_projects)")
        cols = {row["name"] for row in cur.fetchall()}
    except Exception:
        return
    if "meta_json" not in cols:
        # Add project meta storage. Default '{}' keeps existing rows valid.
        con.execute("ALTER TABLE gutachten_projects ADD COLUMN meta_json TEXT NOT NULL DEFAULT '{}' ")


# ── Ingest ────────────────────────────────────────────────────────────────────

def ingest_sections(
    db_path: Path,
    framework: str,
    doc_name: str,
    sections: list[dict[str, str]],
) -> int:
    """Speichert Abschnitte eines Dokuments. Vorhandene Einträge desselben Dokuments
    werden zuerst gelöscht (re-ingest)."""
    con = _connect(db_path)
    try:
        con.execute(
            "DELETE FROM framework_sections WHERE framework=? AND doc_name=?",
            (framework, doc_name),
        )
        rows = [
            (framework, doc_name, s.get("section_ref", ""), s.get("title", ""), s.get("text", ""))
            for s in sections
            if s.get("text", "").strip()
        ]
        con.executemany(
            "INSERT INTO framework_sections (framework, doc_name, section_ref, title, text) "
            "VALUES (?,?,?,?,?)",
            rows,
        )
        con.commit()
        return len(rows)
    finally:
        con.close()


def fetch_sections(db_path: Path, frameworks: list[str] | None = None) -> list[dict[str, Any]]:
    """Lädt alle Abschnitte, optional gefiltert nach Frameworks."""
    con = _connect(db_path)
    try:
        if frameworks:
            placeholders = ",".join("?" * len(frameworks))
            cur = con.execute(
                f"SELECT * FROM framework_sections WHERE framework IN ({placeholders}) ORDER BY framework, id",
                frameworks,
            )
        else:
            cur = con.execute("SELECT * FROM framework_sections ORDER BY framework, id")
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def count_sections_by_framework(db_path: Path) -> dict[str, int]:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT framework, COUNT(*) AS cnt FROM framework_sections GROUP BY framework"
        )
        return {row["framework"]: row["cnt"] for row in cur.fetchall()}
    finally:
        con.close()


# ── Questions ─────────────────────────────────────────────────────────────────

def save_questions(db_path: Path, project_name: str, questions: list[dict[str, Any]]) -> None:
    """Speichert generierte Fragen für ein Projekt (ersetzt vorhandene)."""
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM gutachten_questions WHERE project_name=?", (project_name,))
        rows = []
        for i, q in enumerate(questions, start=1):
            rows.append((
                project_name,
                i,
                str(q.get("framework", "")),
                str(q.get("section_ref", "")),
                str(q.get("thema", "")),
                str(q.get("frage", "")),
                str(q.get("antwort", "")),
                str(q.get("bewertung", "")),
                str(q.get("kommentar", "")),
                str(q.get("source_file", "")),
            ))
        con.executemany(
            "INSERT INTO gutachten_questions "
            "(project_name, question_num, framework, section_ref, thema, frage, "
            " antwort, bewertung, kommentar, source_file) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        con.commit()
    finally:
        con.close()


def load_questions(db_path: Path, project_name: str) -> list[dict[str, Any]]:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM gutachten_questions WHERE project_name=? ORDER BY question_num",
            (project_name,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def update_question_answers(db_path: Path, rows: list[dict[str, Any]]) -> None:
    """Aktualisiert Antwort, Bewertung und Kommentar für eine Liste von Fragen (nach id)."""
    con = _connect(db_path)
    try:
        for r in rows:
            con.execute(
                "UPDATE gutachten_questions SET antwort=?, bewertung=?, kommentar=? WHERE id=?",
                (r.get("antwort", ""), r.get("bewertung", ""), r.get("kommentar", ""), r["id"]),
            )
        con.commit()
    finally:
        con.close()


# ── Assessments ───────────────────────────────────────────────────────────────

def save_assessment(
    db_path: Path,
    project_name: str,
    answer_file: str,
    zusammenfassung: str,
    empfehlungen: str,
    raw_json: str,
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO gutachten_assessments "
            "(project_name, answer_file, zusammenfassung, empfehlungen, raw_json) "
            "VALUES (?,?,?,?,?)",
            (project_name, answer_file, zusammenfassung, empfehlungen, raw_json),
        )
        con.commit()
    finally:
        con.close()


def load_assessments(db_path: Path, project_name: str) -> list[dict[str, Any]]:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM gutachten_assessments WHERE project_name=? ORDER BY created_at DESC",
            (project_name,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


# ── Projekte ──────────────────────────────────────────────────────────────────

def save_project(
    db_path: Path,
    name: str,
    frameworks: list[str],
    pruefungsfokus: str,
    meta: dict[str, Any] | None = None,
) -> None:
    """Legt ein Projekt an oder aktualisiert es (upsert nach Name)."""
    import json as _json
    con = _connect(db_path)
    try:
        meta_json = _json.dumps(meta or {}, ensure_ascii=False)
        con.execute(
            """
            INSERT INTO gutachten_projects (name, frameworks_json, pruefungsfokus, meta_json, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(name) DO UPDATE SET
                frameworks_json = excluded.frameworks_json,
                pruefungsfokus  = excluded.pruefungsfokus,
                meta_json       = excluded.meta_json,
                updated_at      = datetime('now')
            """,
            (name, _json.dumps(frameworks, ensure_ascii=False), pruefungsfokus, meta_json),
        )
        con.commit()
    finally:
        con.close()


def load_project(db_path: Path, name: str) -> dict[str, Any] | None:
    """Lädt ein Projekt nach Name. Gibt None zurück wenn nicht vorhanden."""
    import json as _json
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM gutachten_projects WHERE name=?", (name,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["frameworks"] = _json.loads(d.get("frameworks_json", "[]"))
        except Exception:
            d["frameworks"] = []
        try:
            d["meta"] = _json.loads(d.get("meta_json", "{}"))
        except Exception:
            d["meta"] = {}
        return d
    finally:
        con.close()


def list_projects(db_path: Path) -> list[str]:
    """Gibt alle Projektnamen sortiert nach letzter Änderung zurück."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT name FROM gutachten_projects ORDER BY updated_at DESC, name"
        )
        return [row["name"] for row in cur.fetchall()]
    finally:
        con.close()


def delete_project(db_path: Path, name: str) -> None:
    """Löscht ein Projekt samt aller zugehörigen Fragen und Gutachten."""
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM gutachten_questions   WHERE project_name=?", (name,))
        con.execute("DELETE FROM gutachten_assessments WHERE project_name=?", (name,))
        con.execute("DELETE FROM gutachten_projects    WHERE name=?",         (name,))
        con.commit()
    finally:
        con.close()


# ── Einzelne Frage bearbeiten / löschen ──────────────────────────────────────

def update_question(db_path: Path, question_id: int, fields: dict[str, Any]) -> None:
    """Aktualisiert editierbare Felder einer einzelnen Frage."""
    allowed = {"framework", "section_ref", "thema", "frage", "antwort", "bewertung", "kommentar"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    # Identifiers cannot be parameter-bound; quote allowed column names.
    set_clause = ", ".join(f"{quote_ident(k)}=?" for k in updates)
    values = list(updates.values()) + [question_id]
    con = _connect(db_path)
    try:
        con.execute(f"UPDATE gutachten_questions SET {set_clause} WHERE id=?", values)
        con.commit()
    finally:
        con.close()


def delete_question(db_path: Path, question_id: int) -> None:
    """Löscht eine einzelne Frage und renummeriert den Rest."""
    con = _connect(db_path)
    try:
        # Projektnamen merken für Renummerierung
        cur = con.execute(
            "SELECT project_name FROM gutachten_questions WHERE id=?", (question_id,)
        )
        row = cur.fetchone()
        if row is None:
            return
        project_name = row["project_name"]

        con.execute("DELETE FROM gutachten_questions WHERE id=?", (question_id,))

        # Renummerieren
        cur2 = con.execute(
            "SELECT id FROM gutachten_questions WHERE project_name=? ORDER BY question_num, id",
            (project_name,),
        )
        for new_num, r in enumerate(cur2.fetchall(), start=1):
            con.execute(
                "UPDATE gutachten_questions SET question_num=? WHERE id=?",
                (new_num, r["id"]),
            )
        con.commit()
    finally:
        con.close()


def save_gutachten_draft(db_path: Path, project_name: str, draft_json: str) -> None:
    """Speichert oder aktualisiert den Gutachten-Entwurf für ein Projekt."""
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO gutachten_drafts (project_name, draft_json, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(project_name) DO UPDATE SET
                draft_json = excluded.draft_json,
                updated_at = datetime('now')
            """,
            (project_name, draft_json),
        )
        con.commit()
    finally:
        con.close()


def load_gutachten_draft(db_path: Path, project_name: str) -> str | None:
    """Lädt den gespeicherten Gutachten-Entwurf (JSON-String) oder None."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT draft_json FROM gutachten_drafts WHERE project_name=?",
            (project_name,),
        )
        row = cur.fetchone()
        return row["draft_json"] if row else None
    finally:
        con.close()


def append_questions(db_path: Path, project_name: str, questions: list[dict[str, Any]]) -> int:
    """Hängt neue Fragen an ein Projekt an (ohne bestehende zu löschen).
    Gibt die Anzahl der hinzugefügten Fragen zurück."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT COALESCE(MAX(question_num), 0) AS mx FROM gutachten_questions WHERE project_name=?",
            (project_name,),
        )
        start_num = cur.fetchone()["mx"] + 1
        rows = []
        for i, q in enumerate(questions):
            rows.append((
                project_name,
                start_num + i,
                str(q.get("framework", "")),
                str(q.get("section_ref", "")),
                str(q.get("thema", "")),
                str(q.get("frage", "")),
                str(q.get("antwort", "")),
                str(q.get("bewertung", "")),
                str(q.get("kommentar", "")),
                str(q.get("source_file", "")),
            ))
        con.executemany(
            "INSERT INTO gutachten_questions "
            "(project_name, question_num, framework, section_ref, thema, frage, "
            " antwort, bewertung, kommentar, source_file) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        con.commit()
        return len(rows)
    finally:
        con.close()
