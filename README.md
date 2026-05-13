# AI Compliance Suite (AICS)

**Compliance-Management-Plattform für CRA · NIS2 · EU AI Act · DSGVO · Risikobewertung**

Modular aufgebaute Web-Anwendung zur strukturierten Bewertung, Dokumentation
und Nachverfolgung regulatorischer Anforderungen — mit Audit-Trail,
optionaler KI-Unterstützung (lokales Ollama oder Cloud-LLM) und
GitHub/GitLab-Integration für Issue-getriebene Maßnahmen.

> 🔐 **Lizenz:** Business Source License 1.1. Demo und Evaluation sind frei.
> Produktivnutzung erfordert eine kommerzielle Lizenz — siehe [LICENSE](LICENSE)
> und [Kontakt](#kontakt).

---

## Quickstart (Docker — One-Click)

```bash
# 1. docker-compose.yml herunterladen
curl -O https://raw.githubusercontent.com/martinzeifang/aics-public/main/docker-compose.yml

# 2. Stack starten (Images werden automatisch von ghcr.io gezogen)
docker compose up -d

# 3. Im Browser öffnen
open https://localhost:8443
```

Beim ersten Start wird automatisch:
- ein zufälliger JWT-Secret im Volume generiert (`/app/data/.jwt-secret`)
- ein Self-Signed TLS-Zertifikat angelegt
- ein Initial-Admin-User angelegt mit zufälligem Passwort
  → Container-Logs prüfen für die Zugangsdaten

### Mit Ollama (lokale KI-Unterstützung)

```bash
COMPOSE_PROFILES=ai docker compose up -d
```

Der Ollama-Container pullt das Default-Modell `llama3.1:8b` (~5 GB) im Hintergrund.
Modelle können in der App unter **Admin → KI-Modelle** verwaltet werden.

---

## Module

| Modul | Anwendungsfall | Regulierung |
|-------|----------------|-------------|
| **Risikobewertung** | Multi-Framework-Risikoanalyse (STRIDE, OCTAVE, …) | ISO 27005, DSGVO Art. 32 |
| **CRA** | Cyber Resilience Act Readiness | EU CRA (2024/2847) |
| **DSGVO** | Datenschutz-Reifegrad + TOM-Generator + DSE | DSGVO/GDPR |
| **NIS2** | Netzwerk- und Informationssicherheit | EU NIS2 (2022/2555) |
| **AI Act** | EU-AI-Act-Klassifikation + Anforderungen | EU AI Act (2024/1689) |
| **Gutachten** | Expert-Opinion-Templates | — |
| **Kunden** | Master-Datenverwaltung | — |

---

## Lizenz-Flow

1. App starten → Initial-Login mit Logs-Passwort
2. **Admin → Lizenz** → „🎁 Demo aktivieren" (30 Tage, alle Module außer Gutachten)
3. Für Produktivnutzung: kommerzielle Lizenz erwerben → Schlüssel im UI eingeben

Bei Air-Gap-Setups: **Offline-Request-Datei** im Admin-Bereich generieren, an
den Vertrieb senden, signierte License-Datei zurück importieren.

---

## Stack

- **Backend:** Python 3.11 / Flask / Gunicorn / SQLite
- **Frontend:** Vue 3 / Pinia / Vue Router / Vite / TypeScript
- **Container:** Multi-Stage Dockerfile + nginx-Reverse-Proxy (TLS-Termination)
- **KI:** Ollama (optional, on-prem) oder OpenAI-kompatibel
- **Lizenz-Verifikation:** Ed25519-signierte JWT-artige Tokens (offline-fähig)

---

## Architektur

```
┌────────────────────┐  HTTPS  ┌────────────────┐    HTTP    ┌──────────┐
│  Browser / Client  │ ──────► │ nginx (8443)   │ ─────────► │ Flask    │
└────────────────────┘  TLS    │ (TLS-Termin.)  │            │ (Backend)│
                                └────────────────┘            └────┬─────┘
                                                                   │
                                          ┌────────────────────────┼────────┐
                                          ▼                        ▼        ▼
                                     ┌─────────┐            ┌──────────┐ ┌────────┐
                                     │ SQLite  │            │ Ollama   │ │ License│
                                     │ Volume  │            │ (opt.)   │ │ Server │
                                     └─────────┘            └──────────┘ └────────┘
```

Bei Produktivnutzung: eigenes TLS-Zertifikat in `certs/` mounten, reverse
proxy vor nginx (z.B. Traefik/Caddy) für ACME.

---

## Build aus Source

```bash
git clone https://github.com/martinzeifang/aics-public.git
cd aics-public
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

Lokale Entwicklung (ohne Docker):

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 run_dev.py            # https://localhost:5000

# Frontend
cd frontend
npm install
npm run dev                    # http://localhost:5173 (HMR-Proxy zu :5000/api)
```

---

## Dokumentation

- [docs/web/deployment.md](docs/web/deployment.md) — Operator-Handbuch
- [docs/web/license-setup.md](docs/web/license-setup.md) — Lizenz-Setup
- [docs/web/user-management.md](docs/web/user-management.md) — Benutzerverwaltung
- [docs/web/ollama-setup.md](docs/web/ollama-setup.md) — Ollama (lokale KI)
- [docs/web/two-factor-auth.md](docs/web/two-factor-auth.md) — 2FA / TOTP
- [docs/web/framework-library.md](docs/web/framework-library.md) — Regulierungs-PDFs

---

## Issues & Bug Reports

Bug Reports und Verbesserungsvorschläge sind willkommen im
[GitHub Issue Tracker](https://github.com/martinzeifang/aics-public/issues).

Feature-Requests bitte direkt per E-Mail — wir priorisieren nach Kunden-
und Roadmap-Bedarf.

---

## Kontakt

- **Vertrieb / Lizenzanfragen:** martin.zeifang@gmail.com
- **Bug Reports:** [GitHub Issues](https://github.com/martinzeifang/aics-public/issues)
- **Source-Quelle:** [martinzeifang/aics-public](https://github.com/martinzeifang/aics-public)
