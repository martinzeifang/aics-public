# Architektur — AI Compliance Suite

## Überblick

Die AI Compliance Suite ist eine Web-Anwendung zur Verwaltung von Compliance-Anforderungen
über mehrere EU-Regulatorische Frameworks hinweg. Sie ist zweistufig aufgebaut:

```
Frontend (Vue.js 3)  ←→  Backend (Flask)  ←→  SQLite-DBs
                                          ←→  GitHub/GitLab APIs
                                          ←→  KI-Provider (Ollama / Cloud)
```

## Module

Die Suite umfasst **6 Compliance-Module + 1 Stamm-Modul + Foundations**:

| Modul | Regulatorik | Anforderungen | DB |
|-------|-------------|---------------|-----|
| Kunden | Stammdaten + Multi-Produkt | n/a | `kunden.sqlite` |
| Risikobewertung | 5 Frameworks (STRIDE, HEAVENS, OCTAVE, TARA, Finanz.) | n/a (User-defined) | `risikobewertung.sqlite` |
| CRA | EU 2024/2847 | 32 + 10 OWASP-PC | `cra.sqlite` |
| NIS2 | EU 2022/2555 | 30 | `nis2.sqlite` |
| AI Act | EU 2024/1689 | 13 + OWASP-LLM-Top-10 | `ai_act.sqlite` |
| DORA | EU 2022/2554 | 32 + TPP-Register + TLPT | `dora.sqlite` |

Plus DSGVO-Modul, Gutachten, Compliance-Reports, BASO/ICT-Fragebögen (aus der Desktop-App).

## Backend-Architektur

### Verzeichnisstruktur

```
ai_compliance_suite/   # Konfig + Hauptmodul
ai_act/                # AI-Act-Modul (db, requirements, reports, ...)
cra/                   # CRA-Modul
dora/                  # DORA-Modul
dsgvo/, gutachten/, ... # weitere Module
evidence/              # Evidence-Library
kunden/                # Kunden-Stammdaten
nis2/                  # NIS2-Modul
risikobewertung/       # Multi-Framework-Risiken

server/                # Flask-Web-Backend
├── app.py            # Application-Factory + Blueprint-Registrierung
├── api/              # REST-Endpoints pro Modul
│   ├── auth.py
│   ├── admin.py
│   ├── kunden.py
│   ├── cra/
│   ├── dora/
│   ├── nis2.py
│   ├── aiact.py
│   ├── risikobewertung.py
│   ├── issues.py     # Cross-Modul-Übersicht (Phase 5.7)
│   └── ...
├── auth/             # JWT, LDAP, User-DB
├── config/           # DB-Initialisierung
├── middleware/       # Audit, Rate-Limiting
├── models/           # Permissions, Roles
└── services/         # Cross-Modul-Helfer (reports, prefill)

shared/                # Cross-Modul-Utilities
├── issue_links.py    # Issue-Verlinkung (alle Module)
├── issue_sync.py     # GitHub/GitLab-Status-Sync
└── ...

vcs/                   # Version-Control-Integration
├── github_issues.py
├── gitlab_issues.py
└── issue_assistant.py
```

### Patterns

**1. Application-Factory** (`server/app.py:create_app()`):
- Konfiguriert CORS, JWT, Rate-Limiting, Audit-Middleware
- Registriert alle Module-Blueprints
- Initialisiert DBs

**2. Blueprint pro Modul** unter `server/api/`:
- Identisches CRUD-Pattern: `/projekte`, `/anforderungen`, `/bewertungen`, `/reifegrad`, `/report`
- Permission-Decorator `@require_permission(...)`

**3. DB-Layer** in jedem Modul (`<modul>/db.py`):
- SQLite mit WAL-Mode
- `ensure_db()` legt Tabellen idempotent an
- CRUD-Funktionen direkt mit `sqlite3`

**4. Reifegrad-Berechnung** (`<modul>/requirements.py:berechne_reifegrad()`):
- Gewichtete Aggregation pro Kapitel/Pfeiler + gesamt
- Liefert `{gesamt, kapitel, luecken}` im Frontend-Format

### Cross-Modul-Komponenten

- **`shared/issue_links.py`** — Issue-Verlinkung mit Tabelle `linked_issues` (in jeder Modul-DB)
- **`shared/issue_sync.py`** — GitHub-API-Calls für State-Sync
- **`vcs/github_issues.py`, `vcs/gitlab_issues.py`** — Issue-Erstellung
- **`server/services/reports.py`** — gemeinsame Helfer für DOCX/PDF/Excel
- **`server/services/prefill.py`** — Repo-Scan + KI-Provider-Auswahl
- **`server/api/issues.py`** — modul-übergreifende Issue-Übersicht

## Frontend-Architektur

### Verzeichnisstruktur

```
frontend/src/
├── api/client.ts             # Axios-Client mit JWT-Interceptor
├── components/
│   ├── AppLayout.vue         # Hauptlayout (Header, Tabs, Sidebar, Status)
│   ├── StatusBar.vue         # Footer-Statusleiste
│   ├── SettingsDialog.vue    # Globale Einstellungen
│   ├── shared/               # Wiederverwendbare Komponenten
│   │   ├── ProjektSidebar.vue
│   │   ├── MaturityGauge.vue
│   │   ├── ChapterCard.vue
│   │   ├── RequirementEditor.vue
│   │   └── RequirementActions.vue   # KI + Issues, modul-agnostisch
│   └── sidebars/             # Pro-Modul-Sidebars
├── stores/                   # Pinia-Stores (1 pro Modul)
├── views/                    # Pro-Modul-Views
└── router/index.ts           # Vue-Router mit Guards
```

### Patterns

**1. Pinia-Store pro Modul**:
- `projekte`, `selectedProjekt`, `anforderungen`, `reifegrad`
- `fetchProjekte`, `createProjekt`, `saveBewertung`, ...

**2. Wiederverwendbare Komponenten**:
- `RequirementEditor` mit Slot `#actions`
- `RequirementActions` mit Props `apiBase` für Modul-spezifische Endpoints
- `MaturityGauge` (SVG-Halbkreis)
- `ChapterCard` (Kapitel-/Pfeiler-Kachel mit Ampel)

**3. Auth-Flow**:
- Login → JWT in `sessionStorage`
- Axios-Default-Header `Authorization: Bearer <token>`
- Logout → Backend-Aufruf für Blacklist + lokales Cleanup

## Sicherheit (Phase 6 abgeschlossen)

- **JWT** mit Token-Blacklist (`revoked_tokens`-Tabelle)
- **HTTPS-Pflicht** in Production (Nginx terminiert)
- **HSTS** + Security-Headers (CSP, X-Frame-Options, ...)
- **CORS-Whitelist** über `CORS_ORIGINS` ENV
- **Rate-Limiting** via Flask-Limiter
- **Frontend** speichert Token in `sessionStorage` (nicht persistent)
- **CVE-relevante Pakete** auf Mindest-Versionen gepinnt
- **User-DB** statt hardcoded Demo-Credentials

## Deployment

Siehe `docs/DEPLOYMENT.md` für Schritt-für-Schritt-Anleitung.

Architektur:
```
Browser → Nginx (443/HTTPS) → Web (5000/Flask) → SQLite-DBs
                                              → External APIs
                                                (GitHub, Ollama, ...)
```

## Roadmap

- **Phase 6.4** — Backup-Monitoring, Prometheus-Metrics
- **Phase 6.5** — Vollständige OpenAPI-3.0-Spec
- **Phase 6.6** — LDAP/AD-Integration (vorbereitet, deaktiviert)

## Testing

Aktuell manuell. Pytest-Suite + Cypress-E2E sind als Phase 7 geplant.
