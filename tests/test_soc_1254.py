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
    # Cross-Modul-Bridge-Tests legen noch SQLite-DBs nicht portierter Module an.
    for ext in ('', '-wal', '-shm'):
        p = Path(str(db) + ext)
        if p.exists():
            p.unlink()


@pytest.fixture
def soc_db(pg):
    """Frisches Postgres-Schema je Test (Migration #15 / #1332)."""
    db = Path('data/db/pytest_soc_1254.sqlite')  # logischer Schema-Selektor → Schema "pytest_soc_1254"
    pg.drop_schema(db)
    from soc import db as sdb
    sdb.ensure_db(db)
    yield db


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


def test_playbook_seed_assign_and_mandatory_gate(soc_db):
    """Playbook-Katalog-Seed, Zuordnung, Pflicht-Schritt-Gate (#1314)."""
    from soc import db as sdb
    from soc.playbooks import seed_default_playbooks
    assert seed_default_playbooks(soc_db) == 5
    assert seed_default_playbooks(soc_db) == 0  # idempotent
    pbs = sdb.list_playbooks(soc_db)
    phish = [p for p in pbs if p['kategorie'] == 'phishing'][0]
    iid = sdb.create_incident(soc_db, titel='Phish', severity='high', actor='t')
    inst = sdb.assign_playbook_to_incident(soc_db, iid, phish['id'], actor='t')
    assert sdb.incident_mandatory_open(soc_db, iid) > 0
    for s in sdb.list_incident_playbooks(soc_db, iid)[0]['steps']:
        if s['mandatory']:
            sdb.toggle_playbook_step(soc_db, inst, s['id'], True, actor='t')
    assert sdb.incident_mandatory_open(soc_db, iid) == 0
    ip = sdb.list_incident_playbooks(soc_db, iid)[0]
    assert ip['progress']['done'] >= 5


def test_sla_kpis_and_timestamps(soc_db):
    """SLA-Defaults, Zeitstempel bei Statuswechsel, KPI-Aggregation (#1315)."""
    from soc import db as sdb
    assert sdb.list_sla(soc_db)["high"]["ack_minutes"] == 30
    iid = sdb.create_incident(soc_db, titel="T", severity="high", actor="t")
    sdb.set_incident_status(soc_db, iid, "in_review", actor="t")
    sdb.set_incident_status(soc_db, iid, "resolved", actor="t")
    inc = sdb.get_incident(soc_db, iid)
    assert inc["acknowledged_at"] and inc["resolved_at"]
    s = sdb.incident_sla(soc_db, inc)
    assert s["resolve_target"] == 480 and s["resolve_breached"] is False
    k = sdb.sla_kpis(soc_db)
    assert k["resolved"] == 1 and k["sla_within"] == 1 and k["sla_compliance"] == 1.0
    sdb.save_sla(soc_db, "high", 10, 20)
    assert sdb.list_sla(soc_db)["high"]["resolve_minutes"] == 20


def test_connection_partial_update_no_clobber(soc_db):
    """Manager-Speichern darf Indexer-Felder nicht löschen (#1315-Hotfix)."""
    from soc import db as sdb
    sdb.save_connection(soc_db, name="default", modus="pull", url="https://idx:9200",
                        username="soc-reader", secret="geheim", index_pattern="wazuh-alerts-*",
                        min_level=7, verify_tls=False)
    # Nur Manager speichern (wie saveManager im Frontend) — url/username NICHT senden
    sdb.save_connection(soc_db, name="default", modus="pull",
                        manager_url="https://mgr:55000", manager_user="soc-reader",
                        manager_secret="geheim2")
    c = sdb.list_connections(soc_db, with_secrets=True)[0]
    assert c["url"] == "https://idx:9200" and c["username"] == "soc-reader"  # nicht geleert
    assert c["manager_url"] == "https://mgr:55000" and c["manager_user"] == "soc-reader"
    assert c["verify_tls"] == 0  # behalten
    # Umgekehrt: Indexer speichern lässt Manager stehen
    sdb.save_connection(soc_db, name="default", modus="pull", url="https://idx2:9200")
    c = sdb.list_connections(soc_db, with_secrets=True)[0]
    assert c["url"] == "https://idx2:9200" and c["manager_url"] == "https://mgr:55000"


def test_upsert_asset_insert_with_agent_id(soc_db):
    """Asset-Import mit agent_id darf nicht crashen (dict-kwarg-Bug, #1315-Hotfix)."""
    from soc import db as sdb
    aid = sdb.upsert_asset(soc_db, {"agent_name": "web01", "agent_id": "001", "os": "Ubuntu"})
    assert aid > 0
    # Re-Import aktualisiert, kein Crash, kein Duplikat
    sdb.upsert_asset(soc_db, {"agent_name": "web01", "agent_id": "001", "os": "Ubuntu 22.04"})
    rows = sdb.list_assets(soc_db) if hasattr(sdb, "list_assets") else []
    names = [a for a in rows if a.get("agent_name") == "web01"]
    assert len(names) == 1


def test_pir_and_actions_and_close_gate(soc_db):
    """PIR-Speichern, Maßnahmen-Tracking, Close-Gate für echte Incidents (#1316)."""
    from soc import db as sdb
    iid = sdb.create_incident(soc_db, titel="Echt", severity="high", actor="t")
    # Hochfahren bis resolved (echter Incident-Pfad)
    for st in ("in_review", "confirmed", "contained", "resolved"):
        sdb.set_incident_status(soc_db, iid, st, actor="t")
    # Close ohne PIR → blockiert
    r = sdb.close_incident(soc_db, iid, reason="abgeschlossen nach Analyse", actor="t")
    assert not r["ok"] and "Post-Incident-Review" in r["error"]
    # PIR mit Root-Cause → Close geht
    sdb.save_pir(soc_db, iid, root_cause="Fehlkonfiguration Firewall", lessons="Review-Prozess", actor="t")
    assert sdb.pir_complete(soc_db, iid)
    r = sdb.close_incident(soc_db, iid, reason="abgeschlossen nach Analyse", actor="t")
    assert r["ok"]
    # Maßnahmen
    aid = sdb.save_pir_action(soc_db, incident_id=iid, beschreibung="Firewall härten",
                              owner="ops", frist="2026-07-01", actor="t")
    assert aid > 0
    openacts = sdb.list_pir_actions(soc_db, only_open=True)
    assert len(openacts) == 1 and openacts[0]["incident_titel"] == "Echt"
    sdb.set_pir_action_status(soc_db, aid, "erledigt", actor="t")
    assert sdb.list_pir_actions(soc_db, only_open=True) == []
    done = sdb.list_pir_actions(soc_db, incident_id=iid)
    assert done[0]["status"] == "erledigt" and done[0]["done_at"]


def test_pir_not_required_for_false_positive(soc_db):
    """False-Positive (new→false_positive→closed) braucht keinen PIR (#1316)."""
    from soc import db as sdb
    iid = sdb.create_incident(soc_db, titel="FP", severity="low", actor="t")
    sdb.set_incident_status(soc_db, iid, "false_positive", actor="t")
    r = sdb.close_incident(soc_db, iid, reason="war ein Fehlalarm", actor="t")
    assert r["ok"]


def test_bulk_link_unlink_alerts(soc_db):
    """Mehrere Alarme idempotent zuordnen, Severity-Bump, einzeln lösen (#1328)."""
    from soc import db as sdb
    # Alarme direkt anlegen
    from shared import db as _sdb
    con = _sdb.connect(soc_db)
    for uid, sev in [("a1", "low"), ("a2", "critical"), ("a3", "medium")]:
        con.execute("INSERT INTO soc_alerts(alert_uid, severity, description) VALUES(?,?,?)", (uid, sev, "x"))
    con.commit(); con.close()
    iid = sdb.create_incident(soc_db, titel="I", severity="low", actor="t")
    r = sdb.add_alerts_to_incident(soc_db, iid, ["a1", "a2"], actor="t")
    assert r["ok"] and r["added"] == 2
    # idempotent
    r2 = sdb.add_alerts_to_incident(soc_db, iid, ["a1", "a2"], actor="t")
    assert r2["added"] == 0
    # Severity auf höchste (critical) angehoben
    assert sdb.get_incident(soc_db, iid)["severity"] == "critical"
    assert len(sdb.get_incident_alerts(soc_db, iid)) == 2
    # einzeln lösen
    rm = sdb.remove_alert_from_incident(soc_db, iid, "a1", actor="t")
    assert rm["removed"] == 1
    assert len(sdb.get_incident_alerts(soc_db, iid)) == 1
    # Incident nicht gefunden
    assert not sdb.add_alerts_to_incident(soc_db, 9999, ["a3"], actor="t")["ok"]


def test_evidence_chain_of_custody(soc_db, tmp_path, monkeypatch):
    """Asservat speichern, SHA-256, Chain of Custody, Snapshot, Soft-Delete (#1317)."""
    from soc import db as sdb, evidence as sev
    monkeypatch.setattr(sev, "_BASE", tmp_path / "ev")
    monkeypatch.setattr(sev, "_safe", lambda p: p)  # tmp_path liegt außerhalb des Workspace
    iid = sdb.create_incident(soc_db, titel="Forensik", severity="high", actor="t")
    res = sev.add_evidence(soc_db, iid, filename="dump.log", data=b"line1\nline2\n", actor=" analyst")
    assert res["ok"] and len(res["sha256"]) == 64
    evs = sev.list_evidence(soc_db, iid)
    assert len(evs) == 1 and evs[0]["sha256"] == res["sha256"] and evs[0]["retention_until"]
    coc = sev.list_custody(soc_db, res["id"])
    assert [c["action"] for c in coc] == ["added"]
    # Download protokolliert 'exported'
    out = sev.read_evidence_file(soc_db, res["id"], action="exported", actor="analyst")
    assert out and out[0] == b"line1\nline2\n"
    assert "exported" in [c["action"] for c in sev.list_custody(soc_db, res["id"])]
    # Rohlog-Snapshot
    snap = sev.freeze_log_snapshot(soc_db, iid, actor="analyst")
    assert snap["ok"]
    assert any(e["kind"] == "log_snapshot" for e in sev.list_evidence(soc_db, iid))
    # Soft-Delete braucht Begründung
    assert not sev.delete_evidence(soc_db, res["id"], reason="kurz", actor="a")["ok"]
    d = sev.delete_evidence(soc_db, res["id"], reason="Aufbewahrungsfrist abgelaufen", actor="a")
    assert d["ok"]
    ev = sev.get_evidence(soc_db, res["id"])
    assert ev["deleted_at"] and ev["delete_reason"]
    assert "deleted" in [c["action"] for c in sev.list_custody(soc_db, res["id"])]  # CoC bleibt
    # Verbotener Dateityp
    try:
        sev.add_evidence(soc_db, iid, filename="x.exe", data=b"MZ...", actor="a"); assert False
    except ValueError:
        pass


def test_betrieb_handover_escalation_raci(soc_db):
    """Handover, Eskalationsmatrix (+Seed), Incident-Eskalation, RACI (#1318)."""
    from soc import db as sdb, betrieb
    # Handover
    hid = betrieb.save_handover(soc_db, schicht="Spät", datum="2026-06-11",
                                offene_punkte="Incident #3 offen", actor="t")
    assert hid > 0 and betrieb.list_handovers(soc_db)[0]["schicht"] == "Spät"
    # Seed-Matrix
    betrieb.seed_defaults(soc_db)
    crit = betrieb.list_escalation(soc_db, severity="critical")
    assert len(crit) == 3 and crit[0]["stufe"] == 1
    betrieb.seed_defaults(soc_db)  # idempotent
    assert len(betrieb.list_escalation(soc_db, severity="critical")) == 3
    # eigene Zeile
    eid = betrieb.save_escalation(soc_db, severity="high", stufe=3, rolle="CISO", frist_minuten=60)
    assert eid > 0
    betrieb.save_escalation(soc_db, id=eid, severity="high", stufe=3, rolle="CISO/GF", frist_minuten=45)
    assert any(e["rolle"] == "CISO/GF" for e in betrieb.list_escalation(soc_db, severity="high"))
    # Incident-Eskalation dokumentiert
    iid = sdb.create_incident(soc_db, titel="Esk", severity="critical", actor="t")
    r = betrieb.escalate_incident(soc_db, iid, 2, actor="t")
    assert r["ok"] and r["stufe"] == 2 and r["notified"]
    assert any(t["event"] == "incident.escalated" for t in sdb.list_timeline(soc_db, iid))
    # RACI
    rid = betrieb.save_raci(soc_db, vorfallstyp="Phishing", rolle="SOC-Lead", raci="A")
    assert rid > 0 and betrieb.list_raci(soc_db, vorfallstyp="Phishing")[0]["raci"] == "A"
    betrieb.delete_raci(soc_db, rid)
    assert betrieb.list_raci(soc_db, vorfallstyp="Phishing") == []


def test_uebungen_crud(soc_db):
    """SOC-Übungen anlegen/aktualisieren/auswerten + Detection-Test (#1319)."""
    from soc import uebungen
    uid = uebungen.save_uebung(soc_db, typ="detection_test", titel="EICAR-Test",
                               szenario="EICAR auf Host ablegen", datum="2026-06-11",
                               erwartete_erkennung="Wazuh FIM + AV-Alarm", actor="t")
    assert uid > 0
    # Auswertung (partielles Update)
    uebungen.save_uebung(soc_db, id=uid, status="ausgewertet", ergebnis="bestanden",
                         tatsaechliche_erkennung="Alarm Level 12 ausgelöst",
                         massnahmen="Regel-Tuning dokumentiert")
    u = uebungen.get_uebung(soc_db, uid)
    assert u["status"] == "ausgewertet" and u["ergebnis"] == "bestanden"
    assert u["titel"] == "EICAR-Test"  # nicht überschrieben
    assert u["massnahmen"] == "Regel-Tuning dokumentiert"
    assert len(uebungen.list_uebungen(soc_db)) == 1
    uebungen.delete_uebung(soc_db, uid)
    assert uebungen.list_uebungen(soc_db) == []


def test_detection_usecases_and_coverage(soc_db):
    """Detection-Use-Cases, ATT&CK-Coverage, Lücken, Alarm-Vorschläge (#1321)."""
    import json
    from shared import db as _sdb
    from soc import detection
    # leere Coverage = alles Lücke
    cov0 = detection.attack_coverage(soc_db)
    assert cov0["counts"]["gap"] > 0 and cov0["coverage_pct"] == 0.0
    # aktiver Use-Case für Phishing (T1566)
    uid = detection.save_usecase(soc_db, name="Phishing-Detektion", bedrohung="Phishing",
                                 attack_techniques=["T1566.001", "T1204"], status="aktiv",
                                 wazuh_rules="rule:5710,group:authentication")
    assert uid > 0
    cov = detection.attack_coverage(soc_db)
    t1566 = next(t for tac in cov["tactics"] for t in tac["techniques"] if t["id"] == "T1566")
    assert t1566["status"] == "covered"  # Sub-Technik auf Basis normalisiert
    assert cov["coverage_pct"] > 0
    # geplanter Use-Case → partial
    detection.save_usecase(soc_db, name="BruteForce", attack_techniques=["T1110"], status="geplant")
    cov2 = detection.attack_coverage(soc_db)
    t1110 = next(t for tac in cov2["tactics"] for t in tac["techniques"] if t["id"] == "T1110")
    assert t1110["status"] == "partial"
    # Alarm mit ATT&CK-Technik → Coverage + Vorschlag
    con = _sdb.connect(soc_db)
    con.execute("INSERT INTO soc_alerts(alert_uid, severity, mitre) VALUES(?,?,?)",
                ("ax", "high", json.dumps({"id": ["T1059"], "technique": [], "tactic": []})))
    con.commit(); con.close()
    cov3 = detection.attack_coverage(soc_db)
    t1059 = next(t for tac in cov3["tactics"] for t in tac["techniques"] if t["id"] == "T1059")
    assert t1059["status"] == "covered" and t1059["by_alerts"]
    sugg = detection.suggestions_from_alerts(soc_db)
    assert any(x["id"] == "T1059" for x in sugg)  # noch in keinem Use-Case
    gaps = detection.coverage_gaps(soc_db)
    assert all(g["status"] != "covered" for g in gaps) if gaps and "status" in gaps[0] else True
    assert isinstance(gaps, list)


def test_threatintel_ioc_enrichment(soc_db):
    """IOC pflegen/importieren, Alarm-Anreicherung + Severity-Bump, Rescan (#1322)."""
    from soc import threatintel as ti, ingest
    # Import (gemischte Typen, Auto-Erkennung)
    n = ti.import_iocs(soc_db, "1.2.3.4;ip;90;C2-Server\nbad-domain.test\n" + "a"*64, quelle="feed")
    assert n == 3
    iocs = ti.list_iocs(soc_db, only_active=True)
    assert {i["typ"] for i in iocs} == {"ip", "domain", "hash"}
    # Ingest eines Alarms mit Match-IP → Severity-Bump auf high
    a = {"alert_uid": "ioc1", "severity": "low", "srcip": "1.2.3.4", "description": "x", "rule_level": 3}
    ingest.ingest_alerts(soc_db, [a])
    al = next(x for x in ti.alerts_with_iocs(soc_db) if x["alert_uid"] == "ioc1")
    assert al["severity"] == "high" and al["ioc_hits"][0]["wert"] == "1.2.3.4"
    # Domain-Match im full_log
    a2 = {"alert_uid": "ioc2", "severity": "medium", "full_log": "connect to bad-domain.test now", "rule_level": 5}
    ingest.ingest_alerts(soc_db, [a2])
    al2 = next(x for x in ti.alerts_with_iocs(soc_db) if x["alert_uid"] == "ioc2")
    assert any(h["typ"] == "domain" for h in al2["ioc_hits"])
    # Rescan: neuer IOC trifft bestehenden Alarm
    a3 = {"alert_uid": "ioc3", "severity": "low", "srcip": "9.9.9.9", "rule_level": 2}
    ingest.ingest_alerts(soc_db, [a3])
    ti.save_ioc(soc_db, typ="ip", wert="9.9.9.9", quelle="late")
    matched = ti.rescan_alerts(soc_db)
    assert matched >= 1
    assert any(x["alert_uid"] == "ioc3" for x in ti.alerts_with_iocs(soc_db))
    ti.delete_ioc(soc_db, iocs[0]["id"])


def test_hunting_crud_query_escalate(soc_db, monkeypatch):
    """Hunt anlegen, Ad-hoc-Query (gemockt), Eskalation zu Incident (#1323)."""
    from soc import hunting, db as sdb
    hid = hunting.save_hunt(soc_db, hypothese="Lateral Movement via RDP",
                            attack_bezug="T1021", datum="2026-06-11", jaeger="analyst",
                            query="data.win.eventID:4624 AND rule.level:>=5", actor="t")
    assert hid > 0 and hunting.list_hunts(soc_db)[0]["hypothese"].startswith("Lateral")
    # Query ohne Verbindung -> sauberer Fehler
    r0 = hunting.run_query(soc_db, "*")
    assert not r0["ok"]
    # Verbindung + gemockter Indexer
    sdb.save_connection(soc_db, name="default", modus="pull", url="https://idx:9200", secret="x")
    import soc.wazuh_client as wz
    monkeypatch.setattr(wz, "run_query", lambda conn, q, limit=50: {"total": 3, "hits": [{"alert_uid": "h1"}]})
    r = hunting.run_query(soc_db, "data.srcip:1.2.3.4")
    assert r["ok"] and r["total"] == 3 and len(r["hits"]) == 1
    # Eskalation -> Incident + Hunt abgeschlossen/bestätigt
    esc = hunting.escalate_to_incident(soc_db, hid, severity="high", actor="t")
    assert esc["ok"] and esc["incident_id"] > 0
    h = hunting.get_hunt(soc_db, hid)
    assert h["status"] == "abgeschlossen" and h["ergebnis"] == "bestaetigt"
    inc = sdb.get_incident(soc_db, esc["incident_id"])
    assert inc["klassifikation"] == "threat_hunt"


def test_logsources_health_and_coverage(soc_db):
    """Log-Source-Health aus Assets+Alarmen, Coverage-Lücken, manuelles Register (#1324)."""
    from shared import db as _sdb
    from soc import logsources, db as sdb
    # Asset aktiv mit jüngstem Alarm
    sdb.upsert_asset(soc_db, {"agent_name": "web01", "agent_id": "001", "agent_status": "active",
                              "kritikalitaet": 5})
    # kritisches Asset offline -> Coverage-Lücke
    sdb.upsert_asset(soc_db, {"agent_name": "db01", "agent_id": "002", "agent_status": "disconnected",
                              "kritikalitaet": 5})
    con = _sdb.connect(soc_db)
    con.execute("INSERT INTO soc_alerts(alert_uid, agent_name, event_ts, severity) VALUES(?,?,aics_now(),?)",
                ("la1", "web01", "high"))
    con.commit(); con.close()
    h = logsources.health(soc_db, silent_days=7)
    by = {r["name"]: r for r in h["sources"]}
    assert by["web01"]["status"] == "aktiv" and not by["web01"]["is_gap"]
    assert by["db01"]["status"] == "offline" and by["db01"]["is_gap"]
    assert h["gap_count"] >= 1
    # Manuelle Quelle (Firewall-Syslog), nie gesehen -> still/unbekannt + Lücke
    sid = logsources.save_source(soc_db, name="fw-syslog", typ="firewall", erwartet=True)
    assert sid > 0
    h2 = logsources.health(soc_db)
    fw = next(r for r in h2["sources"] if r["name"] == "fw-syslog")
    assert fw["status"] == "unbekannt" and fw["is_gap"]
    logsources.delete_source(soc_db, sid)
    assert all(r["name"] != "fw-syslog" for r in logsources.list_sources(soc_db))


def test_mgmt_report_data_and_html(soc_db):
    """Management-Report-Aggregation + HTML-Render (#1325)."""
    from soc import mgmt_report, db as sdb
    iid = sdb.create_incident(soc_db, titel="R", severity="high", klassifikation="phishing", actor="t")
    sdb.set_incident_status(soc_db, iid, "in_review", actor="t")
    sdb.set_incident_status(soc_db, iid, "confirmed", actor="t")
    d = mgmt_report.build_report_data(soc_db, period="monat")
    assert d["incidents_total"] == 1 and d["by_severity"].get("high") == 1
    assert d["by_category"].get("phishing") == 1 and d["days"] == 30
    assert "mtta_hours" in d
    html = mgmt_report.render_html(d)
    assert "SOC-Management-Report" in html and "phishing" in html
    # DOCX-Render (python-docx vorhanden)
    blob = mgmt_report.render_docx(d)
    assert blob[:2] == b"PK"  # docx = zip


def test_soccmm_assessment(soc_db):
    """SOC-CMM Auto-Vorbefüllung, Assessment-Snapshot, Reifegrad, Trend, DOCX (#1326)."""
    from soc import soccmm, db as sdb
    from soc.playbooks import seed_default_playbooks
    seed_default_playbooks(soc_db)
    sdb.create_incident(soc_db, titel="x", severity="low", actor="t")
    sugg = soccmm.auto_suggestions(soc_db)
    assert sugg.get("process.incident") and sugg.get("services.response")
    # Assessment speichern
    scores = {k: 3 for k in [a["key"] for d in soccmm.CATALOG for a in d["aspekte"]]}
    scores["business.drivers"] = {"reifegrad": 5, "bemerkung": "klar definiert"}
    res = soccmm.create_assessment(soc_db, datum="2026-06-11", durchgefuehrt_von="t", scores=scores)
    assert res["ok"] and 3.0 <= res["gesamt_reifegrad"] <= 3.1
    assert len(res["domains"]) == 5
    # latest + history
    latest = soccmm.latest_scores(soc_db)
    assert latest["business.drivers"]["reifegrad"] == 5
    hist = soccmm.list_assessments(soc_db)
    assert len(hist) == 1 and hist[0]["gesamt_reifegrad"] == res["gesamt_reifegrad"]
    # DOCX-Nachweis
    blob = soccmm.render_docx(soc_db)
    assert blob[:2] == b"PK"
