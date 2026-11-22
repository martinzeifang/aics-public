"""#1198 — AI-Act Art. 43/48 Konformitätsbewertung + CE: Verfahrenswege,
Annex-VI-Checkliste, NB-Zertifikat, Re-Assessment-Trigger, DoC-Gate,
Pre-Market-Check.

Test-Isolation: alle DB_PATH-Globals werden auf eine Temp-SQLite innerhalb des
Workspace umgebogen (connect_sqlite-Constraint).
"""
import io
import uuid

import pytest

BASE = '/api/aiact'
CONF = '/api/aiact-conformity'
PROJ = 'pytest-conf-1198'

_PDF = b'%PDF-1.4\n%fake\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    from pathlib import Path
    db = Path('data/db') / f'test_aiact_conf_{uuid.uuid4().hex}.sqlite'
    import server.api.aiact as aiact_main
    import server.api.aiact_conformity as bp
    import ai_act.conformity as mod
    import ai_act.db as db_mod
    db_mod.ensure_db(db)
    # Zertifikats-Storage in ein Temp-Verzeichnis umbiegen (kein data/-Müll).
    monkeypatch.setattr(mod, 'CERT_DIR', Path('data/aiact') / f'test_conf_{uuid.uuid4().hex}',
                        raising=False)
    monkeypatch.setattr(aiact_main, 'DB_PATH', db, raising=False)
    monkeypatch.setattr(bp, 'DB_PATH', db, raising=False)
    monkeypatch.setattr(mod, 'DB_PATH', db, raising=False)
    yield db
    for sfx in ('', '-wal', '-shm'):
        p = Path(str(db) + sfx)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    import shutil
    shutil.rmtree(mod.CERT_DIR, ignore_errors=True)


@pytest.fixture
def projekt(client, auth_headers):
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': PROJ, 'produkt': 'Test-KI', 'beschreibung': 'Use-Case'})
    assert r.status_code in (200, 201), r.get_json()
    return PROJ


def test_constants(client, auth_headers):
    r = client.get(f'{CONF}/constants', headers=auth_headers)
    assert r.status_code == 200
    codes = {v['code'] for v in r.get_json()['verfahren']}
    assert 'annex_vi_intern' in codes
    assert 'annex_vii_nb' in codes
    assert len(r.get_json()['checkliste']) >= 3


def test_empty_record_blocks_doc(client, auth_headers, projekt):
    r = client.get(f'{CONF}/projekte/{PROJ}/conformity', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['doc_gate']['doc_allowed'] is False


def test_annex_vi_complete_allows_doc(client, auth_headers, projekt):
    r = client.put(f'{CONF}/projekte/{PROJ}/conformity', headers=auth_headers,
                   json={'verfahren': 'annex_vi_intern', 'qms_geprueft': True,
                         'techdoc_geprueft': True, 'ergebnis': 'konform',
                         'bewertungsdatum': '2026-05-01'})
    assert r.status_code == 200, r.get_json()
    gate = r.get_json()['doc_gate']
    assert gate['assessment_complete'] is True
    assert gate['doc_allowed'] is True


def test_annex_vii_requires_nb_and_certificate(client, auth_headers, projekt):
    # NB-Weg konform, aber ohne Zertifikat → Bewertung NICHT abgeschlossen.
    r = client.put(f'{CONF}/projekte/{PROJ}/conformity', headers=auth_headers,
                   json={'verfahren': 'annex_vii_nb', 'ergebnis': 'konform',
                         'notified_body_name': 'TÜV', 'notified_body_kennnummer': '0123',
                         'bewertungsdatum': '2026-05-01'})
    assert r.get_json()['doc_gate']['assessment_complete'] is False
    # Zertifikat hochladen → jetzt abgeschlossen.
    up = client.post(f'{CONF}/projekte/{PROJ}/certificate', headers=auth_headers,
                     data={'file': (io.BytesIO(_PDF), 'cert.pdf')},
                     content_type='multipart/form-data')
    assert up.status_code == 201, up.get_json()
    assert up.get_json()['record']['nb_zertifikat_sha256']
    assert up.get_json()['doc_gate']['assessment_complete'] is True


def test_reassessment_trigger_blocks_doc(client, auth_headers, projekt):
    r = client.put(f'{CONF}/projekte/{PROJ}/conformity', headers=auth_headers,
                   json={'verfahren': 'annex_vi_intern', 'qms_geprueft': True,
                         'techdoc_geprueft': True, 'ergebnis': 'konform',
                         'bewertungsdatum': '2026-01-01',
                         'wesentliche_aenderung_seit': '2026-03-01'})
    gate = r.get_json()['doc_gate']
    assert gate['reassessment_required'] is True
    assert gate['doc_allowed'] is False


def test_invalid_verfahren_rejected(client, auth_headers, projekt):
    r = client.put(f'{CONF}/projekte/{PROJ}/conformity', headers=auth_headers,
                   json={'verfahren': 'erfunden'})
    assert r.status_code == 400


def test_certificate_rejects_non_pdf(client, auth_headers, projekt):
    up = client.post(f'{CONF}/projekte/{PROJ}/certificate', headers=auth_headers,
                     data={'file': (io.BytesIO(b'not a pdf'), 'cert.txt')},
                     content_type='multipart/form-data')
    assert up.status_code == 400


def test_certificate_rejects_bad_magic(client, auth_headers, projekt):
    up = client.post(f'{CONF}/projekte/{PROJ}/certificate', headers=auth_headers,
                     data={'file': (io.BytesIO(b'PKnotpdf'), 'cert.pdf')},
                     content_type='multipart/form-data')
    assert up.status_code == 400


def test_premarket_uses_structured_record(client, auth_headers, projekt, _tmp_db):
    """High-Risk-Pre-Market-Check muss den Konformitäts-Record als Gate auswerten."""
    from ai_act.db import load_projekt, update_projekt_meta
    p = load_projekt(_tmp_db, PROJ)
    meta = dict(p.get('meta') or {})
    meta.setdefault('aiact', {})['risk_tier'] = {'tier': 'high-risk'}
    update_projekt_meta(_tmp_db, PROJ, meta)
    r = client.get(f'{BASE}/projekte/{PROJ}/pre-market-check', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    checks = {c['key']: c for c in r.get_json()['checks']}
    assert 'conformity' in checks
    assert checks['conformity']['ok'] is False  # noch nicht bewertet
    assert 'ce_marking' in checks


def test_project_scoped_404(client, auth_headers, projekt):
    r = client.get(f'{CONF}/projekte/nope-xyz/conformity', headers=auth_headers)
    assert r.status_code == 404
