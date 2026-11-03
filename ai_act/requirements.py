"""Minimal AI Act readiness requirements dataset.

We intentionally store short titles + hints + a reference URL, not long legal text.
"""

from __future__ import annotations

from typing import Any


BEWERTUNG_SKALA: dict[int, dict[str, Any]] = {
    0: {"label": "Nicht bewertet", "farbe": "#9e9e9e", "reife_pct": 0},
    1: {"label": "Nicht vorhanden", "farbe": "#c62828", "reife_pct": 0},
    2: {"label": "In Planung", "farbe": "#e65100", "reife_pct": 25},
    3: {"label": "Teilweise umgesetzt", "farbe": "#f57f17", "reife_pct": 50},
    4: {"label": "Überwiegend umgesetzt", "farbe": "#2e7d32", "reife_pct": 75},
    5: {"label": "Vollständig umgesetzt", "farbe": "#1b5e20", "reife_pct": 100},
}


KAPITEL: list[str] = ["HR", "GOV", "DATA", "OPS"]


# AI Act main source (official text)
AI_ACT_REF = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689"


AI_ACT_REQUIREMENTS: list[dict[str, Any]] = [
    {
        "id": "AIA-HR-01",
        "kapitel": "HR",
        "titel": "Risikomanagement-System",
        "beschreibung": "Etabliere und betreibe ein dokumentiertes Risikomanagement-System fuer das AI-System ueber den gesamten Lebenszyklus.",
        "hinweise": "Risk register, Residual risk, regelmaessige Reviews; Verknuepfung zu Threat Modeling/TARA.",
        "guidance": "Definiere Rollen, Risikokriterien und Review-Zyklen. Dokumentiere Entscheidungen und Residual-Risiken. Verknuepfe Findings (Sicherheitsluecken, Bias, Incidents) mit Massnahmen.",
        "evidence": ["Risk register", "Threat model / TARA", "Review-Protokolle", "Change/Release-Records"],
        "rubric": {"0": "nicht bewertet", "3": "Prozess vorhanden, aber lueckenhafte Nachweise", "5": "vollstaendig etabliert, regelmaessig betrieben, auditierbar"},
        "ref": AI_ACT_REF,
        "gewichtung": 3,
    },
    {
        "id": "AIA-HR-02",
        "kapitel": "HR",
        "titel": "Daten-Governance und Datenqualität",
        "beschreibung": "Stelle sicher, dass Daten (Training/Validierung/Test) geeignet, dokumentiert und kontrolliert verwaltet sind (Qualitaet, Bias, Repraesentativitaet).",
        "hinweise": "Datasheets, Data lineage, Bias tests, Zugriffskontrollen.",
        "guidance": "Dokumentiere Datenquellen, Sampling, Labeling, Cleaning und Governance (Zugriff, Retention). Fuehre Bias-/Fairness-Checks und Datenqualitaets-KPIs ein.",
        "evidence": ["Datasheet/Datensatz-Doku", "Data lineage", "Bias/Fairness Tests", "Access control policy"],
        "rubric": {"0": "nicht bewertet", "3": "Basis-Doku/Checks vorhanden", "5": "vollstaendige Governance + regelmaessige Tests + nachvollziehbare Lineage"},
        "ref": AI_ACT_REF,
        "gewichtung": 3,
    },
    {
        "id": "AIA-HR-03",
        "kapitel": "HR",
        "titel": "Technische Dokumentation",
        "beschreibung": "Erstelle und pflege strukturierte technische Dokumentation zur Konformitaetsbewertung.",
        "hinweise": "Architektur, intended purpose, limitations, evaluation, cybersecurity measures.",
        "guidance": "Halte Architektur, Datenfluesse, Modell-/Systemgrenzen, Evaluationsmethoden, Security Controls und Betriebsannahmen fest. Versioniere die Doku.",
        "evidence": ["Architektur-Doku", "Data-flow Diagramme", "Evaluation/Test Reports", "Security-by-design Doku"],
        "rubric": {"0": "nicht bewertet", "3": "Doku vorhanden, aber unvollstaendig/inkonsistent", "5": "vollstaendig, versioniert, auditierbar"},
        "ref": AI_ACT_REF,
        "gewichtung": 3,
    },
    {
        "id": "AIA-HR-04",
        "kapitel": "HR",
        "titel": "Logging / Record-Keeping",
        "beschreibung": "Implementiere Logging/Record-Keeping zur Nachvollziehbarkeit (Auditability) und fuer Post-Market/Incident Prozesse.",
        "hinweise": "Audit trails, retention, Zugriff; Security logging.",
        "guidance": "Definiere, welche Events geloggt werden (Inputs/Outputs, Entscheidungen, Systemzustand). Regle Retention, Zugriff, Integritaet und Datenschutz.",
        "evidence": ["Logging-Konzept", "Beispiel-Logs", "Retention policy", "Access controls"],
        "rubric": {"0": "nicht bewertet", "3": "Logging vorhanden, aber ohne klare Governance", "5": "auditierbar, abgesichert, mit Retention/Access"},
        "ref": AI_ACT_REF,
        "gewichtung": 2,
    },
    {
        "id": "AIA-HR-05",
        "kapitel": "HR",
        "titel": "Transparenz und Nutzerinformationen",
        "beschreibung": "Stelle Deployern/Users klare Informationen fuer korrekte Nutzung bereit (Zweck, Grenzen, Risiken, Performance).",
        "hinweise": "User documentation, model card, limitations, performance metrics.",
        "guidance": "Erstelle User-Dokumentation/Model Card mit intended purpose, limitations, Monitoring-Hinweisen und sicheren Konfigurationen.",
        "evidence": ["User documentation", "Model card", "Known limitations", "Performance metrics"],
        "rubric": {"0": "nicht bewertet", "3": "Basis-Doku vorhanden", "5": "vollstaendige, zielgruppengerechte Doku inkl. Grenzen/Monitoring"},
        "ref": AI_ACT_REF,
        "gewichtung": 2,
    },
    {
        "id": "AIA-HR-06",
        "kapitel": "HR",
        "titel": "Menschliche Aufsicht",
        "beschreibung": "Implementiere Human-Oversight Massnahmen (rollen, training, escalation, override/stop) passend zum Risiko.",
        "hinweise": "Override/Stop, monitoring, role definitions.",
        "guidance": "Definiere Rollen und Verantwortlichkeiten. Stelle Override/Stop bereit, dokumentiere Entscheidungsprozesse und Eskalationswege.",
        "evidence": ["Rollen-/Betriebskonzept", "Override/Stop Mechanismen", "Training/Runbooks"],
        "rubric": {"0": "nicht bewertet", "3": "Oversight definiert, aber nicht durchgaengig umgesetzt", "5": "klar definiert, getestet, betrieben"},
        "ref": AI_ACT_REF,
        "gewichtung": 3,
    },
    {
        "id": "AIA-HR-07",
        "kapitel": "HR",
        "titel": "Genauigkeit, Robustheit und Cybersicherheit",
        "beschreibung": "Definiere und erfuelle messbare Anforderungen an Genauigkeit, Robustheit und Cybersicherheit (Security-by-design).",
        "hinweise": "Adversarial testing, secure deployment, SBOM, vuln scans.",
        "guidance": "Lege Metriken/Schwellenwerte fest, implementiere Security Controls, fuehre SBOM+Vuln-Scanning, SAST und Robustheitstests durch. Dokumentiere Hardening.",
        "evidence": ["Security controls", "SBOM", "Vuln scan results", "Robustness/adversarial tests"],
        "rubric": {"0": "nicht bewertet", "3": "einige Controls/Metriken vorhanden", "5": "vollstaendige Controls + Tests + Nachweise"},
        "ref": AI_ACT_REF,
        "gewichtung": 3,
    },
    {
        "id": "AIA-GOV-01",
        "kapitel": "GOV",
        "titel": "Quality Management System (QMS)",
        "beschreibung": "Etabliere ein QMS fuer AI Act Konformitaet (rollen, prozesse, audits, change control).",
        "hinweise": "Policies, Verantwortlichkeiten, Trainings, interne Audits, Change Control.",
        "guidance": "Lege Policies/Procedures fest (Risk, Data, Security, Incident, Change). Fuehre interne Audits und Trainings durch.",
        "evidence": ["Policies/Procedures", "Audit evidence", "Training records", "Change control"],
        "rubric": {"0": "nicht bewertet", "3": "QMS teilweise dokumentiert", "5": "QMS etabliert, auditierbar, regelmaessig betrieben"},
        "ref": AI_ACT_REF,
        "gewichtung": 3,
    },
    {
        "id": "AIA-GOV-02",
        "kapitel": "GOV",
        "titel": "Change Management / Configuration Management",
        "beschreibung": "Kontrollierte Aenderungen ueber den Lebenszyklus (inkl. Modell-/Daten-Versionierung).",
        "hinweise": "Versionierung, Releases, approvals, rollback, traceability.",
        "guidance": "Versioniere Artefakte (Code, Modell, Daten, Doku). Definiere Release- und Rollback-Prozess, inkl. Approval.",
        "evidence": ["Release notes", "Versioning strategy", "Approval records", "Rollback plan"],
        "rubric": {"0": "nicht bewertet", "3": "teilweise versioniert/ohne approvals", "5": "vollstaendige Traceability und kontrollierte Releases"},
        "ref": AI_ACT_REF,
        "gewichtung": 2,
    },
    {
        "id": "AIA-DATA-01",
        "kapitel": "DATA",
        "titel": "Datasets: Dokumentation und Lineage",
        "beschreibung": "Nachvollziehbare Dokumentation von Trainings-/Validierungsdaten und deren Herkunft.",
        "hinweise": "Datasheets, lineage, licensing, retention, access controls.",
        "guidance": "Dokumentiere Herkunft, Lizenzierung, Transformationen, Speicherung und Zugriff. Halte Lineage technisch nachvollziehbar.",
        "evidence": ["Dataset docs", "Lineage logs", "Licensing notes", "Retention policy"],
        "rubric": {"0": "nicht bewertet", "3": "Doku vorhanden, Lineage teilw.", "5": "vollstaendige Lineage und Governance"},
        "ref": AI_ACT_REF,
        "gewichtung": 3,
    },
    {
        "id": "AIA-DATA-02",
        "kapitel": "DATA",
        "titel": "Bias-/Fairness-Pruefungen",
        "beschreibung": "Geeignete Tests/Analysen zur Erkennung und Reduktion von Bias.",
        "hinweise": "Testplaene, metrics, sampling, human review.",
        "guidance": "Definiere Fairness-Metriken, fuehre Tests regelmaessig durch, dokumentiere Findings und Remediation.",
        "evidence": ["Test plan", "Fairness metrics", "Findings/Remediation", "Sampling rationale"],
        "rubric": {"0": "nicht bewertet", "3": "gelegentliche Tests", "5": "regelmaessige, dokumentierte Tests mit Remediation"},
        "ref": AI_ACT_REF,
        "gewichtung": 2,
    },
    {
        "id": "AIA-HR-08",
        "kapitel": "OPS",
        "titel": "Post-Market Monitoring",
        "beschreibung": "Monitoring-Plan und Feedback-Loops nach Inverkehrbringen.",
        "hinweise": "Incident process, telemetry, KPIs, periodic reviews.",
        "guidance": "Definiere Monitoring-KPIs, Telemetrie und Feedbackkanäle. Plane regelmaessige Reviews und Verbesserungen.",
        "evidence": ["Monitoring plan", "KPIs/telemetry", "Review records"],
        "rubric": {"0": "nicht bewertet", "3": "Plan vorhanden", "5": "Plan betrieben + Nachweise"},
        "ref": AI_ACT_REF,
        "gewichtung": 2,
    },
    {
        "id": "AIA-HR-09",
        "kapitel": "OPS",
        "titel": "Incident Management / Meldungen",
        "beschreibung": "Prozess für Incident handling und regulatorische Meldungen.",
        "hinweise": "Runbooks, severity thresholds, communication templates.",
        "guidance": "Definiere Incident-Klassen, Response-Prozess, Verantwortlichkeiten und Kommunikations-/Melde-Templates.",
        "evidence": ["Incident response plan", "Runbooks", "Severity matrix", "Communication templates"],
        "rubric": {"0": "nicht bewertet", "3": "Prozess dokumentiert", "5": "geuebt, betrieben, nachvollziehbar"},
        "ref": AI_ACT_REF,
        "gewichtung": 2,
    },
]


def berechne_reifegrad(
    bewertungen: dict[str, int],
    anforderungen: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Berechnet einen gewichteten Reifegrad aus {req_id: bewertung 0..5}.

    Nicht bewertete Anforderungen (0) werden nicht eingerechnet.
    """
    if anforderungen is None:
        anforderungen = AI_ACT_REQUIREMENTS

    by_kapitel: dict[str, list[float]] = {k: [] for k in KAPITEL}
    total_pct: list[float] = []

    for req in anforderungen:
        rid = str(req.get("id", ""))
        if not rid:
            continue
        gewichtung = int(req.get("gewichtung", 1) or 1)
        bew = int(bewertungen.get(rid, 0) or 0)
        if bew == 0:
            continue
        reife_pct = float(BEWERTUNG_SKALA.get(bew, BEWERTUNG_SKALA[0]).get("reife_pct", 0))
        kap = str(req.get("kapitel", "")) or ""
        by_kapitel.setdefault(kap, []).extend([reife_pct] * max(1, gewichtung))
        total_pct.extend([reife_pct] * max(1, gewichtung))

    gesamt_pct = (sum(total_pct) / len(total_pct)) if total_pct else 0.0
    kapitel_pct = {k: ((sum(vals) / len(vals)) if vals else 0.0) for k, vals in by_kapitel.items()}

    if gesamt_pct >= 70:
        ampel = "gruen"
    elif gesamt_pct >= 40:
        ampel = "orange"
    else:
        ampel = "rot"

    bewertete = sum(1 for _rid, val in bewertungen.items() if int(val or 0) > 0)
    return {
        "gesamt_pct": round(gesamt_pct, 1),
        "kapitel_pct": {k: round(v, 1) for k, v in kapitel_pct.items()},
        "ampel": ampel,
        "bewertete_count": bewertete,
        "gesamt_count": len(anforderungen),
    }
