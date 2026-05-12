# Netzwerk-Validierung (`shared.net_validation`)

Schützt vor unautorisierter Datenübertragung an externe Dienste.

## Funktionen

### `enforce_loopback_base_url`

```python
def enforce_loopback_base_url(
    base_url: str,
    allow_nonlocal: bool = False,
) -> str:
```

Prüft, ob eine Base-URL auf einen Loopback-Host verweist.

**Erlaubte Hosts:** `localhost`, `127.0.0.1`, `::1`

**Wirft:** `ValueError` wenn der Host nicht Loopback ist und `allow_nonlocal` nicht gesetzt ist.

### `LOOPBACK_HOSTS`

```python
LOOPBACK_HOSTS: frozenset = frozenset({"localhost", "127.0.0.1", "::1"})
```

## Override-Möglichkeiten

Nicht-Loopback-Hosts sind nur erlaubt, wenn eine der folgenden Bedingungen erfüllt ist:

1. Config: `ai.on_prem.allow_nonlocal_base_url = true`
2. Environment: `AICS_ALLOW_NONLOCAL_LLM=1`

## Verwendung

```python
from shared.net_validation import enforce_loopback_base_url

# Erlaubt
enforce_loopback_base_url("http://127.0.0.1:11434")

# Blockiert
enforce_loopback_base_url("http://192.168.1.100:11434")
# → ValueError: Non-loopback host not allowed
```

## Anwendung

- `risikobewertung/prompts.py` – Loopback-Guard für Ollama-Prompts
- `compliance_db/local_llm.py` – Loopback-Guard für RAG-Abfragen
