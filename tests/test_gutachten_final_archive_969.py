"""Sprint #20 #969 — Final-Archiv: Upload (SHA-256), Download, Soft-Delete (Admin)."""
import hashlib
import io
from pathlib import Path

import pytest

GUT = '/api/gutachten'
FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'bisg_vorlage.docx'
PROJ = 'pytest-final-969'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['gutachten']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{GUT}/gerichts/{PROJ}', headers=auth_headers)
    client.post(f'{GUT}/gerichts', headers=auth_headers, json={
        'name': PROJ, 'gutachten_art': 'gericht', 'gericht': 'LG', 'aktenzeichen': '1/26', 'sv_name': 'Dr'})
    yield PROJ
    client.delete(f'{GUT}/gerichts/{PROJ}', headers=auth_headers)


def _upload(client, auth_headers, projekt, data, filename):
    return client.post(f'{GUT}/gerichts/{projekt}/final-export', headers=auth_headers,
                       data={'file': (io.BytesIO(data), filename)},
                       content_type='multipart/form-data')


def test_upload_docx_returns_sha256(client, auth_headers, projekt):
    data = FIXTURE.read_bytes()
    r = _upload(client, auth_headers, projekt, data, 'final.docx')
    assert r.status_code == 201, r.get_json()
    assert r.get_json()['sha256'] == hashlib.sha256(data).hexdigest()


def test_upload_pdf(client, auth_headers, projekt):
    pdf = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
    r = _upload(client, auth_headers, projekt, pdf, 'final.pdf')
    assert r.status_code == 201, r.get_json()


def test_upload_fake_docx_rejected(client, auth_headers, projekt):
    r = _upload(client, auth_headers, projekt, b'MZ\x90\x00 this is an exe', 'evil.docx')
    assert r.status_code == 400


def test_list_download_and_softdelete(client, auth_headers, projekt):
    data = FIXTURE.read_bytes()
    fid = _upload(client, auth_headers, projekt, data, 'final.docx').get_json()['id']
    # list
    lst = client.get(f'{GUT}/gerichts/{projekt}/final-exports', headers=auth_headers).get_json()
    assert any(e['id'] == fid and not e['deleted'] for e in lst['final_exports'])
    assert all('datei_pfad' not in e for e in lst['final_exports'])  # interner Pfad nicht ausgeliefert
    # download → bytes match sha
    dl = client.get(f'{GUT}/gerichts/{projekt}/final-export/{fid}/download', headers=auth_headers)
    assert dl.status_code == 200
    assert hashlib.sha256(dl.data).hexdigest() == hashlib.sha256(data).hexdigest()
    # delete ohne Begründung → 400
    assert client.delete(f'{GUT}/gerichts/{projekt}/final-export/{fid}', headers=auth_headers,
                         json={'reason': 'kurz'}).status_code == 400
    # delete als Admin mit Begründung → 200
    d = client.delete(f'{GUT}/gerichts/{projekt}/final-export/{fid}', headers=auth_headers,
                      json={'reason': 'Fehlerhafte Version, ersetzt durch Korrektur.'})
    assert d.status_code == 200, d.get_json()
    # nach Soft-Delete: list zeigt deleted, download → 410
    lst2 = client.get(f'{GUT}/gerichts/{projekt}/final-exports', headers=auth_headers).get_json()
    assert any(e['id'] == fid and e['deleted'] for e in lst2['final_exports'])
    assert client.get(f'{GUT}/gerichts/{projekt}/final-export/{fid}/download',
                      headers=auth_headers).status_code == 410


def test_unknown_projekt_upload_404(client, auth_headers):
    r = _upload(client, auth_headers, 'does-not-exist-zzz', FIXTURE.read_bytes(), 'f.docx')
    assert r.status_code == 404
