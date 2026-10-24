# Framework-Bibliothek

Pfad: **`/admin/frameworks`** (Permission `admin:config`)

Die Framework-Bibliothek ist die zentrale Verwaltung der **Regulierungstexte**,
auf deren Basis das **Gutachten-Modul** Interview-Fragen für ein Compliance-Audit
generiert.

## Workflow

```
                  ┌────────────────────────────────┐
                  │ /admin/frameworks              │
                  │                                │
                  │  Pro Framework:                │
                  │   ⬇️ Download (EUR-Lex / URL)  │
                  │   ⬆️ Manueller Upload          │
                  │   🗂️ Ingest in Sections-DB    │
                  └────────────────────────────────┘
                              │
                              ▼
                  ┌────────────────────────────────┐
                  │ data/<fw>_resources/*.pdf      │
                  └────────────────┬───────────────┘
                                   │ pdfplumber + Section-Splitter
                                   ▼
                  ┌────────────────────────────────┐
                  │ data/db/gutachten.sqlite       │
                  │   framework_sections           │
                  └────────────────┬───────────────┘
                                   │
                                   ▼
                  ┌────────────────────────────────┐
                  │ Gutachten-Modul                │
                  │  ChatGPT-Prompt-Generator      │
                  │  → Interview-Fragen            │
                  └────────────────────────────────┘
```

## Unterstützte Frameworks

| Framework  | Quelle                                    | CELEX(e)               | SPARQL-derived |
|---|---|---|---|
| **DORA**   | EUR-Lex (Publications Office)             | 32022R2554             | ✅ (alle Delegierten/Durchführungs-VOs) |
| **NIS2**   | EUR-Lex                                   | 32022L2555             | ❌ |
| **CRA**    | EUR-Lex                                   | 32024R2847             | ❌ |
| **DSGVO**  | EUR-Lex                                   | 32016R0679             | ❌ |
| **AI Act** | EUR-Lex                                   | 32024R1689             | ❌ |
| **BSI**    | bsi.bund.de (3 Direkt-URLs)               | —                      | ❌ |
| **ISO 27001** | Manueller Upload                       | —                      | ❌ |

### BSI-Quellen (Direkt-Download)

- BSI IT-Grundschutz Kompendium Edition 2023
- BSI-Standard 200-1 (ISMS)
- BSI-Standard 200-2 (IT-Grundschutz-Methodik)

## Aktionen

### ⬇️ Download

- **CELEX-basiert** (DORA/NIS2/CRA/DSGVO/AI Act): nutzt EUR-Lex SPARQL,
  resolves PDF-URL via `cdm:item_belongs_to_work`
- **Direkt-URL** (BSI): klassischer GET-Download
- Zielverzeichnis: `data/<fw>_resources/`
- **Force-Toggle**: vorhandene Datei überschreiben (sonst skip)

### ⬆️ Manueller Upload

- Multipart-Form, akzeptiert `.pdf` und `.xlsx`
- Speichert in `data/<fw>_resources/` mit safe_filename

### 🗂️ Ingest in DB

- Liest alle PDFs aus `data/<fw>_resources/` mit `pdfplumber`
- Splittet in Abschnitte (Artikel/Kapitel-Heuristik)
- Speichert in `gutachten.sqlite::framework_sections`:
  - `framework, doc_name, section_ref, title, text`
- Re-Ingest desselben Dokuments löscht alte Einträge

## API-Endpoints

| Endpoint                                       | Methode | Beschreibung |
|---|---|---|
| `GET /api/gutachten/frameworks`                | GET     | Status pro Framework (PDFs, Sections, CELEX) |
| `POST /api/gutachten/frameworks/<fw>/download` | POST    | Download via SPARQL/Direkt-URL. Body: `{force, lang}` |
| `POST /api/gutachten/frameworks/<fw>/ingest`   | POST    | Ingest aller PDFs aus `data/<fw>_resources/` |
| `POST /api/gutachten/frameworks/<fw>/upload`   | POST    | Multipart-Upload für ISO/BSI |

## Live-Status (Beispiel)

```
Framework  PDFs  Sections  CELEX            extra_resources
DORA         13       456  32022R2554       0  (+SPARQL-derived)
NIS2          2       227  32022L2555       0
CRA           1       184  32024R2847       0
DSGVO         1       213  32016R0679       0
AI_ACT        1       331  32024R1689       0
ISO27001      6       217  —                0  (manuell)
BSI           3       976  —                3  (Direkt-URLs)
```

## Logging

- Jeder Download/Ingest schreibt INFO-Zeilen in `logs/app.log`:
  `[<fw> download] Starte Download für DORA …`
- Im UI wird das Protokoll je Framework zusätzlich live angezeigt
  (klappbares Detail-Element)
