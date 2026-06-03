"""#990 — PDF-Konversion via LibreOffice headless."""
import io

import pytest
from docx import Document

from shared.templates import pdf_converter as pc


def _docx_bytes(text="Hello PDF"):
    d = Document(); d.add_paragraph(text)
    buf = io.BytesIO(); d.save(buf)
    return buf.getvalue()


def test_is_soffice_available_returns_bool():
    assert isinstance(pc.is_soffice_available(), bool)


@pytest.mark.skipif(not pc.is_soffice_available(), reason="LibreOffice nicht installiert")
def test_convert_produces_pdf():
    pdf = pc.convert_docx_to_pdf(_docx_bytes("Konvertierungstest"))
    assert pdf[:4] == b"%PDF"


def test_unavailable_raises(monkeypatch):
    monkeypatch.setattr(pc.shutil, "which", lambda _x: None)
    with pytest.raises(pc.PDFConversionUnavailable):
        pc.convert_docx_to_pdf(_docx_bytes())


def test_timeout_raises(monkeypatch):
    monkeypatch.setattr(pc.shutil, "which", lambda _x: "/usr/bin/soffice")
    import subprocess

    def _boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="soffice", timeout=1)
    monkeypatch.setattr(pc.subprocess, "run", _boom)
    with pytest.raises(pc.PDFConversionTimeout):
        pc.convert_docx_to_pdf(_docx_bytes(), timeout_s=1)
