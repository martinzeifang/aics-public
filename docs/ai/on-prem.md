# On-Prem KI (Ollama)

Die Suite unterstützt einen On-Prem KI-Modus über [Ollama](https://ollama.com), das lokal läuft.

## Sicherheits-Härtung

### Loopback-Guard

Der On-Prem-Modus ist **standardmäßig auf Loopback-Adressen beschränkt**:

- Erlaubt: `localhost`, `127.0.0.1`, `::1`
- Nicht erlaubt: Jede andere IP oder Domain
- Die Funktion `enforce_loopback_base_url()` aus `shared/net_validation.py` blockiert nicht-Loopback-Hosts

**Override** (nur für fortgeschrittene Nutzer):

```json
{
  "ai": {
    "provider": "on_prem",
    "on_prem": {
      "allow_nonlocal_base_url": true
    }
  }
}
```

Alternativ per Environment-Variable:

```bash
export AICS_ALLOW_NONLOCAL_LLM=1
```

### Audit

Jede On-Prem-Anfrage erzeugt ein Audit-Event `ai.on_prem.request`.

### Anwendung

Der Loopback-Guard wird angewendet in:

- `risikobewertung/prompts.py` – Prompt-Generierung für Risikobewertung
- `compliance_db/local_llm.py` – RAG-Abfragen

## Konfiguration

In `ai_compliance_suite.config.json`:

```json
{
  "ai": {
    "provider": "on_prem",
    "on_prem": {
      "base_url": "http://127.0.0.1:11434",
      "model": "llama3.1:latest",
      "timeout_s": 60
    }
  }
}
```

## Modell installieren

Beispiel:

```bash
ollama pull llama3.1:latest
```

## Fehlerbehebung

- Wenn keine Verbindung möglich ist:
  - Prüfen, ob Ollama läuft
  - `base_url` prüfen
- Wenn das Modell fehlt:
  - mit `ollama pull <model>` installieren
- Wenn der Loopback-Guard greift:
  - Prüfen, ob `base_url` auf localhost/127.0.0.1/::1 zeigt
  - Für externe Ollama-Instanzen `allow_nonlocal_base_url` setzen
