# Compliance-DB (RAG-Suche)

Das Compliance-DB-Modul bietet eine lokale Wissenssuche über Regulatorik-Dokumente mit Retrieval-Augmented Generation (RAG). Es kombiniert SQLite FTS5-Volltextsuche mit einem lokalen Ollama-LLM.

## Verzeichnisstruktur

```
compliance_db/
├── __init__.py
├── __main__.py
├── config.py            # Ollama-Einstellungen
├── retrieval.py         # FTS5-Suche + Kompositazerlegung
├── local_llm.py         # Ollama HTTP-Client
└── gui_module.py        # Tkinter-GUI (ComplianceDBModuleFrame)
```

## Konfiguration

Datei: `compliance_db.config.json`

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `paths.gutachten_db_path` | `data/db/gutachten.sqlite` | Quelldatenbank (Gutachten-Inhalte) |
| `paths.index_db_path` | `data/db/compliance_db.sqlite` | FTS5-Suchindex |
| `llm.provider` | `"ollama"` | LLM-Provider |
| `llm.base_url` | `http://localhost:11434` | Ollama API-Endpunkt |
| `llm.model` | `"llama3.1"` | Ollama-Modell |
| `llm.timeout_s` | `120` | HTTP-Timeout in Sekunden |
| `llm.top_k` | `8` | Anzahl Suchergebnisse als Kontext |

## Datenfluss (RAG-Pipeline)

```
gutachten.sqlite (Abschnitte)
         │
         ▼
  rebuild_index_from_gutachten()
         │
         ▼
compliance_db.sqlite (FTS5)
         │
  Benutzeranfrage
         │
         ▼
    _tokenize()
         │
         ▼
  _build_fts_queries()
    ┌────┴────┐
    │         │
  Strict    Expanded
   AND      Compounds
    └────┬────┘
         │
         ▼
   FTS5 BM25-Ranking
         │
         ▼
   Top-K SearchHits
         │
         ▼
  Ollama (llama3.1)
         │
         ▼
   Strukturierte Antwort
```

## Suchalgorithmus

`compliance_db/retrieval.py`

### Tokenisierung

```python
def _tokenize(user_q: str) -> list[str]:
    # Kleinschreibung, Satzzeichen entfernen, Stopwörter filtern
    # Gibt bedeutungsträgende Tokens zurück
```

### Kompositazerlegung (Deutsch)

```python
def _expand_compound(tok: str) -> list[str]:
    # Erkennt Fugen-s: "Datenschutzbeauftragter" → ["Datenschutz", "beauftragter"]
    # Erkennt Doppel-s: "Risikomanagement" → ["Risiko", "management"]
    # Gibt Teile des Kompositums zurück
```

### Suchreihenfolge

1. **Strict AND**: Alle Tokens müssen vorkommen → höchste Präzision
2. **Expanded Compounds**: Komposita zerlegt → bessere Abdeckung
3. **OR Fallback**: Mindestens ein Token → maximale Trefferquote

### SearchHit

```python
@dataclass
class SearchHit:
    rowid: int
    framework: str       # z.B. "DORA", "NIS2"
    doc_name: str        # Dokumentname
    section_ref: str     # z.B. "Art. 5 Abs. 2"
    title: str
    snippet: str         # FTS5-generierter Snippet
    score: float         # BM25-Score
```

## Ollama-Integration

`compliance_db/local_llm.py`

```python
class OllamaError(RuntimeError):
    """Wird bei Ollama API-Fehlern ausgelöst."""

@dataclass
class ContextItem:
    framework: str
    doc_name: str
    section_ref: str
    title: str
    text: str
```

Der Ollama-Client sendet die Top-K-Suchergebnisse als Kontext an das LLM und erhält eine strukturierte, quellenbasierte Antwort.

## Voraussetzungen

Ollama muss auf dem lokalen System installiert und das Modell heruntergeladen sein:

```bash
# Ollama installieren (Windows)
install-ollama.bat

# Ollama installieren (Linux)
./install-ollama.sh

# Modell herunterladen
ollama pull llama3.1
```

## Indexaufbau

Der Index wird aus `gutachten.sqlite` befüllt, d.h. die Gutachten-Frameworks (DORA, NIS2, CRA, etc.) müssen vorher heruntergeladen und eingelesen worden sein:

1. Im Gutachten-Modul: Framework-Dokumente herunterladen
2. Im Compliance-DB-Modul: **Index neu aufbauen**

## API-Referenz

| Funktion | Signatur | Beschreibung |
|---|---|---|
| `ensure_index_db` | `(index_db: Path) -> None` | Erstellt FTS5-Schema |
| `rebuild_index_from_gutachten` | `(gutachten_db, index_db, progress) -> None` | Befüllt FTS5-Index |
| `search` | `(index_db, query, frameworks, limit) -> tuple[list[SearchHit], str]` | Suche + Strategiebeschreibung |
| `fetch_text` | `(index_db, rowid) -> str` | Volltext eines Treffers |
| `list_frameworks` | `(index_db) -> list[str]` | Verfügbare Frameworks |
