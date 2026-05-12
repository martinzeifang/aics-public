# ICT Workflow

Ablauf zur Bearbeitung eines ICT-Framework-Fragebogens mit Reifegradbewertung.

## Besonderheiten gegenüber BASO

- Jede Frage hat eine eindeutige **Fragen-ID** (z.B. `ICT-01.1`)
- Neben Ja/Nein-Antwort wird ein **Reifegrad 1–4** bewertet
- **Prüfberichte** (DOCX) können als zusätzlicher Kontext eingebunden werden
- Die Antwort-Zuordnung erfolgt über Fragen-ID (nicht über Zeilennummer)

## Schritt 1: Datenbank aufbauen

=== "GUI"

    1. Tab **ICT** in der Suite öffnen
    2. **ICT-Fragebögen einlesen**
    3. **Sikos einlesen**
    4. Optional: **Prüfberichte einlesen**

=== "CLI"

    ```bash
    python -m ict ingest \
        --source data/ict/quelle \
        --db data/db/ict.sqlite

    python -m ict ingest-sikos \
        --sikos data/shared/sikos \
        --db data/db/ict.sqlite

    # Optional: Prüfberichte
    python -m ict ingest-reports \
        --reports data/ict/berichte \
        --db data/db/ict.sqlite
    ```

## Schritt 2: Prompts erstellen

```bash
python -m ict prepare \
    --new data/ict/neu \
    --db data/db/ict.sqlite \
    --out out/ict/prompts \
    --answers-out out/ict/answers
```

Der Prompt enthält für jede Frage:
- Fragen-ID und Fragentext
- Top-K ähnliche Antworten aus der Datenbank
- Anweisung zur Reifegradbewertung (1–4)
- Erläuterung der Reifegrad-Skala

## Schritt 3–5: Wie BASO

Identisch zum [BASO Workflow](baso-workflow.md) (Schritte 3–5):

1. Prompt in ChatGPT einfügen
2. JSON-Antwort kopieren
3. In Antwortdatei speichern

## Schritt 6: Antworten eintragen

```bash
python -m ict apply \
    --new data/ict/neu \
    --answers out/ict/answers \
    --out out/ict/filled
```

Das `apply`-Skript schreibt zurück:
- Antwort (Ja/Nein)
- Reifegrad (1–4)
- Erläuterungstext
- Verbesserungspotenzial

Die Zuordnung erfolgt über die **Fragen-ID** – Zeilennummern spielen keine Rolle.

## JSON-Antwortformat

ChatGPT muss ein JSON-Array zurückgeben:

```json
[
  {
    "question_id": "ICT-01.1",
    "answer": "Ja",
    "maturity": 3,
    "explanation": "Die Maßnahme ist vollständig dokumentiert und regelmäßig geprüft.",
    "optimization_potential": "Automatisierung der jährlichen Überprüfung möglich."
  },
  {
    "question_id": "ICT-01.2",
    "answer": "Nein",
    "maturity": 1,
    "explanation": "Bisher keine formale Regelung vorhanden.",
    "optimization_potential": "Einführung einer Richtlinie empfohlen."
  }
]
```
