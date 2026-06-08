"""Tests #938: C5-Threat-Model-Framework aus verknüpfter Risikobewertung.

- Einheitliche Framework-Liste (8 Frameworks, Superset der Risikobewertung).
- adopt_threatmodel_framework: Übernahme + Schutz manueller Overrides.
- API: Verknüpfung übernimmt Framework; manuelle Änderung → manual_override (sticky).
"""
from pathlib import Path

import pytest

CRA = '/api/cra'
RB = '/api/risikobewertung'
FIRMA = 'pytest-firma-938'
CRA_PROJ = 'pytest-cra-938'
RB_PROJ = 'pytest-rb-938'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ── reine Logik ────────────────────────────────────────────────────────────

def test_framework_list_is_superset_of_rb():
    from cra.threat_frameworks import THREAT_FRAMEWORK_IDS
    from risikobewertung.frameworks import FRAMEWORK_IDS
    assert len(THREAT_FRAMEWORK_IDS) == 9  # +EU-AI-Act (#1044)
    for fid in FRAMEWORK_IDS:
        assert fid in THREAT_FRAMEWORK_IDS, f"{fid} fehlt in C5-Liste"
    # CRA-spezifische Ergänzungen vorhanden
    assert 'PASTA' in THREAT_FRAMEWORK_IDS
    assert 'LINDDUN' in THREAT_FRAMEWORK_IDS


@pytest.fixture
def cra_db(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    db = repo_root / 'data' / 'db' / 'pytest_tm_938.sqlite'
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    from cra import db as cradb
    cradb.ensure_db(db)
    yield db
    if db.exists():
        db.unlink()


def test_adopt_sets_risk_link(cra_db):
    from cra.db import adopt_threatmodel_framework, load_threatmodel
    res = adopt_threatmodel_framework(cra_db, 'P', 'TARA')
    assert res['adopted'] is True
    tm = load_threatmodel(cra_db, 'P')
    assert tm['framework'] == 'TARA'
    assert tm['framework_source'] == 'risk_link'


def test_adopt_respects_manual_override(cra_db):
    from cra.db import save_threatmodel, adopt_threatmodel_framework, load_threatmodel
    save_threatmodel(cra_db, 'P', {'framework': 'OCTAVE', 'framework_source': 'manual_override'})
    res = adopt_threatmodel_framework(cra_db, 'P', 'TARA')
    assert res['adopted'] is False
    assert res['reason'] == 'manual_override'
    assert load_threatmodel(cra_db, 'P')['framework'] == 'OCTAVE'


def test_adopt_idempotent_when_already_linked(cra_db):
    from cra.db import adopt_threatmodel_framework
    adopt_threatmodel_framework(cra_db, 'P', 'TARA')
    res = adopt_threatmodel_framework(cra_db, 'P', 'TARA')
    assert res['adopted'] is False
    assert res['reason'] == 'unchanged'


# ── API-Integration ────────────────────────────────────────────────────────

@pytest.fixture
def projekte(client, auth_headers):
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': CRA_PROJ, 'unternehmen': FIRMA, 'produkt': 'P'})
    client.post(f'{RB}/projekte', headers=auth_headers,
                json={'name': RB_PROJ, 'framework': 'TARA', 'unternehmen': FIRMA})
    yield
    client.delete(f'{CRA}/projekte/{CRA_PROJ}', headers=auth_headers)
    client.delete(f'{RB}/projekte/{RB_PROJ}', headers=auth_headers)


def test_frameworks_endpoint(client, auth_headers):
    r = client.get(f'{CRA}/threat-frameworks', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    ids = [f['id'] for f in r.get_json()['frameworks']]
    assert 'TARA' in ids and len(ids) == 9  # +EU-AI-Act (#1044)


def test_link_adopts_framework(client, auth_headers, projekte):
    r = client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
                   json={'risk_projekt': RB_PROJ})
    assert r.status_code == 200, r.get_json()
    adopted = r.get_json().get('framework_adopted')
    assert adopted and adopted.get('framework') == 'TARA'
    # Threat-Model trägt nun TARA aus der Verknüpfung
    tm = client.get(f'{CRA}/projekte/{CRA_PROJ}/threatmodel', headers=auth_headers).get_json()
    assert tm['framework'] == 'TARA'
    assert tm['framework_source'] == 'risk_link'


def test_manual_change_sets_override(client, auth_headers, projekte):
    client.put(f'{CRA}/projekte/{CRA_PROJ}/risk-link', headers=auth_headers,
               json={'risk_projekt': RB_PROJ})
    # Auditor weicht bewusst ab
    s = client.post(f'{CRA}/projekte/{CRA_PROJ}/threatmodel', headers=auth_headers,
                    json={'framework': 'OCTAVE', 'scope': 'org-weit'})
    assert s.get_json().get('framework_source') == 'manual_override'
    tm = client.get(f'{CRA}/projekte/{CRA_PROJ}/threatmodel', headers=auth_headers).get_json()
    assert tm['framework'] == 'OCTAVE'
    assert tm['framework_source'] == 'manual_override'
