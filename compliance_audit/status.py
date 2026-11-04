"""Wasserstandsmeldung: Compliance-Stand aus den Audit-Antworten berechnen.

Die Stufe wird **deterministisch aus den Antworten** abgeleitet, nicht von der KI
vergeben. Grund: Die Aussage „Sie sind weitgehend compliant" ist gegenüber dem
Kunden eine Zusage. Sie muss reproduzierbar sein, bei gleichen Antworten immer
gleich ausfallen und sich Frage für Frage begründen lassen. Die KI formuliert
anschließend nur den Text zur bereits feststehenden Stufe (siehe
:mod:`compliance_audit.prompts`).

Rechenweg
---------
Je Frage gibt es eine Erfüllung aus :data:`ERFUELLUNG`. Nicht anwendbare Fragen
fallen vollständig aus der Rechnung (Scope-Entscheidung des Auditors). Alle
übrigen Fragen bilden den Nenner — **auch die unbeantworteten**:

    quote = (1·erfuellt + 0,5·teilweise) / (gesamt − nicht_anwendbar)

Dass offene Fragen wie „nicht erfüllt" zählen, ist Absicht: Was nicht belegt ist,
ist nicht nachgewiesen. Ein Audit mit 10 von 200 beantworteten Fragen darf nicht
„vollständig compliant" ergeben. Für den Auditor wird die Quote der *bewerteten*
Fragen (:data:`quote_bewertet_prozent`) zusätzlich ausgewiesen, damit der
Unterschied zwischen „schlecht erfüllt" und „noch nicht erhoben" sichtbar bleibt.
"""

from __future__ import annotations

from typing import Any, Iterable

# ── Vokabular ────────────────────────────────────────────────────────────────

#: Erfüllung je Frage. ``offen`` = noch nicht beantwortet.
ERFUELLUNG: tuple[str, ...] = (
    'erfuellt', 'teilweise', 'nicht_erfuellt', 'nicht_anwendbar', 'offen')

#: Anzeigetexte der Erfüllung (Berichte, Word-Vorlagen, UI). Liegt hier, weil
#: dieses Modul das Vokabular besitzt — vorher stand die Tabelle nur im
#: Berichts-Provider und wäre für die Vorlagen-Engine ein zweites Mal entstanden.
ERFUELLUNG_LABELS: dict[str, str] = {
    'erfuellt': 'erfüllt',
    'teilweise': 'teilweise erfüllt',
    'nicht_erfuellt': 'nicht erfüllt',
    'nicht_anwendbar': 'nicht anwendbar',
    'offen': 'offen',
}

#: Gewicht in der Quote. ``offen`` zählt bewusst 0 (siehe Modul-Docstring).
GEWICHT: dict[str, float] = {
    'erfuellt': 1.0,
    'teilweise': 0.5,
    'nicht_erfuellt': 0.0,
    'offen': 0.0,
}

#: Compliance-Stufen, absteigend.
STUFEN: tuple[str, ...] = ('vollstaendig', 'weitgehend', 'teilweise', 'nicht')

#: Untergrenze der Quote je Stufe (``vollstaendig`` zusätzlich: nichts offen).
SCHWELLEN: dict[str, float] = {
    'vollstaendig': 1.0,
    'weitgehend': 0.80,
    'teilweise': 0.40,
    'nicht': 0.0,
}

STUFEN_LABELS: dict[str, str] = {
    'vollstaendig': 'vollständig compliant',
    'weitgehend': 'weitgehend compliant',
    'teilweise': 'teilweise compliant',
    'nicht': 'nicht compliant',
    'unbewertet': 'nicht bewertet',
}

#: Kurztext für den Kunden — was die Stufe praktisch bedeutet.
STUFEN_BEDEUTUNG: dict[str, str] = {
    'vollstaendig': 'Alle anwendbaren Anforderungen sind erfüllt und belegt.',
    'weitgehend': 'Die Anforderungen sind überwiegend erfüllt; es bleiben einzelne Lücken.',
    'teilweise': 'Ein relevanter Teil der Anforderungen ist erfüllt, wesentliche Lücken bestehen.',
    'nicht': 'Die Anforderungen sind überwiegend nicht erfüllt oder nicht nachgewiesen.',
    'unbewertet': 'Es liegen noch keine anwendbaren, bewerteten Fragen vor.',
}

#: Freitext-Bewertungen aus der Zeit vor v7.4.0 → Erfüllung. Die alte Skala war
#: je Projekt konfigurierbar (``prompt.bewertung_skala``), deshalb tolerant.
_SYNONYME: dict[str, str] = {
    'erfuellt': 'erfuellt', 'erfüllt': 'erfuellt', 'ja': 'erfuellt',
    'konform': 'erfuellt', 'vollstaendig': 'erfuellt', 'vollständig': 'erfuellt',
    'gut': 'erfuellt', 'umgesetzt': 'erfuellt', 'compliant': 'erfuellt',
    'teilweise': 'teilweise', 'teilweise erfuellt': 'teilweise',
    'teilweise erfüllt': 'teilweise', 'partiell': 'teilweise',
    'ausreichend': 'teilweise', 'in umsetzung': 'teilweise',
    'teilkonform': 'teilweise',
    'nicht erfuellt': 'nicht_erfuellt', 'nicht erfüllt': 'nicht_erfuellt',
    'nein': 'nicht_erfuellt', 'mangelhaft': 'nicht_erfuellt',
    'nicht umgesetzt': 'nicht_erfuellt', 'fehlt': 'nicht_erfuellt',
    'nicht konform': 'nicht_erfuellt', 'nicht_erfuellt': 'nicht_erfuellt',
    'nicht anwendbar': 'nicht_anwendbar', 'nicht_anwendbar': 'nicht_anwendbar',
    'n/a': 'nicht_anwendbar', 'na': 'nicht_anwendbar',
    'entfaellt': 'nicht_anwendbar', 'entfällt': 'nicht_anwendbar',
    'ausserhalb scope': 'nicht_anwendbar', 'außerhalb scope': 'nicht_anwendbar',
    'offen': 'offen', '': 'offen',
}


def normalize_erfuellung(wert: Any) -> str:
    """Beliebige Bewertung → kanonische Erfüllung (unbekannt → ``offen``).

    Nimmt sowohl die neuen Schlüssel als auch die alten Freitext-Noten, damit
    bestehende Audit-Projekte ohne Nachbearbeitung eine Wasserstandsmeldung
    bekommen.
    """
    key = ' '.join(str(wert or '').strip().lower().split())
    if key in _SYNONYME:
        return _SYNONYME[key]
    # Teilstring-Treffer: „teilweise erfüllt (Nachweis fehlt)" u. ä.
    for needle, ziel in (
        ('nicht anwendbar', 'nicht_anwendbar'), ('nicht erf', 'nicht_erfuellt'),
        ('teilweise', 'teilweise'), ('erf', 'erfuellt'),
    ):
        if needle in key:
            return ziel
    return 'offen'


# ── Berechnung ───────────────────────────────────────────────────────────────

def _zaehlen(fragen: Iterable[dict[str, Any]]) -> dict[str, int]:
    zahl = {k: 0 for k in ERFUELLUNG}
    zahl['gesamt'] = 0
    for f in fragen:
        zahl['gesamt'] += 1
        zahl[erfuellung_of(f)] += 1
    return zahl


def erfuellung_of(frage: dict[str, Any]) -> str:
    """Erfüllung einer Frage — bevorzugt die Spalte ``erfuellung``.

    Fallback auf das alte Freitext-Feld ``bewertung``, damit Projekte von vor
    v7.4.0 mitgerechnet werden.
    """
    roh = frage.get('erfuellung')
    if roh in ERFUELLUNG:
        return str(roh)
    if roh:
        return normalize_erfuellung(roh)
    return normalize_erfuellung(frage.get('bewertung'))


def stufe_fuer(quote: float | None, *, offen: int) -> str:
    """Quote (0..1) → Stufe. ``None`` = nichts Anwendbares → ``unbewertet``."""
    if quote is None:
        return 'unbewertet'
    if quote >= SCHWELLEN['vollstaendig'] and offen == 0:
        return 'vollstaendig'
    # Ohne die Offen-Bedingung wäre eine Quote von 1,0 nicht erreichbar, wenn
    # noch Fragen offen sind — dann greift die nächste Stufe.
    if quote >= SCHWELLEN['weitgehend']:
        return 'weitgehend'
    if quote >= SCHWELLEN['teilweise']:
        return 'teilweise'
    return 'nicht'


def _block(fragen: list[dict[str, Any]]) -> dict[str, Any]:
    """Kennzahlen + Stufe für eine Fragenmenge (Framework oder gesamt)."""
    z = _zaehlen(fragen)
    anwendbar = z['gesamt'] - z['nicht_anwendbar']
    bewertet = anwendbar - z['offen']

    if anwendbar <= 0:
        quote = None
        quote_bewertet = None
    else:
        punkte = sum(GEWICHT[erfuellung_of(f)] for f in fragen
                     if erfuellung_of(f) != 'nicht_anwendbar')
        quote = punkte / anwendbar
        quote_bewertet = (punkte / bewertet) if bewertet > 0 else None

    stufe = stufe_fuer(quote, offen=z['offen'])
    return {
        'stufe': stufe,
        'label': STUFEN_LABELS[stufe],
        'bedeutung': STUFEN_BEDEUTUNG[stufe],
        'quote_prozent': None if quote is None else round(quote * 100, 1),
        'quote_bewertet_prozent': (None if quote_bewertet is None
                                   else round(quote_bewertet * 100, 1)),
        'abdeckung_prozent': (None if anwendbar <= 0
                              else round(bewertet / anwendbar * 100, 1)),
        'fragen': {
            'gesamt': z['gesamt'],
            'anwendbar': anwendbar,
            'bewertet': bewertet,
            'erfuellt': z['erfuellt'],
            'teilweise': z['teilweise'],
            'nicht_erfuellt': z['nicht_erfuellt'],
            'nicht_anwendbar': z['nicht_anwendbar'],
            'offen': z['offen'],
        },
    }


def luecken(fragen: Iterable[dict[str, Any]], *, limit: int = 0) -> list[dict[str, Any]]:
    """Die Lücken — nicht erfüllt zuerst, dann teilweise, dann offen."""
    rang = {'nicht_erfuellt': 0, 'teilweise': 1, 'offen': 2}
    out = []
    for f in fragen:
        e = erfuellung_of(f)
        if e not in rang:
            continue
        out.append({
            'framework': f.get('framework') or '',
            'section_ref': f.get('section_ref') or '',
            'thema': f.get('thema') or '',
            'frage': f.get('frage') or '',
            'erfuellung': e,
            'kommentar': f.get('kommentar') or '',
            'question_num': f.get('question_num'),
        })
    out.sort(key=lambda d: (rang[d['erfuellung']], str(d['framework']),
                            d['question_num'] if isinstance(d['question_num'], int) else 0))
    return out[:limit] if limit and limit > 0 else out


def build_status(fragen: list[dict[str, Any]], *,
                 luecken_limit: int = 0) -> dict[str, Any]:
    """Wasserstandsmeldung: Gesamtstufe + Stufe je Framework + Lücken.

    Args:
        fragen: Fragen eines Audit-Projekts (``framework``, ``erfuellung`` bzw.
            altes ``bewertung``, ``thema``, ``frage``, ``kommentar``).
        luecken_limit: Lückenliste kürzen (0 = alle). Für KI-Prompts sinnvoll,
            damit das Kontextfenster nicht überläuft.

    Returns:
        ``{stufe, label, bedeutung, quote_prozent, …, frameworks: [...],
        luecken: [...]}``. Die Stufe ist reproduzierbar — gleiche Antworten,
        gleiche Stufe.
    """
    fragen = list(fragen or [])
    gesamt = _block(fragen)

    nach_fw: dict[str, list[dict[str, Any]]] = {}
    for f in fragen:
        nach_fw.setdefault(str(f.get('framework') or '(ohne Framework)'), []).append(f)

    frameworks = []
    for name in sorted(nach_fw):
        blk = _block(nach_fw[name])
        blk['framework'] = name
        frameworks.append(blk)

    return {
        **gesamt,
        'schwellen': dict(SCHWELLEN),
        'frameworks': frameworks,
        'luecken': luecken(fragen, limit=luecken_limit),
    }
