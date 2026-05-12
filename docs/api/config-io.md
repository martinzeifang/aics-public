# Config I/O (sicher)

Diese Suite speichert Modul-Konfigurationen als JSON (`*.config.json`).

## Ziele

- **Integrität/Manipulationsschutz (Baseline):** Atomisches Schreiben (`tmp` + `replace`) reduziert das Risiko von teilgeschriebenen Dateien.
- **Vertraulichkeit:** Best-effort restriktive Dateirechte (typisch `0600`) und `umask(077)` beim Schreiben.
- **Nachvollziehbarkeit:** Audit-Event für Load/Save mit SHA-256 über den Datei-Bytes.

## API

- `shared.config_io.safe_load_json_config(path: Path) -> dict`
- `shared.config_io.safe_save_json_config(path: Path, cfg: dict) -> None`

## Audit-Events

- `config.load` (details: `path`, `sha256`)
- `config.save` (details: `path`, `sha256`)

## Grenzen / Annahmen

- Dateirechte sind **plattformabhängig** (Windows/Netzlaufwerke): „best effort“.
- SHA-256 ist **Integritätsnachweis**, kein vollständiger Schutz gegen lokale Angreifer mit Schreibrechten.
