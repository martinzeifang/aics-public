# AI Compliance Suite — Dokumentation

Web-basierte Plattform für strukturierte Compliance-Bewertung mit Audit-Trail
und optionaler KI-Unterstützung.

## Module

| Modul | Anwendungsfall |
|-------|----------------|
| [Risikobewertung](modules/risikobewertung.md) | Multi-Framework-Risikoanalyse (STRIDE, OCTAVE, ISO 27005) |
| [CRA](modules/cra.md) | Cyber Resilience Act Readiness (EU 2024/2847) |
| [DSGVO](modules/dsgvo.md) | Datenschutz-Reifegrad, TOM-Generator, Datenschutzerklärung |
| [NIS2](modules/nis2.md) | NIS2-Richtlinie (EU 2022/2555) |
| [AI Act](modules/ai-act.md) | EU AI Act Klassifikation + Anforderungen (EU 2024/1689) |
| [Gutachten](modules/gutachten.md) | Expert-Opinion-Templates |
| [Firmen](modules/firmen.md) | Master-Datenverwaltung |

## Schnell-Links

- **[Quickstart Docker](web/deployment.md)** — One-Click-Deploy aus `docker-compose.yml`
- **[Lizenz-Setup](web/license-setup.md)** — Demo aktivieren, Lizenz importieren
- **[Benutzerverwaltung](web/user-management.md)** — Rollen, 2FA, Passwort-Reset
- **[Ollama-Setup](web/ollama-setup.md)** — Lokale KI-Modelle
- **[Framework-Bibliothek](web/framework-library.md)** — Regulierungs-PDFs ingesieren

## Technologie-Stack

- **Backend**: Python 3.11 / Flask / Gunicorn / SQLite
- **Frontend**: Vue 3 / Pinia / Vue Router / TypeScript / Vite
- **KI**: Ollama (on-prem) oder OpenAI-kompatible Cloud-LLM
- **Container**: Multi-Stage Dockerfile + nginx (TLS-Termination)
- **Lizenz-Verifikation**: Ed25519-signierte Tokens, offline-fähig

## Lizenz

Business Source License 1.1 — Demo + Evaluation frei. Produktivnutzung
erfordert eine kommerzielle Lizenz. Kontakt: martin.zeifang@gmail.com
