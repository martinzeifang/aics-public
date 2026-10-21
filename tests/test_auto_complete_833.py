"""Tests für die Issue-Sync-Markierung „Neubewertung erforderlich" (#833/#1520/#1526).

KORRIGIERT (#1526): Ein geschlossenes verknüpftes Issue setzt die Anforderung NICHT
mehr automatisch auf Score 5 (nicht compliance-konform), sondern markiert sie als
**„Neubewertung erforderlich"** — der **Score bleibt unverändert**. Deckt die
gemeinsamen Helfer + CRA/AI-Act (object_kind='requirement') ab.
"""
import pytest

from shared.issue_links import add_link
from shared.issue_completion import NEEDS_REASSESS_MARKER


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


def test_reassessment_kommentar_close_marks_and_keeps_base():
    from shared.issue_completion import reassessment_kommentar

    class L:
        state = 'closed'
        state_reason = 'completed'
        issue_number = 42
        url = 'https://github.com/o/r/issues/42'

    out = reassessment_kommentar([L()], 'Meine Bewertung')
    assert out is not None
    assert 'Meine Bewertung' in out
    assert NEEDS_REASSESS_MARKER in out
    assert '#42' in out
    # idempotent: zweiter Lauf ändert nichts
    assert reassessment_kommentar([L()], out) is None


def test_reassessment_kommentar_open_issue_no_change():
    from shared.issue_completion import reassessment_kommentar

    class L:
        state = 'open'
        state_reason = ''
        issue_number = 7
        url = ''

    assert reassessment_kommentar([L()], 'Bewertung') is None


def test_reassessment_migrates_legacy_completion_on_reopen():
    """Alt-Datensatz mit Completion-Marker + kein gelöster Link (Reopen) → markieren."""
    from shared.issue_completion import reassessment_kommentar, COMPLETION_MARKER

    class L:
        state = 'open'
        state_reason = ''
        issue_number = 5
        url = 'https://github.com/o/r/issues/5'

    legacy = f'Basis-Kommentar\n\n{COMPLETION_MARKER} #5 (vorheriger Score: 3)'
    out = reassessment_kommentar([L()], legacy)
    assert out is not None
    assert COMPLETION_MARKER not in out          # Alt-Marker entfernt
    assert NEEDS_REASSESS_MARKER in out          # neu markiert
    assert 'Basis-Kommentar' in out


# -- End-to-End (echte Default-DB, API-Client) -------------------------------

def _clear_links(db_path, proj):
    from shared.issue_links import list_project_links, delete_link
    try:
        for li in list_project_links(db_path, projekt_name=proj):
            delete_link(db_path, li.id)
    except Exception:
        pass


def _add_closed_link(db_path, proj, req_id, number=11):
    add_link(db_path, projekt_name=proj, object_kind='requirement', object_id=req_id,
             provider='github', repo='o/r',
             url=f'https://github.com/o/r/issues/{number}',
             issue_number=number, title='T', state='closed', state_reason='completed')


def _no_network(monkeypatch):
    import shared.issue_sync as sync

    def _boom(**kw):  # pragma: no cover
        raise AssertionError('Kein Netzwerkaufruf erwartet')

    monkeypatch.setattr(sync, 'sync_github_issue', _boom)
    monkeypatch.setattr(sync, 'sync_gitlab_issue', _boom)


class TestCraRequirementReassessment:
    BASE = '/api/cra'
    PROJ = 'pytest-reassess-cra-1526'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.cra import DB_PATH
        from cra.requirements import CRA_ANFORDERUNGEN
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'unternehmen': 'U'})
        yield DB_PATH, str(CRA_ANFORDERUNGEN[0]['id'])
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)

    def _load(self, req_id):
        from cra.db import load_bewertungen
        from server.api.cra import DB_PATH
        return load_bewertungen(DB_PATH, self.PROJ).get(req_id, {})

    def test_sync_marks_reassessment_score_unchanged(self, client, auth_headers, projekt, monkeypatch):
        db, req_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                    json={'anforderung_id': req_id, 'bewertung': 3, 'kommentar': 'Teilweise'})
        _add_closed_link(db, self.PROJ, req_id, number=101)
        _no_network(monkeypatch)

        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/sync', headers=auth_headers)
        assert r.status_code == 200, r.get_json()
        assert r.get_json().get('auto_completed') == 1   # 1 Anforderung markiert
        bw = self._load(req_id)
        assert int(bw['bewertung']) == 3                 # SCORE UNVERÄNDERT (#1526)
        assert NEEDS_REASSESS_MARKER in bw['kommentar']
        assert '#101' in bw['kommentar']

    def test_save_does_not_auto_change_score(self, client, auth_headers, projekt, monkeypatch):
        db, req_id = projekt
        _add_closed_link(db, self.PROJ, req_id, number=202)
        _no_network(monkeypatch)
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                        json={'anforderung_id': req_id, 'bewertung': 2, 'kommentar': 'Start'})
        assert r.status_code == 200
        assert r.get_json().get('bewertung') == 2        # NICHT 5
        assert NEEDS_REASSESS_MARKER not in self._load(req_id).get('kommentar', '')

    def test_open_issue_not_marked(self, client, auth_headers, projekt, monkeypatch):
        db, req_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                    json={'anforderung_id': req_id, 'bewertung': 3, 'kommentar': 'In Arbeit'})
        add_link(db, projekt_name=self.PROJ, object_kind='requirement', object_id=req_id,
                 provider='github', repo='o/r', url='https://github.com/o/r/issues/9',
                 issue_number=9, title='T', state='open', state_reason='')
        _no_network(monkeypatch)
        client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/sync', headers=auth_headers)
        bw = self._load(req_id)
        assert int(bw['bewertung']) == 3
        assert NEEDS_REASSESS_MARKER not in bw.get('kommentar', '')


class TestAIActRequirementReassessment:
    BASE = '/api/aiact'
    PROJ = 'pytest-reassess-aiact-1526'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.aiact import DB_PATH
        from ai_act.requirements import AI_ACT_REQUIREMENTS
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'organisation': 'U'})
        yield DB_PATH, str(AI_ACT_REQUIREMENTS[0]['id'])
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)

    def _load(self, req_id):
        from ai_act.db import load_bewertungen
        from server.api.aiact import DB_PATH
        return load_bewertungen(DB_PATH, self.PROJ).get(req_id, {})

    def test_sync_marks_reassessment_score_unchanged(self, client, auth_headers, projekt, monkeypatch):
        db, req_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/bewertungen', headers=auth_headers,
                    json={'anforderung_id': req_id, 'bewertung': 3, 'kommentar': 'Teilweise'})
        _add_closed_link(db, self.PROJ, req_id, number=404)
        _no_network(monkeypatch)
        r = client.post(f'{self.BASE}/projekte/{self.PROJ}/issues/sync', headers=auth_headers)
        assert r.status_code == 200, r.get_json()
        bw = self._load(req_id)
        assert int(bw['bewertung']) == 3
        assert NEEDS_REASSESS_MARKER in bw['kommentar']
