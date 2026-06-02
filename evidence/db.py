from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.db_security import connect_sqlite
from ai_compliance_suite.config import load_config as _load_suite_config
from shared.crypto_at_rest import EncryptionConfig, encrypt_bytes


DEFAULT_DB_PATH = Path("data/db/evidence.sqlite")
DEFAULT_STORE_DIR = Path("data/evidence")


@dataclass
class EvidenceDocument:
    id: str
    filename: str
    stored_path: str
    source_path: str | None
    doc_type: str
    owner: str
    version: str
    tags: list[str]
    added_at: int
    updated_at: int
    doc_kind: str = "file"   # "file" | "web"
    url: str | None = None
    kunden_id: str = ""


@dataclass
class EvidenceChunkRow:
    doc_id: str
    chunk_idx: int
    text: str
    citation: dict[str, Any]
    created_at: int


@dataclass
class ApprovedMappingRow:
    requirement_id: str
    claim: str
    citations: list[dict[str, Any]]
    confidence: float
    rationale: str
    approved_by: str
    approved_at: int
    kunden_id: str = ""


def ensure_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence_documents (
              id          TEXT PRIMARY KEY,
              filename    TEXT NOT NULL,
              stored_path TEXT NOT NULL,
              source_path TEXT,
              doc_type    TEXT NOT NULL DEFAULT '',
              owner       TEXT NOT NULL DEFAULT '',
              version     TEXT NOT NULL DEFAULT '',
              tags_json   TEXT NOT NULL DEFAULT '[]',
              added_at    INTEGER NOT NULL,
              updated_at  INTEGER NOT NULL
            );
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_ev_updated ON evidence_documents(updated_at DESC);")

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence_text (
              doc_id       TEXT PRIMARY KEY,
              text         TEXT NOT NULL,
              extracted_at INTEGER NOT NULL
            );
            """
        )

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence_chunks (
              doc_id        TEXT NOT NULL,
              chunk_idx     INTEGER NOT NULL,
              text          TEXT NOT NULL,
              citation_json TEXT NOT NULL,
              created_at    INTEGER NOT NULL,
              PRIMARY KEY (doc_id, chunk_idx)
            );
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_ev_chunks_doc ON evidence_chunks(doc_id, chunk_idx);")

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence_mappings_approved (
              requirement_id TEXT NOT NULL,
              claim          TEXT NOT NULL,
              citations_json TEXT NOT NULL,
              confidence     REAL NOT NULL,
              rationale      TEXT NOT NULL,
              approved_by    TEXT NOT NULL,
              approved_at    INTEGER NOT NULL,
              PRIMARY KEY (requirement_id, claim)
            );
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_ev_map_req ON evidence_mappings_approved(requirement_id, approved_at DESC);"
        )

        # Migrations: add new columns if they don't exist yet
        for _col_sql in [
            "ALTER TABLE evidence_documents ADD COLUMN doc_kind TEXT NOT NULL DEFAULT 'file'",
            "ALTER TABLE evidence_documents ADD COLUMN url TEXT",
            "ALTER TABLE evidence_documents ADD COLUMN kunden_id TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE evidence_mappings_approved ADD COLUMN kunden_id TEXT NOT NULL DEFAULT ''",
        ]:
            try:
                con.execute(_col_sql)
            except sqlite3.OperationalError:
                pass  # column already exists

        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_ev_kunden ON evidence_documents(kunden_id, updated_at DESC);"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_ev_map_kunden ON evidence_mappings_approved(kunden_id, requirement_id, approved_at DESC);"
        )


def _now_ts() -> int:
    return int(time.time())


def _safe_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return []
    out: list[str] = []
    for t in tags:
        s = str(t).strip()
        if s:
            out.append(s)
    seen: set[str] = set()
    dedup: list[str] = []
    for t in out:
        if t not in seen:
            dedup.append(t)
            seen.add(t)
    return dedup


def add_document(
    db_path: Path,
    source_file: Path,
    *,
    store_dir: Path = DEFAULT_STORE_DIR,
    doc_type: str = "",
    owner: str = "",
    version: str = "",
    tags: list[str] | None = None,
    copy_into_store: bool = True,
    kunden_id: str = "",
) -> EvidenceDocument:
    ensure_db(db_path)
    store_dir.mkdir(parents=True, exist_ok=True)

    src = Path(source_file)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(str(src))

    doc_id = str(uuid.uuid4())
    filename = src.name

    if copy_into_store:
        stored_name = f"{doc_id}_{filename}"
        dst = store_dir / stored_name

        # Optional at-rest encryption for evidence files
        try:
            cfg = _load_suite_config()
            sec = cfg.get("security", {}) if isinstance(cfg, dict) else {}
            at = sec.get("at_rest_encryption", {}) if isinstance(sec, dict) else {}
            enc_cfg = EncryptionConfig(
                enabled=bool(at.get("enabled", False)),
                key_env=str(at.get("key_env", "AICS_AT_REST_KEY")),
                encrypt_backups=bool(at.get("encrypt_backups", True)),
                encrypt_evidence=bool(at.get("encrypt_evidence", False)),
            )
        except Exception:
            enc_cfg = EncryptionConfig(enabled=False, key_env="AICS_AT_REST_KEY")

        if enc_cfg.enabled and enc_cfg.encrypt_evidence:
            blob = encrypt_bytes(src.read_bytes(), key_env=enc_cfg.key_env)
            dst_enc = dst.with_suffix(dst.suffix + ".enc")
            dst_enc.write_bytes(blob)
            stored_path = str(dst_enc.as_posix())
            source_path = str(src)
        else:
            shutil.copy2(str(src), str(dst))
            stored_path = str(dst.as_posix())
            source_path = str(src)
    else:
        stored_path = str(src)
        source_path = None

    ts = _now_ts()
    tags_json = json.dumps(_safe_tags(tags or []), ensure_ascii=False)

    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.execute(
            """
            INSERT INTO evidence_documents (
              id, filename, stored_path, source_path, doc_type, owner, version,
              tags_json, added_at, updated_at, kunden_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, filename, stored_path, source_path, doc_type or "", owner or "",
             version or "", tags_json, ts, ts, kunden_id or ""),
        )

    return EvidenceDocument(
        id=doc_id,
        filename=filename,
        stored_path=stored_path,
        source_path=source_path,
        doc_type=doc_type or "",
        owner=owner or "",
        version=version or "",
        tags=_safe_tags(tags or []),
        added_at=ts,
        updated_at=ts,
        kunden_id=kunden_id or "",
    )


def add_web_document(
    db_path: Path,
    url: str,
    title: str,
    text: str,
    *,
    doc_type: str = "web",
    owner: str = "",
    version: str = "",
    tags: list[str] | None = None,
    kunden_id: str = "",
) -> EvidenceDocument:
    """Register a web page as an evidence document and persist its text."""
    ensure_db(db_path)
    from urllib.parse import urlparse as _up
    hostname = _up(url).netloc or url[:60]
    filename = f"{hostname} – {title[:60]}" if title else hostname

    doc_id = str(uuid.uuid4())
    ts = _now_ts()
    tags_json = json.dumps(_safe_tags(tags or ["web"]), ensure_ascii=False)

    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.execute(
            """
            INSERT INTO evidence_documents
              (id, filename, stored_path, source_path, doc_type, owner, version,
               tags_json, added_at, updated_at, doc_kind, url, kunden_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'web', ?, ?)
            """,
            (doc_id, filename, "", None, doc_type or "web", owner or "", version or "",
             tags_json, ts, ts, url, kunden_id or ""),
        )
        con.execute(
            "INSERT OR REPLACE INTO evidence_text (doc_id, text, extracted_at) VALUES (?, ?, ?)",
            (doc_id, text, ts),
        )

    return EvidenceDocument(
        id=doc_id,
        filename=filename,
        stored_path="",
        source_path=None,
        doc_type=doc_type or "web",
        owner=owner or "",
        version=version or "",
        tags=_safe_tags(tags or ["web"]),
        added_at=ts,
        updated_at=ts,
        doc_kind="web",
        url=url,
        kunden_id=kunden_id or "",
    )


def list_documents(db_path: Path, *, kunden_id: str | None = None) -> list[EvidenceDocument]:
    """List evidence documents. Pass kunden_id to restrict to a specific customer."""
    ensure_db(db_path)
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.row_factory = sqlite3.Row
        if kunden_id is not None:
            rows = con.execute(
                "SELECT * FROM evidence_documents WHERE kunden_id=? ORDER BY updated_at DESC, filename ASC",
                (kunden_id,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM evidence_documents ORDER BY updated_at DESC, filename ASC"
            ).fetchall()
    out: list[EvidenceDocument] = []
    for r in rows:
        try:
            tags = json.loads(r["tags_json"]) if r["tags_json"] else []
        except Exception:
            tags = []
        keys = r.keys()
        out.append(
            EvidenceDocument(
                id=str(r["id"]),
                filename=str(r["filename"]),
                stored_path=str(r["stored_path"]),
                source_path=str(r["source_path"]) if r["source_path"] else None,
                doc_type=str(r["doc_type"] or ""),
                owner=str(r["owner"] or ""),
                version=str(r["version"] or ""),
                tags=_safe_tags(tags),
                added_at=int(r["added_at"]),
                updated_at=int(r["updated_at"]),
                doc_kind=str(r["doc_kind"]) if "doc_kind" in keys else "file",
                url=str(r["url"]) if "url" in keys and r["url"] else None,
                kunden_id=str(r["kunden_id"]) if "kunden_id" in keys and r["kunden_id"] else "",
            )
        )
    return out


def update_document_metadata(
    db_path: Path,
    doc_id: str,
    *,
    doc_type: str | None = None,
    owner: str | None = None,
    version: str | None = None,
    tags: list[str] | None = None,
) -> None:
    ensure_db(db_path)
    ts = _now_ts()
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        row = con.execute("SELECT id FROM evidence_documents WHERE id=?", (doc_id,)).fetchone()
        if not row:
            raise KeyError(doc_id)
        if tags is not None:
            tags_json = json.dumps(_safe_tags(tags), ensure_ascii=False)
            con.execute(
                "UPDATE evidence_documents SET tags_json=?, updated_at=? WHERE id=?",
                (tags_json, ts, doc_id),
            )
        for col, val in [("doc_type", doc_type), ("owner", owner), ("version", version)]:
            if val is not None:
                con.execute(
                    f"UPDATE evidence_documents SET {col}=?, updated_at=? WHERE id=?",
                    (str(val), ts, doc_id),
                )


def delete_document(db_path: Path, doc_id: str, *, delete_file: bool = True) -> None:
    ensure_db(db_path)
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        row = con.execute(
            "SELECT stored_path FROM evidence_documents WHERE id=?", (doc_id,)
        ).fetchone()
        if not row:
            return
        stored_path = str(row[0])
        con.execute("DELETE FROM evidence_documents WHERE id=?", (doc_id,))
        con.execute("DELETE FROM evidence_text WHERE doc_id=?", (doc_id,))
        con.execute("DELETE FROM evidence_chunks WHERE doc_id=?", (doc_id,))

    if delete_file:
        try:
            p = Path(stored_path)
            if p.exists() and p.is_file():
                os.remove(str(p))
        except Exception:
            pass


def upsert_extracted_text(db_path: Path, doc_id: str, text: str) -> None:
    ensure_db(db_path)
    ts = _now_ts()
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.execute(
            """
            INSERT INTO evidence_text (doc_id, text, extracted_at)
            VALUES (?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
              text=excluded.text,
              extracted_at=excluded.extracted_at
            """,
            (doc_id, text or "", ts),
        )
        con.execute("UPDATE evidence_documents SET updated_at=? WHERE id=?", (ts, doc_id))


def get_extracted_text(db_path: Path, doc_id: str) -> str | None:
    ensure_db(db_path)
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        row = con.execute("SELECT text FROM evidence_text WHERE doc_id=?", (doc_id,)).fetchone()
    return str(row[0]) if row else None


def replace_chunks(
    db_path: Path,
    doc_id: str,
    chunks: list[tuple[int, str]],
    *,
    citation_kind: str = "chunk",
) -> None:
    """Replace stored chunks for a document."""
    ensure_db(db_path)
    ts = _now_ts()
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.execute("DELETE FROM evidence_chunks WHERE doc_id=?", (doc_id,))
        for idx, text in chunks:
            citation = {"kind": citation_kind, "doc_id": doc_id, "chunk": int(idx)}
            con.execute(
                """
                INSERT INTO evidence_chunks (doc_id, chunk_idx, text, citation_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (doc_id, int(idx), text or "", json.dumps(citation, ensure_ascii=False), ts),
            )
        con.execute("UPDATE evidence_documents SET updated_at=? WHERE id=?", (ts, doc_id))


def list_chunks(db_path: Path, doc_id: str) -> list[EvidenceChunkRow]:
    ensure_db(db_path)
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT doc_id, chunk_idx, text, citation_json, created_at FROM evidence_chunks WHERE doc_id=? ORDER BY chunk_idx ASC",
            (doc_id,),
        ).fetchall()
    out: list[EvidenceChunkRow] = []
    for r in rows:
        try:
            citation = json.loads(r["citation_json"]) if r["citation_json"] else {}
        except Exception:
            citation = {}
        out.append(
            EvidenceChunkRow(
                doc_id=str(r["doc_id"]),
                chunk_idx=int(r["chunk_idx"]),
                text=str(r["text"]),
                citation=citation if isinstance(citation, dict) else {},
                created_at=int(r["created_at"]),
            )
        )
    return out


def list_all_chunks(
    db_path: Path,
    *,
    limit: int = 800,
    kunden_id: str | None = None,
) -> list[EvidenceChunkRow]:
    """List chunks across all documents (most recently created first).

    Pass kunden_id to restrict to documents belonging to a specific customer.
    """
    ensure_db(db_path)
    lim = max(1, int(limit))
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.row_factory = sqlite3.Row
        if kunden_id is not None:
            rows = con.execute(
                """
                SELECT c.doc_id, c.chunk_idx, c.text, c.citation_json, c.created_at
                FROM evidence_chunks c
                JOIN evidence_documents d ON d.id = c.doc_id
                WHERE d.kunden_id = ?
                ORDER BY c.created_at DESC
                LIMIT ?
                """,
                (kunden_id, lim),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT doc_id, chunk_idx, text, citation_json, created_at FROM evidence_chunks ORDER BY created_at DESC LIMIT ?",
                (lim,),
            ).fetchall()
    out: list[EvidenceChunkRow] = []
    for r in rows:
        try:
            citation = json.loads(r["citation_json"]) if r["citation_json"] else {}
        except Exception:
            citation = {}
        out.append(
            EvidenceChunkRow(
                doc_id=str(r["doc_id"]),
                chunk_idx=int(r["chunk_idx"]),
                text=str(r["text"]),
                citation=citation if isinstance(citation, dict) else {},
                created_at=int(r["created_at"]),
            )
        )
    return out


def save_approved_mapping(
    db_path: Path,
    *,
    requirement_id: str,
    claim: str,
    citations: list[dict[str, Any]],
    confidence: float,
    rationale: str,
    approved_by: str,
    kunden_id: str = "",
) -> None:
    ensure_db(db_path)
    rid = (requirement_id or "").strip()
    cl = (claim or "").strip()
    if not rid or not cl:
        raise ValueError("requirement_id and claim are required")
    ts = _now_ts()
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.execute(
            """
            INSERT INTO evidence_mappings_approved (
              requirement_id, claim, citations_json, confidence, rationale,
              approved_by, approved_at, kunden_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(requirement_id, claim) DO UPDATE SET
              citations_json=excluded.citations_json,
              confidence=excluded.confidence,
              rationale=excluded.rationale,
              approved_by=excluded.approved_by,
              approved_at=excluded.approved_at,
              kunden_id=excluded.kunden_id
            """,
            (
                rid,
                cl,
                json.dumps(citations or [], ensure_ascii=False),
                float(confidence),
                str(rationale or ""),
                str(approved_by or ""),
                ts,
                kunden_id or "",
            ),
        )


def list_approved_mappings(
    db_path: Path,
    requirement_id: str,
    *,
    kunden_id: str | None = None,
) -> list[ApprovedMappingRow]:
    """List approved mappings for a requirement.

    Pass kunden_id to restrict to a specific customer's approvals.
    """
    ensure_db(db_path)
    rid = (requirement_id or "").strip()
    if not rid:
        return []
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.row_factory = sqlite3.Row
        if kunden_id is not None:
            rows = con.execute(
                """
                SELECT requirement_id, claim, citations_json, confidence, rationale,
                       approved_by, approved_at, kunden_id
                FROM evidence_mappings_approved
                WHERE requirement_id=? AND kunden_id=?
                ORDER BY approved_at DESC
                """,
                (rid, kunden_id),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT requirement_id, claim, citations_json, confidence, rationale,
                       approved_by, approved_at, kunden_id
                FROM evidence_mappings_approved
                WHERE requirement_id=?
                ORDER BY approved_at DESC
                """,
                (rid,),
            ).fetchall()
    out: list[ApprovedMappingRow] = []
    for r in rows:
        try:
            citations = json.loads(r["citations_json"]) if r["citations_json"] else []
        except Exception:
            citations = []
        keys = r.keys()
        out.append(
            ApprovedMappingRow(
                requirement_id=str(r["requirement_id"]),
                claim=str(r["claim"]),
                citations=citations if isinstance(citations, list) else [],
                confidence=float(r["confidence"]),
                rationale=str(r["rationale"]),
                approved_by=str(r["approved_by"]),
                approved_at=int(r["approved_at"]),
                kunden_id=str(r["kunden_id"]) if "kunden_id" in keys and r["kunden_id"] else "",
            )
        )
    return out


def delete_approved_mapping(db_path: Path, requirement_id: str, claim: str) -> None:
    ensure_db(db_path)
    rid = (requirement_id or "").strip()
    cl = (claim or "").strip()
    if not rid or not cl:
        return
    with connect_sqlite(db_path, anchor=Path(__file__)) as con:
        con.execute(
            "DELETE FROM evidence_mappings_approved WHERE requirement_id=? AND claim=?",
            (rid, cl),
        )
