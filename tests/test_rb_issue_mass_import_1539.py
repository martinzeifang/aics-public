"""#1539 — Risikobewertung: Issue-Inhalte aller Risiken in die Bemerkungen
übernehmen (Massenimport, CRA-Parität #830).

- Schreibt nur ``bewertung_text`` (score-neutral, #1526).
- Idempotent: erneuter Import ersetzt den Feedback-Block.
- Berücksichtigt auch Links aus verknüpften CRA-Projekten (#1008).
- ``risk_ids`` beschränkt die Auswahl.
"""
import pytest

BASE = '/api/risikobewertung'
PROJ = 'pytest-rb-import-1539'
CRA_PROJ = 'pytest-rb-import-1539-cra'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture(autouse=True)
def _fake_fetch(monkeypatch):
    """Issue-Inhalt ohne Netz: URL-abhängiger Text."""
    import shared.issue_feedback as fb
    calls = []

    def _fake(url, gitlab_token_env='GITLAB_TOKEN'):
        calls.append(url)
        return {'combined': f'INHALT<{url}>'}
    monkeypatch.setattr(fb, 'fetch_issue_content_by_url', _fake)
    return calls


def _clear_links(db, projekt):
    from shared import db as _sdb
    from shared.issue_links import ensure_tables
    ensure_tables(db)
    with _sdb.connect(db) as con:
        con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (projekt,))


def _link(db, projekt, rid, url):
    from shared.issue_links import add_link
    add_link(db, projekt_name=projekt, object_kind='risk', object_id=str(rid),
             provider='github', repo='o/r', url=url)


@pytest.fixture
def risiken(client, auth_headers):
    from server.api.risikobewertung import DB_PATH
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(DB_PATH, PROJ)
    client.post(f'{BASE}/projekte', headers=auth_headers,
                json={'name': PROJ, 'framework': 'STRIDE'})
    ids = []
    for i in range(3):
        r = client.post(f'{BASE}/projekte/{PROJ}/risiken', headers=auth_headers,
                        json={'risk_name': f'Risiko {i}', 'framework': 'STRIDE',
                              'beschreibung': f'B{i}', 'felder': {}})
        assert r.status_code in (200, 201), r.get_json()
        ids.append(r.get_json()['id'])
    yield ids
    client.delete(f'{BASE}/projekte/{PROJ}', headers=auth_headers)
    _clear_links(DB_PATH, PROJ)


def _risk(rid):
    from risikobewertung.db import load_risiken
    from server.api.risikobewertung import DB_PATH
    return next(r for r in load_risiken(DB_PATH, PROJ) if r['id'] == rid)


def _set_bemerkung(rid, text):
    from risikobewertung.db import save_risiko
    from server.api.risikobewertung import DB_PATH
    r = dict(_risk(rid))
    r['projekt_name'] = PROJ
    r['bewertung_text'] = text
    save_risiko(DB_PATH, r)


def test_import_all_score_neutral_and_idempotent(client, auth_headers, risiken):
    from server.api.risikobewertung import DB_PATH
    a, b, c = risiken
    _set_bemerkung(a, 'Ursprüngliche Bemerkung')
    before = _risk(a)
    _link(DB_PATH, PROJ, a, 'https://github.com/o/r/issues/1')
    _link(DB_PATH, PROJ, a, 'https://github.com/o/r/issues/2')
    _link(DB_PATH, PROJ, b, 'https://github.com/o/r/issues/3')

    r = client.post(f'{BASE}/projekte/{PROJ}/issues/import', headers=auth_headers, json={})
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert (d['imported'], d['failed'], d['total']) == (2, 0, 2)

    ra = _risk(a)
    assert 'Ursprüngliche Bemerkung' in ra['bewertung_text']
    assert 'INHALT<https://github.com/o/r/issues/1>' in ra['bewertung_text']
    assert 'INHALT<https://github.com/o/r/issues/2>' in ra['bewertung_text']
    assert ra['risikowert'] == before['risikowert']          # score-neutral (#1526)
    assert ra['risiko_label'] == before['risiko_label']
    assert 'INHALT<https://github.com/o/r/issues/3>' in _risk(b)['bewertung_text']
    assert not (_risk(c).get('bewertung_text') or '')        # ohne Link unberührt

    # Zweiter Lauf ersetzt den Block statt ihn zu verdoppeln.
    client.post(f'{BASE}/projekte/{PROJ}/issues/import', headers=auth_headers, json={})
    assert _risk(a)['bewertung_text'].count('INHALT<https://github.com/o/r/issues/1>') == 1


def test_risk_ids_filter(client, auth_headers, risiken):
    from server.api.risikobewertung import DB_PATH
    a, b, _ = risiken
    _link(DB_PATH, PROJ, a, 'https://github.com/o/r/issues/11')
    _link(DB_PATH, PROJ, b, 'https://github.com/o/r/issues/12')
    r = client.post(f'{BASE}/projekte/{PROJ}/issues/import', headers=auth_headers,
                    json={'risk_ids': [b]})
    assert r.get_json()['imported'] == 1
    assert 'INHALT' not in (_risk(a).get('bewertung_text') or '')
    assert 'issues/12' in _risk(b)['bewertung_text']


def test_includes_links_from_linked_cra_projekt(client, auth_headers, risiken):
    from server.api.risikobewertung import _CRA_DB_PATH
    from cra.db import update_projekt_meta
    a = risiken[0]
    client.delete(f'/api/cra/projekte/{CRA_PROJ}', headers=auth_headers)
    _clear_links(_CRA_DB_PATH, CRA_PROJ)
    client.post('/api/cra/projekte', headers=auth_headers,
                json={'name': CRA_PROJ, 'unternehmen': 'U'})
    try:
        update_projekt_meta(_CRA_DB_PATH, CRA_PROJ, {'linked_risk_projekt': PROJ})
        _link(_CRA_DB_PATH, CRA_PROJ, a, 'https://github.com/o/r/issues/21')
        r = client.post(f'{BASE}/projekte/{PROJ}/issues/import', headers=auth_headers, json={})
        assert r.get_json()['imported'] == 1
        assert 'issues/21' in _risk(a)['bewertung_text']
    finally:
        client.delete(f'/api/cra/projekte/{CRA_PROJ}', headers=auth_headers)
        _clear_links(_CRA_DB_PATH, CRA_PROJ)


def test_unknown_projekt_404(client, auth_headers):
    r = client.post(f'{BASE}/projekte/gibt-es-nicht-1539/issues/import',
                    headers=auth_headers, json={})
    assert r.status_code == 404
