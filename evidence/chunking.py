from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceChunk:
    idx: int
    text: str


def chunk_text(text: str, *, max_chars: int = 1800) -> list[EvidenceChunk]:
    """Deterministically chunk plain text for retrieval/citation.

    Strategy:
    - Split into paragraphs (blank-line separated)
    - Pack paragraphs into chunks up to max_chars
    - If a paragraph exceeds max_chars, hard-split it
    """

    t = (text or "").strip()
    if not t:
        return []

    paragraphs = [p.strip() for p in t.split("\n\n")]
    paragraphs = [p for p in paragraphs if p]

    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0

    def flush() -> None:
        nonlocal cur, cur_len
        if cur:
            chunks.append("\n\n".join(cur).strip())
        cur = []
        cur_len = 0

    for p in paragraphs:
        if len(p) > max_chars:
            # Flush current chunk first.
            flush()
            start = 0
            while start < len(p):
                part = p[start : start + max_chars]
                chunks.append(part.strip())
                start += max_chars
            continue

        add_len = len(p) + (2 if cur else 0)
        if cur and cur_len + add_len > max_chars:
            flush()
        cur.append(p)
        cur_len += add_len

    flush()

    out: list[EvidenceChunk] = []
    for i, c in enumerate(chunks, start=1):
        if c:
            out.append(EvidenceChunk(idx=i, text=c))
    return out
