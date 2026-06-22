// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

export const nis2Help: ModuleHelp = {
  "title": "NIS2",
  "regulation": "Richtlinie (EU) 2022/2555 (NIS2-Richtlinie) — in Deutschland umgesetzt durch das NIS2-Umsetzungsgesetz (NIS2UmsuCG, Änderungen u.a. im BSIG)",
  "purpose": "Das Modul unterstützt die strukturierte Umsetzung und Nachweisführung der NIS2-Cybersicherheitsanforderungen. Es bildet den Maßnahmenkatalog nach Art. 21, die Governance-Pflichten nach Art. 20 und die Meldepflichten nach Art. 23 ab und erfasst die Einstufung als wesentliche oder wichtige Einrichtung. Ergebnis ist ein bewerteter Anforderungskatalog mit Reifegrad und exportierbarem Bericht.",
  "legalBasis": {
    "title": "Rechtsgrundlage: NIS2-Richtlinie (EU) 2022/2555",
    "intro": "Die NIS2-Richtlinie verpflichtet wesentliche und wichtige Einrichtungen der in Anhang I und II genannten Sektoren zu einem risikobasierten Cybersicherheits-Management. Sie verlangt verbindliche technische und organisatorische Mindestmaßnahmen, eine aktive Verantwortung der Leitungsorgane sowie ein abgestuftes Meldeverfahren bei erheblichen Sicherheitsvorfällen. Verstöße sind bußgeldbewehrt; die Geschäftsleitung haftet persönlich.",
    "bullets": [
      "Art. 21 Abs. 1 NIS2-RL: Geeignete und verhältnismäßige technische, operative und organisatorische Risikomanagementmaßnahmen nach dem Stand der Technik (All-Hazards-Ansatz).",
      "Art. 21 Abs. 2 NIS2-RL: Mindestkatalog von 10 Maßnahmenbereichen — u.a. Risikoanalyse und Sicherheit der Informationssysteme (lit. a), Bewältigung von Sicherheitsvorfällen (lit. b), Business Continuity/Backup/Krisenmanagement (lit. c), Sicherheit der Lieferkette (lit. d), Sicherheit bei Erwerb, Entwicklung und Wartung (lit. e), Bewertung der Wirksamkeit (lit. f), Cyberhygiene und Schulungen (lit. g), Kryptografie/Verschlüsselung (lit. h), Personalsicherheit, Zugriffskontrolle und Asset Management (lit. i), MFA und gesicherte Kommunikation (lit. j).",
      "Art. 20 NIS2-RL: Leitungsorgane müssen die Risikomanagementmaßnahmen billigen, deren Umsetzung überwachen und an Schulungen teilnehmen; Verantwortung und Haftung liegen beim Management.",
      "Art. 23 NIS2-RL: Meldepflicht bei erheblichen Sicherheitsvorfällen — Frühwarnung innerhalb von 24 Stunden, Vorfallmeldung innerhalb von 72 Stunden, Abschlussbericht spätestens 1 Monat nach der Meldung (Zwischenbericht auf Anforderung).",
      "Anhang I (wesentliche Einrichtungen, z.B. Energie, Verkehr, Bankwesen, Gesundheit, Wasser, digitale Infrastruktur) und Anhang II (wichtige Einrichtungen, z.B. Post, Abfall, Chemie, Lebensmittel, verarbeitendes Gewerbe, digitale Dienste) bestimmen Einstufung und Aufsichtsregime.",
      "Art. 24-25 NIS2-RL: Möglichkeit, europäische Cybersicherheitszertifizierungsschemata und Normen zum Nachweis der Konformität heranzuziehen."
    ]
  },
  "implementation": {
    "title": "Vorgehen im Modul",
    "intro": "Im Modul wird zunächst die Einrichtungsklasse (wesentlich/wichtig) bestimmt; danach wird der Anforderungskatalog entlang der Kapitel Governance (Art. 20), Risikomanagement/technische Maßnahmen (Art. 21), Meldepflichten (Art. 23) und Lieferkettensicherheit bewertet. Jede Anforderung erhält einen Reifegrad auf der Skala 0-5 mit Nachweisbezug; der Gesamtstand wird verdichtet und als Bericht exportiert.",
    "bullets": [
      "Einrichtungsklasse zuerst festlegen — sie bestimmt Aufsichts- und Nachweistiefe und damit die Priorisierung der Maßnahmen.",
      "Jede der 10 Maßnahmen aus Art. 21 Abs. 2 einzeln bewerten und je Anforderung konkrete Nachweise hinterlegen (Richtlinien, Protokolle, Schulungsnachweise, Backup-/BCM-Konzepte).",
      "Reifegrad konsistent vergeben: 0 nicht bewertet, 1 nicht erfüllt, 2 in Planung, 3 teilweise, 4 weitgehend, 5 vollständig erfüllt; Gewichtung beachten.",
      "Leitungsverantwortung dokumentieren (Genehmigung der Maßnahmen, Überwachung, Management-Schulungen) als Nachweis zu Art. 20.",
      "Meldeprozess vorab definieren und üben: Eskalationswege, Zuständigkeiten und die Fristen 24h/72h/1 Monat als Runbook festhalten.",
      "Lieferkettensicherheit gesondert betrachten (Anbieterbewertung, Vertragsklauseln) — Art. 21 Abs. 2 lit. d.",
      "Offene und nur teilweise erfüllte Anforderungen in Maßnahmen mit Verantwortlichen und Terminen überführen und über den Bericht nachverfolgen."
    ]
  },
  "moduleSpecific": {
    "title": "Besonderheiten des NIS2-Moduls",
    "intro": "Das Modul ist auf die spezifische Struktur der NIS2-Pflichten zugeschnitten und verbindet Maßnahmenkatalog, Meldefristen und Einrichtungs-Einstufung in einem Bewertungsworkflow.",
    "bullets": [
      "Maßnahmenkatalog nach Art. 21: Die 10 Mindestmaßnahmen sind als bewertbare Einzelanforderungen mit Artikel-Referenz und Nachweishinweisen hinterlegt.",
      "Einrichtungs-Einstufung: Auswahl zwischen wesentlicher Einrichtung (Anhang I), wichtiger Einrichtung (Anhang II) oder beidem; steuert den Bewertungskontext.",
      "Meldefristen-Logik nach Art. 23: 24h-Frühwarnung, 72h-Vorfallmeldung, 1-Monats-Abschlussbericht als feste Referenzwerte im Modul.",
      "Kapitelgliederung: Governance (Art. 20), Risikomanagement/technisch (Art. 21), Meldepflichten (Art. 23), Lieferkette (Art. 21 Abs. 2 lit. d) sowie Implementierung/Zertifizierung (Art. 24-25).",
      "Bewertungsskala 0-5 mit Gewichtung je Anforderung und Reifegrad-Verdichtung für den Gesamtüberblick.",
      "Berichtsexport zur Dokumentation des Umsetzungsstands gegenüber Leitung und Aufsichtsbehörde."
    ]
  },
  "areas": [
    {
      "id": "pflichtdoku",
      "title": "📋 Dokumentation (Pflicht-Doku)",
      "zweck": "Sammeln und Nachweisen der NIS2-Pflichtdokumentation entlang der 10 Maßnahmenbereiche (Asset-Inventar, Risikomanagement, CSIRT/Vorfallbehandlung, Lieferanten, BCP) inkl. token-aware Repo-Auto-Fill (N1–N5).",
      "rechtsgrundlage": "Art. 21 Abs. 2 NIS2-RL (Mindestmaßnahmen); Umsetzung im BSIG",
      "pflichtfelder": [
        "N1 Asset-Inventar (Systeme, Dienste, compose/Helm/k8s/Terraform, Topics).",
        "N3 CSIRT/Vorfallbehandlung (Kontakt + Prozess, z. B. aus SECURITY.md).",
        "N4 Lieferanten/Supply-Chain (aus SBOM/package.json/requirements).",
        "N5 Business-Continuity-/Backup-Hinweise.",
        "Je Nachweis: Beleg/Verweis statt Freitext."
      ],
      "anleitung": "1) Repo-Auto-Fill (N1–N5) laufen lassen – erkennt Assets, CSIRT, Lieferanten, BCP-Hinweise. 2) Vorschläge prüfen und bestätigen. 3) Fehlende Pflichtartefakte erstellen und verlinken. 4) Status je Bereich pflegen.",
      "tipps": [
        "Auto-Fill liefert Vorschläge – die fachliche Bestätigung bleibt erforderlich.",
        "N2 (Risiken) wird nicht hier, sondern in der verknüpften Risikobewertung gepflegt (read-only)."
      ]
    },
    {
      "id": "cockpit",
      "title": "📊 Risiko-Cockpit",
      "zweck": "Firmenweite, modulübergreifende Read-only-Sicht auf offene Risiken (Risikobewertung) und Schwachstellen der zugeordneten Firma.",
      "rechtsgrundlage": "Art. 21 Abs. 1 NIS2-RL (risikobasierter All-Hazards-Ansatz)",
      "pflichtfelder": [
        "Keine Eingabe – Aggregation pro Firma (firmen_id)."
      ],
      "anleitung": "1) Firmen-Zuordnung des Projekts sicherstellen. 2) Offene Risiken sichten. 3) Behandlung in der verknüpften Risikobewertung – das Cockpit spiegelt deren Stand.",
      "tipps": ["NIS2 N2 ist read-only: Risiken kommen aus der Risikobewertung, nicht aus dem NIS2-Modul."]
    },
    {
      "id": "incidents",
      "title": "🚨 Vorfälle (Art. 23)",
      "zweck": "Fristengesteuertes Meldemanagement erheblicher Sicherheitsvorfälle mit den drei Melde-Stufen 24h/72h/1 Monat (plus optionalem Zwischenbericht).",
      "rechtsgrundlage": "Art. 23 Abs. 4 NIS2-RL (Frühwarnung 24h lit. a · Vorfallmeldung 72h lit. b · Abschlussbericht 1 Monat lit. c)",
      "pflichtfelder": [
        "Incident-ID und Titel.",
        "Kenntnis-Zeitpunkt (startet die 24h/72h-Fristen).",
        "Erheblich (Flag) – nur erhebliche Vorfälle sind meldepflichtig.",
        "Schweregrad und betroffene Assets.",
        "Grenzüberschreitend (Flag) und Root Cause.",
        "Melde-Stufen je Vorfall: 24h (Frühwarnung), 72h (Vorfallmeldung), optional 'zwischen', 1M (Abschluss) – je mit Ist-Zeitpunkt/Text/BSI-Referenz."
      ],
      "anleitung": "1) Vorfall bei Kenntnis anlegen, Kenntnis-Zeitpunkt korrekt setzen. 2) Erheblichkeit bewerten. 3) Frühwarnung binnen 24h absetzen (Stufe 24h). 4) Vollständige Vorfallmeldung binnen 72h (Stufe 72h). 5) Auf Ersuchen Zwischenbericht. 6) Abschlussbericht binnen 1 Monat (Stufe 1M).",
      "tipps": [
        "Fristen laufen ab Kenntnis-Zeitpunkt; der Abschlussbericht 1 Monat ab der 72h-Meldung.",
        "Nicht-erhebliche Vorfälle intern dokumentieren, aber nicht melden."
      ]
    },
    {
      "id": "scoping",
      "title": "🎯 Scoping (Art. 2/3)",
      "zweck": "Deterministische Bestimmung der Betroffenheit und Einstufung (wesentlich/wichtig/out-of-scope) anhand Größenschwellen, Sektor und Jurisdiktion.",
      "rechtsgrundlage": "Art. 2/3 NIS2-RL (Anwendungsbereich, Größenschwellen); Art. 26 (Jurisdiktion); Anhang I/II",
      "pflichtfelder": [
        "Mitarbeiterzahl, Jahresumsatz (Mio. EUR), Bilanzsumme (Mio. EUR).",
        "Sektor + Subsektor und Anhang (I = wesentlich, II = wichtig, keiner).",
        "Konzernverbund (für die Schwellenwert-Konsolidierung).",
        "Hauptniederlassung, zuständige Behörde (Default BSI), EU-niedergelassen + ggf. EU-Vertreter.",
        "Ergebnis: size_class + Begründung (deterministisch berechnet)."
      ],
      "anleitung": "1) Unternehmenskennzahlen und Sektor/Subsektor erfassen. 2) Anhangzuordnung (I/II) wählen. 3) Konzernverbund/ Jurisdiktion angeben. 4) Klasse + Begründung ableiten lassen. 5) Bei Änderung neue Version dokumentieren.",
      "tipps": [
        "Die Größenschwellen sind im Konzernverbund zu konsolidieren.",
        "Out-of-scope ist mit Begründung zu dokumentieren, nicht leer zu lassen."
      ]
    },
    {
      "id": "registrierung",
      "title": "📝 Registrierung (Art. 27)",
      "zweck": "Erfassung der 6 Pflichtangaben für die Registrierung bei der zuständigen Behörde inkl. Übermittlungs- und Jahres-Bestätigungs-Tracking.",
      "rechtsgrundlage": "Art. 27 NIS2-RL (Registrierungspflicht, 6 Pflichtangaben Abs. 2)",
      "pflichtfelder": [
        "Name der Einrichtung.",
        "Sektor + Subsektor (Anhang I/II) und Einrichtungsart.",
        "Anschrift und EU-Niederlassungen.",
        "Kontakt (E-Mail, Telefon).",
        "Mitgliedstaaten der Diensterbringung und ggf. IP-Bereiche (für DNS/Cloud/digitale Infrastruktur).",
        "Status, Registrierungsdatum, Bestätigungs-Referenz, nächste Jahres-Bestätigung."
      ],
      "anleitung": "1) Die 6 Pflichtangaben (Name, Sektor/Subsektor+Einrichtungsart, Anschrift/EU-Niederlassungen, Kontakt, Mitgliedstaaten, ggf. IP-Bereiche) vollständig erfassen. 2) Registrierung übermitteln und Datum/Referenz dokumentieren. 3) Jahres-Bestätigung als Wiedervorlage setzen.",
      "tipps": [
        "Bestimmte digitale Dienste müssen IP-Bereiche/Domains mit angeben.",
        "Änderungen sind aktuell zu halten; die Jahres-Bestätigung erscheint im Fristen-Dashboard."
      ]
    },
    {
      "id": "audits",
      "title": "🔍 Audits (Art. 32)",
      "zweck": "Audit-/Konformitätsbewertungs-Register im 3-Jahres-Zyklus mit verknüpften Findings als CAPA-Register.",
      "rechtsgrundlage": "Art. 32 NIS2-RL (Aufsicht/Nachweis im 3-Jahres-Zyklus); CAPA zu Art. 21 Abs. 4",
      "pflichtfelder": [
        "Titel, Audit-Typ (intern/extern/Zertifizierung), Scope, Prüfer.",
        "Durchgeführt am → nächster Audit-Soll (36 Monate, automatisch).",
        "Bei Zertifizierung: Zertifikat-URL + Ablauf.",
        "Ergebnis (offen/bestanden/…).",
        "Findings/CAPA: Beschreibung, Schweregrad, Maßnahme, Verantwortlich, Frist, Status, ggf. Objektbezug."
      ],
      "anleitung": "1) Audit anlegen (Typ/Scope/Prüfer). 2) Durchführungsdatum setzen – die 3-Jahres-Wiedervorlage wird berechnet. 3) Findings als CAPA erfassen (Maßnahme, Verantwortlicher, Frist). 4) Findings nachverfolgen bis Status erledigt.",
      "tipps": [
        "Der 3-Jahres-Zyklus (36 Monate) wird aus 'durchgeführt am' abgeleitet und erscheint im Fristen-Dashboard.",
        "Findings sind das CAPA-Register – offene Findings mit Frist und Verantwortlichem führen."
      ]
    },
    {
      "id": "governance",
      "title": "🏛️ Governance (Art. 20)",
      "zweck": "Nachweis der Leitungsverantwortung: Billigungsbeschluss der Risikomanagementmaßnahmen, Überwachung und Management-Schulungen.",
      "rechtsgrundlage": "Art. 20 NIS2-RL (Billigung/Überwachung durch Leitungsorgane; Schulungspflicht)",
      "pflichtfelder": [
        "Typ (z. B. Billigungsbeschluss/Schulung), Datum, Gremium.",
        "Gegenstand und Bezug zur Risikomanagement-Version (rm_version).",
        "Dokument-URL (Beschluss/Protokoll) und nächster Review.",
        "Schulung: Teilnehmer (Name, Rolle, Status, Quiz-Score) und Quiz-Referenz."
      ],
      "anleitung": "1) Billigungsbeschluss mit Datum/Gremium/Gegenstand und der gebilligten RM-Version erfassen, Protokoll verlinken. 2) Management-Schulungen anlegen und Teilnehmer/Status/Quiz-Score dokumentieren. 3) Nächsten Review setzen.",
      "tipps": [
        "Die Geschäftsleitung haftet persönlich – Billigung und Schulungsteilnahme müssen belegbar sein.",
        "RM-Version im Beschluss benennen, damit die gebilligte Fassung nachvollziehbar ist."
      ]
    },
    {
      "id": "fristen",
      "title": "📅 Fristen",
      "zweck": "Kontrollzyklus-/Wiedervorlage-Dashboard, das fällige Termine über alle Bereiche aggregiert (Risiko-Reviews, Lieferanten-Assessments, Audit-Zyklus, Jahres-Bestätigung).",
      "rechtsgrundlage": "Art. 21 Abs. 2 lit. f (Bewertung der Wirksamkeit) / Art. 27 Abs. 4 NIS2-RL",
      "pflichtfelder": [
        "Keine direkte Eingabe – aggregiert review_datum/assessment_datum (N2/N4), naechster_audit_soll (Audits) und naechste_jahres_bestaetigung (Registrierung)."
      ],
      "anleitung": "1) Fällige/überfällige Termine (Ampel, Warnung ab 30 Tagen) ablesen. 2) Im jeweiligen Quell-Tab (Risiko, Lieferant, Audit, Registrierung) bearbeiten. 3) Wiedervorlage-Datum nach Erledigung neu setzen.",
      "tipps": ["Die Termine stammen aus den Fach-Tabs – hier nur überwachen, dort pflegen."]
    },
    {
      "id": "dvo",
      "title": "📜 DVO 2690",
      "zweck": "Sektor-Anforderungsset der Durchführungsverordnung (EU) 2024/2690: die 13 DVO-Abschnitte als bewertbare Controls, aktiviert je nach Sektor.",
      "rechtsgrundlage": "Durchführungsverordnung (EU) 2024/2690 (technische/methodische Anforderungen, digitale Infrastruktur/Dienste)",
      "pflichtfelder": [
        "Aktivierung des DVO-Sets (gebunden an den Scoping-/Klassifikator-Sektor).",
        "Je DVO-Abschnitt (DVO-1 … DVO-13): Reifegrad/Status und Nachweis."
      ],
      "anleitung": "1) Prüfen, ob das Unternehmen unter die DVO 2024/2690 fällt (digitale Infrastruktur/Dienste – wird gegen den Sektor geprüft). 2) DVO-Set aktivieren – die 13 Abschnitte erscheinen als Controls (Kapitel DVO2690). 3) Je Abschnitt bewerten und Nachweise hinterlegen.",
      "tipps": [
        "Die DVO 2024/2690 gilt nur für bestimmte digitale Sektoren – außerhalb davon nicht aktivieren.",
        "Die 13 Abschnitte konkretisieren Art. 21 – Nachweise möglichst aus bestehenden Pflicht-Doku-Belegen referenzieren."
      ]
    },
    {
      "id": "anforderungen",
      "title": "✅ Anforderungen",
      "zweck": "Bewertung des NIS2-Anforderungskatalogs (Governance Art. 20, Maßnahmen Art. 21, Meldepflichten Art. 23, Lieferkette) mit Reifegrad und Nachweisbezug.",
      "rechtsgrundlage": "Art. 20, 21, 23 NIS2-RL; Art. 24–25 (Zertifizierung)",
      "pflichtfelder": [
        "Je Anforderung: Reifegrad 0–5 (0 nicht bewertet … 5 vollständig erfüllt) und Nachweis.",
        "Bei eigenen Anforderungen: Kapitel, Titel, Beschreibung, Hinweise, Gewichtung."
      ],
      "anleitung": "1) Kapitelweise (Governance/Risikomanagement/Meldepflichten/Lieferkette) durchgehen. 2) Reifegrad je Anforderung konsistent setzen. 3) Nachweis verknüpfen. 4) Offene/teilweise Anforderungen in Maßnahmen/Issues überführen.",
      "tipps": ["Gewichtung beachten – sie beeinflusst den verdichteten Gesamt-Reifegrad."]
    },
    {
      "id": "assistenten",
      "title": "🤖 Assistenten",
      "zweck": "KI-gestützte Wizards (Copy/Paste-Prompts) zum Vorausfüllen von Pflicht-Doku und Anforderungs-Bewertung (N1–N5, DVO).",
      "rechtsgrundlage": "— (Hilfsmittel; die Bewertung bleibt beim Verantwortlichen)",
      "pflichtfelder": [
        "Keine Pflichtfelder – Eingaben sind je Assistent kontextabhängig."
      ],
      "anleitung": "1) Assistenten wählen. 2) Prompt mit Projektkontext erzeugen, ins KI-Tool kopieren. 3) Antwort zurückspielen/prüfen. 4) Ergebnis in den Fach-Tab übernehmen.",
      "tipps": ["KI-Vorschläge fachlich gegenprüfen, bevor sie als Nachweis gelten."]
    },
    {
      "id": "dokumente",
      "title": "📄 Dokumente",
      "zweck": "Ablage und Verwaltung hochgeladener Nachweise/Belege (Richtlinien, Protokolle, Konzepte) zum Projekt.",
      "rechtsgrundlage": "Art. 21 NIS2-RL (Nachweisführung der Maßnahmen)",
      "pflichtfelder": [
        "Datei + aussagekräftiger Titel; sinnvoll: Bezug zur Maßnahme/Anforderung."
      ],
      "anleitung": "1) Nachweis hochladen. 2) Eindeutig benennen und zuordnen. 3) Bei Aktualisierung neue Version ablegen statt überschreiben.",
      "tipps": ["Sprechende Namen und Maßnahmenbezug erleichtern Audit und Bericht."]
    },
    {
      "id": "berichte",
      "title": "📄 Berichte",
      "zweck": "Export des NIS2-Umsetzungsstands (Reifegrad, offene Maßnahmen, Nachweise) gegenüber Leitung und Aufsichtsbehörde.",
      "rechtsgrundlage": "Art. 21 Abs. 2 lit. f / Art. 32 NIS2-RL (Nachweis der Umsetzung)",
      "pflichtfelder": [
        "Auswahl der Berichtsabschnitte und Format.",
        "Voraussetzung: Anforderungen, Governance, Meldeprozess und Lieferkette sind gepflegt."
      ],
      "anleitung": "1) Vorab alle Fach-Tabs finalisieren. 2) Abschnitte und Format wählen. 3) Bericht erzeugen und als Nachweis ablegen/vorlegen.",
      "tipps": ["Die Berichtsqualität hängt direkt vom gepflegten Reifegrad und den Nachweisen ab."]
    }
  ],
  "links": [
    {
      "label": "Modul-Dokumentation NIS2",
      "href": docsUrl('/modules/nis2/')
    },
    {
      "label": "NIS2-Richtlinie (EU) 2022/2555 (EUR-Lex)",
      "href": "https://eur-lex.europa.eu/eli/dir/2022/2555/oj"
    }
  ],
  "module": "nis2"
}
