"""Tests für Sprint #23 DSFA-Rework (DS5 #1105 / DS6 #1106 / DS7 #1107).

Deckt ab:
- DS5 Schwellwertanalyse (Art. 35 Abs. 1/3/4): Kriterienkatalog + Auswertungslogik
  (Regelbeispiel Abs. 3 ⇒ erforderlich; ≥ 2 EDSA-9 ⇒ erforderlich; Negativliste Abs. 5
  schließt aus; Positivliste Abs. 4 löst aus) inkl. dokumentierter Begründung.
- DS6 mehrstufiger Prozess: Stage-Workflow + art36_required-Flag bei Restrisiko 'hoch'.
- DSGVO-DSFA framework_felder enthält Bedrohung/Eintritt×Schwere (+ Restrisiko-Feld),
  ohne FRAMEWORK_IDS-Anzahl zu verändern.
- API-Endpoints: schwellwert-kriterien, schwellwert-auswerten, dpia/<id>/schwellwert,
  dpia/<id>/stage; risk-link liefert stage/schwellwert/art36.

Kein Netz: rein lokale SQLite-Cross-Module-Verknüpfung.
"""
from __future__ import annotations

import pytest

from risikobewertung import frameworks as fw
from dsgvo import db as dsgvo_db
from dsgvo.db import (
    save_projekt, delete_projekt,
    save_dpia, get_dpia, list_dpia, delete_dpia,
    auswerten_schwellwert, schwellwert_kriterien, DSFA_STAGES,
)
from server.api.dsgvo import DB_PATH, _RB_DB_PATH
from risikobewertung.db import delete_projekt as rb_delete_projekt

PROJEKT = "ZZ-Test-DSFA-1106"


# ── Lizenz defensiv freischalten ────────────────────────────────────

@pytest.fixture(autouse=True)
def _license_ok(monkeypatch):
    fake = {"state": "ok", "modules": ["*"]}
    try:
        import server.license_state as m
        if hasattr(m, "get_state"):
            monkeypatch.setattr(m, "get_state", lambda: dict(fake), raising=False)
    except Exception:
        pass
    yield


# ════════════════════════════════════════════════════════════════════
# DS5 — Schwellwertanalyse (reine Logik)
# ════════════════════════════════════════════════════════════════════

def test_schwellwert_kriterien_katalog():
    kat = schwellwert_kriterien()
    assert len(kat['art35_3']) == 3        # Art. 35 Abs. 3 lit. a-c
    assert len(kat['edsa_9']) == 9         # EDSA/DSK-9-Kriterien
    ids = {c['id'] for c in kat['art35_3']}
    assert {'a_profiling', 'b_besondere_kategorien', 'c_systematische_ueberwachung'} <= ids


def test_schwellwert_regelbeispiel_abs3_erforderlich():
    r = auswerten_schwellwert({'art35_3': ['c_systematische_ueberwachung']})
    assert r['erforderlich'] is True
    assert r['ergebnis'] == 'erforderlich'
    assert 'Abs. 3' in r['begruendung_auto']


def test_schwellwert_ein_edsa_kriterium_nicht_erforderlich():
    r = auswerten_schwellwert({'edsa_9': ['k1_bewerten_scoring']})
    assert r['erforderlich'] is False
    assert r['anzahl_edsa_9'] == 1


def test_schwellwert_zwei_edsa_kriterien_erforderlich():
    r = auswerten_schwellwert({'edsa_9': ['k1_bewerten_scoring', 'k4_sensible_daten']})
    assert r['erforderlich'] is True
    assert r['anzahl_edsa_9'] == 2
    assert '≥ 2' in r['begruendung_auto']


def test_schwellwert_positivliste_abs4_erforderlich():
    r = auswerten_schwellwert({'muss_liste': True})
    assert r['erforderlich'] is True
    assert 'Positivliste' in r['begruendung_auto']


def test_schwellwert_negativliste_abs5_schliesst_aus():
    # Negativliste schließt aus, wenn kein zwingendes Regelbeispiel/Positivliste greift.
    r = auswerten_schwellwert({'edsa_9': ['k1_bewerten_scoring', 'k4_sensible_daten'],
                               'ausnahme_liste': True})
    assert r['erforderlich'] is False
    assert r['ausschluss_negativliste'] is True


def test_schwellwert_negativliste_uebersteuert_nicht_abs3():
    # Abs. 3 Regelbeispiel ist zwingend — Negativliste darf nicht ausschließen.
    r = auswerten_schwellwert({'art35_3': ['a_profiling'], 'ausnahme_liste': True})
    assert r['erforderlich'] is True
    assert r['ausschluss_negativliste'] is False


def test_schwellwert_keine_kriterien_nicht_erforderlich():
    r = auswerten_schwellwert({})
    assert r['erforderlich'] is False
    assert 'Keine Kriterien' in r['begruendung_auto']


def test_schwellwert_begruendung_freitext_erhalten():
    r = auswerten_schwellwert({'art35_3': ['a_profiling'], 'begruendung': 'Eigene Notiz'})
    assert r['begruendung'] == 'Eigene Notiz'


def test_schwellwert_ignoriert_unbekannte_ids():
    r = auswerten_schwellwert({'art35_3': ['quatsch'], 'edsa_9': ['nope']})
    assert r['anzahl_art35_3'] == 0
    assert r['anzahl_edsa_9'] == 0
    assert r['erforderlich'] is False


# ════════════════════════════════════════════════════════════════════
# DS6 — Stage-Workflow + Art.-36-Flag
# ════════════════════════════════════════════════════════════════════

def test_dsfa_stages_reihenfolge():
    assert DSFA_STAGES[0] == 'schwellwert'
    assert DSFA_STAGES[-1] == 'freigabe'
    for s in ('beschreibung', 'notwendigkeit', 'risiko', 'massnahmen', 'konsultation'):
        assert s in DSFA_STAGES


def _cleanup(name: str) -> None:
    try:
        for d in list_dpia(DB_PATH, name):
            rbname = (d.get('rb_projekt_id') or '').strip()
            if rbname:
                try:
                    rb_delete_projekt(_RB_DB_PATH, rbname)
                except Exception:
                    pass
            try:
                delete_dpia(DB_PATH, d['id'])
            except Exception:
                pass
    except Exception:
        pass
    try:
        delete_projekt(DB_PATH, name)
    except Exception:
        pass


@pytest.fixture
def projekt():
    _cleanup(PROJEKT)
    save_projekt(DB_PATH, name=PROJEKT, unternehmen="Test GmbH", berater="B")
    yield PROJEKT
    _cleanup(PROJEKT)


def test_art36_flag_bei_restrisiko_hoch(projekt):
    rid = save_dpia(DB_PATH, projekt, {
        'dpia_id': 'DSFA-H', 'titel': 'Hochrisiko', 'restrisiko': 'hoch',
    })
    row = get_dpia(DB_PATH, rid)
    assert int(row['art36_required']) == 1   # Restrisiko hoch ⇒ Art. 36 erforderlich


def test_art36_flag_nicht_bei_restrisiko_niedrig(projekt):
    rid = save_dpia(DB_PATH, projekt, {
        'dpia_id': 'DSFA-N', 'titel': 'Niedrig', 'restrisiko': 'niedrig',
    })
    assert int(get_dpia(DB_PATH, rid)['art36_required']) == 0


def test_art36_flag_explizit_setzbar(projekt):
    rid = save_dpia(DB_PATH, projekt, {
        'dpia_id': 'DSFA-E', 'titel': 'Explizit',
        'restrisiko': 'niedrig', 'art36_required': True,
    })
    assert int(get_dpia(DB_PATH, rid)['art36_required']) == 1


def test_dpia_stage_und_schwellwert_persistiert(projekt):
    rid = save_dpia(DB_PATH, projekt, {
        'dpia_id': 'DSFA-S', 'titel': 'Mit Schwellwert',
        'stage': 'beschreibung',
        'schwellwert_json': {'ergebnis': 'erforderlich', 'erforderlich': True},
    })
    row = get_dpia(DB_PATH, rid)
    assert row['stage'] == 'beschreibung'
    assert row['schwellwert']['ergebnis'] == 'erforderlich'


def test_dpia_default_stage(projekt):
    rid = save_dpia(DB_PATH, projekt, {'dpia_id': 'DSFA-D', 'titel': 'Default'})
    assert get_dpia(DB_PATH, rid)['stage'] == 'schwellwert'


# ════════════════════════════════════════════════════════════════════
# Framework: DSGVO-DSFA framework_felder — Anreicherung, Anzahl unverändert
# ════════════════════════════════════════════════════════════════════

def test_framework_felder_dsfa_enthaelt_bedrohung_eintritt_schwere():
    keys = {f['key'] for f in fw.framework_felder('DSGVO-DSFA')}
    assert 'bedrohung_rechte_freiheiten' in keys   # Bedrohung für Rechte/Freiheiten
    assert 'eintrittswahrscheinlichkeit' in keys   # Eintritt
    assert 'schwere' in keys                        # × Schwere
    assert 'massnahme' in keys                       # lit. d
    assert 'restrisiko' in keys                      # #1106 Anreicherung


def test_framework_ids_anzahl_unveraendert():
    # #938-Superset + Smoke-Count-Invariante: genau 8 Frameworks.
    assert len(fw.FRAMEWORK_IDS) == 8
    assert 'DSGVO-DSFA' in fw.FRAMEWORK_IDS


def test_framework_scoring_unveraendert():
    score, label, _ = fw.berechne_risiko('DSGVO-DSFA', {
        'eintrittswahrscheinlichkeit': 'Maximal', 'schwere': 'Maximal',
    })
    assert score == 16 and label == 'Sehr hoch'


# ════════════════════════════════════════════════════════════════════
# API-Endpoints
# ════════════════════════════════════════════════════════════════════

def test_api_schwellwert_kriterien(client, auth_headers):
    r = client.get('/api/dsgvo/dsfa/schwellwert-kriterien', headers=auth_headers)
    assert r.status_code == 200
    assert len(r.get_json()['edsa_9']) == 9


def test_api_schwellwert_auswerten(client, auth_headers):
    r = client.post('/api/dsgvo/dsfa/schwellwert-auswerten',
                    json={'art35_3': ['a_profiling']}, headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()['erforderlich'] is True


def test_api_dpia_schwellwert_persistiert_und_stage(client, auth_headers, projekt):
    rid = client.post(f'/api/dsgvo/projekte/{projekt}/dpia',
                      json={'dpia_id': 'DSFA-API', 'titel': 'API'},
                      headers=auth_headers).get_json()['id']
    r = client.post(f'/api/dsgvo/projekte/{projekt}/dpia/{rid}/schwellwert',
                    json={'art35_3': ['b_besondere_kategorien']}, headers=auth_headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body['schwellwert']['erforderlich'] is True
    assert body['stage'] == 'beschreibung'   # erforderlich ⇒ nächste Stufe

    row = get_dpia(DB_PATH, rid)
    assert row['schwellwert']['erforderlich'] is True


def test_api_dpia_stage_wechsel(client, auth_headers, projekt):
    rid = client.post(f'/api/dsgvo/projekte/{projekt}/dpia',
                      json={'dpia_id': 'DSFA-ST', 'titel': 'Stage'},
                      headers=auth_headers).get_json()['id']
    r = client.post(f'/api/dsgvo/projekte/{projekt}/dpia/{rid}/stage',
                    json={'stage': 'konsultation'}, headers=auth_headers)
    assert r.status_code == 200
    assert get_dpia(DB_PATH, rid)['stage'] == 'konsultation'

    r2 = client.post(f'/api/dsgvo/projekte/{projekt}/dpia/{rid}/stage',
                     json={'stage': 'quatsch'}, headers=auth_headers)
    assert r2.status_code == 400


def test_api_risk_link_liefert_stage_und_schwellwert(client, auth_headers, projekt):
    rid = client.post(f'/api/dsgvo/projekte/{projekt}/dpia',
                      json={'dpia_id': 'DSFA-RL', 'titel': 'RL', 'restrisiko': 'hoch'},
                      headers=auth_headers).get_json()['id']
    client.post(f'/api/dsgvo/projekte/{projekt}/dpia/{rid}/schwellwert',
                json={'art35_3': ['a_profiling']}, headers=auth_headers)
    r = client.get(f'/api/dsgvo/projekte/{projekt}/dpia/{rid}/risk-link',
                   headers=auth_headers)
    assert r.status_code == 200
    data = r.get_json()
    assert 'stage' in data and 'stages' in data
    assert data['schwellwert']['erforderlich'] is True
    assert int(data['art36_required']) == 1   # Restrisiko hoch
