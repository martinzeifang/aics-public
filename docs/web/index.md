# Web-Anwendung

Die Web-Variante der AI Compliance Suite ist eine Vue.js 3 + Flask-Anwendung,
die einen Großteil der Desktop-Funktionalität in einer modernen Browser-UI
bereitstellt.

## Architektur auf einen Blick

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (Vue 3 + Pinia + Vite)                                 │
│                                                                 │
│  ┌─────────┬─────────────────────────────────────┐              │
│  │ Sidebar │ Module-Tabs                         │              │
│  │ (Liste) │ (Kunden / RB / CRA / NIS2 / DORA /  │              │
│  │         │  AI Act / DSGVO / Gutachten)        │              │
│  └─────────┴─────────────────────────────────────┘              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS + JWT
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Flask-API (server/) — JWT-Auth, RBAC, Audit-Log                │
│  ├─ /api/auth          (Login, Logout, Profile)                 │
│  ├─ /api/admin         (User-/Permission-Management)            │
│  ├─ /api/kunden        (Kundenverwaltung)                       │
│  ├─ /api/risikobewertung                                        │
│  ├─ /api/cra                                                    │
│  ├─ /api/nis2 · /api/dora · /api/aiact · /api/dsgvo             │
│  └─ /api/gutachten     (inkl. /frameworks Download/Ingest)      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  data/db/*.sqlite — pro Modul, gemeinsam mit Desktop-App        │
└─────────────────────────────────────────────────────────────────┘
```

## Module (8)

| Modul              | Pfad                  | Status |
|---|---|---|
| Kunden             | `/kunden`             | ✅ CRUD, Export |
| Risikobewertung    | `/risikobewertung`    | ✅ 5 Frameworks (STRIDE, HEAVENS, OCTAVE, TARA, FI) |
| CRA                | `/cra`                | ✅ 32 Anforderungen + 10 OWASP, Repo-Scan, Reports |
| NIS2               | `/nis2`               | ✅ 30+ Anforderungen, Reifegrad, Reports |
| DORA               | `/dora`               | ✅ 32 Anforderungen, 5 Pfeiler, TPP, Resilience-Tests |
| AI Act             | `/aiact`              | ✅ 13 Anforderungen, OWASP-LLM-Top-10 |
| DSGVO              | `/dsgvo`              | ✅ 36 Anforderungen + TOM + DSE + Schulung |
| Gutachten          | `/gutachten`          | ✅ Multi-Framework-Audit, Fragen-Generator |

## Admin-Bereich (`/admin`)

Sichtbar nur für Benutzer mit Rolle `admin`. Erreichbar über das 🛡️-Symbol
im Header.

| Bereich               | Pfad                  | Beschreibung |
|---|---|---|
| Benutzerverwaltung    | `/admin/users`        | Konten, Rollen, Module, Permissions |
| Framework-Bibliothek  | `/admin/frameworks`   | Regulierungs-PDFs Download/Ingest (DORA/NIS2/CRA/DSGVO/AI Act/BSI) |
| Audit-Log             | `/admin/audit`        | HTTP-Requests + Aktionen |
| DB-Viewer             | `/admin/db`           | SQLite-Tabellen einsehen |
| Backup-Verwaltung     | `/admin/backup`       | DB-Snapshots erstellen, hochladen, wiederherstellen |
| Issue-Übersicht       | `/admin/issues`       | GitHub-/GitLab-Issues |

Siehe auch: [Benutzerverwaltung](user-management.md) ·
[Framework-Bibliothek](framework-library.md)

## Lokales Setup

```bash
# Backend
pip install -r requirements.txt
./start-dev.sh   # bündelt JWT-Secret + Demo-Users

# Frontend (anderes Terminal)
cd frontend
npm install
npm run dev      # https://localhost:5173
```

Login: `admin@example.com` / `admin-password` (Demo-Modus mit
`ENABLE_DEMO_USERS=true`).

## Logging

- **`logs/app.log`** — alle Application-Events + Tracebacks
  (FileHandler + StreamHandler)
- **`logs/audit.log`** — JSON-Lines-Format mit jedem HTTP-Request
  (Methode, Pfad, Status, Dauer, IP, User)
- Globaler Flask-Errorhandler fängt alle uncaught Exceptions
  und gibt `{error, type, path}` zurück
