"""DSGVO-Anforderungskatalog – Verordnung (EU) 2016/679 (Datenschutz-Grundverordnung).

Jede Anforderung ist mit dem exakten Artikelverweis versehen, um wissenschaftliche
Transparenz und Nachvollziehbarkeit im Bericht sicherzustellen.
"""
from __future__ import annotations

from typing import Any

# ── Organisationstypen ────────────────────────────────────────────────────────
ORGANISATIONSTYPEN = {
    "verantwortlicher": {
        "label": "Verantwortlicher (Art. 4 Nr. 7 DSGVO)",
        "farbe": "#1565c0",
        "beschreibung": (
            "Natürliche oder juristische Person, Behörde, Einrichtung oder andere Stelle, "
            "die über Zwecke und Mittel der Verarbeitung personenbezogener Daten entscheidet."
        ),
        "referenz": "Verordnung (EU) 2016/679, Art. 4 Nr. 7",
    },
    "auftragsverarbeiter": {
        "label": "Auftragsverarbeiter (Art. 4 Nr. 8 DSGVO)",
        "farbe": "#4a148c",
        "beschreibung": (
            "Natürliche oder juristische Person, Behörde, Einrichtung oder andere Stelle, "
            "die personenbezogene Daten im Auftrag des Verantwortlichen verarbeitet."
        ),
        "referenz": "Verordnung (EU) 2016/679, Art. 4 Nr. 8",
    },
    "beides": {
        "label": "Verantwortlicher und Auftragsverarbeiter",
        "farbe": "#00695c",
        "beschreibung": (
            "Organisation tritt sowohl als Verantwortlicher für eigene Verarbeitungen "
            "als auch als Auftragsverarbeiter für Dritte auf."
        ),
        "referenz": "Verordnung (EU) 2016/679, Art. 4 Nr. 7 und 8",
    },
}

# ── Kapitel / Domänen ─────────────────────────────────────────────────────────
KAPITEL = {
    "GDS1": {
        "titel": "Grundsätze & Rechtmäßigkeit",
        "untertitel": "Verarbeitungsgrundsätze und Rechtsgrundlagen",
        "farbe": "#1565c0",
        "soft": "#e3f2fd",
        "referenz": "Verordnung (EU) 2016/679, Art. 5, 6, 7, 9",
        "beschreibung": (
            "Grundlegende Verarbeitungsprinzipien: Rechtmäßigkeit, Zweckbindung, "
            "Datenminimierung, Richtigkeit, Speicherbegrenzung, Integrität/Vertraulichkeit "
            "und Rechenschaftspflicht. Anforderungen an Rechtsgrundlagen und Einwilligung."
        ),
    },
    "GDS2": {
        "titel": "Betroffenenrechte",
        "untertitel": "Transparenz und individuelle Rechte",
        "farbe": "#4a148c",
        "soft": "#f3e5f5",
        "referenz": "Verordnung (EU) 2016/679, Art. 12–22",
        "beschreibung": (
            "Informationspflichten bei Erhebung personenbezogener Daten sowie "
            "Umsetzung der Betroffenenrechte: Auskunft, Berichtigung, Löschung, "
            "Einschränkung, Datenübertragbarkeit und Widerspruch."
        ),
    },
    "GDS3": {
        "titel": "Pflichten des Verantwortlichen",
        "untertitel": "Accountability und Governance",
        "farbe": "#00695c",
        "soft": "#e0f2f1",
        "referenz": "Verordnung (EU) 2016/679, Art. 24–26, 28, 30",
        "beschreibung": (
            "Allgemeine Pflichten: Nachweispflicht (Accountability), Privacy by Design "
            "und by Default, gemeinsam Verantwortliche, Auftragsverarbeitung und "
            "Verzeichnis von Verarbeitungstätigkeiten."
        ),
    },
    "GDS4": {
        "titel": "Technische & organisatorische Maßnahmen",
        "untertitel": "Datensicherheit (Art. 32)",
        "farbe": "#bf360c",
        "soft": "#fbe9e7",
        "referenz": "Verordnung (EU) 2016/679, Art. 32",
        "beschreibung": (
            "Geeignete technische und organisatorische Maßnahmen zum Schutz "
            "personenbezogener Daten unter Berücksichtigung von Stand der Technik, "
            "Implementierungskosten und Risiko."
        ),
    },
    "GDS5": {
        "titel": "Meldepflichten & Datenschutz-Folgenabschätzung",
        "untertitel": "Incident Response und DSFA",
        "farbe": "#e65100",
        "soft": "#fff3e0",
        "referenz": "Verordnung (EU) 2016/679, Art. 33–36",
        "beschreibung": (
            "Meldepflicht bei Datenschutzverletzungen (72 Stunden an Aufsichtsbehörde), "
            "Benachrichtigung betroffener Personen und Datenschutz-Folgenabschätzung "
            "bei Hochrisikoverarbeitungen."
        ),
    },
    "GDS6": {
        "titel": "Datenschutzbeauftragter & Drittlandtransfer",
        "untertitel": "DPO und internationale Übermittlungen",
        "farbe": "#2c3e50",
        "soft": "#ecf0f1",
        "referenz": "Verordnung (EU) 2016/679, Art. 37–39, 44–49",
        "beschreibung": (
            "Benennung und Aufgaben des Datenschutzbeauftragten sowie "
            "Anforderungen an die Übermittlung personenbezogener Daten in Drittländer "
            "(Angemessenheitsbeschluss, Standardvertragsklauseln, BCR)."
        ),
    },
}

# ── Bewertungsskala ───────────────────────────────────────────────────────────
BEWERTUNG_SKALA = {
    0: {"label": "Nicht bewertet", "farbe": "#9e9e9e", "reife_pct": 0},
    1: {"label": "Nicht vorhanden", "farbe": "#c62828", "reife_pct": 0},
    2: {"label": "In Planung", "farbe": "#e65100", "reife_pct": 25},
    3: {"label": "Teilweise umgesetzt", "farbe": "#f57f17", "reife_pct": 50},
    4: {"label": "Überwiegend umgesetzt", "farbe": "#2e7d32", "reife_pct": 75},
    5: {"label": "Vollständig umgesetzt", "farbe": "#1b5e20", "reife_pct": 100},
}

BEWERTUNG_LABELS = [v["label"] for v in BEWERTUNG_SKALA.values()]

# ── Anforderungskatalog ───────────────────────────────────────────────────────
DSGVO_ANFORDERUNGEN: list[dict[str, Any]] = [
    # ── GDS1: Grundsätze & Rechtmäßigkeit ────────────────────────────────────
    {
        "id": "GDS1-01",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. a DSGVO",
        "titel": "Rechtmäßigkeit, Verarbeitung nach Treu und Glauben, Transparenz",
        "beschreibung": (
            "Personenbezogene Daten müssen auf rechtmäßige Weise, nach Treu und Glauben "
            "und in einer für die betroffene Person nachvollziehbaren Weise verarbeitet werden."
        ),
        "hinweise": (
            "Dokumentation aller Rechtsgrundlagen je Verarbeitungszweck; "
            "Datenschutzerklärung in klarer, verständlicher Sprache; "
            "Keine irreführenden oder verdeckten Datenerhebungen; "
            "Regelmäßige Überprüfung der Rechtsgrundlagen auf Aktualität."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-02",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. b DSGVO",
        "titel": "Zweckbindung – Verarbeitung nur für festgelegte Zwecke",
        "beschreibung": (
            "Personenbezogene Daten dürfen nur für festgelegte, eindeutige und "
            "legitime Zwecke erhoben werden. Eine Weiterverarbeitung für andere Zwecke "
            "ist nur unter bestimmten Bedingungen zulässig (Kompatibilitätsprüfung)."
        ),
        "hinweise": (
            "Verarbeitungszwecke vor Datenerhebung exakt definieren und dokumentieren; "
            "Zweckänderungen prüfen (Art. 6 Abs. 4 DSGVO – Kompatibilitätskriterien); "
            "Keine Zweckentfremdung von Daten; "
            "Zwecke im Verzeichnis der Verarbeitungstätigkeiten festhalten."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-03",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. c DSGVO",
        "titel": "Datenminimierung – Beschränkung auf das Notwendige",
        "beschreibung": (
            "Personenbezogene Daten müssen dem Verarbeitungszweck angemessen und "
            "erheblich sein sowie auf das für die Zwecke der Verarbeitung notwendige Maß beschränkt sein."
        ),
        "hinweise": (
            "Privacy-Impact-Analyse vor jeder neuen Verarbeitung; "
            "Regelmäßige Überprüfung: Werden wirklich alle erhobenen Felder benötigt?; "
            "Pseudonymisierung und Anonymisierung wo möglich; "
            "Keine 'auf Vorrat'-Erhebung von Daten."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS1-04",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. d DSGVO",
        "titel": "Richtigkeit – Daten aktuell und korrekt halten",
        "beschreibung": (
            "Personenbezogene Daten müssen sachlich richtig und erforderlichenfalls "
            "auf dem neuesten Stand sein. Unrichtige Daten müssen unverzüglich "
            "gelöscht oder berichtigt werden."
        ),
        "hinweise": (
            "Prozess zur Datenpflege und Aktualisierung; "
            "Mechanismus für Betroffene zur Datenkorretur (Art. 16 DSGVO); "
            "Regelmäßige Datenqualitätsprüfungen; "
            "Protokollierung von Berichtigungen."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS1-05",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. e DSGVO",
        "titel": "Speicherbegrenzung – Löschkonzept und Aufbewahrungsfristen",
        "beschreibung": (
            "Personenbezogene Daten dürfen nur so lange gespeichert werden, wie es "
            "für die Zwecke der Verarbeitung erforderlich ist. Es muss ein "
            "dokumentiertes Löschkonzept existieren."
        ),
        "hinweise": (
            "Löschkonzept mit Aufbewahrungsfristen je Datenkategorie; "
            "Automatisierte Löschroutinen implementieren; "
            "Dokumentation gesetzlicher Aufbewahrungspflichten (HGB, AO etc.); "
            "Regelmäßige Überprüfung gespeicherter Daten auf Löschreife."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-06",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 1 lit. f DSGVO",
        "titel": "Integrität und Vertraulichkeit – Datensicherheit",
        "beschreibung": (
            "Personenbezogene Daten müssen durch geeignete technische und organisatorische "
            "Maßnahmen vor unbefugter oder unrechtmäßiger Verarbeitung sowie vor "
            "unbeabsichtigtem Verlust, Zerstörung oder Schädigung geschützt werden."
        ),
        "hinweise": (
            "Verschlüsselung personenbezogener Daten (at rest und in transit); "
            "Zugriffskontrollen und Need-to-Know-Prinzip; "
            "Regelmäßige Sicherheitsaudits; "
            "Mitarbeiterschulungen zum Datenschutz."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-07",
        "kapitel": "GDS1",
        "ref": "Art. 5 Abs. 2 DSGVO",
        "titel": "Rechenschaftspflicht (Accountability) – Nachweisführung",
        "beschreibung": (
            "Der Verantwortliche muss die Einhaltung aller DSGVO-Grundsätze "
            "nachweisen können (Accountability-Prinzip). Alle Maßnahmen müssen "
            "dokumentiert und auf Anfrage vorlegbar sein."
        ),
        "hinweise": (
            "Dokumentationssystem für alle Datenschutzmaßnahmen; "
            "Verzeichnis der Verarbeitungstätigkeiten (Art. 30 DSGVO); "
            "Datenschutz-Policies und Verfahrensanweisungen; "
            "Regelmäßige interne Datenschutzaudits."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-08",
        "kapitel": "GDS1",
        "ref": "Art. 6 DSGVO",
        "titel": "Rechtsgrundlage für jede Verarbeitung",
        "beschreibung": (
            "Jede Verarbeitung personenbezogener Daten erfordert eine Rechtsgrundlage "
            "nach Art. 6 DSGVO: Einwilligung, Vertrag, rechtliche Verpflichtung, "
            "lebenswichtige Interessen, öffentliche Aufgabe oder berechtigte Interessen."
        ),
        "hinweise": (
            "Mapping aller Verarbeitungen auf Rechtsgrundlagen; "
            "Berechtigte-Interessen-Abwägung dokumentieren (Art. 6 Abs. 1 lit. f); "
            "Einwilligungsverwaltungssystem (Consent Management); "
            "Kein Rückgriff auf berechtigte Interessen bei Behörden."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS1-09",
        "kapitel": "GDS1",
        "ref": "Art. 7 DSGVO",
        "titel": "Einwilligungsmanagement – Freiwilligkeit und Widerruf",
        "beschreibung": (
            "Wenn die Einwilligung als Rechtsgrundlage genutzt wird, muss diese "
            "freiwillig, spezifisch, informiert und unmissverständlich sein. "
            "Der Widerruf muss jederzeit möglich sein."
        ),
        "hinweise": (
            "Klare, granulare Einwilligungstexte ohne Vorgabehäkchen; "
            "Nachweis der erteilten Einwilligung (Zeitstempel, Version); "
            "Einfacher Widerrufsmechanismus; "
            "Keine Kopplung von Einwilligung an Vertrag (Art. 7 Abs. 4 DSGVO)."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS1-10",
        "kapitel": "GDS1",
        "ref": "Art. 9 DSGVO",
        "titel": "Besondere Kategorien personenbezogener Daten",
        "beschreibung": (
            "Die Verarbeitung sensibler Datenkategorien (Gesundheit, Herkunft, Religion, "
            "biometrische Daten etc.) ist grundsätzlich verboten und nur in engen "
            "Ausnahmen nach Art. 9 Abs. 2 DSGVO zulässig."
        ),
        "hinweise": (
            "Inventar sensibler Datenkategorien; "
            "Explizite Rechtsgrundlage nach Art. 9 Abs. 2 für jede Verarbeitung; "
            "Erhöhte Sicherheitsmaßnahmen für sensible Daten; "
            "DSFA regelmäßig erforderlich (Art. 35 Abs. 3 lit. b DSGVO)."
        ),
        "gewichtung": 3,
    },
    # ── GDS2: Betroffenenrechte ───────────────────────────────────────────────
    {
        "id": "GDS2-01",
        "kapitel": "GDS2",
        "ref": "Art. 12–14 DSGVO",
        "titel": "Informationspflichten bei Datenerhebung",
        "beschreibung": (
            "Betroffene Personen müssen bei der Erhebung ihrer Daten transparent "
            "informiert werden: Verantwortlicher, Zwecke, Rechtsgrundlagen, "
            "Empfänger, Speicherdauer, Betroffenenrechte und Beschwerderecht."
        ),
        "hinweise": (
            "Datenschutzerklärung / Datenschutzhinweise (Layer-1 und Layer-2); "
            "Informationen verständlich, leicht zugänglich, kostenlos; "
            "Bei indirekter Erhebung: Information innerhalb eines Monats; "
            "Unterscheidung: direkte Erhebung (Art. 13) vs. indirekte Erhebung (Art. 14)."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS2-02",
        "kapitel": "GDS2",
        "ref": "Art. 15 DSGVO",
        "titel": "Auskunftsrecht – Prozess zur Bearbeitung von Anfragen",
        "beschreibung": (
            "Betroffene haben das Recht, Auskunft über ihre verarbeiteten Daten zu erhalten: "
            "Kategorien, Zwecke, Empfänger, Speicherdauer, Rechte, Herkunft der Daten "
            "und Informationen zu automatisierten Entscheidungen."
        ),
        "hinweise": (
            "Definierter Prozess zur Bearbeitung von Auskunftsanfragen; "
            "Identitätsverifikation der anfragenden Person; "
            "Antwortfrist: 1 Monat (verlängerbar auf 3 Monate mit Begründung); "
            "Kostenfreiheit (außer bei offensichtlich unbegründeten/exzessiven Anfragen)."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS2-03",
        "kapitel": "GDS2",
        "ref": "Art. 16–17 DSGVO",
        "titel": "Berichtigung und Löschung ('Recht auf Vergessenwerden')",
        "beschreibung": (
            "Betroffene haben das Recht auf Berichtigung unrichtiger Daten (Art. 16) "
            "und auf Löschung ihrer Daten unter bestimmten Voraussetzungen (Art. 17), "
            "z.B. wenn der Zweck entfallen ist oder die Einwilligung widerrufen wurde."
        ),
        "hinweise": (
            "Prozess zur Bearbeitung von Lösch- und Berichtigungsanfragen; "
            "Kaskaden-Löschung: Unterauftragsverhältnisse informieren; "
            "Löschprotokolle führen; "
            "Ausnahmen dokumentieren (gesetzliche Aufbewahrungspflichten)."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS2-04",
        "kapitel": "GDS2",
        "ref": "Art. 18–19 DSGVO",
        "titel": "Einschränkung der Verarbeitung und Mitteilungspflicht",
        "beschreibung": (
            "Betroffene können die Einschränkung der Verarbeitung verlangen (Art. 18), "
            "z.B. während der Überprüfung einer Berichtigung. Der Verantwortliche muss "
            "Empfänger über Berichtigungen/Löschungen informieren (Art. 19)."
        ),
        "hinweise": (
            "Technische Umsetzung der 'Einschränkung' (z.B. Markierung, Separierung); "
            "Mitteilungsprozess an Empfänger bei Berichtigungen/Löschungen; "
            "Aufhebung der Einschränkung mit Vorabinformation; "
            "Dokumentation aller Einschränkungsanfragen."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS2-05",
        "kapitel": "GDS2",
        "ref": "Art. 20 DSGVO",
        "titel": "Recht auf Datenübertragbarkeit",
        "beschreibung": (
            "Betroffene haben bei Verarbeitung auf Basis der Einwilligung oder zur "
            "Vertragserfüllung das Recht, ihre Daten in maschinenlesbarem Format zu erhalten "
            "und an einen anderen Verantwortlichen zu übertragen."
        ),
        "hinweise": (
            "Export-Funktion für personenbezogene Daten in strukturiertem Format (JSON, CSV, XML); "
            "Direkte Übertragung an anderen Verantwortlichen, wenn technisch möglich; "
            "Gilt nur für automatisiert verarbeitete Daten; "
            "Keine Beeinträchtigung der Rechte anderer Personen."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS2-06",
        "kapitel": "GDS2",
        "ref": "Art. 21–22 DSGVO",
        "titel": "Widerspruchsrecht und automatisierte Entscheidungsfindung",
        "beschreibung": (
            "Betroffene haben das Recht, der Verarbeitung zu widersprechen (Art. 21), "
            "insbesondere bei Direktwerbung. Art. 22 schützt vor rein automatisierten "
            "Entscheidungen mit erheblicher Auswirkung."
        ),
        "hinweise": (
            "Opt-out-Mechanismus für Direktwerbung und Profiling; "
            "Dokumentation von Widersprüchen und Konsequenzen; "
            "Bei automatisierten Entscheidungen: Recht auf Überprüfung durch Menschen; "
            "Information über automatisierte Entscheidungsprozesse (Art. 13/14 Abs. 2 lit. f)."
        ),
        "gewichtung": 2,
    },
    # ── GDS3: Pflichten des Verantwortlichen ──────────────────────────────────
    {
        "id": "GDS3-01",
        "kapitel": "GDS3",
        "ref": "Art. 24 DSGVO",
        "titel": "Verantwortung des Verantwortlichen – Datenschutz-Governance",
        "beschreibung": (
            "Der Verantwortliche muss geeignete technische und organisatorische Maßnahmen "
            "implementieren und nachweisen können, dass die Verarbeitung gemäß DSGVO erfolgt. "
            "Richtlinien müssen regelmäßig überprüft und aktualisiert werden."
        ),
        "hinweise": (
            "Datenschutz-Policy und interne Richtlinien; "
            "Management-Commitment zum Datenschutz; "
            "Regelmäßige Überprüfung und Aktualisierung der Maßnahmen; "
            "Schulungen und Awareness-Programme für Mitarbeiter."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS3-02",
        "kapitel": "GDS3",
        "ref": "Art. 25 DSGVO",
        "titel": "Datenschutz durch Technikgestaltung und durch datenschutzfreundliche Voreinstellungen",
        "beschreibung": (
            "Privacy by Design: Datenschutz muss bereits bei der Konzeption von Systemen "
            "und Prozessen berücksichtigt werden. Privacy by Default: Die datenschutzfreundlichste "
            "Option muss die Voreinstellung sein."
        ),
        "hinweise": (
            "Privacy-by-Design-Checkliste für neue Produkte und Prozesse; "
            "Datenschutzfreundliche Voreinstellungen (kein Opt-out erforderlich); "
            "Datenminimierung als Designprinzip; "
            "Privacy Impact Assessment (PIA) als fester Prozessschritt."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS3-03",
        "kapitel": "GDS3",
        "ref": "Art. 26 DSGVO",
        "titel": "Gemeinsam Verantwortliche – Vereinbarung und Transparenz",
        "beschreibung": (
            "Wenn zwei oder mehr Verantwortliche gemeinsam über Zwecke und Mittel "
            "der Verarbeitung entscheiden, müssen sie eine transparente Vereinbarung "
            "treffen und das Wesentliche den Betroffenen mitteilen."
        ),
        "hinweise": (
            "Prüfung aller Verarbeitungen auf gemeinsame Verantwortlichkeit; "
            "Schriftliche Vereinbarung nach Art. 26 DSGVO; "
            "Anlaufstelle für Betroffene bestimmen; "
            "Inhalt der Vereinbarung in Datenschutzerklärung kommunizieren."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS3-04",
        "kapitel": "GDS3",
        "ref": "Art. 28 DSGVO",
        "titel": "Auftragsverarbeitung – AVV und Kontrolle der Auftragsverarbeiter",
        "beschreibung": (
            "Wenn Dritte im Auftrag des Verantwortlichen personenbezogene Daten verarbeiten, "
            "ist ein Auftragsverarbeitungsvertrag (AVV) nach Art. 28 DSGVO erforderlich. "
            "Der Auftragsverarbeiter muss hinreichende Garantien bieten."
        ),
        "hinweise": (
            "AVV mit allen Auftragsverarbeitern abschließen (Mindestinhalt Art. 28 Abs. 3); "
            "Due Diligence der Auftragsverarbeiter vor Beauftragung; "
            "Unterauftragsverarbeiter-Genehmigung regeln; "
            "Regelmäßige Überprüfung der Auftragsverarbeiter (Audits, Zertifizierungen)."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS3-05",
        "kapitel": "GDS3",
        "ref": "Art. 30 DSGVO",
        "titel": "Verzeichnis von Verarbeitungstätigkeiten (VVT)",
        "beschreibung": (
            "Verantwortliche (und Auftragsverarbeiter) müssen ein Verzeichnis aller "
            "Verarbeitungstätigkeiten führen, das Angaben zu Zwecken, Kategorien, "
            "Empfängern, Löschfristen und technisch-organisatorischen Maßnahmen enthält."
        ),
        "hinweise": (
            "VVT in strukturierter, aktueller Form (Art. 30 Abs. 1); "
            "Alle Verarbeitungen vollständig erfassen; "
            "Regelmäßige Aktualisierung (insb. bei neuen Verarbeitungen); "
            "VVT auf Anfrage der Aufsichtsbehörde vorlegen können."
        ),
        "gewichtung": 3,
    },
    # ── GDS4: Technische & organisatorische Maßnahmen ─────────────────────────
    {
        "id": "GDS4-01",
        "kapitel": "GDS4",
        "ref": "Art. 32 Abs. 1 lit. a DSGVO",
        "titel": "Pseudonymisierung und Verschlüsselung personenbezogener Daten",
        "beschreibung": (
            "Als geeignete Maßnahme zur Datensicherheit ist die Pseudonymisierung "
            "und Verschlüsselung personenbezogener Daten zu implementieren, um "
            "ein dem Risiko angemessenes Schutzniveau zu gewährleisten."
        ),
        "hinweise": (
            "Verschlüsselung ruhender Daten (AES-256 o.ä.); "
            "Verschlüsselung bei Übertragung (TLS 1.2+); "
            "Pseudonymisierungsverfahren wo möglich; "
            "Schlüsselverwaltungskonzept."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS4-02",
        "kapitel": "GDS4",
        "ref": "Art. 32 Abs. 1 lit. b DSGVO",
        "titel": "Dauerhafter Schutz von Vertraulichkeit, Integrität, Verfügbarkeit und Belastbarkeit",
        "beschreibung": (
            "Es müssen Maßnahmen getroffen werden, die dauerhaft die Vertraulichkeit, "
            "Integrität, Verfügbarkeit und Belastbarkeit der Verarbeitungssysteme "
            "und -dienste gewährleisten."
        ),
        "hinweise": (
            "Zugriffskontrollen (RBAC, MFA); "
            "Integritätsprüfungen der Daten; "
            "Redundanz und Failover-Konzepte; "
            "Business-Continuity-Planung für Datenverarbeitungssysteme."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS4-03",
        "kapitel": "GDS4",
        "ref": "Art. 32 Abs. 1 lit. c DSGVO",
        "titel": "Wiederherstellbarkeit nach Datenpannen",
        "beschreibung": (
            "Es muss die Fähigkeit bestehen, Verfügbarkeit und Zugang zu "
            "personenbezogenen Daten bei einem physischen oder technischen Zwischenfall "
            "rasch wiederherstellen zu können."
        ),
        "hinweise": (
            "Backup-Konzept mit regelmäßigen Tests; "
            "Disaster-Recovery-Plan für personenbezogene Daten; "
            "Dokumentierte Recovery Time Objective (RTO) und Recovery Point Objective (RPO); "
            "Regelmäßige Wiederherstellungstests."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS4-04",
        "kapitel": "GDS4",
        "ref": "Art. 32 Abs. 1 lit. d DSGVO",
        "titel": "Überprüfung und Bewertung der Sicherheitsmaßnahmen",
        "beschreibung": (
            "Es muss ein Verfahren zur regelmäßigen Überprüfung, Bewertung und "
            "Evaluierung der Wirksamkeit der technischen und organisatorischen "
            "Maßnahmen zur Gewährleistung der Sicherheit der Verarbeitung existieren."
        ),
        "hinweise": (
            "Jährliche Datenschutzaudits (intern und/oder extern); "
            "Penetrationstests für datenschutzrelevante Systeme; "
            "Schwachstellenmanagement; "
            "Dokumentation der Prüfergebnisse und Maßnahmen."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS4-05",
        "kapitel": "GDS4",
        "ref": "Art. 32 Abs. 4 DSGVO",
        "titel": "Mitarbeiterverpflichtung – Zugang nur für autorisierte Personen",
        "beschreibung": (
            "Personen, die Zugang zu personenbezogenen Daten haben, dürfen diese "
            "nur auf Weisung des Verantwortlichen verarbeiten, es sei denn, "
            "sie sind durch das Unionsrecht oder das Recht der Mitgliedstaaten dazu verpflichtet."
        ),
        "hinweise": (
            "Verpflichtung zur Vertraulichkeit / Datengeheimnis; "
            "Need-to-Know-Prinzip bei Zugriffsrechten; "
            "Regelmäßige Datenschutzschulungen für alle Mitarbeiter; "
            "Offboarding-Prozess mit sofortigem Entzug der Zugriffsrechte."
        ),
        "gewichtung": 2,
    },
    # ── GDS5: Meldepflichten & DSFA ───────────────────────────────────────────
    {
        "id": "GDS5-01",
        "kapitel": "GDS5",
        "ref": "Art. 33 DSGVO",
        "titel": "Meldung von Datenschutzverletzungen an die Aufsichtsbehörde",
        "beschreibung": (
            "Datenschutzverletzungen müssen unverzüglich (in der Regel innerhalb von "
            "72 Stunden) der zuständigen Aufsichtsbehörde gemeldet werden, sofern die "
            "Verletzung voraussichtlich zu einem Risiko für natürliche Personen führt."
        ),
        "hinweise": (
            "Incident-Response-Prozess mit klarer Klassifizierungspflicht; "
            "Risikoabschätzung nach Datenpanne (Risiko vs. kein Risiko vs. hohes Risiko); "
            "72-Stunden-Frist einhalten – Meldung auch bei unvollständiger Information; "
            "Meldekontakt: BSI und zuständige Landesdatenschutzbehörde."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS5-02",
        "kapitel": "GDS5",
        "ref": "Art. 34 DSGVO",
        "titel": "Benachrichtigung betroffener Personen bei hohem Risiko",
        "beschreibung": (
            "Wenn eine Datenschutzverletzung voraussichtlich ein hohes Risiko für "
            "die Rechte und Freiheiten natürlicher Personen zur Folge hat, müssen "
            "die betroffenen Personen unverzüglich benachrichtigt werden."
        ),
        "hinweise": (
            "Kriterien für 'hohes Risiko' definieren und dokumentieren; "
            "Benachrichtigungstext: Art der Verletzung, Kontaktdaten DSB, Konsequenzen, Maßnahmen; "
            "Ausnahmen prüfen (Maßnahmen vor Verletzung, Unverhältnismäßigkeit); "
            "Dokumentation aller Benachrichtigungen."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS5-03",
        "kapitel": "GDS5",
        "ref": "Art. 33 Abs. 5 DSGVO",
        "titel": "Dokumentation aller Datenschutzverletzungen",
        "beschreibung": (
            "Alle Datenschutzverletzungen müssen dokumentiert werden, einschließlich "
            "der damit verbundenen Fakten, Auswirkungen und ergriffenen Abhilfemaßnahmen, "
            "auch wenn keine Meldepflicht bestand."
        ),
        "hinweise": (
            "Datenschutzpannen-Register führen; "
            "Dokumentation: Zeitpunkt, Art der Verletzung, Betroffene, Auswirkungen, Maßnahmen; "
            "Aufbewahrungsfrist: Mindestens 3 Jahre für Prüfzwecke; "
            "Auch 'Near-Miss'-Vorfälle erfassen."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS5-04",
        "kapitel": "GDS5",
        "ref": "Art. 35 DSGVO",
        "titel": "Datenschutz-Folgenabschätzung (DSFA)",
        "beschreibung": (
            "Vor Beginn einer Verarbeitung, die voraussichtlich ein hohes Risiko birgt, "
            "muss der Verantwortliche eine Datenschutz-Folgenabschätzung durchführen. "
            "Dies gilt insbesondere für Profiling, systematische Überwachung und "
            "Verarbeitung besonderer Datenkategorien in großem Umfang."
        ),
        "hinweise": (
            "Screening-Prozess zur Identifikation DSFA-pflichtiger Verarbeitungen; "
            "Muss-Liste der zuständigen Aufsichtsbehörde beachten; "
            "DSFA-Inhalte: Verarbeitungsbeschreibung, Notwendigkeitsbewertung, Risikoabschätzung, Maßnahmen; "
            "Überprüfung bei wesentlichen Änderungen der Verarbeitung."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS5-05",
        "kapitel": "GDS5",
        "ref": "Art. 36 DSGVO",
        "titel": "Vorherige Konsultation der Aufsichtsbehörde bei hohem Restrisiko",
        "beschreibung": (
            "Ergibt die DSFA, dass die Verarbeitung ein hohes Risiko zur Folge hätte, "
            "sofern der Verantwortliche keine Maßnahmen trifft, muss vor Beginn der "
            "Verarbeitung die Aufsichtsbehörde konsultiert werden."
        ),
        "hinweise": (
            "Klare Kriterien, wann Konsultation erforderlich; "
            "Fristen beachten: Aufsichtsbehörde hat 8 Wochen (+ 6 Wochen Verlängerung); "
            "Verarbeitungsbeginn erst nach Stellungnahme; "
            "Dokumentation des Konsultationsverfahrens."
        ),
        "gewichtung": 2,
    },
    # ── GDS6: Datenschutzbeauftragter & Drittlandtransfer ─────────────────────
    {
        "id": "GDS6-01",
        "kapitel": "GDS6",
        "ref": "Art. 37 DSGVO",
        "titel": "Benennung eines Datenschutzbeauftragten (DSB)",
        "beschreibung": (
            "Ein DSB muss benannt werden, wenn: (a) öffentliche Stelle, "
            "(b) umfangreiche regelmäßige und systematische Überwachung von Personen, "
            "oder (c) umfangreiche Verarbeitung besonderer Datenkategorien. "
            "Freiwillige Benennung ist jederzeit möglich und empfohlen."
        ),
        "hinweise": (
            "Prüfung der Benennungspflicht anhand Art. 37 DSGVO; "
            "DSB intern oder extern bestellen; "
            "Kontaktdaten des DSB veröffentlichen und bei Aufsichtsbehörde melden; "
            "DSB muss Fachwissen in Datenschutzrecht und -praxis besitzen."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS6-02",
        "kapitel": "GDS6",
        "ref": "Art. 38–39 DSGVO",
        "titel": "Aufgaben und Stellung des Datenschutzbeauftragten",
        "beschreibung": (
            "Der DSB muss ordnungsgemäß in alle Datenschutzfragen eingebunden werden, "
            "hat umfassende Aufgaben (Beratung, Überwachung, DSFA-Beratung, Zusammenarbeit "
            "mit Aufsichtsbehörde) und genießt besonderen Schutz (kein Interessenkonflikt, "
            "keine Benachteiligung)."
        ),
        "hinweise": (
            "DSB frühzeitig in Projekte einbinden; "
            "Unabhängigkeit des DSB sicherstellen (kein Weisungsrecht in Datenschutzfragen); "
            "Ressourcen und Weiterbildung für DSB bereitstellen; "
            "Geheimhaltungspflicht des DSB beachten."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS6-03",
        "kapitel": "GDS6",
        "ref": "Art. 44–45 DSGVO",
        "titel": "Drittlandtransfer – Angemessenheitsbeschluss",
        "beschreibung": (
            "Übermittlungen personenbezogener Daten in Drittländer sind nur zulässig, "
            "wenn die Europäische Kommission ein angemessenes Schutzniveau festgestellt hat "
            "(Angemessenheitsbeschluss) oder geeignete Garantien bestehen."
        ),
        "hinweise": (
            "Inventar aller Datentransfers in Drittländer; "
            "Prüfung: Angemessenheitsbeschluss für Empfängerland vorhanden?; "
            "US-Transfer: Data Privacy Framework (DPF) seit 2023; "
            "Dokumentation der Transfergrundlage je Empfänger."
        ),
        "gewichtung": 3,
    },
    {
        "id": "GDS6-04",
        "kapitel": "GDS6",
        "ref": "Art. 46 DSGVO",
        "titel": "Drittlandtransfer – Standardvertragsklauseln (SCC) und BCR",
        "beschreibung": (
            "Ohne Angemessenheitsbeschluss sind Drittlandtransfers nur mit geeigneten "
            "Garantien zulässig: EU-Standardvertragsklauseln (SCC, 2021er Fassung), "
            "verbindliche interne Datenschutzvorschriften (BCR) oder genehmigte Verhaltensregeln."
        ),
        "hinweise": (
            "SCC 2021 (Beschluss (EU) 2021/914) für alle Transfers ohne Angemessenheitsbeschluss; "
            "Transfer Impact Assessment (TIA) als Pflichtbestandteil; "
            "BCR für Konzernintere Transfers in Betracht ziehen; "
            "Regelmäßige Überprüfung der Transfergarantien auf Aktualität."
        ),
        "gewichtung": 2,
    },
    {
        "id": "GDS6-05",
        "kapitel": "GDS6",
        "ref": "Art. 83 DSGVO",
        "titel": "Bußgeldrisiken und Sanktionsregime – Compliance-Monitoring",
        "beschreibung": (
            "Verstöße gegen die DSGVO können mit Bußgeldern bis zu 20 Mio. € bzw. "
            "4% des weltweiten Jahresumsatzes geahndet werden. Ein systematisches "
            "Compliance-Monitoring ist essentiell zur Risikovermeidung."
        ),
        "hinweise": (
            "Systematisches Datenschutz-Compliance-Programm; "
            "Regelmäßige interne Datenschutzaudits; "
            "Eskalationsprozess bei Datenschutzvorfällen; "
            "Dokumentation als Entlastungsnachweis (Art. 83 Abs. 2 lit. k)."
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


def load_merged_anforderungen(db_path: "Path | None" = None) -> list[dict[str, Any]]:
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
    return sorted(base.values(), key=lambda r: (kap_order.get(r.get("kapitel", "GDS6"), 99), r["id"]))


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
