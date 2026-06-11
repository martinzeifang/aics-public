"""Sprint #18 — AI-Act Repo-Scan-Fix + Auto-Fill (A1/A2) + Wizards (A3/A4/A5).

Netzzugriffe (Repo/URL) werden gemockt.
"""
import json

import pytest

from server.api.aiact import DB_PATH
from ai_act.db import save_projekt, update_projekt_meta, delete_projekt, load_system_doku
from ai_act.autofill_common import FieldSuggestion

PROJ = 'pytest-aiact-18'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _cleanup_proj(name: str):
    import sqlite3
    try:
        con = sqlite3.connect(str(DB_PATH))
        for tbl in ('aiact_system_doku', 'aiact_data_governance',
                    'aiact_human_oversight', 'aiact_post_market_monitoring'):
            try:
                con.execute(f"DELETE FROM {tbl} WHERE projekt_name=?", (name,))
            except sqlite3.OperationalError:
                pass
        con.commit(); con.close()
    except Exception:
        pass
    delete_projekt(DB_PATH, name)


@pytest.fixture
def projekt():
    _cleanup_proj(PROJ)  # evtl. Rückstände aus früherem Lauf entfernen (1:n-Risiken)
    save_projekt(DB_PATH, name=PROJ, organisation='ACME', produkt='Widget', beschreibung='')
    update_projekt_meta(DB_PATH, PROJ, {'vcs_publish': {'provider': 'github', 'repo': 'acme/app'}})
    yield PROJ
    _cleanup_proj(PROJ)


def _url(suffix=''):
    return f'/api/aiact/projekte/{PROJ}{suffix}'


# ── Story 1 (#1019): Repo-Scan-Fallback ─────────────────────────────

def test_repo_scan_uses_stored_repo(client, auth_headers, monkeypatch, projekt):
    captured = {}

    def _fake(*, repo, branch='', token=None):
        captured['repo'] = repo
        return []
    monkeypatch.setattr('ai_act.repo_autoanswer.suggest_from_repo_signals', _fake)
    r = client.post(_url('/repo-scan'), json={}, headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    assert captured['repo'] == 'acme/app'
    assert r.get_json()['repo_source'] == 'stored'


def test_repo_scan_request_override(client, auth_headers, monkeypatch, projekt):
    monkeypatch.setattr('ai_act.repo_autoanswer.suggest_from_repo_signals', lambda *, repo, branch='', token=None: [])
    r = client.post(_url('/repo-scan'), json={'repo': 'other/repo'}, headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()['repo'] == 'other/repo'
    assert r.get_json()['repo_source'] == 'request'


def test_repo_scan_no_repo_400(client, auth_headers):
    save_projekt(DB_PATH, name='pytest-aiact-norepo', organisation='X', produkt='Y', beschreibung='')
    try:
        r = client.post('/api/aiact/projekte/pytest-aiact-norepo/repo-scan', json={}, headers=auth_headers)
        assert r.status_code == 400
        assert 'Repo' in r.get_json()['error']
    finally:
        delete_projekt(DB_PATH, 'pytest-aiact-norepo')


# ── Story 2 (#1020): A1 System-Doku Auto-Fill ───────────────────────

def test_system_doku_suggest_and_apply(client, auth_headers, monkeypatch, projekt):
    monkeypatch.setattr('ai_act.system_doku_autofill.suggest_system_doku',
                        lambda repo, branch='', token=None: {
                            'system_name': FieldSuggestion('system_name', 'ACME AI', 'README.md', 0.7),
                            'intended_purpose': FieldSuggestion('intended_purpose', 'Klassifiziert Tickets', 'README.md', 0.5),
                        })
    s = client.post(_url('/system-doku/suggest'), json={'source': 'repo'}, headers=auth_headers)
    assert s.status_code == 200, s.get_json()
    sug = s.get_json()['suggestions']
    assert 'system_name' in sug and sug['system_name']['value'] == 'ACME AI'

    a = client.post(_url('/system-doku/apply'),
                    json={'fields': {'system_name': 'ACME AI', 'intended_purpose': 'Klassifiziert Tickets'}},
                    headers=auth_headers)
    assert a.status_code == 200 and 'system_name' in a.get_json()['applied']
    assert (load_system_doku(DB_PATH, PROJ) or {}).get('system_name') == 'ACME AI'


def test_system_doku_suggest_url_requires_url(client, auth_headers, projekt):
    r = client.post(_url('/system-doku/suggest'), json={'source': 'url'}, headers=auth_headers)
    assert r.status_code == 400


# ── Story 3 (#1021): A2 Data-Governance Auto-Fill ───────────────────

def test_data_governance_suggest_apply(client, auth_headers, monkeypatch, projekt):
    monkeypatch.setattr('ai_act.data_governance_autofill.suggest_data_governance',
                        lambda repo, branch='', token=None: {
                            'training_data_source': FieldSuggestion('training_data_source', 'Interne Tickets', 'DATASET.md', 0.7),
                        })
    s = client.post(_url('/data-governance/suggest'), json={'source': 'repo'}, headers=auth_headers)
    assert s.status_code == 200
    assert 'training_data_source' in s.get_json()['suggestions']
    a = client.post(_url('/data-governance/apply'),
                    json={'fields': {'training_data_source': 'Interne Tickets'}}, headers=auth_headers)
    assert a.status_code == 200


# A3 (Art. 9): kein lokaler Risk-Wizard mehr (#1047) — A3 läuft über die
# Risikobewertungs-Verknüpfung (siehe tests/test_aiact_risk_link_1044.py).


# ── Story 5 (#1023): A4 Human-Oversight Wizard ──────────────────────

def test_human_oversight_wizard(client, auth_headers, projekt):
    pr = client.post(_url('/human-oversight/wizard-prompt'), json={}, headers=auth_headers)
    assert pr.status_code == 200 and 'prompt' in pr.get_json()
    resp = json.dumps({'oversight_mode': 'human-in-the-loop', 'intervention_mechanisms': 'Stop-Button'})
    a = client.post(_url('/human-oversight/wizard-apply'), json={'response': resp}, headers=auth_headers)
    assert a.status_code == 200 and 'oversight_mode' in a.get_json()['applied']


# ── Story 6 (#1024): A5 PMM Hilfe + Wizard ──────────────────────────

def test_pmm_help(client, auth_headers):
    r = client.get('/api/aiact/pmm/help', headers=auth_headers)
    assert r.status_code == 200
    body = r.get_json()
    assert 'eu_articles' in body or 'monitoring_plan_snippets' in body


def test_pmm_wizard(client, auth_headers, projekt):
    pr = client.post(_url('/pmm/wizard-prompt'), json={}, headers=auth_headers)
    assert pr.status_code == 200 and 'prompt' in pr.get_json()
    resp = json.dumps({'monitoring_plan': 'Accuracy-Drift wöchentlich', 'serious_incident_reporting_sla': '15 Tage'})
    a = client.post(_url('/pmm/wizard-apply'), json={'response': resp}, headers=auth_headers)
    assert a.status_code == 200 and 'monitoring_plan' in a.get_json()['applied']


# ── #1043: Wizard-Apply mit ungültigem/leerem JSON → 400 (kein stilles Nichts) ──

def test_pmm_wizard_apply_garbage_400(client, auth_headers, projekt):
    r = client.post(_url('/pmm/wizard-apply'), json={'response': 'kein json hier'}, headers=auth_headers)
    assert r.status_code == 400
    assert 'Feld' in r.get_json()['error'] or 'JSON' in r.get_json()['error']


def test_human_oversight_wizard_apply_garbage_400(client, auth_headers, projekt):
    r = client.post(_url('/human-oversight/wizard-apply'), json={'response': 'blubb'}, headers=auth_headers)
    assert r.status_code == 400
