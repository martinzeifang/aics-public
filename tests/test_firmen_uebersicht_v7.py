"""v7.0.0 — Firmen-Gesamtüberblick (Dashboard) + Firmen-Berichts-Center."""
import pytest

F = 'pytest-v7-firma'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def firma(client, auth_headers):
    client.delete(f'/api/firmen/{F}/permanent', headers=auth_headers)
    r = client.post('/api/firmen', headers=auth_headers, json={'name': F, 'company': 'PyTest GmbH'})
    assert r.status_code == 201, r.get_json()
    yield F
    client.delete(f'/api/firmen/{F}', headers=auth_headers)
    client.delete(f'/api/firmen/{F}/permanent', headers=auth_headers)


def test_uebersicht_struktur_und_reifegrad_wie_modul(client, auth_headers, firma):
    # CRA-Bewertung setzen → Firmen-Übersicht muss denselben Wert wie der CRA-Endpunkt zeigen
    r = client.get('/api/firmen/' + F + '/uebersicht', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    u = r.get_json()
    keys = [m['key'] for m in u['module']]
    assert keys == ['cra', 'nis2', 'ai_act', 'dsgvo', 'wiba', 'risikobewertung']
    for k in ('gesamt_pct', 'risiken', 'tom', 'aufgaben', 'berichte', 'produkte', 'nachweise'):
        assert k in u
    cra = next(m for m in u['module'] if m['key'] == 'cra')
    assert cra['projekte'], 'Firmenanlage legt das CRA-Projekt an (#430)'
    if cra['projekte']:
        p = cra['projekte'][0]['name']
        req = client.get(f'/api/cra/projekte/{p}/anforderungen', headers=auth_headers).get_json()
        rid = (req[0] if isinstance(req, list) else (req.get('anforderungen') or req.get('items'))[0])['id']
        client.post(f'/api/cra/projekte/{p}/bewertungen', headers=auth_headers,
                    json={'anforderung_id': rid, 'bewertung': 5, 'kommentar': 'x'})
        modul_pct = client.get(f'/api/cra/projekte/{p}/reifegrad', headers=auth_headers).get_json()['gesamt']['prozent']
        u2 = client.get('/api/firmen/' + F + '/uebersicht', headers=auth_headers).get_json()
        cra2 = next(m for m in u2['module'] if m['key'] == 'cra')
        assert next(x for x in cra2['projekte'] if x['name'] == p)['pct'] == pytest.approx(modul_pct, abs=0.1)
        assert modul_pct > 0


def test_uebersicht_404(client, auth_headers):
    assert client.get('/api/firmen/gibt-es-nicht-v7/uebersicht', headers=auth_headers).status_code == 404


def test_berichts_center_katalog_und_export(client, auth_headers, firma):
    r = client.get(f'/api/firmen/projekte/{F}/berichte', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert {x['key'] for x in body['reports']} == {'gesamt', 'risiken'}
    assert body['ki_summary'] is True
    for typ in ('gesamt', 'risiken'):
        r = client.get(f'/api/firmen/projekte/{F}/berichte/{typ}?format=docx', headers=auth_headers)
        assert r.status_code == 200, r.get_data(as_text=True)[:300]
        assert r.data[:2] == b'PK'                      # DOCX (ZIP)
    r = client.post(f'/api/firmen/projekte/{F}/berichte/gesamt/generate', headers=auth_headers,
                    json={'format': 'docx'})
    assert r.status_code == 201, r.get_json()
    runs = client.get(f'/api/firmen/projekte/{F}/berichte', headers=auth_headers).get_json()['runs']
    assert any(x['typ'] == 'gesamt' and x['status'] == 'finished' for x in runs)


def test_summary_context(firma):
    from firmen.berichte_provider import summary_context
    ctx = summary_context(F)
    assert 'gesamt_umsetzungsgrad_pct' in ctx and 'risiken' in ctx and 'module' in ctx
