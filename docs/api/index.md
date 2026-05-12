# API-Referenz

Diese Sektion dokumentiert die internen Python-APIs der AI Compliance Suite für Entwickler, die Module programmatisch nutzen oder erweitern möchten.

## Modulübersicht

| Modul | Kernklassen | Kernfunktionen |
|---|---|---|
| `shared/config_io` | – | `safe_load_json_config`, `safe_save_json_config` |
| `shared/db_security` | – | `connect_sqlite` |
| `shared/fs_perms` | – | `ensure_private_dir`, `ensure_private_file`, `ensure_private_dirs` |
| `shared/json_io` | – | `safe_json_loads`, `require_object`, `require_array` |
| `shared/net_validation` | – | `enforce_loopback_base_url` |
| `shared/redaction` | – | `redact_secrets` |
| `shared/crypto_at_rest` | – | `encrypt_file`, `decrypt_file`, `is_encrypted` |
| `shared/audit` | – | `add_audit_event`, `get_audit_log`, `AuditEvent` |
| `shared/integrity` | – | `IntegrityManifest.write`, `IntegrityManifest.verify` |
| `security_utils` | – | `workspace_root_from`, `ensure_within_root`, `safe_generated_file`, `sanitize_untrusted_text`, `validate_office_archive` |
| `baso.db` | – | `ensure_db`, `ingest_questionnaires`, `ingest_sikos`, `fetch_answered_items` |
| `baso.retrieval` | `Match` | `top_matches` |
| `ict.db` | – | `ensure_db`, `ingest_questionnaires`, `ingest_sikos`, `ingest_reports` |
| `compliance.risk_matrix` | – | `calculate_risk` |
| `compliance_db.retrieval` | `SearchHit` | `search`, `rebuild_index_from_gutachten`, `list_frameworks` |
| `compliance_db.local_llm` | `ContextItem`, `OllamaError` | `query_ollama` |
| `risikobewertung.frameworks` | – | `framework_felder`, `berechne_risiko` |

Detaillierte Dokumentation:

- [security_utils](security-utils.md) – Sicherheits-Utilities (Pfad-Containment, Office-Validierung)
- [config_io](config-io.md) – Sichere Konfigurations-I/O (atomisch, SHA-256, Audit)

---

## Dataclasses-Übersicht

### `baso.io_xlsx.XlsxItem`

```python
@dataclass(frozen=True)
class XlsxItem:
    file_name: str
    sheet_name: str
    row: int
    layout: str              # "system" | "service"
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

### `baso.io_docx.DocxParagraph`

```python
@dataclass(frozen=True)
class DocxParagraph:
    doc_name: str
    index: int
    text: str
```

### `baso.retrieval.Match`

```python
@dataclass(frozen=True)
class Match:
    score: float      # 0.0–100.0 (rapidfuzz token_set_ratio)
    payload: dict     # Originaldaten des Treffers
```

### `ict.io_xlsx.IctItem`

```python
@dataclass(frozen=True)
class IctItem:
    file_name: str
    sheet_name: str
    row: int
    question_id: str
    title: str
    question: str
    answer: str | None      # "Ja" | "Nein"
    maturity: int | None    # 1–4
    explanation: str | None
    guidance: str | None
    optimization_potential: str | None
```

### `compliance_db.retrieval.SearchHit`

```python
@dataclass
class SearchHit:
    rowid: int
    framework: str      # "DORA" | "NIS2" | "CRA" | ...
    doc_name: str
    section_ref: str    # z.B. "Art. 5 Abs. 2"
    title: str
    snippet: str        # FTS5 highlight snippet
    score: float        # BM25 score
```

### `compliance_db.local_llm.ContextItem`

```python
@dataclass
class ContextItem:
    framework: str
    doc_name: str
    section_ref: str
    title: str
    text: str           # Vollständiger Abschnittstext
```

### `gutachten.io_xlsx.ImportedQuestion`

```python
@dataclass
class ImportedQuestion:
    question_id: str
    framework: str
    section_ref: str
    title: str
    question: str
    answer: str | None
    bewertung: str | None    # "erfüllt" | "teilweise erfüllt" | ...
    bemerkung: str | None
```

---

## GUI-Modul-Interface

Alle Modul-Frames implementieren ein gemeinsames Interface:

```python
class ModuleFrame(ttk.Frame):
    def get_test_mode(self) -> bool: ...
    def set_test_mode(self, value: bool) -> None: ...
    def get_debug_mode(self) -> bool: ...
    def set_debug_mode(self, value: bool) -> None: ...
    def get_debug_log_path(self) -> Path: ...
    def open_project_settings(self) -> None: ...
    def open_prompt_settings(self) -> None: ...
```

Der Suite-Launcher (`ai_compliance_suite/gui.py`) ruft diese Methoden auf, um Module einheitlich zu steuern.

---

## Fehlerbehandlung

| Exception | Modul | Auslöser |
|---|---|---|
| `OllamaError` | `compliance_db.local_llm` | Ollama nicht erreichbar, Modell nicht gefunden (HTTP 404) |
| `ValueError` | `security_utils` | Path-Traversal-Versuch |
| `ValueError` | `security_utils` | Datei zu groß oder ungültige Office-Struktur |
| `sqlite3.Error` | alle DB-Module | Datenbankfehler |
