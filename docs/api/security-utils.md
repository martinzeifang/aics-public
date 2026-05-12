# security_utils – Sicherheits-Utilities

`security_utils.py` (Projektstamm) ist die zentrale Sicherheitsbibliothek. Sie wird von allen Modulen importiert und schützt vor den häufigsten Angriffsvektoren bei der Verarbeitung von Office-Dokumenten und Benutzereingaben.

## Importieren

```python
from security_utils import (
    workspace_root_from,
    ensure_within_root,
    safe_generated_file,
    safe_generated_dir,
    iter_safe_generated_files,
    validate_office_archive,
    sanitize_untrusted_text,
)
```

---

## Funktionen

### `workspace_root_from`

```python
def workspace_root_from(anchor: Path) -> Path:
```

Ermittelt das Projektstammverzeichnis ausgehend von einer Ankerdatei (z.B. `__file__` eines Moduls).

**Parameter:**
- `anchor` – Startpfad für die Suche (z.B. `Path(__file__)`)

**Rückgabe:** Absoluter Pfad zum Projektstamm

---

### `ensure_within_root`

```python
def ensure_within_root(path: Path, root: Path) -> Path:
```

Stellt sicher, dass ein Pfad innerhalb des Projektstamms liegt. Verhindert **Path-Traversal-Angriffe**.

**Parameter:**
- `path` – Zu prüfender Pfad
- `root` – Erlaubtes Stammverzeichnis

**Rückgabe:** Kanonisierter absoluter Pfad

**Wirft:** `ValueError` wenn der Pfad außerhalb von `root` liegt

```python
# Beispiel
root = workspace_root_from(Path(__file__))
safe = ensure_within_root(Path("../../etc/passwd"), root)
# → ValueError: Path traversal attempt detected
```

---

### `safe_generated_file`

```python
def safe_generated_file(path: Path, root: Path) -> Path:
```

Kombiniert `ensure_within_root` mit Elternverzeichnis-Erstellung für Ausgabedateien.

**Anwendungsfall:** Vor dem Schreiben generierter Dateien (Prompts, befüllte XLSX).

---

### `safe_generated_dir`

```python
def safe_generated_dir(path: Path, root: Path) -> Path:
```

Wie `safe_generated_file`, aber für Verzeichnisse. Erstellt das Verzeichnis wenn nötig.

---

### `iter_safe_generated_files`

```python
def iter_safe_generated_files(
    dir_path: Path,
    pattern: str,
    root: Path,
    allowed_suffixes: set[str],
) -> list[Path]:
```

Iteriert sicher über Dateien in einem Verzeichnis:

- Prüft jede Datei auf Path-Containment
- Filtert auf erlaubte Dateiendungen
- Gibt sortierte Liste zurück

**Parameter:**
- `dir_path` – Zu durchsuchendes Verzeichnis
- `pattern` – Glob-Pattern (z.B. `"*.xlsx"`)
- `root` – Projektstammverzeichnis
- `allowed_suffixes` – Erlaubte Endungen (z.B. `{".xlsx", ".XLSX"}`)

---

### `validate_office_archive`

```python
def validate_office_archive(path: Path, expected_suffix: str) -> None:
```

Validiert XLSX- und DOCX-Dateien vor dem Einlesen:

- Prüft ZIP-Signatur (Magic Bytes `PK\x03\x04`)
- Verhindert **Zip-Bomb-Angriffe** (max. 25 MB unkomprimiert)
- Prüft auf erwartete Office-Inhalte (`[Content_Types].xml`)
- Begrenzt Anzahl Dateien im Archiv

**Wirft:** `ValueError` bei ungültiger Struktur

```python
# Beispiel
validate_office_archive(Path("fragebogen.xlsx"), ".xlsx")
validate_office_archive(Path("bericht.docx"), ".docx")
```

---

### `sanitize_untrusted_text`

```python
def sanitize_untrusted_text(value: str, max_len: int = 10_000) -> str:
```

Bereinigt Text aus nicht vertrauenswürdigen Quellen:

- Entfernt Null-Bytes (`\x00`)
- Normalisiert Zeilenenden (CRLF → LF)
- Filtert Steuerzeichen (außer Tab und Newline)
- Beschränkt auf `max_len` Zeichen

**Anwendungsfall:** Text aus XLSX-Zellen, DOCX-Absätzen, PDF-Extraktion.

---

## Input-Validierung (OWASP-PC-C5)

Zusätzlich zu den Pfad-/Office-Validierungen in `security_utils.py` gibt es zentrale Validierungs-Utilities für typische GUI/CLI-Eingaben:

- `shared/validation.py`
  - `normalize_repo(provider, repo)`
  - `validate_branch_ref(branch)`
  - `validate_http_url(url)`
  - `validate_env_var_name(name)`

Diese Funktionen werden u.a. für Repo/Branch/URL/Env-Eingaben in CRA/Issue-Flow genutzt, um fehlerhafte oder missbräuchliche Eingaben früh abzuweisen.

---

## Output-Encoding / Escaping (OWASP-PC-C4)

Für Exporte und Prompt-Dateien werden kontextabhängige Escaping-Funktionen genutzt:

- `shared/encoding.py`
  - `escape_csv_cell(...)`: Schutz vor CSV/Excel Formula-Injection
  - `escape_markdown_codeblock(...)`: verhindert Ausbrechen aus Markdown-Codefences

`security_utils.add_untrusted_block()` nutzt `escape_markdown_codeblock()`, damit untrusted Text in Prompts nicht die Markdown-Struktur manipuliert.

---

## Sicherheitslimits

| Ressource | Limit |
|---|---|
| XLSX: maximale Zeilenzahl | 10.000 |
| XLSX: maximale Spaltenzahl | 200 |
| DOCX: maximale Absatzzahl | 10.000 |
| Office-Archiv: unkomprimierte Größe | 25 MB |
| `sanitize_untrusted_text`: max. Textlänge | 10.000 Zeichen (Standard) |

---

## Schutzmaßnahmen im Überblick

| Bedrohung | Gegenmaßnahme |
|---|---|
| **Path Traversal** | `ensure_within_root()` validiert jeden Pfad |
| **Zip Bombs** | `validate_office_archive()` prüft unkomprimierte Größe |
| **Schadhafte Office-Dateien** | Magic-Byte-Check + Content-Type-Validierung |
| **Injection über Zellinhalte** | `sanitize_untrusted_text()` filtert Steuerzeichen |
| **Übermäßiger Speicherverbrauch** | Row/Column/Paragraph-Limits bei XLSX/DOCX |
