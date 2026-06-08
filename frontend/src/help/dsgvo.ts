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
