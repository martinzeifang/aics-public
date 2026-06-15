"""#1044 — A3 via Risikobewertung: Framework EU-AI-Act + AI-Act↔RB-Verknüpfung."""
from pathlib import Path

import pytest

from server.api.aiact import DB_PATH
from ai_act.db import save_projekt, update_projekt_meta, delete_projekt
from risikobewertung.db import (save_projekt as rb_save, save_risiko, load_projekt as rb_load)
from risikobewertung.frameworks import FRAMEWORK_IDS, framework_felder, berechne_risiko

APROJ = 'pytest-aiact-1044'
RBPROJ = 'pytest-rb-1044'
RB_DB = Path('data/db/risikobewertung.sqlite')


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ── reine Framework-Logik ───────────────────────────────────────────

def test_framework_registered():
    assert 'EU-AI-Act' in FRAMEWORK_IDS
    keys = [f['key'] for f in framework_felder('EU-AI-Act')]
    assert 'lifecycle_phase' in keys and 'risk_category' in keys


def test_framework_scoring():
    felder = framework_felder('EU-AI-Act')
    f = {'lifecycle_phase': 'deployment', 'risk_category': 'bias – x',
         'eintrittswahrscheinlichkeit': felder[2]['optionen'][-1],
         'auswirkung': felder[3]['optionen'][-1]}
    score, label, detail = berechne_risiko('EU-AI-Act', f)
    assert score == 25 and label == 'Kritisch'
    assert berechne_risiko('EU-AI-Act', {})[0] is None


# ── Verknüpfungs-Endpoints ──────────────────────────────────────────

@pytest.fixture
def linked():
    save_projekt(DB_PATH, name=APROJ, organisation='ACME', produkt='Widget', beschreibung='')
    rb_save(RB_DB, RBPROJ, framework='EU-AI-Act', beschreibung='', unternehmen='ACME')
    save_risiko(RB_DB, {'projekt_name': RBPROJ, 'nr': 1, 'risk_name': 'Bias im Scoring',
                        'framework': 'EU-AI-Act', 'risikowert': 16, 'risiko_label': 'hoch'})
    yield
    delete_projekt(DB_PATH, APROJ)
    import sqlite3
    try:
        con = sqlite3.connect(str(RB_DB))
        con.execute("DELETE FROM rb_risiken WHERE projekt_name=?", (RBPROJ,))
        con.execute("DELETE FROM rb_projekte WHERE name=?", (RBPROJ,))
        con.commit(); con.close()
    except Exception:
        pass


def _u(s=''):
    return f'/api/aiact/projekte/{APROJ}/risk-link{s}'


def test_candidates(client, auth_headers, linked):
    r = client.get(_u('/candidates'), headers=auth_headers)
    assert r.status_code == 200
    names = [c['name'] for c in r.get_json()['candidates']]
    assert RBPROJ in names


def test_candidates_cross_firma_and_only_eu_ai_act(client, auth_headers, linked):
    """#1046: EU-AI-Act-RB-Projekt mit abweichender Firma muss Kandidat sein;
    andere Bewertungsarten werden ausgeschlossen."""
    other = 'pytest-rb-1046-otherfirma'        # EU-AI-Act, fremde Firma → muss erscheinen
    octave = 'pytest-rb-1046-octave'           # andere Bewertungsart → muss fehlen
    rb_save(RB_DB, other, framework='EU-AI-Act', beschreibung='', unternehmen='GANZ-ANDERE-GMBH')
    rb_save(RB_DB, octave, framework='OCTAVE', beschreibung='', unternehmen='ACME')
    try:
        r = client.get(_u('/candidates'), headers=auth_headers)
        assert r.status_code == 200
        cands = {c['name']: c for c in r.get_json()['candidates']}
        # firmenfremdes EU-AI-Act-Projekt taucht trotzdem auf
        assert other in cands
        assert cands[other]['framework_match'] is True
        assert cands[other]['firma_match'] is False
        # OCTAVE (gleiche Firma!) ist NICHT zulässig → fehlt
        assert octave not in cands
        # Firmen-Treffer ist als solcher markiert und steht vorn
        assert cands[RBPROJ]['firma_match'] is True
        assert r.get_json()['candidates'][0]['name'] == RBPROJ
    finally:
        import sqlite3
        con = sqlite3.connect(str(RB_DB))
        con.execute("DELETE FROM rb_projekte WHERE name IN (?,?)", (other, octave))
        con.commit(); con.close()


def test_link_rejects_non_eu_ai_act(client, auth_headers, linked):
    """#1046: PUT verweigert die Verknüpfung mit einer Nicht-EU-AI-Act-Bewertung."""
    octave = 'pytest-rb-1046-octave-put'
    rb_save(RB_DB, octave, framework='OCTAVE', beschreibung='', unternehmen='ACME')
    try:
        r = client.put(_u(), json={'risk_projekt': octave}, headers=auth_headers)
        assert r.status_code == 400
        assert 'EU-AI-Act' in r.get_json()['error']
    finally:
        import sqlite3
        con = sqlite3.connect(str(RB_DB))
        con.execute("DELETE FROM rb_projekte WHERE name=?", (octave,))
        con.commit(); con.close()


def test_link_get_linkedrisks_unlink(client, auth_headers, linked):
    # initial: nicht verknüpft
    g0 = client.get(_u(), headers=auth_headers)
    assert g0.status_code == 200 and g0.get_json()['linked_risk_projekt'] is None
    # setzen
    s = client.put(_u(), json={'risk_projekt': RBPROJ}, headers=auth_headers)
    assert s.status_code == 200 and s.get_json()['linked_risk_projekt'] == RBPROJ
    assert s.get_json()['summary']['total'] == 1
    # bidirektional in RB-Meta
    assert (rb_load(RB_DB, RBPROJ).get('meta') or {}).get('linked_aiact_projekt') == APROJ
    # linked-risks
    lr = client.get(f'/api/aiact/projekte/{APROJ}/linked-risks', headers=auth_headers)
    assert lr.status_code == 200 and lr.get_json()['linked'] is True
    assert any(x['risk_name'] == 'Bias im Scoring' for x in lr.get_json()['risiken'])
    # lösen
    d = client.delete(_u(), headers=auth_headers)
    assert d.status_code == 200
    assert client.get(_u(), headers=auth_headers).get_json()['linked_risk_projekt'] is None


def test_link_unknown_rb_404(client, auth_headers, linked):
    r = client.put(_u(), json={'risk_projekt': 'gibtsnicht'}, headers=auth_headers)
    assert r.status_code == 404


def test_linked_a3_risks_helper(client, auth_headers, linked):
    """#1047: linked_a3_risks liest A3-Risiken aus dem verknüpften RB-Projekt
    und mappt sie in die von den A3-Konsumenten erwartete Feldform."""
    from ai_act.db import linked_a3_risks
    # ohne Verknüpfung: leer
    assert linked_a3_risks(DB_PATH, APROJ) == []
    # verknüpfen, dann liefert der Helper das RB-Risiko normalisiert
    s = client.put(_u(), json={'risk_projekt': RBPROJ}, headers=auth_headers)
    assert s.status_code == 200
    risks = linked_a3_risks(DB_PATH, APROJ)
    assert len(risks) == 1
    r = risks[0]
    assert r['titel'] == 'Bias im Scoring'
    assert r['risk_score'] == 16
    assert r['status'] == 'offen'           # is_resolved=0 → offen
    assert {'risk_id', 'lifecycle_phase', 'risk_category', 'severity'} <= set(r)
