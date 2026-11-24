"""Quer-Sicht Releases je Mandant — CRA as a Service (#1749).

Die Release-Prüfung aus #1742 hängt am CRA-Projekt, also am Produkt. Wer CRA
für mehrere Mandanten betreibt, braucht die Gegenrichtung: welcher Kunde hat
ein Release in Prüfung, welches ist rot, wo wartet eine Freigabe.

Vier Dinge hält diese Datei fest:

1. Die Zahlen stammen aus den Modul-Funktionen (``list_konformitaet``,
   ``konformitaet_gate.evaluate``, eingefrorenes ``gate_json``) — ein eigener
   Rechenweg würde irgendwann abweichen (die Lehre aus #1726).
2. Ein Mandant ohne CRA-Projekt bekommt den Abschnitt nicht.
3. Die Liste respektiert ``allowed_firmen`` fail-closed (#1703/S4).
4. **Der eigentliche Wert dieser Datei:** Für N Produkte läuft
   ``konformitaet_gate.evaluate`` höchstens N-mal. Ohne diese Zusicherung
   wächst die Übersicht still zur Ladebremse — das Gate liest Anforderungen,
   Schwachstellen, Anhang VII, DoC, SBOM, Support-Zeitraum und Meldefristen.
"""
from __future__ import annotations

import pytest

PROJ_A = 'pytest-1749-produkt-a'
PROJ_B = 'pytest-1749-produkt-b'
PROJ_C = 'pytest-1749-produkt-c'

FIRMA = 'pytest-1749-firma'
FIRMA_FREMD = 'pytest-1749-fremd'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _vorgang(db, projekt: str, version: str) -> None:
    from cra import konformitaet_db as kdb
    kdb.save_konformitaet(db, projekt, {'release_version': version,
                                        'bewertungsweg': 'A',
                                        'bewertung_abgeschlossen': True})


# ── 1. Zahlen = Modul-Zahlen ────────────────────────────────────────────────

def test_vorgaenge_je_produkt_mit_modul_zahlen(tmp_path, monkeypatch):
    """Firma mit mehreren CRA-Produkten: je Produkt erscheinen die Vorgänge,
    und zwar mit genau den Werten, die ``list_konformitaet`` liefert."""
    from cra import konformitaet_db as kdb
    from cra import konformitaet_gate as kgate
    from firmen import uebersicht as u

    db = tmp_path / 'cra.sqlite'
    _vorgang(db, PROJ_A, '1.0.0')
    _vorgang(db, PROJ_A, '1.1.0')
    _vorgang(db, PROJ_B, '2.0.0')
    # Produkt-Datensatz ohne Version (Phase 1) — kein Release-Vorgang.
    kdb.save_konformitaet(db, PROJ_B, {'bewertungsweg': 'A'})

    # 1.0.0 durchläuft den Vorgang: eingereicht (friert das Gate ein) und freigegeben.
    kdb.einreichen(db, PROJ_A, '1.0.0', von='dev@example.com',
                   gate={'ampel': 'bedingt', 'offen': 0})
    kdb.freigeben(db, PROJ_A, '1.0.0', von='compliance@example.com')

    monkeypatch.setattr(kgate, 'evaluate',
                        lambda projekt, *, version=None: {'ampel': 'rot'})

    produkte = u.cra_releases_fuer_projekte(
        [{'name': PROJ_A, 'produkt': 'A'}, {'name': PROJ_B, 'produkt': 'B'}], db=db)

    assert [p['projekt'] for p in produkte] == [PROJ_A, PROJ_B]
    a, b = produkte
    assert {v['version'] for v in a['vorgaenge']} == {'1.0.0', '1.1.0'}
    assert [v['version'] for v in b['vorgaenge']] == ['2.0.0'], \
        'der versionslose Produkt-Datensatz ist kein Release-Vorgang'

    # Status/Personen kommen unverändert aus der Vorgangsliste.
    roh = {v['release_version']: v for v in kdb.list_konformitaet(db, PROJ_A)}
    for v in a['vorgaenge']:
        q = roh[v['version']]
        assert v['status'] == q['freigabe_status']
        assert v['erstellt_von'] == q['erstellt_von']
        assert v['geprueft_von'] == q['geprueft_von']

    frei = next(v for v in a['vorgaenge'] if v['version'] == '1.0.0')
    assert frei['status'] == 'freigegeben' and frei['offen'] is False
    assert (frei['ampel'], frei['ampel_quelle']) == ('bedingt', 'eingefroren'), \
        'für einen freigegebenen Vorgang gilt der eingefrorene Stand, nicht heute'

    entwurf = next(v for v in a['vorgaenge'] if v['version'] == '1.1.0')
    assert entwurf['offen'] is True
    assert (entwurf['ampel'], entwurf['ampel_quelle']) == ('rot', 'aktuell')

    # 3 Vorgänge, davon 2 Entwürfe (A 1.1.0, B 2.0.0) — beide rot aus dem Lauf;
    # A 1.0.0 ist freigegeben und trägt „bedingt" aus dem eingefrorenen Stand.
    assert u.releases_summe(produkte) == {'gesamt': 3, 'offen': 2,
                                          'in_pruefung': 0, 'rot': 2}


def test_wartet_auf_freigabe_wird_als_solches_gezaehlt(tmp_path, monkeypatch):
    from cra import konformitaet_db as kdb
    from cra import konformitaet_gate as kgate
    from firmen import uebersicht as u

    db = tmp_path / 'cra.sqlite'
    _vorgang(db, PROJ_A, '3.0.0')
    kdb.einreichen(db, PROJ_A, '3.0.0', von='dev@example.com', gate={'ampel': 'gruen'})
    monkeypatch.setattr(kgate, 'evaluate', lambda *a, **k: pytest.fail(
        'ein eingereichter Vorgang trägt seinen Stand selbst'))

    produkte = u.cra_releases_fuer_projekte([{'name': PROJ_A}], db=db)
    v = produkte[0]['vorgaenge'][0]
    assert v['status'] == 'in_pruefung' and v['wartet_auf_freigabe'] is True
    assert u.releases_summe(produkte)['in_pruefung'] == 1


def test_ohne_gate_und_ohne_lauf_bleibt_die_ampel_unbekannt(tmp_path):
    """Kein stiller Rückfall auf grün oder rot (#1741)."""
    from firmen import uebersicht as u

    db = tmp_path / 'cra.sqlite'
    _vorgang(db, PROJ_A, '0.1.0')
    v = u.cra_releases_fuer_projekte([{'name': PROJ_A}], db=db,
                                     live_gate=False)[0]['vorgaenge'][0]
    assert (v['ampel'], v['ampel_quelle']) == ('', 'unbekannt')


# ── 2. Keine leeren Kacheln ─────────────────────────────────────────────────

def test_firma_ohne_cra_projekt_hat_keinen_block(client, auth_headers, monkeypatch):
    from firmen import uebersicht as u

    client.delete(f'/api/firmen/{FIRMA}/permanent', headers=auth_headers)
    assert client.post('/api/firmen', headers=auth_headers,
                       json={'name': FIRMA, 'company': 'PyTest 1749 GmbH'}).status_code == 201
    try:
        monkeypatch.setattr(u, 'module_projekte', lambda *a, **k: [])
        assert u.build_uebersicht(FIRMA)['cra_releases'] is None
    finally:
        client.delete(f'/api/firmen/{FIRMA}', headers=auth_headers)
        client.delete(f'/api/firmen/{FIRMA}/permanent', headers=auth_headers)


def test_firma_mit_cra_projekt_hat_den_block(client, auth_headers):
    """Gegenprobe: Die Firmenanlage legt das CRA-Projekt an (#430) → Block da."""
    client.delete(f'/api/firmen/{FIRMA}/permanent', headers=auth_headers)
    assert client.post('/api/firmen', headers=auth_headers,
                       json={'name': FIRMA, 'company': 'PyTest 1749 GmbH'}).status_code == 201
    try:
        body = client.get(f'/api/firmen/{FIRMA}/uebersicht',
                          headers=auth_headers).get_json()
        rel = body['cra_releases']
        assert rel is not None and rel['produkte']
        for feld in ('gesamt', 'offen', 'in_pruefung', 'rot'):
            assert feld in rel
    finally:
        client.delete(f'/api/firmen/{FIRMA}', headers=auth_headers)
        client.delete(f'/api/firmen/{FIRMA}/permanent', headers=auth_headers)


# ── 3. Mandantenfähigkeit ───────────────────────────────────────────────────

def test_releases_offen_je_firma_ordnet_nur_bestimmbare_projekte_zu(tmp_path):
    from cra import konformitaet_db as kdb
    from cra.db import save_projekt
    from firmen import uebersicht as u

    db = tmp_path / 'cra.sqlite'
    save_projekt(db, PROJ_A, unternehmen='Mandant Eins')
    save_projekt(db, PROJ_C, unternehmen='Niemand bekannt')
    _vorgang(db, PROJ_A, '1.0.0')
    _vorgang(db, PROJ_A, '1.1.0')
    kdb.einreichen(db, PROJ_A, '1.0.0', von='dev@example.com', gate={'ampel': 'rot'})
    _vorgang(db, PROJ_C, '9.9.9')

    firmen = [{'name': FIRMA, 'unternehmen': 'Mandant Eins', 'firmen_id': 1}]
    out = u.releases_offen_je_firma(firmen, db=db)

    assert out == {FIRMA: {'gesamt': 2, 'offen': 2, 'in_pruefung': 1, 'rot': 1}}
    assert all(PROJ_C not in str(k) for k in out), \
        'ein Projekt ohne bestimmbare Firma darf keinem Mandanten zugeschlagen werden'


def test_releases_offen_je_firma_zaehlt_wie_das_dashboard(tmp_path, monkeypatch):
    """Dieselbe Zählregel wie ``releases_summe`` — sonst zeigt die Liste eine
    andere Zahl als das Firmen-Dashboard."""
    from cra import konformitaet_db as kdb
    from cra import konformitaet_gate as kgate
    from cra.db import save_projekt
    from firmen import uebersicht as u

    db = tmp_path / 'cra.sqlite'
    save_projekt(db, PROJ_A, unternehmen='Mandant Eins')
    for ver, ampel in (('1.0.0', 'rot'), ('1.1.0', 'gruen'), ('1.2.0', 'bedingt')):
        _vorgang(db, PROJ_A, ver)
        kdb.einreichen(db, PROJ_A, ver, von='dev@example.com', gate={'ampel': ampel})

    # Alle eingereicht → kein Lauf nötig, beide Wege lesen denselben Stand.
    monkeypatch.setattr(kgate, 'evaluate', lambda *a, **k: pytest.fail('kein Lauf erwartet'))
    dashboard = u.releases_summe(u.cra_releases_fuer_projekte([{'name': PROJ_A}], db=db))
    liste = u.releases_offen_je_firma(
        [{'name': FIRMA, 'unternehmen': 'Mandant Eins', 'firmen_id': 1}], db=db)[FIRMA]
    assert liste == dashboard


def test_endpunkt_filtert_fremde_mandanten_fail_closed(app, client, auth_headers, auth_token):
    from flask_jwt_extended import create_access_token, decode_token

    for name in (FIRMA, FIRMA_FREMD):
        client.delete(f'/api/firmen/{name}/permanent', headers=auth_headers)
        assert client.post('/api/firmen', headers=auth_headers,
                           json={'name': name, 'company': f'{name} GmbH'}).status_code == 201
    try:
        alle = client.get('/api/firmen/releases-offen', headers=auth_headers).get_json()
        assert FIRMA in alle['firmen'] and FIRMA_FREMD in alle['firmen'], \
            'ohne Whitelist (Admin) sind alle Mandanten sichtbar'

        meine_id = client.get(f'/api/firmen/{FIRMA}',
                              headers=auth_headers).get_json()['firmen_id']
        uebernehmen = ('email', 'roles', 'permissions', 'extra_permissions',
                       'allowed_modules', 'display_name', 'tv')
        with app.app_context():
            claims = decode_token(auth_token)
            eng = create_access_token(
                identity=claims['sub'],
                additional_claims={**{k: claims.get(k) for k in uebernehmen},
                                   'allowed_firmen': [meine_id]})
            leer = create_access_token(
                identity=claims['sub'],
                additional_claims={**{k: claims.get(k) for k in uebernehmen},
                                   'allowed_firmen': []})

        body = client.get('/api/firmen/releases-offen',
                          headers={'Authorization': f'Bearer {eng}'}).get_json()
        assert FIRMA in body['firmen']
        assert FIRMA_FREMD not in body['firmen'], 'fremder Mandant bleibt in der Liste'

        body = client.get('/api/firmen/releases-offen',
                          headers={'Authorization': f'Bearer {leer}'}).get_json()
        assert body['firmen'] == {}, 'leere Whitelist = kein Mandant freigegeben'
    finally:
        for name in (FIRMA, FIRMA_FREMD):
            client.delete(f'/api/firmen/{name}', headers=auth_headers)
            client.delete(f'/api/firmen/{name}/permanent', headers=auth_headers)


# ── 4. Ampel-Kosten (der eigentliche Wert dieser Datei) ─────────────────────

def test_evaluate_hoechstens_einmal_je_produkt(tmp_path, monkeypatch):
    """Für N Produkte höchstens N Gate-Läufe — unabhängig von der Zahl der Releases."""
    from cra import konformitaet_gate as kgate
    from firmen import uebersicht as u

    db = tmp_path / 'cra.sqlite'
    produkte = [PROJ_A, PROJ_B, PROJ_C]
    for p in produkte:
        for ver in ('1.0.0', '1.1.0', '1.2.0', '1.3.0'):
            _vorgang(db, p, ver)   # alles Entwürfe, also ohne eingefrorenen Stand

    laeufe: list[tuple[str, str | None]] = []

    def _zaehlend(projekt, *, version=None):
        laeufe.append((projekt, version))
        return {'ampel': 'bedingt'}

    monkeypatch.setattr(kgate, 'evaluate', _zaehlend)

    ergebnis = u.cra_releases_fuer_projekte([{'name': p} for p in produkte], db=db)

    assert len(laeufe) <= len(produkte), (
        f'{len(laeufe)} Gate-Läufe für {len(produkte)} Produkte — die Übersicht '
        f'skaliert mit der Zahl der Releases statt der Produkte')
    assert len(laeufe) == len(produkte)
    assert {p for p, _ in laeufe} == set(produkte), 'je Produkt genau ein Lauf'
    # Und der Lauf gilt dem jüngsten Vorgang, nicht einem beliebigen.
    for p, version in laeufe:
        jüngste = ergebnis[produkte.index(p)]['vorgaenge'][0]['version']
        assert version == jüngste

    # Die übrigen Vorgänge bleiben ohne Ampel — benannt, nicht erfunden.
    gezeigt = [v for e in ergebnis for v in e['vorgaenge']]
    ohne = [v for v in gezeigt if v['ampel_quelle'] == 'unbekannt']
    assert len(ohne) == len(gezeigt) - len(laeufe)


def test_eingereichte_vorgaenge_loesen_keinen_lauf_aus(tmp_path, monkeypatch):
    from cra import konformitaet_db as kdb
    from cra import konformitaet_gate as kgate
    from firmen import uebersicht as u

    db = tmp_path / 'cra.sqlite'
    for p in (PROJ_A, PROJ_B):
        for ver in ('1.0.0', '1.1.0'):
            _vorgang(db, p, ver)
            kdb.einreichen(db, p, ver, von='dev@example.com', gate={'ampel': 'gruen'})

    laeufe: list[str] = []
    monkeypatch.setattr(kgate, 'evaluate',
                        lambda projekt, *, version=None: laeufe.append(projekt) or {})

    u.cra_releases_fuer_projekte([{'name': PROJ_A}, {'name': PROJ_B}], db=db)
    assert laeufe == [], 'der eingefrorene Stand ist hier nicht nur billiger, sondern richtig'


def test_listenansicht_rechnet_nie(tmp_path, monkeypatch):
    """``releases_offen_je_firma`` ist für eine Seite mit 50+ Mandanten — dort
    hat ein Gate-Lauf nichts zu suchen."""
    from cra import konformitaet_gate as kgate
    from cra.db import save_projekt
    from firmen import uebersicht as u

    db = tmp_path / 'cra.sqlite'
    save_projekt(db, PROJ_A, unternehmen='Mandant Eins')
    _vorgang(db, PROJ_A, '1.0.0')
    monkeypatch.setattr(kgate, 'evaluate', lambda *a, **k: pytest.fail(
        'die Mandanten-Liste darf kein Gate laufen lassen'))

    out = u.releases_offen_je_firma(
        [{'name': FIRMA, 'unternehmen': 'Mandant Eins', 'firmen_id': 1}], db=db)
    assert out[FIRMA]['offen'] == 1
