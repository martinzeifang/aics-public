# Datenbankschemas

Alle Datenbanken sind SQLite-Dateien im Verzeichnis `data/db/`. WAL-Modus und 64-MB-Cache sind für jede Verbindung aktiviert.

---

## baso.sqlite

Verwendet von: `baso/db.py`

### Tabelle: `qa_items`

Speichert eingelesene Fragebogen-Elemente aus bereits beantworteten BASO-Fragebögen.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `file_name` | TEXT NOT NULL | Dateiname der XLSX-Quelldatei |
| `sheet_name` | TEXT NOT NULL | Tabellenblatt-Name |
| `row_num` | INTEGER NOT NULL | Zeilennummer in der XLSX |
| `layout` | TEXT NOT NULL | `"system"` oder `"service"` |
| `title` | TEXT NOT NULL | Abschnittstitel |
| `question` | TEXT NOT NULL | Fragentext / Sollmaßnahme |
| `schutzziel` | TEXT | Schutzziel (Vertraulichkeit, Integrität, ...) |
| `status` | TEXT | Umsetzungsstatus |
| `answer` | TEXT | Gespeicherte Antwort |
| `baso_id` | TEXT | BASO-Identifikator |
| `created_at` | TEXT | Timestamp (ISO 8601) |

**Indizes:** `idx_qa_items_layout(layout)`, `idx_qa_items_file(file_name)`

### Tabelle: `siko_paragraphs`

Absätze aus Sicherheitskonzept-Dokumenten (DOCX).

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `doc_name` | TEXT NOT NULL | Dateiname des Siko-Dokuments |
| `para_index` | INTEGER NOT NULL | Position im Dokument |
| `text` | TEXT NOT NULL | Absatztext |

**Index:** `idx_siko_doc(doc_name)`

---

## ict.sqlite

Verwendet von: `ict/db.py`

### Tabelle: `ict_items`

ICT-Fragebogen-Elemente mit Reifegrad-Informationen.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `file_name` | TEXT NOT NULL | XLSX-Quelldatei |
| `sheet_name` | TEXT NOT NULL | Tabellenblatt |
| `row_num` | INTEGER NOT NULL | Zeilennummer |
| `question_id` | TEXT NOT NULL | ICT-Fragen-ID (z.B. `ICT-01.1`) |
| `title` | TEXT NOT NULL | Bereichstitel |
| `question` | TEXT NOT NULL | Fragentext |
| `answer` | TEXT | Antwort (`"Ja"` / `"Nein"`) |
| `maturity` | INTEGER | Reifegrad 1–4 |
| `explanation` | TEXT | Erläuterung zur Antwort |
| `guidance` | TEXT | Hinweistext aus dem Fragebogen |
| `optimization_potential` | TEXT | Verbesserungspotenzial |
| `created_at` | TEXT | Timestamp |

**Indizes:** `idx_ict_items_file(file_name)`, `idx_ict_items_qid(question_id)`

### Tabelle: `ict_report_paragraphs`

Absätze aus ICT-Prüfberichten.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `file_name` | TEXT NOT NULL | Berichtsdatei |
| `para_index` | INTEGER NOT NULL | Position |
| `text` | TEXT NOT NULL | Absatztext |

### Tabelle: `siko_paragraphs`

Identisch mit `baso.sqlite.siko_paragraphs`.

---

## compliance.sqlite

Verwendet von: `compliance/db.py`

### Tabelle: `compliance_reports`

Eingelesene Quartalsberichte.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `file_name` | TEXT NOT NULL | DOCX-Dateiname |
| `text` | TEXT NOT NULL | Volltext des Berichts |
| `created_at` | TEXT | Timestamp |

### Tabelle: `compliance_report_paragraphs`

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `file_name` | TEXT NOT NULL | Quelldatei |
| `para_index` | INTEGER NOT NULL | Absatz-Index |
| `text` | TEXT NOT NULL | Absatztext |

### Tabelle: `compliance_siko_paragraphs`

Wie `baso.sqlite.siko_paragraphs`.

### Tabelle: `compliance_assessments`

Gespeicherte CVE-Risikobewertungen.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `answer_file` | TEXT | Zugehörige Antwortdatei |
| `hersteller` | TEXT | Betroffener Hersteller |
| `cve_nummern` | TEXT | CVE-Nummern (kommagetrennt) |
| `beschreibung_mitre` | TEXT | MITRE-Beschreibung der CVE |
| `datum` | TEXT | Bewertungsdatum |
| `zusammenfassung` | TEXT | KI-generierte Zusammenfassung |
| `stellungnahme` | TEXT | Detaillierte Stellungnahme |
| `eintrittswahrscheinlichkeit` | TEXT | Wahrscheinlichkeitswert |
| `schadenspotenzial` | TEXT | Schadenswert |
| `risikowert` | INTEGER | Berechneter Risikoscore |
| `quellen_json` | TEXT | Quellen als JSON-Array |
| `raw_json` | TEXT NOT NULL | Vollständige JSON-Antwort |
| `created_at` | TEXT | Timestamp |

**Indizes:** `idx_compliance_assessments_date(datum)`, `idx_compliance_assessments_cve(cve_nummern)`

---

## compliance_db.sqlite

Verwendet von: `compliance_db/retrieval.py`

### FTS5-Tabelle: `compliance_content`

Volltextsuchindex über alle Gutachten-Inhalte.

```sql
CREATE VIRTUAL TABLE compliance_content
USING fts5(
    source,       -- Quell-Framework-DB (Pfad)
    framework,    -- z.B. "DORA", "NIS2", "CRA"
    doc_name,     -- Dokumentname
    section_ref,  -- Abschnittsreferenz (z.B. "Art. 5")
    title,        -- Abschnittstitel
    text          -- Volltext des Abschnitts
);
```

**Ranking:** BM25 (eingebaut in FTS5), aufgerufen via `ORDER BY rank`

### Tabelle: `compliance_meta`

| Spalte | Typ | Beschreibung |
|---|---|---|
| `key` | TEXT PK | Schlüssel |
| `value` | TEXT | Wert (z.B. letzter Rebuild-Zeitstempel) |

---

## gutachten.sqlite

Verwendet von: `gutachten/db.py`

### Tabelle: `framework_documents`

Heruntergeladene oder importierte Regulatory-Dokumente.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `framework` | TEXT NOT NULL | Framework-Kürzel (`DORA`, `NIS2`, `CRA`, `ISO27001`, `DSGVO`, `AI_ACT`, `BSI`) |
| `doc_name` | TEXT NOT NULL | Dokumentname |
| `file_path` | TEXT | Lokaler Pfad |
| `source_url` | TEXT | Download-URL |
| `created_at` | TEXT | Timestamp |

### Tabelle: `framework_sections`

Extrahierte Abschnitte aus Regulatory-Dokumenten.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `doc_id` | INTEGER | FK → framework_documents.id |
| `framework` | TEXT NOT NULL | Framework-Kürzel |
| `section_ref` | TEXT | Abschnittsreferenz |
| `title` | TEXT | Abschnittstitel |
| `text` | TEXT NOT NULL | Abschnittstext |
| `page_num` | INTEGER | Seitenzahl im Quelldokument |

### Tabelle: `framework_metadata`

| Spalte | Typ | Beschreibung |
|---|---|---|
| `key` | TEXT PK | Schlüssel |
| `value` | TEXT | Wert |

---

## risikobewertung.sqlite

Verwendet von: `risikobewertung/db.py`

Speichert Risikobewertungen und deren Ergebnisse. Die genaue Schema-Definition liegt in `risikobewertung/db.py`.

---

## Verbindungseinstellungen

Alle Datenbankverbindungen werden mit folgenden Pragmas geöffnet:

```python
conn.execute("PRAGMA journal_mode=WAL")       # Write-Ahead Logging
conn.execute("PRAGMA synchronous=NORMAL")      # Schnellere Schreiboperationen
conn.execute("PRAGMA cache_size=-64000")       # 64 MB Cache
conn.execute("PRAGMA foreign_keys=ON")         # FK-Prüfung aktiviert
```
