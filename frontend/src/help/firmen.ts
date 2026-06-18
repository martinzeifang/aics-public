// Auto-generiert (#926) — Modul-Hilfe-Inhalt.
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

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
  "areas": [
    {
      "id": "stammdaten",
      "title": "Stammdaten",
      "zweck": "Grunddaten der Firma/des Mandanten – die Klammer, auf die alle Modul-Projekte und firmenweiten Aggregationen (Risiko-Cockpit, firmen_id) referenzieren.",
      "rechtsgrundlage": "Organisatorisch; setzt die Rechenschaftspflicht (DSGVO Art. 5 Abs. 2 / Art. 24) und produktbezogene Doku-Pflichten um",
      "pflichtfelder": [
        "Firmen-Name (Pflicht, eindeutig, dauerhaft) – beim Anlegen werden in aktivierten Modulen Projekte mit diesem Namen erzeugt.",
        "Unternehmen (rechtliche Bezeichnung der Organisation).",
        "Berater / Verantwortlicher.",
        "Beschreibung (Kontext zur Firma)."
      ],
      "anleitung": "1) Firma mit eindeutigem, stabilem Namen anlegen. 2) Unternehmen und Verantwortlichen erfassen. 3) Beschreibung ergänzen. 4) Speichern – danach den Firmen-Namen nicht mehr umbenennen.",
      "tipps": [
        "Der Firmen-Name ist der Verknüpfungsschlüssel (firmen_id-Backfill per Name-Match) – nachträgliche Umbenennung bricht Zuordnungen.",
        "Stammdaten zuerst vollständig pflegen, bevor Module aktiviert/Projekte angelegt werden."
      ]
    },
    {
      "id": "module",
      "title": "Module",
      "zweck": "Aktivierung der Compliance-Module je Firma; pro aktiviertem Modul kann ein gleichnamiges Projekt erzeugt werden (Direktlink ins Fachmodul).",
      "rechtsgrundlage": "Anwendbarkeit der jeweiligen Rahmen (CRA VO (EU) 2024/2847; NIS2 RL (EU) 2022/2555; KI-VO VO (EU) 2024/1689; DSGVO)",
      "pflichtfelder": [
        "Modul-Schalter je Rahmen: Risikobewertung, CRA, NIS2, DSGVO, AI Act, WiBA, Gutachten.",
        "Aktivierung nur für tatsächlich anwendbare Rahmen setzen."
      ],
      "anleitung": "1) Nur zutreffende Module aktivieren (Scheinpflichten vermeiden). 2) ‚Projekte anlegen' erzeugt für aktivierte Module die Modul-Projekte. 3) Über ‚Öffnen →' direkt ins jeweilige Fachmodul wechseln.",
      "tipps": [
        "Aktivierung sollte die reale Betroffenheit abbilden – die fachliche Arbeit findet im Modul-Projekt statt.",
        "‚Projekte anlegen' ist idempotent: bereits bestehende Projekte werden nicht doppelt erzeugt."
      ]
    },
    {
      "id": "risiko",
      "title": "Risiko-Projekte",
      "zweck": "Mehrere Risikobewertungs-Projekte je Firma (z. B. je Produkt/Service) mit Standard-Framework-Vorgabe.",
      "rechtsgrundlage": "CRA Art. 13 (Risikobewertung); methodisch ISO/IEC 27005",
      "pflichtfelder": [
        "Standard-Framework (rb_framework) für neue Projekte dieser Firma.",
        "Je Projekt: Name (beim Anlegen im Risikobewertungs-Modul)."
      ],
      "anleitung": "1) Standard-Framework wählen. 2) Über ‚+ Risikobewertungs-Projekt anlegen' ein Projekt je Bewertungseinheit erzeugen. 3) Inhaltliche Risikoarbeit im Risikobewertungs-Modul (‚Öffnen →').",
      "tipps": [
        "Ein Projekt je Produkt/Service hält Risiken sauber getrennt und vergleichbar.",
        "Offene Risiken dieser Projekte fließen in das firmenweite Risiko-Cockpit."
      ]
    },
    {
      "id": "produkte",
      "title": "Produkte (CRA)",
      "zweck": "Produkte der Firma; jedes Produkt erzeugt automatisch ein CRA-Projekt. Bewertungseinheit für die CRA-Konformität.",
      "rechtsgrundlage": "CRA (VO (EU) 2024/2847) Art. 13 + Anhang VII (produktbezogene technische Dokumentation)",
      "pflichtfelder": [
        "Produkt-Name und Produktklasse.",
        "Standard-Produkt-Kennzeichnung (★) – das Default-Produkt entspricht dem CRA-Projekt mit Firmennamen."
      ],
      "anleitung": "1) Je Produkt einen Eintrag anlegen (Klasse setzen). 2) Standard-Produkt markieren. 3) Über ‚CRA öffnen →' die produktbezogene CRA-Readiness bearbeiten.",
      "tipps": [
        "Ein Produkt = eine CRA-Bewertungseinheit; die Produktklasse steuert die CRA-Anforderungstiefe.",
        "Produkt-Namen stabil halten – sie bestimmen den CRA-Projektnamen (‚<Firma> – <Produkt>')."
      ]
    },
    {
      "id": "evidence",
      "title": "Nachweise",
      "zweck": "Zentrale Ablage von Nachweis-Material (Dateien und Web-Quellen) der Firma; wird modulübergreifend für Bewertungen und Prompts genutzt.",
      "rechtsgrundlage": "Nachweis-/Rechenschaftspflicht (DSGVO Art. 5 Abs. 2); produktbezogene Doku der Fachrahmen",
      "pflichtfelder": [
        "Datei-Upload (PDF/DOCX/TXT/MD/CSV/XLSX) oder Web-URL.",
        "Optional: Typ und Schlagwörter zur Auffindbarkeit."
      ],
      "anleitung": "1) Datei hochladen oder URL hinzufügen. 2) Per ‚Extrahieren' den Textinhalt für Bewertungen/Prompts verfügbar machen. 3) Schlagwörter setzen, um Nachweise gezielt zu finden.",
      "tipps": [
        "Nachweise stehen Modulen (z. B. WiBA-Prüffragen) firmenweit zur Verfügung – einmalige zentrale Pflege genügt.",
        "Sprechende Namen/Tags erleichtern das spätere Audit."
      ]
    },
    {
      "id": "gutachten",
      "title": "Gutachten",
      "zweck": "Festlegung der im Gutachten zu prüfenden Frameworks und des Prüfungsfokus für diese Firma.",
      "rechtsgrundlage": "§§ 404a/407a ZPO (Gegenstand/Umfang); methodisch BISG-Standard",
      "pflichtfelder": [
        "Auswahl der zu prüfenden Frameworks (gutachten_frameworks).",
        "Prüfungsfokus (Schwerpunkte für das Gutachten)."
      ],
      "anleitung": "1) Relevante Frameworks ankreuzen. 2) Prüfungsfokus formulieren (oder Vorschlag generieren). 3) Speichern – die Angaben fließen in die Gutachten-Erstellung im Gutachten-Modul ein.",
      "tipps": [
        "Den Prüfungsfokus eng am konkreten Auftrag/Beweisbeschluss halten.",
        "Die Detail-Erstellung des Gutachtens erfolgt im Gutachten-Modul, nicht hier."
      ]
    }
  ],
  "links": [
    {
      "label": "Firmen-Modul-Doku (Online)",
      "href": docsUrl('/modules/firmen/')
    }
  ],
  "module": "firmen"
}
