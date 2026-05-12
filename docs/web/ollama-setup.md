# Ollama-Setup (KI-Modelle)

Diese Anleitung beschreibt, wie der AICS-Server mit einem lokalen Ollama-Modell-Server arbeitet — sowohl in Docker (`docker-compose.yml`, Profil `ai`) als auch in der lokalen Entwicklung.

## Architektur

```
┌──────────────┐   HTTP   ┌───────────────┐
│  AICS-Server │ ───────► │ Ollama-Server │
│ (Flask/8000) │          │   (11434)     │
└──────────────┘          └───────────────┘
                                  │
                                  ▼
                          Llama-/Mistral-/…-Modell
```

Der AICS-Server spricht Ollama über die Umgebungsvariable `OLLAMA_BASE_URL` an
(default `http://ollama:11434` in Docker, `http://localhost:11434` lokal).

## Docker (empfohlen)

`docker-compose.yml` hat ein Profil `ai`, das den Ollama-Container startet:

```bash
docker compose --profile ai up -d
```

Beim ersten Start zieht der Init-Container `ollama-init` das Default-Modell
(`llama3.1:8b`). Das dauert je nach Verbindung 5–30 min.

Status prüfen:

```bash
docker compose logs ollama-init
docker exec aics-ollama ollama list
```

### Modelle verwalten

**Admin-UI** (empfohlen): `https://<host>:8443/admin/ollama`
- Listet alle installierten Modelle inkl. Größe + Familie
- Empfohlene Modelle mit „⬇ Pull“-Button (Streaming-Progress via SSE)
- Modelle löschen mit „Löschen“-Button

**CLI**:
```bash
docker exec aics-ollama ollama pull llama3.2:3b
docker exec aics-ollama ollama rm llama3.2:3b
```

## Lokale Entwicklung

```bash
# Linux
chmod +x install-ollama.sh
./install-ollama.sh

# macOS / Windows: https://ollama.com/download

# Default-Modell pullen
ollama pull llama3.1:8b
```

Im AICS-Server in `.env`:

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

## RAM-Bedarf nach Modell

| Modell           | RAM (min) | Eignung |
|------------------|-----------|---------|
| `llama3.2:1b`    | 2 GB      | Schnelle Iterationen, Smoke-Tests |
| `llama3.2:3b`    | 4 GB      | Brauchbare Qualität, schnelle Antworten |
| `llama3.1:8b`    | 8 GB      | **Default** — gute Compliance-Bewertung |
| `mistral:7b`     | 8 GB      | Alternative zu Llama, deutsche Texte stärker |
| `llama3.1:70b`   | 48 GB     | Server-Class — nur mit GPU sinnvoll |

## Diagnose

`/admin/ollama` → Diagnose-Button. Prüft:
- TCP-Erreichbarkeit + Antwortzeit
- `/api/tags` lieferbar (Modellliste)
- Effektive Generation mit `Hello World`-Prompt

Bei „Verbindung verweigert“: prüfen, ob `OLLAMA_BASE_URL` auf die korrekte
Adresse zeigt (in Docker: **`http://ollama:11434`**, nicht `localhost`).
