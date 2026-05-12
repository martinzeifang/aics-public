# Secret-Redaktion (`shared.redaction`)

Best-Effort-Redaktion von API-Keys, Tokens und sensiblen Mustern in Textinhalten.

## Funktionen

### `redact_secrets`

```python
def redact_secrets(text: str, placeholder: str = "[REDACTED]") -> str:
```

Ersetzt bekannte Secret-Muster durch `[REDACTED]`.

**Erkannte Muster:**

| Muster | Beispiel | Ersetzung |
|---|---|---|
| GitHub PAT | `ghp_xxxxxxxxxxxxxxxxxxxx` | `[REDACTED]` |
| GitHub PAT (feingranular) | `github_pat_xxxxxxxxxxxxxxxxxxxx` | `[REDACTED]` |
| GitLab PAT | `glpat-xxxxxxxxxxxxxxxx` | `[REDACTED]` |
| OpenAI API Key | `sk-xxxxxxxxxxxxxxxxxxxxxxxx` | `[REDACTED]` |
| Bearer-Token (HTTP Header) | `Authorization: Bearer xxxx` | `[REDACTED]` |
| Hex-Sequenzen (64+ Zeichen) | `0xABCDEF...` (>=64 Hex-Zeichen) | `[REDACTED]` |

## Grenzen

- Die Redaktion arbeitet **best-effort**: nicht alle Secret-Formate werden erkannt
- Sie ist **kein Ersatz** für ordnungsgemäßes Secrets-Management (Umgebungsvariablen, Vault)
- Hex-Sequenzen ab 64 Zeichen können auch legitime Daten sein (UUIDs, Hashwerte)

## Verwendung

```python
from shared.redaction import redact_secrets

text = "API Key: sk-abc123...secret..."
safe = redact_secrets(text)
# → "API Key: [REDACTED]"
```

## Einsatzorte

- Risikobewertung Issue Sync – vor Persistierung von Issue-Inhalten
- Cloud-Provider – vor Versand an externe KI-API
- Audit-Logs – vor der Speicherung von Event-Details
