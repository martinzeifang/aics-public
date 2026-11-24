"""KI-Management-Zusammenfassung: Der Modul-Kontext muss im Prompt landen (#1725).

``build_summary_prompt`` las ursprünglich **nur** ``ctx['reifegrad']`` und
``ctx['offene']`` — den Vertrag aus CRA/NIS2/AI-Act/DSGVO. Module mit eigenem
Zuschnitt (Compliance-Audit, Firmen-Gesamtüberblick) lieferten vollständige
Kennzahlen, die stillschweigend verworfen wurden; der Prompt enthielt dann sogar
die Zeile „(keine offenen Punkte erfasst)". Die KI antwortete daraufhin
wahrheitsgemäß, es lägen keine Daten vor — der Fehler lag **vor** dem Modell.

Die Tests prüfen daher nicht die Formulierung, sondern dass jede gelieferte Zahl
nachweisbar im Prompt steht und dass „keine Daten" nur bei leerem Kontext behauptet
wird. Sie brauchen keine Datenbank: ``build_summary_prompt`` ist eine reine Funktion.
"""
from __future__ import annotations

import re

from shared.reports.summary import build_summary_prompt

# Zuschnitt des Compliance-Audits (compliance_audit/berichte_provider.summary_context)
AUDIT_CTX = {
    'reifegrad': {
        'stufe': 'teilweise compliant',
        'erfuellungsquote_prozent': 43.8,
        'abdeckung_prozent': 87.5,
        'fragen': {'gesamt': 16, 'anwendbar': 15, 'bewertet': 13, 'erfuellt': 5,
                   'teilweise': 4, 'nicht_erfuellt': 4, 'offen': 2},
        'je_framework': [
            {'framework': 'NIS2', 'stufe': 'weitgehend compliant',
             'erfuellungsquote_prozent': 81.2, 'fragen': 8},
            {'framework': 'CRA', 'stufe': 'nicht compliant',
             'erfuellungsquote_prozent': 12.5, 'fragen': 8},
        ],
    },
    'offene': [
        {'id': 'CRA Art. 13(1)', 'titel': 'Werden Schwachstellen systematisch behandelt?',
         'status': 'nicht erfüllt'},
        {'id': 'NIS2 Art. 21(2)d', 'titel': 'Liegt ein Lieferantenverzeichnis vor?',
         'status': 'teilweise erfüllt'},
    ],
    'unternehmen': 'Cyberwoks GmbH',
    'frameworks': ['NIS2', 'CRA'],
    'luecken_anzahl': 10,
}

# Zuschnitt des Firmen-Gesamtüberblicks (firmen/berichte_provider.summary_context)
FIRMEN_CTX = {
    'gesamt_umsetzungsgrad_pct': 61,
    'module': [{'modul': 'CRA', 'umsetzungsgrad_pct': 72,
                'projekte': [{'name': 'Produkt A', 'pct': 72, 'risiken': 4, 'offen': 3}]}],
    'risiken': {'offen_gesamt': 9, 'nach_schwere': {'hoch': 2, 'mittel': 7}, 'top': []},
    'dsgvo_tom': {'reifegrad': 55},
    'offene_aufgaben': [{'titel': 'Jahreskontrolle 2026', 'faellig': '2026-12-31'}],
}

# Gewachsener Vertrag (cra/nis2/ai_act/dsgvo)
CRA_CTX = {
    'reifegrad': {'gesamt_prozent': 64, 'kapitel': [{'id': 'C1', 'prozent': 80}]},
    'offene': [{'id': 'CRA-C3-02', 'titel': 'Schwachstellenmeldung', 'bewertung': 2}],
}


# ── Der eigentliche Defekt ───────────────────────────────────────────────────

def test_audit_kennzahlen_landen_im_prompt():
    """Die Zahlen des Compliance-Audits müssen im Prompt auftauchen.

    Ohne diese Zusicherung ist der Fehler nicht abgedeckt: Der Prompt war syntaktisch
    einwandfrei, nur ohne Inhalt.
    """
    p = build_summary_prompt('Compliance-Audit', 'Cyberwoks CRA', AUDIT_CTX)
    assert 'teilweise compliant' in p, 'Stufe fehlt im Prompt'
    assert '43.8' in p, 'Erfuellungsquote fehlt im Prompt'
    assert 'Art. 13(1)' in p, 'Luecke fehlt im Prompt'
    assert 'Cyberwoks GmbH' in p, 'Unternehmen (Zusatzschluessel) fehlt im Prompt'
    assert 'NIS2' in p and 'CRA' in p, 'Framework-Aufschluesselung fehlt'


def test_firmen_kontext_landet_im_prompt():
    """Derselbe Defekt traf den Firmen-Gesamtüberblick (seit #1393)."""
    p = build_summary_prompt('Firma (Gesamtüberblick)', 'Cyberwoks', FIRMEN_CTX)
    assert 'gesamt_umsetzungsgrad_pct' in p or '61' in p, 'Umsetzungsgrad fehlt'
    assert 'Jahreskontrolle 2026' in p, 'offene Aufgaben fehlen'
    assert 'offen_gesamt' in p, 'Risiko-Kennzahlen fehlen'


def test_keine_daten_behauptung_nur_bei_leerem_kontext():
    """„keine Daten" darf nur stehen, wenn es stimmt.

    Vorher enthielt der Prompt bei reichhaltigem, aber unbekannt benanntem Kontext
    die Zeile „(keine offenen Punkte erfasst)" — genau das hat die KI berichtet.
    """
    voll = build_summary_prompt('Compliance-Audit', 'P', AUDIT_CTX)
    assert 'keine' not in voll.lower().split('Erstelle daraus')[0], \
        f'Prompt behauptet fehlende Daten, obwohl Daten vorliegen:\n{voll}'

    leer = build_summary_prompt('Compliance-Audit', 'P', {})
    assert 'keine Kennzahlen erfasst' in leer, \
        'bei wirklich leerem Kontext muss der Prompt das offenlegen'


def test_leere_werte_gelten_als_keine_daten():
    """Leere Sammlungen sind keine Daten — sonst entsteht ein Prompt voller Nullen."""
    leer = build_summary_prompt('X', 'P', {'reifegrad': {}, 'offene': [],
                                           'module': [], 'hinweis': ''})
    assert 'keine Kennzahlen erfasst' in leer


# ── Rückwärtskompatibilität ──────────────────────────────────────────────────

def test_bekannter_vertrag_unveraendert():
    """CRA/NIS2/AI-Act/DSGVO dürfen sich nicht verändern.

    Die bekannten Blöcke behalten Überschrift und Form; nur Zusatzschlüssel kommen
    hinzu. Diese Module liefern keine, ihr Prompt bleibt also derselbe.
    """
    p = build_summary_prompt('CRA', 'Produkt A', CRA_CTX)
    assert 'Reifegrad-Kennzahlen (JSON):' in p
    assert 'Offene/unzureichend bewertete Punkte (1):' in p
    assert '- CRA-C3-02: Schwachstellenmeldung (Bewertung 2/5)' in p
    assert 'Weitere Kennzahlen' not in p, 'ohne Zusatzschluessel kein Zusatzblock'


def test_keine_erfundene_nullbewertung():
    """Ohne 0–5-Skala darf keine Bewertung behauptet werden.

    Compliance-Audit und WiBA bewerten Erfüllungsgrade. Das frühere
    ``o.get('bewertung', 0)`` hätte jede Lücke als „Bewertung 0/5" ausgewiesen —
    eine Zahl, die das Modul nie erhoben hat.
    """
    p = build_summary_prompt('Compliance-Audit', 'P', AUDIT_CTX)
    assert '0/5' not in p, 'Nullbewertung erfunden'
    assert not re.search(r'Bewertung \d+/5', p), 'numerische Bewertung ohne Skala'
    assert 'Status: nicht erfüllt' in p, 'Erfuellungsgrad wird nicht ausgewiesen'


def test_lange_listen_werden_begrenzt():
    """Der Prompt darf nicht unbegrenzt wachsen (Token-Budget)."""
    ctx = {'offene': [{'id': f'Q{i}', 'titel': 'x' * 50} for i in range(500)],
           'ballast': ['y' * 200 for _ in range(500)]}
    p = build_summary_prompt('X', 'P', ctx)
    assert p.count('\n- Q') <= 40, 'offene Punkte nicht begrenzt'
    assert len(p) < 12000, f'Prompt zu lang: {len(p)} Zeichen'
