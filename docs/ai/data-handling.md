# KI-Datenhandhabung

Dieses Dokument beschreibt, welche Daten an KI-Anbieter gesendet werden dürfen und wie die Suite Risiken minimiert.

## Betriebsarten

### On-Prem (Standard)

- `ai.provider = on_prem`
- Es verlassen keine Daten die Maschine.

### Cloud (Opt-In)

- `ai.provider = cloud`
- Erfordert explizite Zustimmung: `ai.cloud.allow_data_egress = true`
- Optionale Redaktion: `ai.cloud.redact = true`

Die UI blockiert das Aktivieren des Cloud-Modus, solange keine Zustimmung gesetzt ist.

## Logging

- Prompts und Rohinhalte von Dokumenten dürfen standardmäßig nicht ins Logging geschrieben werden.
- Anbieter-Implementierungen sollten nur loggen:
  - Anbieter-Name
  - Request-ID / Zeitstempel
  - nicht-sensitive Fehlerzusammenfassungen

## Redaktion

Redaktion ist Best-Effort und ersetzt keine saubere Datenklassifizierung.

Die initiale Konfiguration unterstützt ein `redact`-Flag; konkrete Redaktionslogik wird zusammen mit dem Cloud-Anbieter umgesetzt.
