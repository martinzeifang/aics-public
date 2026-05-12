# Gutachten Workflow

Vollständiger Ablauf zur Erstellung eines Compliance-Gutachtens für regulatorische Frameworks (DORA, NIS2, CRA, ISO 27001, DSGVO, AI Act, BSI).

## Überblick

```
Framework-Dokumente herunterladen
         ↓
PDFs in Datenbank einlesen
         ↓
Interviewfragen generieren (ChatGPT)
         ↓
Fragebogen als Excel exportieren
         ↓
Fragebogen ausfüllen (Kunde/Interview)
         ↓
Ausgefüllten Fragebogen importieren
         ↓
Gutachten-Prompt generieren (ChatGPT)
         ↓
Gutachten als Word exportieren
```

## Schritt 1: Projekt konfigurieren

1. Suite starten: `python -m bnits_suite`
2. Tab **Gutachten** öffnen
3. **Bearbeiten → Projekteinstellungen** öffnen:
   - Projektname eingeben (erscheint im Dateinamen)
   - Frameworks auswählen (z.B. DORA + ISO27001)
   - Prüfungsfokus beschreiben

## Schritt 2: Framework-Dokumente herunterladen

1. **Dokumente herunterladen** klicken → Download-Dialog öffnet sich
2. Frameworks auswählen
3. **Herunterladen** starten
4. Fortschritt abwarten (EUR-Lex PDFs, BSI-Dokumente werden geladen)

!!! note "ISO 27001"
    ISO-27001-Dokumente können nicht automatisch heruntergeladen werden (kostenpflichtig). Lege eigene Fragebögen/Dokumente in `data/iso27001_questionnaires/` ab.

## Schritt 3: Dokumente einlesen

1. **Dokumente einlesen** klicken
2. Das System extrahiert Textabschnitte und speichert sie in `gutachten.sqlite`

## Schritt 4: Interviewfragen generieren

1. **Interviewfragen generieren** klicken
2. Prompt-Datei wird erstellt: `out/gutachten/prompts/<projektname>_fragen_<timestamp>.md`
3. Prompt in ChatGPT einfügen
4. ChatGPT antwortet mit JSON-Array der Interviewfragen:

```json
[
  {
    "framework": "DORA",
    "section_ref": "Art. 5",
    "title": "IKT-Risikomanagement",
    "question": "Verfügen Sie über ein dokumentiertes IKT-Risikomanagement-Framework?"
  },
  ...
]
```

5. JSON in Antwortdatei speichern
6. **Fragen importieren** klicken

## Schritt 5: Fragebogen exportieren

1. **Fragebogen exportieren (Excel)** klicken
2. Excel-Datei wird erstellt: `out/gutachten/fragebogen/<projektname>_<timestamp>.xlsx`

Der Fragebogen enthält für jede Frage:
- Framework / Artikel-Referenz
- Fragentext
- Antwort-Spalte (auszufüllen)
- Bewertungs-Spalte (`erfüllt` / `teilweise erfüllt` / `nicht erfüllt` / `nicht anwendbar`)
- Bemerkungen-Spalte

## Schritt 6: Fragebogen ausfüllen

Der Fragebogen wird an den Kunden oder in einem Interview ausgefüllt. Dabei:
- Antworten in die Antwort-Spalte eintragen
- Bewertung aus Dropdown wählen
- Optionale Bemerkungen ergänzen

## Schritt 7: Ausgefüllten Fragebogen importieren

1. Ausgefüllten Fragebogen in `out/gutachten/ausgefuellt/` ablegen
2. **Ausgefüllten Fragebogen importieren** klicken
3. Antworten werden in `gutachten.sqlite` gespeichert
4. Im **Fragebogen-Editor** können Antworten noch korrigiert werden

## Schritt 8: Gutachten-Prompt generieren

1. **Gutachten-Prompt generieren** klicken
2. Der Prompt enthält alle Fragen, Antworten und Bewertungen
3. Prompt in ChatGPT einfügen
4. ChatGPT generiert das Gutachten als JSON:

```json
{
  "executive_summary": "...",
  "gesamtbewertung": "teilweise erfüllt",
  "framework_bewertungen": [
    {
      "framework": "DORA",
      "erfuellungsgrad": 72,
      "staerken": ["..."],
      "schwaechen": ["..."],
      "empfehlungen": ["..."]
    }
  ],
  "kritische_findings": ["..."],
  "massnahmenplan": ["..."]
}
```

5. JSON in Antwortdatei speichern
6. **Gutachten importieren** klicken

## Schritt 9: Word-Gutachten exportieren

1. **Gutachten exportieren (Word)** klicken
2. DOCX wird erstellt: `out/gutachten/gutachten/<projektname>_<timestamp>.docx`

Das DOCX enthält:
- **Deckblatt** mit Projektname, Frameworks, Datum, Prüfer
- **Executive Summary**
- **Framework-Kapitel** mit Erfüllungsgrad, Stärken, Schwächen, Empfehlungen
- **Interviewtabelle** (alle Fragen, Antworten, Bewertungen)
- **Maßnahmenplan**
- **Quellenverzeichnis** (Regulatorik-Verweise)

## Bewertungsskala

| Bewertung | Bedeutung |
|---|---|
| **erfüllt** | Anforderung vollständig umgesetzt |
| **teilweise erfüllt** | Anforderung überwiegend umgesetzt, Lücken vorhanden |
| **nicht erfüllt** | Anforderung nicht oder kaum umgesetzt |
| **nicht anwendbar** | Anforderung trifft auf die Organisation nicht zu |
