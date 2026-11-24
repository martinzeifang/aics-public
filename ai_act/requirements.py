"""Minimal AI Act readiness requirements dataset.

We intentionally store short titles + hints + a reference URL, not long legal text.
"""

from __future__ import annotations

from typing import Any


BEWERTUNG_SKALA: dict[int, dict[str, Any]] = {
    0: {"label": "Nicht bewertet", "label_en": "Not assessed", "farbe": "#9e9e9e", "reife_pct": 0},
    1: {"label": "Nicht vorhanden", "label_en": "Not in place", "farbe": "#c62828", "reife_pct": 0},
    2: {"label": "In Planung", "label_en": "Planned", "farbe": "#e65100", "reife_pct": 25},
    3: {"label": "Teilweise umgesetzt", "label_en": "Partly implemented", "farbe": "#f57f17", "reife_pct": 50},
    4: {"label": "Überwiegend umgesetzt", "label_en": "Largely implemented", "farbe": "#2e7d32", "reife_pct": 75},
    5: {"label": "Vollständig umgesetzt", "label_en": "Fully implemented", "farbe": "#1b5e20", "reife_pct": 100},
}


KAPITEL: list[str] = ["HR", "GOV", "DATA", "OPS"]


#: Quelle des amtlichen Textes — eine **Fundstelle für den Leser**, nicht die
#: Rechtsgrundlage einer Anforderung.
#:
#: #2060: Alle 13 Anforderungen trugen dies als ``ref``. Im Konformitätsbericht
#: stand an der Stelle der Rechtsgrundlage damit eine Internetadresse; für einen
#: Prüfer ist „CELEX:32024R1689" keine Fundstelle, sondern der Hinweis, dass er
#: selbst suchen soll. CRA, NIS2 und DSGVO nennen je Anforderung Artikel und
#: Absatz — der AI Act war die strukturelle Ausnahme, obwohl die Zuordnungen
#: anderswo im Modul korrekt vorlagen.
#:
#: Die Artikelangaben unten sind gegen ``data/ai_act_resources/32024R1689_DEU.pdf``
#: gelesen (09.11.2026), nicht aus der Erinnerung — die Lehre aus #1763/#1792.
AI_ACT_QUELLE = "https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32024R1689"

#: Alias für Bestandsaufrufer (die Konstante war öffentlich).
AI_ACT_REF = AI_ACT_QUELLE


AI_ACT_REQUIREMENTS: list[dict[str, Any]] = [
    {
        "id": "AIA-HR-01",
        "kapitel": "HR",
        "titel": "Risikomanagement-System",
        "titel_en": "Risk management system",
        "beschreibung": "Etabliere und betreibe ein dokumentiertes Risikomanagement-System fuer das AI-System ueber den gesamten Lebenszyklus.",
        "beschreibung_en": "Establish and operate a documented risk management system for the AI system across its entire lifecycle.",
        "hinweise": "Risk register, Residual risk, regelmaessige Reviews; Verknuepfung zu Threat Modeling/TARA.",
        "hinweise_en": "Risk register, residual risk, regular reviews; link to threat modeling/TARA.",
        "guidance": "Definiere Rollen, Risikokriterien und Review-Zyklen. Dokumentiere Entscheidungen und Residual-Risiken. Verknuepfe Findings (Sicherheitsluecken, Bias, Incidents) mit Massnahmen.",
        "guidance_en": "Define roles, risk criteria and review cycles. Document decisions and residual risks. Link findings (security vulnerabilities, bias, incidents) to measures.",
        "evidence": ["Risk register", "Threat model / TARA", "Review-Protokolle", "Change/Release-Records"],
        "evidence_en": ["Risk register", "Threat model / TARA", "Review records", "Change/Release-Records"],
        "rubric": {"0": "nicht bewertet", "3": "Prozess vorhanden, aber lueckenhafte Nachweise", "5": "vollstaendig etabliert, regelmaessig betrieben, auditierbar"},
        "rubric_en": {"0": "not assessed", "3": "process in place, but gaps in the evidence", "5": "fully established, operated regularly, auditable"},
        "ref": "Verordnung (EU) 2024/1689, Art. 9 (Risikomanagementsystem)",
        "gewichtung": 3,
    },
    {
        "id": "AIA-HR-02",
        "kapitel": "HR",
        "titel": "Daten-Governance und Datenqualität",
        "titel_en": "Data governance and data quality",
        "beschreibung": "Stelle sicher, dass Daten (Training/Validierung/Test) geeignet, dokumentiert und kontrolliert verwaltet sind (Qualitaet, Bias, Repraesentativitaet).",
        "beschreibung_en": "Ensure that the data (training/validation/testing) are appropriate, documented and managed in a controlled manner (quality, bias, representativeness).",
        "hinweise": "Datasheets, Data lineage, Bias tests, Zugriffskontrollen.",
        "hinweise_en": "Datasheets, data lineage, bias tests, access controls.",
        "guidance": "Dokumentiere Datenquellen, Sampling, Labeling, Cleaning und Governance (Zugriff, Retention). Fuehre Bias-/Fairness-Checks und Datenqualitaets-KPIs ein.",
        "guidance_en": "Document data sources, sampling, labeling, cleaning and governance (access, retention). Introduce bias/fairness checks and data quality KPIs.",
        "evidence": ["Datasheet/Datensatz-Doku", "Data lineage", "Bias/Fairness Tests", "Access control policy"],
        "evidence_en": ["Datasheet/data set documentation", "Data lineage", "Bias/fairness tests", "Access control policy"],
        "rubric": {"0": "nicht bewertet", "3": "Basis-Doku/Checks vorhanden", "5": "vollstaendige Governance + regelmaessige Tests + nachvollziehbare Lineage"},
        "rubric_en": {"0": "not assessed", "3": "basic documentation/checks in place", "5": "full governance + regular tests + traceable lineage"},
        "ref": "Verordnung (EU) 2024/1689, Art. 10 (Daten und Daten-Governance)",
        "gewichtung": 3,
    },
    {
        "id": "AIA-HR-03",
        "kapitel": "HR",
        "titel": "Technische Dokumentation",
        "titel_en": "Technical documentation",
        "beschreibung": "Erstelle und pflege strukturierte technische Dokumentation zur Konformitaetsbewertung.",
        "beschreibung_en": "Draw up and maintain structured technical documentation for the conformity assessment.",
        "hinweise": "Architektur, intended purpose, limitations, evaluation, cybersecurity measures.",
        "hinweise_en": "Architecture, intended purpose, limitations, evaluation, cybersecurity measures.",
        "guidance": "Halte Architektur, Datenfluesse, Modell-/Systemgrenzen, Evaluationsmethoden, Security Controls und Betriebsannahmen fest. Versioniere die Doku.",
        "guidance_en": "Record the architecture, data flows, model/system boundaries, evaluation methods, security controls and operating assumptions. Version the documentation.",
        "evidence": ["Architektur-Doku", "Data-flow Diagramme", "Evaluation/Test Reports", "Security-by-design Doku"],
        "evidence_en": ["Architecture documentation", "Data-flow diagrams", "Evaluation/test reports", "Security-by-design documentation"],
        "rubric": {"0": "nicht bewertet", "3": "Doku vorhanden, aber unvollstaendig/inkonsistent", "5": "vollstaendig, versioniert, auditierbar"},
        "rubric_en": {"0": "not assessed", "3": "documentation in place, but incomplete/inconsistent", "5": "complete, versioned, auditable"},
        "ref": ("Verordnung (EU) 2024/1689, Art. 11 i.V.m. Anhang IV "
                "(Technische Dokumentation)"),
        "gewichtung": 3,
    },
    {
        "id": "AIA-HR-04",
        "kapitel": "HR",
        "titel": "Logging / Record-Keeping",
        "titel_en": "Logging / record-keeping",
        "beschreibung": "Implementiere Logging/Record-Keeping zur Nachvollziehbarkeit (Auditability) und fuer Post-Market/Incident Prozesse.",
        "beschreibung_en": "Implement logging/record-keeping for traceability (auditability) and for post-market/incident processes.",
        "hinweise": "Audit trails, retention, Zugriff; Security logging.",
        "hinweise_en": "Audit trails, retention, access; security logging.",
        "guidance": "Definiere, welche Events geloggt werden (Inputs/Outputs, Entscheidungen, Systemzustand). Regle Retention, Zugriff, Integritaet und Datenschutz.",
        "guidance_en": "Define which events are logged (inputs/outputs, decisions, system state). Govern retention, access, integrity and data protection.",
        "evidence": ["Logging-Konzept", "Beispiel-Logs", "Retention policy", "Access controls"],
        "evidence_en": ["Logging concept", "Sample logs", "Retention policy", "Access controls"],
        "rubric": {"0": "nicht bewertet", "3": "Logging vorhanden, aber ohne klare Governance", "5": "auditierbar, abgesichert, mit Retention/Access"},
        "rubric_en": {"0": "not assessed", "3": "logging in place, but without clear governance", "5": "auditable, secured, with retention/access"},
        "ref": "Verordnung (EU) 2024/1689, Art. 12 (Aufzeichnungspflichten)",
        "gewichtung": 2,
    },
    {
        "id": "AIA-HR-05",
        "kapitel": "HR",
        "titel": "Transparenz und Nutzerinformationen",
        "titel_en": "Transparency and user information",
        "beschreibung": "Stelle Deployern/Users klare Informationen fuer korrekte Nutzung bereit (Zweck, Grenzen, Risiken, Performance).",
        "beschreibung_en": "Provide deployers/users with clear information for correct use (purpose, limitations, risks, performance).",
        "hinweise": "User documentation, model card, limitations, performance metrics.",
        "hinweise_en": "User documentation, model card, limitations, performance metrics.",
        "guidance": "Erstelle User-Dokumentation/Model Card mit intended purpose, limitations, Monitoring-Hinweisen und sicheren Konfigurationen.",
        "guidance_en": "Draw up user documentation/a model card with intended purpose, limitations, monitoring notes and secure configurations.",
        "evidence": ["User documentation", "Model card", "Known limitations", "Performance metrics"],
        "evidence_en": ["User documentation", "Model card", "Known limitations", "Performance metrics"],
        "rubric": {"0": "nicht bewertet", "3": "Basis-Doku vorhanden", "5": "vollstaendige, zielgruppengerechte Doku inkl. Grenzen/Monitoring"},
        "rubric_en": {"0": "not assessed", "3": "basic documentation in place", "5": "complete documentation tailored to the audience, including limitations/monitoring"},
        "ref": ("Verordnung (EU) 2024/1689, Art. 13 "
                "(Transparenz und Bereitstellung von Informationen für die Betreiber)"),
        "gewichtung": 2,
    },
    {
        "id": "AIA-HR-06",
        "kapitel": "HR",
        "titel": "Menschliche Aufsicht",
        "titel_en": "Human oversight",
        "beschreibung": "Implementiere Human-Oversight Massnahmen (rollen, training, escalation, override/stop) passend zum Risiko.",
        "beschreibung_en": "Implement human oversight measures (roles, training, escalation, override/stop) appropriate to the risk.",
        "hinweise": "Override/Stop, monitoring, role definitions.",
        "hinweise_en": "Override/stop, monitoring, role definitions.",
        "guidance": "Definiere Rollen und Verantwortlichkeiten. Stelle Override/Stop bereit, dokumentiere Entscheidungsprozesse und Eskalationswege.",
        "guidance_en": "Define roles and responsibilities. Provide override/stop, document decision processes and escalation paths.",
        "evidence": ["Rollen-/Betriebskonzept", "Override/Stop Mechanismen", "Training/Runbooks"],
        "evidence_en": ["Roles/operating concept", "Override/stop mechanisms", "Training/runbooks"],
        "rubric": {"0": "nicht bewertet", "3": "Oversight definiert, aber nicht durchgaengig umgesetzt", "5": "klar definiert, getestet, betrieben"},
        "rubric_en": {"0": "not assessed", "3": "oversight defined, but not implemented throughout", "5": "clearly defined, tested, operated"},
        "ref": "Verordnung (EU) 2024/1689, Art. 14 (Menschliche Aufsicht)",
        "gewichtung": 3,
    },
    {
        "id": "AIA-HR-07",
        "kapitel": "HR",
        "titel": "Genauigkeit, Robustheit und Cybersicherheit",
        "titel_en": "Accuracy, robustness and cybersecurity",
        "beschreibung": "Definiere und erfuelle messbare Anforderungen an Genauigkeit, Robustheit und Cybersicherheit (Security-by-design).",
        "beschreibung_en": "Define and meet measurable requirements for accuracy, robustness and cybersecurity (security-by-design).",
        "hinweise": "Adversarial testing, secure deployment, SBOM, vuln scans.",
        "hinweise_en": "Adversarial testing, secure deployment, SBOM, vuln scans.",
        "guidance": "Lege Metriken/Schwellenwerte fest, implementiere Security Controls, fuehre SBOM+Vuln-Scanning, SAST und Robustheitstests durch. Dokumentiere Hardening.",
        "guidance_en": "Set metrics/thresholds, implement security controls, carry out SBOM + vulnerability scanning, SAST and robustness tests. Document hardening.",
        "evidence": ["Security controls", "SBOM", "Vuln scan results", "Robustness/adversarial tests"],
        "evidence_en": ["Security controls", "SBOM", "Vuln scan results", "Robustness/adversarial tests"],
        "rubric": {"0": "nicht bewertet", "3": "einige Controls/Metriken vorhanden", "5": "vollstaendige Controls + Tests + Nachweise"},
        "rubric_en": {"0": "not assessed", "3": "some controls/metrics in place", "5": "complete controls + tests + evidence"},
        "ref": ("Verordnung (EU) 2024/1689, Art. 15 "
                "(Genauigkeit, Robustheit und Cybersicherheit)"),
        "gewichtung": 3,
    },
    {
        "id": "AIA-GOV-01",
        "kapitel": "GOV",
        "titel": "Quality Management System (QMS)",
        "titel_en": "Quality management system (QMS)",
        "beschreibung": "Etabliere ein QMS fuer AI Act Konformitaet (rollen, prozesse, audits, change control).",
        "beschreibung_en": "Establish a QMS for AI Act conformity (roles, processes, audits, change control).",
        "hinweise": "Policies, Verantwortlichkeiten, Trainings, interne Audits, Change Control.",
        "hinweise_en": "Policies, responsibilities, training, internal audits, change control.",
        "guidance": "Lege Policies/Procedures fest (Risk, Data, Security, Incident, Change). Fuehre interne Audits und Trainings durch.",
        "guidance_en": "Set policies/procedures (risk, data, security, incident, change). Carry out internal audits and training.",
        "evidence": ["Policies/Procedures", "Audit evidence", "Training records", "Change control"],
        "evidence_en": ["Policies/Procedures", "Audit evidence", "Training records", "Change control"],
        "rubric": {"0": "nicht bewertet", "3": "QMS teilweise dokumentiert", "5": "QMS etabliert, auditierbar, regelmaessig betrieben"},
        "rubric_en": {"0": "not assessed", "3": "QMS partly documented", "5": "QMS established, auditable, operated regularly"},
        "ref": "Verordnung (EU) 2024/1689, Art. 17 (Qualitätsmanagementsystem)",
        "gewichtung": 3,
    },
    {
        "id": "AIA-GOV-02",
        "kapitel": "GOV",
        "titel": "Change Management / Configuration Management",
        "titel_en": "Change management / configuration management",
        "beschreibung": "Kontrollierte Aenderungen ueber den Lebenszyklus (inkl. Modell-/Daten-Versionierung).",
        "beschreibung_en": "Controlled changes across the lifecycle (including model/data versioning).",
        "hinweise": "Versionierung, Releases, approvals, rollback, traceability.",
        "hinweise_en": "Versioning, releases, approvals, rollback, traceability.",
        "guidance": "Versioniere Artefakte (Code, Modell, Daten, Doku). Definiere Release- und Rollback-Prozess, inkl. Approval.",
        "guidance_en": "Version the artefacts (code, model, data, documentation). Define a release and rollback process, including approval.",
        "evidence": ["Release notes", "Versioning strategy", "Approval records", "Rollback plan"],
        "evidence_en": ["Release notes", "Versioning strategy", "Approval records", "Rollback plan"],
        "rubric": {"0": "nicht bewertet", "3": "teilweise versioniert/ohne approvals", "5": "vollstaendige Traceability und kontrollierte Releases"},
        "rubric_en": {"0": "not assessed", "3": "partly versioned/without approvals", "5": "full traceability and controlled releases"},
        "ref": ("Verordnung (EU) 2024/1689, Art. 17 Abs. 1 Buchst. a "
                "(Management von Änderungen) i.V.m. Art. 43 Abs. 4"),
        "gewichtung": 2,
    },
    {
        "id": "AIA-DATA-01",
        "kapitel": "DATA",
        "titel": "Datasets: Dokumentation und Lineage",
        "titel_en": "Data sets: documentation and lineage",
        "beschreibung": "Nachvollziehbare Dokumentation von Trainings-/Validierungsdaten und deren Herkunft.",
        "beschreibung_en": "Traceable documentation of training/validation data and their provenance.",
        "hinweise": "Datasheets, lineage, licensing, retention, access controls.",
        "hinweise_en": "Datasheets, lineage, licensing, retention, access controls.",
        "guidance": "Dokumentiere Herkunft, Lizenzierung, Transformationen, Speicherung und Zugriff. Halte Lineage technisch nachvollziehbar.",
        "guidance_en": "Document provenance, licensing, transformations, storage and access. Keep the lineage technically traceable.",
        "evidence": ["Dataset docs", "Lineage logs", "Licensing notes", "Retention policy"],
        "evidence_en": ["Dataset docs", "Lineage logs", "Licensing notes", "Retention policy"],
        "rubric": {"0": "nicht bewertet", "3": "Doku vorhanden, Lineage teilw.", "5": "vollstaendige Lineage und Governance"},
        "rubric_en": {"0": "not assessed", "3": "documentation in place, lineage partial", "5": "full lineage and governance"},
        "ref": ("Verordnung (EU) 2024/1689, Art. 10 Abs. 2 Buchst. b und c "
                "(Herkunft der Daten, Datenaufbereitung)"),
        "gewichtung": 3,
    },
    {
        "id": "AIA-DATA-02",
        "kapitel": "DATA",
        "titel": "Bias-/Fairness-Pruefungen",
        "titel_en": "Bias/fairness checks",
        "beschreibung": "Geeignete Tests/Analysen zur Erkennung und Reduktion von Bias.",
        "beschreibung_en": "Appropriate tests/analyses for detecting and reducing bias.",
        "hinweise": "Testplaene, metrics, sampling, human review.",
        "hinweise_en": "Test plans, metrics, sampling, human review.",
        "guidance": "Definiere Fairness-Metriken, fuehre Tests regelmaessig durch, dokumentiere Findings und Remediation.",
        "guidance_en": "Define fairness metrics, run tests regularly, document findings and remediation.",
        "evidence": ["Test plan", "Fairness metrics", "Findings/Remediation", "Sampling rationale"],
        "evidence_en": ["Test plan", "Fairness metrics", "Findings/Remediation", "Sampling rationale"],
        "rubric": {"0": "nicht bewertet", "3": "gelegentliche Tests", "5": "regelmaessige, dokumentierte Tests mit Remediation"},
        "rubric_en": {"0": "not assessed", "3": "occasional tests", "5": "regular, documented tests with remediation"},
        "ref": ("Verordnung (EU) 2024/1689, Art. 10 Abs. 2 Buchst. f und g "
                "(Untersuchung auf Verzerrungen, Gegenmaßnahmen)"),
        "gewichtung": 2,
    },
    {
        "id": "AIA-HR-08",
        "kapitel": "OPS",
        "titel": "Post-Market Monitoring",
        "titel_en": "Post-market monitoring",
        "beschreibung": "Monitoring-Plan und Feedback-Loops nach Inverkehrbringen.",
        "beschreibung_en": "Monitoring plan and feedback loops after placing on the market.",
        "hinweise": "Incident process, telemetry, KPIs, periodic reviews.",
        "hinweise_en": "Incident process, telemetry, KPIs, periodic reviews.",
        "guidance": "Definiere Monitoring-KPIs, Telemetrie und Feedbackkanäle. Plane regelmaessige Reviews und Verbesserungen.",
        "guidance_en": "Define monitoring KPIs, telemetry and feedback channels. Plan regular reviews and improvements.",
        "evidence": ["Monitoring plan", "KPIs/telemetry", "Review records"],
        "evidence_en": ["Monitoring plan", "KPIs/telemetry", "Review records"],
        "rubric": {"0": "nicht bewertet", "3": "Plan vorhanden", "5": "Plan betrieben + Nachweise"},
        "rubric_en": {"0": "not assessed", "3": "plan in place", "5": "plan operated + evidence"},
        "ref": "Verordnung (EU) 2024/1689, Art. 72 (Beobachtung nach dem Inverkehrbringen)",
        "gewichtung": 2,
    },
    {
        "id": "AIA-HR-09",
        "kapitel": "OPS",
        "titel": "Incident Management / Meldungen",
        "titel_en": "Incident management / reporting",
        "beschreibung": "Prozess für Incident handling und regulatorische Meldungen.",
        "beschreibung_en": "Process for incident handling and regulatory reporting.",
        "hinweise": "Runbooks, severity thresholds, communication templates.",
        "hinweise_en": "Runbooks, severity thresholds, communication templates.",
        "guidance": "Definiere Incident-Klassen, Response-Prozess, Verantwortlichkeiten und Kommunikations-/Melde-Templates.",
        "guidance_en": "Define incident classes, the response process, responsibilities and communication/reporting templates.",
        "evidence": ["Incident response plan", "Runbooks", "Severity matrix", "Communication templates"],
        "evidence_en": ["Incident response plan", "Runbooks", "Severity matrix", "Communication templates"],
        "rubric": {"0": "nicht bewertet", "3": "Prozess dokumentiert", "5": "geuebt, betrieben, nachvollziehbar"},
        "rubric_en": {"0": "not assessed", "3": "process documented", "5": "exercised, operated, traceable"},
        "ref": "Verordnung (EU) 2024/1689, Art. 73 (Meldung schwerwiegender Vorfälle)",
        "gewichtung": 2,
    },
]


#: Schwelle für die Kachel „Offene Punkte" im Dashboard: Eine Anforderung
#: gilt **unter** diesem Wert als nicht erfüllt (#2066).
#:
#: Der Wert ist derselbe wie ``cra.konformitaet_gate._ERFUELLT_AB`` und
#: ``shared.ki_pruefhinweise.ERFUELLUNG_AB`` — dort als Kopie mit Test, weil
#: ``shared`` nicht von einem Fachmodul abhängen darf (#1862/#2018). Hier liegt
#: er als Modulkonstante, damit der Endpunkt ihn **mitliefern** kann: Die
#: Kachel war mit „Score < 5" beschriftet und rechnete ``<= 2``; Anforderungen
#: mit Score 3 und 4 fielen durch das Raster, und keine Modul-View setzte die
#: Schwelle. Wer die Zahl liefert, liefert jetzt auch ihre Bedeutung.
LUECKEN_SCHWELLE = 4


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
    # #2066: wie in DSGVO — der Schlüssel fehlte, die Kachel zeigte bei 9 von
    # 13 offenen Anforderungen eine grüne Null.
    luecken = [
        req for req in anforderungen
        if int(bewertungen.get(req["id"], 0) or 0) < LUECKEN_SCHWELLE
    ]
    luecken.sort(key=lambda r: (int(bewertungen.get(r["id"], 0) or 0),
                                -int(r.get("gewichtung", 1))))

    return {
        "gesamt_pct": round(gesamt_pct, 1),
        "kapitel_pct": {k: round(v, 1) for k, v in kapitel_pct.items()},
        "ampel": ampel,
        "bewertete_count": bewertete,
        "gesamt_count": len(anforderungen),
        "luecken": luecken,
        "luecken_schwelle": LUECKEN_SCHWELLE,
    }
