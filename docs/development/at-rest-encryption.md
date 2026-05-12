# At-Rest Encryption (optional)

## Ziel

Schutz lokaler Artefakte **im Ruhezustand** (Backups und Evidence-Dateien) gegen unautorisierten Dateisystemzugriff.

## Umfang / Grenzen

- Unterstützt:
  - **Backup-Archive** (`out/backup/backup_*.zip`) → optional als `*.zip.enc`
  - **Evidence Store Dateien** (`data/evidence/*`) → optional als `*.enc`
- **Nicht** unterstützt (derzeit):
  - Verschlüsselung der **laufenden SQLite DB-Dateien** (`data/db/*.sqlite`) – hierfür wäre SQLCipher/SEE erforderlich.

## Konfiguration

In `ai_compliance_suite.config.json`:

```json
{
  "security": {
    "at_rest_encryption": {
      "enabled": true,
      "key_env": "AICS_AT_REST_KEY",
      "encrypt_backups": true,
      "encrypt_evidence": false
    }
  }
}
```

Key über Environment Variable:

```bash
export AICS_AT_REST_KEY='eine-lange-passphrase'
```

## Betrieb

- Backups werden nach dem Erstellen verschlüsselt und als `backup_*.zip.enc` abgelegt.
- Restore/Validate unterstützt `*.zip.enc` automatisch (Key erforderlich).
- Evidence-Dateien werden beim Hinzufügen in die Bibliothek (copy_into_store) optional verschlüsselt gespeichert.

## Security Notes

- Der Key darf **nicht** in Konfig-Dateien/Repos gespeichert werden.
- Empfehlung: zusätzlich **Full Disk Encryption** (BitLocker/FileVault/LUKS).
