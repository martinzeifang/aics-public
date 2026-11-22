"""AI Act — Statische Hilfe zum Post-Market-Monitoring (Story 6 / #1024).

Reine, statische Nachschlage-Daten für den PMM-Wizard (Art. 72/73).
KEINE LLM-Anbindung, KEINE Netzaufrufe, KEINE erfundenen Kontaktdaten
(Telefon/URLs): nur generische, sichere Angaben.
"""
from __future__ import annotations

from typing import Any

PMM_HELP: dict[str, Any] = {
    # Generischer, sicherer Hinweis — KEINE erfundenen URLs/Telefonnummern.
    'behoerde': (
        'In Deutschland ist die Bundesnetzagentur (BNetzA) als nationale '
        'Marktüberwachungsbehörde für den EU AI Act vorgesehen (Sitz Bonn). '
        'Serious Incidents nach Art. 73 sind an die zuständige '
        'Marktüberwachungsbehörde am Aufstellungsort zu melden. Konkrete '
        'Meldewege/Kontaktdaten bitte den offiziellen, aktuellen Veröffentlichungen '
        'der Behörde entnehmen.'
    ),
    'monitoring_plan_snippets': [
        'Accuracy-Drift (Genauigkeit über die Zeit gegen Baseline)',
        'Latency (Antwortzeiten / Inferenz-Latenz)',
        'Error-Rate (Fehler-/Ausfallquote im Betrieb)',
        'User-Feedback (Beschwerden, Korrekturen, Zufriedenheits-Signale)',
    ],
    'incident_threshold_examples': [
        'Genauigkeitsabfall > 5 % im 7-Tage-Rolling-Window',
        'Error-Rate > 2 % über 24 Stunden',
        'Signifikanter Anstieg negativer User-Feedback-Meldungen',
        'Detektierter Daten-/Konzept-Drift oberhalb der Alarm-Schwelle',
    ],
    'eu_articles': [
        'Art. 72 — Post-Market-Monitoring-Plan (kontinuierliche Überwachung)',
        'Art. 73 — Serious-Incident-Reporting (Meldefrist 15 Tage)',
    ],
    'serious_incident_reporting_sla_default': '15 Tage',
}


def get_pmm_help() -> dict[str, Any]:
    """Gibt die statischen PMM-Hilfedaten zurück."""
    return PMM_HELP
