# DB-Sicherheit (`shared.db_security`)

Schützt SQLite-Datenbanken vor unbefugtem Zugriff und Path-Traversal.

## Funktionen

### `connect_sqlite`

```python
def connect_sqlite(db_path: Path, workspace_root: Path) -> sqlite3.Connection:
```

Öffnet eine SQLite-Datenbank mit folgenden Sicherheitsmaßnahmen:

- **Path Containment**: Der DB-Pfad muss innerhalb von `workspace_root` liegen
- **POSIX Permissions**: Verzeichnis wird auf 0700, Datei auf 0600 gesetzt
- **umask(077)**: Verhindert zu freizügige Rechte bei neuerstellten Dateien
- **Audit**: Erzeugt Audit-Event `db.open`

**Parameter:**
- `db_path` – Pfad zur SQLite-Datenbank
- `workspace_root` – Projektstammverzeichnis (aus `workspace_root_from`)

**Wirft:** `ValueError` bei Path-Traversal, `PermissionError` bei fehlschlagender Berechtigungssetzung

## Verwendung

Alle Modul-DBs nutzen `connect_sqlite`:

```python
from shared.db_security import connect_sqlite
from security_utils import workspace_root_from

ROOT = workspace_root_from(Path(__file__))
conn = connect_sqlite(Path("data/db/baso.sqlite"), ROOT)
```

## Umgestellte Module

`dsgvo`, `nis2`, `ai_act`, `ict`, `baso`, `cra`, `risikobewertung`, `kunden`, `evidence`, `prefill`, `compliance_db`, `shared` – insgesamt 12 Datenbanken.

## Audit-Events

| Event | Details |
|---|---|
| `db.open` | DB-Pfad (innerhalb Workspace) |
