"""Tests fuer die automatische Vervollstaendigung geloester Anforderungen (#833).

Deckt die gemeinsamen Helfer (shared/issue_completion.py) sowie das Verhalten
der Endpunkte ``/issues/sync`` und ``.../bewertungen`` fuer CRA und AI-Act ab.

Der Issue-Status wird ausschliesslich ueber persistierte ``linked_issues``-Zeilen
mit ``state='closed'`` simuliert; es werden keine Netzwerkaufrufe gemacht.
Projekte werden - wie in den Referenztests (#795/#830) - ueber den API-Client
auf der echten Default-DB angelegt; ``linked_issues`` wird je Testprojekt
gezielt geleert.
"""
import sqlite3

import pytest

from shared.issue_links import add_link


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# -- Unit-Tests der gemeinsamen Helfer ---------------------------------------

def test_first_resolved_link_uses_persisted_state():
    from shared.issue_completion import first_resolved_link

    class L:
        def __init__(self, state, reason=''):
            self.state = state
            self.state_reason = reason
            self.issue_number = 1
            self.url = 'https://github.com/o/r/issues/1'

    assert first_resolved_link([L('open')]) is None
    assert first_resolved_link([L('closed', 'not_planned')]) is None
    assert first_resolved_link([L('closed', 'completed')]) is not None
    # erster geloester Link gewinnt
    links = [L('open'), L('closed', 'completed')]
    assert first_resolved_link(links).state == 'closed'


def test_completion_note_github_and_gitlab():
    from shared.issue_completion import completion_note, COMPLETION_MARKER

    class GH:
        issue_number = 42
        url = 'https://github.com/o/r/issues/42'

    class GL:
        issue_number = None
        url = 'https://gitlab.com/g/p/-/issues/7'

    gh_note = completion_note(GH(), 3)
    assert COMPLETION_MARKER in gh_note
    assert '#42' in gh_note
    assert 'vorheriger Score: 3' in gh_note

    gl_note = completion_note(GL(), 0)
    assert 'https://gitlab.com/g/p/-/issues/7' in gl_note


def test_is_assessed():
    from shared.issue_completion import is_assessed, COMPLETION_MARKER

    assert is_assessed(3, '') is True
    assert is_assessed(0, 'Manueller Kommentar') is True
    assert is_assessed(0, '') is False
    # Eine reine Auto-Notiz zaehlt NICHT als manuelle Bewertung.
    assert is_assessed(0, f'{COMPLETION_MARKER} #1 (vorheriger Score: 0)') is False


def test_already_completed_and_merge_idempotent():
    from shared.issue_completion import (
        already_completed, merge_completion_note, completion_note,
    )

    class GH:
        issue_number = 5
        url = 'https://github.com/o/r/issues/5'

    base = 'Mein Kommentar'
    note = completion_note(GH(), 2)
    once = merge_completion_note(base, note)
    assert already_completed(once)
    assert 'Mein Kommentar' in once

    note2 = completion_note(GH(), 5)
    twice = merge_completion_note(once, note2)
    assert twice.count('Vollständig bearbeitet') == 1
    assert 'Mein Kommentar' in twice


# -- Hilfen fuer End-to-End-Tests (echte Default-DB, API-Client) -------------

def _clear_links(db_path, proj):
    try:
        con = sqlite3.connect(str(db_path))
        con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (proj,))
        con.commit()
        con.close()
    except Exception:
        pass


def _add_closed_link(db_path, proj, req_id, number=11):
    add_link(
        db_path, projekt_name=proj, object_kind='requirement', object_id=req_id,
        provider='github', repo='o/r',
        url=f'https://github.com/o/r/issues/{number}',
        issue_number=number, title='T', state='closed', state_reason='completed',
    )


def _no_network(monkeypatch):
    """Sync-Endpunkt darf in diesen Tests keine echten API-Calls machen."""
    import shared.issue_sync as sync

    def _boom(**kw):  # pragma: no cover - sollte nie aufgerufen werden
        raise AssertionError('Kein Netzwerkaufruf erwartet')

    monkeypatch.setattr(sync, 'sync_github_issue', _boom)
    monkeypatch.setattr(sync, 'sync_gitlab_issue', _boom)


# -- CRA: end-to-end Szenarien -----------------------------------------------

class TestCraAutoComplete:
    BASE = '/api/cra'
    PROJ = 'pytest-autocomplete-cra-833'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.cra import DB_PATH
        from cra.requirements import CRA_ANFORDERUNGEN
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'unternehmen': 'U'})
        req_id = str(CRA_ANFORDERUNGEN[0]['id'])
        yield DB_PATH, req_id
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)

    def _load(self, req_id):
        from cra.db import load_bewertungen
        from server.api.cra import DB_PATH
        return load_bewertungen(DB_PATH, self.PROJ).get(req_id, {})

    def test_sync_completes_assessed_requirement(self, client, auth_headers, projekt, monkeypatch):
        db, req_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                    json={'anforderung_id': req_id, 'bewertung': 3, 'kommentar': 'Teilweise erfuellt'})
        _add_closed_link(db, self.PROJ, req_id, number=101)
        _no_network(monkeypatch)

        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/sync', headers=auth_headers)
        assert r.status_code == 200, r.get_json()
        assert r.get_json().get('auto_completed') == 1

        bw = self._load(req_id)
        assert bw['bewertung'] == 5
        assert '#101' in bw['kommentar']
        assert 'vorheriger Score: 3' in bw['kommentar']

    def test_deferred_until_first_bewertung(self, client, auth_headers, projekt, monkeypatch):
        db, req_id = projekt
        _add_closed_link(db, self.PROJ, req_id, number=202)
        _no_network(monkeypatch)

        # Noch nicht bewertet -> Sync darf nichts vervollstaendigen.
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/sync', headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json().get('auto_completed') == 0
        assert self._load(req_id).get('bewertung') in (None, 0)

        # Erste Bewertung speichern -> aufgeschobene Vervollstaendigung greift.
        r2 = client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                         json={'anforderung_id': req_id, 'bewertung': 2, 'kommentar': 'Start'})
        assert r2.status_code == 200, r2.get_json()
        assert r2.get_json().get('bewertung') == 5
        bw = self._load(req_id)
        assert bw['bewertung'] == 5
        assert '#202' in bw['kommentar']
        assert 'vorheriger Score: 2' in bw['kommentar']

    def test_idempotent_second_sync(self, client, auth_headers, projekt, monkeypatch):
        db, req_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                    json={'anforderung_id': req_id, 'bewertung': 4, 'kommentar': 'Fast fertig'})
        _add_closed_link(db, self.PROJ, req_id, number=303)
        _no_network(monkeypatch)

        r1 = client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/sync', headers=auth_headers)
        assert r1.get_json().get('auto_completed') == 1
        bw1 = self._load(req_id)

        r2 = client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/sync', headers=auth_headers)
        assert r2.get_json().get('auto_completed') == 0
        bw2 = self._load(req_id)
        assert bw2['kommentar'] == bw1['kommentar']
        assert bw2['kommentar'].count('Vollständig bearbeitet') == 1
        assert bw2['bewertung'] == 5

    def test_open_issue_does_not_complete(self, client, auth_headers, projekt, monkeypatch):
        db, req_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                    json={'anforderung_id': req_id, 'bewertung': 3, 'kommentar': 'In Arbeit'})
        add_link(db, projekt_name=self.PROJ, object_kind='requirement', object_id=req_id,
                 provider='github', repo='o/r', url='https://github.com/o/r/issues/9',
                 issue_number=9, title='T', state='open', state_reason='')
        _no_network(monkeypatch)

        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/sync', headers=auth_headers)
        assert r.get_json().get('auto_completed') == 0
        assert self._load(req_id)['bewertung'] == 3


# -- AI-Act: bestaetigt die zweite Modul-Abdeckung ---------------------------

class TestAIActAutoComplete:
    BASE = '/api/aiact'
    PROJ = 'pytest-autocomplete-aiact-833'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.aiact import DB_PATH
        from ai_act.requirements import AI_ACT_REQUIREMENTS
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'organisation': 'U'})
        req_id = str(AI_ACT_REQUIREMENTS[0]['id'])
        yield DB_PATH, req_id
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)

    def _load(self, req_id):
        from ai_act.db import load_bewertungen
        from server.api.aiact import DB_PATH
        return load_bewertungen(DB_PATH, self.PROJ).get(req_id, {})

    def test_sync_completes_assessed_requirement(self, client, auth_headers, projekt, monkeypatch):
        db, req_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                    json={'anforderung_id': req_id, 'bewertung': 3, 'kommentar': 'Teilweise erfuellt'})
        _add_closed_link(db, self.PROJ, req_id, number=404)
        _no_network(monkeypatch)

        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/sync', headers=auth_headers)
        assert r.status_code == 200, r.get_json()
        assert r.get_json().get('auto_completed') == 1

        bw = self._load(req_id)
        assert bw['bewertung'] == 5
        assert '#404' in bw['kommentar']

    def test_deferred_until_first_bewertung(self, client, auth_headers, projekt, monkeypatch):
        db, req_id = projekt
        _add_closed_link(db, self.PROJ, req_id, number=505)
        _no_network(monkeypatch)

        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/sync', headers=auth_headers)
        assert r.get_json().get('auto_completed') == 0

        r2 = client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                         json={'anforderung_id': req_id, 'bewertung': 1, 'kommentar': 'Start'})
        assert r2.status_code == 200, r2.get_json()
        assert r2.get_json().get('bewertung') == 5
        bw = self._load(req_id)
        assert bw['bewertung'] == 5
        assert '#505' in bw['kommentar']
