# KI-Anbieter-Schnittstelle

Dieses Dokument beschreibt die anbieterunabhängige Schnittstelle, über die die AI Compliance Suite KI-Funktionen anspricht.

## Ziele

- Standardbetrieb ist **on-prem** (keine Cloud-Verbindung erforderlich).
- Cloud-Betrieb ist optional und muss explizit aktiviert werden.
- Die Suite spricht KI über eine schmale, austauschbare Schnittstelle an.

## Code-Stellen

- Schnittstelle + Factory: `ai_compliance_suite/ai/provider.py`
- Anbieter-Implementierungen:
  - `ai_compliance_suite/ai/providers/on_prem.py`
  - `ai_compliance_suite/ai/providers/cloud.py`

## Konfigurationsvertrag

Die Suite-Konfiguration (`ai_compliance_suite.config.json`) enthält einen `ai`-Abschnitt.

```json
{
  "ai": {
    "provider": "on_prem",
    "on_prem": {},
    "cloud": {}
  }
}
```

- `ai.provider`: `"on_prem"` oder `"cloud"`.
- `ai.on_prem`: anbieter-spezifische Einstellungen für das On-Prem-Backend.
- `ai.cloud`: anbieter-spezifische Einstellungen für das Cloud-Backend.

## Anbieter-API

- `generate_text(AITextRequest) -> AITextResponse`
- `healthcheck() -> None`

Die Schnittstelle ist absichtlich minimal. Neue Fähigkeiten (z.B. strukturierte Extraktion, Embeddings) sollten erst ergänzt werden, wenn es einen konkreten Consumer gibt.
