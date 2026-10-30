"""#1508/#1520/#1526 — OWASP-Issue-Sync markiert „Neubewertung erforderlich".

KORRIGIERT (#1526): Beim Schließen eines verknüpften Issues wird die Kontrolle NICHT
mehr automatisch auf „erfüllt" gesetzt (das wäre nicht compliance-konform), sondern
als **„Neubewertung erforderlich"** markiert — **Score/Antwort bleiben unverändert**.
Deckt CRA (`owasp`), AI-Act (`owasp_llm`) und WiBA (`wiba_control`) ab.

Issue-Status wird über persistierte ``linked_issues``-Zeilen simuliert; Netzwerk wird
per Monkeypatch unterbunden.
"""
import pytest

from shared.issue_links import add_link
# #1850: Der Marker nennt jetzt den ANLASS (Issue geschlossen, N neue
# Kommentare) statt pauschal 'verknuepftes Issue geaendert'. Geprueft wird
# deshalb der stabile Praefix - den liest auch die Oberflaeche
# (RequirementActions.vue filtert auf den Teilstring).
from shared.issue_abgleich import MARKER as REASSESS_PRAEFIX


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _clear_links(db_path, proj):
    from shared.issue_links import list_project_links, delete_link
    try:
        for li in list_project_links(db_path, projekt_name=proj):
            delete_link(db_path, li.id)
    except Exception:
        pass


def _add_closed_link(db_path, proj, kind, object_id, number=11):
    add_link(db_path, projekt_name=proj, object_kind=kind, object_id=object_id,
             provider='github', repo='o/r',
             url=f'https://github.com/o/r/issues/{number}',
             issue_number=number, title='T', state='closed', state_reason='completed')


def _no_network(monkeypatch):
    import shared.issue_sync as sync

    def _boom(**kw):  # pragma: no cover
        raise AssertionError('Kein Netzwerkaufruf erwartet')

    monkeypatch.setattr(sync, 'sync_github_issue', _boom)
    monkeypatch.setattr(sync, 'sync_gitlab_issue', _boom)


# ── CRA OWASP (object_kind='owasp') ─────────────────────────────────────────

class TestCraOwaspReassessment:
    BASE = '/api/cra'
    PROJ = 'pytest-owasp-cra-1526'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.cra import DB_PATH
        from cra.owasp_proactive_controls import OWASP_PC_V3
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'unternehmen': 'U'})
        yield DB_PATH, str(OWASP_PC_V3[0]['id'])
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)

    def _load(self, owasp_id):
        from cra.db import load_owasp_checks
        from server.api.cra import DB_PATH
        return load_owasp_checks(DB_PATH, self.PROJ).get(owasp_id, {})

    def _save(self, client, auth_headers, owasp_id, status, kommentar=''):
        return client.put(f'{self.BASE}/projekte/{self.PROJ}/owasp/{owasp_id}',
                          headers=auth_headers, json={'status': status, 'kommentar': kommentar})

    def _sync(self, client, auth_headers, owasp_id):
        return client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp/{owasp_id}/issues/sync',
                           headers=auth_headers)

    def test_close_marks_reassessment_score_unchanged(self, client, auth_headers, projekt, monkeypatch):
        db, owasp_id = projekt
        self._save(client, auth_headers, owasp_id, 3, 'Teilweise erfüllt')
        _add_closed_link(db, self.PROJ, 'owasp', owasp_id, number=101)
        _no_network(monkeypatch)

        r = self._sync(client, auth_headers, owasp_id)
        assert r.status_code == 200, r.get_json()
        chk = self._load(owasp_id)
        assert int(chk['status']) == 3                       # SCORE UNVERÄNDERT (#1526)
        assert REASSESS_PRAEFIX in chk['kommentar']     # markiert
        assert '#101' in chk['kommentar']

    def test_save_does_not_auto_change_score(self, client, auth_headers, projekt, monkeypatch):
        db, owasp_id = projekt
        _add_closed_link(db, self.PROJ, 'owasp', owasp_id, number=202)
        _no_network(monkeypatch)
        # Speichern bei bereits geschlossenem Issue ändert den Score NICHT automatisch.
        r = self._save(client, auth_headers, owasp_id, 2, 'Start')
        assert r.status_code == 200
        chk = self._load(owasp_id)
        assert int(chk['status']) == 2
        assert REASSESS_PRAEFIX not in chk.get('kommentar', '')

    def test_unassessed_not_marked(self, client, auth_headers, projekt, monkeypatch):
        db, owasp_id = projekt
        _add_closed_link(db, self.PROJ, 'owasp', owasp_id, number=303)
        _no_network(monkeypatch)
        self._sync(client, auth_headers, owasp_id)
        chk = self._load(owasp_id)
        assert int(chk.get('status') or 0) == 0
        assert REASSESS_PRAEFIX not in chk.get('kommentar', '')

    def test_idempotent_second_sync(self, client, auth_headers, projekt, monkeypatch):
        db, owasp_id = projekt
        self._save(client, auth_headers, owasp_id, 4, 'Fast fertig')
        _add_closed_link(db, self.PROJ, 'owasp', owasp_id, number=404)
        _no_network(monkeypatch)
        self._sync(client, auth_headers, owasp_id)
        k1 = self._load(owasp_id)['kommentar']
        self._sync(client, auth_headers, owasp_id)
        k2 = self._load(owasp_id)['kommentar']
        assert k1 == k2
        assert k2.count(REASSESS_PRAEFIX) == 1
        assert int(self._load(owasp_id)['status']) == 4

    def test_open_issue_not_marked(self, client, auth_headers, projekt, monkeypatch):
        db, owasp_id = projekt
        self._save(client, auth_headers, owasp_id, 3, 'In Arbeit')
        add_link(db, projekt_name=self.PROJ, object_kind='owasp', object_id=owasp_id,
                 provider='github', repo='o/r', url='https://github.com/o/r/issues/9',
                 issue_number=9, title='T', state='open', state_reason='')
        _no_network(monkeypatch)
        self._sync(client, auth_headers, owasp_id)
        chk = self._load(owasp_id)
        assert REASSESS_PRAEFIX not in chk.get('kommentar', '')
        assert int(chk['status']) == 3


# ── AI-Act OWASP-LLM (object_kind='owasp_llm') ──────────────────────────────

class TestAIActOwaspLlmReassessment:
    BASE = '/api/aiact'
    PROJ = 'pytest-owasp-aiact-1526'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.aiact import DB_PATH
        from ai_act.owasp_llm_register import register_items
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'organisation': 'U'})
        yield DB_PATH, str(register_items()[0]['id'])
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)

    def _load(self, llm_id):
        from ai_act.db import load_owasp_llm_checks
        from server.api.aiact import DB_PATH
        return load_owasp_llm_checks(DB_PATH, self.PROJ).get(llm_id, {})

    def test_close_marks_reassessment_score_unchanged(self, client, auth_headers, projekt, monkeypatch):
        db, llm_id = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp-llm/{llm_id}',
                    headers=auth_headers, json={'status': 3, 'kommentar': 'Teilweise'})
        _add_closed_link(db, self.PROJ, 'owasp_llm', llm_id, number=505)
        _no_network(monkeypatch)
        client.post(f'{self.BASE}/projekte/{self.PROJ}/owasp-llm/{llm_id}/issues/sync',
                    headers=auth_headers)
        chk = self._load(llm_id)
        assert int(chk['status']) == 3
        assert REASSESS_PRAEFIX in chk['kommentar']


# ── WiBA (object_kind='wiba_control') ───────────────────────────────────────

class TestWibaControlReassessment:
    BASE = '/api/wiba'
    PROJ = 'pytest-owasp-wiba-1526'
    CID = 'orga-1'

    @pytest.fixture
    def projekt(self, client, auth_headers):
        from server.api.wiba import DB_PATH
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)
        client.post(f'{self.BASE}/projekte', headers=auth_headers,
                    json={'name': self.PROJ, 'unternehmen': 'U'})
        yield DB_PATH
        client.delete(f'{self.BASE}/projekte/{self.PROJ}', headers=auth_headers)
        _clear_links(DB_PATH, self.PROJ)

    def _load(self):
        from wiba.db import load_antworten
        from server.api.wiba import DB_PATH
        return load_antworten(DB_PATH, self.PROJ).get(self.CID, {})

    def test_close_marks_reassessment_answer_unchanged(self, client, auth_headers, projekt, monkeypatch):
        db = projekt
        client.post(f'{self.BASE}/projekte/{self.PROJ}/antworten', headers=auth_headers,
                    json={'control_id': self.CID, 'status': 'nein', 'notiz': 'Lücke'})
        _add_closed_link(db, self.PROJ, 'wiba_control', self.CID, number=701)
        _no_network(monkeypatch)
        client.post(f'{self.BASE}/projekte/{self.PROJ}/controls/{self.CID}/issues/sync',
                    headers=auth_headers)
        a = self._load()
        assert a['status'] == 'nein'                     # ANTWORT UNVERÄNDERT (#1526)
        assert REASSESS_PRAEFIX in a['notiz']
