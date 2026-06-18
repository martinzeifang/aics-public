"""Sprint #18 — CRA C3 In-App Vulnerability-Sync (Stories A+B, #947/#948).

- record_sync_state / load_sync_state (Last-Sync-Persistenz, Story A)
- Run-Historie + Concurrency-Lock (Story B)
- REST: POST /sync-vulns (202), Doppelstart (409), Status, Runs
"""
import time
from pathlib import Path

import pytest

CRA = '/api/cra'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['cra', 'risikobewertung']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def cra_db():
    repo_root = Path(__file__).resolve().parent.parent
    db = repo_root / 'data' / 'db' / 'pytest_sync_18.sqlite'
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    from cra import db as cradb
    cradb.ensure_db(db)
    yield db
    if db.exists():
        db.unlink()


# ── Story A: Last-Sync-Persistenz ──────────────────────────────────────────

def test_record_and_load_sync_state(cra_db):
    from cra.db import record_sync_state, load_sync_state
    assert load_sync_state(cra_db, 'P') is None
    record_sync_state(cra_db, 'P', {'inserted': 3, 'updated': 1, 'unchanged': 12,
                                    'new_high_critical': 2, 'total': 16, 'repo': 'o/r'})
    s = load_sync_state(cra_db, 'P')
    assert s['inserted'] == 3 and s['new_hc'] == 2 and s['total'] == 16
    assert s['source'] == 'o/r' and s['last_run_at']
    # Upsert überschreibt
    record_sync_state(cra_db, 'P', {'inserted': 0, 'total': 5, 'repo': 'o/r'})
    assert load_sync_state(cra_db, 'P')['inserted'] == 0


def test_sync_vulns_records_state(cra_db, monkeypatch):
    from cra import vuln_sync
    from cra.db import load_sync_state
    monkeypatch.setattr(vuln_sync, 'collect_findings', lambda **kw: [
        {'cve_id': 'CVE-X', 'schwere': 'critical', 'source': 'github_dependabot'},
    ])
    vuln_sync.sync_vulns(cra_db, 'P', repo='o/r', sources=('github',))
    s = load_sync_state(cra_db, 'P')
    assert s and s['inserted'] == 1 and s['new_hc'] == 1


# ── Story B: Run-Historie + Lock ───────────────────────────────────────────

def test_run_lifecycle_and_lock(cra_db):
    from cra.db import (start_sync_run, get_running_sync_run, finish_sync_run,
                        list_sync_runs)
    rid = start_sync_run(cra_db, 'P')
    assert rid > 0
    running = get_running_sync_run(cra_db, 'P')
    assert running and running['id'] == rid          # Lock aktiv
    finish_sync_run(cra_db, rid, 'finished', {'inserted': 2})
    assert get_running_sync_run(cra_db, 'P') is None  # Lock frei
    runs = list_sync_runs(cra_db, 'P')
    assert runs[0]['status'] == 'finished' and runs[0]['report']['inserted'] == 2


# ── Story B: REST-Endpoints ────────────────────────────────────────────────

PROJ = 'pytest-sync-ep-18'


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers, json={'name': PROJ, 'produkt': 'P'})
    yield PROJ
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)


def test_start_sync_returns_202(client, auth_headers, projekt, monkeypatch):
    # Hintergrund-Sync stubben (kein Netzwerk, deterministisch)
    from cra import vuln_sync
    monkeypatch.setattr(vuln_sync, 'sync_vulns',
                        lambda *a, **k: {'inserted': 0, 'updated': 0, 'unchanged': 0,
                                         'new_high_critical': 0, 'total': 0})
    r = client.post(f'{CRA}/sync-vulns', headers=auth_headers, json={'projekt': projekt})
    assert r.status_code == 202, r.get_json()
    assert r.get_json().get('run_id')
    time.sleep(0.3)  # Thread abschließen lassen
    st = client.get(f'{CRA}/sync-vulns/status?projekt={projekt}', headers=auth_headers).get_json()
    assert st['running'] is False


def test_concurrent_start_returns_409(client, auth_headers, projekt):
    from cra.db import start_sync_run
    from server.api.cra import DB_PATH
    rid = start_sync_run(DB_PATH, projekt)  # simuliert laufenden Run
    try:
        r = client.post(f'{CRA}/sync-vulns', headers=auth_headers, json={'projekt': projekt})
        assert r.status_code == 409
        assert r.get_json()['run_id'] == rid
    finally:
        from cra.db import finish_sync_run
        finish_sync_run(DB_PATH, rid, 'finished', {})


def test_start_sync_unknown_projekt_404(client, auth_headers):
    r = client.post(f'{CRA}/sync-vulns', headers=auth_headers, json={'projekt': 'does-not-exist-xyz'})
    assert r.status_code == 404


# ── Story C: Scheduler-Spec-Parsing (#949), unabhängig von apscheduler ──────

def test_parse_schedule_config_valid_and_defaults():
    from cra.sync_scheduler import parse_schedule_config
    specs = parse_schedule_config({'sync': {'schedule': [
        {'projekt': 'AICS', 'cron': '0 4 * * *', 'source': 'github'},
        {'projekt': 'P2'},  # defaults: cron 0 4 * * *, source all
    ]}})
    assert len(specs) == 2
    assert specs[0] == {'projekt': 'AICS', 'cron': '0 4 * * *', 'source': 'github',
                        'job_id': 'cra-vuln-sync:AICS'}
    assert specs[1]['cron'] == '0 4 * * *' and specs[1]['source'] == 'all'


def test_parse_schedule_config_skips_invalid():
    from cra.sync_scheduler import parse_schedule_config
    specs = parse_schedule_config({'sync': {'schedule': [
        {'cron': '0 4 * * *'},          # ohne projekt → skip
        {'projekt': 'X', 'cron': 'bad'},  # cron kein 5-Feld → skip
        'notadict',                      # falscher Typ → skip
        {'projekt': 'OK', 'source': 'weird'},  # source → all
    ]}})
    assert len(specs) == 1
    assert specs[0]['projekt'] == 'OK' and specs[0]['source'] == 'all'


def test_parse_schedule_config_empty():
    from cra.sync_scheduler import parse_schedule_config
    assert parse_schedule_config({}) == []
    assert parse_schedule_config({'sync': {}}) == []
    assert parse_schedule_config(None) == []


def test_scheduler_modules_import_without_apscheduler():
    # Guarded Imports: shared.scheduler + cra.sync_scheduler müssen importierbar
    # sein, auch wenn apscheduler fehlt (Import erst in den Funktionen).
    import importlib
    import shared.scheduler as s
    import cra.sync_scheduler as cs
    importlib.reload(s)
    importlib.reload(cs)
    assert hasattr(s, 'start_scheduler') and hasattr(cs, 'register_cra_sync_jobs')
