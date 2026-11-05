# Cloud KI (OpenAI-kompatibel)

Der Cloud-Modus nutzt eine OpenAI-kompatible Chat-Completions-API.

## Sicherheits-Gate

Der Cloud-Modus ist **standardmäßig gesperrt** und erfordert explizite Zustimmung:

- `ai.cloud.allow_data_egress = true` in der Konfiguration
- Die Suite-UI erzwingt den Consent-Dialog unter `Datei -> AI-Einstellungen`
- **Ohne Consent**: Kein Data-Egress an externe KI-Dienste

## Netzwerk-Härtung

- **HTTPS-only**: Die `base_url` muss mit `https://` beginnen
- **Keine Loopback-Umgehung**: Der Cloud-Provider umgeht den Loopback-Guard nicht
- **Redaktion vor Versand**: Wenn `ai.cloud.redact = true`, führt der Anbieter eine Best-Effort-Redaktion für offensichtliche Muster (API-Keys, Tokens, E-Mails) durch
- **Audit**: Jede Cloud-Anfrage erzeugt ein Audit-Event `ai.cloud.request`

## Konfiguration

API-Key per Environment Variable setzen (Standard: `AI_CLOUD_API_KEY`).

Beispiel-Konfiguration:

```json
{
  "ai": {
    "provider": "cloud",
    "cloud": {
      "allow_data_egress": true,
      "api_key_env": "AI_CLOUD_API_KEY",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-4.1-mini",
      "timeout_s": 60,
      "redact": true
    }
  }
}
```

## Redaktion

Wenn `ai.cloud.redact = true`, führt der Anbieter eine Best-Effort-Redaktion für offensichtliche Muster (API-Keys, E-Mails) durch. Das reduziert das Risiko, garantiert aber nicht, dass alle sensitiven Inhalte entfernt werden.

## Lange Antworten (Massenbewertung)

Seit v7.1.1 (#1588) streamt die Suite Cloud-Antworten Token für Token (Anthropic Messages-API
bzw. OpenAI-kompatibel mit `stream: true`). `timeout_s` gilt damit als Wartezeit zwischen zwei
Tokens (mindestens 300 s), nicht mehr für die gesamte Antwort.

- **Ausgabebudget:** „⚡ Direkt mit KI“ (Assistenten, Sammel-Prompt der Massenbewertung) erlaubt
  bis zu 16 384 Tokens, Einzelbewertungen 4 096. Über `ai.max_output_tokens` lässt sich das Budget
  für `run-stream` ändern. Unterstützt das Modell weniger, versucht die Suite es automatisch mit
  8 192 bzw. 4 096 Tokens.
- **Abgeschnittene Antworten** werden erkannt und mit einer klaren Meldung angezeigt (statt
  „Antwort nicht verwertbar“). Dann weniger Einträge auf einmal bewerten.
