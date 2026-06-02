from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable, Dict, List, Optional

from security_utils import safe_generated_file, workspace_root_from
from shared.db_security import connect_sqlite

from baso.io_docx import extract_docx_paragraphs


def _get_db_connection(db_path: Path) -> sqlite3.Connection:
    """Get a properly configured SQLite connection with WAL mode and optimizations."""
    db_path = Path(db_path)
    db_path = safe_generated_file(db_path, workspace_root_from(Path(__file__)))

    con = connect_sqlite(db_path, anchor=Path(__file__))

    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA cache_size=-64000")  # 64MB cache
    return con


def _iter_docx_files(dir_path: Path) -> List[Path]:
    # Ignore MS Office lock/temp files like "~$foo.docx".
    files = []
    for p in sorted(dir_path.glob("*.docx")):
        if not p.is_file():
            continue
        if p.name.startswith("~$"):
            continue
        files.append(p)
    return files


SCHEMA = """
CREATE TABLE IF NOT EXISTS compliance_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_name TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS compliance_report_paragraphs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_name TEXT NOT NULL,
  para_index INTEGER NOT NULL,
  text TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_compliance_reports_file ON compliance_reports(file_name);
CREATE INDEX IF NOT EXISTS idx_compliance_report_paras_file ON compliance_report_paragraphs(file_name);

CREATE TABLE IF NOT EXISTS compliance_siko_paragraphs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_name TEXT NOT NULL,
  para_index INTEGER NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_compliance_siko_doc ON compliance_siko_paragraphs(doc_name);

CREATE TABLE IF NOT EXISTS compliance_assessments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  answer_file TEXT,
  hersteller TEXT,
  cve_nummern TEXT,
  beschreibung_mitre TEXT,
  datum TEXT,
  zusammenfassung TEXT,
  stellungnahme TEXT,
  eintrittswahrscheinlichkeit TEXT,
  schadenspotenzial TEXT,
  risikowert INTEGER,
  quellen_json TEXT,
  raw_json TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_compliance_assessments_date ON compliance_assessments(datum);
CREATE INDEX IF NOT EXISTS idx_compliance_assessments_cve ON compliance_assessments(cve_nummern);
"""


def ensure_db(db_path: Path) -> None:
    db_path = safe_generated_file(db_path, workspace_root_from(Path(__file__)))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = _get_db_connection(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def ingest_reports(
    reports_dir: Path,
    db_path: Path,
    *,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> None:
    reports_dir = reports_dir.resolve()
    if not reports_dir.exists():
        raise FileNotFoundError(f"reports_dir not found: {reports_dir}")
    files = _iter_docx_files(reports_dir)
    con = _get_db_connection(db_path)
    try:
        total = len(files)
        for i, p in enumerate(files, start=1):
            con.execute("DELETE FROM compliance_reports WHERE file_name = ?", (p.name,))
            con.execute("DELETE FROM compliance_report_paragraphs WHERE file_name = ?", (p.name,))

            try:
                paras = extract_docx_paragraphs(p)
            except (ValueError, OSError, Exception) as e:
                # Skip invalid/corrupted docx but continue.
                if progress:
                    progress(i, total, f"SKIP (ungueltig): {p.name}")
                continue
            text = "\n".join(pp.text for pp in paras)
            con.execute("INSERT INTO compliance_reports(file_name, text) VALUES (?, ?)", (p.name, text))
            con.executemany(
                "INSERT INTO compliance_report_paragraphs(file_name, para_index, text) VALUES (?, ?, ?)",
                [(pp.doc_name, pp.index, pp.text) for pp in paras],
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
    if not sikos_dir.exists():
        raise FileNotFoundError(f"sikos_dir not found: {sikos_dir}")
    files = _iter_docx_files(sikos_dir)
    con = _get_db_connection(db_path)
    try:
        total = len(files)
        for i, p in enumerate(files, start=1):
            con.execute("DELETE FROM compliance_siko_paragraphs WHERE doc_name = ?", (p.name,))
            try:
                paras = extract_docx_paragraphs(p)
            except (ValueError, OSError, Exception) as e:
                if progress:
                    progress(i, total, f"SKIP (ungueltig): {p.name}")
                continue
            con.executemany(
                "INSERT INTO compliance_siko_paragraphs(doc_name, para_index, text) VALUES (?, ?, ?)",
                [(pp.doc_name, pp.index, pp.text) for pp in paras],
            )
            if progress:
                progress(i, total, p.name)
        con.commit()
    finally:
        con.close()


def fetch_report_texts(db_path: Path, limit: int = 50000) -> List[Dict]:
    con = _get_db_connection(db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute("SELECT file_name, text FROM compliance_reports LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def fetch_siko_paragraphs(db_path: Path, limit: int = 50000) -> List[Dict]:
    con = _get_db_connection(db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute("SELECT doc_name, para_index, text FROM compliance_siko_paragraphs LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def upsert_assessment(db_path: Path, data: Dict, *, answer_file: str | None = None) -> None:
    """Insert/update one assessment into the DB.

    We treat answer_file as a stable identifier; if provided, we replace prior rows for it.
    """
    import json

    con = _get_db_connection(db_path)
    try:
        if answer_file:
            con.execute("DELETE FROM compliance_assessments WHERE answer_file = ?", (answer_file,))

        quellen = data.get("quellen")
        if isinstance(quellen, list):
            quellen_json = json.dumps(quellen, ensure_ascii=False)
        else:
            quellen_json = None

        raw_score = data.get("risikowert")
        score = int(raw_score) if raw_score not in (None, "") else None

        con.execute(
            """
            INSERT INTO compliance_assessments(
              answer_file,
              hersteller,
              cve_nummern,
              beschreibung_mitre,
              datum,
              zusammenfassung,
              stellungnahme,
              eintrittswahrscheinlichkeit,
              schadenspotenzial,
              risikowert,
              quellen_json,
              raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                answer_file,
                data.get("hersteller"),
                data.get("cve_nummern"),
                data.get("beschreibung_mitre"),
                data.get("datum"),
                data.get("zusammenfassung"),
                data.get("stellungnahme"),
                data.get("eintrittswahrscheinlichkeit"),
                data.get("schadenspotenzial"),
                score,
                quellen_json,
                json.dumps(data, ensure_ascii=False),
            ),
        )
        con.commit()
    finally:
        con.close()
