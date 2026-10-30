"""#1577 — Framework einer Risikobewertung nachträglich wechseln.

Die Bewertungsfelder sind framework-spezifisch (STRIDE: Kategorie/Likelihood/Impact,
EU-AI-Act: Lebenszyklus/Kategorie, DSGVO-DSFA …) und damit **nicht übertragbar**.
Ein Wechsel setzt daher Score/Level/Detail aller Risiken zurück, archiviert die
bisherige Bewertung nachvollziehbar in ``felder._vorher`` und markiert jedes Risiko
als „⚠️ Neubewertung erforderlich" (gleicher Marker wie beim Issue-Sync, #1526 —
die Massenbewertung wählt diese Risiken automatisch vor).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from risikobewertung.frameworks import FRAMEWORK_IDS, FRAMEWORK_LABELS

MARKER = 'Neubewertung erforderlich'


def _label(fw: str) -> str:
    return FRAMEWORK_LABELS.get(fw, fw)


def neubewertung_markieren(risk: dict[str, Any], alt_fw: str, neu_fw: str,
                           datum: str | None = None) -> dict[str, Any]:
    """Ein Risiko auf das neue Framework umstellen (rein, ohne DB)."""
    datum = datum or date.today().isoformat()
    felder = risk.get('felder') if isinstance(risk.get('felder'), dict) else {}
    # Interne Meta-Felder (z. B. _source='req-gap') bleiben erhalten.
    neu_felder = {k: v for k, v in felder.items() if str(k).startswith('_') and k != '_vorher'}
    vorher = {
        'framework': alt_fw,
        'felder': {k: v for k, v in felder.items() if not str(k).startswith('_')},
        'risikowert': risk.get('risikowert'),
        'risiko_label': risk.get('risiko_label', ''),
        'detail_text': risk.get('detail_text', ''),
        'gewechselt_am': datum,
    }
    neu_felder['_vorher'] = vorher
    bisher = (f"{risk.get('risiko_label')} ({risk.get('risikowert')})"
              if risk.get('risiko_label') else 'unbewertet')
    hinweis = (f"⚠️ {MARKER} — Framework am {datum} von „{_label(alt_fw)}\" auf "
               f"„{_label(neu_fw)}\" geändert. Bisherige Bewertung: {bisher}.")
    alt_text = str(risk.get('bewertung_text') or '').strip()
    out = dict(risk)
    out.update({
        'framework': neu_fw,
        'felder': neu_felder,
        'risikowert': None,
        'risiko_label': '',
        'detail_text': '',
        'bewertung_text': f"{hinweis}\n\n{alt_text}" if alt_text else hinweis,
    })
    return out


def warnungen(projekt: dict[str, Any], alt_fw: str, neu_fw: str) -> list[str]:
    """Fachliche Hinweise zu Verknüpfungen, die ein bestimmtes Framework voraussetzen."""
    meta = projekt.get('meta') if isinstance(projekt.get('meta'), dict) else {}
    out: list[str] = []
    if alt_fw == 'EU-AI-Act' and neu_fw != 'EU-AI-Act' and meta.get('linked_aiact_projekt'):
        out.append(f"Verknüpft mit AI-Act-Projekt „{meta['linked_aiact_projekt']}\" (AIA-HR-01): "
                   "dort werden nur Bewertungen mit Bewertungsart EU-AI-Act anerkannt.")
    if alt_fw == 'DSGVO-DSFA' and neu_fw != 'DSGVO-DSFA':
        out.append('Bewertungsart DSGVO-DSFA gehört zu einer Datenschutz-Folgenabschätzung '
                   '(Art. 35 Abs. 7 c+d) — ein anderes Framework passt nicht mehr zur DSFA.')
    if meta.get('linked_cra_projekt'):
        out.append(f"Das Threat-Model des verknüpften CRA-Projekts „{meta['linked_cra_projekt']}\" "
                   'übernimmt das neue Framework (außer bei manuellem Override).')
    return out


def framework_wechseln(db_path: Path, projekt_name: str, neu_fw: str, *,
                       dry_run: bool = False) -> dict[str, Any]:
    """Framework des Projekts + aller Risiken wechseln. ``dry_run`` liefert nur die Vorschau."""
    from risikobewertung.db import load_projekt, load_risiken, save_projekt, save_risiko
    if neu_fw not in FRAMEWORK_IDS:
        raise ValueError(f'Ungültiges Framework: {neu_fw}')
    projekt = load_projekt(db_path, projekt_name)
    if not projekt:
        raise LookupError('Projekt nicht gefunden')
    alt_fw = projekt.get('framework') or 'STRIDE'
    risiken = load_risiken(db_path, projekt_name)
    result: dict[str, Any] = {
        'alt': alt_fw, 'neu': neu_fw, 'risiken': len(risiken),
        'bewertet': sum(1 for r in risiken if r.get('risiko_label')),
        'warnungen': warnungen(projekt, alt_fw, neu_fw), 'geaendert': False,
    }
    if alt_fw == neu_fw or dry_run:
        return result
    save_projekt(db_path, name=projekt_name, framework=neu_fw,
                 beschreibung=projekt.get('beschreibung', '') or '',
                 unternehmen=projekt.get('unternehmen', '') or '',
                 produkt=projekt.get('produkt', '') or '',
                 berater=projekt.get('berater', '') or '',
                 meta=projekt.get('meta') or {})
    datum = date.today().isoformat()
    for r in risiken:
        neu = neubewertung_markieren(r, alt_fw, neu_fw, datum)
        neu['projekt_name'] = projekt_name
        save_risiko(db_path, neu)
    result['geaendert'] = True
    return result
