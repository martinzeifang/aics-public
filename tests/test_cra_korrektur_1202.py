"""Tests #1202: CRA Art. 13(19)-(22) Korrekturmaßnahmen/Rückruf-Workflow.

- cra_korrektur-Register mit Maßnahmentyp + betroffenen Versionen/Mitgliedstaaten.
- Behörden-Informations-Record (ja/nein + Datum) + Audit-Trail.
- Status/Abschluss-Workflow (nur vorwärts) + Verknüpfung zu cra_vuln.
- Endpoints GET/POST /projekte/<p>/korrekturmassnahmen (+/status, /behoerde).
"""
import pytest

CRA = '/api/cra'
KOR = '/api/cra-korrektur'
FIRMA = 'pytest-firma-1202'
PROJ = 'pytest-cra-1202'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': PROJ, 'unternehmen': FIRMA})
    yield PROJ
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)


# ── DB-Ebene (tmp-DB) ─────────────────────────────────────────────────────────

def test_status_only_forward(tmp_path):
    from cra import korrektur_db as kdb
    db = tmp_path / 'cra.sqlite'
    kid = kdb.create_korrektur(db, PROJ, {'massnahmentyp': 'rueckruf', 'titel': 'X',
                                          'betroffene_versionen': 'v1-v2',
                                          'betroffene_ms': 'DE'})
    k = kdb.set_status(db, kid, PROJ, 'in_durchfuehrung')
    assert k['status'] == 'in_durchfuehrung'
    with pytest.raises(ValueError):
        kdb.set_status(db, kid, PROJ, 'offen')  # rückwärts verboten
    # Abschluss setzt Datum + Audit-Event
    k = kdb.set_status(db, kid, PROJ, 'abgeschlossen')
    assert k['abgeschlossen_am']
    events = [e['event'] for e in k['audit_trail']]
    assert 'erstellt' in events and 'status_gewechselt' in events


def test_behoerde_record(tmp_path):
    from cra import korrektur_db as kdb
    db = tmp_path / 'cra.sqlite'
    kid = kdb.create_korrektur(db, PROJ, {'massnahmentyp': 'ruecknahme', 'titel': 'Y'})
    k = kdb.get_korrektur(db, kid, PROJ)
    assert k['behoerde_informiert'] is False
    k = kdb.inform_behoerde(db, kid, PROJ, 'BNetzA')
    assert k['behoerde_informiert'] is True
    assert k['behoerde_info_datum']
    assert k['behoerde_name'] == 'BNetzA'
    assert any(e['event'] == 'behoerde_informiert' for e in k['audit_trail'])


def test_invalid_typ(tmp_path):
    from cra import korrektur_db as kdb
    db = tmp_path / 'cra.sqlite'
    with pytest.raises(ValueError):
        kdb.create_korrektur(db, PROJ, {'massnahmentyp': 'loeschung'})


# ── Endpoints ─────────────────────────────────────────────────────────────────

def test_korrektur_lifecycle_api(client, auth_headers, projekt):
    r = client.post(f'{KOR}/projekte/{projekt}/korrekturmassnahmen', headers=auth_headers,
                    json={'massnahmentyp': 'rueckruf', 'titel': 'Firmware-Recall',
                          'ausloeser': 'CVE-2026-1', 'betroffene_versionen': 'v1.0-v1.4',
                          'betroffene_ms': 'DE, FR', 'vuln_id': 42})
    assert r.status_code == 201, r.json
    kid = r.json['id']
    assert r.json['massnahmentyp'] == 'rueckruf'
    assert r.json['vuln_id'] == 42

    # Behörde informieren
    r = client.post(f'{KOR}/projekte/{projekt}/korrekturmassnahmen/{kid}/behoerde',
                    headers=auth_headers, json={'behoerde_name': 'Marktaufsicht'})
    assert r.status_code == 200, r.json
    assert r.json['behoerde_informiert'] is True

    # Status vorwärts
    r = client.post(f'{KOR}/projekte/{projekt}/korrekturmassnahmen/{kid}/status',
                    headers=auth_headers, json={'status': 'abgeschlossen'})
    assert r.status_code == 200, r.json
    assert r.json['abgeschlossen_am']

    # Rückwärts → 400
    r = client.post(f'{KOR}/projekte/{projekt}/korrekturmassnahmen/{kid}/status',
                    headers=auth_headers, json={'status': 'offen'})
    assert r.status_code == 400

    r = client.get(f'{KOR}/projekte/{projekt}/korrekturmassnahmen', headers=auth_headers)
    assert r.status_code == 200 and len(r.json) == 1


def test_idor_scoped(client, auth_headers, projekt):
    r = client.post(f'{KOR}/projekte/{projekt}/korrekturmassnahmen', headers=auth_headers,
                    json={'massnahmentyp': 'korrektur', 'titel': 'X'})
    kid = r.json['id']
    r = client.get(f'{KOR}/projekte/fremd-projekt/korrekturmassnahmen/{kid}',
                   headers=auth_headers)
    assert r.status_code == 404
