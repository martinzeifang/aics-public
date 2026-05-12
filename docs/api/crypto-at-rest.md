# At-Rest-Verschlüsselung (`shared.crypto_at_rest`)

Optionale Fernet-basierte Dateiverschlüsselung für Backups und Evidence-Dateien.

## Verfahren

- **Algorithmus**: AES-128-CBC + HMAC-SHA256 (Fernet)
- **Format**: `AICSENC1 || salt(16 Byte) || token` – pro Datei eindeutiger Salt
- **Schlüssel**: 32 Byte, URL-safe Base64-kodiert

## Funktionen

### `encrypt_file`

```python
def encrypt_file(input_path: Path, output_path: Path, key: bytes) -> None:
```

Verschlüsselt eine Datei. Überschreibt `output_path` falls vorhanden.

### `decrypt_file`

```python
def decrypt_file(input_path: Path, output_path: Path, key: bytes) -> None:
```

Entschlüsselt eine Datei. Prüft das `AICSENC1`-Header-Magic.

### `is_encrypted`

```python
def is_encrypted(path: Path) -> bool:
```

Prüft, ob eine Datei das `AICSENC1`-Header-Magic trägt (ohne zu entschlüsseln).

## Schlüsselverwaltung

Der Schlüssel wird **ausschließlich** über die Environment-Variable `AICS_AT_REST_KEY` bezogen:

```bash
export AICS_AT_REST_KEY='eine-lange-base64-passphrase'
```

**Nicht** in Konfigurationsdateien oder im Repository speichern!

## Konfiguration

```json
{
  "security": {
    "at_rest_encryption": {
      "enabled": true,
      "encrypt_backups": true,
      "encrypt_evidence": false
    }
  }
}
```

## Eingesetzt in

- `evidence/db.py` – Evidence-Dateien beim Hinzufügen in die Bibliothek
- Backup/Validate-Funktionen – Erkennung und Entschlüsselung von `*.zip.enc`

## Sicherheitshinweise

- Die Verschlüsselung schützt **nur im Ruhezustand** – nach dem Entschlüsseln liegt die Datei im Klartext vor
- Empfohlen wird zusätzlich **Full Disk Encryption** (BitLocker, FileVault, LUKS)
- Der Key-Verlust bedeutet **dauerhaften Datenverlust** – sichern Sie den Key separat
