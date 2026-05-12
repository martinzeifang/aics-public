# CLI-Referenz

Die AI Compliance Suite bietet für BASO und ICT vollständige Kommandozeilenschnittstellen. Die anderen Module sind primär über die GUI bedienbar, können aber auch programmatisch genutzt werden.

---

## Suite-Launcher

```bash
# Gesamte Suite (alle Module als Tabs)
python -m bnits_suite

# Alternativ (Windows)
start-suite.bat

# Alternativ (Linux/macOS)
./start-suite.sh
```

---

## BASO CLI

```bash
python -m baso <befehl> [optionen]
```

### `ingest` – Fragebögen einlesen

Liest ausgefüllte BASO-Fragebögen (XLSX) aus dem Quellverzeichnis in die Datenbank.

```bash
python -m baso ingest \
    --source <verzeichnis> \
    --db <pfad>
```

| Option | Pflicht | Beschreibung |
|---|---|---|
| `--source` | ✓ | Verzeichnis mit ausgefüllten XLSX-Fragebögen |
| `--db` | ✓ | Pfad zur SQLite-Datenbank |

**Beispiel:**
```bash
python -m baso ingest \
    --source data/baso/quelle \
    --db data/db/baso.sqlite
```

---

### `ingest-sikos` – Sicherheitskonzepte einlesen

Importiert Sicherheitskonzepte (DOCX) als Wissensquelle.

```bash
python -m baso ingest-sikos \
    --sikos <verzeichnis> \
    --db <pfad>
```

| Option | Pflicht | Beschreibung |
|---|---|---|
| `--sikos` | ✓ | Verzeichnis mit Sicherheitskonzept-DOCX |
| `--db` | ✓ | Pfad zur SQLite-Datenbank |

---

### `prepare` – Prompts erstellen

Generiert KI-Prompts für neue Fragebögen mit ähnlichen Beispielen aus der Datenbank.

```bash
python -m baso prepare \
    --new <verzeichnis> \
    --db <pfad> \
    --out <verzeichnis> \
    [--top <n>] \
    [--batch-size <n>] \
    [--answers-out <verzeichnis>]
```

| Option | Pflicht | Standard | Beschreibung |
|---|---|---|---|
| `--new` | ✓ | – | Verzeichnis mit neuen (leeren) Fragebögen |
| `--db` | ✓ | – | SQLite-Datenbank |
| `--out` | ✓ | – | Ausgabeverzeichnis für Prompt-Dateien (`.md`) |
| `--top` | – | `3` | Anzahl ähnlicher Beispiele im Prompt |
| `--batch-size` | – | `20` | Fragen pro Prompt-Datei |
| `--answers-out` | – | – | Verzeichnis für leere JSON-Antwortvorlagen |

**Ausgabe:**
- `out/baso/prompts/<dateiname>.part001.md`, `.part002.md`, ...
- `out/baso/answers/<dateiname>.part001.json` (leer, für ChatGPT-Antwort)

---

### `apply` – Antworten eintragen

Schreibt JSON-Antworten aus ChatGPT in die XLSX-Fragebögen zurück.

```bash
python -m baso apply \
    --new <verzeichnis> \
    --answers <verzeichnis> \
    --out <verzeichnis> \
    [--by <name>]
```

| Option | Pflicht | Standard | Beschreibung |
|---|---|---|---|
| `--new` | ✓ | – | Verzeichnis mit leeren Fragebögen (XLSX-Templates) |
| `--answers` | ✓ | – | Verzeichnis mit JSON-Antwortdateien |
| `--out` | ✓ | – | Ausgabeverzeichnis für befüllte XLSX |
| `--by` | – | `""` | Prüferkürzel für Bewertungs-Spalte |

---

### `gui` – Grafische Oberfläche

```bash
python -m baso gui
```

Startet das BASO-Modul als eigenständiges Fenster (ohne Suite-Launcher).

---

## ICT CLI

```bash
python -m ict <befehl> [optionen]
```

### `ingest`

```bash
python -m ict ingest \
    --source <verzeichnis> \
    --db <pfad>
```

### `ingest-sikos`

```bash
python -m ict ingest-sikos \
    --sikos <verzeichnis> \
    --db <pfad>
```

### `ingest-reports` – Prüfberichte einlesen

Importiert ICT-Prüfberichte (DOCX) als zusätzlichen Kontext.

```bash
python -m ict ingest-reports \
    --reports <verzeichnis> \
    --db <pfad>
```

### `prepare`

```bash
python -m ict prepare \
    --new <verzeichnis> \
    --db <pfad> \
    --out <verzeichnis> \
    [--top <n>] \
    [--batch-size <n>] \
    [--answers-out <verzeichnis>]
```

### `apply`

```bash
python -m ict apply \
    --new <verzeichnis> \
    --answers <verzeichnis> \
    --out <verzeichnis>
```

---

## Standalone-Module

Diese Module haben keinen vollständigen CLI, starten aber als eigenständige Fenster:

```bash
python -m compliance_db     # Compliance-DB RAG-Suche
python -m gutachten         # Gutachten-Modul
python -m risikobewertung   # Risikobewertung
```

---

## Vollständiger Workflow (BASO)

```bash
# 1. Datenbank aufbauen
python -m baso ingest --source data/baso/quelle --db data/db/baso.sqlite
python -m baso ingest-sikos --sikos data/shared/sikos --db data/db/baso.sqlite

# 2. Prompts erstellen
python -m baso prepare \
    --new data/baso/neu \
    --db data/db/baso.sqlite \
    --out out/baso/prompts \
    --answers-out out/baso/answers

# 3. Prompt in ChatGPT einfügen, JSON-Antwort in out/baso/answers/ speichern

# 4. Antworten eintragen
python -m baso apply \
    --new data/baso/neu \
    --answers out/baso/answers \
    --out out/baso/filled \
    --by "M. Zeifang"
```

---

!!! note "Hinweis zu ChatGPT"
    Die Suite nutzt **keinen offiziellen ChatGPT-API-Endpunkt**. Prompts werden manuell in ChatGPT Web eingefügt, die JSON-Antwort wird in die vorbereitete Antwortdatei kopiert. Dieses Design ermöglicht die Nutzung des ChatGPT Pro Web-Abonnements.
