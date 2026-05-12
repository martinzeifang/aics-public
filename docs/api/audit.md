# Audit-Logging (`shared.audit`)

Strukturierte Erfassung sicherheitsrelevanter Ereignisse in der Suite.

## Datenstruktur

### `AuditEvent`

```python
@dataclass(frozen=True)
class AuditEvent:
    timestamp: str       # ISO-8601
    event_type: str      # z.B. "config.load"
    details: str         # Freitext mit Kontext
```

## Funktionen

### `add_audit_event`

```python
def add_audit_event(event_type: str, details: str) -> None:
```

Fügt ein Audit-Event mit aktuellem Zeitstempel hinzu. Persistiert in der Suite-Config-DB.

### `get_audit_log`

```python
def get_audit_log(limit: int = 100) -> list[AuditEvent]:
```

Gibt die letzten `limit` Audit-Events zurück (neueste zuerst).

## Ereigniskatalog

| Kategorie | Events | Auslöser |
|---|---|---|
| **Config** | `config.load`, `config.save` | Laden/Speichern von Modul-Configs |
| **DB** | `db.open` | Öffnen einer SQLite-Datenbank |
| **Export** | `export.write` | Schreiben einer Export-Datei (XLSX, CSV) |
| **JSON** | `json.load` | Import von JSON-Daten (ChatGPT-Antworten) |
| **KI (Cloud)** | `ai.cloud.request` | Anfrage an externen KI-Dienst |
| **KI (On-Prem)** | `ai.on_prem.request` | Anfrage an lokalen LLM |
| **Integrity** | `integrity.manifest.write`, `integrity.check` | Integritätsprüfung |
| **Daten** | `data.change` | Datenänderungen (Risikobewertung Change Log) |
| **Risiko** | `risk.update_from_issue` | Issue-Sync in Risikobewertung |

## GUI-Viewer

In der Suite-GUI unter `Datei → Audit-Log anzeigen` abrufbar. Zeigt die letzten 100 Events als sortierte Tabelle.

## Hinweise

- Audit-Events sind **append-only** – einmal geschriebene Events können nicht gelöscht werden
- Details werden vor der Speicherung durch `shared.redaction` auf Secrets gefiltert
- Das Audit-Log ist kein Ersatz für Syslog oder SIEM-Systeme bei hohen Sicherheitsanforderungen
