// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'

export const firmenHelp: ModuleHelp = {
  "title": "Firmen",
  "regulation": "Organisatorische Grundlage / Mandantenfähigkeit (kein eigenes Fachgesetz); ableitbar aus der Rechenschafts- und Dokumentationspflicht der DSGVO (VO (EU) 2016/679, Art. 5 Abs. 2, Art. 24, Art. 30) sowie aus den Nachweispflichten der fachlichen Rahmenwerke (CRA – VO (EU) 2024/2847; NIS2 – RL (EU) 2022/2555; KI-VO – VO (EU) 2024/1689).",
  "purpose": "Das Modul Firmen ist die zentrale Stammdaten- und Strukturklammer der Suite: Pro Firma werden Produkte erfasst, und pro Produkt entsteht je Compliance-Rahmen (CRA, NIS2, KI-VO, DSGVO, Risikobewertung) ein eigenes Projekt. Es ist weniger an ein einzelnes Gesetz gebunden, sondern liefert die mandantenfähige Grundordnung, auf der die fachlichen Module aufsetzen.",
  "legalBasis": {
    "title": "Rechtlicher und organisatorischer Rahmen",
    "intro": "Eine eigene Compliance-Pflicht zur Firmenverwaltung gibt es nicht; das Modul setzt jedoch die Rechenschafts- und Nachweispflichten der einschlägigen Regelwerke organisatorisch um. Diese verlangen, dass Verantwortliche pro Produkt bzw. Verarbeitung nachvollziehbar dokumentieren, wer wofür zuständig ist und welche Maßnahmen getroffen wurden. Saubere Stammdaten je Firma/Produkt sind die Voraussetzung, um diese Nachweise konsistent und prüffest zu führen.",
    "bullets": [
      "DSGVO Art. 5 Abs. 2 i. V. m. Art. 24: Rechenschaftspflicht – der Verantwortliche muss die Einhaltung nachweisen können; dies erfordert eine klare Zuordnung von Verarbeitungen zu Verantwortlichen/Produkten.",
      "DSGVO Art. 30: Verzeichnis von Verarbeitungstätigkeiten – pro Verantwortlichem zu führen; die produktbezogene Struktur liefert die Grundlage für vollständige Einträge.",
      "CRA (VO (EU) 2024/2847) Art. 13 und Anhang VII: produktbezogene technische Dokumentation und Konformitätsnachweise – setzen eine eindeutige Produkt-/Hersteller-Zuordnung voraus.",
      "NIS2 (RL (EU) 2022/2555) Art. 20–21: Verantwortung der Leitungsorgane und Risikomanagement je Einrichtung – erfordert eindeutige Zuordnung von Maßnahmen zur jeweiligen Organisation/Dienst.",
      "KI-VO (VO (EU) 2024/1689) Art. 11 und Anhang IV: technische Dokumentation je KI-System – benötigt eine klare Bindung an Anbieter und konkretes System/Produkt."
    ]
  },
  "implementation": {
    "title": "Vorgehen im Modul",
    "intro": "Empfohlener Arbeitsablauf: zuerst die Stammdaten anlegen (Firma, dann Produkt), anschließend pro Produkt je benötigtem Compliance-Rahmen ein Projekt erzeugen und dieses dann im jeweiligen Fachmodul (CRA, NIS2, KI-VO, DSGVO, Risikobewertung) bearbeiten. Das Modul Firmen bleibt die Übersicht; die inhaltliche Arbeit findet in den Modul-Projekten statt.",
    "bullets": [
      "Schritt 1: Firma anlegen (Organisation/Mandant) mit eindeutiger Bezeichnung.",
      "Schritt 2: Produkt(e) je Firma erfassen – ein Produkt = eine Bewertungseinheit (z. B. ein Software-/KI-Produkt oder Dienst).",
      "Schritt 3: Pro Produkt je relevantem Rahmen ein Projekt erzeugen; nur die tatsächlich anwendbaren Rahmen aktivieren, um Scheinpflichten zu vermeiden.",
      "Repository- und Dokumentations-URLs (z. B. Quellcode-Repo, Doku-Links) pro Produkt hinterlegen – sie werden in die entstehenden Modul-Projekte übernommen und für Issue-/Doku-Verknüpfung genutzt.",
      "Erst Stammdaten vollständig pflegen, dann in das jeweilige Fachmodul wechseln; das vermeidet doppelte Anlage und inkonsistente Zuordnungen.",
      "Eindeutige, dauerhafte Bezeichnungen wählen (keine nachträglichen Umbenennungen), damit Nachweise und verknüpfte Projekte stabil bleiben."
    ]
  },
  "moduleSpecific": {
    "title": "Besonderheiten des Moduls",
    "intro": "Firmen ist ein Workflow- und Stammdatenmodul ohne eigene Fragebogen-/Bewertungslogik. Seine Aufgabe ist die mandantenfähige Strukturierung, aus der die fachlichen Projekte hervorgehen.",
    "bullets": [
      "Hierarchie: Firma → Produkt → Projekt je Compliance-Rahmen (1 Produkt kann mehrere Rahmen-Projekte haben).",
      "Mandantenfähigkeit: Daten sind je Firma getrennt; dies trennt auch Verantwortlichkeiten und Nachweise sauber.",
      "Repository/Doku pro Produkt: hinterlegte URLs steuern die Verknüpfung zu Issues und Dokumentation in den Fachmodulen.",
      "Keine eigenen Compliance-Inhalte: Bewertung, Prompts und Berichte entstehen erst in den jeweiligen Modul-Projekten.",
      "Single Source of Truth: Stammdaten hier sind referenzierend für alle nachgelagerten Module – Änderungen wirken modulübergreifend."
    ]
  },
  "links": [
    {
      "label": "Architektur-Übersicht (docs/ARCHITECTURE.md)",
      "href": "docs/ARCHITECTURE.md"
    },
    {
      "label": "Datenbank-Architektur (docs/ARCHITECTURE_DATABASE.md)",
      "href": "docs/ARCHITECTURE_DATABASE.md"
    }
  ],
  "module": "firmen"
}
