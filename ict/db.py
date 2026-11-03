from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from shared import db as _sdb

from baso.io_docx import extract_docx_paragraphs

from .io_xlsx import read_items


def _get_db_connection(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer."""
    return _sdb.connect(db_path)


SCHEMA = """
CREATE TABLE IF NOT EXISTS ict_items (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  file_name TEXT NOT NULL,
  sheet_name TEXT NOT NULL,
  row_num INTEGER NOT NULL,
  question_id TEXT NOT NULL,
  title TEXT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT,
  maturity INTEGER,
  explanation TEXT,
  guidance TEXT,
  optimization_potential TEXT,
  created_at TEXT DEFAULT (aics_now())
);

CREATE INDEX IF NOT EXISTS idx_ict_items_file ON ict_items(file_name);
CREATE INDEX IF NOT EXISTS idx_ict_items_qid ON ict_items(question_id);

CREATE TABLE IF NOT EXISTS ict_report_paragraphs (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  file_name TEXT NOT NULL,
  para_index INTEGER NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ict_report_paras_file ON ict_report_paragraphs(file_name);

CREATE TABLE IF NOT EXISTS siko_paragraphs (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  doc_name TEXT NOT NULL,
  para_index INTEGER NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ict_siko_doc ON siko_paragraphs(doc_name);
"""


def ensure_db(db_path: Path) -> None:
    con = _get_db_connection(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def ingest_questionnaires(source_dir: Path, db_path: Path, *, progress: Optional[Callable[[int, int, str], None]] = None) -> None:
    files = sorted(source_dir.resolve().glob("*.xlsx"))
    con = _get_db_connection(db_path)
    try:
        total = len(files)
        for i, p in enumerate(files, start=1):
            con.execute("DELETE FROM ict_items WHERE file_name = ?", (p.name,))
            items = read_items(p)
            con.executemany(
                """
                INSERT INTO ict_items(
                  file_name, sheet_name, row_num, question_id, title, question,
                  answer, maturity, explanation, guidance
                  , optimization_potential
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        it.file_name,
                        it.sheet_name,
                        it.row,
                        it.question_id,
                        it.title,
                        it.question,
                        it.answer,
                        it.maturity,
                        it.explanation,
                        it.guidance,
                        it.optimization_potential,
                    )
                    for it in items
                ],
            )
            if progress:
                progress(i, total, p.name)
        con.commit()
    finally:
        con.close()


def ingest_sikos(sikos_dir: Path, db_path: Path, *, progress: Optional[Callable[[int, int, str], None]] = None) -> None:
    files = [p for p in sorted(sikos_dir.resolve().glob("*.docx")) if p.is_file() and not p.name.startswith("~$")]
    con = _get_db_connection(db_path)
    try:
        total = len(files)
        for i, p in enumerate(files, start=1):
            con.execute("DELETE FROM siko_paragraphs WHERE doc_name = ?", (p.name,))
            try:
                paras = extract_docx_paragraphs(p)
            except (ValueError, OSError, Exception) as e:
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


def ingest_reports(reports_dir: Path, db_path: Path, *, progress: Optional[Callable[[int, int, str], None]] = None) -> None:
    files = [p for p in sorted(reports_dir.resolve().glob("*.docx")) if p.is_file() and not p.name.startswith("~$")]
    con = _get_db_connection(db_path)
    try:
        total = len(files)
        for i, p in enumerate(files, start=1):
            con.execute("DELETE FROM ict_report_paragraphs WHERE file_name = ?", (p.name,))
            try:
                paras = extract_docx_paragraphs(p)
            except (ValueError, OSError, Exception) as e:
                if progress:
                    progress(i, total, f"SKIP (ungueltig): {p.name}")
                continue
            con.executemany(
                "INSERT INTO ict_report_paragraphs(file_name, para_index, text) VALUES (?, ?, ?)",
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
            SELECT file_name, title, question, question_id, answer, maturity, explanation, guidance, optimization_potential
            FROM ict_items
            WHERE answer IS NOT NULL AND trim(answer) <> ''
              AND maturity IS NOT NULL
              AND explanation IS NOT NULL AND trim(explanation) <> ''
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


def fetch_report_paragraphs(db_path: Path, limit: int = 50000) -> list[dict]:
    con = _get_db_connection(db_path)
    try:
        cur = con.execute("SELECT file_name, para_index, text FROM ict_report_paragraphs LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()
