"""DOCX→PDF-Konversion via LibreOffice headless (#990).

Synchron mit Timeout. Fehlerfälle als typisierte Exceptions, die der REST-Layer
auf 503/504/500 abbildet.
"""
from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path


class PDFConversionError(Exception):
    """Basisklasse für PDF-Konversionsfehler."""


class PDFConversionUnavailable(PDFConversionError):
    """LibreOffice (soffice) ist nicht installiert."""


class PDFConversionTimeout(PDFConversionError):
    """Die Konversion hat das Zeitlimit überschritten."""


class PDFConversionFailed(PDFConversionError):
    """soffice ist mit einem Fehler abgebrochen."""


def is_soffice_available() -> bool:
    return shutil.which("soffice") is not None


def _tmp_root() -> Path:
    try:
        from server.api.workspace_tmp import workspace_tmpdir
        return Path(workspace_tmpdir())
    except Exception:
        root = Path("data/tmp")
        root.mkdir(parents=True, exist_ok=True)
        return root


def convert_docx_to_pdf(docx_bytes: bytes, *, timeout_s: int = 60) -> bytes:
    """Konvertiert DOCX-Bytes nach PDF-Bytes. Raises PDFConversion*-Fehler."""
    if not is_soffice_available():
        raise PDFConversionUnavailable("LibreOffice (soffice) ist nicht installiert")

    work = _tmp_root() / f"pdfconv_{uuid.uuid4().hex}"
    work.mkdir(parents=True, exist_ok=True)
    infile = work / "input.docx"
    try:
        infile.write_bytes(docx_bytes)
        try:
            proc = subprocess.run(
                ["soffice", "--headless", "--convert-to", "pdf",
                 "--outdir", str(work), str(infile)],
                capture_output=True, timeout=timeout_s,
                env={"HOME": str(work), "PATH": "/usr/bin:/bin:/usr/local/bin"},
            )
        except subprocess.TimeoutExpired as exc:
            raise PDFConversionTimeout(f"PDF-Konversion > {timeout_s}s") from exc
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", "replace")[:500]
            raise PDFConversionFailed(f"soffice exit {proc.returncode}: {err}")
        pdf = work / "input.pdf"
        if not pdf.exists():
            raise PDFConversionFailed("soffice erzeugte keine PDF-Datei")
        return pdf.read_bytes()
    finally:
        shutil.rmtree(work, ignore_errors=True)
