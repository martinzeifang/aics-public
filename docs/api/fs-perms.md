# Dateisystem-Permissions (`shared.fs_perms`)

Setzt restriktive Datei- und Verzeichnisrechte (POSIX) für die Datenhaltung der Suite.

## Funktionen

### `ensure_private_dir`

```python
def ensure_private_dir(path: Path, mode: int = 0o700) -> Path:
```

Erstellt ein Verzeichnis mit Owner-only-Zugriff (0700). Existiert das Verzeichnis bereits, werden die Rechte korrigiert.

### `ensure_private_file`

```python
def ensure_private_file(path: Path, mode: int = 0o600) -> Path:
```

Setzt die Rechte einer Datei auf Owner-only (0600).

### `ensure_private_dirs`

```python
def ensure_private_dirs(paths: list[Path], mode: int = 0o700) -> None:
```

Bulk-Version von `ensure_private_dir` für mehrere Pfade.

## Verwendung

Wird beim Suite-Start aufgerufen:

```python
from shared.fs_perms import ensure_private_dirs
ensure_private_dirs([data_dir, db_dir, evidence_dir, out_dir, logs_dir])
```

## Hinweise

- Auf Windows haben POSIX-Permissions keine direkte Entsprechung; dort ist die Umsetzung „best effort".
- Die Funktionen verwenden `path.chmod()` und fangen `PermissionError` – kein Fail-Closed bei nicht setzbaren Rechten.
