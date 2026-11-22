"""#1577 — Framework einer Risikobewertung nachträglich ändern (mit Pflicht-Neubewertung)."""
import pytest

from risikobewertung.framework_wechsel import neubewertung_markieren, warnungen, MARKER

P = 'pytest-1577-rb'


def test_neubewertung_markieren_archiviert_und_setzt_zurueck():
    r = {'id': 1, 'framework': 'STRIDE', 'risikowert': 16, 'risiko_label': 'Hoch',
         'detail_text': 'W=4 × I=4', 'bewertung_text': 'Alte Begründung',
         'felder': {'stride_kategorie': 'Spoofing', 'auswirkung': 'Hoch', '_source': 'req-gap'}}
    n = neubewertung_markieren(r, 'STRIDE', 'EU-AI-Act', '2026-10-16')
    assert n['framework'] == 'EU-AI-Act'
    assert n['risikowert'] is None and n['risiko_label'] == '' and n['detail_text'] == ''
    assert n['felder']['_source'] == 'req-gap'                       # Meta bleibt
    assert 'stride_kategorie' not in n['felder']                     # alte Felder nicht übernommen
    assert n['felder']['_vorher']['felder']['stride_kategorie'] == 'Spoofing'
    assert n['felder']['_vorher']['risiko_label'] == 'Hoch'
    assert MARKER in n['bewertung_text'] and 'Hoch (16)' in n['bewertung_text']
    assert n['bewertung_text'].endswith('Alte Begründung')


def test_warnungen():
    w = warnungen({'meta': {'linked_aiact_projekt': 'X – KI'}}, 'EU-AI-Act', 'STRIDE')
    assert any('AIA-HR-01' in x for x in w)
    assert any('DSFA' in x for x in warnungen({'meta': {}}, 'DSGVO-DSFA', 'STRIDE'))
    assert warnungen({'meta': {}}, 'STRIDE', 'TARA') == []


@pytest.fixture
def projekt():
    from server.api.risikobewertung import DB_PATH
    from risikobewertung.db import save_projekt, delete_projekt, bulk_insert_risiken, load_risiken, save_risiko
    try:
        delete_projekt(DB_PATH, P)
    except Exception:
        pass
    save_projekt(DB_PATH, P, 'STRIDE', '')
    bulk_insert_risiken(DB_PATH, P, [{'risk_name': 'A', 'beschreibung': 'a', 'framework': 'STRIDE'},
                                     {'risk_name': 'B', 'beschreibung': 'b', 'framework': 'STRIDE'}])
    r = load_risiken(DB_PATH, P)[0]
    r.update({'risikowert': 12, 'risiko_label': 'Mittel', 'bewertung_text': 'ok',
              'felder': {'stride_kategorie': 'Tampering'}, 'projekt_name': P})
    save_risiko(DB_PATH, r)
    yield DB_PATH
    try:
        delete_projekt(DB_PATH, P)
    except Exception:
        pass


def test_endpoint_preview_confirm_und_wechsel(client, auth_headers, projekt):
    from risikobewertung.db import load_risiken, load_projekt
    base = f'/api/risikobewertung/projekte/{P}/framework'
    r = client.post(base, headers=auth_headers, json={'framework': 'EU-AI-Act', 'dry_run': True})
    assert r.status_code == 200
    pv = r.get_json()
    assert pv['risiken'] == 2 and pv['bewertet'] == 1 and pv['geaendert'] is False
    assert load_projekt(projekt, P)['framework'] == 'STRIDE'          # Vorschau ändert nichts

    assert client.post(base, headers=auth_headers, json={'framework': 'EU-AI-Act'}).status_code == 428
    assert client.post(base, headers=auth_headers, json={'framework': 'Quatsch', 'confirm': True}).status_code == 400

    r = client.post(base, headers=auth_headers, json={'framework': 'EU-AI-Act', 'confirm': True})
    assert r.status_code == 200 and r.get_json()['geaendert'] is True
    assert load_projekt(projekt, P)['framework'] == 'EU-AI-Act'
    for risk in load_risiken(projekt, P):
        assert risk['framework'] == 'EU-AI-Act'
        assert not risk.get('risiko_label') and risk.get('risikowert') is None
        assert MARKER in risk['bewertung_text']


def test_put_wechselt_nicht_mehr_stillschweigend(client, auth_headers, projekt):
    from risikobewertung.db import load_risiken
    r = client.put(f'/api/risikobewertung/projekte/{P}', headers=auth_headers, json={'framework': 'TARA'})
    assert r.status_code == 200
    risiken = load_risiken(projekt, P)
    assert all(x['framework'] == 'TARA' and MARKER in x['bewertung_text'] for x in risiken)
    # Gleiches Framework erneut → keine weitere Markierung
    client.put(f'/api/risikobewertung/projekte/{P}', headers=auth_headers, json={'framework': 'TARA'})
    assert all(load_risiken(projekt, P)[i]['bewertung_text'].count(MARKER) == 1 for i in range(2))
