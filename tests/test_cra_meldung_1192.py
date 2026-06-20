"""Tests #1192/#1209: CRA Art. 14 Melde-Workflow + Nutzer-Advisory.

- cra_meldung-Tabelle + Stufen-Transition (nur vorwärts).
- Deadline-Berechnung 24h/72h/14d/1M ab erkannt_am.
- Endpoints meldungen (+/stufe, /export, /nutzer-advisory).
- Audit-Events + 'Gemeldet-am'.
"""
import pytest

CRA = '/api/cra'
MELD = '/api/cra-meldung'
FIRMA = 'pytest-firma-1192'
PROJ = 'pytest-cra-1192'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': PROJ, 'unternehmen': FIRMA})
    yield PROJ
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)


# ── Deadline-Engine (Phase 0) ────────────────────────────────────────────────

def test_deadlines_evaluate_stages():
    import cra.deadlines as dl
    from datetime import datetime, timezone
    now = datetime(2026, 9, 12, 8, 0, 0, tzinfo=timezone.utc)
    res = dl.evaluate('2026-09-12T00:00:00', 'cra_art14', now=now)
    keys = [s['key'] for s in res['stages']]
    assert keys == ['early_warning', 'notification', 'final_report']
    ew = res['stages'][0]
    # 24h-Frist, 8h vergangen → noch on track
    assert ew['overdue'] is False
    # 14-Tage-Frist im Vorfall-Set ist 1 Monat
    inc = dl.evaluate('2026-09-12T00:00:00', 'cra_art14_incident', now=now)
    assert inc['stages'][-1]['offset_hours'] == 30 * 24


def test_deadlines_overdue():
    import cra.deadlines as dl
    from datetime import datetime, timezone
    now = datetime(2026, 9, 20, 0, 0, 0, tzinfo=timezone.utc)
    res = dl.evaluate('2026-09-01T00:00:00', 'cra_art14', now=now)
    assert res['any_overdue'] is True
    assert res['stages'][0]['ampel'] == 'overdue'


def test_parse_duration():
    import cra.deadlines as dl
    assert dl.parse_duration_hours('7 Tage') == 7 * 24
    assert dl.parse_duration_hours('24h') == 24
    assert dl.parse_duration_hours('2 Wochen') == 2 * 168


# ── DB-Transition ─────────────────────────────────────────────────────────────

def test_stufe_only_forward(tmp_path):
    from cra import meldung_db as mdb
    db = tmp_path / 'cra.sqlite'
    mid = mdb.create_meldung(db, PROJ, {'typ': 'vuln_exploited', 'titel': 'X'})
    m = mdb.set_stufe(db, mid, PROJ, 'early_warning_24h')
    assert m['status'] == 'early_warning_24h'
    assert m['early_warning_gemeldet_am']  # gemeldet-am gesetzt
    with pytest.raises(ValueError):
        mdb.set_stufe(db, mid, PROJ, 'erkannt')  # rückwärts verboten


# ── Endpoints ─────────────────────────────────────────────────────────────────

def test_meldung_lifecycle_api(client, auth_headers, projekt):
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen', headers=auth_headers,
                    json={'typ': 'serious_incident', 'titel': 'Vorfall A',
                          'betroffene_ms': 'DE, FR'})
    assert r.status_code == 201, r.json
    mid = r.json['id']
    assert r.json['deadlines'] is not None
    assert r.json['deadlines']['stages'][-1]['offset_hours'] == 30 * 24

    r = client.post(f'{MELD}/projekte/{projekt}/meldungen/{mid}/stufe',
                    headers=auth_headers, json={'status': 'notification_72h'})
    assert r.status_code == 200, r.json
    assert r.json['notification_gemeldet_am']

    r = client.get(f'{MELD}/projekte/{projekt}/meldungen', headers=auth_headers)
    assert r.status_code == 200 and len(r.json) == 1

    # ENISA-SRP-Export (JSON)
    r = client.get(f'{MELD}/projekte/{projekt}/meldungen/{mid}/export?format=json',
                   headers=auth_headers)
    assert r.status_code == 200
    assert r.json['report_type'] == 'serious_incident'
    assert 'stage_texts' in r.json


def test_nutzer_advisory_csaf(client, auth_headers, projekt):
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen', headers=auth_headers,
                    json={'typ': 'vuln_exploited', 'titel': 'CVE-X'})
    mid = r.json['id']
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen/{mid}/nutzer-advisory',
                    headers=auth_headers,
                    json={'empfohlene_massnahmen': 'Patch installieren',
                          'schweregrad': 'high', 'veroeffentlichungskanal': 'Website'})
    assert r.status_code == 200, r.json
    assert r.json['advisory']['schweregrad'] == 'high'
    r = client.get(f'{MELD}/projekte/{projekt}/meldungen/{mid}/nutzer-advisory/csaf',
                   headers=auth_headers)
    assert r.status_code == 200
    assert r.json['document']['csaf_version'] == '2.0'


def test_idor_scoped(client, auth_headers, projekt):
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen', headers=auth_headers,
                    json={'typ': 'vuln_exploited', 'titel': 'X'})
    mid = r.json['id']
    # falsches Projekt → 404
    r = client.get(f'{MELD}/projekte/fremd-projekt/meldungen/{mid}', headers=auth_headers)
    assert r.status_code == 404
