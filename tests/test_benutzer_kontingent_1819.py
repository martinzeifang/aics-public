"""Benutzergrenze wächst mit dem Mandantenbestand — und sperrt nicht (#1819).

Zwei Entscheidungen werden hier festgehalten, beide aus dem Betrieb:

**Die Grenze wächst mit.** Fünf Named-User je Lizenz passen beim Direktkunden
mit einem Mandanten. Ein Dienstleister mit sechzig Mandanten zahlt fünfstellig
im Monat und durfte fünf Berater anlegen. Das Token trägt deshalb seit #1819
die *Regel* statt einer Zahl: Sockel (``usr``) plus Zuschlag je aktivem
Mandanten (``usrm``), ausgerechnet im Client, weil sich der Bestand hier ändert.

**Sie sperrt nicht.** Bis v8.0.11 gab ``POST /api/admin/users`` ein **423**
zurück, sobald das Kontingent erreicht war. Das Mandanten-Kontingent war aus
demselben Grund schon in #1713 von der Sperre auf einen Hinweis umgestellt
worden — zwei gleichartige kaufmännische Zusagen, die sich entgegengesetzt
verhalten, kann niemand erklären. Und die Sperre traf den Falschen: Wer einen
Kollegen anlegen muss, kann den Vertrag nicht ändern.
"""
from __future__ import annotations

import inspect

import pytest

from shared.licensing.kontingent import erlaubte_benutzer, ueberhang


# ── Die Formel ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sockel,je_mandant,mandanten,erwartet", [
    (5, 2, 0, 5),      # frische Installation
    (5, 2, 1, 7),      # Direktkunde
    (5, 2, 60, 125),   # Dienstleister — der Fall, der den Ausschlag gab
    (5, 0, 60, 5),     # Zuschlag aus → Verhalten wie bis v8.0.11
])
def test_grenze_waechst_mit_dem_bestand(sockel, je_mandant, mandanten, erwartet):
    assert erlaubte_benutzer(sockel, je_mandant, mandanten) == erwartet


def test_unbegrenzt_bleibt_unbegrenzt():
    """``usr = 0`` heißt unbegrenzt. Ein Zuschlag darf daraus keine endliche
    Zahl machen — sonst bekäme ausgerechnet der größte Kunde still eine
    Grenze, die nie vereinbart war."""
    assert erlaubte_benutzer(0, 2, 300) == 0
    assert ueberhang(900, 0, 2, 300) == 0


def test_muellwerte_senken_die_grenze_nicht():
    assert erlaubte_benutzer(5, -3, 10) == 5
    assert erlaubte_benutzer(5, 2, -10) == 5
    assert erlaubte_benutzer(5, None, None) == 5


def test_die_formel_steht_nur_an_einer_stelle():
    """Dieselbe Regel läuft im Lizenzserver, im Backend und in der Anzeige.

    Im Frontend darf sie **nicht** noch einmal entstehen: Der Server liefert
    ``max_users_effektiv`` und ``user_ueberhang`` fertig mit. Eine zweite
    Herleitung driftet (die Lehre aus #1703/S9) — und die Abweichung fällt
    erst auf, wenn ein Kunde eine Zahl bestreitet.
    """
    from pathlib import Path
    sb = Path('frontend/src/components/StatusBar.vue').read_text(encoding='utf-8')
    assert 'max_users_effektiv' in sb, 'Der Fuß soll die gerechnete Zahl zeigen'
    assert 'max_users_je_mandant *' not in sb and 'max_users_je_mandant*' not in sb, \
        'Das Frontend rechnet die Grenze nicht selbst nach'


# ── Der Claim ───────────────────────────────────────────────────────────────

def test_token_ohne_usrm_verhaelt_sich_wie_bisher():
    """Bestandstoken kennen ``usrm`` nicht → 0 → nur der Sockel gilt."""
    from server import license_state as ls
    zustand = ls.LicenseState()
    assert zustand.max_users_je_mandant == 0


def test_ein_zustand_meldet_seine_eigenen_grenzen():
    """Eine Kopie des Lizenzzustands darf nicht die Zahlen des laufenden
    melden — sonst zeigt eine Vorschau (etwa der Vorher/Nachher-Vergleich in
    ``/api/license/refresh``) Werte, die zu einem anderen Token gehören."""
    from server import license_state as ls

    eigen = ls.LicenseState(max_users=7, max_users_je_mandant=3)
    d = eigen.to_dict()
    assert d['max_users'] == 7 and d['max_users_je_mandant'] == 3
    assert d['max_users_effektiv'] == erlaubte_benutzer(7, 3, d['aktive_mandanten'])


def test_claim_wird_gelesen():
    quelle = inspect.getsource(__import__('server.license_state', fromlist=['x']))
    assert "p.get('usrm')" in quelle, 'Der Zuschlag aus dem Token wird nicht gelesen'


# ── Anzeige statt Sperre ────────────────────────────────────────────────────

def test_benutzeranlage_sperrt_nicht_mehr():
    """Die 423-Antwort ist weg — und soll nicht zurückkommen."""
    from pathlib import Path
    quelle = Path('server/api/admin.py').read_text(encoding='utf-8')
    assert 'license-user-limit' not in quelle, \
        'Die Benutzeranlage darf am Kontingent nicht mehr scheitern'
    assert '_benutzer_lizenzhinweis' in quelle


def test_anlage_meldet_den_ueberhang(client, auth_headers, monkeypatch):
    """Angelegt wird trotzdem — die Antwort sagt nur, dass es kostet."""
    from server import license_state as ls

    st = ls.get_state()
    vorher = (st.max_users, st.max_users_je_mandant)
    st.max_users, st.max_users_je_mandant = 1, 0
    ls.kontingent_neu_rechnen()
    try:
        r = client.post('/api/admin/users', headers=auth_headers, json={
            'email': 'kontingent-1819@example.com',
            'password': 'Sehr-Langes-Testkennwort-2026!',
            'roles': ['viewer'],
        })
        assert r.status_code == 201, r.json
        # Ein Hinweis ist zu erwarten, sobald mehr als ein Nicht-Admin da ist;
        # die Zahl hängt am Bestand der Testdatenbank, die Form nicht.
        hinweis = r.json.get('lizenz_hinweis')
        if hinweis:
            assert hinweis['code'] == 'benutzer-kontingent-ueberschritten'
            assert hinweis['ueberhang'] >= 1
            assert 'abgerechnet' in hinweis['message']
    finally:
        client.delete(f"/api/admin/users/{r.json.get('id')}", headers=auth_headers)
        st.max_users, st.max_users_je_mandant = vorher
        ls.kontingent_neu_rechnen()


def test_zustand_liefert_den_rechenweg_mit():
    """Die Oberfläche soll die Grenze nicht herleiten müssen, sondern lesen."""
    from server import license_state as ls

    st = ls.get_state()
    vorher = (st.max_users, st.max_users_je_mandant)
    st.max_users, st.max_users_je_mandant = 5, 2
    ls.kontingent_neu_rechnen()
    try:
        d = st.to_dict()
        for feld in ('max_users', 'max_users_je_mandant', 'max_users_effektiv',
                     'user_count', 'aktive_mandanten', 'user_ueberhang'):
            assert feld in d, f'{feld} fehlt im Lizenzzustand'
        assert d['max_users_effektiv'] == erlaubte_benutzer(5, 2, d['aktive_mandanten'])
    finally:
        st.max_users, st.max_users_je_mandant = vorher
        ls.kontingent_neu_rechnen()


def test_nicht_zaehlbar_behauptet_keine_ueberschreitung(monkeypatch):
    """Scheitert die Zählung, wird nichts behauptet.

    Ein Hinweis im Fuß jedes Anwenders, weil eine Abfrage fehlschlug, wäre die
    falsche Richtung — und das Erste, was der Betreiber meldet.
    """
    from server import license_state as ls

    def kaputt():
        raise RuntimeError('keine Datenbank')

    monkeypatch.setattr(ls, '_zaehle_benutzer', kaputt)
    ls.kontingent_neu_rechnen()
    try:
        k = ls._kontingent()
        assert k['zaehlbar'] is False
        assert k['user_ueberhang'] == 0
    finally:
        ls.kontingent_neu_rechnen()


def test_fehlende_mandantenzahl_erfindet_keine_ueberschreitung(monkeypatch):
    """Dieselbe Richtung für die zweite Zählung.

    ``_count_firmen`` fängt seine Fehler selbst ab und liefert (0, 0). Würde
    `_kontingent` das benutzen, fiele die Grenze stillschweigend auf den
    Sockel zurück — bei 60 Mandanten von 125 auf 5 — und der Fuß meldete eine
    Überschreitung, weil eine Abfrage scheiterte.
    """
    from server import license_state as ls
    import shared.licensing.usage as usage

    def kaputt():
        raise RuntimeError('keine Datenbank')

    monkeypatch.setattr(usage, 'count_firmen', kaputt)
    ls.kontingent_neu_rechnen()
    try:
        k = ls._kontingent(5, 2)
        assert k['zaehlbar'] is False
        assert k['user_ueberhang'] == 0
    finally:
        ls.kontingent_neu_rechnen()


def test_administratoren_zaehlen_mit():
    """#1822: Die Ausnahme für Admin-Konten ist gefallen.

    Bis v8.0.11 waren Administratoren vom Named-User-Limit ausgenommen (#393) —
    aus der Zeit, als „Named-User" die Fachanwender meinte. In der Praxis
    arbeitet ein Konto mit Administratorrolle in denselben Modulen wie jedes
    andere, und die Ausnahme war am Ende eine Einladung, Arbeitskonten mit
    Admin-Rolle anzulegen. Die zweite Zahl bleibt als Teilmenge erhalten.
    """
    from server import license_state as ls

    gesamt, admins = ls._zaehle_benutzer()
    assert gesamt >= admins, 'Admins sind eine Teilmenge, kein Abzug'

    quelle = inspect.getsource(ls._zaehle_benutzer)
    assert 'len(active)' in quelle and 'len(active) - len(admins)' not in quelle, \
        'Administratoren duerfen nicht wieder abgezogen werden'


def test_zaehlregel_steht_einmal():
    """„Aktiv und kein Admin" bestimmt Heartbeat, Anzeige und Abrechnung.

    Liefe die Regel an mehreren Stellen auseinander, stritte man mit dem
    Kunden über Zahlen, die beide Seiten korrekt ausgerechnet haben.
    """
    from server import license_state as ls

    assert 'return _zaehle_benutzer()' in inspect.getsource(ls._count_users)
    assert '_zaehle_benutzer()' in inspect.getsource(ls._kontingent)


def test_fuss_zeigt_den_hinweis():
    from pathlib import Path
    sb = Path('frontend/src/components/StatusBar.vue').read_text(encoding='utf-8')
    assert 'lizenzHinweis' in sb and 'user_ueberhang' in sb
    layout = Path('frontend/src/components/AppLayout.vue').read_text(encoding='utf-8')
    assert 'Lizenz-User-Limit' not in layout, \
        'Das blockierend klingende Banner gehört nicht zurück'
