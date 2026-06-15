"""#1088/#1089 — AI-Act Pflicht-Doku-Status: Sektion erst grün, wenn ALLE
inhaltlichen Pflichtfelder befüllt sind (A1/A2/A4/A5)."""
import pytest

from server.api.aiact import DB_PATH
from ai_act.db import (save_projekt, delete_projekt, save_system_doku,
                       save_human_oversight)

PROJ = 'pytest-aiact-status-1088'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekt():
    delete_projekt(DB_PATH, PROJ)
    save_projekt(DB_PATH, name=PROJ, organisation='ACME', produkt='X', beschreibung='')
    yield
    import sqlite3
    con = sqlite3.connect(str(DB_PATH))
    for t in ('aiact_system_doku', 'aiact_human_oversight'):
        try: con.execute(f"DELETE FROM {t} WHERE projekt_name=?", (PROJ,))
        except sqlite3.OperationalError: pass
    con.commit(); con.close()
    delete_projekt(DB_PATH, PROJ)


def _status(client, headers):
    r = client.get(f'/api/aiact/projekte/{PROJ}/pflicht-doku', headers=headers)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_a1_not_green_with_only_system_name(client, auth_headers, projekt):
    # #1089: nur system_name → NICHT grün
    save_system_doku(DB_PATH, PROJ, {'system_name': 'Nur Name'})
    s = _status(client, auth_headers)
    assert s['system_doku']['ok'] is False
    assert 'intended_purpose' in s['system_doku']['missing']


def test_a1_green_when_all_filled(client, auth_headers, projekt):
    save_system_doku(DB_PATH, PROJ, {
        'system_name': 'N', 'version': '1.0', 'provider': 'ACME', 'intended_purpose': 'P',
        'architecture': 'A', 'training_methodology': 'T', 'computational_resources': 'C',
        'test_methodology': 'TM', 'cybersecurity_measures': 'CM', 'accuracy_robustness': 'AR'})
    s = _status(client, auth_headers)
    assert s['system_doku']['ok'] is True
    assert s['system_doku']['missing'] == []


def test_a4_green_when_all_filled(client, auth_headers, projekt):
    # #1088: A4 grün, wenn alle Felder befüllt
    s0 = _status(client, auth_headers)
    assert s0['human_oversight']['ok'] is False
    save_human_oversight(DB_PATH, PROJ, {
        'oversight_mode': 'human-in-the-loop', 'intervention_mechanisms': 'Stop',
        'monitoring_interface': 'Dashboard', 'output_interpretation_aids': 'Confidence',
        'abnormal_behavior_detection': 'Drift-Alarm', 'training_program': 'jährlich'})
    s1 = _status(client, auth_headers)
    assert s1['human_oversight']['ok'] is True
    assert s1['human_oversight']['missing'] == []
