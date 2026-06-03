"""Tests für #832:

Feature 1 — Risiko-Titel aus dem ersten Satz der Beschreibung ableiten, wenn
            kein manueller Titel vergeben wurde (inkl. Backfill-Migration).
Feature 2 — Risiko automatisch als gelöst markieren, wenn ein verknüpftes Issue
            erledigt ist — aber NUR, wenn bereits eine Initial-Bewertung vorliegt;
            sonst beim Speichern der Initial-Bewertung.

Alle Netz-Aufrufe (GitHub/GitLab) werden gemockt — kein echter Traffic.
"""

import uuid
from pathlib import Path

import pytest

BASE = '/api/risikobewertung'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def tmp_db_path():
    """Temp-SQLite INNERHALB des Repos (connect_sqlite erlaubt nur Workspace-
    Pfade, vgl. tests/test_issue_sync_788.py)."""
    d = Path('data/db'); d.mkdir(parents=True, exist_ok=True)
    p = d / f'_test832_{uuid.uuid4().hex}.sqlite'
    yield p
    for suf in ('', '-wal', '-shm'):
        Path(str(p) + suf).unlink(missing_ok=True)


# ============================================================
# Feature 1a — first_sentence_title (Unit)
# ============================================================

class TestFirstSentenceTitle:
    def test_empty(self):
        from risikobewertung.db import first_sentence_title
        assert first_sentence_title('') == ''
        assert first_sentence_title('   ') == ''
        assert first_sentence_title(None) == ''  # type: ignore[arg-type]

    def test_first_sentence_period(self):
        from risikobewertung.db import first_sentence_title
        assert first_sentence_title('Dies ist Satz eins. Und das ist zwei.') == 'Dies ist Satz eins'

    def test_question_and_exclamation(self):
        from risikobewertung.db import first_sentence_title
        assert first_sentence_title('Was passiert hier? Egal.') == 'Was passiert hier'
        assert first_sentence_title('Achtung! Mehr Text.') == 'Achtung'

    def test_newline_terminates(self):
        from risikobewertung.db import first_sentence_title
        assert first_sentence_title('Erste Zeile\nzweite Zeile') == 'Erste Zeile'

    def test_no_terminator_uses_full_text(self):
        from risikobewertung.db import first_sentence_title
        assert first_sentence_title('Ein Satz ohne Ende') == 'Ein Satz ohne Ende'

    def test_collapse_whitespace(self):
        from risikobewertung.db import first_sentence_title
        assert first_sentence_title('  viel    Abstand   hier.  ') == 'viel Abstand hier'

    def test_decimal_not_split(self):
        # '3.5' -> der Punkt ist NICHT von Whitespace gefolgt, also kein Satzende.
        from risikobewertung.db import first_sentence_title
        assert first_sentence_title('Version 3.5 ist betroffen. Ende.') == 'Version 3.5 ist betroffen'

    def test_truncation_on_word_boundary(self):
        from risikobewertung.db import first_sentence_title
        wort = 'wort'
        text = ' '.join([wort] * 100)  # weit über 200 Zeichen, kein Satzende
        out = first_sentence_title(text, max_len=20)
        assert out.endswith('…')
        assert len(out) <= 21
        # An Wortgrenze geschnitten: der Teil vor … besteht nur aus ganzen
        # 'wort'-Tokens, kein Wort wird mittendrin abgeschnitten.
        kern = out[:-1]
        assert all(tok == wort for tok in kern.split())

    def test_max_len_default(self):
        from risikobewertung.db import first_sentence_title
        out = first_sentence_title('x' * 500)
        assert len(out) <= 201 and out.endswith('…')


def test_is_generic_title():
    from risikobewertung.db import is_generic_title
    assert is_generic_title('')
    assert is_generic_title('   ')
    assert is_generic_title('Risiko 1')
    assert is_generic_title('Risiko 42')
    assert not is_generic_title('Risiko 1 mit Namen')
    assert not is_generic_title('Echtes Risiko')


# ============================================================
# Feature 1b — Create-Pfad: Titel aus erstem Satz
# ============================================================

def test_create_risk_without_title_derives_from_first_sentence(client, auth_headers):
    proj = f'pytest-832-create-{uuid.uuid4().hex[:8]}'
    try:
        client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': proj, 'framework': 'STRIDE'})
        r = client.post(f'{BASE}/projekte/{proj}/risiken', headers=auth_headers,
                        json={'risk_name': '', 'framework': 'STRIDE',
                              'beschreibung': 'SQL-Injection im Login-Formular. Weitere Details folgen.',
                              'felder': {}})
        assert r.status_code in (200, 201), r.get_json()
        assert r.get_json()['risk_name'] == 'SQL-Injection im Login-Formular'
    finally:
        client.delete(f'{BASE}/projekte/{proj}', headers=auth_headers)


def test_create_risk_keeps_manual_title(client, auth_headers):
    proj = f'pytest-832-manual-{uuid.uuid4().hex[:8]}'
    try:
        client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': proj, 'framework': 'STRIDE'})
        r = client.post(f'{BASE}/projekte/{proj}/risiken', headers=auth_headers,
                        json={'risk_name': 'Mein Titel', 'framework': 'STRIDE',
                              'beschreibung': 'Egal welche Beschreibung. Zweiter Satz.',
                              'felder': {}})
        assert r.get_json()['risk_name'] == 'Mein Titel'
    finally:
        client.delete(f'{BASE}/projekte/{proj}', headers=auth_headers)


# ============================================================
# Feature 1c — Backfill-Migration
# ============================================================

def test_backfill_updates_generic_title(tmp_db_path):
    import sqlite3
    from risikobewertung.db import _connect, save_risiko, load_risiken

    # Risiko anlegen, dann Titel nachträglich generisch zurücksetzen
    # (umgeht den Create-Auto-Titel) und Migration laufen lassen.
    rid = save_risiko(tmp_db_path, {
        'projekt_name': 'P', 'risk_name': 'Echter Titel',
        'beschreibung': 'Backfill Satz eins. Satz zwei.', 'felder': {},
    })
    con = sqlite3.connect(str(tmp_db_path))
    con.execute("UPDATE rb_risiken SET risk_name='Risiko 1' WHERE id=?", (rid,))
    con.commit()
    con.close()

    # _connect() ruft die idempotente Migration auf.
    _connect(tmp_db_path).close()

    risks = load_risiken(tmp_db_path, 'P')
    assert risks[0]['risk_name'] == 'Backfill Satz eins'

    # Idempotent: erneuter Lauf ändert den (nun nicht-generischen) Titel nicht.
    _connect(tmp_db_path).close()
    assert load_risiken(tmp_db_path, 'P')[0]['risk_name'] == 'Backfill Satz eins'


def test_backfill_skips_manual_title(tmp_db_path):
    from risikobewertung.db import _connect, save_risiko, load_risiken
    save_risiko(tmp_db_path, {
        'projekt_name': 'P', 'risk_name': 'Manuell gesetzt',
        'beschreibung': 'Eine Beschreibung. Zweiter Satz.', 'felder': {},
    })
    _connect(tmp_db_path).close()
    assert load_risiken(tmp_db_path, 'P')[0]['risk_name'] == 'Manuell gesetzt'


# ============================================================
# Feature 2 — Auto-Resolve
# ============================================================

def _seed_resolved_link(db_path, projekt, risk_id, number=99):
    """Verknüpftes, bereits geschlossenes GitHub-Issue in linked_issues legen."""
    from shared.issue_links import add_link
    add_link(db_path, projekt_name=projekt, object_kind='risk', object_id=str(risk_id),
             provider='github', repo='owner/repo',
             url=f'https://github.com/owner/repo/issues/{number}',
             issue_number=number, state='closed', state_reason='completed')


def test_auto_resolve_requires_initial_assessment(tmp_db_path):
    from server.api import risikobewertung as rb
    from risikobewertung.db import save_risiko, load_risiken
    rb_db = rb.DB_PATH
    rb.DB_PATH = tmp_db_path
    try:
        # Risiko OHNE Bewertung (felder leer, kein bewertung_text).
        rid = save_risiko(tmp_db_path, {
            'projekt_name': 'P', 'risk_name': 'Ungeprüft',
            'beschreibung': 'x', 'felder': {},
        })
        _seed_resolved_link(tmp_db_path, 'P', rid)
        # Kein Initial-Assessment -> kein Auto-Resolve.
        assert rb._mark_risk_resolved_if_issue_done('P', rid) is False
        assert not load_risiken(tmp_db_path, 'P')[0]['is_resolved']

        # Jetzt Initial-Assessment speichern (felder befüllt) ...
        save_risiko(tmp_db_path, {
            'id': rid, 'projekt_name': 'P', 'risk_name': 'Ungeprüft',
            'beschreibung': 'x', 'felder': {'wert': 3},
        })
        # ... und erneut prüfen -> jetzt auto-resolved.
        assert rb._mark_risk_resolved_if_issue_done('P', rid) is True
        risk = load_risiken(tmp_db_path, 'P')[0]
        assert risk['is_resolved']
        assert risk['resolved_reason'] == 'Gelöst durch #99'
    finally:
        rb.DB_PATH = rb_db


def test_auto_resolve_marks_resolved_with_assessment(tmp_db_path):
    from server.api import risikobewertung as rb
    from risikobewertung.db import save_risiko, load_risiken
    rb_db = rb.DB_PATH
    rb.DB_PATH = tmp_db_path
    try:
        rid = save_risiko(tmp_db_path, {
            'projekt_name': 'P', 'risk_name': 'Geprüft',
            'beschreibung': 'x', 'felder': {'wert': 4},
        })
        _seed_resolved_link(tmp_db_path, 'P', rid, number=123)
        assert rb._mark_risk_resolved_if_issue_done('P', rid) is True
        risk = load_risiken(tmp_db_path, 'P')[0]
        assert risk['is_resolved']
        assert risk['resolved_reason'] == 'Gelöst durch #123'
        # Idempotent: zweiter Aufruf markiert nicht erneut.
        assert rb._mark_risk_resolved_if_issue_done('P', rid) is False
    finally:
        rb.DB_PATH = rb_db


def test_no_auto_resolve_when_issue_open(tmp_db_path):
    from server.api import risikobewertung as rb
    from risikobewertung.db import save_risiko, load_risiken
    from shared.issue_links import add_link
    rb_db = rb.DB_PATH
    rb.DB_PATH = tmp_db_path
    try:
        rid = save_risiko(tmp_db_path, {
            'projekt_name': 'P', 'risk_name': 'Geprüft',
            'beschreibung': 'x', 'felder': {'wert': 4},
        })
        add_link(tmp_db_path, projekt_name='P', object_kind='risk', object_id=str(rid),
                 provider='github', repo='owner/repo',
                 url='https://github.com/owner/repo/issues/5',
                 issue_number=5, state='open')
        assert rb._mark_risk_resolved_if_issue_done('P', rid) is False
        assert not load_risiken(tmp_db_path, 'P')[0]['is_resolved']
    finally:
        rb.DB_PATH = rb_db


def test_resolved_reason_gitlab_uses_url(tmp_db_path):
    from server.api import risikobewertung as rb
    from risikobewertung.db import save_risiko, load_risiken
    from shared.issue_links import add_link
    rb_db = rb.DB_PATH
    rb.DB_PATH = tmp_db_path
    try:
        rid = save_risiko(tmp_db_path, {
            'projekt_name': 'P', 'risk_name': 'Geprüft',
            'beschreibung': 'x', 'felder': {'wert': 4},
        })
        url = 'https://gitlab.com/group/proj/-/issues/7'
        add_link(tmp_db_path, projekt_name='P', object_kind='risk', object_id=str(rid),
                 provider='gitlab', repo='group/proj', url=url,
                 issue_iid=7, state='closed')
        assert rb._mark_risk_resolved_if_issue_done('P', rid) is True
        assert load_risiken(tmp_db_path, 'P')[0]['resolved_reason'] == f'Gelöst durch {url}'
    finally:
        rb.DB_PATH = rb_db
