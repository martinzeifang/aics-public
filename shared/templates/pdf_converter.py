"""DOCX→PDF-Konversion (#990 / #1032).

Primär über einen **separaten Gotenberg-Container** (HTTP-API) — so bleibt das
App-Image schlank und LibreOffice muss nicht bei jedem App-Update gezogen werden.
Fallback auf lokales ``soffice`` (Entwicklungsmaschine), falls Gotenberg nicht
erreichbar ist und LibreOffice lokal installiert ist.

Konfiguration über ``GOTENBERG_URL`` (Default ``http://gotenberg:3000``).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class PDFConversionError(Exception):
    """Basisklasse für PDF-Konversionsfehler."""


class PDFConversionUnavailable(PDFConversionError):
    """Weder Gotenberg erreichbar noch lokales LibreOffice installiert."""


class PDFConversionTimeout(PDFConversionError):
    """Die Konversion hat das Zeitlimit überschritten."""


class PDFConversionFailed(PDFConversionError):
    """Der Konverter brach mit einem Fehler ab."""


def gotenberg_url() -> str:
    return os.environ.get("GOTENBERG_URL", "http://gotenberg:3000").rstrip("/")


def is_gotenberg_available(timeout_s: int = 3) -> bool:
    try:
        import requests
        r = requests.get(f"{gotenberg_url()}/health", timeout=timeout_s)
        return r.status_code == 200
    except Exception:
        return False


def is_soffice_available() -> bool:
    """Kompat-Name: True, wenn überhaupt PDF erzeugt werden kann
    (Gotenberg erreichbar ODER lokales soffice vorhanden)."""
    return is_gotenberg_available() or shutil.which("soffice") is not None


def _convert_via_gotenberg(docx_bytes: bytes, *, timeout_s: int) -> bytes:
    import requests
    url = f"{gotenberg_url()}/forms/libreoffice/convert"
    files = {"files": ("input.docx", docx_bytes, _DOCX_MIME)}
    try:
        resp = requests.post(url, files=files, timeout=timeout_s)
    except requests.Timeout as exc:
        raise PDFConversionTimeout(f"Gotenberg > {timeout_s}s") from exc
    except requests.RequestException as exc:
        # Verbindungsfehler → vom Aufrufer als „nicht erreichbar" behandelt
        raise ConnectionError(str(exc)) from exc
    if resp.status_code != 200:
        raise PDFConversionFailed(
            f"Gotenberg HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.content


def _convert_via_local_soffice(docx_bytes: bytes, *, timeout_s: int) -> bytes:
    if not shutil.which("soffice"):
        raise PDFConversionUnavailable("Gotenberg nicht erreichbar und kein lokales LibreOffice")
    try:
        from server.api.workspace_tmp import workspace_tmpdir
        tmp_root = Path(workspace_tmpdir())
    except Exception:
        tmp_root = Path("data/tmp"); tmp_root.mkdir(parents=True, exist_ok=True)
    work = tmp_root / f"pdfconv_{uuid.uuid4().hex}"
    work.mkdir(parents=True, exist_ok=True)
    infile = work / "input.docx"
    try:
        infile.write_bytes(docx_bytes)
        try:
            proc = subprocess.run(
                ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(work), str(infile)],
                capture_output=True, timeout=timeout_s,
                env={"HOME": str(work), "PATH": "/usr/bin:/bin:/usr/local/bin"})
        except subprocess.TimeoutExpired as exc:
            raise PDFConversionTimeout(f"soffice > {timeout_s}s") from exc
        if proc.returncode != 0:
            raise PDFConversionFailed(
                f"soffice exit {proc.returncode}: {(proc.stderr or b'').decode('utf-8','replace')[:300]}")
        pdf = work / "input.pdf"
        if not pdf.exists():
            raise PDFConversionFailed("soffice erzeugte keine PDF-Datei")
        return pdf.read_bytes()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def convert_docx_to_pdf(docx_bytes: bytes, *, timeout_s: int = 60) -> bytes:
    """Konvertiert DOCX→PDF. Primär Gotenberg, Fallback lokales soffice."""
    try:
        return _convert_via_gotenberg(docx_bytes, timeout_s=timeout_s)
    except ConnectionError:
        # Gotenberg nicht erreichbar → lokaler Fallback (oder Unavailable)
        return _convert_via_local_soffice(docx_bytes, timeout_s=timeout_s)
