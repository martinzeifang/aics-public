from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document

from security_utils import MAX_DOCX_PARAGRAPHS, validate_office_archive


@dataclass(frozen=True)
class DocxParagraph:
    doc_name: str
    index: int
    text: str


def extract_docx_paragraphs(docx_path: Path) -> list[DocxParagraph]:
    validate_office_archive(docx_path, expected_suffix=".docx")
    doc = Document(str(docx_path))
    out: list[DocxParagraph] = []
    idx = 0
    for p in doc.paragraphs:
        if idx >= MAX_DOCX_PARAGRAPHS:
            raise ValueError(f"DOCX exceeds safe paragraph limit: {docx_path.name}")
        t = (p.text or "").strip()
        if not t:
            continue
        out.append(DocxParagraph(doc_name=docx_path.name, index=idx, text=t))
        idx += 1
    return out
