# Logging / Record-Keeping (AIA-HR-04 · Art. 12)

Jeder KI-Aufruf der Suite wird automatisch protokolliert — unabhängig vom Provider und vom
Aufrufweg. Die Protokolle liegen im **append-only Audit-Trail mit Integritätskette** (Postgres,
#1338) und sind über *Administration → Audit* bzw. `GET /api/admin/audit/events?action=…`
abrufbar (z. B. für Revisionsberichte).

## Protokollierte Ereignisse

| Ereignis | Wann | Inhalt (nur Metadaten) |
|---|---|---|
| `ai.on_prem.request` | Ollama-Aufruf (nicht-streamend) | Start/Erfolg/Fehler, Modell, Endpunkt, HTTP-Status |
| `ai.on_prem.stream` | Ollama-Aufruf (Streaming: Auto-Bewertung, Berichts-KI, „Direkt mit KI") | `start` / `success` / `fail` / `aborted`, Modell, Prompt-Länge, Token-Anzahl, Dauer (#1550) |
| `ai.cloud.request` | Cloud-Aufruf | Start/Erfolg/Fehler, Host, Modell, Redaktion aktiv |
| `ai.egress.confirmed` | Bestätigung vor Datenübermittlung an KI | Nutzer, Provider, Zweck (#1519) |
| `ai.assessment.evidence_used` | KI-Bewertung mit App-Nachweisen | Modul, Anforderung, genutzte Quellen, Provider (#1485) |
| `<modul>.req_risk.*`, `aiact.*` | fachliche Folgeaktionen | Projekt, Objekt, Akteur |

Zusätzlich gilt für jeden schreibenden API-Aufruf der allgemeine Audit-Mechanismus
(Akteur erst nach JWT-Verifikation, Client-IP über ProxyFix, #1187).

## Datenminimierung

Prompt- und Antwort**inhalte** werden **nicht** protokolliert (Schutz von Projekt- und
personenbezogenen Daten). Die Rückverfolgbarkeit einer Bewertung ergibt sich aus
Zeitstempel + Modell + Provider im Audit-Trail, den genutzten Nachweisen (Provenienz) und der
Kennzeichnung im gespeicherten Kommentar (siehe [Transparenz](transparenz.md)).

## Aufbewahrung

Audit-Einträge sind append-only und werden nicht durch die Anwendung gelöscht. Die
Aufbewahrungsdauer legt der Betreiber fest (Empfehlung: mindestens 6 Monate, Art. 19 / Art. 26
Abs. 6 analog). Für die Fehlersuche stellt das Support-Bundle (#1509) Logs redigiert bereit.
