# ICT Fragebogen-Modul

Das ICT-Modul verarbeitet ICT-Framework-Fragebögen mit Reifegradbewertungen (1–4). Der Workflow ist analog zu BASO, ergänzt um Reifegradlogik und die Einbindung von Prüfberichten.

## Verzeichnisstruktur

```
ict/
├── __init__.py
├── __main__.py
├── cli.py               # CLI-Einstiegspunkt
├── config.py            # Konfiguration inkl. Reifegrad-Skala
├── db.py                # SQLite-Schema + CRUD
├── io_xlsx.py           # XLSX lesen (Reifegrade)
├── prompts.py           # Prompt-Generierung mit Reifegradanweisungen
├── apply_answers.py     # Antworten + Reifegrade in XLSX schreiben
└── gui_module.py        # Tkinter-GUI (ICTModuleFrame)
```

## Konfiguration

Datei: `ict.config.json`

=== "Pfade"

    | Schlüssel | Standard | Beschreibung |
    |---|---|---|
    | `paths.source_dir` | `data/ict/quelle` | Ausgefüllte Fragebögen |
    | `paths.new_dir` | `data/ict/neu` | Neue Fragebögen |
    | `paths.sikos_dir` | `data/shared/sikos` | Sicherheitskonzepte |
    | `paths.reports_dir` | `data/ict/berichte` | ICT-Prüfberichte (DOCX) |
    | `paths.db_path` | `data/db/ict.sqlite` | Datenbank |
    | `paths.prompts_dir` | `out/ict/prompts` | Prompt-Ausgabe |
    | `paths.answers_dir` | `out/ict/answers` | Antwort-Eingabe |
    | `paths.filled_dir` | `out/ict/filled` | Befüllte XLSX |

=== "Prompt"

    | Schlüssel | Werte | Beschreibung |
    |---|---|---|
    | `prompt.answer_values` | `["Ja", "Nein"]` | Erlaubte Antwortwerte |
    | `prompt.maturity_values` | `[1, 2, 3, 4]` | Reifegrad-Skala |

## Reifegrad-Skala

| Reifegrad | Bedeutung |
|---|---|
| **1** | Initial / ad-hoc – keine formale Steuerung |
| **2** | Wiederholt – grundlegende Prozesse vorhanden |
| **3** | Definiert – dokumentierte, standardisierte Prozesse |
| **4** | Gemessen / Optimiert – kontinuierliche Verbesserung |

## Datenmodell

```python
@dataclass(frozen=True)
class IctItem:
    file_name: str
    sheet_name: str
    row: int
    question_id: str          # z.B. "ICT-01.1"
    title: str
    question: str
    answer: str | None        # "Ja" | "Nein"
    maturity: int | None      # 1-4
    explanation: str | None
    guidance: str | None
    optimization_potential: str | None
```

## Datenbankfunktionen

`ict/db.py`

| Funktion | Beschreibung |
|---|---|
| `ensure_db(db_path)` | Schema erstellen |
| `ingest_questionnaires(source_dir, db_path, progress)` | ICT-XLSX einlesen |
| `ingest_sikos(sikos_dir, db_path, progress)` | DOCX-Sikos einlesen |
| `ingest_reports(reports_dir, db_path, progress)` | Prüfberichte einlesen |
| `fetch_answered_items(db_path)` | Beantwortete Elemente laden |

## Besonderheiten gegenüber BASO

- **Prüfberichte**: ICT-Berichte (DOCX) werden zusätzlich zu Sikos in die DB eingelesen und als Kontext in Prompts eingebunden
- **Reifegrad**: Neben der Ja/Nein-Antwort wird ein Reifegrad 1–4 in den Prompt aufgenommen und in das XLSX zurückgeschrieben
- **Fragen-ID**: Jede Frage hat eine eindeutige ICT-ID (z.B. `ICT-01.1`), die zur Zuordnung beim Antwortimport genutzt wird

## CLI

```bash
# Fragebögen einlesen
python -m ict ingest --source data/ict/quelle --db data/db/ict.sqlite

# Sikos einlesen
python -m ict ingest-sikos --sikos data/shared/sikos --db data/db/ict.sqlite

# Prüfberichte einlesen
python -m ict ingest-reports --reports data/ict/berichte --db data/db/ict.sqlite

# Prompts erstellen
python -m ict prepare \
    --new data/ict/neu \
    --db data/db/ict.sqlite \
    --out out/ict/prompts \
    [--top 3] [--batch-size 20]

# Antworten eintragen
python -m ict apply \
    --new data/ict/neu \
    --answers out/ict/answers \
    --out out/ict/filled
```
