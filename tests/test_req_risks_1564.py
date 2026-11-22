"""#1564 — Risiko für Nichterfüllung an Anforderungen/OWASP (CRA, NIS2, DSGVO, AI Act)."""
import pytest

PRE = 'pytest-1564'
PROJ = {'cra': f'{PRE}-cra', 'nis2': f'{PRE}-nis2', 'dsgvo': f'{PRE}-dsgvo', 'aiact': f'{PRE}-aiact'}
CREATE = {
    'cra': ('/api/cra/projekte', {'name': PROJ['cra'], 'unternehmen': f'{PRE}-firma'}),
    'nis2': ('/api/nis2/projekte', {'name': PROJ['nis2'], 'unternehmen': f'{PRE}-firma'}),
    'dsgvo': ('/api/dsgvo/projekte', {'name': PROJ['dsgvo'], 'unternehmen': f'{PRE}-firma'}),
    'aiact': ('/api/aiact/projekte', {'name': PROJ['aiact'], 'organisation': f'{PRE}-firma'}),
}


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _wipe_rb():
    from risikobewertung.db import list_projekte, delete_projekt
    from shared.req_risks import RB_DB_PATH
    from shared import db as _sdb
    from shared.risk_req_links import ensure_tables
    ensure_tables(RB_DB_PATH)
    for n in list_projekte(RB_DB_PATH):
        if n.startswith(PRE):
            with _sdb.connect(RB_DB_PATH) as con:
                con.execute("DELETE FROM risk_requirement_links WHERE rb_projekt_name=?", (n,))
            delete_projekt(RB_DB_PATH, n)


@pytest.fixture
def projekte(client, auth_headers):
    def clean():
        for m, (url, body) in CREATE.items():
            client.delete(f"{url}/{body['name']}", headers=auth_headers)
        _wipe_rb()
    clean()
    for m, (url, body) in CREATE.items():
        r = client.post(url, headers=auth_headers, json=body)
        assert r.status_code in (200, 201), (m, r.get_json())
    yield
    clean()


def _base(m):
    return f"/api/{m}/projekte/{PROJ[m]}/req-risks"


@pytest.mark.parametrize('modul', ['cra', 'nis2', 'dsgvo', 'aiact'])
def test_full_flow_per_module(client, auth_headers, projekte, modul):
    h = auth_headers
    ov = client.get(_base(modul), headers=h).get_json()
    assert ov['linked_risk_projekt'] is None and 'candidates' in ov

    r = client.post(f"{_base(modul)}/create-rb", headers=h, json={})
    assert r.status_code == 201, r.get_json()
    rb = r.get_json()['linked_risk_projekt']
    from risikobewertung.db import load_projekt as rb_load, load_risiken
    from shared.req_risks import RB_DB_PATH
    if modul == 'aiact':
        assert rb_load(RB_DB_PATH, rb)['framework'] == 'EU-AI-Act'

    obj = f"{_base(modul)}/requirement/REQ-X1"
    c = client.post(obj, headers=h, json={'titel': 'Testanforderung', 'score': 2, 'kommentar': 'Lücke'})
    assert c.status_code == 201, c.get_json()
    d = c.get_json()
    assert len(d['risks']) == 1 and d['risks'][0]['bewertet'] is False   # unbewertet → in RB bewerten
    risk = next(x for x in load_risiken(RB_DB_PATH, rb) if x['id'] == d['risks'][0]['id'])
    assert 'Nichterfüllung REQ-X1' in risk['risk_name'] and '2/5' in risk['beschreibung']

    # Herkunft in der Risikobewertung sichtbar
    links = client.get(f"/api/risikobewertung/projekte/{rb}/risiken/{risk['id']}/req-links",
                       headers=h).get_json()['items']
    assert links == [{'modul': modul, 'modul_label': links[0]['modul_label'], 'object_kind': 'requirement',
                      'object_id': 'REQ-X1', 'projekt': PROJ[modul]}]

    # Vorhandenes Risiko an zweites Objekt hängen, dann lösen (Risiko bleibt)
    o2 = f"{_base(modul)}/{'owasp_llm' if modul == 'aiact' else 'owasp'}/C9"
    assert client.post(o2, headers=h, json={'risk_id': risk['id']}).status_code == 200
    assert client.get(_base(modul), headers=h).get_json()['coverage'] == {
        'requirement:REQ-X1': 1, f"{'owasp_llm' if modul == 'aiact' else 'owasp'}:C9": 1}
    u = client.delete(f"{o2}/{risk['id']}", headers=h)
    assert u.status_code == 200 and u.get_json()['risks'] == []
    assert any(x['id'] == risk['id'] for x in load_risiken(RB_DB_PATH, rb))


def test_aiact_rejects_non_eu_ai_act_rb(client, auth_headers, projekte):
    from risikobewertung.db import save_projekt
    from shared.req_risks import RB_DB_PATH
    save_projekt(RB_DB_PATH, f'{PRE}-stride', 'STRIDE', '')
    r = client.put(f"{_base('aiact')}/link", headers=auth_headers, json={'rb_projekt': f'{PRE}-stride'})
    assert r.status_code == 400
    assert client.put(f"{_base('cra')}/link", headers=auth_headers,
                      json={'rb_projekt': f'{PRE}-stride'}).status_code == 200


def test_errors(client, auth_headers, projekte):
    h = auth_headers
    assert client.get('/api/cra/projekte/gibt-es-nicht-1564/req-risks', headers=h).status_code == 404
    assert client.post(f"{_base('cra')}/requirement/X", headers=h, json={}).status_code == 400  # keine RB
    client.post(f"{_base('cra')}/create-rb", headers=h, json={})
    assert client.post(f"{_base('cra')}/create-rb", headers=h, json={}).status_code == 400   # schon verknüpft
    assert client.post(f"{_base('cra')}/bogus/X", headers=h, json={}).status_code == 400
    assert client.post(f"{_base('cra')}/requirement/X", headers=h, json={'risk_id': 999999}).status_code == 404


def test_rb_editor_cra_mapping_keeps_other_links(client, auth_headers, projekte):
    """Der RB-Editor (#885) ersetzt nur CRA-Anforderungs-Links — OWASP-/Fremdmodul-Links bleiben."""
    h = auth_headers
    rb = client.post(f"{_base('cra')}/create-rb", headers=h, json={}).get_json()['linked_risk_projekt']
    rid = client.post(f"{_base('cra')}/owasp/C1", headers=h,
                      json={'titel': 'Access Control'}).get_json()['risks'][0]['id']
    client.post(f"{_base('cra')}/requirement/AI1-01", headers=h, json={'risk_id': rid})
    assert client.get(f"/api/risikobewertung/projekte/{rb}/risiken/{rid}/cra-requirements",
                      headers=h).get_json()['anforderungen'] == ['AI1-01']
    client.post(f"/api/risikobewertung/projekte/{rb}/risiken/{rid}/cra-requirements", headers=h,
                json={'anforderungen': []})
    kinds = {(l['object_kind'], l['object_id']) for l in client.get(
        f"/api/risikobewertung/projekte/{rb}/risiken/{rid}/req-links", headers=h).get_json()['items']}
    assert kinds == {('owasp', 'C1')}
