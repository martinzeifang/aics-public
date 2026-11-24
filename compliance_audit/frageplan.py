"""Empfehlung, wie viele Fragen eine Audit-Frage braucht (#2133).

Der Compliance-Audit war an die Norm gebunden („Wie weit ist das Unternehmen mit
Norm X?"). Jetzt lässt sich eine **frei formulierte Audit-Frage** stellen
(„Unterliegt Software XY der CRA?", „Ist diese Auslagerung laut DORA wesentlich?")
und die passenden Normen auswählen. Bevor Fragen generiert werden, schlägt der
Assistent vor, **wie viele** Fragen zur Beantwortung nötig sind und wie sie sich
auf die gewählten Normen verteilen.

Das ist eine **Empfehlung**, keine Entscheidung: Der Mensch bestätigt oder ändert
die Zahl, dann läuft die bestehende Fragen-Generierung damit (Linie aus #1773).
Die KI vergibt hier keine Compliance-Stufe — die bleibt gerechnet
(:mod:`compliance_audit.status`).
"""

from __future__ import annotations

import json
from typing import Any

from security_utils import add_untrusted_block, sanitize_untrusted_text

#: Grenzen für eine brauchbare Empfehlung. Eine Audit-Frage, die 200 Fragen
#: braucht, ist keine Audit-Frage mehr; 0 Fragen beantwortet nichts.
MIN_FRAGEN = 1
MAX_FRAGEN = 60
MAX_PRO_FRAMEWORK = 40

SYSTEM_PROMPT = (
    'Du bist ein erfahrener Compliance-Auditor. Du planst einen zielgerichteten '
    'Fragenkatalog für eine konkrete Audit-Frage. Du empfiehlst, wie viele '
    'Interviewfragen nötig sind, um die Frage am Ende begründet zu beantworten, '
    'und wie sie sich auf die gewählten Normen verteilen. Du beantwortest die '
    'Audit-Frage NICHT und bewertest nichts. Antworte ausschließlich mit dem '
    'geforderten JSON.'
)

#: Erwartete Antwortfelder (auch Referenz für den Parser).
ANTWORT_FELDER: tuple[str, ...] = ('gesamt', 'verteilung', 'begruendung')


def build_empfehlung_prompt(projekt: dict[str, Any],
                            section_info: list[dict[str, Any]]) -> str:
    """Prompt für die Fragenzahl-Empfehlung.

    Args:
        projekt: Audit-Projekt (``name``, ``unternehmen``, ``audit_frage``,
            ``frameworks``, ``pruefungsfokus``).
        section_info: je gewähltem Framework ``{framework, count, titel: [...]}``
            — damit die KI weiß, welches Normmaterial überhaupt vorliegt.
    """
    frameworks = [str(f) for f in (projekt.get('frameworks') or [])]
    lines: list[str] = [SYSTEM_PROMPT, '']

    lines.append('## Auftrag')
    lines.append(
        'Empfiehl, wie viele Interviewfragen nötig sind, um die unten genannte '
        'Audit-Frage mit Belegen aus den gewählten Normen begründet zu '
        'beantworten. Nenne eine Gesamtzahl und verteile sie auf die Normen. '
        'Lieber wenige, gezielte Fragen als viele allgemeine.')
    lines.append('')

    lines.append('## Audit-Frage (das Ziel)')
    add_untrusted_block(lines, 'Audit-Frage',
                        sanitize_untrusted_text(projekt.get('audit_frage'), max_len=1000),
                        max_len=1000)
    lines.append('')

    lines.append('## Rahmen')
    add_untrusted_block(lines, 'Unternehmen',
                        sanitize_untrusted_text(projekt.get('unternehmen'), max_len=200),
                        max_len=200)
    if projekt.get('pruefungsfokus'):
        add_untrusted_block(lines, 'Prüfungsfokus',
                            sanitize_untrusted_text(projekt.get('pruefungsfokus'), max_len=2000),
                            max_len=2000)
    lines.append('')

    lines.append('## Gewählte Normen und vorhandenes Material')
    info_nach_fw = {str(s.get('framework')): s for s in (section_info or [])}
    for fw in frameworks:
        info = info_nach_fw.get(fw) or {}
        cnt = int(info.get('count') or 0)
        titel = [sanitize_untrusted_text(t, max_len=120)
                 for t in (info.get('titel') or [])][:6]
        zeile = f"- {sanitize_untrusted_text(fw, max_len=120)}: {cnt} eingelesene Abschnitte"
        if not cnt:
            zeile += ' (keine Normtexte eingelesen — Fachwissen nutzen)'
        lines.append(zeile)
        for t in titel:
            lines.append(f"    · {t}")
    lines.append('')

    lines.append('## Antwortformat')
    lines.append('Antworte ausschließlich mit diesem JSON, ohne Rahmentext:')
    lines.append('```json')
    lines.append(json.dumps({
        'gesamt': 'ganze Zahl — empfohlene Gesamtzahl der Fragen',
        'verteilung': [{
            'framework': 'string — exakt einer der gewählten Normnamen',
            'anzahl': 'ganze Zahl — Fragen für diese Norm',
            'begruendung': 'string — ein Satz, warum diese Zahl',
        }],
        'begruendung': 'string — 2–3 Sätze: warum diese Gesamtzahl die '
                       'Audit-Frage trägt, ohne mehr zu erheben als nötig',
    }, ensure_ascii=False, indent=2))
    lines.append('```')
    lines.append('')
    lines.append('Regeln:')
    lines.append(f"- framework: ausschließlich aus dieser Liste: {', '.join(frameworks) or '(keine)'}")
    lines.append('- Die Summe der Einzelzahlen muss der Gesamtzahl entsprechen.')
    lines.append('- Beantworte oder bewerte die Audit-Frage nicht — plane nur den Katalog.')
    lines.append('- Deutsch, sachlich, ohne Werbesprache.')
    return '\n'.join(lines)


def _json_objekt(text: str) -> dict[str, Any]:
    """JSON-Objekt aus einer KI-Antwort holen — tolerant gegen Rahmen/Beitext."""
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


def parse_empfehlung_response(text: str, frameworks: list[str]) -> dict[str, Any]:
    """KI-Antwort zur Fragenzahl-Empfehlung parsen und absichern.

    Die KI schlägt vor; dieser Parser erzwingt die harten Regeln, damit aus einem
    Vorschlag keine stillschweigend falsche Vorgabe wird:

    * Nur **gewählte** Frameworks zählen (ein erfundenes wird verworfen).
    * Jede Zahl wird auf ``[0, MAX_PRO_FRAMEWORK]`` begrenzt.
    * Die **Gesamtzahl ist die Summe der Verteilung** — so kann die Summe nie von
      der Zahl abweichen, mit der dann generiert wird. Fehlt die Verteilung,
      gilt die genannte Gesamtzahl, gleichmäßig auf die Normen verteilt.

    Raises:
        ValueError: wenn kein JSON-Objekt gefunden wurde.
    """
    data = _json_objekt(text)
    erlaubt = [str(f) for f in (frameworks or [])]

    verteilung: list[dict[str, Any]] = []
    gesehen: set[str] = set()
    for v in data.get('verteilung') or []:
        if not isinstance(v, dict):
            continue
        fw = str(v.get('framework') or '').strip()
        if fw not in erlaubt or fw in gesehen:
            continue  # erfundene oder doppelte Norm verwerfen
        gesehen.add(fw)
        try:
            anzahl = int(v.get('anzahl') or 0)
        except (TypeError, ValueError):
            anzahl = 0
        anzahl = max(0, min(anzahl, MAX_PRO_FRAMEWORK))
        verteilung.append({
            'framework': fw,
            'anzahl': anzahl,
            'begruendung': str(v.get('begruendung') or '').strip(),
        })

    # Fehlende Frameworks aus der Verteilung ergänzen (0), damit die Oberfläche
    # jede gewählte Norm zeigt — der Auditor sieht sofort, was bei 0 steht.
    for fw in erlaubt:
        if fw not in gesehen:
            verteilung.append({'framework': fw, 'anzahl': 0, 'begruendung': ''})

    summe = sum(v['anzahl'] for v in verteilung)
    if summe <= 0:
        # Keine brauchbare Verteilung — genannte Gesamtzahl gleichmäßig streuen.
        try:
            gesamt = int(data.get('gesamt') or 0)
        except (TypeError, ValueError):
            gesamt = 0
        gesamt = max(MIN_FRAGEN, min(gesamt or len(erlaubt) * 5, MAX_FRAGEN))
        if erlaubt:
            je, rest = divmod(gesamt, len(erlaubt))
            for i, v in enumerate(verteilung):
                v['anzahl'] = je + (1 if i < rest else 0)
        summe = sum(v['anzahl'] for v in verteilung)

    # Gesamt = Summe, auf MAX_FRAGEN gedeckelt (dann anteilig kürzen).
    if summe > MAX_FRAGEN and summe > 0:
        faktor = MAX_FRAGEN / summe
        for v in verteilung:
            v['anzahl'] = int(v['anzahl'] * faktor)
        summe = sum(v['anzahl'] for v in verteilung)

    return {
        'gesamt': summe,
        'verteilung': verteilung,
        'begruendung': str(data.get('begruendung') or '').strip(),
    }
