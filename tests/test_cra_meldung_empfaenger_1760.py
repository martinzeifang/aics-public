"""Tests #1760: Empfänger der Art.-14-Meldung, Nutzerunterrichtung, Fristbeginn.

Drei Behauptungen, die die Meldeakte vorher nicht halten konnte:

1. Eine Stufe gilt nur als gemeldet, wenn Adressat (CSIRT-Koordinator des
   Mitgliedstaats + ENISA) und Einreichungsreferenz belegt sind — serverseitig
   erzwungen, nicht nur im Formular.
2. Die Nutzerunterrichtung (Art. 14 Abs. 8) ist erst mit URL, Datum und
   Empfängerkreis veröffentlicht; ein Freitext-Kanal belegt nichts.
3. Die Abschlussfrist läuft ab Verfügbarkeit der Korrekturmaßnahme bzw. ab
   Einreichung der 72-Stunden-Meldung — nicht ab Erkennung. Fehlt der Anker,
   ist die Frist unbestimmt und die Ampel zeigt nicht rot.
"""
from datetime import datetime, timezone

import pytest

CRA = '/api/cra'
MELD = '/api/cra-meldung'
FIRMA = 'pytest-firma-1760'
PROJ = 'pytest-cra-1760'

VOLL = {'csirt': {'mitgliedstaat': 'DE', 'stelle': 'CERT-Bund', 'referenz': 'CB-2026-1'},
        'enisa': {'referenz': 'SRP-2026-1'}}


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


# ── Teil 3: Fristbeginn der Abschlussstufe ────────────────────────────────────

def test_abschlussfrist_unbestimmt_ohne_massnahme():
    """Ohne Korrekturmaßnahme läuft die 14-Tage-Frist nicht — also nicht rot."""
    import cra.deadlines as dl
    now = datetime(2026, 9, 30, 0, 0, tzinfo=timezone.utc)
    res = dl.art14_fristen('2026-09-01T00:00:00', 'cra_art14', now=now)
    final = res['stages'][-1]
    assert final['ampel'] == 'unbestimmt'
    assert final['due_at'] is None and final['overdue'] is False
    assert 'nicht erfasst' in final['hinweis']
    assert res['abschlussfrist']['bestimmt'] is False
    assert res['abschlussfrist']['anker_feld'] == 'massnahme_verfuegbar_ab'
    # Alte Rechnung ab Erkennung wäre hier längst überfällig gewesen.
    alt = dl.evaluate('2026-09-01T00:00:00', 'cra_art14', now=now)
    assert alt['stages'][-1]['overdue'] is True


def test_abschlussfrist_14_tage_ab_massnahme():
    import cra.deadlines as dl
    now = datetime(2026, 9, 30, 0, 0, tzinfo=timezone.utc)
    res = dl.art14_fristen('2026-09-01T00:00:00', 'cra_art14',
                           massnahme_verfuegbar_ab='2026-09-28T06:00:00', now=now)
    final = res['stages'][-1]
    assert final['due_at'].startswith('2026-10-12T06:00')   # 14 Tage ab Maßnahme
    assert final['overdue'] is False
    assert res['abschlussfrist']['bestimmt'] is True


def test_abschlussfrist_ein_monat_ab_72h_meldung():
    """Vorfall: 1 Kalendermonat ab Einreichung der 72-h-Meldung (nicht 30·24 h)."""
    import cra.deadlines as dl
    now = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    res = dl.art14_fristen('2026-01-15T08:00:00', 'cra_art14_incident',
                           notification_gemeldet_am='2026-01-31T09:30:00', now=now)
    final = res['stages'][-1]
    assert final['due_at'].startswith('2026-02-28T09:30')   # Monatsende-sicher
    # Ohne Meldung wäre die Frist unbestimmt.
    ohne = dl.art14_fristen('2026-01-15T08:00:00', 'cra_art14_incident', now=now)
    assert ohne['stages'][-1]['ampel'] == 'unbestimmt'


def test_gemeldete_stufe_ist_nicht_mehr_ueberfaellig():
    import cra.deadlines as dl
    now = datetime(2026, 9, 10, 0, 0, tzinfo=timezone.utc)
    res = dl.art14_fristen(
        '2026-09-01T00:00:00', 'cra_art14', now=now,
        erfuellt={'early_warning': '2026-09-01T10:00:00',
                  'notification': '2026-09-08T00:00:00'})
    ampeln = {s['key']: s['ampel'] for s in res['stages']}
    assert ampeln['early_warning'] == 'erfuellt'            # pünktlich
    assert ampeln['notification'] == 'erfuellt_verspaetet'  # nach 72h
    assert res['any_overdue'] is False


def test_evaluate_default_unveraendert():
    """Bestandsaufrufer (cra/db, Gate) dürfen sich nicht verändert sehen."""
    import cra.deadlines as dl
    now = datetime(2026, 9, 2, 1, 0, tzinfo=timezone.utc)
    res = dl.evaluate('2026-09-01T00:00:00', 'cra_art14', now=now)
    assert [s['key'] for s in res['stages']] == \
        ['early_warning', 'notification', 'final_report']
    assert res['stages'][-1]['offset_hours'] == 14 * 24
    assert res['stages'][0]['overdue'] is True   # 24h-Frist nach 25h


# ── Teil 1: Empfänger je Stufe (DB-Ebene) ─────────────────────────────────────

def test_stufe_ohne_empfaenger_wird_abgelehnt(tmp_path):
    from cra import meldung_db as mdb
    db = tmp_path / 'cra.sqlite'
    mid = mdb.create_meldung(db, PROJ, {'typ': 'vuln_exploited', 'titel': 'X'})
    with pytest.raises(mdb.AngabenUnvollstaendig) as ex:
        mdb.set_stufe(db, mid, PROJ, 'early_warning_24h')
    assert len(ex.value.fehlende) == 3   # Mitgliedstaat + 2 Referenzen
    # Nichts geschrieben: Status und Zeitstempel unverändert.
    m = mdb.get_meldung(db, mid, PROJ)
    assert m['status'] == 'erkannt' and not m['early_warning_gemeldet_am']


def test_stufe_mit_empfaenger_setzt_referenzen_und_gleichzeitigkeit(tmp_path):
    from cra import meldung_db as mdb
    db = tmp_path / 'cra.sqlite'
    mid = mdb.create_meldung(db, PROJ, {'typ': 'vuln_exploited', 'titel': 'X'})
    m = mdb.set_stufe(db, mid, PROJ, 'early_warning_24h', VOLL)
    ew = m['empfaenger']['early_warning']
    assert ew['csirt']['mitgliedstaat'] == 'DE'
    assert ew['csirt']['referenz'] == 'CB-2026-1'
    assert ew['enisa']['referenz'] == 'SRP-2026-1'
    # Ohne eigene Angabe gilt der Stufenzeitpunkt für beide Kanäle — das ist
    # der Beleg der von Art. 14 verlangten Gleichzeitigkeit.
    assert ew['csirt']['gemeldet_am'] == ew['enisa']['gemeldet_am']
    assert ew['csirt']['gemeldet_am']


def test_unbekannter_mitgliedstaat_abgelehnt(tmp_path):
    from cra import meldung_db as mdb
    db = tmp_path / 'cra.sqlite'
    mid = mdb.create_meldung(db, PROJ, {'titel': 'X'})
    with pytest.raises(mdb.AngabenUnvollstaendig):
        mdb.set_stufe(db, mid, PROJ, 'early_warning_24h', {
            'csirt': {'mitgliedstaat': 'CH', 'referenz': 'X'},
            'enisa': {'referenz': 'Y'}})


def test_empfaenger_vorab_lueckenhaft_gemeldet_streng(tmp_path):
    from cra import meldung_db as mdb
    db = tmp_path / 'cra.sqlite'
    mid = mdb.create_meldung(db, PROJ, {'titel': 'X'})
    # Vorab-Erfassung darf lückenhaft sein (noch nichts behauptet).
    m = mdb.set_empfaenger(db, mid, PROJ, 'notification',
                           {'csirt': {'mitgliedstaat': 'FR'}})
    assert m['empfaenger']['notification']['csirt']['mitgliedstaat'] == 'FR'
    # Nach der Meldung darf der Adressat nicht wieder verschwinden.
    mdb.set_stufe(db, mid, PROJ, 'notification_72h', VOLL)
    with pytest.raises(mdb.AngabenUnvollstaendig):
        mdb.set_empfaenger(db, mid, PROJ, 'notification',
                           {'enisa': {'referenz': ''}})
    # Eingangsbestätigung nachtragen bleibt möglich.
    m = mdb.set_empfaenger(db, mid, PROJ, 'notification',
                           {'enisa': {'eingang_bestaetigt_am': '2026-09-02T10:00:00'}})
    assert m['empfaenger']['notification']['enisa']['eingang_bestaetigt_am']
    assert m['empfaenger']['notification']['enisa']['referenz'] == 'SRP-2026-1'


# ── Teil 2: Nutzerunterrichtung ───────────────────────────────────────────────

def test_advisory_veroeffentlicht_braucht_url_datum_kreis(tmp_path):
    from cra import meldung_db as mdb
    db = tmp_path / 'cra.sqlite'
    mid = mdb.create_meldung(db, PROJ, {'titel': 'X'})
    # Entwurf: lückenhaft erlaubt.
    m = mdb.set_advisory(db, mid, PROJ, {'veroeffentlichungskanal': 'Website'})
    assert m['advisory']['veroeffentlichungskanal'] == 'Website'
    # Behauptete Veröffentlichung: Pflichtfelder.
    with pytest.raises(mdb.AngabenUnvollstaendig) as ex:
        mdb.set_advisory(db, mid, PROJ, {'veroeffentlichungskanal': 'Website',
                                         'veroeffentlicht': True})
    assert any('URL' in f for f in ex.value.fehlende)
    # URL ohne Schema ist keine URL.
    with pytest.raises(mdb.AngabenUnvollstaendig):
        mdb.set_advisory(db, mid, PROJ, {
            'veroeffentlichungskanal': 'Website', 'url': 'www.example.org',
            'veroeffentlicht_am': '2026-09-02', 'empfaengerkreis': 'alle Kunden',
            'veroeffentlicht': True})
    m = mdb.set_advisory(db, mid, PROJ, {
        'veroeffentlichungskanal': 'Website', 'url': 'https://example.org/adv/1',
        'veroeffentlicht_am': '2026-09-02T12:00:00',
        'empfaengerkreis': 'alle Kunden mit Wartungsvertrag',
        'veroeffentlicht': True})
    assert m['advisory']['veroeffentlicht'] is True


# ── Nachweis-Lücken + SRP-Payload ─────────────────────────────────────────────

def test_nachweis_luecken_zeigen_fehlendes(tmp_path):
    from cra import meldung_db as mdb
    db = tmp_path / 'cra.sqlite'
    mid = mdb.create_meldung(db, PROJ, {'titel': 'X'})
    m = mdb.get_meldung(db, mid, PROJ)
    status = mdb.nachweis_status(m)
    # Noch nichts gemeldet → keine Pflichtlücke, aber Fristbeginn offen.
    assert status['pflicht_offen'] == 0
    assert any(l['bereich'] == 'final_report' for l in status['luecken'])

    m = mdb.set_stufe(db, mid, PROJ, 'early_warning_24h', VOLL)
    status = mdb.nachweis_status(m)
    assert status['belegt'] is True          # Adressat + Referenzen vorhanden
    assert status['vollstaendig'] is False   # Eingangsbestätigungen fehlen
    assert any('Eingangsbestätigung ENISA' in l['text'] for l in status['luecken'])


def test_nachweis_meldet_abweichende_zeitpunkte(tmp_path):
    from cra import meldung_db as mdb
    db = tmp_path / 'cra.sqlite'
    mid = mdb.create_meldung(db, PROJ, {'titel': 'X'})
    mdb.set_stufe(db, mid, PROJ, 'early_warning_24h', VOLL)
    m = mdb.set_empfaenger(db, mid, PROJ, 'early_warning', {
        'csirt': {'gemeldet_am': '2026-09-01T08:00:00'},
        'enisa': {'gemeldet_am': '2026-09-03T08:00:00'}})
    texte = [l['text'] for l in mdb.nachweis_luecken(m)]
    assert any('gleichzeitige' in t for t in texte)


def test_srp_payload_nennt_adressaten(tmp_path):
    from cra import meldung_db as mdb
    db = tmp_path / 'cra.sqlite'
    mid = mdb.create_meldung(db, PROJ, {'titel': 'X'})
    m = mdb.set_stufe(db, mid, PROJ, 'early_warning_24h', VOLL)
    payload = mdb.build_srp_payload(m)
    ew = payload['recipients']['early_warning']
    assert ew['csirt_coordinator']['member_state'] == 'DE'
    assert ew['csirt_coordinator']['member_state_name'] == 'Deutschland'
    assert ew['csirt_coordinator']['submission_reference'] == 'CB-2026-1'
    assert ew['enisa']['submission_reference'] == 'SRP-2026-1'
    assert 'CSIRT-Koordinator Deutschland' in payload['stage_texts']['early_warning']
    assert payload['user_notification']['published'] is False
    assert isinstance(payload['evidence_gaps'], list)


# ── API ───────────────────────────────────────────────────────────────────────

def test_api_stufe_ohne_empfaenger_400_mit_feldliste(client, auth_headers, projekt):
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen', headers=auth_headers,
                    json={'typ': 'vuln_exploited', 'titel': 'CVE-1760'})
    mid = r.json['id']
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen/{mid}/stufe',
                    headers=auth_headers, json={'status': 'early_warning_24h'})
    assert r.status_code == 400
    assert len(r.json['fehlende_felder']) == 3

    r = client.post(f'{MELD}/projekte/{projekt}/meldungen/{mid}/stufe',
                    headers=auth_headers,
                    json={'status': 'early_warning_24h', 'empfaenger': VOLL})
    assert r.status_code == 200, r.json
    assert r.json['empfaenger']['early_warning']['enisa']['referenz'] == 'SRP-2026-1'
    assert r.json['nachweis']['belegt'] is True
    # Abschlussfrist noch unbestimmt → keine rote Ampel.
    final = r.json['deadlines']['stages'][-1]
    assert final['ampel'] == 'unbestimmt'


def test_api_empfaenger_und_nachweis(client, auth_headers, projekt):
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen', headers=auth_headers,
                    json={'typ': 'vuln_exploited', 'titel': 'CVE-1760-b'})
    mid = r.json['id']
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen/{mid}/empfaenger',
                    headers=auth_headers,
                    json={'stufe': 'early_warning', **VOLL})
    assert r.status_code == 200, r.json
    # Stufe ohne eigenen Empfänger-Body: die vorab erfassten Angaben genügen.
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen/{mid}/stufe',
                    headers=auth_headers, json={'status': 'early_warning_24h'})
    assert r.status_code == 200, r.json

    r = client.post(f'{MELD}/projekte/{projekt}/meldungen/{mid}/empfaenger',
                    headers=auth_headers, json={'stufe': 'quatsch', **VOLL})
    assert r.status_code == 400

    r = client.get(f'{MELD}/projekte/{projekt}/meldungen/{mid}/nachweis',
                   headers=auth_headers)
    assert r.status_code == 200
    assert r.json['belegt'] is True
    assert r.json['abschlussfrist']['anker_feld'] == 'massnahme_verfuegbar_ab'


def test_api_massnahme_setzt_fristbeginn(client, auth_headers, projekt):
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen', headers=auth_headers,
                    json={'typ': 'vuln_exploited', 'titel': 'CVE-1760-c',
                          'erkannt_am': '2026-09-01T00:00:00'})
    mid = r.json['id']
    assert r.json['deadlines']['stages'][-1]['due_at'] is None
    r = client.put(f'{MELD}/projekte/{projekt}/meldungen/{mid}', headers=auth_headers,
                   json={'massnahme_verfuegbar_ab': '2026-09-20T06:00'})
    assert r.status_code == 200, r.json
    final = r.json['deadlines']['stages'][-1]
    assert final['due_at'].startswith('2026-10-04T06:00')
    assert r.json['deadlines']['abschlussfrist']['bestimmt'] is True


def test_api_advisory_400_und_csaf_entwurf(client, auth_headers, projekt):
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen', headers=auth_headers,
                    json={'typ': 'vuln_exploited', 'titel': 'CVE-1760-d'})
    mid = r.json['id']
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen/{mid}/nutzer-advisory',
                    headers=auth_headers,
                    json={'veroeffentlichungskanal': 'Website', 'veroeffentlicht': True})
    assert r.status_code == 400 and r.json['fehlende_felder']

    r = client.get(f'{MELD}/projekte/{projekt}/meldungen/{mid}/nutzer-advisory/csaf',
                   headers=auth_headers)
    assert r.json['document']['tracking']['status'] == 'draft'

    r = client.post(f'{MELD}/projekte/{projekt}/meldungen/{mid}/nutzer-advisory',
                    headers=auth_headers,
                    json={'veroeffentlichungskanal': 'Website',
                          'url': 'https://example.org/a/1',
                          'veroeffentlicht_am': '2026-09-02T12:00',
                          'empfaengerkreis': 'alle Kunden', 'veroeffentlicht': True})
    assert r.status_code == 200, r.json
    r = client.get(f'{MELD}/projekte/{projekt}/meldungen/{mid}/nutzer-advisory/csaf',
                   headers=auth_headers)
    assert r.json['document']['tracking']['status'] == 'final'
    assert r.json['publication_url'] == 'https://example.org/a/1'
    assert r.json['audience'] == 'alle Kunden'


def test_api_constants_liefern_pflichtfelder(client, auth_headers):
    r = client.get(f'{MELD}/constants', headers=auth_headers)
    assert r.status_code == 200
    assert r.json['mitgliedstaaten']['DE'] == 'Deutschland'
    assert 'CH' not in r.json['mitgliedstaaten']
    assert r.json['stufen'] == ['early_warning', 'notification', 'final_report']
    assert 'referenz' in r.json['empfaenger_pflichtfelder']['enisa']
    assert r.json['abschlussfrist_anker']['cra_art14']['feld'] == 'massnahme_verfuegbar_ab'


def test_api_export_enthaelt_adressaten(client, auth_headers, projekt):
    r = client.post(f'{MELD}/projekte/{projekt}/meldungen', headers=auth_headers,
                    json={'typ': 'serious_incident', 'titel': 'Vorfall 1760'})
    mid = r.json['id']
    client.post(f'{MELD}/projekte/{projekt}/meldungen/{mid}/stufe',
                headers=auth_headers,
                json={'status': 'early_warning_24h', 'empfaenger': VOLL})
    r = client.get(f'{MELD}/projekte/{projekt}/meldungen/{mid}/export?format=json',
                   headers=auth_headers)
    assert r.status_code == 200
    assert r.json['recipients']['early_warning']['enisa']['submission_reference'] \
        == 'SRP-2026-1'
    assert r.json['deadlines']['abschlussfrist']['anker_feld'] == 'notification_gemeldet_am'


def test_nicht_gemeldete_akte_gilt_nicht_als_belegt():
    """Eine Akte ohne abgegebene Stufe hat keine Lücke — und sah deshalb aus
    wie vollständig belegt.

    Gefunden beim Ansehen der Firefox-Aufnahmen: In der Liste stand „✓ belegt"
    bei einer Meldung, in der nichts gemeldet worden war. Formal richtig (es
    gibt nichts zu belegen), praktisch gefährlich — es liest sich wie
    „Meldepflicht erfüllt". ``gemeldet`` trennt die beiden Lagen.
    """
    from cra.meldung_db import nachweis_status

    frisch = {"typ": "vuln_exploited", "titel": "noch nichts gemeldet"}
    st = nachweis_status(frisch)
    assert st["gemeldet"] is False
    # „belegt" darf hier nicht allein entscheiden, was die Liste anzeigt —
    # genau darauf stützte sich die Anzeige und schrieb „✓ belegt".
    assert st["pflicht_offen"] == 0

    gemeldet = dict(frisch, early_warning_gemeldet_am="2026-10-22 16:12:00")
    assert nachweis_status(gemeldet)["gemeldet"] is True
