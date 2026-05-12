# BASO Fragebogen-Modul

Das BASO-Modul unterstützt die Bearbeitung von BASO/ForumISM-Sicherheitsfragebögen im XLSX-Format. Es erkennt vorausgefüllte Fragebögen, baut daraus eine Wissensdatenbank auf und generiert KI-Prompts für neue Fragebögen.

## Verzeichnisstruktur

```
baso/
├── __init__.py
├── __main__.py          # Delegiert an cli.py
├── cli.py               # CLI-Einstiegspunkt (argparse)
├── config.py            # Konfigurationsmanagement
├── db.py                # SQLite-Schema + CRUD
├── io_xlsx.py           # XLSX lesen (2 Layouts)
├── io_docx.py           # DOCX-Sikos einlesen
├── prompts.py           # Prompt-Generierung
├── apply_answers.py     # JSON-Antworten in XLSX schreiben
├── retrieval.py         # Fuzzy-Matching
├── textnorm.py          # Textnormalisierung
├── gui_module.py        # Tkinter-GUI (BasoModuleFrame)
└── gui.py               # Legacy-Standalone-GUI
```

## Konfiguration

Datei: `baso.config.json` im Projektstamm

=== "Pfade"

    | Schlüssel | Standard | Beschreibung |
    |---|---|---|
    | `paths.source_dir` | `data/baso/quelle` | Bereits ausgefüllte Fragebögen |
    | `paths.new_dir` | `data/baso/neu` | Neue (leere) Fragebögen |
    | `paths.sikos_dir` | `data/shared/sikos` | Sicherheitskonzepte (DOCX) |
    | `paths.db_path` | `data/db/baso.sqlite` | SQLite-Datenbank |
    | `paths.prompts_dir` | `out/baso/prompts` | Erzeugte Prompt-Dateien |
    | `paths.answers_dir` | `out/baso/answers` | Abgelegte JSON-Antworten |
    | `paths.filled_dir` | `out/baso/filled` | Befüllte XLSX-Ausgabe |

=== "UI"

    | Schlüssel | Standard | Beschreibung |
    |---|---|---|
    | `ui.evaluated_by` | `"Martin Zeifang"` | Prüferkürzel in Ausgabedokumenten |
    | `ui.top_k` | `3` | Anzahl ähnlicher Beispiele im Prompt |
    | `ui.batch_size` | `20` | Fragen pro Prompt-Datei |
    | `ui.test_mode` | `false` | Beschränkt Verarbeitung auf wenige Elemente |
    | `ui.debug_mode` | `true` | Schreibt Debug-Log |

=== "Prompt"

    | Schlüssel | Beschreibung |
    |---|---|
    | `prompt.header` | Einleitungstext der Prompt-Dateien |
    | `prompt.style_system` | Anweisungstext für System-Layout |
    | `prompt.style_service` | Anweisungstext für Service-Layout |
    | `prompt.system_statuses` | Erlaubte Umsetzungsstatus-Werte |
    | `prompt.service_contract_values` | Erlaubte Vertragswerte (`Ja`, `Nein`, `Nicht anwendbar`) |

## XLSX-Layouts

Das Modul erkennt zwei unterschiedliche Fragebogen-Layouts:

### Layout "system" (Quelldateien aus `quelle/`)

| Spalte | Beschreibung |
|---|---|
| Titel | Abschnittsüberschrift |
| BASO-ID | Eindeutige Kennung der Anforderung |
| Frage / Sollmaßnahme | Fragentext |
| Schutzziel | Z.B. Vertraulichkeit, Integrität, Verfügbarkeit |
| Umsetzung | Status der Umsetzung |
| Bemerkung | Freitext-Anmerkungen |

### Layout "service" (Neue Dienstleistungsfragebögen aus `neu/`)

| Spalte | Beschreibung |
|---|---|
| Titel | Abschnittsüberschrift |
| Frage / Sollmaßnahme | Fragentext |
| Vertraglich zugesichert | `Ja` / `Nein` / `Nicht anwendbar` |
| Operativ umgesetzt | Umsetzungsstatus |
| Bemerkung | Freitext; Schutzziele werden hier eingetragen |

## Datenmodell

```python
@dataclass(frozen=True)
class XlsxItem:
    file_name: str
    sheet_name: str
    row: int
    layout: str              # "system" oder "service"
    title: str
    question: str
    schutzziel: str | None = None
    umsetzung: str | None = None
    bemerkung_umsetzung: str | None = None
    baso_id: str | None = None
    contract_assured: str | None = None
    ops_met: str | None = None
    bemerkung: str | None = None
```

## Datenbankfunktionen

`baso/db.py`

| Funktion | Beschreibung |
|---|---|
| `ensure_db(db_path)` | Erstellt Schema wenn nicht vorhanden |
| `ingest_questionnaires(source_dir, db_path, progress)` | Liest XLSX-Fragebögen ein |
| `ingest_sikos(sikos_dir, db_path, progress)` | Liest DOCX-Sikos ein |
| `fetch_answered_items(db_path, limit)` | Gibt beantwortete Elemente zurück |
| `fetch_siko_paragraphs(db_path, limit)` | Gibt Siko-Absätze zurück |

## Ähnlichkeitssuche

`baso/retrieval.py` + `baso/textnorm.py`

```python
def top_matches(
    query: str,
    candidates: list[dict],
    text_key: str,
    top_k: int = 5
) -> list[Match]:
    ...
```

Verwendet `rapidfuzz.fuzz.token_set_ratio` nach Textnormalisierung:
- Kleinschreibung
- Entfernung von Satzzeichen
- Kollabieren mehrfacher Leerzeichen

Der `token_set_ratio` ist reihenfolgeunabhängig und funktioniert auch bei Teilmengen-Ähnlichkeit.

## GUI (`BasoModuleFrame`)

Die Tkinter-Benutzeroberfläche bietet:

| Schaltfläche | Aktion |
|---|---|
| Fragebögen einlesen | `ingest_questionnaires()` |
| Sikos einlesen | `ingest_sikos()` |
| Prompts erstellen | Fuzzy-Match + Prompt-Generierung |
| Fragebögen befüllen | `apply_answers()` (grüner Button) |

Über **Bearbeiten** → Projekteinstellungen / Prompt-Einstellungen kann die Konfiguration direkt in der GUI angepasst werden.

## CLI

```bash
# Fragebögen einlesen
python -m baso ingest --source data/baso/quelle --db data/db/baso.sqlite

# Sikos einlesen
python -m baso ingest-sikos --sikos data/shared/sikos --db data/db/baso.sqlite

# Prompts erstellen
python -m baso prepare \
    --new data/baso/neu \
    --db data/db/baso.sqlite \
    --out out/baso/prompts \
    [--top 3] \
    [--batch-size 20] \
    [--answers-out out/baso/answers]

# Antworten eintragen
python -m baso apply \
    --new data/baso/neu \
    --answers out/baso/answers \
    --out out/baso/filled \
    [--by "Martin Zeifang"]

# GUI starten
python -m baso gui
```

## Sicherheitshinweise

- Maximale XLSX-Größe: 10.000 Zeilen, 200 Spalten, 25 MB
- Office-Dateien werden auf gültige ZIP-Struktur geprüft (Anti-Zip-Bomb)
- Pfade werden gegen das Workspace-Root validiert (kein Path-Traversal)
