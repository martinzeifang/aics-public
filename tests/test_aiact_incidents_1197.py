"""#1197 — AI-Act Art. 73 Serious-Incident-Register: Schweregrad/Frist, Lifecycle,
Fristenuhr (2/10/15 Tage), A23-Report-Bindung, Issue-Link.

Test-Isolation: alle DB_PATH-Globals (aiact-Haupt + Incidents-Blueprint + DB-Modul)
werden auf eine eigene Temp-SQLite **innerhalb** des Workspace umgebogen
(connect_sqlite verlangt einen Pfad unter dem Repo-Root).
"""
import uuid
from datetime import datetime, timezone

import pytest

BASE = '/api/aiact'
INC = '/api/aiact-incidents'
PROJ = 'pytest-inc-1197'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch):
    """Isolierte Temp-DB unter data/db/ (Workspace-Root-Constraint von connect_sqlite)."""
    from pathlib import Path
    db = Path('data/db') / f'test_aiact_inc_{uuid.uuid4().hex}.sqlite'
    import server.api.aiact as aiact_main
    import server.api.aiact_incidents as bp
    import ai_act.incidents as mod
    import ai_act.db as db_mod
    db_mod.ensure_db(db)
    monkeypatch.setattr(aiact_main, 'DB_PATH', db, raising=False)
    monkeypatch.setattr(bp, 'DB_PATH', db, raising=False)
    monkeypatch.setattr(mod, 'DB_PATH', db, raising=False)
    yield db
    for sfx in ('', '-wal', '-shm'):
        p = Path(str(db) + sfx)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


@pytest.fixture
def projekt(client, auth_headers):
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': PROJ, 'produkt': 'Test-KI', 'beschreibung': 'Use-Case'})
    assert r.status_code in (200, 201), r.get_json()
    return PROJ


def test_constants_has_severity_and_frist():
    from ai_act import incidents as inc
    sg = {s['code']: s for s in inc.schweregrade()}
    assert sg['weit_verbreitet']['frist_tage'] == 2
    assert sg['tod']['frist_tage'] == 10
    assert sg['schwere_schaedigung']['frist_tage'] == 15
    assert sg['standard']['frist_tage'] == 15


def test_create_and_list(client, auth_headers, projekt):
    r = client.post(f'{INC}/projekte/{PROJ}/incidents', headers=auth_headers,
                    json={'titel': 'Datenleck', 'schweregrad': 'tod',
                          'kenntnis_datum': '2026-06-01'})
    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert d['frist_tage'] == 10
    assert d['schweregrad_label']
    lst = client.get(f'{INC}/projekte/{PROJ}/incidents', headers=auth_headers).get_json()
    assert lst['summary']['gesamt'] == 1
    assert lst['summary']['offen'] == 1


def test_deadline_due_date_derivation(client, auth_headers, projekt):
    """Bei Schweregrad 'tod' (10 Tage) muss die Regelstufe overdue sein,
    wenn der Kenntnis-Zeitpunkt > 10 Tage zurückliegt."""
    r = client.post(f'{INC}/projekte/{PROJ}/incidents', headers=auth_headers,
                    json={'titel': 'X', 'schweregrad': 'tod',
                          'kenntnis_datum': '2020-01-01'})
    d = r.get_json()
    assert d['overdue'] is True
    assert d['ampel'] == 'red'
    # next_due / due_date gesetzt
    assert d['due_date']


def test_status_lifecycle_and_fulfilled_stops_clock(client, auth_headers, projekt):
    r = client.post(f'{INC}/projekte/{PROJ}/incidents', headers=auth_headers,
                    json={'titel': 'Y', 'schweregrad': 'standard',
                          'kenntnis_datum': '2020-01-01'})
    iid = r.get_json()['id']
    # Vollbericht gemeldet → Regelstufe erfüllt → nicht mehr überfällig.
    u = client.put(f'{INC}/projekte/{PROJ}/incidents/{iid}', headers=auth_headers,
                   json={'titel': 'Y', 'schweregrad': 'standard',
                         'kenntnis_datum': '2020-01-01', 'status': 'abgeschlossen',
                         'vollbericht_am': '2020-01-05'})
    assert u.status_code == 200, u.get_json()
    d = u.get_json()
    assert d['overdue'] is False


def test_invalid_severity_rejected(client, auth_headers, projekt):
    r = client.post(f'{INC}/projekte/{PROJ}/incidents', headers=auth_headers,
                    json={'titel': 'Z', 'schweregrad': 'unbekannt'})
    assert r.status_code == 400


def test_attach_a23_report(client, auth_headers, projekt):
    r = client.post(f'{INC}/projekte/{PROJ}/incidents', headers=auth_headers,
                    json={'titel': 'Mit Report', 'schweregrad': 'standard'})
    iid = r.get_json()['id']
    a = client.post(f'{INC}/projekte/{PROJ}/incidents/{iid}/report', headers=auth_headers,
                    json={'report_text': 'A23-generierter Bericht'})
    assert a.status_code == 200, a.get_json()
    assert a.get_json()['report_text'] == 'A23-generierter Bericht'


def test_attach_report_requires_text(client, auth_headers, projekt):
    r = client.post(f'{INC}/projekte/{PROJ}/incidents', headers=auth_headers,
                    json={'titel': 'NoReport', 'schweregrad': 'standard'})
    iid = r.get_json()['id']
    a = client.post(f'{INC}/projekte/{PROJ}/incidents/{iid}/report', headers=auth_headers,
                    json={})
    assert a.status_code == 400


def test_issue_link_manual(client, auth_headers, projekt):
    r = client.post(f'{INC}/projekte/{PROJ}/incidents', headers=auth_headers,
                    json={'titel': 'Link', 'schweregrad': 'standard'})
    iid = r.get_json()['id']
    lk = client.post(f'{INC}/projekte/{PROJ}/incidents/{iid}/issues/link', headers=auth_headers,
                     json={'url': 'https://github.com/org/repo/issues/42'})
    assert lk.status_code == 201, lk.get_json()
    assert lk.get_json()['number'] == 42
    lst = client.get(f'{INC}/projekte/{PROJ}/incidents/{iid}/issues', headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.get_json()['links']) == 1


def test_project_scoped_404(client, auth_headers, projekt):
    r = client.get(f'{INC}/projekte/does-not-exist-xyz/incidents', headers=auth_headers)
    assert r.status_code == 404


def test_delete(client, auth_headers, projekt):
    r = client.post(f'{INC}/projekte/{PROJ}/incidents', headers=auth_headers,
                    json={'titel': 'Del', 'schweregrad': 'standard'})
    iid = r.get_json()['id']
    d = client.delete(f'{INC}/projekte/{PROJ}/incidents/{iid}', headers=auth_headers)
    assert d.status_code == 200
    lst = client.get(f'{INC}/projekte/{PROJ}/incidents', headers=auth_headers).get_json()
    assert lst['summary']['gesamt'] == 0
