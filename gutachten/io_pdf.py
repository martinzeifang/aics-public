"""PDF-Text-Extraktion für Regulierungstexte (DORA, NIS2, CRA).

Strategie: pdfplumber für saubere Textextraktion, Seiten-Chunking mit
Artikel/Kapitel-Erkennung via Regex.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional


# Regex-Muster für EU-Regulierungstexte (deutsch) und ISO-Strukturen
_ARTIKEL_RE = re.compile(
    r"^\s*(?:Artikel|Kapitel|Abschnitt|Anhang|Erwägungsgrund|Section|Chapter|Annex)\s+"
    r"(?:[IVXLC]+|\d+[a-z]?)\b",
    re.IGNORECASE | re.MULTILINE,
)

_TITEL_RE = re.compile(
    r"^\s*(?:Artikel|Kapitel|Abschnitt|Anhang|Erwägungsgrund|Section|Chapter|Annex)\s+"
    r"(?:[IVXLC]+|\d+[a-z]?)\s*\n?(.{0,120})",
    re.IGNORECASE,
)

_MAX_CHUNK_CHARS = 3000
_MIN_SECTION_CHARS = 100


def extract_sections(
    pdf_path: Path,
    progress: Optional[Callable[[int, int], None]] = None,
) -> list[dict[str, str]]:
    """Extrahiert Text-Abschnitte aus einem PDF.

    Gibt eine Liste von Dicts zurück:
        {"section_ref": str, "title": str, "text": str}

    Fällt pdfplumber nicht zur Verfügung, wird pypdf als Fallback versucht.
    """
    text = _extract_full_text(pdf_path, progress=progress)
    if not text.strip():
        return []
    return _split_into_sections(text, pdf_path.name)


def _extract_full_text(
    pdf_path: Path,
    progress: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Extrahiert den vollständigen Text aus dem PDF."""
    try:
        import pdfplumber  # type: ignore
        return _extract_pdfplumber(pdf_path, progress=progress)
    except ImportError:
        pass
    try:
        import pypdf  # type: ignore
        return _extract_pypdf(pdf_path, progress=progress)
    except ImportError:
        pass
    raise RuntimeError(
        "Kein PDF-Parser verfügbar. Bitte 'pdfplumber' installieren: pip install pdfplumber"
    )


def _extract_pdfplumber(
    pdf_path: Path,
    progress: Optional[Callable[[int, int], None]] = None,
) -> str:
    import pdfplumber  # type: ignore

    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            txt = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            pages.append(txt)
            if progress:
                progress(i + 1, total)
    return "\n".join(pages)


def _extract_pypdf(
    pdf_path: Path,
    progress: Optional[Callable[[int, int], None]] = None,
) -> str:
    import pypdf  # type: ignore

    pages: list[str] = []
    with open(str(pdf_path), "rb") as f:
        reader = pypdf.PdfReader(f)
        total = len(reader.pages)
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            pages.append(txt)
            if progress:
                progress(i + 1, total)
    return "\n".join(pages)


def _split_into_sections(text: str, doc_name: str) -> list[dict[str, str]]:
    """Teilt Volltext in Abschnitte auf anhand von Artikel/Kapitel-Grenzen."""
    # Finde alle Trennstellen
    splits = [(m.start(), m.group().strip()) for m in _ARTIKEL_RE.finditer(text)]

    if not splits:
        # Kein strukturierter Text – in Seiten-große Chunks aufteilen
        return _chunk_plain(text, doc_name)

    sections: list[dict[str, str]] = []

    # Text vor erstem Artikel (Präambel)
    if splits[0][0] > _MIN_SECTION_CHARS:
        preface = text[: splits[0][0]].strip()
        if preface:
            sections.append({
                "section_ref": "Präambel",
                "title": "Einleitung / Erwägungsgründe",
                "text": preface[:_MAX_CHUNK_CHARS],
            })

    for idx, (start, ref_text) in enumerate(splits):
        end = splits[idx + 1][0] if idx + 1 < len(splits) else len(text)
        chunk = text[start:end].strip()

        if len(chunk) < _MIN_SECTION_CHARS:
            continue

        # Titel: erste nicht-leere Zeile nach der Referenz
        lines = chunk.splitlines()
        section_ref = lines[0].strip() if lines else ref_text
        title = ""
        for line in lines[1:4]:
            stripped = line.strip()
            if stripped and not stripped[0].isdigit():
                title = stripped[:120]
                break

        # Ggf. langen Chunk aufteilen
        if len(chunk) > _MAX_CHUNK_CHARS:
            sub_chunks = _subdivide(chunk, section_ref)
            sections.extend(sub_chunks)
        else:
            sections.append({
                "section_ref": section_ref,
                "title": title,
                "text": chunk,
            })

    return sections


def _subdivide(text: str, base_ref: str) -> list[dict[str, str]]:
    """Teilt einen zu langen Abschnitt in Unter-Chunks auf."""
    results: list[dict[str, str]] = []
    offset = 0
    part = 1
    while offset < len(text):
        # Versuche an Satzende zu trennen
        end = offset + _MAX_CHUNK_CHARS
        if end < len(text):
            # Suche letzten Satzabschluss im Fenster
            last_dot = text.rfind(".", offset, end)
            if last_dot > offset + _MAX_CHUNK_CHARS // 2:
                end = last_dot + 1
        chunk = text[offset:end].strip()
        if chunk:
            results.append({
                "section_ref": f"{base_ref} (Teil {part})",
                "title": "",
                "text": chunk,
            })
            part += 1
        offset = end
    return results


def _chunk_plain(text: str, doc_name: str) -> list[dict[str, str]]:
    """Einfaches Chunking für Dokumente ohne erkannte Struktur."""
    chunks: list[dict[str, str]] = []
    offset = 0
    part = 1
    while offset < len(text):
        end = offset + _MAX_CHUNK_CHARS
        if end < len(text):
            last_nl = text.rfind("\n", offset, end)
            if last_nl > offset:
                end = last_nl
        chunk = text[offset:end].strip()
        if len(chunk) >= _MIN_SECTION_CHARS:
            chunks.append({
                "section_ref": f"Abschnitt {part}",
                "title": "",
                "text": chunk,
            })
            part += 1
        offset = end
    return chunks


# ── Verzeichnis-Ingest ────────────────────────────────────────────────────────

FRAMEWORK_DIRS: dict[str, str] = {
    "DORA":     "dora_dir",
    "NIS2":     "nis2_dir",
    "CRA":      "cra_dir",
    "ISO27001": "iso_dir",
    "DSGVO":    "dsgvo_dir",
    "AI_ACT":   "ai_act_dir",
    "BSI":      "bsi_dir",
}


def ingest_framework_dir(
    framework: str,
    dir_path: Path,
    db_path: Path,
    progress: Optional[Callable[[str, int, int], None]] = None,
) -> tuple[int, list[str]]:
    """Liest alle PDFs (und XLSX für ISO) aus einem Verzeichnis und speichert sie in der DB.

    Gibt (Anzahl_Abschnitte, Liste_von_Fehlermeldungen) zurück.
    """
    from .db import ingest_sections, ensure_db

    ensure_db(db_path)

    pdf_files = sorted(dir_path.glob("*.pdf"))
    total = len(pdf_files)
    total_sections = 0
    errors: list[str] = []

    for i, pdf in enumerate(pdf_files, start=1):
        if progress:
            progress(pdf.name, i, total)
        try:
            sections = extract_sections(pdf)
            n = ingest_sections(db_path, framework, pdf.name, sections)
            total_sections += n
        except Exception as e:
            errors.append(f"{pdf.name}: {e}")

    return total_sections, errors
