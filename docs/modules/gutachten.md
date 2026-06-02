# Gutachten-Modul

Das Gutachten-Modul unterstützt die vollständige Erstellung von
Compliance-Gutachten für regulatorische Frameworks wie DORA, NIS2,
CRA, ISO 27001, DSGVO, AI Act und BSI-Grundschutz.

## Funktionen

- **Framework-Bibliothek**: Regulierungs-PDFs automatisch von EUR-Lex
  oder der BSI-Webseite herunterladen und indexieren
- **PDF-Indexierung**: Seitenweise Textextraktion mit `pdfplumber`,
  Abschnitts- und Artikel-Erkennung, Seitenzahl-Persistenz
- **Interview-Fragen-Generator**: Strukturierter Prompt auf Basis der
  indexierten Framework-Texte
- **Fragebogen-Workflow**: Fragen als XLSX exportieren, Antworten +
  Bewertungen aus XLSX importieren oder direkt im Web-Editor erfassen
- **Gutachten-Generator**: DOCX-Bericht mit Deckblatt, Executive Summary,
  Framework-Kapiteln, Interviewtabelle, Empfehlungen und Quellenverzeichnis

## Unterstützte Frameworks

| Framework | Kürzel | Dokument-Quelle |
|---|---|---|
| Digital Operational Resilience Act | `DORA` | EUR-Lex (automatisch) |
| Network and Information Security 2 | `NIS2` | EUR-Lex (automatisch) |
| Cyber Resilience Act | `CRA` | EUR-Lex (automatisch) |
| ISO/IEC 27001:2022 | `ISO27001` | XLSX-Fragebogen (manuell einlegen) |
| Datenschutz-Grundverordnung | `DSGVO` | EUR-Lex (automatisch) |
| EU AI Act | `AI_ACT` | EUR-Lex (automatisch) |
| BSI IT-Grundschutz | `BSI` | BSI-Webseite (automatisch) |

## Bewertungsskala

Antworten werden in vier Stufen klassifiziert:

- **erfüllt**
- **teilweise erfüllt**
- **nicht erfüllt**
- **nicht anwendbar**

Pro Frage wird zusätzlich eine Freitext-Bemerkung gespeichert.

## Datenhaltung

| Aspekt | Details |
|---|---|
| **Datenbank** | `data/db/gutachten.sqlite` (Dokumente, Sections, Metadaten) |
| **Eingabe** | EUR-Lex-PDFs, BSI-Webseite, XLSX-Fragebogen |
| **Ausgabe** | XLSX (Fragebogen), DOCX (Gutachten) |
| **KI** | optional (für Fragen- und Gutachten-Prompts) |

## DOCX-Ausgabe

Das fertige Gutachten enthält:

- Deckblatt (Projektname, Frameworks, Datum, Prüfer)
- Executive Summary
- Framework-Kapitel mit aggregierten Bewertungen
- Interviewtabelle (Frage / Antwort / Bewertung / Bemerkung)
- Empfehlungen
- Quellen-/Regulatorik-Verzeichnis

## Sicherheitshinweise

- Downloads erfolgen ausschließlich von bekannten URLs (EUR-Lex, BSI)
- Heruntergeladene PDFs werden auf Dateigröße geprüft
- XLSX-Fragebogen werden gegen Office-Archive-Validierung gefahren

Erreichbar in der Web-App unter `/gutachten`. Framework-Downloads
liegen im Admin-Bereich unter `/admin/frameworks`.
