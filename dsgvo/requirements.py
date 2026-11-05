"""DSGVO-Anforderungskatalog – Verordnung (EU) 2016/679 (Datenschutz-Grundverordnung).

Jede Anforderung ist mit dem exakten Artikelverweis versehen, um wissenschaftliche
Transparenz und Nachvollziehbarkeit im Bericht sicherzustellen.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from shared import katalog_sprache as _ks

if TYPE_CHECKING:  # #1896: nur für die Annotation, nicht zur Laufzeit
    from pathlib import Path

# ── Organisationstypen ────────────────────────────────────────────────────────
ORGANISATIONSTYPEN = {
    "verantwortlicher": {
        "label": "Verantwortlicher (Art. 4 Nr. 7 DSGVO)",
        "label_en": "Controller (Art. 4(7) GDPR)",
        "farbe": "#1565c0",
        "beschreibung": (
            "Natürliche oder juristische Person, Behörde, Einrichtung oder andere Stelle, "
            "die über Zwecke und Mittel der Verarbeitung personenbezogener Daten entscheidet."
        ),
        "beschreibung_en": (
            "A natural or legal person, public authority, agency or other body "
            "which determines the purposes and means of the processing of "
            "personal data."),
        "referenz": "Verordnung (EU) 2016/679, Art. 4 Nr. 7",
        "referenz_en": "Regulation (EU) 2016/679, Art. 4(7)",
    },
    "auftragsverarbeiter": {
        "label": "Auftragsverarbeiter (Art. 4 Nr. 8 DSGVO)",
        "label_en": "Processor (Art. 4(8) GDPR)",
        "farbe": "#4a148c",
        "beschreibung": (
            "Natürliche oder juristische Person, Behörde, Einrichtung oder andere Stelle, "
            "die personenbezogene Daten im Auftrag des Verantwortlichen verarbeitet."
        ),
        "beschreibung_en": (
            "A natural or legal person, public authority, agency or other body "
            "which processes personal data on behalf of the controller."),
        "referenz": "Verordnung (EU) 2016/679, Art. 4 Nr. 8",
        "referenz_en": "Regulation (EU) 2016/679, Art. 4(8)",
    },
    "beides": {
        "label": "Verantwortlicher und Auftragsverarbeiter",
        "label_en": "Controller and processor",
        "farbe": "#00695c",
        "beschreibung": (
            "Organisation tritt sowohl als Verantwortlicher für eigene Verarbeitungen "
            "als auch als Auftragsverarbeiter für Dritte auf."
        ),
        "beschreibung_en": (
            "The organisation acts both as a controller for its own processing "
            "and as a processor for third parties."),
        "referenz": "Verordnung (EU) 2016/679, Art. 4 Nr. 7 und 8",
        "referenz_en": "Regulation (EU) 2016/679, Art. 4(7) and (8)",
    },
}

# ── Kapitel / Domänen ─────────────────────────────────────────────────────────
KAPITEL = {
    "GDS1": {
        "titel": "Grundsätze & Rechtmäßigkeit",
        "titel_en": "Principles & lawfulness",
        "untertitel": "Verarbeitungsgrundsätze und Rechtsgrundlagen",
        "untertitel_en": "Principles of processing and legal bases",
        "farbe": "#1565c0",
        "soft": "#e3f2fd",
        "referenz": "Verordnung (EU) 2016/679, Art. 5, 6, 7, 9",
        "referenz_en": "Regulation (EU) 2016/679, Art. 5, 6, 7, 9",
        "beschreibung": (
            "Grundlegende Verarbeitungsprinzipien: Rechtmäßigkeit, Zweckbindung, "
            "Datenminimierung, Richtigkeit, Speicherbegrenzung, Integrität/Vertraulichkeit "
            "und Rechenschaftspflicht. Anforderungen an Rechtsgrundlagen und Einwilligung."
        ),
        "beschreibung_en": (
            "Fundamental principles of processing: lawfulness, purpose "
            "limitation, data minimisation, accuracy, storage limitation, "
            "integrity/confidentiality and accountability. Requirements for "
            "legal bases and consent."),
    },
    "GDS2": {
        "titel": "Betroffenenrechte",
        "titel_en": "Rights of the data subject",
        "untertitel": "Transparenz und individuelle Rechte",
        "untertitel_en": "Transparency and individual rights",
        "farbe": "#4a148c",
        "soft": "#f3e5f5",
        "referenz": "Verordnung (EU) 2016/679, Art. 12–22",
        "referenz_en": "Regulation (EU) 2016/679, Art. 12–22",
        "beschreibung": (
            "Informationspflichten bei Erhebung personenbezogener Daten sowie "
            "Umsetzung der Betroffenenrechte: Auskunft, Berichtigung, Löschung, "
            "Einschränkung, Datenübertragbarkeit und Widerspruch."
        ),
        "beschreibung_en": (
            "Information obligations when personal data are collected, and "
            "implementation of the rights of the data subject: access, "
            "rectification, erasure, restriction, data portability and "
            "objection."),
    },
    "GDS3": {
        "titel": "Pflichten des Verantwortlichen",
        "titel_en": "Obligations of the controller",
        "untertitel": "Accountability und Governance",
        "untertitel_en": "Accountability and governance",
        "farbe": "#00695c",
        "soft": "#e0f2f1",
        "referenz": "Verordnung (EU) 2016/679, Art. 24–26, 28, 30",
        "referenz_en": "Regulation (EU) 2016/679, Art. 24–26, 28, 30",
        "beschreibung": (
            "Allgemeine Pflichten: Nachweispflicht (Accountability), Privacy by Design "
            "und by Default, gemeinsam Verantwortliche, Auftragsverarbeitung und "
            "Verzeichnis von Verarbeitungstätigkeiten."
        ),
        "beschreibung_en": (
            "General obligations: accountability, data protection by design "
            "and by default, joint controllers, processing on behalf of a "
            "controller and the record of processing activities."),
    },
    "GDS4": {
        "titel": "Technische & organisatorische Maßnahmen",
        "titel_en": "Technical & organisational measures",
        "untertitel": "Datensicherheit (Art. 32)",
        "untertitel_en": "Security of processing (Art. 32)",
        "farbe": "#bf360c",
        "soft": "#fbe9e7",
        "referenz": "Verordnung (EU) 2016/679, Art. 32",
        "referenz_en": "Regulation (EU) 2016/679, Art. 32",
        "beschreibung": (
            "Geeignete technische und organisatorische Maßnahmen zum Schutz "
            "personenbezogener Daten unter Berücksichtigung von Stand der Technik, "
            "Implementierungskosten und Risiko."
        ),
        "beschreibung_en": (
            "Appropriate technical and organisational measures to protect "
            "personal data, taking into account the state of the art, the cost "
            "of implementation and the risk."),
    },
    "GDS5": {
        "titel": "Meldepflichten & Datenschutz-Folgenabschätzung",
        "titel_en": "Notification obligations & data protection impact assessment",
        "untertitel": "Incident Response und DSFA",
        "untertitel_en": "Incident response and DPIA",
        "farbe": "#e65100",
        "soft": "#fff3e0",
        "referenz": "Verordnung (EU) 2016/679, Art. 33–36",
        "referenz_en": "Regulation (EU) 2016/679, Art. 33–36",
        "beschreibung": (
            "Meldepflicht bei Datenschutzverletzungen (72 Stunden an Aufsichtsbehörde), "
            "Benachrichtigung betroffener Personen und Datenschutz-Folgenabschätzung "
            "bei Hochrisikoverarbeitungen."
        ),
        "beschreibung_en": (
            "Obligation to notify personal data breaches (within 72 hours to "
            "the supervisory authority), communication to the data subjects "
            "concerned, and the data protection impact assessment for "
            "high-risk processing."),
    },
    "GDS6": {
        "titel": "Datenschutzbeauftragter & Drittlandtransfer",
        "titel_en": "Data protection officer & third-country transfers",
        "untertitel": "DPO und internationale Übermittlungen",
        "untertitel_en": "DPO and international transfers",
        "farbe": "#2c3e50",
        "soft": "#ecf0f1",
        "referenz": "Verordnung (EU) 2016/679, Art. 37–39, 44–49",
        "referenz_en": "Regulation (EU) 2016/679, Art. 37–39, 44–49",
        "beschreibung": (
            "Benennung und Aufgaben des Datenschutzbeauftragten sowie "
            "Anforderungen an die Übermittlung personenbezogener Daten in Drittländer "
            "(Angemessenheitsbeschluss, Standardvertragsklauseln, BCR)."
        ),
        "beschreibung_en": (
            "Designation and tasks of the data protection officer, and "
            "requirements for transfers of personal data to third countries "
            "(adequacy decision, standard contractual clauses, BCR)."),
    },
}

# ── Bewertungsskala ───────────────────────────────────────────────────────────
BEWERTUNG_SKALA = {
    0: {"label": "Nicht bewertet", "label_en": "Not assessed", "farbe": "#9e9e9e", "reife_pct": 0},
    1: {"label": "Nicht vorhanden", "label_en": "Not in place", "farbe": "#c62828", "reife_pct": 0},
    2: {"label": "In Planung", "label_en": "Planned", "farbe": "#e65100", "reife_pct": 25},
    3: {"label": "Teilweise umgesetzt", "label_en": "Partly implemented", "farbe": "#f57f17", "reife_pct": 50},
    4: {"label": "Überwiegend umgesetzt", "label_en": "Largely implemented", "farbe": "#2e7d32", "reife_pct": 75},
    5: {"label": "Vollständig umgesetzt", "label_en": "Fully implemented", "farbe": "#1b5e20", "reife_pct": 100},
}

BEWERTUNG_LABELS = [v["label"] for v in BEWERTUNG_SKALA.values()]

# ── Anforderungskatalog ───────────────────────────────────────────────────────
DSGVO_ANFORDERUNGEN: list[dict[str, Any]] = [
    # ── GDS1: Grundsätze & Rechtmäßigkeit ────────────────────────────────────
    {
        "id": "GDS1-01",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. a DSGVO",
        "ref_en": "Art. 5(1) point (a) GDPR",
        "titel": "Rechtmäßigkeit, Verarbeitung nach Treu und Glauben, Transparenz",
        "titel_en": "Lawfulness, fairness and transparency",
        "beschreibung": (
            "Personenbezogene Daten müssen auf rechtmäßige Weise, nach Treu und Glauben "
            "und in einer für die betroffene Person nachvollziehbaren Weise verarbeitet werden."
        ),
        "beschreibung_en": (
            "Personal data must be processed lawfully, fairly and in a manner that is "
            "transparent to the data subject."
        ),
        "hinweise": (
            "Dokumentation aller Rechtsgrundlagen je Verarbeitungszweck; "
            "Datenschutzerklärung in klarer, verständlicher Sprache; "
            "Keine irreführenden oder verdeckten Datenerhebungen; "
            "Regelmäßige Überprüfung der Rechtsgrundlagen auf Aktualität."
        ),
        "hinweise_en": (
            "Document all legal bases for each processing purpose; Privacy notice in clear, "
            "plain language; No misleading or covert collection of data; Review the legal "
            "bases regularly to confirm they are still current."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-02",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. b DSGVO",
        "ref_en": "Art. 5(1) point (b) GDPR",
        "titel": "Zweckbindung – Verarbeitung nur für festgelegte Zwecke",
        "titel_en": "Purpose limitation – processing only for specified purposes",
        "beschreibung": (
            "Personenbezogene Daten dürfen nur für festgelegte, eindeutige und "
            "legitime Zwecke erhoben werden. Eine Weiterverarbeitung für andere Zwecke "
            "ist nur unter bestimmten Bedingungen zulässig (Kompatibilitätsprüfung)."
        ),
        "beschreibung_en": (
            "Personal data may only be collected for specified, explicit and legitimate "
            "purposes. Further processing for other purposes is permitted only under certain "
            "conditions (compatibility test)."
        ),
        "hinweise": (
            "Verarbeitungszwecke vor Datenerhebung exakt definieren und dokumentieren; "
            "Zweckänderungen prüfen (Art. 6 Abs. 4 DSGVO – Kompatibilitätskriterien); "
            "Keine Zweckentfremdung von Daten; "
            "Zwecke im Verzeichnis der Verarbeitungstätigkeiten festhalten."
        ),
        "hinweise_en": (
            "Define and document the processing purposes precisely before any data is "
            "collected; Assess any change of purpose (Art. 6(4) GDPR – compatibility "
            "criteria); No repurposing of data; Record the purposes in the record of "
            "processing activities."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-03",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. c DSGVO",
        "ref_en": "Art. 5(1) point (c) GDPR",
        "titel": "Datenminimierung – Beschränkung auf das Notwendige",
        "titel_en": "Data minimisation – limited to what is necessary",
        "beschreibung": (
            "Personenbezogene Daten müssen dem Verarbeitungszweck angemessen und "
            "erheblich sein sowie auf das für die Zwecke der Verarbeitung notwendige Maß beschränkt sein."
        ),
        "beschreibung_en": (
            "Personal data must be adequate and relevant to the purpose of the processing and "
            "limited to what is necessary for the purposes of the processing."
        ),
        "hinweise": (
            "Privacy-Impact-Analyse vor jeder neuen Verarbeitung; "
            "Regelmäßige Überprüfung: Werden wirklich alle erhobenen Felder benötigt?; "
            "Pseudonymisierung und Anonymisierung wo möglich; "
            "Keine 'auf Vorrat'-Erhebung von Daten."
        ),
        "hinweise_en": (
            "Privacy impact analysis before every new processing operation; Regular review: "
            "are all the fields collected really needed?; Pseudonymisation and anonymisation "
            "wherever possible; No collection of data 'just in case'."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS1-04",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. d DSGVO",
        "ref_en": "Art. 5(1) point (d) GDPR",
        "titel": "Richtigkeit – Daten aktuell und korrekt halten",
        "titel_en": "Accuracy – keeping data correct and up to date",
        "beschreibung": (
            "Personenbezogene Daten müssen sachlich richtig und erforderlichenfalls "
            "auf dem neuesten Stand sein. Unrichtige Daten müssen unverzüglich "
            "gelöscht oder berichtigt werden."
        ),
        "beschreibung_en": (
            "Personal data must be accurate and, where necessary, kept up to date. Inaccurate "
            "data must be erased or rectified without delay."
        ),
        "hinweise": (
            "Prozess zur Datenpflege und Aktualisierung; "
            "Mechanismus für Betroffene zur Datenkorretur (Art. 16 DSGVO); "
            "Regelmäßige Datenqualitätsprüfungen; "
            "Protokollierung von Berichtigungen."
        ),
        "hinweise_en": (
            "Process for maintaining and updating data; Mechanism for data subjects to have "
            "their data corrected (Art. 16 GDPR); Regular data quality checks; Logging of "
            "rectifications."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS1-05",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. e DSGVO",
        "ref_en": "Art. 5(1) point (e) GDPR",
        "titel": "Speicherbegrenzung – Löschkonzept und Aufbewahrungsfristen",
        "titel_en": "Storage limitation – erasure concept and retention periods",
        "beschreibung": (
            "Personenbezogene Daten dürfen nur so lange gespeichert werden, wie es "
            "für die Zwecke der Verarbeitung erforderlich ist. Es muss ein "
            "dokumentiertes Löschkonzept existieren."
        ),
        "beschreibung_en": (
            "Personal data may only be stored for as long as is necessary for the purposes of "
            "the processing. A documented erasure concept must exist."
        ),
        "hinweise": (
            "Löschkonzept mit Aufbewahrungsfristen je Datenkategorie; "
            "Automatisierte Löschroutinen implementieren; "
            "Dokumentation gesetzlicher Aufbewahrungspflichten (HGB, AO etc.); "
            "Regelmäßige Überprüfung gespeicherter Daten auf Löschreife."
        ),
        "hinweise_en": (
            "Erasure concept with retention periods for each category of data; Implement "
            "automated erasure routines; Document statutory retention obligations (German "
            "Commercial Code HGB, Fiscal Code AO, etc.); Review stored data regularly to see "
            "whether it is due for erasure."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-06",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. f DSGVO",
        "ref_en": "Art. 5(1) point (f) GDPR",
        "titel": "Integrität und Vertraulichkeit – Datensicherheit",
        "titel_en": "Integrity and confidentiality – data security",
        "beschreibung": (
            "Personenbezogene Daten müssen durch geeignete technische und organisatorische "
            "Maßnahmen vor unbefugter oder unrechtmäßiger Verarbeitung sowie vor "
            "unbeabsichtigtem Verlust, Zerstörung oder Schädigung geschützt werden."
        ),
        "beschreibung_en": (
            "Personal data must be protected by appropriate technical and organisational "
            "measures against unauthorised or unlawful processing and against accidental loss, "
            "destruction or damage."
        ),
        "hinweise": (
            "Verschlüsselung personenbezogener Daten (at rest und in transit); "
            "Zugriffskontrollen und Need-to-Know-Prinzip; "
            "Regelmäßige Sicherheitsaudits; "
            "Mitarbeiterschulungen zum Datenschutz."
        ),
        "hinweise_en": (
            "Encryption of personal data (at rest and in transit); Access controls and the "
            "need-to-know principle; Regular security audits; Data protection training for "
            "staff."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-07",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 2 DSGVO",
        "ref_en": "Art. 5(2) GDPR",
        "titel": "Rechenschaftspflicht (Accountability) – Nachweisführung",
        "titel_en": "Accountability – demonstrating compliance",
        "beschreibung": (
            "Der Verantwortliche muss die Einhaltung aller DSGVO-Grundsätze "
            "nachweisen können (Accountability-Prinzip). Alle Maßnahmen müssen "
            "dokumentiert und auf Anfrage vorlegbar sein."
        ),
        "beschreibung_en": (
            "The controller must be able to demonstrate compliance with all GDPR principles "
            "(accountability principle). All measures must be documented and available for "
            "inspection on request."
        ),
        "hinweise": (
            "Dokumentationssystem für alle Datenschutzmaßnahmen; "
            "Verzeichnis der Verarbeitungstätigkeiten (Art. 30 DSGVO); "
            "Datenschutz-Policies und Verfahrensanweisungen; "
            "Regelmäßige interne Datenschutzaudits."
        ),
        "hinweise_en": (
            "Documentation system for all data protection measures; Record of processing "
            "activities (Art. 30 GDPR); Data protection policies and procedural instructions; "
            "Regular internal data protection audits."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-08",
        "kapitel": "GDS1",
        "ref": "Art. 6 DSGVO",
        "ref_en": "Art. 6 GDPR",
        "titel": "Rechtsgrundlage für jede Verarbeitung",
        "titel_en": "Legal basis for every processing operation",
        "beschreibung": (
            "Jede Verarbeitung personenbezogener Daten erfordert eine Rechtsgrundlage "
            "nach Art. 6 DSGVO: Einwilligung, Vertrag, rechtliche Verpflichtung, "
            "lebenswichtige Interessen, öffentliche Aufgabe oder berechtigte Interessen."
        ),
        "beschreibung_en": (
            "Every processing of personal data requires a legal basis under Art. 6 GDPR: "
            "consent, contract, legal obligation, vital interests, public task or legitimate "
            "interests."
        ),
        "hinweise": (
            "Mapping aller Verarbeitungen auf Rechtsgrundlagen; "
            "Berechtigte-Interessen-Abwägung dokumentieren (Art. 6 Abs. 1 lit. f); "
            "Einwilligungsverwaltungssystem (Consent Management); "
            "Kein Rückgriff auf berechtigte Interessen bei Behörden."
        ),
        "hinweise_en": (
            "Map every processing operation to a legal basis; Document the legitimate "
            "interests balancing test (Art. 6(1) point (f)); Consent management system; No "
            "reliance on legitimate interests by public authorities."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-09",
        "kapitel": "GDS1",
        "ref": "Art. 7 DSGVO",
        "ref_en": "Art. 7 GDPR",
        "titel": "Einwilligungsmanagement – Freiwilligkeit und Widerruf",
        "titel_en": "Consent management – freely given consent and withdrawal",
        "beschreibung": (
            "Wenn die Einwilligung als Rechtsgrundlage genutzt wird, muss diese "
            "freiwillig, spezifisch, informiert und unmissverständlich sein. "
            "Der Widerruf muss jederzeit möglich sein."
        ),
        "beschreibung_en": (
            "Where consent is used as the legal basis, it must be freely given, specific, "
            "informed and unambiguous. It must be possible to withdraw it at any time."
        ),
        "hinweise": (
            "Klare, granulare Einwilligungstexte ohne Vorgabehäkchen; "
            "Nachweis der erteilten Einwilligung (Zeitstempel, Version); "
            "Einfacher Widerrufsmechanismus; "
            "Keine Kopplung von Einwilligung an Vertrag (Art. 7 Abs. 4 DSGVO)."
        ),
        "hinweise_en": (
            "Clear, granular consent wording without pre-ticked boxes; Evidence of the consent "
            "given (time stamp, version); Simple withdrawal mechanism; No bundling of consent "
            "with a contract (Art. 7(4) GDPR)."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS1-10",
        "kapitel": "GDS1",
        "ref": "Art. 9 DSGVO",
        "ref_en": "Art. 9 GDPR",
        "titel": "Besondere Kategorien personenbezogener Daten",
        "titel_en": "Special categories of personal data",
        "beschreibung": (
            "Die Verarbeitung sensibler Datenkategorien (Gesundheit, Herkunft, Religion, "
            "biometrische Daten etc.) ist grundsätzlich verboten und nur in engen "
            "Ausnahmen nach Art. 9 Abs. 2 DSGVO zulässig."
        ),
        "beschreibung_en": (
            "The processing of sensitive categories of data (health, origin, religion, "
            "biometric data, etc.) is prohibited in principle and permitted only within the "
            "narrow exceptions of Art. 9(2) GDPR."
        ),
        "hinweise": (
            "Inventar sensibler Datenkategorien; "
            "Explizite Rechtsgrundlage nach Art. 9 Abs. 2 für jede Verarbeitung; "
            "Erhöhte Sicherheitsmaßnahmen für sensible Daten; "
            "DSFA regelmäßig erforderlich (Art. 35 Abs. 3 lit. b DSGVO)."
        ),
        "hinweise_en": (
            "Inventory of sensitive categories of data; Explicit legal basis under Art. 9(2) "
            "for every processing operation; Heightened security measures for sensitive data; "
            "A DPIA is regularly required (Art. 35(3) point (b) GDPR)."
        ),
        "gewichtung": 3,
    },
    # ── GDS2: Betroffenenrechte ───────────────────────────────────────────────
    {
        "id": "GDS2-01",
        "kapitel": "GDS2",
        "ref": "Art. 12–14 DSGVO",
        "ref_en": "Art. 12–14 GDPR",
        "titel": "Informationspflichten bei Datenerhebung",
        "titel_en": "Information obligations when data is collected",
        "beschreibung": (
            "Betroffene Personen müssen bei der Erhebung ihrer Daten transparent "
            "informiert werden: Verantwortlicher, Zwecke, Rechtsgrundlagen, "
            "Empfänger, Speicherdauer, Betroffenenrechte und Beschwerderecht."
        ),
        "beschreibung_en": (
            "Data subjects must be informed transparently when their data is collected: "
            "controller, purposes, legal bases, recipients, storage period, rights of the data "
            "subject and the right to lodge a complaint."
        ),
        "hinweise": (
            "Datenschutzerklärung / Datenschutzhinweise (Layer-1 und Layer-2); "
            "Informationen verständlich, leicht zugänglich, kostenlos; "
            "Bei indirekter Erhebung: Information innerhalb eines Monats; "
            "Unterscheidung: direkte Erhebung (Art. 13) vs. indirekte Erhebung (Art. 14)."
        ),
        "hinweise_en": (
            "Privacy policy / privacy notice (layer 1 and layer 2); Information intelligible, "
            "easily accessible and free of charge; Where the data is not obtained from the "
            "data subject: inform within one month; Distinguish collection from the data "
            "subject (Art. 13) from collection from other sources (Art. 14)."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS2-02",
        "kapitel": "GDS2",
        "ref": "Art. 15 DSGVO",
        "ref_en": "Art. 15 GDPR",
        "titel": "Auskunftsrecht – Prozess zur Bearbeitung von Anfragen",
        "titel_en": "Right of access – process for handling requests",
        "beschreibung": (
            "Betroffene haben das Recht, Auskunft über ihre verarbeiteten Daten zu erhalten: "
            "Kategorien, Zwecke, Empfänger, Speicherdauer, Rechte, Herkunft der Daten "
            "und Informationen zu automatisierten Entscheidungen."
        ),
        "beschreibung_en": (
            "Data subjects have the right to obtain access to the data processed about them: "
            "categories, purposes, recipients, storage period, rights, the source of the data "
            "and information on automated decision-making."
        ),
        "hinweise": (
            "Definierter Prozess zur Bearbeitung von Auskunftsanfragen; "
            "Identitätsverifikation der anfragenden Person; "
            "Antwortfrist: 1 Monat (verlängerbar auf 3 Monate mit Begründung); "
            "Kostenfreiheit (außer bei offensichtlich unbegründeten/exzessiven Anfragen)."
        ),
        "hinweise_en": (
            "Defined process for handling access requests; Verification of the requesting "
            "person's identity; Deadline for replying: one month (extendable to three months "
            "with reasons); Free of charge (except for manifestly unfounded or excessive "
            "requests)."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS2-03",
        "kapitel": "GDS2",
        "ref": "Art. 16–17 DSGVO",
        "ref_en": "Art. 16–17 GDPR",
        "titel": "Berichtigung und Löschung ('Recht auf Vergessenwerden')",
        "titel_en": "Rectification and erasure ('right to be forgotten')",
        "beschreibung": (
            "Betroffene haben das Recht auf Berichtigung unrichtiger Daten (Art. 16) "
            "und auf Löschung ihrer Daten unter bestimmten Voraussetzungen (Art. 17), "
            "z.B. wenn der Zweck entfallen ist oder die Einwilligung widerrufen wurde."
        ),
        "beschreibung_en": (
            "Data subjects have the right to rectification of inaccurate data (Art. 16) and to "
            "erasure of their data under certain conditions (Art. 17), for example where the "
            "purpose no longer applies or consent has been withdrawn."
        ),
        "hinweise": (
            "Prozess zur Bearbeitung von Lösch- und Berichtigungsanfragen; "
            "Kaskaden-Löschung: Unterauftragsverhältnisse informieren; "
            "Löschprotokolle führen; "
            "Ausnahmen dokumentieren (gesetzliche Aufbewahrungspflichten)."
        ),
        "hinweise_en": (
            "Process for handling erasure and rectification requests; Cascading erasure: "
            "inform sub-processors; Keep erasure logs; Document the exceptions (statutory "
            "retention obligations)."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS2-04",
        "kapitel": "GDS2",
        "ref": "Art. 18–19 DSGVO",
        "ref_en": "Art. 18–19 GDPR",
        "titel": "Einschränkung der Verarbeitung und Mitteilungspflicht",
        "titel_en": "Restriction of processing and notification obligation",
        "beschreibung": (
            "Betroffene können die Einschränkung der Verarbeitung verlangen (Art. 18), "
            "z.B. während der Überprüfung einer Berichtigung. Der Verantwortliche muss "
            "Empfänger über Berichtigungen/Löschungen informieren (Art. 19)."
        ),
        "beschreibung_en": (
            "Data subjects can request the restriction of processing (Art. 18), for example "
            "while a rectification is being verified. The controller must inform recipients of "
            "rectifications and erasures (Art. 19)."
        ),
        "hinweise": (
            "Technische Umsetzung der 'Einschränkung' (z.B. Markierung, Separierung); "
            "Mitteilungsprozess an Empfänger bei Berichtigungen/Löschungen; "
            "Aufhebung der Einschränkung mit Vorabinformation; "
            "Dokumentation aller Einschränkungsanfragen."
        ),
        "hinweise_en": (
            "Technical implementation of the 'restriction' (e.g. flagging, separation); "
            "Notification process towards recipients in the event of rectification or erasure; "
            "Lifting of the restriction with prior information to the data subject; "
            "Documentation of all restriction requests."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS2-05",
        "kapitel": "GDS2",
        "ref": "Art. 20 DSGVO",
        "ref_en": "Art. 20 GDPR",
        "titel": "Recht auf Datenübertragbarkeit",
        "titel_en": "Right to data portability",
        "beschreibung": (
            "Betroffene haben bei Verarbeitung auf Basis der Einwilligung oder zur "
            "Vertragserfüllung das Recht, ihre Daten in maschinenlesbarem Format zu erhalten "
            "und an einen anderen Verantwortlichen zu übertragen."
        ),
        "beschreibung_en": (
            "Where processing is based on consent or on the performance of a contract, data "
            "subjects have the right to receive their data in a machine-readable format and to "
            "transmit it to another controller."
        ),
        "hinweise": (
            "Export-Funktion für personenbezogene Daten in strukturiertem Format (JSON, CSV, XML); "
            "Direkte Übertragung an anderen Verantwortlichen, wenn technisch möglich; "
            "Gilt nur für automatisiert verarbeitete Daten; "
            "Keine Beeinträchtigung der Rechte anderer Personen."
        ),
        "hinweise_en": (
            "Export function for personal data in a structured format (JSON, CSV, XML); Direct "
            "transmission to another controller where technically feasible; Applies only to "
            "data processed by automated means; No adverse effect on the rights of other "
            "persons."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS2-06",
        "kapitel": "GDS2",
        "ref": "Art. 21–22 DSGVO",
        "ref_en": "Art. 21–22 GDPR",
        "titel": "Widerspruchsrecht und automatisierte Entscheidungsfindung",
        "titel_en": "Right to object and automated decision-making",
        "beschreibung": (
            "Betroffene haben das Recht, der Verarbeitung zu widersprechen (Art. 21), "
            "insbesondere bei Direktwerbung. Art. 22 schützt vor rein automatisierten "
            "Entscheidungen mit erheblicher Auswirkung."
        ),
        "beschreibung_en": (
            "Data subjects have the right to object to processing (Art. 21), in particular for "
            "direct marketing. Art. 22 protects against decisions based solely on automated "
            "processing that have a significant effect."
        ),
        "hinweise": (
            "Opt-out-Mechanismus für Direktwerbung und Profiling; "
            "Dokumentation von Widersprüchen und Konsequenzen; "
            "Bei automatisierten Entscheidungen: Recht auf Überprüfung durch Menschen; "
            "Information über automatisierte Entscheidungsprozesse (Art. 13/14 Abs. 2 lit. f)."
        ),
        "hinweise_en": (
            "Opt-out mechanism for direct marketing and profiling; Documentation of objections "
            "and the consequences drawn from them; For automated decisions: right to review by "
            "a human being; Information about automated decision-making processes (Art. "
            "13/14(2) point (f))."
        ),
        "gewichtung": 2,
    },
    # ── GDS3: Pflichten des Verantwortlichen ──────────────────────────────────
    {
        "id": "GDS3-01",
        "kapitel": "GDS3",
        "ref": "Art. 24 DSGVO",
        "ref_en": "Art. 24 GDPR",
        "titel": "Verantwortung des Verantwortlichen – Datenschutz-Governance",
        "titel_en": "Responsibility of the controller – data protection governance",
        "beschreibung": (
            "Der Verantwortliche muss geeignete technische und organisatorische Maßnahmen "
            "implementieren und nachweisen können, dass die Verarbeitung gemäß DSGVO erfolgt. "
            "Richtlinien müssen regelmäßig überprüft und aktualisiert werden."
        ),
        "beschreibung_en": (
            "The controller must implement appropriate technical and organisational measures "
            "and be able to demonstrate that the processing is carried out in accordance with "
            "the GDPR. Policies must be reviewed and updated regularly."
        ),
        "hinweise": (
            "Datenschutz-Policy und interne Richtlinien; "
            "Management-Commitment zum Datenschutz; "
            "Regelmäßige Überprüfung und Aktualisierung der Maßnahmen; "
            "Schulungen und Awareness-Programme für Mitarbeiter."
        ),
        "hinweise_en": (
            "Data protection policy and internal guidelines; Management commitment to data "
            "protection; Regular review and updating of the measures; Training and awareness "
            "programmes for staff."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS3-02",
        "kapitel": "GDS3",
        "ref": "Art. 25 DSGVO",
        "ref_en": "Art. 25 GDPR",
        "titel": "Datenschutz durch Technikgestaltung und durch datenschutzfreundliche Voreinstellungen",
        "titel_en": "Data protection by design and data protection by default",
        "beschreibung": (
            "Privacy by Design: Datenschutz muss bereits bei der Konzeption von Systemen "
            "und Prozessen berücksichtigt werden. Privacy by Default: Die datenschutzfreundlichste "
            "Option muss die Voreinstellung sein."
        ),
        "beschreibung_en": (
            "Data protection by design: data protection must be taken into account as early as "
            "the design of systems and processes. Data protection by default: the most "
            "privacy-friendly option must be the default setting."
        ),
        "hinweise": (
            "Privacy-by-Design-Checkliste für neue Produkte und Prozesse; "
            "Datenschutzfreundliche Voreinstellungen (kein Opt-out erforderlich); "
            "Datenminimierung als Designprinzip; "
            "Privacy Impact Assessment (PIA) als fester Prozessschritt."
        ),
        "hinweise_en": (
            "Data protection by design checklist for new products and processes; "
            "Privacy-friendly default settings (no opt-out required); Data minimisation as a "
            "design principle; Privacy impact assessment (PIA) as a fixed step in the process."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS3-03",
        "kapitel": "GDS3",
        "ref": "Art. 26 DSGVO",
        "ref_en": "Art. 26 GDPR",
        "titel": "Gemeinsam Verantwortliche – Vereinbarung und Transparenz",
        "titel_en": "Joint controllers – arrangement and transparency",
        "beschreibung": (
            "Wenn zwei oder mehr Verantwortliche gemeinsam über Zwecke und Mittel "
            "der Verarbeitung entscheiden, müssen sie eine transparente Vereinbarung "
            "treffen und das Wesentliche den Betroffenen mitteilen."
        ),
        "beschreibung_en": (
            "Where two or more controllers jointly determine the purposes and means of the "
            "processing, they must enter into a transparent arrangement and make the essence "
            "of it available to the data subjects."
        ),
        "hinweise": (
            "Prüfung aller Verarbeitungen auf gemeinsame Verantwortlichkeit; "
            "Schriftliche Vereinbarung nach Art. 26 DSGVO; "
            "Anlaufstelle für Betroffene bestimmen; "
            "Inhalt der Vereinbarung in Datenschutzerklärung kommunizieren."
        ),
        "hinweise_en": (
            "Review all processing operations for joint controllership; Written arrangement "
            "under Art. 26 GDPR; Designate a contact point for data subjects; Communicate the "
            "content of the arrangement in the privacy policy."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS3-04",
        "kapitel": "GDS3",
        "ref": "Art. 28 DSGVO",
        "ref_en": "Art. 28 GDPR",
        "titel": "Auftragsverarbeitung – AVV und Kontrolle der Auftragsverarbeiter",
        "titel_en": "Processing on behalf of a controller – DPA and oversight of processors",
        "beschreibung": (
            "Wenn Dritte im Auftrag des Verantwortlichen personenbezogene Daten verarbeiten, "
            "ist ein Auftragsverarbeitungsvertrag (AVV) nach Art. 28 DSGVO erforderlich. "
            "Der Auftragsverarbeiter muss hinreichende Garantien bieten."
        ),
        "beschreibung_en": (
            "Where third parties process personal data on behalf of the controller, a data "
            "processing agreement (DPA) under Art. 28 GDPR is required. The processor must "
            "provide sufficient guarantees."
        ),
        "hinweise": (
            "AVV mit allen Auftragsverarbeitern abschließen (Mindestinhalt Art. 28 Abs. 3); "
            "Due Diligence der Auftragsverarbeiter vor Beauftragung; "
            "Unterauftragsverarbeiter-Genehmigung regeln; "
            "Regelmäßige Überprüfung der Auftragsverarbeiter (Audits, Zertifizierungen)."
        ),
        "hinweise_en": (
            "Conclude a DPA with every processor (minimum content: Art. 28(3)); Due diligence "
            "on processors before engaging them; Govern the authorisation of sub-processors; "
            "Review the processors regularly (audits, certifications)."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS3-05",
        "kapitel": "GDS3",
        "ref": "Art. 30 DSGVO",
        "ref_en": "Art. 30 GDPR",
        "titel": "Verzeichnis von Verarbeitungstätigkeiten (VVT)",
        "titel_en": "Record of processing activities (RoPA)",
        "beschreibung": (
            "Verantwortliche (und Auftragsverarbeiter) müssen ein Verzeichnis aller "
            "Verarbeitungstätigkeiten führen, das Angaben zu Zwecken, Kategorien, "
            "Empfängern, Löschfristen und technisch-organisatorischen Maßnahmen enthält."
        ),
        "beschreibung_en": (
            "Controllers (and processors) must maintain a record of all processing activities "
            "containing information on purposes, categories, recipients, erasure periods and "
            "technical and organisational measures."
        ),
        "hinweise": (
            "VVT in strukturierter, aktueller Form (Art. 30 Abs. 1); "
            "Alle Verarbeitungen vollständig erfassen; "
            "Regelmäßige Aktualisierung (insb. bei neuen Verarbeitungen); "
            "VVT auf Anfrage der Aufsichtsbehörde vorlegen können."
        ),
        "hinweise_en": (
            "RoPA in a structured and up-to-date form (Art. 30(1)); Record all processing "
            "operations completely; Update regularly (in particular for new processing "
            "operations); Be able to make the RoPA available to the supervisory authority on "
            "request."
        ),
        "gewichtung": 3,
    },
    # ── GDS4: Technische & organisatorische Maßnahmen ─────────────────────────
    {
        "id": "GDS4-01",
        "kapitel": "GDS4",
        "ref": "Art. 32 Abs. 1 lit. a DSGVO",
        "ref_en": "Art. 32(1) point (a) GDPR",
        "titel": "Pseudonymisierung und Verschlüsselung personenbezogener Daten",
        "titel_en": "Pseudonymisation and encryption of personal data",
        "beschreibung": (
            "Als geeignete Maßnahme zur Datensicherheit ist die Pseudonymisierung "
            "und Verschlüsselung personenbezogener Daten zu implementieren, um "
            "ein dem Risiko angemessenes Schutzniveau zu gewährleisten."
        ),
        "beschreibung_en": (
            "As an appropriate measure for data security, the pseudonymisation and encryption "
            "of personal data is to be implemented in order to ensure a level of protection "
            "appropriate to the risk."
        ),
        "hinweise": (
            "Verschlüsselung ruhender Daten (AES-256 o.ä.); "
            "Verschlüsselung bei Übertragung (TLS 1.2+); "
            "Pseudonymisierungsverfahren wo möglich; "
            "Schlüsselverwaltungskonzept."
        ),
        "hinweise_en": (
            "Encryption of data at rest (AES-256 or similar); Encryption in transit (TLS "
            "1.2+); Pseudonymisation procedures wherever possible; Key management concept."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS4-02",
        "kapitel": "GDS4",
        "ref": "Art. 32 Abs. 1 lit. b DSGVO",
        "ref_en": "Art. 32(1) point (b) GDPR",
        "titel": "Dauerhafter Schutz von Vertraulichkeit, Integrität, Verfügbarkeit und Belastbarkeit",
        "titel_en": "Ongoing confidentiality, integrity, availability and resilience",
        "beschreibung": (
            "Es müssen Maßnahmen getroffen werden, die dauerhaft die Vertraulichkeit, "
            "Integrität, Verfügbarkeit und Belastbarkeit der Verarbeitungssysteme "
            "und -dienste gewährleisten."
        ),
        "beschreibung_en": (
            "Measures must be taken that ensure the ongoing confidentiality, integrity, "
            "availability and resilience of the processing systems and services."
        ),
        "hinweise": (
            "Zugriffskontrollen (RBAC, MFA); "
            "Integritätsprüfungen der Daten; "
            "Redundanz und Failover-Konzepte; "
            "Business-Continuity-Planung für Datenverarbeitungssysteme."
        ),
        "hinweise_en": (
            "Access controls (RBAC, MFA); Integrity checks on the data; Redundancy and "
            "failover concepts; Business continuity planning for data processing systems."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS4-03",
        "kapitel": "GDS4",
        "ref": "Art. 32 Abs. 1 lit. c DSGVO",
        "ref_en": "Art. 32(1) point (c) GDPR",
        "titel": "Wiederherstellbarkeit nach Datenpannen",
        "titel_en": "Ability to restore data after an incident",
        "beschreibung": (
            "Es muss die Fähigkeit bestehen, Verfügbarkeit und Zugang zu "
            "personenbezogenen Daten bei einem physischen oder technischen Zwischenfall "
            "rasch wiederherstellen zu können."
        ),
        "beschreibung_en": (
            "There must be the ability to restore the availability of and access to personal "
            "data in a timely manner in the event of a physical or technical incident."
        ),
        "hinweise": (
            "Backup-Konzept mit regelmäßigen Tests; "
            "Disaster-Recovery-Plan für personenbezogene Daten; "
            "Dokumentierte Recovery Time Objective (RTO) und Recovery Point Objective (RPO); "
            "Regelmäßige Wiederherstellungstests."
        ),
        "hinweise_en": (
            "Backup concept with regular tests; Disaster recovery plan for personal data; "
            "Documented recovery time objective (RTO) and recovery point objective (RPO); "
            "Regular restore tests."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS4-04",
        "kapitel": "GDS4",
        "ref": "Art. 32 Abs. 1 lit. d DSGVO",
        "ref_en": "Art. 32(1) point (d) GDPR",
        "titel": "Überprüfung und Bewertung der Sicherheitsmaßnahmen",
        "titel_en": "Testing and evaluating the security measures",
        "beschreibung": (
            "Es muss ein Verfahren zur regelmäßigen Überprüfung, Bewertung und "
            "Evaluierung der Wirksamkeit der technischen und organisatorischen "
            "Maßnahmen zur Gewährleistung der Sicherheit der Verarbeitung existieren."
        ),
        "beschreibung_en": (
            "There must be a process for regularly testing, assessing and evaluating the "
            "effectiveness of the technical and organisational measures for ensuring the "
            "security of the processing."
        ),
        "hinweise": (
            "Jährliche Datenschutzaudits (intern und/oder extern); "
            "Penetrationstests für datenschutzrelevante Systeme; "
            "Schwachstellenmanagement; "
            "Dokumentation der Prüfergebnisse und Maßnahmen."
        ),
        "hinweise_en": (
            "Annual data protection audits (internal and/or external); Penetration tests for "
            "systems relevant to data protection; Vulnerability management; Documentation of "
            "the test results and of the measures taken."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS4-05",
        "kapitel": "GDS4",
        "ref": "Art. 32 Abs. 4 DSGVO",
        "ref_en": "Art. 32(4) GDPR",
        "titel": "Mitarbeiterverpflichtung – Zugang nur für autorisierte Personen",
        "titel_en": "Obligation of staff – access only for authorised persons",
        "beschreibung": (
            "Personen, die Zugang zu personenbezogenen Daten haben, dürfen diese "
            "nur auf Weisung des Verantwortlichen verarbeiten, es sei denn, "
            "sie sind durch das Unionsrecht oder das Recht der Mitgliedstaaten dazu verpflichtet."
        ),
        "beschreibung_en": (
            "Persons who have access to personal data may process it only on instructions from "
            "the controller, unless they are required to do so by Union or Member State law."
        ),
        "hinweise": (
            "Verpflichtung zur Vertraulichkeit / Datengeheimnis; "
            "Need-to-Know-Prinzip bei Zugriffsrechten; "
            "Regelmäßige Datenschutzschulungen für alle Mitarbeiter; "
            "Offboarding-Prozess mit sofortigem Entzug der Zugriffsrechte."
        ),
        "hinweise_en": (
            "Confidentiality undertaking / commitment to data secrecy; Need-to-know principle "
            "for access rights; Regular data protection training for all staff; Offboarding "
            "process with immediate withdrawal of access rights."
        ),
        "gewichtung": 2,
    },
    # ── GDS5: Meldepflichten & DSFA ───────────────────────────────────────────
    {
        "id": "GDS5-01",
        "kapitel": "GDS5",
        "ref": "Art. 33 DSGVO",
        "ref_en": "Art. 33 GDPR",
        "titel": "Meldung von Datenschutzverletzungen an die Aufsichtsbehörde",
        "titel_en": "Notification of a personal data breach to the supervisory authority",
        "beschreibung": (
            "Datenschutzverletzungen müssen unverzüglich (in der Regel innerhalb von "
            "72 Stunden) der zuständigen Aufsichtsbehörde gemeldet werden, sofern die "
            "Verletzung voraussichtlich zu einem Risiko für natürliche Personen führt."
        ),
        "beschreibung_en": (
            "Personal data breaches must be notified to the competent supervisory authority "
            "without undue delay (as a rule within 72 hours), where the breach is likely to "
            "result in a risk to natural persons."
        ),
        "hinweise": (
            "Incident-Response-Prozess mit klarer Klassifizierungspflicht; "
            "Risikoabschätzung nach Datenpanne (Risiko vs. kein Risiko vs. hohes Risiko); "
            "72-Stunden-Frist einhalten – Meldung auch bei unvollständiger Information; "
            "Meldekontakt: die zuständige Datenschutz-Aufsichtsbehörde "
            "(Art. 51/55) – nicht das BSI, das nach BSIG/NIS-2 meldet."
        ),
        "hinweise_en": (
            "Incident response process with a clear obligation to classify; Risk assessment "
            "after a personal data breach (risk vs. no risk vs. high risk); Meet the 72-hour "
            "deadline – notify even where the information is incomplete; Point of contact for "
            "notification: the competent data protection supervisory authority "
            "(Art. 51/55) – not the BSI, which receives reports under the "
            "German BSIG/NIS 2 regime."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS5-02",
        "kapitel": "GDS5",
        "ref": "Art. 34 DSGVO",
        "ref_en": "Art. 34 GDPR",
        "titel": "Benachrichtigung betroffener Personen bei hohem Risiko",
        "titel_en": "Communication to the data subjects where the risk is high",
        "beschreibung": (
            "Wenn eine Datenschutzverletzung voraussichtlich ein hohes Risiko für "
            "die Rechte und Freiheiten natürlicher Personen zur Folge hat, müssen "
            "die betroffenen Personen unverzüglich benachrichtigt werden."
        ),
        "beschreibung_en": (
            "Where a personal data breach is likely to result in a high risk to the rights and "
            "freedoms of natural persons, the data subjects must be informed without undue "
            "delay."
        ),
        "hinweise": (
            "Kriterien für 'hohes Risiko' definieren und dokumentieren; "
            "Benachrichtigungstext: Art der Verletzung, Kontaktdaten DSB, Konsequenzen, Maßnahmen; "
            "Ausnahmen prüfen (Maßnahmen vor Verletzung, Unverhältnismäßigkeit); "
            "Dokumentation aller Benachrichtigungen."
        ),
        "hinweise_en": (
            "Define and document the criteria for a 'high risk'; Content of the communication: "
            "nature of the breach, contact details of the DPO, likely consequences, measures "
            "taken; Check the exceptions (measures in place before the breach, "
            "disproportionate effort); Documentation of all communications."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS5-03",
        "kapitel": "GDS5",
        "ref": "Art. 33 Abs. 5 DSGVO",
        "ref_en": "Art. 33(5) GDPR",
        "titel": "Dokumentation aller Datenschutzverletzungen",
        "titel_en": "Documentation of every personal data breach",
        "beschreibung": (
            "Alle Datenschutzverletzungen müssen dokumentiert werden, einschließlich "
            "der damit verbundenen Fakten, Auswirkungen und ergriffenen Abhilfemaßnahmen, "
            "auch wenn keine Meldepflicht bestand."
        ),
        "beschreibung_en": (
            "All personal data breaches must be documented, including the facts relating to "
            "them, their effects and the remedial action taken, even where there was no "
            "obligation to notify."
        ),
        "hinweise": (
            "Datenschutzpannen-Register führen; "
            "Dokumentation: Zeitpunkt, Art der Verletzung, Betroffene, Auswirkungen, Maßnahmen; "
            "Aufbewahrung: Art. 33 Abs. 5 nennt keine Frist; Hausempfehlung "
            "mindestens 3 Jahre für Prüfzwecke; "
            "Auch 'Near-Miss'-Vorfälle erfassen."
        ),
        "hinweise_en": (
            "Maintain a register of personal data breaches; Documentation: time, nature of the "
            "breach, data subjects affected, effects, measures; Retention: Art. 33(5) "
            "names no period, in-house recommendation at least three years for "
            "audit purposes; Record 'near miss' incidents as well."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS5-04",
        "kapitel": "GDS5",
        "ref": "Art. 35 DSGVO",
        "ref_en": "Art. 35 GDPR",
        "titel": "Datenschutz-Folgenabschätzung (DSFA)",
        "titel_en": "Data protection impact assessment (DPIA)",
        "beschreibung": (
            "Vor Beginn einer Verarbeitung, die voraussichtlich ein hohes Risiko birgt, "
            "muss der Verantwortliche eine Datenschutz-Folgenabschätzung durchführen. "
            "Dies gilt insbesondere für Profiling, systematische Überwachung und "
            "Verarbeitung besonderer Datenkategorien in großem Umfang."
        ),
        "beschreibung_en": (
            "Before beginning processing that is likely to result in a high risk, the "
            "controller must carry out a data protection impact assessment. This applies in "
            "particular to profiling, systematic monitoring and the processing of special "
            "categories of data on a large scale."
        ),
        "hinweise": (
            "Screening-Prozess zur Identifikation DSFA-pflichtiger Verarbeitungen; "
            "Muss-Liste der zuständigen Aufsichtsbehörde beachten; "
            "DSFA-Inhalte: Verarbeitungsbeschreibung, Notwendigkeitsbewertung, Risikoabschätzung, Maßnahmen; "
            "Überprüfung bei wesentlichen Änderungen der Verarbeitung."
        ),
        "hinweise_en": (
            "Screening process for identifying processing operations that require a DPIA; "
            "Observe the mandatory list of the competent supervisory authority; Content of the "
            "DPIA: description of the processing, assessment of necessity, risk assessment, "
            "measures; Review where the processing changes substantially."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS5-05",
        "kapitel": "GDS5",
        "ref": "Art. 36 DSGVO",
        "ref_en": "Art. 36 GDPR",
        "titel": "Vorherige Konsultation der Aufsichtsbehörde bei hohem Restrisiko",
        "titel_en": (
            "Prior consultation of the supervisory authority where a high residual risk "
            "remains"
        ),
        "beschreibung": (
            "Ergibt die DSFA, dass die Verarbeitung ein hohes Risiko zur Folge hätte, "
            "sofern der Verantwortliche keine Maßnahmen trifft, muss vor Beginn der "
            "Verarbeitung die Aufsichtsbehörde konsultiert werden."
        ),
        "beschreibung_en": (
            "Where the DPIA indicates that the processing would result in a high risk in the "
            "absence of measures taken by the controller, the supervisory authority must be "
            "consulted before the processing begins."
        ),
        "hinweise": (
            "Klare Kriterien, wann Konsultation erforderlich; "
            "Fristen beachten: Aufsichtsbehörde hat 8 Wochen (+ 6 Wochen Verlängerung); "
            "Verarbeitungsbeginn erst nach Stellungnahme; "
            "Dokumentation des Konsultationsverfahrens."
        ),
        "hinweise_en": (
            "Clear criteria for when a consultation is required; Observe the deadlines: the "
            "supervisory authority has eight weeks (plus a six-week extension); Do not begin "
            "processing before the authority has given its advice; Documentation of the "
            "consultation procedure."
        ),
        "gewichtung": 2,
    },
    # ── GDS6: Datenschutzbeauftragter & Drittlandtransfer ─────────────────────
    {
        "id": "GDS6-01",
        "kapitel": "GDS6",
        "ref": "Art. 37 DSGVO",
        "ref_en": "Art. 37 GDPR",
        "titel": "Benennung eines Datenschutzbeauftragten (DSB)",
        "titel_en": "Designation of a data protection officer (DPO)",
        "beschreibung": (
            "Ein DSB muss benannt werden, wenn: (a) öffentliche Stelle, "
            "(b) umfangreiche regelmäßige und systematische Überwachung von Personen, "
            "oder (c) umfangreiche Verarbeitung besonderer Datenkategorien. "
            "Freiwillige Benennung ist jederzeit möglich und empfohlen."
        ),
        "beschreibung_en": (
            "A DPO must be designated where: (a) the organisation is a public authority, (b) "
            "it carries out regular and systematic monitoring of individuals on a large scale, "
            "or (c) it processes special categories of data on a large scale. A voluntary "
            "designation is possible at any time and is recommended."
        ),
        "hinweise": (
            "Prüfung der Benennungspflicht anhand Art. 37 DSGVO; "
            "DSB intern oder extern bestellen; "
            "Kontaktdaten des DSB veröffentlichen und bei Aufsichtsbehörde melden; "
            "DSB muss Fachwissen in Datenschutzrecht und -praxis besitzen."
        ),
        "hinweise_en": (
            "Assess the obligation to designate against Art. 37 GDPR; Appoint the DPO "
            "internally or externally; Publish the DPO's contact details and communicate them "
            "to the supervisory authority; The DPO must have expert knowledge of data "
            "protection law and practice."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS6-02",
        "kapitel": "GDS6",
        "ref": "Art. 38–39 DSGVO",
        "ref_en": "Art. 38–39 GDPR",
        "titel": "Aufgaben und Stellung des Datenschutzbeauftragten",
        "titel_en": "Tasks and position of the data protection officer",
        "beschreibung": (
            "Der DSB muss ordnungsgemäß in alle Datenschutzfragen eingebunden werden, "
            "hat umfassende Aufgaben (Beratung, Überwachung, DSFA-Beratung, Zusammenarbeit "
            "mit Aufsichtsbehörde) und genießt besonderen Schutz (kein Interessenkonflikt, "
            "keine Benachteiligung)."
        ),
        "beschreibung_en": (
            "The DPO must be properly involved in all data protection matters, has "
            "comprehensive tasks (advice, monitoring, advice on DPIAs, cooperation with the "
            "supervisory authority) and enjoys particular protection (no conflict of "
            "interests, no penalisation)."
        ),
        "hinweise": (
            "DSB frühzeitig in Projekte einbinden; "
            "Unabhängigkeit des DSB sicherstellen (kein Weisungsrecht in Datenschutzfragen); "
            "Ressourcen und Weiterbildung für DSB bereitstellen; "
            "Geheimhaltungspflicht des DSB beachten."
        ),
        "hinweise_en": (
            "Involve the DPO in projects at an early stage; Ensure the DPO's independence (no "
            "right to issue instructions on data protection matters); Provide the DPO with "
            "resources and further training; Observe the DPO's obligation of secrecy."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS6-03",
        "kapitel": "GDS6",
        "ref": "Art. 44–45 DSGVO",
        "ref_en": "Art. 44–45 GDPR",
        "titel": "Drittlandtransfer – Angemessenheitsbeschluss",
        "titel_en": "Third-country transfer – adequacy decision",
        "beschreibung": (
            "Übermittlungen personenbezogener Daten in Drittländer sind nur zulässig, "
            "wenn die Europäische Kommission ein angemessenes Schutzniveau festgestellt hat "
            "(Angemessenheitsbeschluss) oder geeignete Garantien bestehen."
        ),
        "beschreibung_en": (
            "Transfers of personal data to third countries are permitted only where the "
            "European Commission has decided that an adequate level of protection exists "
            "(adequacy decision) or where appropriate safeguards are in place."
        ),
        "hinweise": (
            "Inventar aller Datentransfers in Drittländer; "
            "Prüfung: Angemessenheitsbeschluss für Empfängerland vorhanden?; "
            "US-Transfer: Data Privacy Framework (DPF) seit 2023; "
            "Dokumentation der Transfergrundlage je Empfänger."
        ),
        "hinweise_en": (
            "Inventory of all data transfers to third countries; Check: is there an adequacy "
            "decision for the recipient country?; Transfers to the US: Data Privacy Framework "
            "(DPF) since 2023; Document the basis for the transfer for each recipient."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS6-04",
        "kapitel": "GDS6",
        "ref": "Art. 46 DSGVO",
        "ref_en": "Art. 46 GDPR",
        "titel": "Drittlandtransfer – Standardvertragsklauseln (SCC) und BCR",
        "titel_en": "Third-country transfer – standard contractual clauses (SCC) and BCR",
        "beschreibung": (
            "Ohne Angemessenheitsbeschluss sind Drittlandtransfers nur mit geeigneten "
            "Garantien zulässig: EU-Standardvertragsklauseln (SCC, 2021er Fassung), "
            "verbindliche interne Datenschutzvorschriften (BCR) oder genehmigte Verhaltensregeln."
        ),
        "beschreibung_en": (
            "Without an adequacy decision, third-country transfers are permitted only with "
            "appropriate safeguards: EU standard contractual clauses (SCC, 2021 version), "
            "binding corporate rules (BCR) or approved codes of conduct."
        ),
        "hinweise": (
            "SCC 2021 (Beschluss (EU) 2021/914) für alle Transfers ohne Angemessenheitsbeschluss; "
            "Transfer Impact Assessment (TIA) als Pflichtbestandteil; "
            "BCR für Konzernintere Transfers in Betracht ziehen; "
            "Regelmäßige Überprüfung der Transfergarantien auf Aktualität."
        ),
        "hinweise_en": (
            "SCC 2021 (Decision (EU) 2021/914) for all transfers without an adequacy decision; "
            "Transfer impact assessment (TIA) as a mandatory component; Consider BCR for "
            "intra-group transfers; Review the transfer safeguards regularly to confirm they "
            "are still current."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS6-05",
        "kapitel": "GDS6",
        "ref": "Art. 83 DSGVO",
        "ref_en": "Art. 83 GDPR",
        "titel": "Bußgeldrisiken und Sanktionsregime – Compliance-Monitoring",
        "titel_en": "Fine exposure and the regime of sanctions – compliance monitoring",
        "beschreibung": (
            "Verstöße gegen die DSGVO können mit Bußgeldern bis zu 20 Mio. € bzw. "
            "4% des weltweiten Jahresumsatzes geahndet werden. Ein systematisches "
            "Compliance-Monitoring ist essentiell zur Risikovermeidung."
        ),
        "beschreibung_en": (
            "Infringements of the GDPR can be punished with fines of up to EUR 20 million or "
            "4% of total worldwide annual turnover. Systematic compliance monitoring is "
            "essential in order to avoid that risk."
        ),
        "hinweise": (
            "Systematisches Datenschutz-Compliance-Programm; "
            "Regelmäßige interne Datenschutzaudits; "
            "Eskalationsprozess bei Datenschutzvorfällen; "
            "Dokumentation als Entlastungsnachweis (Art. 83 Abs. 2 lit. k)."
        ),
        "hinweise_en": (
            "Systematic data protection compliance programme; Regular internal data protection "
            "audits; Escalation process for data protection incidents; Documentation as "
            "exculpatory evidence (Art. 83(2) point (k))."
        ),
        "gewichtung": 3,
    },
]


_STANDARD_IDS: frozenset[str] = frozenset(r["id"] for r in DSGVO_ANFORDERUNGEN)


def anforderungen_by_kapitel() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict]] = {k: [] for k in KAPITEL}
    for req in DSGVO_ANFORDERUNGEN:
        result[req["kapitel"]].append(req)
    return result


def load_merged_anforderungen(db_path: Path | None = None, *,
                              sprache: str | None = None,
                              ) -> list[dict[str, Any]]:
    """Gibt den vollständigen Anforderungskatalog zurück.

    Standardanforderungen werden durch DB-Einträge überschrieben (gleiche ID),
    neue DB-Einträge werden am Ende des jeweiligen Kapitels angefügt.
    """
    base: dict[str, dict[str, Any]] = {
        r["id"]: dict(r, _quelle="standard") for r in DSGVO_ANFORDERUNGEN
    }

    if db_path is not None:
        try:
            from dsgvo.db import load_custom_anforderungen
            for custom in load_custom_anforderungen(db_path):
                rid = custom["id"]
                quelle = "override" if custom.get("ist_override") else "custom"
                entry = {
                    "id": rid,
                    "kapitel": custom["kapitel"],
                    "ref": custom["ref"],
                    "titel": custom["titel"],
                    "beschreibung": custom["beschreibung"],
                    "hinweise": custom["hinweise"],
                    "gewichtung": int(custom["gewichtung"]),
                    "_quelle": quelle,
                }
                base[rid] = entry
        except Exception:
            pass

    kap_order = {k: i for i, k in enumerate(KAPITEL)}
    aus = sorted(base.values(),
                 key=lambda r: (kap_order.get(r.get("kapitel", "GDS6"), 99),
                                r["id"]))
    # #1954: siehe shared/katalog_sprache — nur titel/beschreibung.
    return _ks.uebersetze_viele(aus, sprache or "")


def berechne_reifegrad(
    bewertungen: dict[str, int],
    anforderungen: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if anforderungen is None:
        anforderungen = DSGVO_ANFORDERUNGEN

    by_kapitel: dict[str, list[float]] = {k: [] for k in KAPITEL}
    total_pct: list[float] = []

    for req in anforderungen:
        rid = req["id"]
        gewichtung = req.get("gewichtung", 1)
        bew = bewertungen.get(rid, 0)
        if bew == 0:
            continue
        reife_pct = BEWERTUNG_SKALA[bew]["reife_pct"]
        by_kapitel.setdefault(req["kapitel"], []).extend([reife_pct] * gewichtung)
        total_pct.extend([reife_pct] * gewichtung)

    gesamt_pct = (sum(total_pct) / len(total_pct)) if total_pct else 0.0
    kapitel_pct = {
        k: (sum(vals) / len(vals)) if vals else 0.0
        for k, vals in by_kapitel.items()
    }

    if gesamt_pct >= 70:
        ampel = "gruen"
    elif gesamt_pct >= 40:
        ampel = "orange"
    else:
        ampel = "rot"

    bewertete = sum(1 for rid in bewertungen if bewertungen[rid] > 0)

    return {
        "gesamt_pct": round(gesamt_pct, 1),
        "kapitel_pct": {k: round(v, 1) for k, v in kapitel_pct.items()},
        "ampel": ampel,
        "bewertete_count": bewertete,
        "gesamt_count": len(DSGVO_ANFORDERUNGEN),
    }
