"""KI-Prompt für die Wasserstandsmeldung.

Wichtig: Die Compliance-Stufe steht **vor** dem KI-Aufruf fest
(:func:`compliance_audit.status.build_status`). Der Prompt übergibt sie als
Vorgabe und verlangt ausdrücklich, dass die KI sie nicht verändert. Die KI
schreibt nur den Text für den Kunden — Einordnung, Lücken, nächste Schritte.

So bleibt die Aussage „Sie sind weitgehend compliant" reproduzierbar und
begründbar, während die Formulierung trotzdem laienverständlich wird.
"""

from __future__ import annotations

import json
from typing import Any

from security_utils import add_untrusted_block, sanitize_untrusted_text

from compliance_audit.status import STUFEN_LABELS

SYSTEM_PROMPT = (
    'Du bist ein erfahrener Compliance-Auditor und schreibst eine '
    'Wasserstandsmeldung für den Kunden. Du bewertest nicht neu — die '
    'Compliance-Stufe ist vorgegeben und berechnet. Du erklärst sie '
    'verständlich, nennst die wichtigsten Lücken und die nächsten Schritte. '
    'Antworte ausschließlich mit dem geforderten JSON.'
)

#: Erwartete Antwortstruktur (auch für den Parser die Referenz).
ANTWORT_FELDER: tuple[str, ...] = (
    'kundenmitteilung', 'je_framework', 'top_massnahmen', 'fazit')


def build_status_prompt(projekt: dict[str, Any], status: dict[str, Any], *,
                        luecken_limit: int = 40) -> str:
    """Prompt für die Wasserstandsmeldung eines Audit-Projekts.

    Args:
        projekt: Audit-Projekt (``name``, ``unternehmen``, ``pruefungsfokus``).
        status: Ergebnis von :func:`compliance_audit.status.build_status`.
        luecken_limit: wie viele Lücken in den Prompt wandern.
    """
    lines: list[str] = [SYSTEM_PROMPT, '']

    lines.append('## Auftrag')
    lines.append(
        'Erstelle aus dem berechneten Compliance-Stand eine Wasserstandsmeldung '
        'für den Kunden. Die Stufe ist VORGEGEBEN und darf nicht verändert, '
        'relativiert oder neu bewertet werden — begründe sie.')
    lines.append('')

    lines.append('## Kunde und Prüfumfang')
    add_untrusted_block(lines, 'Projekt',
                        sanitize_untrusted_text(projekt.get('name'), max_len=200),
                        max_len=200)
    add_untrusted_block(lines, 'Unternehmen',
                        sanitize_untrusted_text(projekt.get('unternehmen'), max_len=200),
                        max_len=200)
    if projekt.get('pruefungsfokus'):
        add_untrusted_block(lines, 'Prüfungsfokus',
                            sanitize_untrusted_text(projekt.get('pruefungsfokus'),
                                                    max_len=2000),
                            max_len=2000)
    lines.append('')

    lines.append('## Berechneter Stand (VORGABE — nicht ändern)')
    stufe = str(status.get('stufe') or 'unbewertet')
    lines.append(f'- Gesamtstufe: **{STUFEN_LABELS.get(stufe, stufe)}** (`{stufe}`)')
    lines.append(f"- Erfüllungsquote: {status.get('quote_prozent')} %"
                 ' (offene Fragen zählen als nicht nachgewiesen)')
    lines.append(f"- Quote nur der bewerteten Fragen: {status.get('quote_bewertet_prozent')} %")
    lines.append(f"- Abdeckung (bewertete von anwendbaren Fragen): {status.get('abdeckung_prozent')} %")
    f = status.get('fragen') or {}
    lines.append(
        f"- Fragen: {f.get('gesamt')} gesamt · {f.get('erfuellt')} erfüllt · "
        f"{f.get('teilweise')} teilweise · {f.get('nicht_erfuellt')} nicht erfüllt · "
        f"{f.get('offen')} offen · {f.get('nicht_anwendbar')} nicht anwendbar")
    lines.append('')

    lines.append('### Je Framework (ebenfalls Vorgabe)')
    for fw in status.get('frameworks') or []:
        fwf = fw.get('fragen') or {}
        lines.append(
            f"- {sanitize_untrusted_text(fw.get('framework'), max_len=120)}: "
            f"**{fw.get('label')}** ({fw.get('quote_prozent')} %, "
            f"{fwf.get('offen')} offen von {fwf.get('anwendbar')} anwendbaren)")
    lines.append('')

    luecken = (status.get('luecken') or [])[:luecken_limit]
    if luecken:
        lines.append('### Lücken (nicht erfüllt / teilweise / offen)')
        for lk in luecken:
            ref = sanitize_untrusted_text(lk.get('section_ref'), max_len=60)
            lines.append(
                f"- [{lk.get('erfuellung')}] "
                f"{sanitize_untrusted_text(lk.get('framework'), max_len=80)}"
                f"{' ' + ref if ref else ''}: "
                f"{sanitize_untrusted_text(lk.get('frage'), max_len=400)}")
            if lk.get('kommentar'):
                lines.append(
                    f"    Anmerkung: {sanitize_untrusted_text(lk.get('kommentar'), max_len=300)}")
        if len(status.get('luecken') or []) > luecken_limit:
            lines.append(f"- … und {len(status['luecken']) - luecken_limit} weitere Lücken")
        lines.append('')

    lines.append('## Antwortformat')
    lines.append('Antworte ausschließlich mit diesem JSON, ohne Rahmentext:')
    lines.append('```json')
    lines.append(json.dumps({
        'kundenmitteilung': 'string — 4–6 Sätze, laienverständlich, nennt die Stufe '
                            'beim Namen und sagt, was sie praktisch bedeutet',
        'je_framework': [{
            'framework': 'string',
            'einschaetzung': 'string — 2–3 Sätze zur vorgegebenen Stufe',
            'hauptluecken': ['string'],
            'naechste_schritte': ['string'],
        }],
        'top_massnahmen': [{
            'massnahme': 'string',
            'begruendung': 'string',
            'prioritaet': 'hoch | mittel | niedrig',
            'aufwand': 'hoch | mittel | niedrig',
        }],
        'fazit': 'string — 2–3 Sätze',
    }, ensure_ascii=False, indent=2))
    lines.append('```')
    lines.append('')
    lines.append('Regeln:')
    lines.append('- Die vorgegebenen Stufen sind gesetzt. Wenn die Datenlage dünn ist, '
                 'sage das in der Mitteilung, ändere aber nicht die Stufe.')
    lines.append('- Keine erfundenen Nachweise, Normstellen oder Zahlen.')
    lines.append('- Offene Fragen sind „noch nicht erhoben", nicht „nicht erfüllt" — '
                 'in der Quote zählen sie trotzdem gegen den Kunden. Erkläre das, '
                 'falls viele Fragen offen sind.')
    lines.append('- Deutsch, sachlich, ohne Werbesprache.')
    return '\n'.join(lines)


def _json_objekt(text: str) -> dict[str, Any]:
    """JSON-Objekt aus einer KI-Antwort holen — tolerant gegen Rahmen und Beitext.

    Die Provider liefern mal reines JSON, mal in ```json-Zaeunen, mal mit einem
    Satz davor oder danach. Beide Parser dieses Moduls nutzen denselben Weg.
    """
    raw = (text or '').strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1]
        if raw.rstrip().endswith('```'):
            raw = raw.rstrip()[:-3]
    raw = raw.strip()
    if not raw.startswith('{'):
        start, ende = raw.find('{'), raw.rfind('}')
        if start < 0 or ende <= start:
            raise ValueError('Keine JSON-Antwort gefunden')
        raw = raw[start:ende + 1]
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('JSON-Objekt erwartet')
    return data


def parse_status_response(text: str) -> dict[str, Any]:
    """KI-Antwort robust parsen (auch mit ```json-Rahmen oder Rahmentext).

    Raises:
        ValueError: wenn kein JSON-Objekt gefunden wurde.
    """
    data = _json_objekt(text)

    out: dict[str, Any] = {
        'kundenmitteilung': str(data.get('kundenmitteilung') or '').strip(),
        'fazit': str(data.get('fazit') or '').strip(),
        'je_framework': [],
        'top_massnahmen': [],
    }
    for fw in data.get('je_framework') or []:
        if not isinstance(fw, dict):
            continue
        out['je_framework'].append({
            'framework': str(fw.get('framework') or '').strip(),
            'einschaetzung': str(fw.get('einschaetzung') or '').strip(),
            'hauptluecken': [str(x).strip() for x in (fw.get('hauptluecken') or []) if str(x).strip()],
            'naechste_schritte': [str(x).strip() for x in (fw.get('naechste_schritte') or []) if str(x).strip()],
        })
    for m in data.get('top_massnahmen') or []:
        if not isinstance(m, dict):
            continue
        out['top_massnahmen'].append({
            'massnahme': str(m.get('massnahme') or '').strip(),
            'begruendung': str(m.get('begruendung') or '').strip(),
            'prioritaet': str(m.get('prioritaet') or '').strip().lower(),
            'aufwand': str(m.get('aufwand') or '').strip().lower(),
        })
    return out


# ── Auditbericht ─────────────────────────────────────────────────────────────

BERICHT_SYSTEM = (
    'Du bist ein erfahrener IT-Compliance-Auditor und schreibst den Bericht zu '
    'einem durchgeführten Audit. Du bewertest die Erfüllung nicht neu — sie steht '
    'in den Antworten und der berechneten Quote. Du fasst zusammen, ordnest ein '
    'und leitest Maßnahmen ab. Antworte ausschließlich mit dem geforderten JSON.'
)

#: Pflichtfelder der Antwort. Bewusst identisch zum bestehenden Schema, das
#: ``/bericht/import`` validiert und ``/bericht/export`` ins DOCX rendert —
#: der Prompt wird getauscht, der Vertrag nach hinten bleibt.
BERICHT_FELDER: tuple[str, ...] = (
    'gesamtbewertung', 'zusammenfassung', 'framework_bewertungen',
    'handlungsempfehlungen', 'fazit')


def build_bericht_prompt(projekt: dict[str, Any], fragen: list[dict[str, Any]],
                         status: dict[str, Any] | None = None, *,
                         max_fragen: int = 60) -> str:
    """Prompt für den **Auditbericht**.

    Vorher nutzte dieser Pfad ``gutachten.prompts._build_gutachten_prompt`` — mit
    einer Signatur, die nicht mehr zur Aufrufstelle passte
    (``TypeError: unexpected keyword argument 'pruefungsfokus'``), also HTTP 500.
    Fachlich war es ohnehin falsch: Hier entsteht ein Auditbericht, kein Gutachten.

    Der berechnete Compliance-Stand wird mitgegeben, damit der Bericht und die
    Wasserstandsmeldung dieselbe Aussage treffen und nicht auseinanderlaufen.
    """
    lines: list[str] = [BERICHT_SYSTEM, '']

    lines.append('## Auftrag')
    lines.append('Erstelle den Bericht zu einem abgeschlossenen Compliance-Audit: '
                 'Zusammenfassung für die Leitung, Einordnung je Framework, '
                 'Feststellungen und priorisierte Maßnahmen.')
    lines.append('')

    lines.append('## Audit')
    add_untrusted_block(lines, 'Projekt',
                        sanitize_untrusted_text(projekt.get('name'), max_len=200),
                        max_len=200)
    add_untrusted_block(lines, 'Unternehmen',
                        sanitize_untrusted_text(projekt.get('unternehmen'), max_len=200),
                        max_len=200)
    frameworks = [str(f) for f in (projekt.get('frameworks') or [])]
    lines.append(f"- Frameworks: {', '.join(frameworks) or '(keine)'}")
    if projekt.get('pruefungsfokus'):
        add_untrusted_block(lines, 'Prüfungsfokus',
                            sanitize_untrusted_text(projekt.get('pruefungsfokus'),
                                                    max_len=2000),
                            max_len=2000)
    lines.append('')

    if status:
        f = status.get('fragen') or {}
        lines.append('## Berechneter Stand (nicht neu bewerten)')
        lines.append(f"- Gesamtstufe: **{status.get('label')}** "
                     f"({status.get('quote_prozent')} % Erfüllungsquote)")
        lines.append(
            f"- Fragen: {f.get('gesamt')} gesamt · {f.get('erfuellt')} erfüllt · "
            f"{f.get('teilweise')} teilweise · {f.get('nicht_erfuellt')} nicht erfüllt · "
            f"{f.get('offen')} offen · {f.get('nicht_anwendbar')} nicht anwendbar")
        for fw in status.get('frameworks') or []:
            lines.append(f"  - {sanitize_untrusted_text(fw.get('framework'), max_len=120)}: "
                         f"{fw.get('label')} ({fw.get('quote_prozent')} %)")
        lines.append('')

    lines.append('## Antworten aus dem Audit')
    gezeigt = 0
    for q in fragen:
        if gezeigt >= max_fragen:
            break
        gezeigt += 1
        ref = sanitize_untrusted_text(q.get('section_ref'), max_len=60)
        lines.append(
            f"### {gezeigt}. [{sanitize_untrusted_text(q.get('framework'), max_len=60)}"
            f"{' ' + ref if ref else ''}] "
            f"{sanitize_untrusted_text(q.get('frage'), max_len=500)}")
        lines.append(f"  Antwort: {sanitize_untrusted_text(q.get('antwort'), max_len=1500) or '(offen)'}")
        bew = sanitize_untrusted_text(q.get('erfuellung') or q.get('bewertung'), max_len=60)
        lines.append(f"  Erfüllung: {bew or '(nicht bewertet)'}")
        if q.get('kommentar'):
            lines.append(f"  Anmerkung: {sanitize_untrusted_text(q.get('kommentar'), max_len=600)}")
    if len(fragen) > gezeigt:
        lines.append(f"… und {len(fragen) - gezeigt} weitere Fragen (gekürzt).")
    lines.append('')

    lines.append('## Antwortformat')
    lines.append('Antworte ausschließlich mit diesem JSON, ohne Rahmentext:')
    lines.append('```json')
    lines.append(json.dumps({
        'gesamtbewertung': 'string — ein Satz zum Gesamtbild des Audits',
        'zusammenfassung': 'string — 5–8 Sätze für die Leitung, ohne Fachjargon',
        'framework_bewertungen': [{
            'framework': 'string',
            'bewertung': 'string — 2–4 Sätze Einordnung',
            'staerken': ['string'],
            'luecken': ['string'],
        }],
        'handlungsempfehlungen': [{
            'massnahme': 'string',
            'begruendung': 'string — mit Bezug zur Fundstelle, wenn vorhanden',
            'prioritaet': 'hoch | mittel | niedrig',
            'aufwand': 'hoch | mittel | niedrig',
        }],
        'fazit': 'string — 3–4 Sätze',
    }, ensure_ascii=False, indent=2))
    lines.append('```')
    lines.append('')
    lines.append('Regeln:')
    lines.append('- Keine erfundenen Nachweise, Normstellen oder Zahlen. Nur was in den '
                 'Antworten steht.')
    lines.append('- Offene Fragen als „nicht erhoben" benennen, nicht als Mangel.')
    lines.append('- Die berechnete Stufe nicht verändern; der Bericht muss zur '
                 'Wasserstandsmeldung passen.')
    lines.append('- Deutsch, sachlich, ohne Werbesprache.')
    return '\n'.join(lines)


def parse_bericht_response(text: str) -> dict[str, Any]:
    """KI-Antwort zum Auditbericht parsen und auf das Zielschema normalisieren.

    Raises:
        ValueError: wenn kein JSON-Objekt gefunden wurde oder Pflichtfelder fehlen.
    """
    data = _json_objekt(text)

    out: dict[str, Any] = {
        'gesamtbewertung': str(data.get('gesamtbewertung') or '').strip(),
        'zusammenfassung': str(data.get('zusammenfassung') or '').strip(),
        'fazit': str(data.get('fazit') or '').strip(),
        'framework_bewertungen': [],
        'handlungsempfehlungen': [],
    }
    for fw in data.get('framework_bewertungen') or []:
        if not isinstance(fw, dict):
            continue
        out['framework_bewertungen'].append({
            'framework': str(fw.get('framework') or '').strip(),
            'bewertung': str(fw.get('bewertung') or '').strip(),
            'staerken': [str(x).strip() for x in (fw.get('staerken') or []) if str(x).strip()],
            'luecken': [str(x).strip() for x in (fw.get('luecken') or []) if str(x).strip()],
        })
    for m in data.get('handlungsempfehlungen') or []:
        if isinstance(m, str):   # tolerant: manche Antworten liefern nur Strings
            out['handlungsempfehlungen'].append({'massnahme': m.strip(), 'begruendung': '',
                                                 'prioritaet': '', 'aufwand': ''})
            continue
        if not isinstance(m, dict):
            continue
        out['handlungsempfehlungen'].append({
            'massnahme': str(m.get('massnahme') or '').strip(),
            'begruendung': str(m.get('begruendung') or '').strip(),
            'prioritaet': str(m.get('prioritaet') or '').strip().lower(),
            'aufwand': str(m.get('aufwand') or '').strip().lower(),
        })

    fehlend = [f for f in ('gesamtbewertung', 'zusammenfassung', 'fazit') if not out[f]]
    if fehlend:
        raise ValueError(f"Pflichtfelder fehlen oder sind leer: {', '.join(fehlend)}")
    return out
