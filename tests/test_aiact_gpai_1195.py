"""#1195 — AI-Act Art. 51-55 GPAI-Modul: Klassifizierung, FLOP-Schwellenwert,
systemic-risk + 2-Wochen-Notifikation, Annex-XI/XII-Register, AI-Office-Incidents,
Wizard.

Test-Isolation: alle DB_PATH-Globals werden auf eine Temp-SQLite innerhalb des
Workspace umgebogen (connect_sqlite-Constraint).
"""
import uuid

import pytest

BASE = '/api/aiact'
GPAI = '/api/aiact-gpai'
PROJ = 'pytest-gpai-1195'


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
    db = Path('data/db') / f'test_aiact_gpai_{uuid.uuid4().hex}.sqlite'
    import server.api.aiact as aiact_main
    import server.api.aiact_gpai as bp
    import ai_act.gpai as mod
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
                    json={'name': PROJ, 'produkt': 'Foundation-Model', 'beschreibung': 'LLM'})
    assert r.status_code in (200, 201), r.get_json()
    return PROJ


def test_requirements_catalog():
    from ai_act import gpai
    ids = {r['id'] for r in gpai.requirements()}
    assert 'AIA-GPAI-01' in ids
    assert 'AIA-GPAI-08' in ids
    assert gpai.SYSTEMIC_FLOP_THRESHOLD == 1e25


def test_below_threshold_not_systemic(client, auth_headers, projekt):
    r = client.put(f'{GPAI}/projekte/{PROJ}/klassifizierung', headers=auth_headers,
                   json={'ist_gpai': True, 'training_flop': 1e24})
    assert r.status_code == 200, r.get_json()
    k = r.get_json()['klassifizierung']
    assert k['ueber_schwellenwert'] is False
    assert k['systemisch'] is False
    assert k['notifikation_deadline'] is None


def test_above_threshold_systemic_with_deadline(client, auth_headers, projekt):
    r = client.put(f'{GPAI}/projekte/{PROJ}/klassifizierung', headers=auth_headers,
                   json={'ist_gpai': True, 'training_flop': 5e25,
                         'schwellwert_erreicht_am': '2020-01-01'})
    assert r.status_code == 200, r.get_json()
    k = r.get_json()['klassifizierung']
    assert k['ueber_schwellenwert'] is True
    assert k['systemisch'] is True
    # 2-Wochen-Frist seit 2020 → überfällig.
    assert k['notifikation_deadline'] is not None
    assert k['notifikation_deadline']['any_overdue'] is True


def test_manual_override_systemic(client, auth_headers, projekt):
    r = client.put(f'{GPAI}/projekte/{PROJ}/klassifizierung', headers=auth_headers,
                   json={'ist_gpai': True, 'training_flop': 1e20,
                         'systemisch_override': 'ja'})
    assert r.get_json()['klassifizierung']['systemisch'] is True


def test_systemic_only_checks_hidden_when_not_systemic(client, auth_headers, projekt):
    client.put(f'{GPAI}/projekte/{PROJ}/klassifizierung', headers=auth_headers,
               json={'ist_gpai': True, 'training_flop': 1e24})
    r = client.get(f'{GPAI}/projekte/{PROJ}/gpai', headers=auth_headers)
    ids = {c['id'] for c in r.get_json()['checks']}
    assert 'AIA-GPAI-01' in ids       # immer
    assert 'AIA-GPAI-05' not in ids   # systemic_only → ausgeblendet


def test_systemic_checks_visible_when_systemic(client, auth_headers, projekt):
    client.put(f'{GPAI}/projekte/{PROJ}/klassifizierung', headers=auth_headers,
               json={'ist_gpai': True, 'training_flop': 5e25})
    r = client.get(f'{GPAI}/projekte/{PROJ}/gpai', headers=auth_headers)
    ids = {c['id'] for c in r.get_json()['checks']}
    assert 'AIA-GPAI-05' in ids       # Red-Teaming
    assert 'AIA-GPAI-07' in ids       # Cybersecurity


def test_save_check(client, auth_headers, projekt):
    client.put(f'{GPAI}/projekte/{PROJ}/klassifizierung', headers=auth_headers,
               json={'ist_gpai': True, 'training_flop': 1e24})
    r = client.post(f'{GPAI}/projekte/{PROJ}/checks/AIA-GPAI-01', headers=auth_headers,
                    json={'status': 5, 'kommentar': 'Annex XI vollständig'})
    assert r.status_code == 200, r.get_json()
    c = next(x for x in r.get_json()['checks'] if x['id'] == 'AIA-GPAI-01')
    assert c['status'] == 5


def test_save_check_invalid_id(client, auth_headers, projekt):
    r = client.post(f'{GPAI}/projekte/{PROJ}/checks/AIA-GPAI-99', headers=auth_headers,
                    json={'status': 3})
    assert r.status_code == 400


def test_ai_office_incident_only_systemic(client, auth_headers, projekt):
    # nicht systemisch → 409
    client.put(f'{GPAI}/projekte/{PROJ}/klassifizierung', headers=auth_headers,
               json={'ist_gpai': True, 'training_flop': 1e24})
    r = client.post(f'{GPAI}/projekte/{PROJ}/incidents', headers=auth_headers,
                    json={'titel': 'X'})
    assert r.status_code == 409
    # systemisch → erlaubt
    client.put(f'{GPAI}/projekte/{PROJ}/klassifizierung', headers=auth_headers,
               json={'ist_gpai': True, 'training_flop': 5e25})
    r2 = client.post(f'{GPAI}/projekte/{PROJ}/incidents', headers=auth_headers,
                     json={'titel': 'Modell-Missbrauch', 'eingetreten_am': '2026-05-01'})
    assert r2.status_code == 201, r2.get_json()
    assert len(r2.get_json()['incidents']) == 1


def test_wizard_prompt_and_parse(client, auth_headers, projekt):
    pr = client.get(f'{GPAI}/projekte/{PROJ}/wizard/prompt', headers=auth_headers)
    assert pr.status_code == 200
    assert 'GPAI' in pr.get_json()['prompt']
    raw = ('{"ist_gpai": true, "training_flop": 2e25, '
           '"checks":[{"id":"AIA-GPAI-01","status":4,"kommentar":"ok"}]}')
    pa = client.post(f'{GPAI}/projekte/{PROJ}/wizard/parse', headers=auth_headers,
                     json={'response': raw, 'apply': True})
    assert pa.status_code == 200, pa.get_json()
    assert pa.get_json()['klassifizierung']['systemisch'] is True
    c = next(x for x in pa.get_json()['checks'] if x['id'] == 'AIA-GPAI-01')
    assert c['status'] == 4


def test_project_scoped_404(client, auth_headers, projekt):
    r = client.get(f'{GPAI}/projekte/nope-xyz/gpai', headers=auth_headers)
    assert r.status_code == 404
