# Gutachten-Modul

Das Gutachten-Modul ist das umfangreichste Modul der Suite (~5.500 LOC). Es unterstützt die vollständige Erstellung von Compliance-Gutachten für regulatorische Frameworks wie DORA, NIS2, CRA, ISO 27001, DSGVO, AI Act und BSI-Grundschutz.

## Verzeichnisstruktur

```
gutachten/
├── __init__.py
├── __main__.py
├── config.py                # Framework-Konfiguration + Prüfungsfokus
├── db.py                    # SQLite-Schema + CRUD
├── file_download.py         # Framework-Dokumente herunterladen
├── io_xlsx.py               # Fragebogen XLSX lesen/schreiben
├── io_pdf.py                # PDF-Textextraktion (pdfplumber)
├── prompts.py               # Fragen- und Gutachten-Prompts
├── gutachten_gen.py         # Orchestrierung der Gutachten-Erstellung
├── gui_module.py            # Hauptfenster (GutachtenModuleFrame)
├── _panel_gutachten.py      # Fragebogen-Editor-Panel
└── _download_dialog.py      # Download-Dialog
```

## Unterstützte Frameworks

| Framework | Kürzel | Dokument-Typ | Download |
|---|---|---|---|
| Digital Operational Resilience Act | `DORA` | EUR-Lex PDF | Automatisch |
| Network and Information Security 2 | `NIS2` | EUR-Lex PDF | Automatisch |
| Cyber Resilience Act | `CRA` | EUR-Lex PDF | Automatisch |
| ISO/IEC 27001:2022 | `ISO27001` | XLSX-Fragebogen | Manuell einlegen |
| Datenschutz-Grundverordnung | `DSGVO` | EUR-Lex PDF | Automatisch |
| EU AI Act | `AI_ACT` | EUR-Lex PDF | Automatisch |
| BSI IT-Grundschutz | `BSI` | BSI-Webseite | Automatisch |

## Konfiguration

Datei: `gutachten.config.json`

=== "Pfade"

    | Schlüssel | Standard |
    |---|---|
    | `paths.dora_dir` | `data/dora_downloads` |
    | `paths.nis2_dir` | `data/nis2_resources` |
    | `paths.cra_dir` | `data/cra_resources` |
    | `paths.iso_dir` | `data/iso27001_questionnaires` |
    | `paths.dsgvo_dir` | `data/dsgvo_resources` |
    | `paths.ai_act_dir` | `data/ai_act_resources` |
    | `paths.bsi_dir` | `data/bsi_resources` |
    | `paths.db_path` | `data/db/gutachten.sqlite` |
    | `paths.prompts_dir` | `out/gutachten/prompts` |
    | `paths.answers_dir` | `out/gutachten/answers` |
    | `paths.fragebogen_dir` | `out/gutachten/fragebogen` |
    | `paths.ausgefuellt_dir` | `out/gutachten/ausgefuellt` |
    | `paths.gutachten_dir` | `out/gutachten/gutachten` |

=== "UI"

    | Schlüssel | Beschreibung |
    |---|---|
    | `ui.projekt_name` | Projektname für Dateinamen |
    | `ui.frameworks` | Ausgewählte Frameworks (Liste) |
    | `ui.pruefungsfokus` | Beschreibung des Prüfungsumfangs |
    | `ui.debug_mode` | Debug-Logging aktivieren |
    | `ui.test_mode` | Eingeschränkte Verarbeitung |

=== "Prompt"

    | Schlüssel | Beschreibung |
    |---|---|
    | `prompt.fragen_header` | Einleitung für Interview-Fragen-Prompt |
    | `prompt.gutachten_header` | Einleitung für Gutachten-Prompt |
    | `prompt.bewertung_skala` | `["erfüllt", "teilweise erfüllt", "nicht erfüllt", "nicht anwendbar"]` |
    | `prompt.fragen_batch_size` | Fragen pro Prompt-Batch (Standard: 15) |

## Datenmodelle

```python
@dataclass
class Doc:
    url: str
    framework: str
    doc_name: str
    ...

@dataclass
class ImportedQuestion:
    question_id: str
    framework: str
    section_ref: str
    title: str
    question: str
    answer: str | None
    bewertung: str | None    # "erfüllt" | "teilweise erfüllt" | ...
    bemerkung: str | None
```

## Datenbankstruktur

### `framework_documents`
Metadaten zu heruntergeladenen/importierten Dokumenten.

### `framework_sections`
Extrahierte Textabschnitte, indiziert nach Framework und Abschnittsreferenz (z.B. `Art. 5`).

### `framework_metadata`
Konfigurationsschlüssel/-werte (z.B. Indexierungszeitpunkt).

## PDF-Extraktion

`gutachten/io_pdf.py` nutzt `pdfplumber` zur Textextraktion:

- Seitenweise Extraktion
- Abschnittsidentifikation über Überschriften-Erkennung
- Referenzerkennung (Artikel-Nummern, Paragrafen)
- Seitenzahl-Persistenz für spätere Quellangaben

## Gutachten-Generierung

`gutachten/gutachten_gen.py` orchestriert:

1. Antworten aus DB laden
2. Bewertungen aggregieren (Erfüllungsgrad je Framework)
3. Gutachten-Prompt mit Antworten und Bewertungsskala erstellen
4. JSON-Antwort von ChatGPT empfangen
5. DOCX mit formatiertem Gutachten exportieren

### DOCX-Ausgabe enthält:
- Deckblatt (Projektname, Frameworks, Datum, Prüfer)
- Executive Summary
- Framework-Kapitel mit Bewertungen
- Interviewtabelle (Frage / Antwort / Bewertung)
- Empfehlungen
- Quellen-/Regulatorik-Verzeichnis

## Fragebogen-Editor (`GutachtenEditorPanel`)

`gutachten/_panel_gutachten.py`

Eine ttk.Frame-Unterklasse, die eine tabellarische Ansicht der Interview-Fragen mit:
- Inline-Antwortbearbeitung
- Bewertungs-Dropdown (erfüllt / teilweise erfüllt / nicht erfüllt / nicht anwendbar)
- Freitextfeld für Bemerkungen
- Navigation durch Fragen

## GUI-Funktionen

| Funktion | Beschreibung |
|---|---|
| Framework-Download | Öffnet `_DownloadDialog` für automatische Downloads |
| PDFs einlesen | Extrahiert Text und speichert in DB |
| Interviewfragen generieren | Erstellt Fragen-Prompt aus DB-Inhalten |
| Fragebogen exportieren | XLSX-Fragebogen mit Fragen erstellen |
| Ausgefüllten Fragebogen importieren | Antworten aus XLSX in DB laden |
| Gutachten erstellen | Gutachten-Prompt generieren |
| Gutachten exportieren | Fertiges DOCX-Gutachten ausgeben |

## Download-Dialog

`gutachten/_download_dialog.py`

Zeigt verfügbare Dokumente je Framework mit:
- Download-Status (ausstehend / heruntergeladen / Fehler)
- Manuelle Auswahl einzelner Dokumente
- Fortschrittsanzeige
- Fehlerprotokoll

## Sicherheitshinweise

- Downloads werden nur von konfigurierten, bekannten URLs (EUR-Lex, BSI) durchgeführt
- Heruntergeladene PDFs werden auf Dateigröße geprüft
- XLSX-Fragebogen werden gegen Office-Archive-Validierung geprüft
