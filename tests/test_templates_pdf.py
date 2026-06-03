"""#990/#1032 — PDF-Konversion via Gotenberg-Sidecar (+ lokaler soffice-Fallback)."""
import io

import pytest
import requests
from docx import Document

from shared.templates import pdf_converter as pc


def _docx_bytes(text="Hello PDF"):
    d = Document(); d.add_paragraph(text)
    buf = io.BytesIO(); d.save(buf)
    return buf.getvalue()


class _Resp:
    def __init__(self, status_code, content=b"", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text


def test_is_available_returns_bool():
    assert isinstance(pc.is_soffice_available(), bool)


def test_gotenberg_unreachable_health(monkeypatch):
    def _boom(*a, **k):
        raise requests.ConnectionError("nope")
    monkeypatch.setattr(requests, "get", _boom)
    assert pc.is_gotenberg_available() is False


def test_convert_via_gotenberg_success(monkeypatch):
    def _post(url, files=None, timeout=None):
        assert "/forms/libreoffice/convert" in url
        return _Resp(200, content=b"%PDF-1.7 fake")
    monkeypatch.setattr(requests, "post", _post)
    out = pc.convert_docx_to_pdf(_docx_bytes())
    assert out[:4] == b"%PDF"


def test_convert_gotenberg_timeout(monkeypatch):
    def _post(*a, **k):
        raise requests.Timeout("slow")
    monkeypatch.setattr(requests, "post", _post)
    with pytest.raises(pc.PDFConversionTimeout):
        pc.convert_docx_to_pdf(_docx_bytes(), timeout_s=1)


def test_convert_gotenberg_http_error(monkeypatch):
    def _post(*a, **k):
        return _Resp(500, text="boom")
    monkeypatch.setattr(requests, "post", _post)
    with pytest.raises(pc.PDFConversionFailed):
        pc.convert_docx_to_pdf(_docx_bytes())


def test_unavailable_when_no_gotenberg_no_soffice(monkeypatch):
    def _post(*a, **k):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(requests, "post", _post)
    monkeypatch.setattr(pc.shutil, "which", lambda _x: None)
    with pytest.raises(pc.PDFConversionUnavailable):
        pc.convert_docx_to_pdf(_docx_bytes())


@pytest.mark.skipif(not __import__("shutil").which("soffice"),
                    reason="lokales LibreOffice nicht installiert")
def test_fallback_to_local_soffice(monkeypatch):
    """Gotenberg nicht erreichbar → lokaler soffice-Fallback erzeugt PDF."""
    def _post(*a, **k):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(requests, "post", _post)
    out = pc.convert_docx_to_pdf(_docx_bytes("Fallback"))
    assert out[:4] == b"%PDF"
