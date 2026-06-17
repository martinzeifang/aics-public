from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional
from contextlib import contextmanager

from shared import db as _sdb

from .io_docx import extract_docx_paragraphs
from .io_xlsx import read_items


SCHEMA = """
CREATE TABLE IF NOT EXISTS qa_items (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  file_name TEXT NOT NULL,
  sheet_name TEXT NOT NULL,
  row_num INTEGER NOT NULL,
  layout TEXT NOT NULL,
  title TEXT NOT NULL,
  question TEXT NOT NULL,
  schutzziel TEXT,
  status TEXT,
  answer TEXT,
  baso_id TEXT,
  created_at TEXT DEFAULT (aics_now())
);

CREATE INDEX IF NOT EXISTS idx_qa_items_layout ON qa_items(layout);
CREATE INDEX IF NOT EXISTS idx_qa_items_file ON qa_items(file_name);

CREATE TABLE IF NOT EXISTS siko_paragraphs (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  doc_name TEXT NOT NULL,
  para_index INTEGER NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_siko_doc ON siko_paragraphs(doc_name);
"""


def _get_db_connection(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer."""
    return _sdb.connect(db_path)


def ensure_db(db_path: Path) -> None:
    con = _get_db_connection(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def ingest_questionnaires(
    source_dir: Path,
    db_path: Path,
    *,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> None:
    source_dir = source_dir.resolve()
    files = sorted(source_dir.glob("*.xlsx"))
    con = _get_db_connection(db_path)
    try:
        total = len(files)
        for i, p in enumerate(files, start=1):
            con.execute("DELETE FROM qa_items WHERE file_name = ?", (p.name,))
            items = read_items(p)
            rows = []
            for it in items:
                answer = None
                status = None
                schutzziel = None
                baso_id = None
                if it.layout == "system":
                    answer = it.bemerkung_umsetzung
                    status = it.umsetzung
                    schutzziel = it.schutzziel
                else:
                    answer = it.bemerkung
                    status = it.ops_met
                    baso_id = it.baso_id

                # Store all rows; retrieval later filters for non-empty answers.
                rows.append(
                    (
                        it.file_name,
                        it.sheet_name,
                        it.row,
                        it.layout,
                        it.title,
                        it.question,
                        schutzziel,
                        status,
                        answer,
                        baso_id,
                    )
                )

            con.executemany(
                """
                INSERT INTO qa_items(
                  file_name, sheet_name, row_num, layout, title, question,
                  schutzziel, status, answer, baso_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            if progress:
                progress(i, total, p.name)
        con.commit()
    finally:
        con.close()


def ingest_sikos(
    sikos_dir: Path,
    db_path: Path,
    *,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> None:
    sikos_dir = sikos_dir.resolve()
    files = [p for p in sorted(sikos_dir.glob("*.docx")) if p.is_file() and not p.name.startswith("~$")]
    con = _get_db_connection(db_path)
    try:
        total = len(files)
        for i, p in enumerate(files, start=1):
            con.execute("DELETE FROM siko_paragraphs WHERE doc_name = ?", (p.name,))
            try:
                paras = extract_docx_paragraphs(p)
            except Exception:
                if progress:
                    progress(i, total, f"SKIP (ungueltig): {p.name}")
                continue
            con.executemany(
                "INSERT INTO siko_paragraphs(doc_name, para_index, text) VALUES (?, ?, ?)",
                [(pp.doc_name, pp.index, pp.text) for pp in paras],
            )
            if progress:
                progress(i, total, p.name)
        con.commit()
    finally:
        con.close()


def fetch_answered_items(db_path: Path, limit: int = 50000) -> list[dict]:
    con = _get_db_connection(db_path)
    try:
        cur = con.execute(
            """
            SELECT file_name, layout, title, question, schutzziel, status, answer
            FROM qa_items
            WHERE answer IS NOT NULL AND trim(answer) <> ''
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def fetch_siko_paragraphs(db_path: Path, limit: int = 50000) -> list[dict]:
    con = _get_db_connection(db_path)
    try:
        cur = con.execute("SELECT doc_name, para_index, text FROM siko_paragraphs LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()
