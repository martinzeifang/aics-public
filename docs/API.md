# API-Referenz — AI Compliance Suite

Base-URL: `https://<server>/api`

Alle Endpoints (außer `/auth/login` und `/health`) erfordern JWT-Bearer-Token im
`Authorization: Bearer <token>` Header.

## Authentication

| Method | Path | Beschreibung |
|--------|------|--------------|
| POST | `/auth/login` | Login mit `{email, password}` → `{access_token, user}` |
| GET | `/auth/profile` | Aktueller User (mit Permissions) |
| POST | `/auth/logout` | Token in Blacklist eintragen |
| POST | `/auth/refresh` | Token erneuern |

## Module-APIs

Alle Module folgen identischem Pattern:

```
GET    /<modul>/projekte                                  Liste
GET    /<modul>/projekte/<name>                           Detail
POST   /<modul>/projekte                                  Anlegen
PUT    /<modul>/projekte/<name>                           Update
DELETE /<modul>/projekte/<name>                           Löschen

GET    /<modul>/projekte/<name>/anforderungen             Liste mit Bewertungen
POST   /<modul>/projekte/<name>/bewertungen               Bewertung speichern
GET    /<modul>/projekte/<name>/reifegrad                 Reifegrad-Berechnung
GET    /<modul>/projekte/<name>/report?format=pdf|docx    Report-Export
```

### Module

- `/cra` — Cyber Resilience Act (32 Anforderungen, 5 Kapitel + 10 OWASP Controls)
- `/nis2` — NIS2-Richtlinie (30 Anforderungen, 5 Kapitel)
- `/aiact` — EU AI Act (13 Anforderungen, 4 Kapitel + OWASP-LLM-Mapping)
- `/dora` — DORA (32 Anforderungen, 5 Pfeiler + TPP + Testing)
- `/risikobewertung` — 5 Frameworks (STRIDE, HEAVENS, OCTAVE, TARA, Finanzinstitute)
- `/kunden` — Multi-Produkt-Verwaltung + Evidence + Impressum-Parser

## RequirementActions-API (KI + Issues)

Pro Modul + Anforderung verfügbar:

```
GET    /<modul>/projekte/<n>/anforderungen/<id>/prompt           ChatGPT-Prompt
POST   /<modul>/projekte/<n>/anforderungen/<id>/parse-response   JSON-Antwort übernehmen

GET    /<modul>/projekte/<n>/anforderungen/<id>/issues           Verlinkte Issues
POST   /<modul>/projekte/<n>/anforderungen/<id>/issues           Neues Issue
POST   /<modul>/projekte/<n>/anforderungen/<id>/issues/link      Existierendes verlinken
POST   /<modul>/projekte/<n>/anforderungen/<id>/issues/sync      Status sync
DELETE /<modul>/projekte/<n>/anforderungen/<id>/issues/<lid>     Verknüpfung lösen
```

CRA hat zusätzlich `/owasp/<id>/...` mit identischem Pattern.

## Admin

| Method | Path | Permission | Beschreibung |
|--------|------|-----------|--------------|
| GET | `/admin/users` | `admin:users` | User-Liste |
| POST | `/admin/users` | `admin:users` | User anlegen |
| GET/PUT | `/admin/settings` | `admin:config` | Globale Settings |
| GET | `/admin/audit/events` | `admin:audit` | Audit-Log |
| GET | `/admin/db/{list,...}` | `admin:audit` | DB-Viewer (read-only) |
| GET/POST/DELETE | `/admin/backup` | `admin:config` | Backup-Verwaltung |

## Cross-Modul

| Method | Path | Beschreibung |
|--------|------|--------------|
| GET | `/issues/all?module=&state=&projekt=` | Alle Issues über alle Module |
| POST | `/issues/sync-all` | GitHub-Issue-Status sync (alle Module) |
| GET | `/issues/stats` | Counts by_module / by_state / by_provider |

## Health & Status

| Method | Path | Beschreibung |
|--------|------|--------------|
| GET | `/health` (ohne Auth) | Service-Status |

## Permission-Modell

Permissions werden über Rollen vergeben:

- `admin` — Vollzugriff (`admin:*`, `cra:*`, etc.)
- `cra_editor` — CRA-Bearbeitung
- `cra_viewer` — CRA-Lesezugriff

Tatsächliche Permissions:
- `cra:read`, `cra:write`, `cra:prefill`, `cra:issue_link`, `cra:export`
- `admin:users`, `admin:roles`, `admin:audit`, `admin:config`

## Beispiel-Aufrufe

### Login

```bash
curl -X POST https://server/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin-password"}'
# → {"access_token": "eyJ...", "user": {...}}
```

### CRA Anforderungen abrufen

```bash
TOKEN="eyJ..."
curl -H "Authorization: Bearer $TOKEN" \
  "https://server/api/cra/projekte/MyProject/anforderungen"
```

### KI-Prompt für eine Anforderung

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://server/api/cra/projekte/MyProject/anforderungen/AI1-01/prompt"
# → {"prompt": "Du bist ein Experte für CRA-Compliance...", "req_id": "AI1-01"}
```

### Issue erstellen

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"provider":"github","repo":"owner/repo","title":"CRA Gap"}' \
     "https://server/api/cra/projekte/MyProject/anforderungen/AI1-01/issues"
# → {"created": true, "url": "https://github.com/owner/repo/issues/N", ...}
```

## OpenAPI-Spezifikation

Eine vollständige OpenAPI-3.0-Spec wird in einer zukünftigen Version bereitgestellt.
Für jetzt dient diese Markdown-Datei als Referenz.
