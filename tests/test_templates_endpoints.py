"""#991 — REST-Layer der Template-Engine."""
import io

import pytest
from docx import Document


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _docx_upload(text="{{ projekt.name }}"):
    d = Document(); d.add_paragraph(text)
    buf = io.BytesIO(); d.save(buf); buf.seek(0)
    return buf


def test_health(client, auth_headers):
    r = client.get('/api/templates/health', headers=auth_headers)
    assert r.status_code == 200
    assert 'soffice_available' in r.get_json()


def test_health_requires_auth(client):
    r = client.get('/api/templates/health')
    assert r.status_code == 401


def test_upload_list_get_mapping_default_delete(client, auth_headers):
    # Upload
    r = client.post('/api/templates', headers=auth_headers,
                    data={'file': (_docx_upload(), 'tpl.docx'),
                          'modul': 'cra', 'name': 'PytestVorlage'},
                    content_type='multipart/form-data')
    assert r.status_code == 201, r.get_json()
    tid = r.get_json()['id']
    assert 'projekt' in r.get_json()['variablen']
    try:
        # List
        lst = client.get('/api/templates?modul=cra', headers=auth_headers)
        assert lst.status_code == 200
        assert any(t['id'] == tid for t in lst.get_json())
        # Get one (+ schema)
        one = client.get(f'/api/templates/{tid}', headers=auth_headers)
        assert one.status_code == 200
        assert 'schema' in one.get_json()
        # Mapping
        m = client.put(f'/api/templates/{tid}/mapping', headers=auth_headers,
                       json={'mapping': {'projekt.name': 'projekt.name'}})
        assert m.status_code == 200
        # Default
        d = client.put(f'/api/templates/{tid}/default', headers=auth_headers)
        assert d.status_code == 200
    finally:
        dele = client.delete(f'/api/templates/{tid}', headers=auth_headers,
                             json={'reason': 'pytest cleanup'})
        assert dele.status_code == 200


def test_upload_rejects_non_docx(client, auth_headers):
    bogus = io.BytesIO(b'MZ\x90\x00 not a docx')
    r = client.post('/api/templates', headers=auth_headers,
                    data={'file': (bogus, 'evil.docx'), 'modul': 'cra', 'name': 'Bogus'},
                    content_type='multipart/form-data')
    assert r.status_code == 400


def test_upload_unknown_module(client, auth_headers):
    r = client.post('/api/templates', headers=auth_headers,
                    data={'file': (_docx_upload(), 'tpl.docx'),
                          'modul': 'gibtsnicht', 'name': 'X'},
                    content_type='multipart/form-data')
    assert r.status_code == 400


def test_render_missing_template_404(client, auth_headers):
    r = client.post('/api/templates/99999999/render', headers=auth_headers,
                    json={'projekt': 'X', 'format': 'docx'})
    assert r.status_code == 404


def test_render_missing_projekt_400(client, auth_headers):
    # Vorlage anlegen, dann ohne projekt rendern → 400
    up = client.post('/api/templates', headers=auth_headers,
                     data={'file': (_docx_upload(), 'tpl.docx'),
                           'modul': 'cra', 'name': 'PytestRender'},
                     content_type='multipart/form-data')
    tid = up.get_json()['id']
    try:
        r = client.post(f'/api/templates/{tid}/render', headers=auth_headers,
                        json={'format': 'docx'})
        assert r.status_code == 400
    finally:
        client.delete(f'/api/templates/{tid}', headers=auth_headers, json={'reason': 'x'})
