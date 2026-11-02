# At-Rest-Verschlüsselung & Key-Handling (#1189)

Datenschutz by Design / ISO/IEC 27701, OWASP Secure-by-Design (sichere Defaults).

## Schlüssel

| Variable | Zweck | Pflicht |
|---|---|---|
| `JWT_SECRET_KEY` | Token-Signatur | immer |
| `AICS_AT_REST_KEY` | **separater** At-Rest-Schlüssel (Feld- + Datei-Verschlüsselung) | sobald Verschlüsselung aktiv |

`shared/crypto_at_rest.py` leitet per PBKDF2-HMAC-SHA256 (200 000 Iterationen, zufälliges
Salt je Wert) einen Fernet-Schlüssel ab. Ohne `AICS_AT_REST_KEY` fällt es auf
`JWT_SECRET_KEY` zurück — das **koppelt Signatur- und Verschlüsselungsschlüssel** und ist
für den Produktivbetrieb unerwünscht.

## Fail-closed-Startup-Guard

`server/app.py:_guard_at_rest_encryption` prüft beim Start: ist
`security.at_rest_encryption` aktiv (`enabled`/`encrypt_evidence`/`encrypt_backups`), aber
**kein** separater `AICS_AT_REST_KEY` gesetzt, dann:
- **Produktion** (`FLASK_ENV` ≠ development/testing): Start wird **abgebrochen** (RuntimeError).
- **Dev/Test**: nur Warnung im Log.

## Evidence-Datei-Verschlüsselung aktivieren

In `ai_compliance_suite.config.json`:
```json
"security": { "at_rest_encryption": {
  "enabled": true, "key_env": "AICS_AT_REST_KEY",
  "encrypt_backups": true, "encrypt_evidence": true
} }
```
Neue Evidence-Dateien werden dann verschlüsselt abgelegt (`*.enc`, Magic `AICSENC1`).
Bestehende Klartext-Dateien bleiben lesbar (transparente Migration: beim erneuten
Hochladen verschlüsselt). Feld-Secrets (TOTP, Tokens) nutzen denselben Schlüssel
(`AICSFLD1:`-Präfix) mit Klartext-Fallback für Alt-Werte.

## Restore & Rotation

- **Backup/Restore:** Verschlüsselte Dateien/Backups sind nur mit demselben
  `AICS_AT_REST_KEY` entschlüsselbar. Den Schlüssel **getrennt vom Backup** sichern
  (z. B. Secret-Manager). Restore = Volume zurückspielen + identischen Key bereitstellen.
- **Rotation:** Da das Salt pro Wert gespeichert wird, ist ein Schlüsselwechsel ein
  Re-Encrypt-Vorgang: mit altem Key entschlüsseln, mit neuem Key neu schreiben
  (Evidence erneut hochladen / Feld-Secrets beim nächsten Schreibzugriff). Während der
  Übergangszeit beide Keys vorhalten ist nicht automatisiert → geplante Wartung.
- **DB-at-rest:** Live-Postgres wird auf OS-/Volume-Ebene verschlüsselt (LUKS/Cloud-Disk-
  Encryption empfohlen). Feldverschlüsselung schützt einzelne Secrets zusätzlich in der DB.

## Datenbank-Optionen (Bewertung)

- **Volume-/OS-Verschlüsselung** (empfohlen, transparent, kein App-Eingriff).
- **Feldverschlüsselung** (bereits umgesetzt für Secrets) für Defense-in-Depth.
- **SQLCipher** entfällt nach der Postgres-Migration (#15); für Postgres ist
  Volume-/TDE-Verschlüsselung das Mittel der Wahl.
