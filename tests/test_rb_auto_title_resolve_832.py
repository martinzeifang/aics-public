# #1850: Der Marker nennt jetzt den ANLASS (Issue geschlossen, N neue
# Kommentare) statt pauschal 'verknuepftes Issue geaendert'. Geprueft wird
# deshalb der stabile Praefix - den liest auch die Oberflaeche
# (RequirementActions.vue filtert auf den Teilstring).
from shared.issue_abgleich import MARKER as REASSESS_PRAEFIX
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
    from shared import db as _sdb  # #1530: PG statt sqlite3
    from risikobewertung.db import _connect, save_risiko, load_risiken

    # Risiko anlegen, dann Titel nachträglich generisch zurücksetzen
    # (umgeht den Create-Auto-Titel) und Migration laufen lassen.
    rid = save_risiko(tmp_db_path, {
        'projekt_name': 'P', 'risk_name': 'Echter Titel',
        'beschreibung': 'Backfill Satz eins. Satz zwei.', 'felder': {},
    })
    con = _sdb.connect(str(tmp_db_path))
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


def _abgleich(db_path, projekt, risk_id):
    """Abgleich + Markierung über den **gemeinsamen** Weg (#1846/#1850).

    Bis v8.1.1 stand diese Logik als `_mark_risk_resolved_if_issue_done` in
    `server/api/risikobewertung`, dreimal ähnlich auch in CRA, NIS2 und
    AI Act. Sie liegt jetzt in `shared/issue_abgleich`; die Module liefern
    nur noch, wo ihr Freitext steht.

    Ohne Netz schlägt der Abruf fehl — der Abgleich fällt dann auf den
    **gespeicherten** Stand zurück (ein unerreichbares GitHub darf nicht
    verbergen, dass das Issue zu ist). Genau diesen Pfad prüfen die Tests
    hier, wie vorher.
    """
    from risikobewertung.db import hat_erstbewertung, load_risiken, save_risiko
    from shared import issue_abgleich as ia

    risk = next((r for r in load_risiken(db_path, projekt)
                 if str(r.get('id')) == str(risk_id)), {})

    def _schreib(text):
        neu = dict(risk)
        neu['projekt_name'] = projekt
        neu['bewertung_text'] = text
        save_risiko(db_path, neu)

    erg = ia.abgleiche_und_markiere(
        db_path, projekt_name=projekt, object_kind='risk',
        object_id=str(risk_id),
        lies_text=lambda: str(risk.get('bewertung_text') or ''),
        schreib_text=_schreib,
        bewertet=hat_erstbewertung(risk))
    # „Markiert?" = Anlass vorhanden UND erstbewertet.
    return bool(erg.neubewertung_noetig and hat_erstbewertung(risk))


def test_marker_verlangt_erstbewertung(tmp_db_path):
    from risikobewertung.db import load_risiken, save_risiko
    # Risiko OHNE Bewertung (felder leer, kein bewertung_text).
    rid = save_risiko(tmp_db_path, {
        'projekt_name': 'P', 'risk_name': 'Ungeprüft',
        'beschreibung': 'x', 'felder': {},
    })
    _seed_resolved_link(tmp_db_path, 'P', rid)
    assert _abgleich(tmp_db_path, 'P', rid) is False
    risk = load_risiken(tmp_db_path, 'P')[0]
    assert not risk['is_resolved']
    assert REASSESS_PRAEFIX not in (risk.get('bewertung_text') or '')

    # Mit Erstbewertung (felder befüllt) wird markiert …
    save_risiko(tmp_db_path, {
        'id': rid, 'projekt_name': 'P', 'risk_name': 'Ungeprüft',
        'beschreibung': 'x', 'felder': {'wert': 3},
    })
    assert _abgleich(tmp_db_path, 'P', rid) is True
    risk = load_risiken(tmp_db_path, 'P')[0]
    # … aber NICHT automatisch gelöst (#1526).
    assert not risk['is_resolved']
    assert REASSESS_PRAEFIX in (risk.get('bewertung_text') or '')


def test_marker_nennt_das_issue_und_bleibt_einmalig(tmp_db_path):
    from risikobewertung.db import load_risiken, save_risiko
    rid = save_risiko(tmp_db_path, {
        'projekt_name': 'P', 'risk_name': 'Geprüft',
        'beschreibung': 'x', 'felder': {'wert': 4},
    })
    _seed_resolved_link(tmp_db_path, 'P', rid, number=123)
    assert _abgleich(tmp_db_path, 'P', rid) is True
    text = load_risiken(tmp_db_path, 'P')[0].get('bewertung_text') or ''
    assert REASSESS_PRAEFIX in text
    assert '#123' in text, ("Der Marker muss sagen, WELCHES Ticket gemeint "
                            "ist — bei mehreren Verknüpfungen ist das die "
                            "halbe Auskunft.")
    # Zweiter Abgleich: kein zweiter Marker.
    _abgleich(tmp_db_path, 'P', rid)
    assert (load_risiken(tmp_db_path, 'P')[0].get('bewertung_text') or ''
            ).count(REASSESS_PRAEFIX) == 1


def test_offenes_issue_wird_nicht_markiert(tmp_db_path):
    from risikobewertung.db import load_risiken, save_risiko
    from shared.issue_links import add_link
    rid = save_risiko(tmp_db_path, {
        'projekt_name': 'P', 'risk_name': 'Geprüft',
        'beschreibung': 'x', 'felder': {'wert': 4},
    })
    add_link(tmp_db_path, projekt_name='P', object_kind='risk', object_id=str(rid),
             provider='github', repo='owner/repo',
             url='https://github.com/owner/repo/issues/5',
             issue_number=5, state='open')
    assert _abgleich(tmp_db_path, 'P', rid) is False
    risk = load_risiken(tmp_db_path, 'P')[0]
    assert not risk['is_resolved']
    assert REASSESS_PRAEFIX not in (risk.get('bewertung_text') or '')


def test_gitlab_wird_genauso_markiert(tmp_db_path):
    """GitLab-Links übersprangen fünf von sieben Abgleich-Wegen stillschweigend."""
    from risikobewertung.db import load_risiken, save_risiko
    from shared.issue_links import add_link
    rid = save_risiko(tmp_db_path, {
        'projekt_name': 'P', 'risk_name': 'Geprüft',
        'beschreibung': 'x', 'felder': {'wert': 4},
    })
    add_link(tmp_db_path, projekt_name='P', object_kind='risk', object_id=str(rid),
             provider='gitlab', repo='group/proj',
             url='https://gitlab.com/group/proj/-/issues/7',
             issue_iid=7, state='closed')
    assert _abgleich(tmp_db_path, 'P', rid) is True
    text = load_risiken(tmp_db_path, 'P')[0].get('bewertung_text') or ''
    assert REASSESS_PRAEFIX in text and '#7' in text


