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
      "Dashboard (v7.0.0): Gesamtüberblick je Firma – Gesamt-Umsetzungsgrad (Ø der Module CRA, NIS2, AI Act, DSGVO, WiBA), Umsetzungsgrad je Modul und Projekt (identisch zu den Modul-Dashboards), offene Risiken aus dem Risiko-Cockpit, DSGVO-TOM/BSI-WiBA, offene Aufgaben/Fristen, Produkte, Nachweise und zuletzt erzeugte Berichte.",
      "Reiter Risiko-Cockpit: alle offenen Risiken und Schwachstellen der Firma modulübergreifend (Risikobewertung, CRA, SOC).",
      "Reiter Pentests (v7.1.0): Pentest-Berichte als PDF hochladen, Findings per KI extrahieren und nach CRA (Schwachstellen/Risiken), DSGVO (TOM-Wirksamkeit) und WiBA (Beleg) übernehmen – inkl. Nachtest und Status-Rückfluss.",
      "Reiter Berichte: Firmen-Gesamtbericht (Management-Überblick) und Risikobericht als Word/PDF, ablegbar mit Historie, plus KI-Management-Zusammenfassung.",
      "Keine eigenen Compliance-Bewertungen: Bewertung und Prompts entstehen in den jeweiligen Modul-Projekten; die Firma verdichtet sie im Dashboard und in den Firmenberichten.",
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
    },
    {
      "id": "pentest",
      "title": "🛡️ Pentests",
      "zweck": "Pentest-Berichte (PDF) einmal je Firma hochladen, die Findings per KI herauslösen und modulübergreifend als Nachweis und Risiko verfolgen: Anwendungs-Pentest → CRA, Pentest der internen Infrastruktur → DSGVO-TOM und BSI-WiBA.",
      "rechtsgrundlage": "CRA Anhang I Teil II Nr. 3 (regelmäßige Sicherheitstests) und Anhang VII (Testberichte); DSGVO Art. 32 Abs. 1 lit. d (regelmäßige Überprüfung der Wirksamkeit der TOM); BSI-WiBA als Basis-Absicherung",
      "pflichtfelder": [
        "PDF-Bericht (oder DOCX), Art (Anwendung / interne Infrastruktur), Prüfer, Prüfzeitraum, Umfang.",
        "Je Finding: Ref, Titel, Schwere (critical … info), CVSS, Kategorie, betroffenes System, Empfehlung, Status (offen / behoben / akzeptiert / False Positive).",
        "Nachtest: zweiter Bericht mit „Nachtest von …“ – behobene Findings erhalten den Nachtest als Beleg."
      ],
      "anleitung": "1) „➕ Pentest-Bericht hochladen“ (Datei liegt danach auch unter Nachweise). 2) „🤖 Findings extrahieren“: lange Berichte werden in Teile zerlegt; „⚡ Direkt mit KI“ erst nach ausdrücklicher Bestätigung oder Copy/Paste. 3) Vorschau prüfen, Auswahl übernehmen. 4) „Übernehmen nach“: CRA (Schwachstellen, Risiken, Anhang VII), DSGVO-TOM (Wirksamkeitsprüfung, Risiken) bzw. WiBA (Beleg an Prüffragen). 5) Status pflegen – er fließt in CRA-Schwachstellen, Risiken und TOM-Wirksamkeit zurück.",
      "tipps": [
        "Pentest-Berichte sind hochsensibel: bevorzugt lokale KI (Ollama) oder Copy/Paste in ein freigegebenes Werkzeug; der Cloud-Weg verlangt eine Bestätigung und wird auditiert.",
        "Kein Automatismus bei Bewertungen: TOM-Status und WiBA-Antworten werden nie automatisch geändert. Widerspricht ein offenes Finding einem „Ja“ bzw. einer bewerteten OWASP-Kontrolle, erscheint „⚠️ Neubewertung erforderlich“.",
        "Die Zuordnung Finding → TOM/WiBA-Prüffrage ist ein Vorschlag aus der Kategorie – vor der Übernahme prüfen.",
        "Gescannte PDFs ohne Textebene: Findings über „➕ Finding manuell“ erfassen."
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
