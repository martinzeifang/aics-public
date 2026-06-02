"""Tests für WP-10 (#743): Eingabevalidierung & Upload-Sicherheit.

Abgedeckt:
  (a) Magic-Byte-Validator akzeptiert echte PDF/ZIP-Header, lehnt Fakes ab.
  (b) LDAP-Filter-Escaping neutralisiert `*)(uid=*`-Injection.
  (c) Fake-MIME-Upload an einen echten Endpunkt (kunden Evidence) wird abgelehnt;
      MAX_CONTENT_LENGTH ist global gesetzt.
"""

from __future__ import annotations

import io
import uuid
import zipfile

import pytest


# ---------------------------------------------------------------------------
# (a) Magic-Byte-Validator
# ---------------------------------------------------------------------------

def _make_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('hello.txt', 'hi')
    return buf.getvalue()


def test_magic_bytes_accepts_real_pdf():
    from shared.upload_validation import validate_magic_bytes
    # Echter PDF-Header
    validate_magic_bytes(b'%PDF-1.7\n...', suffix='.pdf')


def test_magic_bytes_accepts_real_zip_office():
    from shared.upload_validation import validate_magic_bytes
    zip_bytes = _make_zip_bytes()
    assert zip_bytes.startswith(b'PK\x03\x04')
    validate_magic_bytes(zip_bytes, suffix='.xlsx')
    validate_magic_bytes(zip_bytes, suffix='.docx')


def test_magic_bytes_rejects_fake_pdf():
    from shared.upload_validation import validate_magic_bytes, UploadValidationError
    # .pdf-Endung, aber kein PDF-Inhalt
    with pytest.raises(UploadValidationError):
        validate_magic_bytes(b'this is not a pdf at all', suffix='.pdf')


def test_magic_bytes_rejects_fake_xlsx():
    from shared.upload_validation import validate_magic_bytes, UploadValidationError
    # .xlsx-Endung, aber kein ZIP-Magic
    with pytest.raises(UploadValidationError):
        validate_magic_bytes(b'%PDF-1.7 fake xlsx', suffix='.xlsx')


def test_validate_upload_file_zipbomb_check(tmp_path):
    """Echte XLSX-Datei besteht Magic + validate_office_archive."""
    from shared.upload_validation import validate_upload_file
    import openpyxl

    xlsx = tmp_path / 'real.xlsx'
    wb = openpyxl.Workbook()
    wb.active['A1'] = 'x'
    wb.save(str(xlsx))

    validate_upload_file(xlsx, suffix='.xlsx')


def test_validate_upload_file_rejects_fake_office(tmp_path):
    from shared.upload_validation import validate_upload_file, UploadValidationError
    fake = tmp_path / 'fake.xlsx'
    fake.write_bytes(b'not a zip file')
    with pytest.raises(UploadValidationError):
        validate_upload_file(fake, suffix='.xlsx')


# ---------------------------------------------------------------------------
# (b) LDAP-Filter-Injection-Escaping
# ---------------------------------------------------------------------------

def test_ldap_filter_escaping_neutralizes_injection():
    from server.auth.ldap import build_search_filter, escape_filter_chars

    payload = '*)(uid=*'
    escaped = escape_filter_chars(payload)
    # Filter-Metazeichen dürfen im Ergebnis nicht mehr roh vorkommen
    assert '*' not in escaped
    assert '(' not in escaped
    assert ')' not in escaped
    assert '\\2a' in escaped  # * -> \2a

    template = '(|(uid={username})(mail={username}))'
    built = build_search_filter(template, payload)
    # Die Injection darf keine zusätzlichen rohen Klammern einschleusen:
    # nur die Klammern des Templates selbst (3 auf, 3 zu) bleiben übrig.
    assert built.count('(') == 3
    assert built.count(')') == 3
    assert '*)(uid=*' not in built


def test_ldap_filter_escaping_keeps_normal_username():
    from server.auth.ldap import build_search_filter
    built = build_search_filter('(uid={username})', 'alice')
    assert built == '(uid=alice)'


# ---------------------------------------------------------------------------
# (c) Endpunkt-Test: Fake-MIME-Upload wird abgelehnt + MAX_CONTENT_LENGTH
# ---------------------------------------------------------------------------

def test_max_content_length_configured(app):
    assert app.config.get('MAX_CONTENT_LENGTH')
    assert app.config['MAX_CONTENT_LENGTH'] >= 1024 * 1024


def _create_kunde(client, auth_headers) -> str:
    name = f'wp10-{uuid.uuid4().hex[:8]}'
    resp = client.post('/api/kunden', json={'name': name}, headers=auth_headers)
    assert resp.status_code in (201, 409), resp.get_data(as_text=True)
    return name


def test_evidence_upload_rejects_fake_pdf(client, auth_headers):
    """kunden ist NICHT lizenzgated → kein 423. Fake-PDF muss 400 liefern."""
    name = _create_kunde(client, auth_headers)
    data = {
        'file': (io.BytesIO(b'this is definitely not a pdf'), 'evil.pdf'),
    }
    resp = client.post(
        f'/api/kunden/{name}/evidence/file',
        data=data,
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert resp.status_code == 400, resp.get_data(as_text=True)


def test_evidence_upload_rejects_dotonly_filename(client, auth_headers):
    name = _create_kunde(client, auth_headers)
    data = {
        'file': (io.BytesIO(b'%PDF-1.7 real header'), '...'),
    }
    resp = client.post(
        f'/api/kunden/{name}/evidence/file',
        data=data,
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert resp.status_code == 400, resp.get_data(as_text=True)


def test_evidence_upload_accepts_real_pdf(client, auth_headers):
    name = _create_kunde(client, auth_headers)
    pdf_bytes = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'
    data = {
        'file': (io.BytesIO(pdf_bytes), 'report.pdf'),
    }
    resp = client.post(
        f'/api/kunden/{name}/evidence/file',
        data=data,
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
