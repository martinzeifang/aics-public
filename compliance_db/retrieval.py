from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from shared.db_security import connect_sqlite


@dataclass
class SearchHit:
    rowid: int
    framework: str
    doc_name: str
    section_ref: str
    title: str
    snippet: str
    score: float


def _connect(p: Path) -> sqlite3.Connection:
    con = connect_sqlite(p, anchor=Path(__file__))
    con.row_factory = sqlite3.Row
    return con


def ensure_index_db(index_db: Path) -> None:
    con = _connect(index_db)
    try:
        con.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;

            CREATE VIRTUAL TABLE IF NOT EXISTS compliance_content
            USING fts5(
                source,
                framework,
                doc_name,
                section_ref,
                title,
                text
            );

            CREATE TABLE IF NOT EXISTS compliance_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        con.commit()
    finally:
        con.close()


def rebuild_index_from_gutachten(
    *,
    gutachten_db: Path,
    index_db: Path,
    progress: Callable[[int, int, str], None] | None = None,
) -> int:
    ensure_index_db(index_db)

    src = _connect(gutachten_db)
    dst = _connect(index_db)
    try:
        cur = src.execute(
            "SELECT COUNT(*) AS cnt FROM framework_sections"
        )
        total = int(cur.fetchone()["cnt"])
        if progress:
            progress(0, max(total, 1), "Lese framework_sections…")

        dst.execute("BEGIN")
        dst.execute("DELETE FROM compliance_content")

        c2 = src.execute(
            "SELECT framework, doc_name, section_ref, title, text FROM framework_sections ORDER BY id"
        )
        done = 0
        batch: list[tuple[str, str, str, str, str, str]] = []
        for row in c2.fetchall():
            batch.append(
                (
                    "gutachten.framework_sections",
                    str(row["framework"] or ""),
                    str(row["doc_name"] or ""),
                    str(row["section_ref"] or ""),
                    str(row["title"] or ""),
                    str(row["text"] or ""),
                )
            )
            if len(batch) >= 500:
                dst.executemany(
                    "INSERT INTO compliance_content (source, framework, doc_name, section_ref, title, text) VALUES (?,?,?,?,?,?)",
                    batch,
                )
                done += len(batch)
                batch.clear()
                if progress:
                    progress(done, max(total, 1), f"Indexiere… {done}/{total}")

        if batch:
            dst.executemany(
                "INSERT INTO compliance_content (source, framework, doc_name, section_ref, title, text) VALUES (?,?,?,?,?,?)",
                batch,
            )
            done += len(batch)

        dst.execute(
            "INSERT INTO compliance_meta(key,value) VALUES('last_rebuild', datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
        )
        dst.execute(
            "INSERT INTO compliance_meta(key,value) VALUES('rows', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(done),),
        )
        dst.commit()
        if progress:
            progress(done, max(total, 1), "Index fertig")
        return done
    finally:
        try:
            src.close()
        finally:
            dst.close()


def _tokenize(user_q: str) -> list[str]:
    import re
    toks = re.findall(r"[A-Za-z0-9äöüÄÖÜß]+", user_q)
    return [t for t in toks if t][:12]


def _expand_compound(tok: str) -> list[str]:
    """Split a long German compound word at a Fugen-s junction.

    Two cases:
    - Double 's' (true Fugen-s): "Auslagerungssicherung" → strip one 's'
      → ["Auslagerung", "sicherung"]
    - Single 's': keep the 's' as the start of the right component
      → "Datensicherung" → ["Daten", "sicherung"]

    Words of 12 chars or fewer are returned unchanged (avoids splitting
    common short compounds like "Grundschutz" or "Datenschutz").
    Returns the original token in a list when no plausible split is found.
    """
    if len(tok) <= 12:
        return [tok]
    tok_l = tok.lower()

    # Prefer double-s (most reliable Fugen-s indicator).
    for i in range(4, len(tok) - 5):
        if tok_l[i] == "s" and tok_l[i + 1] == "s":
            left, right = tok[:i], tok[i + 1:]   # strip one 's'
            if len(left) >= 4 and len(right) >= 4:
                return [left, right]

    # Single 's': keep 's' as the start of the right part.
    for i in range(4, len(tok) - 4):
        if tok_l[i] == "s":
            left, right = tok[:i], tok[i:]        # keep 's'
            if len(left) >= 4 and len(right) >= 4:
                return [left, right]

    return [tok]


def _dedup(lst: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for x in lst:
        xl = x.lower()
        if xl not in seen:
            seen.add(xl)
            out.append(x)
    return out


def _build_fts_queries(user_q: str) -> list[tuple[str, str]]:
    """Return a list of (fts5_query, label) pairs, from strictest to most lenient.

    Three strategies are tried in order:
    1. AND of all original tokens with prefix matching (current default).
    2. AND where each compound token is expanded to an OR-group:
       ``(original* OR left* OR right*) AND other_token*``
       This expands compound words without breaking non-compound tokens.
    3. OR of all tokens including expanded sub-parts (broadest fallback).
    """
    toks = _tokenize(user_q)
    if not toks:
        return []

    tok_parts: list[tuple[str, list[str]]] = [(t, _expand_compound(t)) for t in toks]
    has_expansion = any(parts != [t] for t, parts in tok_parts)

    queries: list[tuple[str, str]] = []

    # Strategy 1 – strict AND on original tokens.
    q1 = " AND ".join(t + "*" for t in _dedup(toks))
    queries.append((q1, "strikt"))

    if has_expansion:
        # Strategy 2 – AND with per-token OR-groups for compounds.
        # e.g.: (Auslagerungssicherung* OR Auslagerung* OR sicherung*) AND IT* AND Grundschutz*
        parts2: list[str] = []
        for orig, parts in tok_parts:
            if parts == [orig]:
                parts2.append(orig + "*")
            else:
                variants = _dedup([orig] + [p for p in parts if p.lower() != orig.lower()])
                group = " OR ".join(v + "*" for v in variants)
                parts2.append(f"({group})")
        q2 = " AND ".join(parts2)
        if q2 != q1:
            queries.append((q2, "Komposita-Split"))

    # Strategy 3 – OR of all tokens including expanded sub-parts.
    all_toks: list[str] = []
    for orig, parts in tok_parts:
        all_toks.append(orig)
        for p in parts:
            if p.lower() != orig.lower():
                all_toks.append(p)
    q3 = " OR ".join(t + "*" for t in _dedup(all_toks))
    if q3 not in (q for q, _ in queries):
        queries.append((q3, "OR-Fallback"))

    return queries


def _run_fts(
    con: sqlite3.Connection,
    fts_q: str,
    frameworks: list[str] | None,
    limit: int,
) -> list[SearchHit]:
    where = "compliance_content MATCH ?"
    args: list = [fts_q]
    if frameworks:
        placeholders = ",".join("?" for _ in frameworks)
        where += f" AND framework IN ({placeholders})"
        args.extend(frameworks)
    try:
        cur = con.execute(
            f"""
            SELECT
                rowid,
                framework,
                doc_name,
                section_ref,
                title,
                snippet(compliance_content, 5, '[', ']', '…', 24) AS snip,
                bm25(compliance_content, 0, 0, 0, 5, 10, 1) AS score
            FROM compliance_content
            WHERE {where}
            ORDER BY score
            LIMIT ?
            """,
            args + [int(limit)],
        )
    except sqlite3.OperationalError:
        # Malformed FTS5 query (e.g. stray punctuation) – return empty.
        return []
    hits: list[SearchHit] = []
    for r in cur.fetchall():
        hits.append(
            SearchHit(
                rowid=int(r["rowid"]),
                framework=str(r["framework"] or ""),
                doc_name=str(r["doc_name"] or ""),
                section_ref=str(r["section_ref"] or ""),
                title=str(r["title"] or ""),
                snippet=str(r["snip"] or ""),
                score=float(r["score"] or 0.0),
            )
        )
    return hits


# Minimum number of hits from the strict AND query before we skip fallbacks.
_MIN_STRICT_HITS = 3


def search(
    *,
    index_db: Path,
    query: str,
    frameworks: list[str] | None = None,
    limit: int = 50,
) -> tuple[list[SearchHit], str]:
    """Search the compliance index.

    Returns ``(hits, info)`` where *info* is a human-readable string that
    describes which search strategy produced the results.
    """
    ensure_index_db(index_db)
    strategies = _build_fts_queries(query)
    if not strategies:
        return [], "Keine Suchbegriffe"

    con = _connect(index_db)
    try:
        seen: set[int] = set()
        result: list[SearchHit] = []
        used_label = ""

        for i, (fts_q, label) in enumerate(strategies):
            hits = _run_fts(con, fts_q, frameworks, limit)
            new_hits = [h for h in hits if h.rowid not in seen]
            for h in new_hits:
                seen.add(h.rowid)
                result.append(h)

            if i == 0:
                used_label = label
                # Strict query returned enough → skip fallbacks.
                if len(result) >= _MIN_STRICT_HITS:
                    break
            else:
                if new_hits:
                    used_label = label if not result or i == len(strategies) - 1 else used_label + f" + {label}"

        # Sort by BM25 score (more-negative = better match).
        result.sort(key=lambda h: h.score)
        result = result[:limit]

        info = f"{len(result)} Treffer ({used_label})"
        return result, info
    finally:
        con.close()


def fetch_text(index_db: Path, rowid: int) -> str:
    con = _connect(index_db)
    try:
        cur = con.execute(
            "SELECT text FROM compliance_content WHERE rowid=?",
            (int(rowid),),
        )
        row = cur.fetchone()
        return str(row["text"] or "") if row else ""
    finally:
        con.close()


def list_frameworks(index_db: Path) -> list[str]:
    ensure_index_db(index_db)
    con = _connect(index_db)
    try:
        cur = con.execute(
            "SELECT DISTINCT framework AS fw FROM compliance_content WHERE framework<>'' ORDER BY fw"
        )
        return [str(r["fw"]) for r in cur.fetchall()]
    finally:
        con.close()
