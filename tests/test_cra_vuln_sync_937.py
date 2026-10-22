"""Tests #937: C3 Vulnerability-Auto-Sync (GitHub/GitLab) + Idempotenz.

Deckt die testbaren Kernteile ohne externe API ab:
- upsert_vuln: Insert/Update/Idempotenz, Schutz von triage_kommentar + Status,
  Schwere nur anheben.
- Detector-Mapping aus Dependabot/GitLab-Rohdaten (Funktion mit gemocktem _gh/_gl).
- sync_vulns-Report-Aggregation.
"""
from pathlib import Path

import pytest


@pytest.fixture
def cra_db(tmp_path, monkeypatch):
    # DB muss innerhalb des Workspace-Roots liegen (security_utils). Wir legen sie
    # in data/db/ ab und räumen auf.
    repo_root = Path(__file__).resolve().parent.parent
    db = repo_root / 'data' / 'db' / 'pytest_vuln_937.sqlite'
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    from cra import db as cradb
    cradb.ensure_db(db)
    yield db
    if db.exists():
        db.unlink()


def test_upsert_insert_then_idempotent(cra_db):
    from cra.db import upsert_vuln, list_vuln
    f = {'cve_id': 'CVE-2024-1', 'schwere': 'high', 'cvss_score': 7.5,
         'source': 'github_dependabot', 'titel': 'Bug'}
    assert upsert_vuln(cra_db, 'P', f)['action'] == 'inserted'
    # Re-Sync identischer Fund → unchanged
    assert upsert_vuln(cra_db, 'P', f)['action'] == 'unchanged'
    rows = list_vuln(cra_db, 'P')
    assert len(rows) == 1
    assert rows[0]['source'] == 'github_dependabot'
    assert rows[0]['last_synced_at']


def test_upsert_preserves_manual_triage(cra_db):
    from cra.db import upsert_vuln, save_vuln, list_vuln
    upsert_vuln(cra_db, 'P', {'cve_id': 'CVE-2024-2', 'schwere': 'high', 'cvss_score': 8.0})
    vid = list_vuln(cra_db, 'P')[0]['id']
    # Auditor triagiert manuell
    save_vuln(cra_db, 'P', {'id': vid, 'status': 'fixed', 'triage_kommentar': 'gepatcht',
                            'schwere': 'high', 'cvss_score': 8.0})
    # Re-Sync mit niedrigerer Schwere darf nichts verschlechtern
    upsert_vuln(cra_db, 'P', {'cve_id': 'CVE-2024-2', 'schwere': 'low', 'cvss_score': 1.0,
                              'source': 'github_dependabot'})
    row = list_vuln(cra_db, 'P')[0]
    assert row['status'] == 'fixed'                 # Status nicht zurückgesetzt
    assert row['triage_kommentar'] == 'gepatcht'    # Kommentar erhalten
    assert row['schwere'] == 'high'                 # Schwere nicht abgesenkt


def test_upsert_raises_without_cve(cra_db):
    from cra.db import upsert_vuln
    with pytest.raises(ValueError):
        upsert_vuln(cra_db, 'P', {'schwere': 'high'})


def test_dependabot_mapping(monkeypatch):
    from cra import pflicht_doku_autodetect as ad
    sample = [{
        'state': 'open',
        'html_url': 'https://github.com/o/r/security/dependabot/1',
        'dependency': {'package': {'name': 'requests'}, 'manifest_path': 'requirements.txt'},
        'security_advisory': {'cve_id': 'CVE-2024-9', 'severity': 'critical',
                              'summary': 'RCE', 'cvss': {'score': 9.8}},
        'security_vulnerability': {'first_patched_version': {'identifier': '2.32.0'}},
    }]
    monkeypatch.setattr(ad, '_gh_api_json', lambda path: sample)
    out = ad.detect_dependabot_vulns('o', 'r')
    assert len(out) == 1
    v = out[0]
    assert v['cve_id'] == 'CVE-2024-9'
    assert v['schwere'] == 'critical'
    assert v['cvss_score'] == 9.8
    assert v['affected_component'] == 'requests@requirements.txt'
    assert v['fixed_in_version'] == '2.32.0'
    assert v['source'] == 'github_dependabot'
    assert v['status'] == 'open'


def test_dependabot_dismissed_maps_to_wontfix(monkeypatch):
    from cra import pflicht_doku_autodetect as ad
    sample = [{'state': 'auto_dismissed',
               'dependency': {'package': {'name': 'x'}, 'manifest_path': 'p'},
               'security_advisory': {'ghsa_id': 'GHSA-x', 'severity': 'low'}}]
    monkeypatch.setattr(ad, '_gh_api_json', lambda path: sample)
    out = ad.detect_dependabot_vulns('o', 'r')
    assert out[0]['status'] == 'wontfix'
    assert out[0]['cve_id'] == 'GHSA-x'


def test_gitlab_mapping(monkeypatch):
    from cra import pflicht_doku_autodetect as ad
    sample = [{
        'id': 42, 'state': 'confirmed', 'severity': 'high', 'title': 'SQLi',
        'web_url': 'https://gitlab.com/o/r/-/security/vulnerabilities/42',
        'identifiers': [{'external_type': 'cve', 'name': 'CVE-2024-7'}],
        'location': {'file': 'app/db.py'},
    }]
    monkeypatch.setattr(ad, '_gl_api_json', lambda base, path, env='GITLAB_TOKEN': sample)
    out = ad.detect_vulns_gitlab('https://gitlab.com', '123')
    assert out[0]['cve_id'] == 'CVE-2024-7'
    assert out[0]['schwere'] == 'high'
    assert out[0]['affected_component'] == 'app/db.py'
    assert out[0]['status'] == 'triaging'
    assert out[0]['source'] == 'gitlab'


def test_sync_report_counts(cra_db, monkeypatch):
    from cra import vuln_sync
    monkeypatch.setattr(vuln_sync, 'collect_findings', lambda **kw: [
        {'cve_id': 'CVE-A', 'schwere': 'critical', 'source': 'github_dependabot'},
        {'cve_id': 'CVE-B', 'schwere': 'low', 'source': 'github_advisory'},
    ])
    rep = vuln_sync.sync_vulns(cra_db, 'P', repo='o/r', sources=('github',))
    assert rep['inserted'] == 2
    assert rep['new_high_critical'] == 1
    assert rep['total'] == 2
