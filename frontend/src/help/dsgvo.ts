// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

export const dsgvoHelp: ModuleHelp = {
  "title": "DSGVO",
  "regulation": "Verordnung (EU) 2016/679 (Datenschutz-Grundverordnung, DSGVO/GDPR) – ergänzt durch das BDSG",
  "purpose": "Das Modul unterstützt die Erfüllung der Pflichten aus der Datenschutz-Grundverordnung. Es bündelt das Führen des Verarbeitungsverzeichnisses, die Dokumentation technischer und organisatorischer Maßnahmen (TOMs), die Prüfung von DSFA-Auslösern und die Nachweise zu Betroffenenrechten und Datenpannen.",
  "legalBasis": {
    "title": "Rechtliche Grundlage",
    "intro": "Die DSGVO verlangt von Verantwortlichen den Nachweis rechtmäßiger, transparenter und sicherer Verarbeitung personenbezogener Daten (Rechenschaftspflicht, Art. 5 Abs. 2). Jede Verarbeitung benötigt eine Rechtsgrundlage; Betroffenenrechte müssen gewahrt, die Verarbeitung dokumentiert und durch angemessene Maßnahmen abgesichert werden. Bei hohem Risiko sind zusätzliche Prüf- und Meldepflichten zu beachten.",
    "bullets": [
      "Grundsätze der Verarbeitung: Rechtmäßigkeit, Zweckbindung, Datenminimierung, Richtigkeit, Speicherbegrenzung, Integrität/Vertraulichkeit sowie Rechenschaftspflicht (Art. 5 Abs. 1 und 2).",
      "Rechtsgrundlagen: jede Verarbeitung muss auf einer Grundlage nach Art. 6 Abs. 1 (z. B. Einwilligung, Vertrag, rechtliche Verpflichtung, berechtigtes Interesse) beruhen; besondere Kategorien zusätzlich nach Art. 9.",
      "Betroffenenrechte: Information (Art. 13/14), Auskunft (Art. 15), Berichtigung (Art. 16), Löschung (Art. 17), Einschränkung (Art. 18), Datenübertragbarkeit (Art. 20), Widerspruch (Art. 21) und automatisierte Einzelentscheidungen (Art. 22); Modalitäten und Fristen nach Art. 12.",
      "Verzeichnis von Verarbeitungstätigkeiten: zu führen nach Art. 30 (Pflichtangaben in Abs. 1 für Verantwortliche, Abs. 2 für Auftragsverarbeiter).",
      "Technische und organisatorische Maßnahmen: Sicherheit der Verarbeitung nach Art. 32 (u. a. Pseudonymisierung/Verschlüsselung, Vertraulichkeit, Integrität, Verfügbarkeit, Belastbarkeit, regelmäßige Überprüfung).",
      "Datenschutz-Folgenabschätzung (DSFA): erforderlich bei voraussichtlich hohem Risiko nach Art. 35; Konsultation der Aufsichtsbehörde nach Art. 36.",
      "Datenpannen: Meldung an die Aufsichtsbehörde binnen 72 Stunden nach Art. 33, Benachrichtigung der Betroffenen bei hohem Risiko nach Art. 34.",
      "Privacy by Design/Default (Art. 25) und Auftragsverarbeitung per Vertrag (Art. 28)."
    ]
  },
  "implementation": {
    "title": "Vorgehen im Modul",
    "intro": "Pflegen Sie zunächst das Verarbeitungsverzeichnis je Verarbeitungstätigkeit, ordnen Sie jeder Tätigkeit Rechtsgrundlage und TOMs zu und prüfen Sie die DSFA-Auslöser. Das Modul erzeugt daraus Nachweise und unterstützt das Management von Betroffenenanfragen und Datenpannen.",
    "bullets": [
      "Verarbeitungstätigkeit anlegen und die Pflichtfelder nach Art. 30 erfassen: Zweck, Kategorien betroffener Personen und Daten, Empfänger, Drittlandübermittlungen, Löschfristen.",
      "Rechtsgrundlage nach Art. 6 Abs. 1 je Tätigkeit dokumentieren; bei besonderen Kategorien zusätzlich Art. 9 angeben und Einwilligungsnachweise hinterlegen.",
      "TOMs nach Kategorien zuordnen (Zutritt, Zugang, Zugriff, Weitergabe, Eingabe, Verfügbarkeit, Trennung) und mit Art. 32 verknüpfen; Wirksamkeit regelmäßig überprüfen.",
      "DSFA-Auslöser je Tätigkeit prüfen (z. B. systematische Bewertung/Profiling, umfangreiche Verarbeitung besonderer Kategorien, systematische Überwachung); bei hohem Risiko DSFA nach Art. 35 starten.",
      "Löschfristen und Speicherbegrenzung festlegen und überwachen; Aufbewahrungspflichten dokumentieren.",
      "Workflows für Betroffenenanfragen mit Fristenüberwachung (Antwort grundsätzlich binnen eines Monats, Art. 12 Abs. 3) und für Datenpannen mit 72-Stunden-Frist (Art. 33) nutzen.",
      "Auftragsverarbeiter erfassen und AV-Verträge nach Art. 28 sowie Drittlandgarantien (Kapitel V) hinterlegen.",
      "Ergebnisse als revisionssichere Nachweise zur Rechenschaftspflicht (Art. 5 Abs. 2) exportieren."
    ]
  },
  "moduleSpecific": {
    "title": "Modul-Besonderheiten",
    "intro": "Das Modul ist auf drei zentrale Bausteine zugeschnitten: Verarbeitungsverzeichnis, TOM-Kategorien und DSFA-Auslöser. Diese sind miteinander verknüpft, sodass aus einer Verarbeitungstätigkeit direkt Risiko- und Maßnahmenbezug entsteht.",
    "bullets": [
      "Verarbeitungsverzeichnis: strukturierte Erfassung aller Pflichtangaben nach Art. 30 mit getrennten Sichten für Verantwortliche (Abs. 1) und Auftragsverarbeiter (Abs. 2).",
      "TOM-Kategorien: vordefinierte Maßnahmenkategorien (Zutritts-, Zugangs-, Zugriffs-, Weitergabe-, Eingabe-, Verfügbarkeits-, Trennungskontrolle) als Vorlage zur Dokumentation nach Art. 32.",
      "DSFA-Auslöser: regelbasierte Prüfung anhand der Kriterien aus Art. 35 Abs. 3 und der Positivlisten der Aufsichtsbehörden zur Entscheidung, ob eine DSFA verpflichtend ist.",
      "Verknüpfung von Tätigkeit, Rechtsgrundlage, TOMs und DSFA-Status für eine konsistente Nachweisführung."
    ]
  },
  "areas": [
    {
      "id": "pflichtdoku",
      "title": "📋 Dokumentation (VVT, Art. 30)",
      "zweck": "Führen des Verzeichnisses von Verarbeitungstätigkeiten (VVT) als zentrale Pflichtdokumentation – je Verarbeitung ein Eintrag mit allen Art.-30-Pflichtangaben.",
      "rechtsgrundlage": "Art. 30 DSGVO (Abs. 1 für Verantwortliche, Abs. 2 für Auftragsverarbeiter)",
      "pflichtfelder": [
        "VVT-ID + Name: eindeutige Kennung (z. B. VVT-001) und sprechende Bezeichnung der Verarbeitung.",
        "Rolle: 'verantwortlicher' oder 'auftragsverarbeiter' – steuert, ob Abs. 1 oder Abs. 2 maßgeblich ist.",
        "Zweck: konkreter Verarbeitungszweck (keine pauschalen Sammelzwecke).",
        "Rechtsgrundlage: Buchstabe(n) nach Art. 6 Abs. 1; bei besonderen Kategorien zusätzlich 'Art. 9'-Grundlage (Art. 9 Abs. 2 Buchst.).",
        "Kategorien betroffener Personen und Kategorien personenbezogener Daten.",
        "Empfänger: an wen Daten offengelegt werden (intern/extern, Auftragsverarbeiter).",
        "Drittland: 'nein' oder Zielland inkl. Bezug auf Übermittlungsgarantie.",
        "Löschfrist + Verweis aufs Löschkonzept (loeschfrist_ref).",
        "TOM-Verweis (Art. 32, tom_ref) und Verantwortlicher.",
        "DSFA-Trigger: setzen, wenn ein Auslöser nach Art. 35 vorliegt (verlinkt in die DSFA)."
      ],
      "anleitung": "1) Pro Verarbeitungstätigkeit einen Eintrag anlegen. 2) Rolle festlegen. 3) Zweck und Rechtsgrundlage(n) exakt benennen. 4) Personen-/Datenkategorien, Empfänger und ggf. Drittland erfassen. 5) Löschfrist und TOM verlinken statt frei zu beschreiben. 6) DSFA-Trigger prüfen und ggf. setzen – dann im DSFA-Tar­geting weiterbearbeiten.",
      "tipps": [
        "Eine Tätigkeit = ein Zweck. Mischzwecke trennen.",
        "Art. 9-Daten erfordern immer eine zusätzliche Grundlage – ohne diese ist der Eintrag unvollständig.",
        "Löschfrist/TOM nicht doppelt pflegen, sondern auf Löschkonzept und TOM-Katalog referenzieren."
      ]
    },
    {
      "id": "dashboard",
      "title": "📊 Dashboard",
      "zweck": "Read-only-Gesamtüberblick (vormals „DSMS-Cockpit\") über den Reifegrad aller DSMS-Bereiche, offene Punkte/Fristen, Dokumente-Soll-Ist und offene Risiken – Steuerungs- und Nachweisinstrument für die Rechenschaftspflicht.",
      "rechtsgrundlage": "Art. 5 Abs. 2 DSGVO (Rechenschaftspflicht)",
      "pflichtfelder": [
        "Keine direkte Eingabe – das Cockpit aggregiert aus VVT, TOM-Katalog, DSFA, Betroffenenrechten, Löschkonzept, Einwilligung und DSB."
      ],
      "anleitung": "1) Reifegrade je Bereich ablesen. 2) Bereiche mit niedrigem Reifegrad bzw. offenen Fristen priorisieren. 3) Über den jeweiligen Bereichs-Tab nachpflegen – das Cockpit aktualisiert sich daraus.",
      "tipps": ["Lücken hier zeigen, welcher Fach-Tab als Nächstes zu befüllen ist."]
    },
    {
      "id": "cockpit",
      "title": "📊 Risiko-Cockpit",
      "zweck": "Firmenweite, modulübergreifende Sicht auf alle offenen Datenschutz-/Sicherheitsrisiken (aus Risikobewertung und CRA) der zugeordneten Firma.",
      "rechtsgrundlage": "Art. 24/32 DSGVO (risikobasierter Ansatz)",
      "pflichtfelder": [
        "Keine Eingabe – read-only Aggregation pro Firma (firmen_id)."
      ],
      "anleitung": "1) Firmen-Zuordnung des Projekts sicherstellen (sonst keine Aggregation). 2) Offene Risiken sichten. 3) Behandlung in der verknüpften Risikobewertung vornehmen – das Cockpit spiegelt deren Stand.",
      "tipps": ["Risiken werden in der Risikobewertung gepflegt, nicht hier."]
    },
    {
      "id": "anforderungen",
      "title": "✅ Anforderungen",
      "zweck": "Strukturierte Selbsteinschätzung der DSGVO-Anforderungen je Kapitel mit Reifegrad-Berechnung.",
      "rechtsgrundlage": "DSGVO gesamt (Art. 5, 6, 12–22, 24, 25, 28, 30, 32, 35)",
      "pflichtfelder": [
        "Je Anforderung: Erfüllungsstatus/Reifegrad und Begründung/Nachweis.",
        "Verantwortlicher und ggf. Maßnahme/Frist bei Lücken."
      ],
      "anleitung": "1) Kapitelweise durchgehen. 2) Status je Anforderung realistisch setzen. 3) Nachweis bzw. Verweis (VVT/TOM/Löschkonzept) ergänzen. 4) Lücken in Maßnahmen/Issues überführen.",
      "tipps": ["Status nur 'erfüllt', wenn ein konkreter Nachweis existiert – das fließt in den Reifegrad."]
    },
    {
      "id": "assistenten",
      "title": "🤖 Assistenten",
      "zweck": "KI-gestützte Wizards (Copy/Paste-Prompts), die Entwürfe für VVT, Rechtsgrundlage, Branchen-Spezifika, Datenpannen-Bewertung, Betroffenenrechte, Schulung und Datenschutzerklärung liefern.",
      "rechtsgrundlage": "— (Hilfsmittel; rechtliche Bewertung bleibt beim Verantwortlichen)",
      "pflichtfelder": [
        "Keine Pflichtfelder – Eingaben sind kontextabhängig je Assistent."
      ],
      "anleitung": "1) Passenden Assistenten wählen. 2) Prompt mit Projektkontext erzeugen, in das KI-Tool kopieren. 3) Antwort zurückspielen/prüfen. 4) Ergebnis in den jeweiligen Fach-Tab übernehmen – Assistenten ersetzen die fachliche Prüfung nicht.",
      "tipps": ["KI-Vorschläge immer fachlich/rechtlich gegenprüfen, bevor sie als Nachweis gelten."]
    },
    {
      "id": "dokumente",
      "title": "📄 Dokumente",
      "zweck": "Ablage und Verwaltung hochgeladener Nachweise/Belege (z. B. AV-Verträge, Richtlinien, Screenshots) zum Projekt.",
      "rechtsgrundlage": "Art. 5 Abs. 2 DSGVO (Nachweisführung)",
      "pflichtfelder": [
        "Datei + aussagekräftiger Titel; sinnvoll: Bezug zur Verarbeitung/Anforderung."
      ],
      "anleitung": "1) Nachweis hochladen. 2) Eindeutig benennen und zuordnen. 3) Bei Aktualisierung neue Version ablegen statt überschreiben.",
      "tipps": ["Dateien werden zur Nachweisführung referenziert – sprechende Namen erleichtern das Audit."]
    },
    {
      "id": "tom-katalog",
      "title": "🔐 TOM-Katalog (Art. 32 + SDM)",
      "zweck": "Strukturierte Dokumentation technischer und organisatorischer Maßnahmen entlang der 7 SDM-Gewährleistungsziele inkl. Wirksamkeitsprüfung.",
      "rechtsgrundlage": "Art. 32 DSGVO; Standard-Datenschutzmodell (SDM)",
      "pflichtfelder": [
        "Ziel: eines der 7 SDM-Ziele (Datenminimierung, Verfügbarkeit, Integrität, Vertraulichkeit, Nichtverkettung, Transparenz, Intervenierbarkeit).",
        "Maßnahme (Key/Titel) und Beschreibung.",
        "Status (Ist-Reifegrad 0–5) und Soll (Ziel-Reifegrad, Default 5).",
        "Verantwortlicher.",
        "Wirksamkeitsprüfung: Datum + Ergebnis (Art. 32 Abs. 1 Buchst. d – regelmäßige Überprüfung).",
        "VVT-Verweis (welche Verarbeitungen die Maßnahme schützt)."
      ],
      "anleitung": "1) Je SDM-Ziel die umgesetzten Maßnahmen erfassen. 2) Ist-Status und Soll setzen. 3) Verantwortlichen benennen. 4) Wirksamkeit datieren und Ergebnis dokumentieren. 5) Maßnahme mit den relevanten VVT-Einträgen verknüpfen.",
      "tipps": [
        "Ohne dokumentierte Wirksamkeitsprüfung ist Art. 32 Abs. 1 d nicht erfüllt.",
        "Status < Soll erzeugt eine sichtbare Lücke – das gehört in die Maßnahmenplanung."
      ]
    },
    {
      "id": "betroffenenrechte",
      "title": "📨 Betroffenenrechte",
      "zweck": "Fall-/Fristenmanagement für Betroffenenanträge (Auskunft, Berichtigung, Löschung usw.) mit Identitätsprüfung und Art.-19-Empfängermitteilung.",
      "rechtsgrundlage": "Art. 15–22 DSGVO; Fristen/Modalitäten Art. 12; Mitteilungspflicht Art. 19",
      "pflichtfelder": [
        "Antrag-ID und Typ (Auskunft Art. 15, Berichtigung 16, Löschung 17, Einschränkung 18, Übertragbarkeit 20, Widerspruch 21, Art. 22).",
        "Eingangsdatum und Fristdatum (grds. 1 Monat ab Eingang, Art. 12 Abs. 3).",
        "Verlängerung (max. +2 Monate bei Komplexität, mit Begründung) – Flag setzen.",
        "Identität geprüft (Pflicht vor Auskunftserteilung).",
        "Status, Bearbeiter, Ergebnis/Notizen.",
        "Empfänger-Mitteilung (Art. 19): Status, Empfängerliste, Datum – bei Berichtigung/Löschung/Einschränkung."
      ],
      "anleitung": "1) Antrag mit Typ und Eingangsdatum anlegen; Frist wird daraus berechnet. 2) Identität prüfen und Flag setzen. 3) Bearbeiten, Ergebnis dokumentieren. 4) Bei Berichtigung/Löschung/Einschränkung die betroffenen Empfänger nach Art. 19 informieren und dokumentieren. 5) Vor Fristablauf abschließen oder begründet verlängern.",
      "tipps": [
        "Fristbeginn ist der Eingang, nicht der Bearbeitungsbeginn.",
        "Auskunft ohne Identitätsprüfung kann selbst eine Datenpanne auslösen."
      ]
    },
    {
      "id": "loeschkonzept",
      "title": "🗑️ Löschkonzept",
      "zweck": "Regelbasiertes Löschkonzept je Datenkategorie mit Aufbewahrungsfristen und Löschklassen nach DIN 66398.",
      "rechtsgrundlage": "Art. 17 DSGVO (Löschung) / Art. 5 Abs. 1 e (Speicherbegrenzung); DIN 66398",
      "pflichtfelder": [
        "Regel-ID und Datenkategorie.",
        "Aufbewahrungsfrist und Rechtsgrundlage der Frist ('gesetzlich' / vertraglich / berechtigtes Interesse).",
        "Löschklasse (DIN 66398) und Lösch-Trigger (Ereignis, das die Frist startet).",
        "Verantwortlicher und Status.",
        "VVT-Verweis (welche Verarbeitung die Regel betrifft)."
      ],
      "anleitung": "1) Je Datenkategorie eine Löschregel anlegen. 2) Frist + deren Rechtsgrundlage benennen. 3) Löschklasse und auslösendes Ereignis (Trigger) festlegen. 4) Verantwortlichen zuordnen und mit VVT verknüpfen.",
      "tipps": [
        "Frist ohne benannten Trigger ist nicht operationalisierbar.",
        "Gesetzliche Aufbewahrung (z. B. HGB/AO) und DSGVO-Löschung gegeneinander abwägen."
      ]
    },
    {
      "id": "transfer",
      "title": "🌍 Drittlandtransfer + TIA",
      "zweck": "Register aller Drittlandübermittlungen mit Übermittlungsgrundlage und Transfer-Impact-Assessment (TIA).",
      "rechtsgrundlage": "Art. 44–49 DSGVO (Kapitel V)",
      "pflichtfelder": [
        "Transfer-ID, Empfänger und Drittland.",
        "Grundlage: Angemessenheitsbeschluss (Art. 45), geeignete Garantien wie SCC/BCR (Art. 46) oder Ausnahme (Art. 49).",
        "Garantie-Detail (z. B. konkrete SCC-Module, Zusatzmaßnahmen).",
        "TIA-Status und TIA-Inhalt (Bewertung des Drittland-Rechtsniveaus, Schrems-II).",
        "VVT- und ggf. AVV-Verweis."
      ],
      "anleitung": "1) Je Übermittlung einen Eintrag anlegen. 2) Korrekte Grundlage nach Stufenfolge wählen (45 vor 46 vor 49). 3) Bei SCC/BCR ein TIA durchführen und dokumentieren, inkl. Zusatzmaßnahmen. 4) Mit VVT und AVV verknüpfen.",
      "tipps": [
        "Art. 49-Ausnahmen sind eng auszulegen und nicht für regelmäßige Massen­transfers gedacht.",
        "Ohne TIA sind SCC nach Schrems II i. d. R. nicht ausreichend."
      ]
    },
    {
      "id": "einwilligung",
      "title": "✍️ Einwilligungen",
      "zweck": "Nachweis erteilter Einwilligungen inkl. Text-Version, Zeitpunkt, Kanal und Widerruf.",
      "rechtsgrundlage": "Art. 7 DSGVO (Bedingungen für die Einwilligung); Art. 6 Abs. 1 a / Art. 9 Abs. 2 a",
      "pflichtfelder": [
        "Einwilligungs-ID und Zweck (eng gefasst, je Zweck eine Einwilligung).",
        "Einwilligungstext + Text-Version (Versionierung für Nachweis).",
        "Zeitpunkt der Erteilung, Kanal (z. B. Web-Formular, schriftlich) und Quelle des Betroffenen.",
        "Status (aktiv/widerrufen) und ggf. Widerrufszeitpunkt."
      ],
      "anleitung": "1) Je Zweck eine Einwilligung mit konkretem Text und Version anlegen. 2) Erteilungszeitpunkt und Kanal erfassen (Nachweis der Freiwilligkeit/Information). 3) Bei Widerruf Zeitpunkt eintragen und Status setzen – Widerruf muss so einfach wie die Erteilung sein.",
      "tipps": [
        "Gekoppelte/voreingestellte Einwilligungen sind unwirksam (Art. 7 Abs. 4 / Opt-in).",
        "Den genauen Einwilligungstext archivieren – pauschale Verweise genügen nicht."
      ]
    },
    {
      "id": "dsgvo-dsb",
      "title": "🛡️ DSB (Datenschutzbeauftragter)",
      "zweck": "Stammdaten und Pflichtnachweise zum Datenschutzbeauftragten inkl. Veröffentlichung und Meldung an die Aufsicht.",
      "rechtsgrundlage": "Art. 37–39 DSGVO",
      "pflichtfelder": [
        "Typ (intern/extern) und Name.",
        "Bestelldatum.",
        "Kontakt-E-Mail; Flag 'Kontakt veröffentlicht' (Art. 37 Abs. 7).",
        "Flag 'der Aufsichtsbehörde gemeldet' (Art. 37 Abs. 7).",
        "Aufgaben-/Tätigkeitsnachweis (Art. 39) und Notizen."
      ],
      "anleitung": "1) DSB anlegen (intern/extern) mit Bestelldatum. 2) Kontaktdaten erfassen und veröffentlichen (Website/Datenschutzhinweis) – Flag setzen. 3) Der Aufsichtsbehörde melden – Flag setzen. 4) Aufgabenerfüllung/Tätigkeitsbericht dokumentieren.",
      "tipps": [
        "Veröffentlichung UND Meldung an die Aufsicht sind getrennte Pflichten – beide erfüllen.",
        "Prüfen, ob überhaupt eine Benennungspflicht besteht (Art. 37 Abs. 1, ggf. § 38 BDSG)."
      ]
    },
    {
      "id": "datenpannen",
      "title": "🚨 Datenpannen",
      "zweck": "Vorfallregister für Datenschutzverletzungen mit 72-Stunden-Meldefrist und Betroffenenbenachrichtigung.",
      "rechtsgrundlage": "Art. 33 DSGVO (Meldung an Aufsicht, 72 h); Art. 34 (Benachrichtigung Betroffener)",
      "pflichtfelder": [
        "Pannen-ID, Titel, Beschreibung.",
        "Art der Verletzung (Vertraulichkeit/Integrität/Verfügbarkeit).",
        "Festgestellt am (startet die 72-Stunden-Frist) und Zahl der Betroffenen.",
        "Betroffene Datenkategorien und Risikoeinschätzung (gering/mittel/hoch).",
        "Meldepflicht an Aufsicht (Art. 33) + Meldedatum.",
        "Benachrichtigungspflicht Betroffene (Art. 34, bei hohem Risiko) + Datum.",
        "Sofortmaßnahmen, Ursache, Lessons Learned, Status (offen/gemeldet/abgeschlossen)."
      ],
      "anleitung": "1) Vorfall sofort bei Kenntnis anlegen (Datum 'festgestellt am' korrekt). 2) Art und Risiko bewerten. 3) Ist Meldepflicht gegeben: binnen 72 h an die Aufsicht melden und Datum erfassen. 4) Bei hohem Risiko Betroffene unverzüglich benachrichtigen. 5) Sofortmaßnahmen, Ursache und Lessons Learned dokumentieren, dann abschließen.",
      "tipps": [
        "Die 72-Stunden-Frist beginnt mit Kenntnis, nicht mit Abschluss der Analyse.",
        "Auch ein 'meldefreier' Vorfall ist intern zu dokumentieren (Art. 33 Abs. 5)."
      ]
    },
    {
      "id": "lia",
      "title": "⚖️ LIA-Register (Berechtigtes Interesse)",
      "zweck": "Geführtes Legitimate-Interest-Assessment (3-Stufen-Test) als Nachweis für Verarbeitungen auf Grundlage des berechtigten Interesses.",
      "rechtsgrundlage": "Art. 6 Abs. 1 f DSGVO (Abwägung)",
      "pflichtfelder": [
        "LIA-ID, betroffene Verarbeitung und VVT-Verweis.",
        "Stufe 1 (Zweck/Legitimität): Zweck, berechtigtes Interesse, Flag 'legitim'.",
        "Stufe 2 (Erforderlichkeit): Erforderlichkeit, Prüfung milderer Mittel + Ergebnis.",
        "Stufe 3 (Abwägung): Interessen der Betroffenen, vernünftige Erwartung, Garantien/Opt-out.",
        "Ergebnis + Begründung, Reviewer, Review-Datum, Review-Zyklus (Monate) und nächstes Review."
      ],
      "anleitung": "1) Verarbeitung benennen und mit VVT verknüpfen. 2) Stufe 1: berechtigtes Interesse darlegen und Legitimität bestätigen. 3) Stufe 2: Erforderlichkeit prüfen, mildere Mittel ausschließen. 4) Stufe 3: Interessen der Betroffenen abwägen, Schutzgarantien/Opt-out angeben. 5) Ergebnis begründen, Reviewer/Datum und Wiedervorlage setzen.",
      "tipps": [
        "Überwiegt das berechtigte Interesse nicht eindeutig, ist Art. 6(1)f keine taugliche Grundlage.",
        "Ein einfaches Opt-out stärkt die Abwägung erheblich."
      ]
    },
    {
      "id": "subprozessoren",
      "title": "🔗 Subprozessoren",
      "zweck": "Register der Unterauftragsverarbeiter je AV-Vertrag mit Genehmigungs- und Drittland-Status.",
      "rechtsgrundlage": "Art. 28 Abs. 2 und Abs. 4 DSGVO",
      "pflichtfelder": [
        "Zuordnung zum AV-Vertrag (avv_pk), Name des Subprozessors und Leistung.",
        "Drittland-Flag + Garantie (SCC/Adäquanz/BCR), falls Drittland.",
        "Genehmigungsstatus (ausstehend/erteilt) + Datum (Art. 28 Abs. 2 – vorherige Genehmigung).",
        "Sub-AVV vorhanden + URL/Datum.",
        "Back-to-Back-Pflichten weitergegeben (Art. 28 Abs. 4 – identische Pflichten)."
      ],
      "anleitung": "1) Subprozessor dem jeweiligen AV-Vertrag zuordnen. 2) Leistung beschreiben. 3) Bei Drittland Garantie angeben. 4) Genehmigung (allgemein/spezifisch) dokumentieren. 5) Bestehen des Sub-AVV und Weitergabe identischer Pflichten bestätigen.",
      "tipps": [
        "Ohne weitergegebene Back-to-Back-Pflichten haftet der Hauptauftragnehmer voll (Art. 28 Abs. 4).",
        "Bei genereller Genehmigung Widerspruchsmöglichkeit bei Subprozessor-Wechsel sicherstellen."
      ]
    },
    {
      "id": "zweckaenderung",
      "title": "🔄 Zweckänderung",
      "zweck": "Kompatibilitätsprüfung bei Weiterverarbeitung zu einem anderen Zweck anhand der 5 Kriterien des Art. 6 Abs. 4.",
      "rechtsgrundlage": "Art. 6 Abs. 4 DSGVO",
      "pflichtfelder": [
        "ZA-ID, VVT-Verweis, ursprünglicher und neuer Zweck.",
        "Kriterium a: Zusammenhang ursprünglicher/neuer Zweck.",
        "Kriterium b: Kontext der Erhebung / Beziehung zu Betroffenen.",
        "Kriterium c: Art der Daten (insb. besondere Kategorien).",
        "Kriterium d: mögliche Folgen für die Betroffenen.",
        "Kriterium e: geeignete Garantien (z. B. Verschlüsselung/Pseudonymisierung).",
        "Ergebnis + Begründung und ggf. neue Rechtsgrundlage."
      ],
      "anleitung": "1) Ursprünglichen und neuen Zweck gegenüberstellen. 2) Die 5 Kriterien (a–e) einzeln bewerten. 3) Vereinbarkeit feststellen und begründen. 4) Ist der neue Zweck nicht vereinbar, separate Rechtsgrundlage (z. B. neue Einwilligung) dokumentieren.",
      "tipps": ["Bei besonderen Kategorien (Krit. c) ist die Hürde für Vereinbarkeit deutlich höher."]
    },
    {
      "id": "joint-controller",
      "title": "🤝 Joint Controller",
      "zweck": "Register gemeinsamer Verantwortlichkeiten mit Pflichtenverteilung und Betroffenen-Zusammenfassung.",
      "rechtsgrundlage": "Art. 26 DSGVO",
      "pflichtfelder": [
        "JC-ID, Partner + Kontakt, VVT-Verweis, Verarbeitung und gemeinsame Festlegung von Zweck/Mitteln.",
        "Pflichtenverteilung (Art. 26 Abs. 1): Anlaufstelle für Betroffene, Zuständigkeit Information (Art. 13/14), TOM (Art. 32), Meldung (Art. 33/34).",
        "Vereinbarung vorhanden + URL/Datum.",
        "Zusammenfassung des Wesentlichen für Betroffene (Art. 26 Abs. 2): Status/Text/URL.",
        "Reviewer, Review-Datum, Review-Zyklus und nächstes Review."
      ],
      "anleitung": "1) Partner und gemeinsame Verarbeitung erfassen. 2) Pflichten je Bereich eindeutig zuordnen und Anlaufstelle bestimmen. 3) Joint-Controller-Vereinbarung hinterlegen. 4) Das Wesentliche der Vereinbarung für Betroffene zugänglich machen.",
      "tipps": ["Betroffene können ihre Rechte gegenüber jedem Verantwortlichen geltend machen – die interne Verteilung ändert das nicht."]
    },
    {
      "id": "eu-vertreter",
      "title": "🇪🇺 EU-Vertreter",
      "zweck": "Anwendbarkeitsprüfung (Art. 3 Abs. 2) und Benennungsregister für den EU-Vertreter nicht in der Union niedergelassener Verantwortlicher.",
      "rechtsgrundlage": "Art. 27 DSGVO (i. V. m. Art. 3 Abs. 2)",
      "pflichtfelder": [
        "Anwendbarkeitsprüfung: Niederlassung außerhalb der EU, Angebot an EU-Betroffene, Verhaltensbeobachtung, Ausnahme nach Art. 27 Abs. 2 + Prüfnotiz.",
        "Bei Benennungspflicht: Vertreter-Name, Anschrift (in einem Mitgliedstaat der Betroffenen), Kontakt.",
        "Mandat vorhanden + Datum.",
        "Im Datenschutzhinweis genannt (Flag)."
      ],
      "anleitung": "1) Anwendbarkeit prüfen (Art. 3 Abs. 2) und Ausnahmen bewerten. 2) Bei Pflicht einen Vertreter mit Sitz in der EU benennen. 3) Schriftliches Mandat hinterlegen. 4) Vertreter im Datenschutzhinweis ausweisen.",
      "tipps": ["Greift eine Ausnahme nach Abs. 2, Prüfnotiz mit Begründung dokumentieren statt das Register leer zu lassen."]
    },
    {
      "id": "tom",
      "title": "🔒 TOM-Generator",
      "zweck": "Generiert ein TOM-Dokument als Nachweis/Anlage (z. B. zum AV-Vertrag) aus den erfassten Maßnahmen.",
      "rechtsgrundlage": "Art. 32 DSGVO (i. V. m. Art. 28 Abs. 3)",
      "pflichtfelder": [
        "Dokument-Metadaten (Organisation/Stand) und die zugrunde liegenden TOM-Inhalte.",
        "Empfehlung: Pflege primär im TOM-Katalog, hier nur Dokument-Export/Zusammenstellung."
      ],
      "anleitung": "1) TOM-Inhalte im TOM-Katalog pflegen. 2) Im Generator die Metadaten setzen und das Dokument erzeugen. 3) Als Anlage/Nachweis ablegen.",
      "tipps": ["Doppelpflege vermeiden – der TOM-Katalog (Art. 32 + SDM) ist die Quelle, der Generator das Ausgabeformat."]
    },
    {
      "id": "privacy",
      "title": "📜 Datenschutzerklärung",
      "zweck": "Erzeugt eine Datenschutzerklärung/Informationsdokument auf Basis erfasster Intake-Angaben.",
      "rechtsgrundlage": "Art. 13/14 DSGVO (Informationspflichten); Art. 12 (Transparenz)",
      "pflichtfelder": [
        "Verantwortlicher (Name/Anschrift/Kontakt) und ggf. DSB-Kontakt.",
        "Zwecke und Rechtsgrundlagen der Verarbeitung; bei Art. 6(1)f das berechtigte Interesse.",
        "Empfänger/Kategorien, Drittlandübermittlungen + Garantien.",
        "Speicherdauer/Löschfristen.",
        "Betroffenenrechte und Beschwerderecht bei der Aufsicht; ggf. Pflicht zur Bereitstellung und automatisierte Entscheidungen."
      ],
      "anleitung": "1) Intake-Felder vollständig ausfüllen (das Modul markiert fehlende Pflichtangaben). 2) Zwecke/Rechtsgrundlagen aus dem VVT übernehmen. 3) Dokument erzeugen und juristisch gegenlesen. 4) Veröffentlichen und versionieren.",
      "tipps": ["Inhalte mit dem VVT konsistent halten – Abweichungen zwischen VVT und Datenschutzerklärung sind ein typischer Prüfbefund."]
    },
    {
      "id": "training",
      "title": "🎓 Schulung",
      "zweck": "Erstellt Schulungs-/Sensibilisierungsunterlagen und dokumentiert die Awareness-Maßnahmen.",
      "rechtsgrundlage": "Art. 39 Abs. 1 b DSGVO (Sensibilisierung/Schulung); Art. 32 (Zuverlässigkeit)",
      "pflichtfelder": [
        "Zielgruppe(n) der Schulung (steuert Umfang/Dauer).",
        "Inhalte/Themenschwerpunkte und Stand/Version.",
        "Empfehlung: Durchführung als Jahreskontrolle nachweisen (Tab Kontrollen)."
      ],
      "anleitung": "1) Zielgruppe(n) wählen. 2) Inhalte zusammenstellen und Dokument erzeugen. 3) Schulung durchführen und Teilnahme/Datum als Nachweis (Kontrollen/Dokumente) ablegen.",
      "tipps": ["Schulungsnachweise (wer/wann) sind für die Rechenschaftspflicht wichtiger als die Foliensätze selbst."]
    },
    {
      "id": "kontrollen",
      "title": "🗓️ Kontrollen",
      "zweck": "Jährlicher Datenschutz-Kontrollplan mit Freigabe-Workflow (GF/DSB) und revisionssicheren Anhängen.",
      "rechtsgrundlage": "Art. 5 Abs. 2 / Art. 24 DSGVO (Rechenschaft, Überprüfung der Wirksamkeit)",
      "pflichtfelder": [
        "Kontroll-ID, Titel, Bereich und Jahr.",
        "Frequenz (z. B. jährlich) und Verantwortlicher.",
        "Status (geplant → freigegeben → in_durchfuehrung → abgeschlossen).",
        "Geplant am; bei Durchführung: durchgeführt am/von + Ergebnis.",
        "Freigabe (von/am) durch GF/DSB – danach sind Stammdaten gesperrt.",
        "Bezug (bezug_ref) und ggf. Anhänge (Nachweise mit SHA-256)."
      ],
      "anleitung": "1) Standard-Jahreskontrollen seeden oder eigene anlegen. 2) Plan freigeben lassen (GF/DSB) – danach keine Stammdatenänderung mehr. 3) Kontrolle durchführen, Ergebnis und Datum erfassen, Nachweise anhängen. 4) Abschließen; offene Kontrollen erscheinen im Cockpit.",
      "tipps": [
        "Nach Freigabe sind Stammdaten gesperrt – Inhalte vorher final prüfen.",
        "Anhänge sind SHA-256-gesichert und nur soft-löschbar (Revisionssicherheit)."
      ]
    },
    {
      "id": "jahresbericht",
      "title": "📅 Jahresbericht",
      "zweck": "Aggregierter Datenschutz-Jahresbericht mit Freigabe-/Signatur-Workflow als zentraler Rechenschaftsnachweis.",
      "rechtsgrundlage": "Art. 5 Abs. 2 DSGVO (Rechenschaftspflicht)",
      "pflichtfelder": [
        "Jahr; der Bericht aggregiert Kontrollen, DSFAs, Datenpannen, Betroffenenrechte, Einwilligungs-Widerrufe, TOM-Reifegrad und firmenweite Risiken.",
        "Status-Workflow: entwurf → freigegeben (GF, Permission DSGVO_APPROVE) → signiert (DSB, Permission DSGVO_SIGN).",
        "Bei Signatur: finalisierte PDF (SHA-256, danach unveränderlich)."
      ],
      "anleitung": "1) Berichtsjahr wählen – Inhalte werden automatisch aus den Bereichen aggregiert. 2) Entwurf prüfen. 3) GF gibt frei (DSGVO_APPROVE). 4) DSB signiert (DSGVO_SIGN); danach ist der Bericht inkl. PDF unveränderlich.",
      "tipps": [
        "Vor der Freigabe alle Fach-Tabs aktualisieren – nach Signatur ist keine Änderung mehr möglich.",
        "Freigabe und Signatur sind getrennte Rollen/Permissions (GF vs. DSB)."
      ]
    },
    {
      "id": "berichte",
      "title": "📄 Berichte (Berichts-Center)",
      "zweck": "Erzeugt Einzelberichte je DSMS-Bereich (VVT, TOM, Löschkonzept, Betroffenenrechte, Transfer, Einwilligung, DSFA, DSB) als DOCX/PDF.",
      "rechtsgrundlage": "Art. 5 Abs. 2 DSGVO (Nachweis/Berichtswesen)",
      "pflichtfelder": [
        "Auswahl des Bereichs und Berichtsformat (DOCX/PDF).",
        "Voraussetzung: der jeweilige Bereich ist im zugehörigen Tab gepflegt."
      ],
      "anleitung": "1) Bereich wählen. 2) Format (DOCX/PDF) wählen. 3) Bericht erzeugen und ablegen/weitergeben.",
      "tipps": ["Die Berichtsqualität hängt direkt von der Datenpflege im jeweiligen Fach-Tab ab."]
    }
  ],
  "links": [
    {
      "label": "DSGVO-Modul-Doku (Online)",
      "href": docsUrl('/modules/dsgvo/')
    },
    {
      "label": "DSGVO Volltext (EUR-Lex, Verordnung (EU) 2016/679)",
      "href": "https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32016R0679"
    },
    {
      "label": "BfDI – Datenschutz-Grundverordnung",
      "href": "https://www.bfdi.bund.de/DE/Buerger/Inhalte/Allgemein/Datenschutzrecht/DSGVO.html"
    }
  ],
  "module": "dsgvo"
}
