"""NIS2-Modul – Anforderungskatalog (Richtlinie (EU) 2022/2555)."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from shared import katalog_sprache as _ks

EINRICHTUNGSKLASSEN: dict[str, dict[str, str]] = {
    "wesentlich": {
        "label": "Wesentliche Einrichtung",
        "label_en": "Essential entity",
        "beschreibung": "Einrichtungen der in Anhang I genannten Sektoren (z.B. Energie, Verkehr, Bankwesen, Gesundheit, Wasser, digitale Infrastruktur).",
        "beschreibung_en": (
            "Entities in the sectors listed in Annex I (such as energy, "
            "transport, banking, health, water, digital infrastructure)."),
    },
    "wichtig": {
        "label": "Wichtige Einrichtung",
        "label_en": "Important entity",
        "beschreibung": "Einrichtungen der in Anhang II genannten Sektoren (z.B. Post, Abfallwirtschaft, Chemie, Lebensmittel, verarbeitendes Gewerbe, digitale Dienste).",
        "beschreibung_en": (
            "Entities in the sectors listed in Annex II (such as postal "
            "services, waste management, chemicals, food, manufacturing, "
            "digital providers)."),
    },
    "beide": {
        "label": "Wesentliche und Wichtige Einrichtung",
        "label_en": "Essential and important entity",
        "beschreibung": "Einrichtung ist sowohl als wesentliche als auch als wichtige Einrichtung eingestuft.",
        "beschreibung_en": (
            "The entity is classified both as an essential and as an important "
            "entity."),
    },
}

KAPITEL: dict[str, dict[str, str]] = {
    "NIS1": {
        "titel": "Governance & Verantwortung",
        "titel_en": "Governance & responsibility",
        "referenz": "Art. 20 NIS2-RL",
        "referenz_en": "Art. 20 NIS 2 Directive",
        "beschreibung": "Anforderungen an das Management, die Unternehmensleitung und die organisatorische Verantwortung für Cybersicherheit.",
        "beschreibung_en": (
            "Requirements for management, the management bodies and "
            "organisational responsibility for cybersecurity."),
    },
    "NIS2": {
        "titel": "Risikomanagement & Technische Maßnahmen",
        "titel_en": "Risk management & technical measures",
        "referenz": "Art. 21 NIS2-RL",
        "referenz_en": "Art. 21 NIS 2 Directive",
        "beschreibung": "Maßnahmen zur Bewältigung von Cybersicherheitsrisiken für Netz- und Informationssysteme.",
        "beschreibung_en": (
            "Measures to manage cybersecurity risks to network and information "
            "systems."),
    },
    "NIS3": {
        "titel": "Meldepflichten & Incident Response",
        "titel_en": "Reporting obligations & incident response",
        "referenz": "Art. 23 NIS2-RL",
        "referenz_en": "Art. 23 NIS 2 Directive",
        "beschreibung": "Pflichten zur Meldung erheblicher Sicherheitsvorfälle an die zuständigen Behörden.",
        "beschreibung_en": (
            "Obligations to report significant incidents to the competent "
            "authorities."),
    },
    "NIS4": {
        "titel": "Lieferkettensicherheit",
        "titel_en": "Supply chain security",
        "referenz": "Art. 21 Abs. 2 lit. d NIS2-RL",
        "referenz_en": "Art. 21(2) point (d) NIS 2 Directive",
        "beschreibung": "Sicherheit in der Lieferkette einschließlich sicherheitsrelevanter Aspekte der Beziehungen zwischen Einrichtungen und ihren unmittelbaren Anbietern.",
        "beschreibung_en": (
            "Security in the supply chain, including security-related aspects "
            "of the relationships between entities and their direct suppliers."),
    },
    "NIS5": {
        "titel": "Implementierung & Zertifizierung",
        "titel_en": "Implementation & certification",
        "referenz": "Art. 24–25 NIS2-RL",
        "referenz_en": "Art. 24–25 NIS 2 Directive",
        "beschreibung": "Nutzung von europäischen Cybersicherheitszertifizierungsschemata und Standardisierungsvorgaben zur Umsetzung.",
        "beschreibung_en": (
            "Use of European cybersecurity certification schemes and "
            "standardisation requirements for implementation."),
    },
}

BEWERTUNG_SKALA: dict[int, dict[str, str]] = {
    0: {"label": "Nicht bewertet", "label_en": "Not assessed",       "farbe": "#9E9E9E"},
    1: {"label": "Nicht erfüllt", "label_en": "Not fulfilled",         "farbe": "#C62828"},
    2: {"label": "In Planung", "label_en": "Planned",            "farbe": "#E65100"},
    3: {"label": "Teilweise erfüllt", "label_en": "Partly fulfilled",     "farbe": "#F57F17"},
    4: {"label": "Weitgehend erfüllt", "label_en": "Largely fulfilled",    "farbe": "#2E7D32"},
    5: {"label": "Vollständig erfüllt", "label_en": "Fully fulfilled",   "farbe": "#1B5E20"},
}

BEWERTUNG_LABELS: dict[int, str] = {k: v["label"] for k, v in BEWERTUNG_SKALA.items()}

NIS2_ANFORDERUNGEN: list[dict[str, Any]] = [
    # ── NIS1: Governance & Verantwortung ────────────────────────────────────
    {
        "id": "NIS1-01", "kapitel": "NIS1", "gewichtung": 3,
        "ref": "Art. 20 Abs. 1 NIS2-RL",
        "ref_en": "Art. 20(1) NIS 2 Directive",
        "titel": "Verantwortung der Unternehmensleitung",
        "titel_en": "Responsibility of the management bodies",
        "beschreibung": "Die Leitungsorgane der Einrichtung müssen die Maßnahmen zum Cybersicherheits-Risikomanagement genehmigen und deren Umsetzung überwachen.",
        "beschreibung_en": "The entity's management bodies must approve the cybersecurity risk-management measures and oversee their implementation.",
        "hinweise": "Nachweise: Beschlüsse des Leitungsorgans, Sitzungsprotokolle, Richtlinien mit Freigabevermerk der Geschäftsführung.",
        "hinweise_en": "Evidence: management body resolutions, minutes of meetings, policies carrying a documented approval by the management.",
    },
    {
        "id": "NIS1-02", "kapitel": "NIS1", "gewichtung": 3,
        "ref": "Art. 20 Abs. 2 NIS2-RL",
        "ref_en": "Art. 20(2) NIS 2 Directive",
        "titel": "Schulung der Unternehmensleitung",
        "titel_en": "Training of the management bodies",
        "beschreibung": "Mitglieder der Leitungsorgane müssen an Schulungen zu Cybersicherheitsrisiken teilnehmen und ihren Mitarbeitenden vergleichbare Schulungen anbieten.",
        "beschreibung_en": "Members of the management bodies must follow training on cybersecurity risks and offer comparable training to their employees.",
        "hinweise": "Nachweise: Schulungsnachweise, Zertifikate, Schulungsplan für das Managementteam.",
        "hinweise_en": "Evidence: training records, certificates, training plan for the management team.",
    },
    {
        "id": "NIS1-03", "kapitel": "NIS1", "gewichtung": 2,
        "ref": "Art. 20 Abs. 1 NIS2-RL",
        "ref_en": "Art. 20(1) NIS 2 Directive",
        "titel": "Haftung der Leitungsorgane",
        "titel_en": "Liability of the management bodies",
        "beschreibung": "Leitungsorgane können für Verstöße gegen Cybersicherheitspflichten haftbar gemacht werden. Einrichtungen müssen sicherstellen, dass Leitungsorgane die Anforderungen kennen.",
        "beschreibung_en": "Management bodies can be held liable for infringements of cybersecurity obligations. Entities must ensure that their management bodies are aware of the requirements.",
        "hinweise": "Nachweise: Dokumentierte Kenntnis der Pflichten, interne Richtlinien zur Haftung.",
        "hinweise_en": "Evidence: documented awareness of the obligations, internal policies on liability.",
    },
    {
        "id": "NIS1-04", "kapitel": "NIS1", "gewichtung": 2,
        # #2055: Hing an „Art. 20 NIS2-RL". Art. 20 „Governance" hat **zwei**
        # Absätze — Billigung/Überwachung durch die Leitungsorgane (Abs. 1) und
        # deren Schulungspflicht (Abs. 2); von einer Strategie der Einrichtung
        # steht dort nichts. Die *nationale* Cybersicherheitsstrategie ist
        # Art. 7 und richtet sich an die Mitgliedstaaten — sie hier einzusetzen
        # wäre derselbe Fehler wie in #2050, nur umgekehrt.
        #
        # Tragfähig ist Art. 21 Abs. 1 (geeignete und verhältnismäßige
        # Maßnahmen) i.V.m. Abs. 2 Buchst. a (Konzepte zur Risikoanalyse und
        # Sicherheit für Informationssysteme) und Art. 20 Abs. 1 für die
        # Billigung durch die Leitung.
        "ref": ("Art. 21 Abs. 1 i.V.m. Abs. 2 Buchst. a NIS2-RL; "
                "Billigung durch die Leitung: Art. 20 Abs. 1"),
        "ref_en": ("Art. 21(1) in conjunction with (2)(a) NIS 2 Directive; "
                   "approval by management: Art. 20(1)"),
        "titel": "Cybersicherheitsstrategie",
        "titel_en": "Cybersecurity strategy",
        "beschreibung": "Die Einrichtung hat eine dokumentierte Cybersicherheitsstrategie mit klaren Zielen, Verantwortlichkeiten und Überprüfungsmechanismen.",
        "beschreibung_en": "The entity has a documented cybersecurity strategy with clear objectives, responsibilities and review mechanisms.",
        "hinweise": "Nachweise: Strategie-Dokument, Governance-Framework, RACI-Matrix für Cybersicherheit.",
        "hinweise_en": "Evidence: strategy document, governance framework, RACI matrix for cybersecurity.",
    },
    {
        "id": "NIS1-05", "kapitel": "NIS1", "gewichtung": 2,
        "ref": "Art. 20 NIS2-RL",
        "ref_en": "Art. 20 NIS 2 Directive",
        "titel": "Rollen und Verantwortlichkeiten",
        "titel_en": "Roles and responsibilities",
        "beschreibung": "Klare Definition von Cybersicherheitsrollen (CISO, IT-Sicherheitsbeauftragter o.ä.) mit dokumentierten Aufgaben und Befugnissen.",
        "beschreibung_en": "Clear definition of cybersecurity roles (CISO, information security officer or similar) with documented tasks and powers.",
        "hinweise": "Nachweise: Stellenbeschreibungen, Organigramm, Beauftragungsschreiben.",
        "hinweise_en": "Evidence: job descriptions, organisational chart, letters of appointment.",
    },

    # ── NIS2: Risikomanagement & Technische Maßnahmen ───────────────────────
    {
        "id": "NIS2-01", "kapitel": "NIS2", "gewichtung": 3,
        "ref": "Art. 21 Abs. 1 NIS2-RL",
        "ref_en": "Art. 21(1) NIS 2 Directive",
        "titel": "Risikoanalyse und Sicherheitsrichtlinien",
        "titel_en": "Risk analysis and security policies",
        "beschreibung": "Geeignete und verhältnismäßige technische, betriebliche und organisatorische Maßnahmen auf Basis einer umfassenden Risikoanalyse für Netz- und Informationssysteme.",
        "beschreibung_en": "Appropriate and proportionate technical, operational and organisational measures based on a comprehensive risk analysis for network and information systems.",
        "hinweise": "Nachweise: Risikoregister, Risikoanalyse-Dokument, Sicherheitsrichtlinien (ISO 27001, BSI IT-Grundschutz).",
        "hinweise_en": "Evidence: risk register, risk analysis document, security policies (ISO 27001, BSI IT-Grundschutz).",
    },
    {
        "id": "NIS2-02", "kapitel": "NIS2", "gewichtung": 3,
        "ref": "Art. 21 Abs. 2 lit. a NIS2-RL",
        "ref_en": "Art. 21(2) point (a) NIS 2 Directive",
        "titel": "Konzepte für Risikoanalyse und Informationssicherheit",
        "titel_en": "Policies on risk analysis and information system security",
        "beschreibung": "Konzepte in Bezug auf die Risikoanalyse und Sicherheit von Informationssystemen müssen vorhanden und regelmäßig aktualisiert werden.",
        "beschreibung_en": "Policies on risk analysis and the security of information systems must be in place and updated regularly.",
        "hinweise": "Nachweise: ISMS-Dokumentation, Sicherheitskonzept, Informationssicherheits-Leitlinie.",
        "hinweise_en": "Evidence: ISMS documentation, security concept, information security policy.",
    },
    {
        "id": "NIS2-03", "kapitel": "NIS2", "gewichtung": 3,
        "ref": "Art. 21 Abs. 2 lit. b NIS2-RL",
        "ref_en": "Art. 21(2) point (b) NIS 2 Directive",
        "titel": "Bewältigung von Sicherheitsvorfällen",
        "titel_en": "Incident handling",
        "beschreibung": "Konzepte und Verfahren für die Bewältigung von Sicherheitsvorfällen (Incident Management) müssen etabliert sein.",
        "beschreibung_en": "Policies and procedures for incident handling must be established.",
        "hinweise": "Nachweise: Incident-Response-Plan, Notfallhandbuch, Eskalationsverfahren, Playbooks.",
        "hinweise_en": "Evidence: incident response plan, emergency manual, escalation procedures, playbooks.",
    },
    {
        "id": "NIS2-04", "kapitel": "NIS2", "gewichtung": 3,
        "ref": "Art. 21 Abs. 2 lit. c NIS2-RL",
        "ref_en": "Art. 21(2) point (c) NIS 2 Directive",
        "titel": "Business Continuity und Krisenmanagement",
        "titel_en": "Business continuity and crisis management",
        "beschreibung": "Aufrechterhaltung des Betriebs (BCM) mit Backup-Management, Wiederherstellung im Notfall und Krisenmanagement.",
        "beschreibung_en": "Business continuity (BCM) with backup management, disaster recovery and crisis management.",
        "hinweise": "Nachweise: BCM-Plan, BCP-Tests, RTO/RPO-Definitionen, Backup-Konzept, Disaster-Recovery-Tests.",
        "hinweise_en": "Evidence: BCM plan, BCP tests, RTO/RPO definitions, backup concept, disaster recovery tests.",
    },
    {
        "id": "NIS2-05", "kapitel": "NIS2", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. e NIS2-RL",
        "ref_en": "Art. 21(2) point (e) NIS 2 Directive",
        "titel": "Sicherheit beim Erwerb, Entwicklung und Wartung",
        "titel_en": "Security in acquisition, development and maintenance",
        "beschreibung": "Sicherheit bei der Beschaffung, Entwicklung und Wartung von Netz- und Informationssystemen einschließlich Management und Offenlegung von Schwachstellen.",
        "beschreibung_en": "Security in the acquisition, development and maintenance of network and information systems, including vulnerability handling and disclosure.",
        "hinweise": "Nachweise: Secure-SDLC-Prozesse, Patch-Management-Konzept, Vulnerability-Disclosure-Policy.",
        "hinweise_en": "Evidence: secure SDLC processes, patch management concept, vulnerability disclosure policy.",
    },
    {
        "id": "NIS2-06", "kapitel": "NIS2", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. f NIS2-RL",
        "ref_en": "Art. 21(2) point (f) NIS 2 Directive",
        "titel": "Wirksamkeit von Sicherheitsmaßnahmen",
        "titel_en": "Effectiveness of security measures",
        "beschreibung": "Konzepte und Verfahren zur Bewertung der Wirksamkeit von Risikomanagementmaßnahmen im Bereich Cybersicherheit.",
        "beschreibung_en": "Policies and procedures to assess the effectiveness of cybersecurity risk-management measures.",
        "hinweise": "Nachweise: KPIs für Cybersicherheit, Audit-Berichte, Penetrationstests, Metriken-Dashboard.",
        "hinweise_en": "Evidence: cybersecurity KPIs, audit reports, penetration tests, metrics dashboard.",
    },
    {
        "id": "NIS2-07", "kapitel": "NIS2", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. g NIS2-RL",
        "ref_en": "Art. 21(2) point (g) NIS 2 Directive",
        "titel": "Grundlegende Hygienemaßnahmen und Schulungen",
        "titel_en": "Basic cyber hygiene practices and training",
        "beschreibung": "Grundlegende Praktiken der Cyberhygiene und Schulungen im Bereich Cybersicherheit für alle Mitarbeitenden.",
        "beschreibung_en": "Basic cyber hygiene practices and cybersecurity training for all staff.",
        "hinweise": "Nachweise: Security-Awareness-Schulungen, Phishing-Tests, Patch-Zyklen, Passwortrichtlinie, MFA.",
        "hinweise_en": "Evidence: security awareness training, phishing tests, patch cycles, password policy, MFA.",
    },
    {
        "id": "NIS2-08", "kapitel": "NIS2", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. h NIS2-RL",
        "ref_en": "Art. 21(2) point (h) NIS 2 Directive",
        "titel": "Kryptografie und Verschlüsselung",
        "titel_en": "Cryptography and encryption",
        "beschreibung": "Konzepte und Verfahren für den Einsatz von Kryptografie und gegebenenfalls Verschlüsselung.",
        "beschreibung_en": "Policies and procedures regarding the use of cryptography and, where appropriate, encryption.",
        "hinweise": "Nachweise: Kryptografie-Richtlinie, Inventar kryptografischer Verfahren, Zertifikatsmanagement.",
        "hinweise_en": "Evidence: cryptography policy, inventory of cryptographic methods, certificate management.",
    },
    {
        "id": "NIS2-09", "kapitel": "NIS2", "gewichtung": 3,
        "ref": "Art. 21 Abs. 2 lit. i NIS2-RL",
        "ref_en": "Art. 21(2) point (i) NIS 2 Directive",
        "titel": "Sicherheit des Personals und Zugangskontrolle",
        "titel_en": "Human resources security and access control",
        "beschreibung": "Sicherheit des Personals, Konzepte für die Zugriffskontrolle und Management von Anlagen (Asset Management).",
        "beschreibung_en": "Human resources security, access control policies and asset management.",
        "hinweise": "Nachweise: IAM-Konzept, Zero-Trust-Architektur, privilegierte Zugangsverwaltung (PAM), HR-Sicherheitsrichtlinien.",
        "hinweise_en": "Evidence: IAM concept, zero-trust architecture, privileged access management (PAM), HR security policies.",
    },
    {
        "id": "NIS2-10", "kapitel": "NIS2", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. j NIS2-RL",
        "ref_en": "Art. 21(2) point (j) NIS 2 Directive",
        "titel": "Multi-Faktor-Authentifizierung",
        "titel_en": "Multi-factor authentication",
        "beschreibung": "Verwendung von Multi-Faktor-Authentifizierung (MFA) oder kontinuierlicher Authentifizierungslösungen, gesicherte Sprach-, Video- und Textkommunikation.",
        "beschreibung_en": "Use of multi-factor authentication (MFA) or continuous authentication solutions, secured voice, video and text communication.",
        "hinweise": "Nachweise: MFA-Implementierungsnachweis, Konfigurationsdokumentationen, Authentifizierungsrichtlinie.",
        "hinweise_en": "Evidence: proof of MFA implementation, configuration documentation, authentication policy.",
    },

    # ── NIS3: Meldepflichten & Incident Response ─────────────────────────────
    {
        "id": "NIS3-01", "kapitel": "NIS3", "gewichtung": 3,
        "ref": "Art. 23 Abs. 1 NIS2-RL",
        "ref_en": "Art. 23(1) NIS 2 Directive",
        "titel": "Meldung erheblicher Sicherheitsvorfälle",
        "titel_en": "Notification of significant incidents",
        "beschreibung": "Erhebliche Sicherheitsvorfälle sind unverzüglich der zuständigen nationalen Behörde (BSI in Deutschland) oder dem CSIRT zu melden.",
        "beschreibung_en": "Significant incidents must be notified without undue delay to the competent national authority (the BSI in Germany) or to the CSIRT.",
        "hinweise": "Nachweise: Meldehistorie, Meldeprozess-Dokumentation, Kontaktdaten der zuständigen Behörde.",
        "hinweise_en": "Evidence: notification history, documentation of the notification process, contact details of the competent authority.",
    },
    {
        "id": "NIS3-02", "kapitel": "NIS3", "gewichtung": 3,
        "ref": "Art. 23 Abs. 4 NIS2-RL",
        "ref_en": "Art. 23(4) NIS 2 Directive",
        "titel": "Frühwarnung binnen 24 Stunden",
        "titel_en": "Early warning within 24 hours",
        "beschreibung": "Unverzügliche Frühwarnung an die zuständige Behörde oder das CSIRT binnen 24 Stunden nach Kenntnisnahme eines erheblichen Sicherheitsvorfalls.",
        "beschreibung_en": "Early warning without undue delay to the competent authority or the CSIRT within 24 hours of becoming aware of a significant incident.",
        "hinweise": "Nachweise: Dokumentierter Eskalationsprozess, Kontaktliste BSI/CSIRT, Bereitschaftsdienst (24/7).",
        "hinweise_en": "Evidence: documented escalation process, BSI/CSIRT contact list, on-call service (24/7).",
    },
    {
        "id": "NIS3-03", "kapitel": "NIS3", "gewichtung": 3,
        "ref": "Art. 23 Abs. 4 lit. b NIS2-RL",
        "ref_en": "Art. 23(4) point (b) NIS 2 Directive",
        "titel": "Vorfallsmeldung binnen 72 Stunden",
        "titel_en": "Incident notification within 72 hours",
        "beschreibung": "Vorfallsmeldung mit erster Bewertung des Sicherheitsvorfalls, Schweregrad und Kompromittierungsindikatoren binnen 72 Stunden nach Kenntnisnahme.",
        "beschreibung_en": "Incident notification with an initial assessment of the incident, its severity and the indicators of compromise within 72 hours of becoming aware.",
        "hinweise": "Nachweise: Meldeformulare, Ticketsystem-Exports mit Zeitstempeln, Kommunikationsnachweis mit BSI.",
        "hinweise_en": "Evidence: notification forms, ticket system exports with timestamps, record of the communication with the BSI.",
    },
    {
        "id": "NIS3-04", "kapitel": "NIS3", "gewichtung": 2,
        "ref": "Art. 23 Abs. 4 lit. d NIS2-RL",
        "ref_en": "Art. 23(4) point (d) NIS 2 Directive",
        "titel": "Abschlussbericht binnen eines Monats",
        "titel_en": "Final report within one month",
        "beschreibung": "Abschlussbericht mit detaillierter Beschreibung des Vorfalls, Ursachenanalyse, ergriffenen Abhilfemaßnahmen und Auswirkungen spätestens einen Monat nach Meldung.",
        "beschreibung_en": "Final report with a detailed description of the incident, root cause analysis, the mitigation measures applied and the impact, no later than one month after the notification.",
        "hinweise": "Nachweise: Post-Incident-Review-Dokumente, Root-Cause-Analysis, Lessons-Learned-Protokolle.",
        "hinweise_en": "Evidence: post-incident review documents, root cause analysis, lessons-learned records.",
    },
    {
        "id": "NIS3-05", "kapitel": "NIS3", "gewichtung": 2,
        "ref": "Art. 23 Abs. 2 NIS2-RL",
        "ref_en": "Art. 23(2) NIS 2 Directive",
        "titel": "Benachrichtigung betroffener Empfänger",
        "titel_en": "Notification of affected recipients",
        "beschreibung": "Erhebliche Cybersicherheitsbedrohungen müssen den betroffenen Empfängern der Dienste mitgeteilt werden, wenn dies geboten ist.",
        "beschreibung_en": "Significant cyber threats must be communicated to the affected recipients of the services where this is appropriate.",
        "hinweise": "Nachweise: Kommunikationsplan, Benachrichtigungsvorlagen, Meldenachweis an Firmen/Nutzer.",
        "hinweise_en": "Evidence: communication plan, notification templates, proof of notification to companies/users.",
    },
    {
        "id": "NIS3-06", "kapitel": "NIS3", "gewichtung": 2,
        "ref": "Art. 23 Abs. 3 NIS2-RL",
        "ref_en": "Art. 23(3) NIS 2 Directive",
        "titel": "Erkennung und Klassifizierung von Vorfällen",
        "titel_en": "Detection and classification of incidents",
        "beschreibung": "Prozesse zur Erkennung, Bewertung und Klassifizierung von Sicherheitsvorfällen nach Erheblichkeit (wesentliche vs. nicht-wesentliche Vorfälle).",
        "beschreibung_en": "Processes for the detection, assessment and classification of incidents by significance (significant versus non-significant incidents).",
        "hinweise": "Nachweise: SIEM/SOC-Dokumentation, Klassifizierungsmatrix, Erkennungsverfahren.",
        "hinweise_en": "Evidence: SIEM/SOC documentation, classification matrix, detection procedures.",
    },

    # ── NIS4: Lieferkettensicherheit ─────────────────────────────────────────
    {
        "id": "NIS4-01", "kapitel": "NIS4", "gewichtung": 3,
        "ref": "Art. 21 Abs. 2 lit. d NIS2-RL",
        "ref_en": "Art. 21(2) point (d) NIS 2 Directive",
        "titel": "Sicherheit in der Lieferkette",
        "titel_en": "Supply chain security",
        "beschreibung": "Sicherheit in der Lieferkette einschließlich sicherheitsbezogener Aspekte der Beziehungen zwischen Einrichtungen und ihren unmittelbaren Anbietern und Diensteanbietern.",
        "beschreibung_en": "Supply chain security, including security-related aspects concerning the relationships between each entity and its direct suppliers or service providers.",
        "hinweise": "Nachweise: Lieferantenverzeichnis mit Risikoklassifizierung, Vertragsklauseln, Lieferantenbewertungen.",
        "hinweise_en": "Evidence: supplier register with risk classification, contractual clauses, supplier assessments.",
    },
    {
        "id": "NIS4-02", "kapitel": "NIS4", "gewichtung": 2,
        "ref": "Art. 21 Abs. 3 NIS2-RL",
        "ref_en": "Art. 21(3) NIS 2 Directive",
        "titel": "Berücksichtigung von Schwachstellen in der Lieferkette",
        "titel_en": "Taking account of vulnerabilities in the supply chain",
        "beschreibung": "Berücksichtigung der Gesamtqualität der Produkte und Cybersicherheitspraktiken der Lieferanten und Diensteanbieter, einschließlich ihrer Entwicklungsverfahren.",
        "beschreibung_en": "Taking into account the overall quality of the products and the cybersecurity practices of the suppliers and service providers, including their development procedures.",
        "hinweise": "Nachweise: Lieferanten-Audits, SBOM-Anforderungen, Sicherheitsfragebögen für Lieferanten.",
        "hinweise_en": "Evidence: supplier audits, SBOM requirements, security questionnaires for suppliers.",
    },
    {
        "id": "NIS4-03", "kapitel": "NIS4", "gewichtung": 2,
        # #2054: Hing an „Art. 22 NIS2-RL" und verlangte die **Beteiligung** an
        # koordinierten Risikobewertungen. Art. 22 richtet sich an Unionsorgane:
        # „(1) Die Kooperationsgruppe kann … koordinierte Risikobewertungen …
        # durchführen. (2) Die Kommission legt … fest …". Eine Einrichtung kann
        # sich daran nicht beteiligen, und ein „Nachweis der Beteiligung" ist
        # für einen Mandanten **nicht erbringbar** — eine Anforderung, die
        # niemand erfüllen kann, wird nicht bearbeitet, sondern umgangen.
        #
        # Die Pflicht der Einrichtung steht in Art. 21 Abs. 3 Satz 2: Sie muss
        # die **Ergebnisse** der Bewertungen nach Art. 22 Abs. 1
        # „berücksichtigen".
        "ref": "Art. 21 Abs. 3 Satz 2 i.V.m. Art. 22 Abs. 1 NIS2-RL",
        "ref_en": "Art. 21(3) sentence 2 in conjunction with Art. 22(1) NIS 2 Directive",
        "titel": "Ergebnisse koordinierter Lieferketten-Risikobewertungen berücksichtigen",
        "titel_en": "Take into account the outcomes of coordinated supply-chain risk assessments",
        "beschreibung": "Die Ergebnisse der von der Kooperationsgruppe durchgeführten koordinierten Risikobewertungen kritischer IKT-Lieferketten werden bei den Maßnahmen nach Art. 21 Abs. 2 Buchst. d berücksichtigt.",
        "beschreibung_en": "The outcomes of the Cooperation Group's coordinated risk assessments of critical ICT supply chains are taken into account in the measures under Art. 21(2)(d).",
        "hinweise": "Nachweise: Vermerk, welche veröffentlichten Bewertungen geprüft wurden, und welche Folgerungen für die Lieferantenmaßnahmen gezogen wurden.",
        "hinweise_en": "Evidence: a note on which published assessments were reviewed and what conclusions were drawn for supplier measures.",
    },
    {
        "id": "NIS4-04", "kapitel": "NIS4", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. d NIS2-RL",
        "ref_en": "Art. 21(2) point (d) NIS 2 Directive",
        "titel": "Vertragliche Sicherheitsanforderungen",
        "titel_en": "Contractual security requirements",
        "beschreibung": "Vertragliche Sicherheitsanforderungen an Lieferanten und Diensteanbieter, einschließlich Mindest-Cybersicherheitsstandards und Auditrechte.",
        "beschreibung_en": "Contractual security requirements for suppliers and service providers, including minimum cybersecurity standards and audit rights.",
        "hinweise": "Nachweise: Musterverträge mit Sicherheitsklauseln, SLAs mit Sicherheitsanforderungen, Auditberichte.",
        "hinweise_en": "Evidence: model contracts with security clauses, SLAs with security requirements, audit reports.",
    },

    # ── NIS5: Implementierung & Zertifizierung ───────────────────────────────
    {
        "id": "NIS5-01", "kapitel": "NIS5", "gewichtung": 2,
        "ref": "Art. 24 NIS2-RL",
        "ref_en": "Art. 24 NIS 2 Directive",
        "titel": "Nutzung europäischer Cybersicherheitszertifizierung",
        "titel_en": "Use of European cybersecurity certification",
        "beschreibung": "Nutzung von Produkten, Diensten und Verfahren der IKT, die im Rahmen europäischer Cybersicherheitszertifizierungsschemata (gem. Cybersecurity Act) zertifiziert sind.",
        "beschreibung_en": "Use of ICT products, ICT services and ICT processes that are certified under European cybersecurity certification schemes (pursuant to the Cybersecurity Act).",
        "hinweise": "Nachweise: Zertifizierungsnachweise, Inventar zertifizierter Produkte/Dienste, Beschaffungsrichtlinie.",
        "hinweise_en": "Evidence: certificates, inventory of certified products/services, procurement policy.",
    },
    {
        "id": "NIS5-02", "kapitel": "NIS5", "gewichtung": 2,
        "ref": "Art. 25 NIS2-RL",
        "ref_en": "Art. 25 NIS 2 Directive",
        "titel": "Normen und technische Spezifikationen",
        "titel_en": "Standards and technical specifications",
        "beschreibung": "Berücksichtigung europäischer und internationaler Normen (ISO/IEC 27001, ETSI EN-Normen) sowie technischer Spezifikationen bei der Umsetzung der Sicherheitsmaßnahmen.",
        "beschreibung_en": "Taking European and international standards (ISO/IEC 27001, ETSI EN standards) as well as technical specifications into account when implementing the security measures.",
        "hinweise": "Nachweise: ISO 27001-Zertifikat oder Zertifizierungsplanung, Normenmapping, Compliance-Berichte.",
        "hinweise_en": "Evidence: ISO 27001 certificate or certification planning, mapping of standards, compliance reports.",
    },
    {
        "id": "NIS5-03", "kapitel": "NIS5", "gewichtung": 2,
        "ref": "Art. 32 Abs. 2 lit. b und g NIS2-RL",
        "ref_en": "Art. 32(2) points (b) and (g) NIS 2 Directive",
        "titel": "Nachweis der Einhaltung für wesentliche Einrichtungen",
        "titel_en": "Evidence of compliance for essential entities",
        "beschreibung": "Wesentliche Einrichtungen müssen auf Anfrage der Behörden die Einhaltung der Sicherheitsanforderungen durch Zertifizierungen oder regelmäßige Audits nachweisen.",
        "beschreibung_en": "Essential entities must demonstrate compliance with the security requirements upon request by the authorities, by means of certifications or regular audits.",
        "hinweise": "Nachweise: Zertifizierungsberichte (ISO 27001, BSI IT-Grundschutz), externe Audit-Berichte, Self-Assessment.",
        "hinweise_en": "Evidence: certification reports (ISO 27001, BSI IT-Grundschutz), external audit reports, self-assessment.",
    },
    {
        "id": "NIS5-04", "kapitel": "NIS5", "gewichtung": 3,
        "ref": "Art. 3 Abs. 4 NIS2-RL",
        "ref_en": "Art. 3(4) NIS 2 Directive",
        "titel": "Registrierung bei der zuständigen Behörde",
        "titel_en": "Registration with the competent authority",
        "beschreibung": "Einrichtungen müssen sich bei der zuständigen nationalen Behörde (Deutschland: BSI) registrieren und relevante Informationen übermitteln.",
        "beschreibung_en": "Entities must register with the competent national authority (Germany: BSI) and submit the relevant information.",
        "hinweise": "Nachweise: Registrierungsnachweis beim BSI, aktuelle Registrierungsdaten, Ansprechpartner-Dokumentation.",
        "hinweise_en": "Evidence: proof of registration with the BSI, up-to-date registration data, documentation of the contact persons.",
    },
    {
        "id": "NIS5-05", "kapitel": "NIS5", "gewichtung": 2,
        "ref": "Art. 32–33 NIS2-RL",
        "ref_en": "Art. 32–33 NIS 2 Directive",
        "titel": "Zusammenarbeit mit Aufsichtsbehörden",
        "titel_en": "Cooperation with the supervisory authorities",
        "beschreibung": "Kooperation mit den zuständigen Behörden bei Aufsichtsmaßnahmen, Vor-Ort-Prüfungen und der Bereitstellung von Informationen.",
        "beschreibung_en": "Cooperation with the competent authorities in supervisory measures, on-site inspections and the provision of information.",
        "hinweise": "Nachweise: Kommunikationshistorie mit BSI, Reaktionsplan für Behördenanfragen, interne Ansprechpartner.",
        "hinweise_en": "Evidence: history of the communication with the BSI, response plan for requests from authorities, internal contact persons.",
    },
]

_STANDARD_IDS: frozenset[str] = frozenset(r["id"] for r in NIS2_ANFORDERUNGEN)


def anforderungen_by_kapitel() -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {k: [] for k in KAPITEL}
    for req in NIS2_ANFORDERUNGEN:
        result[req["kapitel"]].append(req)
    return result


def load_merged_anforderungen(db_path: "Path | None" = None, *,
                              sprache: str | None = None) -> list[dict]:
    """Gibt den vollständigen Anforderungskatalog zurück, mit _quelle-Tag pro Eintrag."""
    base: dict[str, dict] = {
        r["id"]: dict(r, _quelle="standard") for r in NIS2_ANFORDERUNGEN
    }

    if db_path is not None:
        try:
            from nis2.db import load_custom_anforderungen
            for custom in load_custom_anforderungen(db_path):
                rid = custom["id"]
                quelle = "override" if custom.get("ist_override") else "custom"
                base[rid] = {
                    "id": rid,
                    "kapitel": custom["kapitel"],
                    "ref": custom["ref"],
                    "titel": custom["titel"],
                    "beschreibung": custom["beschreibung"],
                    "hinweise": custom["hinweise"],
                    "gewichtung": int(custom["gewichtung"]),
                    "_quelle": quelle,
                }
        except Exception:
            pass

    kap_order = {k: i for i, k in enumerate(KAPITEL)}
    aus = sorted(base.values(),
                 key=lambda r: (kap_order.get(r.get("kapitel", "NIS5"), 99),
                                r["id"]))
    # #1954: siehe shared/katalog_sprache — nur titel/beschreibung.
    return _ks.uebersetze_viele(aus, sprache or "")


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
    bewertungen: dict[str, dict],
    anforderungen: list[dict],
) -> dict[str, Any]:
    gesamt_punkte = 0
    max_punkte = 0
    kapitel_scores: dict[str, dict[str, Any]] = {k: {"punkte": 0, "max": 0, "anzahl": 0, "bewertet": 0} for k in KAPITEL}

    for req in anforderungen:
        kid = req["kapitel"]
        gew = int(req.get("gewichtung", 1))
        bew = bewertungen.get(req["id"], {})
        wert = int(bew.get("bewertung", 0))

        max_punkte += 5 * gew
        gesamt_punkte += wert * gew
        if kid in kapitel_scores:
            kapitel_scores[kid]["max"] += 5 * gew
            kapitel_scores[kid]["punkte"] += wert * gew
            kapitel_scores[kid]["anzahl"] += 1
            if wert > 0:
                kapitel_scores[kid]["bewertet"] += 1

    prozent = round(gesamt_punkte / max_punkte * 100, 1) if max_punkte > 0 else 0.0

    for kid, ks in kapitel_scores.items():
        ks["prozent"] = round(ks["punkte"] / ks["max"] * 100, 1) if ks["max"] > 0 else 0.0

    # #2066: Gerechnet wurde `<= 2`, beschriftet war die Kachel mit „Score < 5".
    luecken = [
        req for req in anforderungen
        if int(bewertungen.get(req["id"], {}).get("bewertung", 0)) < LUECKEN_SCHWELLE
    ]
    luecken.sort(key=lambda r: (int(bewertungen.get(r["id"], {}).get("bewertung", 0)), -int(r.get("gewichtung", 1))))

    return {
        "gesamt_punkte": gesamt_punkte,
        "max_punkte": max_punkte,
        "prozent": prozent,
        "kapitel_scores": kapitel_scores,
        "luecken": luecken,
        "luecken_schwelle": LUECKEN_SCHWELLE,
    }
