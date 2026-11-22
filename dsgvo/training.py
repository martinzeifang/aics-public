"""DSGVO Annual Training Content Generator.

Generates a company-specific DSGVO annual training script + quiz as DOCX.
Content is structured per audience role. Each factual claim that can be
backed by evidence is cited; all other content is generic best-practice.

DIE SPRACHE GEHÖRT DEM MANDANTEN (#1954)
Die Unterlage wird im Haus des Mandanten vorgetragen, also entscheidet
``firmen.sprache`` über ihre Sprache und nicht der Bearbeiter, der sie zufällig
erzeugt — aufgelöst über ``shared.reports.texte.aufloesen``, fail-open auf
Deutsch.

**Jede Aussage muss der deutschen entsprechen.** Eine Schulung, die im
Englischen etwas anderes lehrt als im Deutschen, ist schlimmer als keine: Sie
erzeugt zwei Belegschaften mit zwei Kenntnisständen und einen Nachweis, der für
beide gilt. Der Ton darf erklärend sein, die Lehre nicht. Wo der deutsche Text
fachlich schief liegt, folgt die englische Fassung ihm **wörtlich** und die
Abweichung wird gemeldet statt still korrigiert — sonst steht in zwei Sprachen
Verschiedenes und niemand weiß, welche gilt.

WO DIE ÜBERSETZUNG STEHT
Die Inhalte (``ZIELGRUPPEN``, ``TRAINING_OUTLINE``, ``QUIZ_FRAGEN``,
``SZENARIEN``) tragen ihre englische Fassung als ``*_en``-Feld **neben** der
deutschen (Muster ``ReportSpec.titel_en``): Wer eine Frage ändert, sieht die
Übersetzung im selben Atemzug. Ein eigener Katalog wäre die Spiegel-Liste aus
#1731/#1735 — und eine Quizfrage, deren Antwortbuchstabe nicht mehr zur Option
passt, fällt dort niemandem auf.

``antwort`` bleibt unübersetzt: Das ist ein **Datenwert** (``"B"``), der auf den
Buchstaben einer Option zeigt. Deshalb behalten ``optionen_en`` dieselbe
Reihenfolge und dieselben Buchstaben wie ``optionen`` — eine umgestellte
Antwortliste wäre eine falsche Musterlösung, und zwar eine, die richtig aussieht.

``ZIELGRUPPEN`` und ``TRAINING_OUTLINE`` speisen zusätzlich die
Auswahl-Oberfläche (``GET /api/dsgvo/training/outline``). Die ist
Bedienoberfläche und folgt weiter der deutschen Beschriftung; die ``*_en``-Felder
reisen additiv mit und werden dort heute nicht gelesen.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from shared.reports import texte as _rt


# ── Colours ───────────────────────────────────────────────────────────────────

_EU_BLUE   = "#003399"
_DARK      = "#1a237e"
_DRAFT_BG  = "#FFF9C4"
_DRAFT_FG  = "#5D4037"
_TOPIC_BG  = "#E8EAF6"
_QUIZ_BG   = "#E3F2FD"
_SZEN_BG   = "#FFF3E0"
_HR_COL    = "#880E4F"
_IT_COL    = "#1B5E20"
_MGMT_COL  = "#BF360C"
_ALL_COL   = "#003399"


# ── Audience roles ────────────────────────────────────────────────────────────

ZIELGRUPPEN: dict[str, dict[str, Any]] = {
    "alle": {
        "label": "Alle Mitarbeiter",
        "label_en": "All employees",
        "farbe": _ALL_COL,
        "beschreibung": "Datenschutz-Grundlagen für alle Beschäftigten",
        "beschreibung_en": "Data protection basics for all staff",
    },
    "hr": {
        "label": "Personal / HR",
        "label_en": "Human Resources / HR",
        "farbe": _HR_COL,
        "beschreibung": "Beschäftigtendatenschutz, Bewerberdaten, Onboarding/Offboarding",
        "beschreibung_en": "Employee data protection, applicant data, onboarding/offboarding",
    },
    "it": {
        "label": "IT / Technik",
        "label_en": "IT / Technology",
        "farbe": _IT_COL,
        "beschreibung": "Technische Maßnahmen, Datensicherheit, Protokollierung",
        "beschreibung_en": "Technical measures, data security, logging",
    },
    "management": {
        "label": "Führungskräfte / Management",
        "label_en": "Managers / Management",
        "farbe": _MGMT_COL,
        "beschreibung": "Verantwortlichkeit, Haftung, Datenschutz-Folgenabschätzung",
        "beschreibung_en": "Accountability, liability, data protection impact assessment",
    },
}


# ── Content outline ───────────────────────────────────────────────────────────

TRAINING_OUTLINE: dict[str, list[dict[str, Any]]] = {
    "alle": [
        {
            "id": "A1",
            "titel": "Was ist Datenschutz?",
            "titel_en": "What is data protection?",
            "dauer_min": 10,
            "inhalte": [
                "Definition personenbezogener Daten (Art. 4 Nr. 1 DSGVO)",
                "Besondere Kategorien personenbezogener Daten (Art. 9 DSGVO): Gesundheit, Religion, politische Meinung …",
                "Wer ist Verantwortlicher, wer Auftragsverarbeiter?",
                "Wichtigste Grundsätze: Zweckbindung, Datenminimierung, Speicherbegrenzung (Art. 5 DSGVO)",
            ],
            "inhalte_en": [
                "Definition of personal data (Art. 4(1) GDPR)",
                "Special categories of personal data (Art. 9 GDPR): health, religion, political opinions …",
                "Who is the controller, who is the processor?",
                "Key principles: purpose limitation, data minimisation, storage limitation (Art. 5 GDPR)",
            ],
            "lernziel": "Mitarbeiter können personenbezogene Daten erkennen und einordnen.",
            "lernziel_en": "Employees can recognise and classify personal data.",
        },
        {
            "id": "A2",
            "titel": "Rechtsgrundlagen der Datenverarbeitung",
            "titel_en": "Legal bases for data processing",
            "dauer_min": 8,
            "inhalte": [
                "Übersicht der sechs Rechtsgrundlagen nach Art. 6 DSGVO",
                "Einwilligung: Anforderungen, Widerruf, Double-Opt-in",
                "Vertragserfüllung und berechtigtes Interesse im Alltag",
                "Was passiert, wenn keine Rechtsgrundlage vorliegt?",
            ],
            "inhalte_en": [
                "Overview of the six legal bases under Art. 6 GDPR",
                "Consent: requirements, withdrawal, double opt-in",
                "Performance of a contract and legitimate interests in everyday work",
                "What happens if there is no legal basis?",
            ],
            "lernziel": "Mitarbeiter wissen, dass ohne Rechtsgrundlage keine Verarbeitung stattfinden darf.",
            "lernziel_en": "Employees know that no processing may take place without a legal basis.",
        },
        {
            "id": "A3",
            "titel": "Rechte der betroffenen Personen",
            "titel_en": "Rights of data subjects",
            "dauer_min": 10,
            "inhalte": [
                "Auskunftsrecht (Art. 15 DSGVO) – Bearbeitungsfrist 1 Monat",
                "Berichtigung (Art. 16) und Löschung / Recht auf Vergessenwerden (Art. 17)",
                "Einschränkung der Verarbeitung (Art. 18) und Datenübertragbarkeit (Art. 20)",
                "Widerspruchsrecht (Art. 21) insbesondere gegen Direktmarketing",
                "Ablauf bei eingehenden Betroffenenanfragen im Unternehmen",
            ],
            "inhalte_en": [
                "Right of access (Art. 15 GDPR) – one-month time limit for responding",
                "Rectification (Art. 16) and erasure / right to be forgotten (Art. 17)",
                "Restriction of processing (Art. 18) and data portability (Art. 20)",
                "Right to object (Art. 21), in particular to direct marketing",
                "Procedure for incoming data subject requests within the company",
            ],
            "lernziel": "Mitarbeiter wissen, wie Betroffenenanfragen intern weiterzuleiten sind und welche Fristen gelten.",
            "lernziel_en": "Employees know how to forward data subject requests internally and which time limits apply.",
        },
        {
            "id": "A4",
            "titel": "Datenschutz im Arbeitsalltag",
            "titel_en": "Data protection in everyday work",
            "dauer_min": 15,
            "inhalte": [
                "E-Mail: Kein Versand vertraulicher Daten unverschlüsselt",
                "Passwörter: Sichere Passwörter, kein Teilen, MFA wo möglich",
                "Bildschirmsperre bei Verlassen des Arbeitsplatzes (Clean Desk)",
                "Ausdrucke: Vertrauliche Dokumente nicht offen liegen lassen, sicheres Shreddern",
                "Mobile Geräte: Verschlüsselung, keine privaten Cloud-Dienste für Firmendaten",
                "Soziale Medien: Keine Firmendaten oder interne Infos öffentlich teilen",
                "Telearbeit / Homeoffice: Sicherung des Heimnetzwerks, VPN-Nutzung",
            ],
            "inhalte_en": [
                "Email: do not send confidential data unencrypted",
                "Passwords: strong passwords, no sharing, MFA wherever possible",
                "Lock the screen when leaving the workplace (clean desk)",
                "Printouts: do not leave confidential documents lying around, shred them securely",
                "Mobile devices: encryption, no private cloud services for company data",
                "Social media: do not share company data or internal information publicly",
                "Teleworking / home office: securing the home network, use of VPN",
            ],
            "lernziel": "Mitarbeiter können datenschutzrelevante Alltagssituationen erkennen und richtig handeln.",
            "lernziel_en": "Employees can recognise everyday situations relevant to data protection and act correctly.",
        },
        {
            "id": "A5",
            "titel": "Datenpannen – Erkennen und Melden",
            "titel_en": "Personal data breaches – recognising and reporting",
            "dauer_min": 8,
            "inhalte": [
                "Was ist eine Datenschutzverletzung? (Art. 4 Nr. 12 DSGVO)",
                "Beispiele: Verlust eines USB-Sticks, E-Mail an falschen Empfänger, Ransomware",
                "72-Stunden-Meldefrist an die Aufsichtsbehörde (Art. 33 DSGVO)",
                "Interner Meldeprozess: Wer ist sofort zu informieren?",
                "Dokumentationspflicht nach Art. 33 Abs. 5 DSGVO",
            ],
            "inhalte_en": [
                "What is a personal data breach? (Art. 4(12) GDPR)",
                "Examples: loss of a USB stick, email to the wrong recipient, ransomware",
                "72-hour deadline for notifying the supervisory authority (Art. 33 GDPR)",
                "Internal reporting process: who must be informed immediately?",
                "Documentation obligation under Art. 33(5) GDPR",
            ],
            "lernziel": "Jeder Mitarbeiter weiß, wann und wie er eine Datenpanne intern melden muss.",
            "lernziel_en": "Every employee knows when and how to report a personal data breach internally.",
        },
        {
            "id": "A6",
            "titel": "Datenschutzbeauftragter und Anlaufstellen",
            "titel_en": "Data protection officer and points of contact",
            "dauer_min": 5,
            "inhalte": [
                "Rolle und Aufgaben des Datenschutzbeauftragten (DSB)",
                "Wann wende ich mich an den DSB?",
                "Externe Aufsichtsbehörden: Bundesbeauftragter (BfDI) und Landesbehörden",
                "Beschwerdemöglichkeiten für Mitarbeiter und Kunden",
            ],
            "inhalte_en": [
                "Role and tasks of the data protection officer (DPO)",
                "When do I turn to the DPO?",
                "External supervisory authorities: the Federal Commissioner (BfDI) and the state authorities",
                "Avenues of complaint for employees and customers",
            ],
            "lernziel": "Mitarbeiter kennen den DSB und wissen, wann sie ihn einschalten müssen.",
            "lernziel_en": "Employees know the DPO and know when to involve them.",
        },
    ],
    "hr": [
        {
            "id": "HR1",
            "titel": "Beschäftigtendatenschutz (§ 26 BDSG)",
            "titel_en": "Employee data protection (§ 26 BDSG)",
            "dauer_min": 12,
            "inhalte": [
                "Rechtsgrundlage § 26 BDSG und Art. 6 Abs. 1 lit. b DSGVO für Beschäftigtendaten",
                "Welche Daten dürfen für das Beschäftigungsverhältnis verarbeitet werden?",
                "Einwilligung im Beschäftigungsverhältnis: freiwillig oder nicht?",
                "Verbot der Verarbeitung besonderer Kategorien ohne Einwilligung oder gesetzliche Grundlage",
                "Betriebsvereinbarungen als Rechtsgrundlage (§ 26 Abs. 4 BDSG)",
            ],
            "inhalte_en": [
                "Legal basis § 26 BDSG and Art. 6(1)(b) GDPR for employee data",
                "Which data may be processed for the employment relationship?",
                "Consent in the employment relationship: freely given or not?",
                "Prohibition on processing special categories without consent or a statutory basis",
                "Works agreements as a legal basis (§ 26(4) BDSG)",
            ],
            "lernziel": "HR-Mitarbeiter kennen die Grenzen zulässiger Datenverarbeitung im Beschäftigungsverhältnis.",
            "lernziel_en": "HR staff know the limits of permissible data processing in the employment relationship.",
        },
        {
            "id": "HR2",
            "titel": "Bewerberdaten und Recruiting",
            "titel_en": "Applicant data and recruiting",
            "dauer_min": 8,
            "inhalte": [
                "Speicherung von Bewerberdaten: nur so lange wie nötig (max. 6 Monate nach Absage)",
                "Weitergabe von Bewerberdaten innerhalb des Unternehmens: Need-to-Know",
                "Nutzung von Recruiting-Portalen und sozialen Netzwerken (XING, LinkedIn)",
                "Rücksendung oder Löschung von Unterlagen nach Absage",
            ],
            "inhalte_en": [
                "Storage of applicant data: only as long as necessary (max. 6 months after a rejection)",
                "Disclosure of applicant data within the company: need-to-know",
                "Use of recruiting portals and social networks (XING, LinkedIn)",
                "Returning or erasing documents after a rejection",
            ],
            "lernziel": "HR-Mitarbeiter wissen, wie mit Bewerberdaten DSGVO-konform umzugehen ist.",
            "lernziel_en": "HR staff know how to handle applicant data in compliance with the GDPR.",
        },
        {
            "id": "HR3",
            "titel": "Onboarding und Offboarding",
            "titel_en": "Onboarding and offboarding",
            "dauer_min": 8,
            "inhalte": [
                "Datenschutzverpflichtung neuer Mitarbeiter (Unterschrift / Belehrung)",
                "Zugriffsrechte: nur notwendige Systeme freischalten (Least Privilege)",
                "Offboarding: sofortige Sperrung aller Zugänge, Rückgabe von Geräten",
                "Aufbewahrung von Personalakten nach Austritt (gesetzliche Fristen)",
            ],
            "inhalte_en": [
                "Data protection undertaking by new employees (signature / briefing)",
                "Access rights: enable only the necessary systems (least privilege)",
                "Offboarding: immediate blocking of all access, return of devices",
                "Retention of personnel files after departure (statutory periods)",
            ],
            "lernziel": "HR verwaltet Zugriffsrechte und Personalakten datenschutzkonform.",
            "lernziel_en": "HR manages access rights and personnel files in compliance with data protection law.",
        },
    ],
    "it": [
        {
            "id": "IT1",
            "titel": "Technische und organisatorische Maßnahmen (TOM)",
            "titel_en": "Technical and organisational measures (TOM)",
            "dauer_min": 12,
            "inhalte": [
                "Art. 32 DSGVO: Anforderungen an geeignete TOMs",
                "Verschlüsselung (AES-256 at rest, TLS 1.2+ in transit)",
                "Zugriffskontrollen: RBAC, MFA, Least-Privilege-Prinzip",
                "Protokollierung: Was, wie lange, wie sicher?",
                "Penetrationstests und Schwachstellenmanagement",
            ],
            "inhalte_en": [
                "Art. 32 GDPR: requirements for appropriate TOMs",
                "Encryption (AES-256 at rest, TLS 1.2+ in transit)",
                "Access controls: RBAC, MFA, least-privilege principle",
                "Logging: what, for how long, how securely?",
                "Penetration testing and vulnerability management",
            ],
            "lernziel": "IT-Mitarbeiter verstehen die DSGVO-Anforderungen an Datensicherheit und können sie umsetzen.",
            "lernziel_en": "IT staff understand the GDPR requirements for data security and can implement them.",
        },
        {
            "id": "IT2",
            "titel": "Incident Response und Datenpannen",
            "titel_en": "Incident response and personal data breaches",
            "dauer_min": 10,
            "inhalte": [
                "Klassifizierung von Sicherheitsvorfällen (Risiko: kein / mittel / hoch)",
                "72-Stunden-Meldung: Wer meldet? Welche Daten braucht die Aufsichtsbehörde?",
                "Forensische Sicherung von Beweismitteln ohne DSGVO-Verstoß",
                "Post-Incident-Review und Dokumentation nach Art. 33 Abs. 5",
            ],
            "inhalte_en": [
                "Classification of security incidents (risk: none / medium / high)",
                "72-hour notification: who notifies? Which data does the supervisory authority need?",
                "Forensic preservation of evidence without infringing the GDPR",
                "Post-incident review and documentation under Art. 33(5)",
            ],
            "lernziel": "IT reagiert bei Sicherheitsvorfällen fristgerecht und dokumentiert korrekt.",
            "lernziel_en": "IT responds to security incidents within the deadlines and documents them correctly.",
        },
        {
            "id": "IT3",
            "titel": "Datenschutz-Folgenabschätzung (DSFA) aus IT-Sicht",
            "titel_en": "Data protection impact assessment (DPIA) from an IT perspective",
            "dauer_min": 8,
            "inhalte": [
                "Wann ist eine DSFA erforderlich? (Art. 35 DSGVO, DSK-Blacklist)",
                "Rolle der IT bei der Erstellung einer DSFA",
                "Privacy by Design und Privacy by Default (Art. 25 DSGVO)",
                "Neue Systeme und Prozesse: Datenschutz von Anfang an einplanen",
            ],
            "inhalte_en": [
                "When is a DPIA required? (Art. 35 GDPR, DSK blacklist)",
                "The role of IT in preparing a DPIA",
                "Privacy by design and privacy by default (Art. 25 GDPR)",
                "New systems and processes: plan for data protection from the outset",
            ],
            "lernziel": "IT-Mitarbeiter beziehen Datenschutzanforderungen bereits bei der Systementwicklung ein.",
            "lernziel_en": "IT staff take data protection requirements into account as early as system development.",
        },
    ],
    "management": [
        {
            "id": "M1",
            "titel": "Verantwortlichkeit und Haftung",
            "titel_en": "Accountability and liability",
            "dauer_min": 10,
            "inhalte": [
                "Der Verantwortliche nach Art. 4 Nr. 7 DSGVO – persönliche Haftung der Geschäftsführung",
                "Bußgelder bis 20 Mio. € oder 4% des weltweiten Jahresumsatzes (Art. 83 DSGVO)",
                "Schadensersatz gegenüber Betroffenen (Art. 82 DSGVO)",
                "Accountability-Prinzip: Wir müssen Compliance nachweisen, nicht nur behaupten",
                "Delegation an Datenschutzbeauftragten – Verantwortung bleibt beim Management",
            ],
            "inhalte_en": [
                "The controller under Art. 4(7) GDPR – personal liability of the management",
                "Fines of up to EUR 20 million or 4% of worldwide annual turnover (Art. 83 GDPR)",
                "Compensation to data subjects (Art. 82 GDPR)",
                "Accountability principle: we must demonstrate compliance, not merely assert it",
                "Delegation to the data protection officer – responsibility remains with management",
            ],
            "lernziel": "Führungskräfte verstehen ihre persönliche Verantwortung und die finanziellen Risiken.",
            "lernziel_en": "Managers understand their personal responsibility and the financial risks.",
        },
        {
            "id": "M2",
            "titel": "Datenschutz-Governance und Compliance-Programm",
            "titel_en": "Data protection governance and compliance programme",
            "dauer_min": 10,
            "inhalte": [
                "Verzeichnis von Verarbeitungstätigkeiten (VVT) nach Art. 30 DSGVO",
                "Datenschutz-Folgenabschätzung (DSFA): wann notwendig, wie delegieren?",
                "Auftragsverarbeiterverträge (AVV): Pflicht bei jedem Dienstleister mit Datenzugang",
                "Regelmäßige Datenschutzaudits und Meldeketten",
                "Datenschutz als Wettbewerbsvorteil: Vertrauen der Kunden stärken",
            ],
            "inhalte_en": [
                "Records of processing activities (RoPA) under Art. 30 GDPR",
                "Data protection impact assessment (DPIA): when is it necessary, how to delegate it?",
                "Data processing agreements (DPA): mandatory for every service provider with access to data",
                "Regular data protection audits and reporting chains",
                "Data protection as a competitive advantage: strengthening customer trust",
            ],
            "lernziel": "Führungskräfte können ein funktionierendes Datenschutz-Compliance-Programm steuern.",
            "lernziel_en": "Managers can steer a functioning data protection compliance programme.",
        },
        {
            "id": "M3",
            "titel": "Aktuelle Entwicklungen und Praxisfälle",
            "titel_en": "Current developments and practical cases",
            "dauer_min": 8,
            "inhalte": [
                "Bußgeldfälle 2023/2024: Was können wir daraus lernen?",
                "KI und automatisierte Entscheidungen (Art. 22 DSGVO): Handlungsbedarf?",
                "Drittlandtransfers nach Schrems II: Status und To-dos",
                "Datenschutz in sozialen Medien und Marketing",
            ],
            "inhalte_en": [
                "Fine cases 2023/2024: what can we learn from them?",
                "AI and automated decisions (Art. 22 GDPR): is action needed?",
                "Third-country transfers after Schrems II: status and to-dos",
                "Data protection in social media and marketing",
            ],
            "lernziel": "Führungskräfte bleiben aktuell und erkennen neue Risiken.",
            "lernziel_en": "Managers stay up to date and recognise new risks.",
        },
    ],
}


# ── Quiz questions ────────────────────────────────────────────────────────────
#
# ``antwort`` ist ein Datenwert und zeigt auf den **Buchstaben** einer Option.
# ``optionen_en`` behält deshalb Reihenfolge und Buchstaben von ``optionen``.

QUIZ_FRAGEN: dict[str, list[dict[str, Any]]] = {
    "alle": [
        {
            "frage": "Was ist eine personenbezogene Information?",
            "frage_en": "What is personal information?",
            "optionen": [
                "A) Der Vorname einer Person allein",
                "B) Alle Informationen, die sich auf eine identifizierte oder identifizierbare natürliche Person beziehen",
                "C) Nur Informationen in digitaler Form",
                "D) Nur Name, Adresse und Geburtsdatum",
            ],
            "optionen_en": [
                "A) A person's first name on its own",
                "B) Any information relating to an identified or identifiable natural person",
                "C) Only information in digital form",
                "D) Only name, address and date of birth",
            ],
            "antwort": "B",
            "erklaerung": "Art. 4 Nr. 1 DSGVO: Personenbezogene Daten sind alle Informationen, die sich auf eine identifizierte oder identifizierbare natürliche Person beziehen.",
            "erklaerung_en": "Art. 4(1) GDPR: personal data means any information relating to an identified or identifiable natural person.",
        },
        {
            "frage": "Sie bemerken, dass ein Kollege versehentlich eine E-Mail mit Firmendaten an eine falsche Adresse geschickt hat. Was tun Sie?",
            "frage_en": "You notice that a colleague has accidentally sent an email containing company data to the wrong address. What do you do?",
            "optionen": [
                "A) Nichts – ist doch ein Versehen",
                "B) Den Kollegen bitten, es selbst zu melden",
                "C) Sofort den Datenschutzbeauftragten oder Vorgesetzten informieren",
                "D) Auf die Aufsichtsbehörde warten",
            ],
            "optionen_en": [
                "A) Nothing – it was an oversight after all",
                "B) Ask the colleague to report it themselves",
                "C) Inform the data protection officer or your line manager immediately",
                "D) Wait for the supervisory authority",
            ],
            "antwort": "C",
            "erklaerung": "Datenpannen müssen intern sofort gemeldet werden. Das Unternehmen hat 72 Stunden Zeit zur Meldung an die Aufsichtsbehörde (Art. 33 DSGVO).",
            "erklaerung_en": "Personal data breaches must be reported internally immediately. The company has 72 hours to notify the supervisory authority (Art. 33 GDPR).",
        },
        {
            "frage": "Welche der folgenden Aussagen zum Recht auf Löschung ist FALSCH?",
            "frage_en": "Which of the following statements about the right to erasure is FALSE?",
            "optionen": [
                "A) Es gilt auch dann nicht, wenn eine gesetzliche Aufbewahrungspflicht besteht",
                "B) Der Betroffene kann jederzeit ohne Begründung verlangen, dass seine Daten gelöscht werden",
                "C) Das Unternehmen hat 1 Monat Zeit zu antworten",
                "D) Es kann eingeschränkt werden, wenn die Daten zur Geltendmachung von Rechtsansprüchen benötigt werden",
            ],
            "optionen_en": [
                "A) It also does not apply where a statutory retention obligation exists",
                "B) The data subject may demand at any time and without giving reasons that their data be erased",
                "C) The company has 1 month to respond",
                "D) It can be restricted where the data are needed for the establishment of legal claims",
            ],
            "antwort": "B",
            "erklaerung": "Das Recht auf Löschung gilt nur unter bestimmten Voraussetzungen (Art. 17 DSGVO), z. B. wenn der Zweck entfallen ist oder die Einwilligung widerrufen wurde.",
            "erklaerung_en": "The right to erasure applies only under certain conditions (Art. 17 GDPR), e.g. where the purpose has ceased to apply or consent has been withdrawn.",
        },
        {
            "frage": "Wie lange darf eine Einwilligung maximal gespeichert werden, ohne erneut eingeholt werden zu müssen?",
            "frage_en": "For how long at most may a consent be stored without having to be obtained again?",
            "optionen": [
                "A) 1 Jahr",
                "B) 2 Jahre",
                "C) Solange der Zweck besteht und die Einwilligung nicht widerrufen wurde",
                "D) 5 Jahre",
            ],
            "optionen_en": [
                "A) 1 year",
                "B) 2 years",
                "C) As long as the purpose exists and the consent has not been withdrawn",
                "D) 5 years",
            ],
            "antwort": "C",
            "erklaerung": "Eine Einwilligung gilt bis zum Widerruf durch den Betroffenen. Allerdings sollte die Aktualität regelmäßig geprüft werden.",
            "erklaerung_en": "A consent remains valid until it is withdrawn by the data subject. However, whether it is still up to date should be reviewed regularly.",
        },
        {
            "frage": "Was bedeutet das Prinzip der Datenminimierung?",
            "frage_en": "What does the principle of data minimisation mean?",
            "optionen": [
                "A) Daten sollten so klein wie möglich gespeichert werden (Dateigröße)",
                "B) Es dürfen nur Daten erhoben werden, die für den konkreten Zweck erforderlich sind",
                "C) Alle Daten müssen nach 6 Monaten gelöscht werden",
                "D) Nur Daten aus der EU dürfen verarbeitet werden",
            ],
            "optionen_en": [
                "A) Data should be stored as small as possible (file size)",
                "B) Only data that are necessary for the specific purpose may be collected",
                "C) All data must be erased after 6 months",
                "D) Only data from the EU may be processed",
            ],
            "antwort": "B",
            "erklaerung": "Art. 5 Abs. 1 lit. c DSGVO: Daten müssen dem Zweck angemessen und erheblich sein sowie auf das für die Zwecke der Verarbeitung notwendige Maß beschränkt sein.",
            "erklaerung_en": "Art. 5(1)(c) GDPR: data must be adequate, relevant and limited to what is necessary in relation to the purposes of the processing.",
        },
    ],
    "hr": [
        {
            "frage": "Wie lange dürfen Bewerberdaten nach einer Absage gespeichert werden?",
            "frage_en": "For how long may applicant data be stored after a rejection?",
            "optionen": [
                "A) Unbegrenzt",
                "B) 10 Jahre (Verjährungsfristen)",
                "C) In der Regel maximal 6 Monate",
                "D) Genau 30 Tage",
            ],
            "optionen_en": [
                "A) Indefinitely",
                "B) 10 years (limitation periods)",
                "C) As a rule, a maximum of 6 months",
                "D) Exactly 30 days",
            ],
            "antwort": "C",
            "erklaerung": "Nach ständiger Aufsichtsbehördenpraxis: Bewerberdaten dürfen nach Ablehnung maximal 6 Monate gespeichert werden, um Klagen nach AGG abzuwehren.",
            "erklaerung_en": "According to settled supervisory authority practice: after a rejection, applicant data may be stored for a maximum of 6 months in order to defend against claims under the German General Equal Treatment Act (AGG).",
        },
        {
            "frage": "Welche Rechtsgrundlage gilt für die Verarbeitung von Beschäftigtendaten im Arbeitsverhältnis?",
            "frage_en": "Which legal basis applies to the processing of employee data in the employment relationship?",
            "optionen": [
                "A) Art. 6 Abs. 1 lit. a DSGVO (Einwilligung) – immer",
                "B) § 26 BDSG i.V.m. Art. 9 DSGVO für besondere Kategorien",
                "C) Es gibt keine spezielle Regelung, es gilt nur die DSGVO",
                "D) Tarifvertrag reicht als Rechtsgrundlage aus",
            ],
            "optionen_en": [
                "A) Art. 6(1)(a) GDPR (consent) – always",
                "B) § 26 BDSG in conjunction with Art. 9 GDPR for special categories",
                "C) There is no special rule, only the GDPR applies",
                "D) A collective agreement is sufficient as a legal basis",
            ],
            "antwort": "B",
            "erklaerung": "§ 26 BDSG ist die nationale Öffnungsklausel für Beschäftigtendaten. Für besondere Datenkategorien (z. B. Gesundheitsdaten) gilt zusätzlich Art. 9 DSGVO.",
            "erklaerung_en": "§ 26 BDSG is the national opening clause for employee data. For special categories of data (e.g. health data), Art. 9 GDPR applies in addition.",
        },
    ],
    "it": [
        {
            "frage": "Was ist eine Datenschutz-Folgenabschätzung (DSFA) und wann ist sie Pflicht?",
            "frage_en": "What is a data protection impact assessment (DPIA) and when is it mandatory?",
            "optionen": [
                "A) Eine Sicherheitsüberprüfung aller IT-Systeme, jährlich",
                "B) Eine Risikoanalyse, die bei voraussichtlich hohem Risiko für Betroffene durchgeführt werden muss",
                "C) Ein Penetrationstest",
                "D) Eine Zertifizierung nach ISO 27001",
            ],
            "optionen_en": [
                "A) A security review of all IT systems, carried out annually",
                "B) A risk analysis that must be carried out where the processing is likely to result in a high risk to data subjects",
                "C) A penetration test",
                "D) A certification to ISO 27001",
            ],
            "antwort": "B",
            "erklaerung": "Art. 35 DSGVO: Eine DSFA ist vor der Verarbeitung durchzuführen, wenn die Verarbeitung voraussichtlich ein hohes Risiko für die Rechte und Freiheiten natürlicher Personen mit sich bringt.",
            "erklaerung_en": "Art. 35 GDPR: a DPIA must be carried out prior to the processing where the processing is likely to result in a high risk to the rights and freedoms of natural persons.",
        },
        {
            "frage": "Was bedeutet Privacy by Default?",
            "frage_en": "What does privacy by default mean?",
            "optionen": [
                "A) Alle Datenschutzeinstellungen sind standardmäßig auf Maximum gesetzt",
                "B) Datenschutz wird erst auf Anfrage aktiviert",
                "C) Technische Voreinstellungen gewährleisten, dass nur die zur Erreichung des Zwecks erforderlichen Daten verarbeitet werden",
                "D) Das System speichert keine Daten",
            ],
            "optionen_en": [
                "A) All data protection settings are set to maximum by default",
                "B) Data protection is activated only on request",
                "C) Technical default settings ensure that only the data necessary for achieving the purpose are processed",
                "D) The system stores no data",
            ],
            "antwort": "C",
            "erklaerung": "Art. 25 Abs. 2 DSGVO: Durch datenschutzfreundliche Voreinstellungen soll sichergestellt werden, dass nur die für den konkreten Zweck erforderlichen Daten verarbeitet werden.",
            "erklaerung_en": "Art. 25(2) GDPR: data protection by default is intended to ensure that only the data necessary for the specific purpose are processed.",
        },
    ],
    "management": [
        {
            "frage": "Was ist die maximale Bußgeldhöhe für schwere DSGVO-Verstöße?",
            "frage_en": "What is the maximum level of fine for serious infringements of the GDPR?",
            "optionen": [
                "A) 100.000 €",
                "B) 20 Mio. € oder 4 % des weltweiten Jahresumsatzes – der höhere Betrag gilt",
                "C) 500.000 € je Vorfall",
                "D) Bußgelder gibt es erst nach drei Verstößen",
            ],
            "optionen_en": [
                "A) EUR 100,000",
                "B) EUR 20 million or 4 % of worldwide annual turnover – whichever is higher",
                "C) EUR 500,000 per incident",
                "D) Fines are only imposed after three infringements",
            ],
            "antwort": "B",
            "erklaerung": "Art. 83 Abs. 5 DSGVO: Bei den schwerwiegendsten Verstößen können Bußgelder bis 20 Mio. € oder 4 % des gesamten weltweiten Jahresumsatzes verhängt werden.",
            "erklaerung_en": "Art. 83(5) GDPR: for the most serious infringements, fines of up to EUR 20 million or 4 % of the total worldwide annual turnover may be imposed.",
        },
        {
            "frage": "Muss für jeden externen Dienstleister, der Zugang zu personenbezogenen Daten hat, ein Auftragsverarbeitungsvertrag (AVV) abgeschlossen werden?",
            "frage_en": "Must a data processing agreement (DPA) be concluded with every external service provider that has access to personal data?",
            "optionen": [
                "A) Nur bei Dienstleistern außerhalb der EU",
                "B) Nur bei Dienstleistern mit mehr als 10 Mitarbeitern",
                "C) Ja, grundsätzlich für alle Auftragsverarbeiter nach Art. 28 DSGVO",
                "D) Nein, es reicht eine NDA",
            ],
            "optionen_en": [
                "A) Only with service providers outside the EU",
                "B) Only with service providers with more than 10 employees",
                "C) Yes, as a matter of principle for all processors under Art. 28 GDPR",
                "D) No, an NDA is sufficient",
            ],
            "antwort": "C",
            "erklaerung": "Art. 28 DSGVO: Für jeden Auftragsverarbeiter ist ein schriftlicher Vertrag (AVV) erforderlich, der die Verarbeitung nach den Weisungen des Verantwortlichen sicherstellt.",
            "erklaerung_en": "Art. 28 GDPR: for every processor a written contract (DPA) is required which ensures that the processing takes place on the instructions of the controller.",
        },
    ],
}


# ── Scenarios ────────────────────────────────────────────────────────────────
#
# E-Mail-Adressen und Personennamen in den Fällen sind **Daten** des Szenarios
# und bleiben in jeder Sprache unverändert — wer sie übersetzt, erzeugt einen
# Fall, der sich mit dem deutschen nicht mehr bespricht.

SZENARIEN: dict[str, list[dict[str, Any]]] = {
    "alle": [
        {
            "titel": "Szenario: Falsch adressierte E-Mail",
            "titel_en": "Scenario: misaddressed email",
            "beschreibung": (
                "Ihr Kollege Max hat versehentlich eine Excel-Tabelle mit Kundenadressen "
                "an externe-firmen@example.com statt an internes-crm@ihrunternehmen.de gesendet."
            ),
            "beschreibung_en": (
                "Your colleague Max has accidentally sent an Excel spreadsheet containing "
                "customer addresses to externe-firmen@example.com instead of "
                "internes-crm@ihrunternehmen.de."
            ),
            "frage": "Was sind die richtigen nächsten Schritte?",
            "frage_en": "What are the correct next steps?",
            "loesung": [
                "Sofort den Datenschutzbeauftragten (DSB) oder Vorgesetzten informieren.",
                "Sichern: Wann? Welche Daten? Wie viele Betroffene?",
                "DSB prüft: Risiko gering (z. B. nur Namen) oder hoch (z. B. Gesundheitsdaten)?",
                "Bei mehr als geringem Risiko: Meldung an Aufsichtsbehörde innerhalb 72 Stunden.",
                "Dokumentation des Vorfalls nach Art. 33 Abs. 5 DSGVO.",
            ],
            "loesung_en": [
                "Inform the data protection officer (DPO) or your line manager immediately.",
                "Secure the facts: when? which data? how many data subjects?",
                "The DPO assesses: low risk (e.g. names only) or high risk (e.g. health data)?",
                "Where the risk is more than low: notify the supervisory authority within 72 hours.",
                "Document the incident in accordance with Art. 33(5) GDPR.",
            ],
        },
        {
            "titel": "Szenario: Anfrage auf Auskunft",
            "titel_en": "Scenario: request for access",
            "beschreibung": (
                "Frau Müller schreibt Ihnen eine E-Mail und fragt, welche Daten Sie "
                "über sie gespeichert haben."
            ),
            "beschreibung_en": (
                "Ms Müller sends you an email asking which data you have stored about her."
            ),
            "frage": "Wie gehen Sie vor?",
            "frage_en": "How do you proceed?",
            "loesung": [
                "Eingang dokumentieren – 1-Monats-Frist läuft ab Eingang.",
                "Identität der anfragenden Person verifizieren.",
                "Anfrage intern an den DSB oder die zuständige Abteilung weiterleiten.",
                "Vollständige Auskunft erteilen (Art. 15 DSGVO): welche Daten, wozu, wie lange?",
                "Antwort schriftlich oder per E-Mail innerhalb 1 Monat.",
            ],
            "loesung_en": [
                "Document receipt – the 1-month time limit runs from receipt.",
                "Verify the identity of the requesting person.",
                "Forward the request internally to the DPO or the responsible department.",
                "Provide complete access (Art. 15 GDPR): which data, for what purpose, for how long?",
                "Reply in writing or by email within 1 month.",
            ],
        },
    ],
    "hr": [
        {
            "titel": "Szenario: Kandidat fragt nach gelöschten Bewerberdaten",
            "titel_en": "Scenario: candidate asks about erased applicant data",
            "beschreibung": (
                "Herr Schmidt hat sich vor 8 Monaten beworben und nicht die Stelle bekommen. "
                "Er fragt jetzt, ob seine Daten noch gespeichert sind."
            ),
            "beschreibung_en": (
                "Mr Schmidt applied 8 months ago and did not get the position. He now asks "
                "whether his data are still stored."
            ),
            "frage": "Was antworten Sie?",
            "frage_en": "What do you reply?",
            "loesung": [
                "Prüfen: Wurden die Daten nach 6 Monaten gelöscht? Wenn ja: Löschbestätigung.",
                "Wenn noch gespeichert: Sofort löschen und Herrn Schmidt informieren.",
                "Intern prüfen: Gibt es einen laufenden Prozess für die Löschung nach Ablehnung?",
            ],
            "loesung_en": [
                "Check: were the data erased after 6 months? If so: confirmation of erasure.",
                "If they are still stored: erase them immediately and inform Mr Schmidt.",
                "Check internally: is there a running process for erasure after a rejection?",
            ],
        },
    ],
    "it": [
        {
            "titel": "Szenario: Ransomware-Angriff",
            "titel_en": "Scenario: ransomware attack",
            "beschreibung": (
                "Freitagabend erkennt das Monitoring-System eine Ransomware-Infektion "
                "auf drei Servern. Firmendaten könnten abgeflossen sein."
            ),
            "beschreibung_en": (
                "On Friday evening the monitoring system detects a ransomware infection on "
                "three servers. Company data may have been exfiltrated."
            ),
            "frage": "Was sind die sofortigen Datenschutz-Pflichten?",
            "frage_en": "What are the immediate data protection obligations?",
            "loesung": [
                "Systeme isolieren – kein weiterer Datenverlust.",
                "DSB sofort informieren: potenzielle Datenpanne.",
                "Dokumentieren: Zeitpunkt, betroffene Systeme, möglicherweise betroffene Datenkategorien.",
                "Risikobewertung: Wurden personenbezogene Daten abgeflossen? Welche?",
                "Bei relevantem Risiko: Meldung an Aufsichtsbehörde innerhalb 72 Stunden.",
                "Bei hohem Risiko für Betroffene: Betroffene benachrichtigen (Art. 34 DSGVO).",
            ],
            "loesung_en": [
                "Isolate the systems – no further loss of data.",
                "Inform the DPO immediately: potential personal data breach.",
                "Document: point in time, systems affected, categories of data possibly affected.",
                "Risk assessment: were personal data exfiltrated? Which ones?",
                "Where there is a relevant risk: notify the supervisory authority within 72 hours.",
                "Where there is a high risk to data subjects: communicate the breach to them (Art. 34 GDPR).",
            ],
        },
    ],
    "management": [
        {
            "titel": "Szenario: Neues CRM-System",
            "titel_en": "Scenario: new CRM system",
            "beschreibung": (
                "Ihr Vertrieb möchte ein Cloud-CRM-System (Anbieter in den USA) einführen, "
                "um alle Firmendaten zentral zu speichern."
            ),
            "beschreibung_en": (
                "Your sales department wants to introduce a cloud CRM system (provider in "
                "the USA) in order to store all company data centrally."
            ),
            "frage": "Welche Datenschutzfragen müssen Sie vor Go-Live klären?",
            "frage_en": "Which data protection questions must you clarify before go-live?",
            "loesung": [
                "AVV (Auftragsverarbeitungsvertrag) nach Art. 28 DSGVO abschließen.",
                "Drittlandtransfer prüfen: Angemessenheitsbeschluss oder EU-Standardvertragsklauseln (SCCs)?",
                "Datenschutz-Folgenabschätzung (DSFA) prüfen: hohes Risiko durch zentralisierte Firmendaten?",
                "Sicherheitszertifizierungen des Anbieters prüfen (ISO 27001, SOC 2).",
                "Mitarbeiter informieren: neue Datenverarbeitungsaktivität im VVT dokumentieren.",
            ],
            "loesung_en": [
                "Conclude a DPA (data processing agreement) under Art. 28 GDPR.",
                "Check the third-country transfer: adequacy decision or EU standard contractual clauses (SCCs)?",
                "Consider a data protection impact assessment (DPIA): high risk from centralised company data?",
                "Check the provider's security certifications (ISO 27001, SOC 2).",
                "Inform employees: document the new processing activity in the RoPA.",
            ],
        },
    ],
}


# ── Prosa des Dokuments je Sprache (#1954) ───────────────────────────────────
#
# Der deutsche Katalog ist eine **zeichengenaue** Kopie der Zeichenketten, die
# vorher im Quelltext standen — einschließlich der doppelten Leerzeichen in
# Überschriften und Bannern und der drei Leerzeichen um den Trennstrich der
# Themen-Kopfzeile. Auf Deutsch bleibt das Dokument damit byte-identisch.
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "entwurf_banner": "⚠  ENTWURF – Schulungsinhalt bitte vor Verwendung fachlich und rechtlich prüfen.",
        "titel": "DSGVO-Jahresschulung",
        "untertitel": "Datenschutz-Grundverordnung (EU) 2016/679  ·  {firma}",

        # Kopftabelle. Die Schlüssel sind die Kennung der Zeile — **nicht** die
        # Beschriftung: Die gelbe Hinterlegung der Status-Zeile hing bis #1954
        # an einem Vergleich gegen den deutschen Text (`label == "Status"`) und
        # wäre mit der Übersetzung lautlos verschwunden.
        "meta_organisation": "Organisation",
        "meta_projekt": "Projekt",
        "meta_datum": "Datum",
        "meta_referent": "Referent",
        "meta_zielgruppen": "Zielgruppe(n)",
        "meta_dauer": "Geschätzte Dauer",
        "meta_status": "Status",
        "status_entwurf": "ENTWURF",
        "dauer_ca": "ca. {min} Minuten",
        "leer": "—",

        "h_agenda": "1  Agenda",
        "ag_nr": "Nr.",
        "ag_thema": "Thema",
        "ag_dauer": "Dauer",
        "min_zeile": "{min} min",
        "ag_q": "Q",
        "ag_quiz": "Quiz und Abschlussdiskussion",
        "ag_quiz_dauer": "10 min",

        "h_inhalte": "2  Schulungsinhalte",
        "zielgruppe_banner": "Zielgruppe: {label}  –  {desc}",
        "thema_kopf": "{id}  {titel}",
        "thema_meta": "Lernziel: {lernziel}   |   Dauer: ca. {min} Minuten",

        "h_szenarien": "Praxisszenarien",
        "szen_frage": "❓  {frage}",
        "musterloesung": "✓  Musterlösung:",
        "loesung_schritt": "  {schritt}",

        "h_quiz": "3  Quiz und Wissensüberprüfung",
        "quiz_intro": (
            "Die folgenden Fragen dienen der Wissensüberprüfung. "
            "Bitte Antworten im Seminar besprechen."),
        "fragen_fuer": "Fragen für: {label}",
        "frage_kopf": "Frage {nr}: {frage}",
        "option_zeile": "  {option}",
        "antwort_zeile": "✓  Richtige Antwort: {antwort}  –  {erklaerung}",

        "disclaimer": (
            "Rechtlicher Hinweis: Dieses Schulungsmaterial wurde automatisiert erstellt und stellt "
            "einen unverbindlichen Entwurf dar. Es ersetzt keine rechtliche oder datenschutzfachliche "
            "Prüfung. Bitte lassen Sie den Inhalt vor der Verwendung durch einen qualifizierten "
            "Datenschutzbeauftragten prüfen und unternehmensspezifisch anpassen."),
    },
    "en": {
        "entwurf_banner": "⚠  DRAFT – Please have the training content reviewed professionally and legally before use.",
        "titel": "GDPR Annual Training",
        "untertitel": "General Data Protection Regulation (EU) 2016/679  ·  {firma}",

        "meta_organisation": "Organisation",
        "meta_projekt": "Project",
        "meta_datum": "Date",
        "meta_referent": "Trainer",
        "meta_zielgruppen": "Audience(s)",
        "meta_dauer": "Estimated duration",
        "meta_status": "Status",
        "status_entwurf": "DRAFT",
        "dauer_ca": "approx. {min} minutes",
        "leer": "—",

        "h_agenda": "1  Agenda",
        "ag_nr": "No.",
        "ag_thema": "Topic",
        "ag_dauer": "Duration",
        "min_zeile": "{min} min",
        "ag_q": "Q",
        "ag_quiz": "Quiz and closing discussion",
        "ag_quiz_dauer": "10 min",

        "h_inhalte": "2  Training content",
        "zielgruppe_banner": "Audience: {label}  –  {desc}",
        "thema_kopf": "{id}  {titel}",
        "thema_meta": "Learning objective: {lernziel}   |   Duration: approx. {min} minutes",

        "h_szenarien": "Practical scenarios",
        "szen_frage": "❓  {frage}",
        "musterloesung": "✓  Model answer:",
        "loesung_schritt": "  {schritt}",

        "h_quiz": "3  Quiz and knowledge check",
        "quiz_intro": (
            "The following questions serve as a knowledge check. "
            "Please discuss the answers during the session."),
        "fragen_fuer": "Questions for: {label}",
        "frage_kopf": "Question {nr}: {frage}",
        "option_zeile": "  {option}",
        "antwort_zeile": "✓  Correct answer: {antwort}  –  {erklaerung}",

        "disclaimer": (
            "Legal notice: this training material was generated automatically and "
            "constitutes a non-binding draft. It does not replace a legal or data "
            "protection review. Please have the content reviewed by a qualified data "
            "protection officer and adapted to your company before use."),
    },
}

_t = _rt.macher(TEXTE)


def _feld(eintrag: dict[str, Any], name: str, sprache: str = "de") -> Any:
    """Ein Inhaltsfeld in der gewünschten Sprache — mit deutschem Rückfall.

    Fehlt ``<name>_en``, gilt die deutsche Fassung. Das ist dieselbe Zusage wie
    ``shared.reports.texte.macher``: Ein neues Thema erscheint sofort in jeder
    Unterlage, auf Deutsch, bis es jemand übersetzt. Würde es fehlen, wäre eine
    halbe Übersetzung eine **unvollständige Schulung** — und das ist schlimmer
    als ein deutscher Absatz darin.
    """
    if sprache != "de":
        wert = eintrag.get(f"{name}_en")
        if wert:
            return wert
    return eintrag.get(name)


# ── DOCX helpers ──────────────────────────────────────────────────────────────

def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex_word(h: str) -> str:
    return h.lstrip("#").upper()


def _set_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), _hex_word(fill))
    tc_pr.append(shd)


def _set_border(cell, color: str = "DDDDDD") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = OxmlElement("w:tcBorders")
    tc_pr.append(tc_borders)
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        tc_borders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), color.lstrip("#"))


def _banner(doc, text: str, bg: str, fg: str = "#FFFFFF", size: int = 11) -> None:
    tbl = doc.add_table(rows=1, cols=1)
    cell = tbl.cell(0, 0)
    _set_shading(cell, bg)
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    r, g, b = _hex_rgb(fg)
    run.font.color.rgb = RGBColor(r, g, b)


def _heading(doc, text: str, level: int = 1, color: str = "#003399") -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt({1: 14, 2: 12, 3: 10}[level])
    r, g, b = _hex_rgb(color)
    run.font.color.rgb = RGBColor(r, g, b)
    p.paragraph_format.space_before = Pt({1: 14, 2: 8, 3: 5}[level])
    p.paragraph_format.space_after = Pt(3)


def _body(doc, text: str, size: int = 10, italic: bool = False) -> None:
    p = doc.add_paragraph(text)
    if p.runs:
        p.runs[0].font.size = Pt(size)
        p.runs[0].italic = italic
    p.paragraph_format.space_after = Pt(3)


def _bullet(doc, text: str, level: int = 0) -> None:
    p = doc.add_paragraph(text, style="List Bullet")
    if p.runs:
        p.runs[0].font.size = Pt(10)
    p.paragraph_format.left_indent = Inches(0.3 + level * 0.2)
    p.paragraph_format.space_after = Pt(2)


def _safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "-", s or "")
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:60] or "DSGVO_Schulung"


def _total_minutes(zielgruppen: list[str]) -> int:
    total = 0
    for zg in zielgruppen:
        for topic in TRAINING_OUTLINE.get(zg, []):
            total += topic.get("dauer_min", 0)
    return total


# ── DOCX export ───────────────────────────────────────────────────────────────

def export_training_docx(
    *,
    out_dir: Path,
    projekt_name: str,
    unternehmen: str = "",
    berater: str = "",
    zielgruppen: list[str] | None = None,
    themen: list[str] | None = None,
    sprache: str | None = None,
) -> Path:
    """Generate a DSGVO training script + quiz DOCX draft.

    Args:
        out_dir: Output directory.
        projekt_name: Project name (used for filename and header).
        unternehmen: Company name.
        berater: Author/trainer name.
        zielgruppen: Subset of ZIELGRUPPEN keys to include. Defaults to ['alle'].
        themen: Optional filter on topic IDs (e.g. ['A1', 'A2', 'HR1']).
        sprache: Übersteuert die Sprache für diesen Lauf; ohne Angabe entscheidet
            ``firmen.sprache`` des Mandanten (#1954), fail-open auf Deutsch.

    Returns:
        Path to the generated DOCX.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spr = _rt.aufloesen("dsgvo", projekt_name, sprache)

    if not zielgruppen:
        zielgruppen = ["alle"]
    zielgruppen = [z for z in zielgruppen if z in TRAINING_OUTLINE]
    if not zielgruppen:
        zielgruppen = ["alle"]

    doc = Document()
    for section in doc.sections:
        section.top_margin    = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)

    # Dokumentsprache (``w:lang``) nur außerhalb von Deutsch setzen: Auf Deutsch
    # bleibt das Dokument damit byte-identisch zum Bestand, und eine englische
    # Unterlage wird in Word nicht Wort für Wort rot unterstrichen.
    if spr != "de":
        from shared.reports.docx_pdf import set_doc_lang
        set_doc_lang(doc, spr)

    firma = unternehmen or projekt_name
    total_min = _total_minutes(zielgruppen)
    zg_labels = " + ".join(_feld(ZIELGRUPPEN[z], "label", spr)
                           for z in zielgruppen if z in ZIELGRUPPEN)

    # ── DRAFT banner ──────────────────────────────────────────────────────────
    _banner(doc,
            _t(spr, "entwurf_banner"),
            _DRAFT_BG, fg=_DRAFT_FG, size=10)
    doc.add_paragraph()

    # ── Title ─────────────────────────────────────────────────────────────────
    title_p = doc.add_paragraph()
    tr = title_p.add_run(_t(spr, "titel"))
    tr.bold = True
    tr.font.size = Pt(22)
    r, g, b = _hex_rgb(_EU_BLUE)
    tr.font.color.rgb = RGBColor(r, g, b)

    sub_p = doc.add_paragraph(_t(spr, "untertitel", firma=firma))
    sub_p.runs[0].font.size = Pt(11)
    sub_p.runs[0].italic = True
    doc.add_paragraph()

    # Metadata table
    meta_tbl = doc.add_table(rows=0, cols=2)
    meta_tbl.autofit = False
    meta_tbl.columns[0].width = Inches(1.8)
    meta_tbl.columns[1].width = Inches(4.7)
    for schluessel, val in [
        ("meta_organisation", firma),
        ("meta_projekt",      projekt_name),
        ("meta_datum",        str(date.today())),
        ("meta_referent",     berater or _t(spr, "leer")),
        ("meta_zielgruppen",  zg_labels),
        ("meta_dauer",        _t(spr, "dauer_ca", min=total_min)),
        ("meta_status",       _t(spr, "status_entwurf")),
    ]:
        row = meta_tbl.add_row()
        lc, vc = row.cells[0], row.cells[1]
        _set_shading(lc, "F5F5F5")
        # Der Vergleich läuft über den **Schlüssel**: Vor #1954 stand hier
        # `label == "Status"`, und der deutsche Text entschied über die
        # Hinterlegung — in einer englischen Unterlage wäre sie lautlos weg.
        _set_shading(vc, "FFFDE7" if schluessel == "meta_status" else "FFFFFF")
        _set_border(lc)
        _set_border(vc)
        lp = lc.paragraphs[0]
        lr = lp.add_run(_t(spr, schluessel))
        lr.bold = True
        lr.font.size = Pt(9)
        vp = vc.paragraphs[0]
        vr = vp.add_run(val)
        vr.font.size = Pt(9)

    doc.add_paragraph()

    # ── 1. Agenda ─────────────────────────────────────────────────────────────
    _heading(doc, _t(spr, "h_agenda"), level=1)
    agenda_tbl = doc.add_table(rows=0, cols=3)
    agenda_tbl.autofit = False
    agenda_tbl.columns[0].width = Inches(0.7)
    agenda_tbl.columns[1].width = Inches(4.2)
    agenda_tbl.columns[2].width = Inches(1.5)
    hrow = agenda_tbl.add_row()
    for ci, ht in enumerate([_t(spr, "ag_nr"), _t(spr, "ag_thema"),
                             _t(spr, "ag_dauer")]):
        hc = hrow.cells[ci]
        _set_shading(hc, _EU_BLUE)
        _set_border(hc, _EU_BLUE)
        hp = hc.paragraphs[0]
        hr_ = hp.add_run(ht)
        hr_.bold = True
        hr_.font.size = Pt(9)
        hr_.font.color.rgb = RGBColor(255, 255, 255)

    all_topics: list[tuple[str, dict[str, Any]]] = []
    for zg in zielgruppen:
        for topic in TRAINING_OUTLINE.get(zg, []):
            if themen is None or topic["id"] in themen:
                all_topics.append((zg, topic))

    for zg, topic in all_topics:
        row = agenda_tbl.add_row()
        nc, tc, dc = row.cells[0], row.cells[1], row.cells[2]
        zg_color = ZIELGRUPPEN.get(zg, {}).get("farbe", _ALL_COL)
        bg = "F8F9FA"
        _set_shading(nc, bg)
        _set_shading(tc, bg)
        _set_shading(dc, bg)
        _set_border(nc)
        _set_border(tc)
        _set_border(dc)
        np_ = nc.paragraphs[0]
        nr_ = np_.add_run(topic["id"])
        nr_.bold = True
        nr_.font.size = Pt(9)
        r, g, b = _hex_rgb(zg_color)
        nr_.font.color.rgb = RGBColor(r, g, b)
        tp_ = tc.paragraphs[0]
        tr_ = tp_.add_run(_feld(topic, "titel", spr))
        tr_.font.size = Pt(9)
        dp_ = dc.paragraphs[0]
        dr_ = dp_.add_run(_t(spr, "min_zeile", min=topic['dauer_min']))
        dr_.font.size = Pt(9)
        dr_.italic = True

    # Quiz row
    quiz_row = agenda_tbl.add_row()
    for ci, txt in enumerate([_t(spr, "ag_q"), _t(spr, "ag_quiz"),
                              _t(spr, "ag_quiz_dauer")]):
        cell = quiz_row.cells[ci]
        _set_shading(cell, _QUIZ_BG.lstrip("#"))
        _set_border(cell)
        p = cell.paragraphs[0]
        r_ = p.add_run(txt)
        r_.font.size = Pt(9)
        r_.bold = ci < 2

    doc.add_paragraph()

    # ── 2. Training content per audience ─────────────────────────────────────
    _heading(doc, _t(spr, "h_inhalte"), level=1)

    for zg in zielgruppen:
        zg_info = ZIELGRUPPEN.get(zg, {})
        zg_color = zg_info.get("farbe", _ALL_COL)
        zg_label = _feld(zg_info, "label", spr) or zg
        zg_desc  = _feld(zg_info, "beschreibung", spr) or ""

        _banner(doc, _t(spr, "zielgruppe_banner", label=zg_label, desc=zg_desc),
                zg_color, size=11)
        doc.add_paragraph()

        for topic in TRAINING_OUTLINE.get(zg, []):
            if themen is not None and topic["id"] not in themen:
                continue

            # Topic header
            _heading(doc, _t(spr, "thema_kopf", id=topic['id'],
                             titel=_feld(topic, "titel", spr)),
                     level=2, color=zg_color)

            meta_p = doc.add_paragraph()
            mr = meta_p.add_run(_t(spr, "thema_meta",
                                   lernziel=_feld(topic, "lernziel", spr),
                                   min=topic['dauer_min']))
            mr.italic = True
            mr.font.size = Pt(9)
            r_, g_, b_ = _hex_rgb(zg_color)
            mr.font.color.rgb = RGBColor(r_, g_, b_)
            meta_p.paragraph_format.space_after = Pt(4)

            for inhalt in _feld(topic, "inhalte", spr) or []:
                _bullet(doc, inhalt)

            doc.add_paragraph()

        # Szenarien for this audience
        szenarien = SZENARIEN.get(zg, [])
        if szenarien:
            _heading(doc, _t(spr, "h_szenarien"), level=2, color=zg_color)
            for sz in szenarien:
                szen_tbl = doc.add_table(rows=0, cols=1)
                hrow = szen_tbl.add_row()
                hc = hrow.cells[0]
                _set_shading(hc, _SZEN_BG.lstrip("#"))
                _set_border(hc, "FFB300")
                hp = hc.paragraphs[0]
                hr_ = hp.add_run(_feld(sz, "titel", spr))
                hr_.bold = True
                hr_.font.size = Pt(10)

                brow = szen_tbl.add_row()
                bc = brow.cells[0]
                _set_shading(bc, "FFFDE7")
                _set_border(bc, "FFB300")
                bp = bc.paragraphs[0]
                br_ = bp.add_run(_feld(sz, "beschreibung", spr))
                br_.font.size = Pt(9)

                frow = szen_tbl.add_row()
                fc = frow.cells[0]
                _set_shading(fc, "FFF9C4")
                _set_border(fc, "FFB300")
                fp = fc.paragraphs[0]
                fr_ = fp.add_run(_t(spr, "szen_frage",
                                    frage=_feld(sz, "frage", spr)))
                fr_.bold = True
                fr_.font.size = Pt(9)

                lrow = szen_tbl.add_row()
                lc = lrow.cells[0]
                _set_shading(lc, "F1F8E9")
                _set_border(lc, "8BC34A")
                lp = lc.paragraphs[0]
                lr_ = lp.add_run(_t(spr, "musterloesung"))
                lr_.bold = True
                lr_.font.size = Pt(9)
                for step in _feld(sz, "loesung", spr) or []:
                    sp = lc.add_paragraph(_t(spr, "loesung_schritt", schritt=step))
                    if sp.runs:
                        sp.runs[0].font.size = Pt(9)

                doc.add_paragraph()

        doc.add_paragraph()

    # ── 3. Quiz ───────────────────────────────────────────────────────────────
    _heading(doc, _t(spr, "h_quiz"), level=1)
    _body(doc, _t(spr, "quiz_intro"))
    doc.add_paragraph()

    q_num = 1
    for zg in zielgruppen:
        fragen = QUIZ_FRAGEN.get(zg, [])
        if not fragen:
            continue
        zg_label = _feld(ZIELGRUPPEN.get(zg, {}), "label", spr) or zg
        _heading(doc, _t(spr, "fragen_fuer", label=zg_label), level=2,
                 color=ZIELGRUPPEN.get(zg, {}).get("farbe", _ALL_COL))
        for frage in fragen:
            q_tbl = doc.add_table(rows=0, cols=1)
            qhrow = q_tbl.add_row()
            qhc = qhrow.cells[0]
            _set_shading(qhc, _QUIZ_BG.lstrip("#"))
            _set_border(qhc, "1565C0")
            qhp = qhc.paragraphs[0]
            qhr_ = qhp.add_run(_t(spr, "frage_kopf", nr=q_num,
                                  frage=_feld(frage, "frage", spr)))
            qhr_.bold = True
            qhr_.font.size = Pt(10)

            for opt in _feld(frage, "optionen", spr) or []:
                optrow = q_tbl.add_row()
                optc = optrow.cells[0]
                _set_shading(optc, "EEF2FF")
                _set_border(optc, "C5CAE9")
                optp = optc.paragraphs[0]
                optr_ = optp.add_run(_t(spr, "option_zeile", option=opt))
                optr_.font.size = Pt(9)

            ansrow = q_tbl.add_row()
            ansc = ansrow.cells[0]
            _set_shading(ansc, "E8F5E9")
            _set_border(ansc, "66BB6A")
            ansp = ansc.paragraphs[0]
            # `antwort` bleibt unübersetzt — ein Datenwert, der auf den
            # Buchstaben einer Option zeigt.
            ansr_ = ansp.add_run(_t(spr, "antwort_zeile",
                                    antwort=frage['antwort'],
                                    erklaerung=_feld(frage, "erklaerung", spr)))
            ansr_.bold = True
            ansr_.font.size = Pt(9)
            r_, g_, b_ = _hex_rgb(_IT_COL)
            ansr_.font.color.rgb = RGBColor(r_, g_, b_)

            doc.add_paragraph()
            q_num += 1

    # ── Legal disclaimer ──────────────────────────────────────────────────────
    _banner(doc,
            _t(spr, "disclaimer"),
            _DRAFT_BG, fg=_DRAFT_FG, size=9)

    # ── Save ──────────────────────────────────────────────────────────────────
    # Der Dateiname bleibt in jeder Sprache derselbe: Er ist ein Bezeichner und
    # kein Dokumenttext.
    ts = date.today().strftime("%Y%m%d")
    zg_slug = "_".join(zielgruppen)
    filename = f"DSGVO_Schulung_{_safe_filename(firma)}_{zg_slug}_{ts}.docx"
    out_path = out_dir / filename
    doc.save(str(out_path))
    return out_path
