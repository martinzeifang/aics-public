# Runtime-Integritätsprüfung (Manifest)

## Zweck

Best-effort Erkennung manipulierter Module/Skripte durch Hash-Validierung gegen ein Manifest.

## Manifest

- Datei: `.integrity.manifest.json` im Repo-Root
- Inhalt: `sha256` pro Datei (relativer Pfad → Hash)

Generieren:

```bash
python3 -m shared.integrity --write
```

Prüfen:

```bash
python3 -m shared.integrity --verify
```

## Enforcement

- Standard: Wenn ein Manifest vorhanden ist, wird geprüft und als Audit-Event geloggt.
- Fail-closed (optional):

```bash
export AICS_INTEGRITY_ENFORCE=1
```

Dann wird die Suite bei `missing/mismatched` Dateien beendet.

## Audit-Events

- `integrity.manifest.write`
- `integrity.check` (outcome: `success|fail`)

## Grenzen

- Schutz ist **detektiv**, nicht präventiv: lokale Angreifer mit Schreibrechten können Manifest/Code gemeinsam ändern.
- Für starken Supply-Chain-Schutz sind Signaturen/Trusted-Builds/Release-Attestations nötig.
