"""Tests für das SOC-Modul (Security Operations Center, Sprint #29 / Epic #1254).

Deckt ab:
- Permissions/Rolle (Operator) registriert.
- DB: Verbindung (Secret verschlüsselt), Dedup-Idempotenz, Incident-Statusmaschine,
  sha256-Timeline-Kette, KPIs, Severity-Mapping.
- Meldepflicht-Router: Asset-Tags → Regime.
- Brücken: DSGVO-Datenpanne + NIS2-/AI-Act-Meldeentwurf-Dokument.
- API-Smoke: /api/soc/constants (read).
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _fresh(db: Path):
    for ext in ('', '-wal', '-shm'):
        p = Path(str(db) + ext)
        if p.exists():
            p.unlink()


@pytest.fixture
def soc_db(tmp_path):
    repo = Path(__file__).resolve().parent.parent
    db = repo / 'data' / 'db' / 'pytest_soc_1254.sqlite'
    db.parent.mkdir(parents=True, exist_ok=True)
    _fresh(db)
    from soc import db as sdb
    sdb.ensure_db(db)
    yield db
    _fresh(db)


# ── Permissions/Rolle ───────────────────────────────────────────────────────

def test_role_and_permissions_registered():
    from server.models.permission import (
        RoleEnum, Permission, MODULES, MODULE_PERMISSIONS, ROLE_PERMISSIONS,
    )
    assert 'soc' in MODULES
    assert RoleEnum.SOC_OPERATOR in ROLE_PERMISSIONS
    for p in (Permission.SOC_READ, Permission.SOC_WRITE, Permission.SOC_TRIAGE,
              Permission.SOC_INCIDENT, Permission.SOC_CONFIG, Permission.SOC_EXPORT):
        assert p in MODULE_PERMISSIONS['soc']
    # Operator hat genau die SOC-Permissions
    assert set(ROLE_PERMISSIONS[RoleEnum.SOC_OPERATOR]) == set(MODULE_PERMISSIONS['soc'])


def test_authz_prefix_registered():
    from server.middleware.authz import _MODULE_PREFIXES
    assert ('/api/soc', 'soc') in _MODULE_PREFIXES


# ── Severity / Statusmaschine ───────────────────────────────────────────────

def test_severity_mapping():
    from soc.constants import severity_from_level
    assert severity_from_level(13) == 'critical'
    assert severity_from_level(9) == 'high'
    assert severity_from_level(5) == 'medium'
    assert severity_from_level(2) == 'low'
    assert severity_from_level(None) == 'low'


def test_incident_transitions():
    from soc.constants import can_transition
    assert can_transition('new', 'in_review', incident=True)
    assert can_transition('confirmed', 'contained', incident=True)
    assert not can_transition('new', 'closed', incident=True)
    assert can_transition('closed', 'reopened', incident=True)


# ── DB-Ebene ────────────────────────────────────────────────────────────────

def test_connection_secret_encrypted(soc_db):
    from soc import db as sdb
    sdb.save_connection(soc_db, name='t', modus='pull', url='https://x:9200',
                        username='u', secret='geheim', min_level=7)
    full = sdb.load_connection(soc_db, 't', with_secret=True)
    assert full['secret'] == 'geheim'
    listed = sdb.list_connections(soc_db)[0]
    assert 'secret' not in listed         # kein Klartext in der Liste
    assert listed['has_secret'] is True


def _alert(uid='a1', level=5, srcip='203.0.113.7'):
    from soc import wazuh_client as wz
    return wz.normalize_alert({'_id': uid, '_source': {
        'rule': {'id': '5710', 'level': level, 'description': 'sshd fail',
                 'groups': ['authentication_failures'], 'mitre': {'id': ['T1110'], 'tactic': ['Credential Access']}},
        'agent': {'id': '003', 'name': 'pve01'}, 'data': {'srcip': srcip},
        'full_log': 'Failed password', 'timestamp': '2026-06-11T08:43:08.835+0000'}})


def test_ingest_dedup_idempotent(soc_db):
    from soc import ingest
    res = ingest.ingest_alerts(soc_db, [_alert(), _alert()])  # zweimal derselbe _id
    assert res['new'] == 1 and res['skipped'] == 1


def test_dedup_group_key_stable():
    a1, a2 = _alert('x1'), _alert('x2')   # gleiche Entität+5min-Bucket → gleiche Gruppe
    assert a1['group_key'] == a2['group_key']


def test_timeline_hash_chain(soc_db):
    from soc import db as sdb
    iid = sdb.create_incident(soc_db, titel='T', actor='tester')
    sdb.add_timeline_note(soc_db, iid, actor='tester', detail='note 1')
    sdb.set_incident_status(soc_db, iid, 'in_review', actor='tester')
    tl = sdb.list_timeline(soc_db, iid)
    assert len(tl) >= 3
    for i in range(1, len(tl)):
        assert tl[i]['prev_hash'] == tl[i - 1]['entry_hash']


def test_kpis(soc_db):
    from soc import db as sdb, ingest
    ingest.ingest_alerts(soc_db, [_alert()])
    sdb.create_incident(soc_db, titel='Inc', actor='t')
    k = sdb.kpis(soc_db)
    assert k['alerts_total'] == 1
    assert k['incidents_open'] >= 1


# ── Meldepflicht-Router ─────────────────────────────────────────────────────

def test_router_triggers_regimes(soc_db):
    from soc import db as sdb, meldepflicht
    iid = sdb.create_incident(soc_db, titel='Inc', actor='t')
    aid = sdb.upsert_asset(soc_db, {'agent_name': 'web01', 'personenbezogen': True, 'nis2_scope': True})
    sdb.update_incident(soc_db, iid, {'asset_id': aid, 'awareness_at': '2026-06-11T09:00:00+00:00'}, actor='t')
    res = meldepflicht.evaluate_incident(soc_db, iid, actor='t')
    assert set(res['regimes']) == {'dsgvo', 'nis2'}
    tracks = sdb.list_meldetracks(soc_db, iid)
    nis2 = [t for t in tracks if t['regime'] == 'nis2'][0]
    assert len(nis2['deadlines']) == 3   # Frühwarnung/Meldung/Abschluss


# ── Brücken ─────────────────────────────────────────────────────────────────

def test_router_honors_incident_regime_flags(soc_db):
    """Ohne Asset: am Incident gewählte Regelwerke triggern die Tracks (#1301)."""
    from soc import db as sdb, meldepflicht
    iid = sdb.create_incident(soc_db, titel='X', actor='t')
    sdb.set_incident_regimes(soc_db, iid, {'nis2_scope': True, 'cra_produkt': True}, actor='t')
    res = meldepflicht.evaluate_incident(soc_db, iid, actor='t')
    assert set(res['regimes']) == {'nis2', 'cra'}


def test_bridge_dsgvo(soc_db, tmp_path, monkeypatch):
    from soc import db as sdb, bridges
    from dsgvo import db as ddb
    dsgvo_db = soc_db.parent / 'pytest_soc_dsgvo.sqlite'
    _fresh(dsgvo_db); ddb.ensure_db(dsgvo_db)
    monkeypatch.setattr(bridges, 'DSGVO_DB', dsgvo_db)
    iid = sdb.create_incident(soc_db, titel='Datenabfluss', severity='high', actor='t')
    sdb.update_incident(soc_db, iid, {'awareness_at': '2026-06-11T09:00:00+00:00'}, actor='t')
    sdb.upsert_meldetrack(soc_db, iid, regime='dsgvo', legal='Art. 33/34 DSGVO', deadlines=[])
    res = bridges.to_dsgvo_datenpanne(soc_db, iid, 'TestProjekt', actor='t')
    assert res['ok']
    pannen = ddb.list_pannen(dsgvo_db, 'TestProjekt')
    assert pannen and pannen[0]['meldung_aufsicht_pflicht'] and pannen[0]['meldung_betroffene_pflicht']
    _fresh(dsgvo_db)


def test_bridge_nis2_document(soc_db, monkeypatch):
    from soc import db as sdb, bridges
    from shared.documents import db as docdb
    nis2_db = soc_db.parent / 'pytest_soc_nis2.sqlite'
    _fresh(nis2_db)
    monkeypatch.setattr(bridges, 'NIS2_DB', nis2_db)
    iid = sdb.create_incident(soc_db, titel='Vorfall', severity='critical', actor='t')
    sdb.upsert_meldetrack(soc_db, iid, regime='nis2', legal='Art. 23 NIS2', deadlines=[])
    res = bridges.to_nis2_meldung(soc_db, iid, 'TestProjekt', actor='t')
    assert res['ok']
    docs = docdb.list_documents(nis2_db, 'nis2', 'TestProjekt')
    assert docs and 'NIS2' in docs[0]['titel']
    _fresh(nis2_db)


# ── API-Smoke ───────────────────────────────────────────────────────────────

def test_close_incident_requires_reason(soc_db):
    from soc import db as sdb
    iid = sdb.create_incident(soc_db, titel='X', actor='t')
    assert not sdb.close_incident(soc_db, iid, reason='kurz', actor='t')['ok']
    assert sdb.close_incident(soc_db, iid, reason='Bestätigter False Positive', actor='admin')['ok']
    inc = sdb.get_incident(soc_db, iid)
    assert inc['status'] == 'closed' and inc['closed_by'] == 'admin' and inc['closed_reason']


def test_list_incidents_excludes_closed_by_default(soc_db):
    from soc import db as sdb
    a = sdb.create_incident(soc_db, titel='offen', actor='t')
    b = sdb.create_incident(soc_db, titel='zu', actor='t')
    sdb.close_incident(soc_db, b, reason='Abgeschlossen nach Prüfung', actor='t')
    assert {i['id'] for i in sdb.list_incidents(soc_db)} == {a}
    assert {i['id'] for i in sdb.list_incidents(soc_db, include_closed=True)} == {a, b}


def test_manager_credentials_roundtrip(soc_db):
    from soc import db as sdb
    sdb.save_connection(soc_db, name='default', modus='pull', manager_url='https://m:55000',
                        manager_user='soc-reader', manager_secret='Sc!secret')
    c = sdb.load_connection(soc_db, 'default', with_secret=True)
    assert c['manager_url'] == 'https://m:55000' and c['manager_secret'] == 'Sc!secret'
    assert sdb.list_connections(soc_db)[0]['has_manager_secret'] is True
    assert 'manager_secret' not in sdb.list_connections(soc_db)[0]


def test_incident_report_docx(soc_db):
    from soc import db as sdb, report_export
    iid = sdb.create_incident(soc_db, titel='Report-Test', severity='high', actor='t')
    items = [{'incident': sdb.get_incident(soc_db, iid), 'alerts': [], 'meldetracks': [],
              'timeline': sdb.list_timeline(soc_db, iid)}]
    data = report_export.render_incidents_docx(items)
    assert data[:2] == b'PK' and len(data) > 1000   # DOCX = ZIP


def test_template_adapter_registered(soc_db):
    from shared.templates.schema import get_context_builder
    assert get_context_builder('soc') is not None
    from soc import template_context as tc
    ctx = tc.build_soc_context(soc_db)
    assert 'soc' in ctx and 'incidents' in ctx['soc']


def test_risk_cockpit_includes_soc(soc_db):
    from soc import db as sdb
    import shared.risk_cockpit as rc
    sdb.create_incident(soc_db, titel='Firmen-Incident', severity='high', firmen_id=7, actor='t')
    items = rc.collect_soc_incidents(soc_db, 7)
    assert len(items) == 1 and items[0]['source'] == 'soc' and items[0]['severity'] == 'high'
    nodb = soc_db.parent / 'pytest_none.sqlite'
    ck = rc.build_cockpit(7, rb_db=nodb, cra_db=nodb, soc_db=soc_db)
    assert ck['summary']['by_source']['soc'] == 1


def test_scheduler_parse():
    from soc import sync_scheduler as s
    assert s.parse_soc_schedule({'sync': {}}) == []
    assert s.parse_soc_schedule({'sync': {'scheduler_enabled': True, 'interval_minutes': 10}})[0]['trigger'] == 'interval'
    cron = s.parse_soc_schedule({'sync': {'scheduler_enabled': True, 'schedule': [{'cron': '*/15 * * * *'}]}})
    assert cron and cron[0]['trigger'] == 'cron'
    # ungültige Crontabs werden verworfen
    assert s.parse_soc_schedule({'sync': {'scheduler_enabled': True, 'schedule': [{'cron': 'bad'}]}}) == []


def test_api_constants(client, auth_headers):
    r = client.get('/api/soc/constants', headers=auth_headers)
    assert r.status_code == 200
    data = r.get_json()
    assert 'alert_states' in data and 'regimes' in data
    assert 'dsgvo' in data['regimes']


def test_control_evidence_and_likelihood(soc_db):
    from soc import db as sdb
    for i in range(4):
        sdb.create_incident(soc_db, titel='I%d' % i, agent_name='web01', actor='t')
    iid = sdb.create_incident(soc_db, titel='c', agent_name='web01', actor='t')
    sdb.close_incident(soc_db, iid, reason='Nach Pruefung geschlossen', actor='t')
    ev = sdb.control_evidence(soc_db)
    assert ev['incidents_closed'] == 1 and ev['control'] == 'incident_handling'
    lk = sdb.incident_frequency(soc_db, agent='web01')
    assert lk['incidents'] == 5 and lk['eintrittswahrscheinlichkeit_stufe'] == 4


def test_owasp_llm_detection(soc_db):
    from soc import db as sdb, ingest, wazuh_client as wz, owasp_llm
    hit = {'_id': 'l1', '_source': {'rule': {'id': '100', 'level': 10,
           'description': 'prompt injection / jailbreak on chatbot', 'groups': ['llm']},
           'agent': {'id': '1', 'name': 'ai01'}, 'data': {}, 'full_log': 'ignore previous instructions',
           'timestamp': '2026-06-11T08:00:00+0000'}}
    ingest.ingest_alerts(soc_db, [wz.normalize_alert(hit)])
    det = owasp_llm.detect_llm_alerts(soc_db)
    assert det and det[0]['llm_id'] == 'LLM01' and det[0]['count'] == 1


def test_asset_partial_upsert_and_risk(soc_db):
    """Agent-Re-Import überschreibt manuelle Felder NICHT; Risiko-Score + asset_id (#1305-1310)."""
    from soc import db as sdb, ingest, wazuh_client as wz
    aid = sdb.upsert_asset(soc_db, {'agent_name': 'web01', 'kritikalitaet': 5, 'cra_produkt': True, 'owner': 'Ops'})
    sdb.upsert_asset(soc_db, {'agent_name': 'web01', 'agent_id': '9', 'ip': '10.0.0.1', 'agent_status': 'active', 'source': 'agent'})
    a = sdb.get_asset(soc_db, aid)
    assert a['kritikalitaet'] == 5 and a['cra_produkt'] and a['owner'] == 'Ops'  # nicht überschrieben
    assert a['ip'] == '10.0.0.1' and a['agent_status'] == 'active' and a['agent_id'] == '9'  # ergänzt
    assert len(sdb.list_assets(soc_db)) == 1  # kein Duplikat
    hit = {'_id': 'x1', '_source': {'rule': {'id': '1', 'level': 10, 'description': 't', 'groups': []},
           'agent': {'id': '9', 'name': 'web01'}, 'data': {}, 'full_log': 'x', 'timestamp': '2026-06-11T08:00:00+0000'}}
    ingest.ingest_alerts(soc_db, [wz.normalize_alert(hit)])
    assert len(sdb.list_alerts(soc_db, asset_id=aid)) == 1
    iid = sdb.create_incident(soc_db, titel='Krit', severity='critical', actor='t')
    sdb.assign_incident_asset(soc_db, iid, aid, actor='t')
    risk = sdb.asset_risk_score(soc_db, aid)
    assert risk['score'] > 10 and risk['ampel'] in ('orange', 'rot')
    det = sdb.asset_detail(soc_db, aid)
    assert len(det['incidents']) == 1 and len(det['alerts']) == 1
