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
| **Firmen** | Master-Datenverwaltung | — |

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

## Updates und Echtheitsprüfung

Ein Update ist ein Image-Wechsel. Die Images sind signiert und tragen eine
Software-Stückliste (SBOM) — beides lässt sich vor dem Einspielen prüfen.

### Update einspielen

```bash
# Gewünschte Version setzen (oder :latest)
export AICS_IMAGE_TAG=7.4.2
docker compose pull
docker compose up -d
```

Die verfügbaren Versionen stehen unter
[Releases](https://github.com/martinzeifang/aics-public/releases). Ein Rückgang
auf die Vorversion ist derselbe Befehl mit dem älteren Tag — die Image-Tags
bleiben erhalten.

### Signatur prüfen

Die Images werden **keyless** über Sigstore signiert; es gibt also keinen
öffentlichen Schlüssel zu verwalten. Geprüft wird die Identität des Workflows,
der das Image gebaut hat:

```bash
# cosign installieren: https://docs.sigstore.dev/cosign/installation/
IMAGE=ghcr.io/martinzeifang/ai_compliance_suite:7.4.2

cosign verify "$IMAGE" \
  --certificate-identity-regexp '^https://github.com/martinzeifang/aics-public/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Die Identität ist bewusst eng gefasst: Seit 7.4.8 baut **dieses** Repository die
veröffentlichten Images, und nur dessen Workflow soll als gültig gelten. Für
Images bis 7.4.7 lautet die Identität
`^https://github.com/martinzeifang/AI_Compliance_Suite/.*` — damals wurde im
privaten Repo gebaut.

Die Ausgabe nennt Repository, Workflow und Commit, aus dem das Image entstanden
ist. Schlägt die Prüfung fehl, stammt das Image nicht aus diesem Projekt — dann
nicht einspielen.

### Software-Stückliste (SBOM) abrufen

Die SBOM liegt im SPDX-Format als Attestation am Image:

```bash
cosign download attestation "$IMAGE" \
  --predicate-type spdxjson | jq -r '.payload' | base64 -d | jq '.predicate'
```

Damit lässt sich prüfen, welche Komponenten in welcher Version enthalten sind —
etwa um eine neu veröffentlichte Schwachstelle gegen den eigenen Bestand zu
halten. Zusätzlich hängt am Image eine SLSA-Provenance (`--predicate-type
slsaprovenance`), die den Bauvorgang beschreibt.

### Sicherheitsmeldungen

Behobene Schwachstellen werden mit dem Release veröffentlicht. Meldungen zu
Lücken bitte vertraulich an die Adresse in [SECURITY.md](SECURITY.md), nicht als
öffentliches Issue.

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

Feature-Requests bitte direkt per E-Mail — wir priorisieren nach Firmen-
und Roadmap-Bedarf.

---

## Kontakt

- **Vertrieb / Lizenzanfragen:** martin.zeifang@gmail.com
- **Bug Reports:** [GitHub Issues](https://github.com/martinzeifang/aics-public/issues)
- **Source-Quelle:** [martinzeifang/aics-public](https://github.com/martinzeifang/aics-public)
