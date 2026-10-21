"""#1575 — DSGVO-TOM ↔ BSI-WiBA: Mapping, Status-Ableitung, Automatik, Formulierung."""
from pathlib import Path

import pytest

from dsgvo import tom_wiba as tw

DP = 'pytest-1575-dsgvo'
WP = 'pytest-1575-wiba'
FIRMA = 'Acme 1575 GmbH'
DSGVO_DB = Path('data/db/dsgvo.sqlite')


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ── Unit ────────────────────────────────────────────────────────────────────

def test_status_from_answers():
    assert tw.status_from_answers(['ja', 'ja', 'nein', 'nicht_relevant']) == 3   # 2/3 → 3,33
    assert tw.status_from_answers(['ja'] * 4) == 5
    assert tw.status_from_answers(['ja', 'nein']) == 3                             # 2,5 → 3 (kaufmännisch)
    assert tw.status_from_answers(['offen', 'nein']) == 0
    assert tw.status_from_answers(['nicht_relevant']) is None                     # nichts im Scope
    assert tw.status_from_answers([]) is None


def test_mapping_keys_exist_in_seed_and_ids_wellformed():
    from dsgvo.tom_katalog import SEED_KATALOG
    seed_keys = {e['massnahme_key'] for e in SEED_KATALOG}
    assert set(tw.TOM_WIBA_MAPPING) <= seed_keys
    for ids in tw.TOM_WIBA_MAPPING.values():
        for cid in ids:
            theme, _, nr = cid.rpartition('-')
            assert theme and nr.isdigit(), cid
    assert {'IN-04', 'VT-04', 'TR-04', 'TR-05'} <= seed_keys          # WiBA-Zusatz-TOM


def test_effektive_quelle():
    assert tw.effektive_quelle({'massnahme_key': 'VF-01', 'status': 0}) == 'wiba'
    assert tw.effektive_quelle({'massnahme_key': 'VF-01', 'status': 3}) == 'manuell'   # Bestand bewertet
    assert tw.effektive_quelle({'massnahme_key': 'IV-01', 'status': 0}) == 'manuell'   # ohne WiBA-Bezug
    assert tw.effektive_quelle({'massnahme_key': 'VF-01', 'status': 3, 'status_quelle': 'wiba'}) == 'wiba'


def test_entwurf_und_prompt():
    m = {'massnahme_key': 'VF-01', 'titel': 'Backup- und Restore-Konzept', 'ziel': 'Verfügbarkeit'}
    fragen = [{'frage': 'Backups getestet?', 'status': 'ja', 'notiz': 'quartalsweise'},
              {'frage': 'Backup-Medium festgelegt?', 'status': 'nein', 'notiz': ''},
              {'frage': 'X?', 'status': 'offen', 'notiz': ''}]
    e = tw.entwurf_umsetzung(m, fragen, 'W')
    assert 'Backups getestet? (Ja) — quartalsweise' in e
    assert 'Handlungsbedarf' in e and 'Backup-Medium festgelegt?' in e
    assert 'Noch nicht geprüft: 1' in e
    p = tw.build_formulierung_prompt(m, fragen, 'Acme')
    assert '[Ja] Backups getestet?' in p and '"umsetzung"' in p


# ── Integration ─────────────────────────────────────────────────────────────

@pytest.fixture
def setup():
    from server.api.wiba import DB_PATH as WDB
    from wiba import db as wdb
    from dsgvo.db import save_projekt, delete_projekt
    from dsgvo import tom_katalog as tk
    wdb.ensure_db(WDB)
    wdb.replace_catalog(
        WDB,
        themen=[{'theme_key': 'backup', 'titel': 'Backup', 'bausteine': 'CON.3', 'ziel': 'Z', 'reihenfolge': 1}],
        prueffragen=[{'control_id': f'backup-{i}', 'theme_key': 'backup', 'nr': i,
                      'frage': f'Backup-Frage {i}?', 'hilfsmittel': '', 'aufwand': '1'} for i in range(1, 8)],
        version='test', quelle='pytest')
    wdb.save_projekt(WDB, name=WP, unternehmen=FIRMA)
    save_projekt(DSGVO_DB, DP, unternehmen=FIRMA)
    tk.seed_projekt(DSGVO_DB, DP)
    yield WDB
    for fn in (lambda: wdb.delete_projekt(WDB, WP), lambda: delete_projekt(DSGVO_DB, DP)):
        try:
            fn()
        except Exception:
            pass
    try:
        from dsgvo.db import _connect
        con = _connect(DSGVO_DB)
        con.execute('DELETE FROM dsgvo_tom_katalog WHERE projekt_name=?', (DP,))
        con.commit(); con.close()
    except Exception:
        pass


def _answer(client, h, cid, status):
    r = client.post(f'/api/wiba/projekte/{WP}/antworten', headers=h,
                    json={'control_id': cid, 'status': status, 'notiz': f'N-{cid}'})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_wiba_antwort_zieht_tom_status_automatisch(client, auth_headers, setup):
    from dsgvo import tom_katalog as tk
    res = _answer(client, auth_headers, 'backup-1', 'ja')               # 1/7 → Status 1
    assert any(x['projekt'] == DP for x in res['tom_sync'])
    for i in range(2, 6):
        _answer(client, auth_headers, f'backup-{i}', 'ja')
    _answer(client, auth_headers, 'backup-6', 'nein')
    _answer(client, auth_headers, 'backup-7', 'nicht_relevant')
    vf = tk.get_massnahme(DSGVO_DB, DP, 'VF-01')
    assert vf['status'] == 4 and vf['status_quelle'] == 'wiba'          # 5 von 6 im Scope → 4,17

    r = client.get(f'/api/dsgvo-tom/projekte/{DP}/wiba', headers=auth_headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['wiba_projekt'] == WP and body['explizit'] is False
    it = body['items']['VF-01']
    assert it['counts']['ja'] == 5 and it['counts']['nein'] == 1 and it['in_scope'] == 6
    assert it['status_abgeleitet'] == 4


def test_manuelle_tom_wird_nicht_ueberschrieben(client, auth_headers, setup):
    from dsgvo import tom_katalog as tk
    m = tk.get_massnahme(DSGVO_DB, DP, 'VF-01')
    r = client.post(f'/api/dsgvo-tom/projekte/{DP}/massnahmen', headers=auth_headers,
                    json={**m, 'status': 2})
    assert r.status_code in (200, 201), r.get_json()
    assert tk.get_massnahme(DSGVO_DB, DP, 'VF-01')['status_quelle'] == 'manuell'
    for i in range(1, 8):
        _answer(client, auth_headers, f'backup-{i}', 'ja')
    assert tk.get_massnahme(DSGVO_DB, DP, 'VF-01')['status'] == 2          # manuell bleibt
    # Zurück auf WiBA → sofort abgeleitet
    r = client.put(f'/api/dsgvo-tom/projekte/{DP}/massnahmen/VF-01/status-quelle',
                   headers=auth_headers, json={'quelle': 'wiba'})
    assert r.status_code == 200 and r.get_json()['status'] == 5


def test_sync_endpoint_und_explizite_verknuepfung(client, auth_headers, setup):
    r = client.post(f'/api/dsgvo-tom/projekte/{DP}/wiba/sync', headers=auth_headers, json={})
    assert r.status_code == 200 and r.get_json()['wiba_projekt'] == WP
    r = client.put(f'/api/dsgvo-tom/projekte/{DP}/wiba-link', headers=auth_headers,
                   json={'wiba_projekt': WP})
    assert r.status_code == 200
    assert client.get(f'/api/dsgvo-tom/projekte/{DP}/wiba', headers=auth_headers).get_json()['explizit'] is True


def test_formulierung_und_umsetzung(client, auth_headers, setup, monkeypatch):
    _answer(client, auth_headers, 'backup-1', 'ja')
    r = client.get(f'/api/dsgvo-tom/projekte/{DP}/massnahmen/VF-01/formulierung', headers=auth_headers)
    assert r.status_code == 200
    d = r.get_json()
    assert 'Backup-Frage 1? (Ja) — N-backup-1' in d['entwurf'] and 'Backup-Frage 1?' in d['prompt']
    import ai_compliance_suite.ai.dispatch as dispatch
    monkeypatch.setattr(dispatch, 'current_provider_name', lambda: 'cloud')
    raw = '```json\n{"umsetzung": "Tägliche Sicherung mit Restore-Test.", "luecken": ["Medium festlegen"]}\n```'
    r = client.post(f'/api/dsgvo-tom/projekte/{DP}/massnahmen/VF-01/umsetzung',
                    headers=auth_headers, json={'raw': raw})
    assert r.status_code == 200, r.get_json()
    m = r.get_json()
    assert 'Tägliche Sicherung' in m['umsetzung'] and 'Medium festlegen' in m['umsetzung']
    assert 'KI-generiert' in m['umsetzung'] and m['umsetzung_quelle'] == 'ki'


def test_wiba_tom_mapping_endpoint(client, auth_headers):
    r = client.get('/api/wiba/tom-mapping', headers=auth_headers)
    assert r.status_code == 200
    d = r.get_json()
    assert any(k['key'] == 'VF-01' for k in d['controls']['backup-1'])
    assert any(t['key'] == 'TR-04' for t in d['toms'])
