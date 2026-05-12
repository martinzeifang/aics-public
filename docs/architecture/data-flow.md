# Datenfluss

## BASO- und ICT-Workflow

```mermaid
sequenceDiagram
    participant User
    participant GUI
    participant DB as SQLite DB
    participant FS as Dateisystem
    participant GPT as ChatGPT (Web)

    User->>GUI: Fragebögen einlesen
    GUI->>FS: Liest XLSX aus data/baso/quelle/
    GUI->>DB: Speichert qa_items (Fragen + Antworten)

    User->>GUI: Sikos einlesen
    GUI->>FS: Liest DOCX aus data/shared/sikos/
    GUI->>DB: Speichert siko_paragraphs

    User->>GUI: Prompts erstellen
    GUI->>DB: Liest neue Fragebögen (data/baso/neu/)
    DB-->>GUI: Ähnliche Antworten (Fuzzy-Match)
    GUI->>FS: Schreibt .md Prompt-Dateien (out/baso/prompts/)
    GUI->>FS: Legt leere .json Antwortdateien an

    User->>GPT: Fügt Prompt ein
    GPT-->>User: JSON-Antwort
    User->>FS: Speichert JSON in out/baso/answers/

    User->>GUI: Fragebögen befüllen
    GUI->>FS: Liest JSON-Antworten
    GUI->>FS: Kopiert XLSX-Template
    GUI->>FS: Schreibt Antworten in XLSX (out/baso/filled/)
```

---

## Ähnlichkeitssuche (Retrieval)

Beim Erstellen von Prompts sucht das System nach ähnlichen, bereits beantworteten Fragen:

```mermaid
flowchart LR
    NF[Neue Frage] --> NRM[normalize_text]
    DB[(qa_items)] --> |alle Antworten| Cands[Kandidaten-Liste]
    Cands --> |normalize_text| NRM2[normalisiert]
    NRM --> FZ[rapidfuzz<br/>token_set_ratio]
    NRM2 --> FZ
    FZ --> |Top-K Matches| CTX[Kontext für Prompt]
    CTX --> PROMPT[Prompt-Datei .md]
```

`token_set_ratio` ist besonders geeignet für Fragebögen, da es unabhängig von Wortreihung und Teilmengen ähnliche Texte findet (z.B. "Verschlüsselung der Daten" vs. "Daten werden verschlüsselt").

---

## Compliance-DB: RAG-Pipeline

```mermaid
flowchart TB
    subgraph Indexierung
        GDB[(gutachten.sqlite)] --> RIB[rebuild_index_from_gutachten]
        RIB --> FTS[(compliance_db.sqlite<br/>FTS5 Index)]
    end

    subgraph Suche
        Q[Benutzeranfrage] --> TOK[_tokenize]
        TOK --> BFQ[_build_fts_queries]
        BFQ --> |Strict AND| FTS
        BFQ --> |Expanded Compounds| FTS
        BFQ --> |OR Fallback| FTS
        FTS --> |BM25 Ranking| HITS[SearchHit Liste]
        HITS --> OLLAMA[Ollama llama3.1]
        OLLAMA --> ANS[Strukturierte Antwort]
    end
```

### Deutsche Kompositazerlegung

Die FTS5-Suche behandelt deutschsprachige Komposita durch `_expand_compound()`:

- Erkennt Fugen-s: `Datenschutzbeauftragter` → `Datenschutz + beauftragter`
- Erkennt Doppel-s: `Risikomanagement` → `Risiko + management`
- Liefert mehrere Suchanfragen für bessere Trefferquote

---

## Gutachten-Workflow

```mermaid
sequenceDiagram
    participant User
    participant GUI as Gutachten GUI
    participant DL as file_download.py
    participant DB as gutachten.sqlite
    participant FS as Dateisystem
    participant GPT as ChatGPT

    User->>GUI: Framework wählen (z.B. DORA, NIS2)
    GUI->>DL: Framework-Dokumente herunterladen
    DL->>FS: PDFs speichern (data/dora_downloads/ etc.)
    GUI->>DB: PDFs einlesen + in DB speichern

    User->>GUI: Interviewfragen generieren
    GUI->>DB: Abschnitte laden
    GUI->>FS: Fragen-Prompt schreiben (out/gutachten/prompts/)
    User->>GPT: Prompt einfügen
    GPT-->>User: JSON-Array mit Fragen
    User->>GUI: JSON importieren
    GUI->>FS: Excel-Fragebogen exportieren (out/gutachten/fragebogen/)

    User->>FS: Fragebogen ausfüllen
    User->>GUI: Ausgefüllten Fragebogen importieren
    GUI->>DB: Antworten speichern

    User->>GUI: Gutachten erstellen
    GUI->>FS: Gutachten-Prompt schreiben
    User->>GPT: Prompt einfügen
    GPT-->>User: JSON-Gutachten
    User->>GUI: JSON importieren
    GUI->>FS: DOCX-Gutachten exportieren (out/gutachten/gutachten/)
```

---

## Risikobewertung-Workflow

```mermaid
flowchart TB
    USER[Benutzer] --> |Risiko beschreiben| GUI
    GUI --> |Prompt generieren| OLLAMA[Ollama llama3.1]
    OLLAMA --> |Strukturierter Risiko-Text| GUI

    GUI --> |Framework wählen| FW{Framework}
    FW --> FI[Financial Impact<br/>Wahrscheinlichkeit × Schaden]
    FW --> STRIDE[STRIDE<br/>6 Bedrohungskategorien]
    FW --> CVSS[CVSS<br/>Exploitability × Impact]
    FW --> OCTAVE[OCTAVE<br/>Akteur + Motiv + Zugang]

    FI --> |Score + Label| SCORE[Risiko-Score]
    STRIDE --> SCORE
    CVSS --> SCORE
    OCTAVE --> SCORE

    SCORE --> EXPORT{Export}
    EXPORT --> XLSX[Excel-Bericht]
    EXPORT --> DOCX[Word-Bericht]
    EXPORT --> JSON[JSON-Bericht]
```

---

## CRA-Workflow (CI Evidence + Auto-fill)

```mermaid
sequenceDiagram
    participant User
    participant CRA as CRA-Readiness GUI
    participant GH as GitHub Actions/Repo
    participant EV as evidence.sqlite

    User->>CRA: Linked App setzen (provider/repo/branch)
    User->>CRA: CI Evidenzen importieren
    CRA->>GH: gh run list/download (SBOM/OSV/Evidence Pack)
    CRA->>EV: Dokumente speichern + extract + chunk

    User->>CRA: CRA Auto-fill aus CI
    CRA->>EV: Chunks laden (citations)
    CRA-->>User: Prefill-Vorschläge (Review + Übernahme)
```

---

## Konfigurationsfluss

Jedes Modul lädt seine Konfiguration beim Start:

```mermaid
flowchart LR
    JSON[*.config.json] --> CFG[config.py<br/>load_config / save_config]
    CFG --> GUI[GUI-Modul]
    CFG --> CLI[CLI-Befehle]
    GUI --> |Benutzeränderungen| CFG
    CFG --> JSON
```

Die JSON-Dateien liegen im Projektstamm (z.B. `baso.config.json`) und werden beim ersten Start mit Standardwerten angelegt.
