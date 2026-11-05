"""#1196 — AI-Act Art. 27 FRIA-Workflow: Register, Pflichtfelder, Trigger,
Stepper, Mitteilung, Wizard.

Test-Isolation: alle DB_PATH-Globals werden auf eine Temp-SQLite innerhalb des
Workspace umgebogen (connect_sqlite-Constraint).
"""
import uuid

import pytest

BASE = '/api/aiact'
FRIA = '/api/aiact-fria'
PROJ = 'pytest-fria-1196'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch):
    from pathlib import Path
    db = Path('data/db') / f'test_aiact_fria_{uuid.uuid4().hex}.sqlite'
    import server.api.aiact as aiact_main
    import server.api.aiact_fria as bp
    import ai_act.fria as mod
    import ai_act.db as db_mod
    db_mod.ensure_db(db)
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


@pytest.fixture
def projekt(client, auth_headers):
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': PROJ, 'organisation': 'Stadtverwaltung',
                          'produkt': 'Test-KI', 'beschreibung': 'Use-Case'})
    assert r.status_code in (200, 201), r.get_json()
    return PROJ


def _set_high_risk(db):
    """Risk-Tier high-risk im Projekt-Meta setzen (sonst greift der Trigger nicht)."""
    from ai_act.db import load_projekt, update_projekt_meta
    p = load_projekt(db, PROJ)
    meta = p.get('meta') if isinstance(p.get('meta'), dict) else {}
    meta = dict(meta)
    meta['risk_tier'] = 'high-risk'
    update_projekt_meta(db, PROJ, meta)


def test_constants(client, auth_headers):
    r = client.get(f'{FRIA}/constants', headers=auth_headers)
    assert r.status_code == 200
    codes = {b['code'] for b in r.get_json()['betreiber_typen']}
    assert 'oeffentliche_stelle' in codes
    assert 'annex_iii_5b' in codes


def test_empty_record_and_trigger_off(client, auth_headers, projekt):
    r = client.get(f'{FRIA}/projekte/{PROJ}/fria', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d['record']['betreiber_typ'] == 'keine'
    assert d['trigger']['required'] is False  # kein high-risk + kein Betreiber


def test_trigger_requires_highrisk_and_operator(client, auth_headers, projekt, _tmp_db):
    _set_high_risk(_tmp_db)
    # high-risk gesetzt, aber Betreiber-Typ 'keine' → noch nicht pflichtig
    t = client.get(f'{FRIA}/projekte/{PROJ}/trigger', headers=auth_headers,
                   query_string={'betreiber_typ': 'keine'}).get_json()
    assert t['is_high_risk'] is True
    assert t['required'] is False
    # öffentliche Stelle → Pflicht ausgelöst
    t2 = client.get(f'{FRIA}/projekte/{PROJ}/trigger', headers=auth_headers,
                    query_string={'betreiber_typ': 'oeffentliche_stelle'}).get_json()
    assert t2['required'] is True


def test_save_fria_fields(client, auth_headers, projekt):
    r = client.put(f'{FRIA}/projekte/{PROJ}/fria', headers=auth_headers,
                   json={'betreiber_typ': 'oeffentliche_stelle',
                         'nutzungsprozesse': 'Automatisierte Bescheide',
                         'zeitraum_frequenz': 'dauerhaft',
                         'betroffene_gruppen': 'Antragsteller',
                         'schadensrisiken': ['Diskriminierung', 'Intransparenz'],
                         'oversight_massnahmen': 'Vier-Augen',
                         'massnahmen_bei_risiko': 'Abschaltung',
                         'governance': 'DSB',
                         'beschwerdemechanismus': 'Widerspruch',
                         'stage': 'massnahmen', 'status': 'in_bearbeitung'})
    assert r.status_code == 200, r.get_json()
    rec = r.get_json()['record']
    assert rec['nutzungsprozesse'] == 'Automatisierte Bescheide'
    assert rec['schadensrisiken'] == ['Diskriminierung', 'Intransparenz']
    assert rec['stage'] == 'massnahmen'


def test_invalid_betreiber_rejected(client, auth_headers, projekt):
    r = client.put(f'{FRIA}/projekte/{PROJ}/fria', headers=auth_headers,
                   json={'betreiber_typ': 'erfunden'})
    assert r.status_code == 400


def test_invalid_stage_rejected(client, auth_headers, projekt):
    r = client.put(f'{FRIA}/projekte/{PROJ}/fria', headers=auth_headers,
                   json={'betreiber_typ': 'keine', 'stage': 'nope'})
    assert r.status_code == 400


def test_report_to_authority(client, auth_headers, projekt):
    r = client.post(f'{FRIA}/projekte/{PROJ}/mitteilung', headers=auth_headers,
                    json={'behoerde': 'BNetzA'})
    assert r.status_code == 200, r.get_json()
    rec = r.get_json()['record']
    assert rec['status'] == 'an_behoerde_gemeldet'
    assert rec['mitteilung_behoerde_am']
    assert rec['behoerde'] == 'BNetzA'


def test_mitteilung_export(client, auth_headers, projekt):
    client.put(f'{FRIA}/projekte/{PROJ}/fria', headers=auth_headers,
               json={'betreiber_typ': 'oeffentliche_stelle',
                     'nutzungsprozesse': 'Prozess X'})
    r = client.get(f'{FRIA}/projekte/{PROJ}/mitteilung/export', headers=auth_headers)
    assert r.status_code == 200
    assert b'Art. 27' in r.data
    assert b'Prozess X' in r.data


def test_wizard_prompt_and_parse(client, auth_headers, projekt):
    pr = client.get(f'{FRIA}/projekte/{PROJ}/wizard/prompt', headers=auth_headers)
    assert pr.status_code == 200
    assert 'Art. 27' in pr.get_json()['prompt']
    raw = ('{"nutzungsprozesse":"KI-Triage","schadensrisiken":["Bias"],'
           '"betroffene_gruppen":"Patienten"}')
    pa = client.post(f'{FRIA}/projekte/{PROJ}/wizard/parse', headers=auth_headers,
                     json={'response': raw, 'apply': True})
    assert pa.status_code == 200, pa.get_json()
    rec = pa.get_json()['record']
    assert rec['nutzungsprozesse'] == 'KI-Triage'
    assert rec['schadensrisiken'] == ['Bias']


def test_premarket_gate_lists_fria_when_required(client, auth_headers, projekt, _tmp_db):
    """Pre-Market-Check muss FRIA als (kritisches) Gate auflisten, wenn pflichtig."""
    _set_high_risk(_tmp_db)
    client.put(f'{FRIA}/projekte/{PROJ}/fria', headers=auth_headers,
               json={'betreiber_typ': 'oeffentliche_stelle'})
    r = client.get(f'{BASE}/projekte/{PROJ}/pre-market-check', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    keys = {c['key'] for c in r.get_json()['checks']}
    assert 'fria' in keys


def test_project_scoped_404(client, auth_headers, projekt):
    r = client.get(f'{FRIA}/projekte/nope-xyz/fria', headers=auth_headers)
    assert r.status_code == 404
