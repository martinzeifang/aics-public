# Security Tooling & Dependency Management

Dieses Dokument beschreibt die Sicherheits-Tooling-Baseline der AI Compliance Suite.

> Hinweis: Technische Guidance, keine Rechtsberatung.

## 1) Dependency Updates

**Dependabot** ist aktiviert:

- Konfiguration: `.github/dependabot.yml`
- Aktualisierungsintervall: wöchentlich
- Ziel: zeitnahe Updates für direkte und indirekte Python-Abhängigkeiten

## 2) Vulnerability Scanning

Für CRA/AI-Act existieren CI-Workflows, die Dependencies scannen und Artefakte erzeugen:

- OSV-Scanner + pip-audit:
  - CRA: `.github/workflows/cra-osv-scan.yml`
  - AI Act: `.github/workflows/ai-act-osv-scan.yml`

Die Scans schlagen fehl, wenn bekannte Schwachstellen gefunden werden ("fail the build").

## 3) SBOM

SBOMs werden in CI erzeugt (CycloneDX/SPDX, je Workflow):

- CRA: `.github/workflows/cra-sbom.yml`
- AI Act: `.github/workflows/ai-act-sbom.yml`

## 4) Sicherheitsarchitektur (Überblick)

Die Sicherheitshärtung folgt dem **Defense-in-Depth**-Ansatz und deckt folgende Bereiche ab:

| Bereich | Module | Beschreibung |
|---|---|---|
| **Config-I/O** | `shared/config_io.py` | Atomisches Schreiben, restriktive Permissions (0600), SHA-256-Sidecar, Audit-Events |
| **Dateisystem-Permissions** | `shared/fs_perms.py` | `ensure_private_dir` (0700), `ensure_private_file` (0600), `ensure_private_dirs` |
| **DB-Zugriff** | `shared/db_security.py` | Workspace-Path-Containment, POSIX-Permissions, Audit |
| **Runtime-Integrität** | `shared/integrity.py` | SHA-256-Manifest beim Suite-Start; optional fail-closed |
| **JSON-Importe** | `shared/json_io.py` | Größenbegrenzung (10 MB), Fence-Stripping, Audit |
| **Netzwerk-Härtung** | `shared/net_validation.py` | Loopback-Guard, Cloud-Egress-Gate, HTTPS-only |
| **Secret-Redaktion** | `shared/redaction.py` | Best-Effort-Redaktion von API-Keys, Tokens |
| **At-Rest-Verschlüsselung** | `shared/crypto_at_rest.py` | Fernet-basiert für Backups/Evidence; optional |
| **Audit-Logging** | `shared/audit.py` | Strukturierte Audit-Events für sicherheitsrelevante Aktionen |
| **Office-Validierung** | `security_utils.py` | Zip-Bomb-Erkennung, Magic-Bytes, Path-Containment |
| **Input-Validierung** | `shared/validation.py` | Repo/Branch/URL/Env-Namen |
| **Output-Encoding** | `shared/encoding.py` | CSV-Formula-Injection-Schutz, Markdown-Escaping |
| **Fehlerbehandlung** | `shared/errors.py` | Globales Tkinter-Exception-Handling |

## 5) Zentrale Sicherheitsfunktionen im Detail

### 5.1 Config-I/O (`shared/config_io`)

- `safe_load_json_config()` / `safe_save_json_config()` – atomisches Schreiben mit umask(077), chmod(0600)
- **SHA-256 Sidecar**: Jede Config-Datei erhält eine `.sha256`-Datei; Mismatch -> Fehler beim Laden
- **Auto-Fix**: Unsichere Permissions werden beim Laden korrigiert (außer bei `AICS_CONFIG_ENFORCE_PERMS=1`)
- **Audit**: `config.load` / `config.save` mit Pfad und SHA-256
- Alle Modul-Configs auf `safe_load_json_config`/`safe_save_json_config` umgestellt

[API-Referenz](../api/config-io.md)

### 5.2 Dateisystem-Permissions (`shared/fs_perms`)

- `ensure_private_dir(path)` – Verzeichnis mit 0700 (owner-only)
- `ensure_private_file(path)` – 0600 auf bestehende Datei
- `ensure_private_dirs(paths)` – Bulk-Version
- Aufruf beim Suite-Start für `data/`, `data/db/`, `data/evidence/`, `out/`, `logs/`

### 5.3 DB-Sicherheit (`shared/db_security`)

- `connect_sqlite(db_path, workspace_root)` – Guards:
  - **Path Containment**: DB-Pfad innerhalb `workspace_root`
  - **POSIX Permissions**: dir 0700, file 0600, umask(077)
  - **Audit**: `db.open`
- Alle Modul-DBs umgestellt (12 Dateien)

### 5.4 Runtime-Integrität (`shared/integrity`)

- Manifest `.integrity.manifest.json` mit SHA-256-Hashes
- `python -m shared.integrity --write` / `--verify`
- Automatische Prüfung beim Suite-Start
- Fail-closed optional: `AICS_INTEGRITY_ENFORCE=1`

[Detaildokumentation](integrity-check.md)

### 5.5 JSON-Importe (`shared/json_io`)

- `safe_json_loads(data, max_size=10_000_000)` – Größenlimit, BOM/Fence-Stripping, Audit
- `require_object` / `require_array` – Typprüfung
- Umstellung in `risikobewertung/prompts.py`, `compliance/gui_module.py`, `gutachten/gui_module.py`, `vcs/issue_assistant.py`

### 5.6 Netzwerk-Härtung (`shared/net_validation`)

- **Loopback-Guard**: `enforce_loopback_base_url()` blockiert nicht-Loopback
  - Erlaubt: `localhost`, `127.0.0.1`, `::1`
  - Override: `on_prem.allow_nonlocal_base_url` oder `AICS_ALLOW_NONLOCAL_LLM=1`
- **Cloud-Egress-Gate**: `ai.cloud.allow_data_egress = true`, HTTPS-only, Redaktion, Audit

### 5.7 Secret-Redaktion (`shared/redaction`)

- `redact_secrets(text)` – erkennt: `ghp_*`, `github_pat_*`, `glpat-*`, `sk-*`, Bearer-Tokens, Hex >=64
- Angewendet in Risikobewertung Issue Sync und Cloud-Provider

### 5.8 At-Rest-Verschlüsselung (`shared/crypto_at_rest`, optional)

- Fernet (AES-128-CBC + HMAC-SHA256), Format `AICSENC1 || salt(16) || token`
- Backup-Archive: `backup_*.zip` -> `*.zip.enc`
- Evidence-Dateien: `*.enc` im Store
- Key per Env `AICS_AT_REST_KEY`, Config `security.at_rest_encryption.enabled`
- Kein Live-SQLite-Schutz (SQLCipher nicht als Dependency)

[Detaildokumentation](at-rest-encryption.md)

### 5.9 Audit-Logging (`shared/audit`)

| Kategorie | Events |
|---|---|
| Config | `config.load`, `config.save` |
| DB | `db.open` |
| Export | `export.write` |
| JSON | `json.load` |
| KI (Cloud) | `ai.cloud.request` |
| KI (On-Prem) | `ai.on_prem.request` |
| Integrity | `integrity.manifest.write`, `integrity.check` |
| Daten | `data.change` (Change Log) |
| Risiko | `risk.update_from_issue` |

Audit-Log-Viewer in Suite-GUI: `Datei -> Audit-Log anzeigen`

### 5.10 Office-Validierung (`security_utils`)

- `validate_office_archive()` – ZIP-Signatur, 25 MB Limit, `[Content_Types].xml`
- `sanitize_untrusted_text()` – Null-Bytes entfernen, Steuerzeichen filtern
- `ensure_within_root()` – Path-Containment
- `add_untrusted_block()` – `BEGIN_UNTRUSTED_DATA`/`END_UNTRUSTED_DATA`-Marker in Prompts

## 6) Export-Härtung

Alle Exporte nutzen `safe_generated_file()`: Path-Containment + Permissions (0600) + Audit `export.write`.

Betroffen: `baso/ict/cra/dsgvo/nis2/risikobewertung/gutachten/io_xlsx.py`, `shared/db_viewer.py`.

## 7) Mandantentrennung (Tenant Scoping)

Nachweisbibliothek (`evidence/`) mit `kunden_id`-Dropdown; "(Alle)" nur nach Bestätigung.

## 8) Sicherheitslimits

| Ressource | Limit | Gegenmaßnahme |
|---|---|---|
| XLSX: Zeilen | 10.000 | `io_xlsx`-Limits |
| XLSX: Spalten | 200 | `io_xlsx`-Limits |
| DOCX: Absätze | 10.000 | `io_docx`-Limits |
| Office-Archiv | 25 MB | `validate_office_archive` |
| Text (untrusted) | 10.000 Zeichen | `sanitize_untrusted_text` |
| PDF-Größe | 25 MB | `evidence/extract.py` |
| PDF-Seiten | 500 | `evidence/extract.py` |
| JSON-Import | 10 MB | `safe_json_loads` |