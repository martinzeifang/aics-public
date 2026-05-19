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
