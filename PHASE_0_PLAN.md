# Phase-0 Plan: Spezifikationen & Refactorings

**Status:** In Progress  
**Start:** 2026-05-08  
**Ziel:** Solide Fundament für Web-API-Entwicklung (Phase 1-5)

---

## 📋 Übersicht Phase-0

Phase-0 besteht aus 6 Spezifikations-Issues + 3 Architektur-Refactorings, um:
1. Klare API-Contracts vor Backend/Frontend-Entwicklung zu definieren
2. Infrastruktur-Entscheidungen zu treffen (DB-Isolation, Build-Pipeline)
3. Sicherheit & Logging früh zu konzeptionalisieren
4. Code-Reuse zwischen Desktop & Web zu maximieren

---

## 🔧 Refactoring-Umfang pro Modul

### 1. shared/db_security.py (Status: REVIEW)

**Aktuell:** SQLite-Connection-Manager mit File-Hardening  
**Größe:** 94 Zeilen  
**Abhängigkeiten:** `shared/audit.py`, `security_utils`

#### Refactoring für Multi-DB
```python
# ZIEL: Separate Engines für users.sqlite, cra.sqlite, audit.sqlite
# Änderung: Minimal
# - Klasse DbManager(db_name: str) → wraps connect_sqlite()
# - Context-Manager für Transaktionen
# - Connection-Pool-Sizing konfigurierbar
```

**Effort:** 1-2 Tage  
**Risiko:** LOW (keine Breaking Changes, nur Erweiterungen)

---

### 2. shared/audit.py (Status: REVIEW)

**Aktuell:** Event-basiertes Audit-Logging (JSON, Datei-basiert)  
**Größe:** 79 Zeilen  
**Features:**
- PII-Redaction (sensitive keys in `_SENSITIVE_KEYS`)
- Truncation (max 500 chars)
- Strukturiertes JSON-Format

#### Erweiterung für Web-API
```python
# ZIEL: HTTP-Context + SQLite-Persistierung
# Neue Funktion: log_http_request(method, path, status, duration, user_id, ip, user_agent)
# Neue Abhängigkeit: audit.sqlite (SQLAlchemy)
# Middleware-Adapter für Flask

# Struktur BLEIBT:
# - audit_event() für Desktop/CLI (JSON → audit.log)
# - log_http_request() für Web-API (JSON → audit.sqlite + audit.log)
```

**Effort:** 2-3 Tage  
**Risiko:** LOW (Backward-kompatibel, nur Erweiterungen)

---

### 3. prefill/review_dialog.py (Status: REVIEW)

**Aktuell:** Tkinter-Dialog für KI-Vorschlag-Review  
**Größe:** 200+ Zeilen  
**Problem:** Direkte Tkinter-Abhängigkeiten verhindern Web-API-Nutzung

#### Refactoring: Decoupling

**VORHER:**
```
prefill/
├── __init__.py
├── engine.py          ← Pure Python (OK)
├── review_dialog.py   ← Tkinter-gekoppelt (PROBLEM)
├── db.py              ← SQLite-Zugriff (OK)
└── config.py
```

**NACHHER:**
```
prefill/
├── __init__.py
├── engine.py          ← Pure Python (UNVERÄNDERT)
├── db.py              ← SQLite-Zugriff (UNVERÄNDERT)
├── config.py          ← Konfiguration (UNVERÄNDERT)
├── api.py             ← NEU: Flask-Adapter
│   ├── @app.post('/api/cra/prefill')
│   ├── generate_prefill(questions, top_k=5) → engine.py
│   └── accept_prefill(prefill_id, score, kommentar) → db.py
│
└── tk_ui/             ← NEU: Tkinter-spezifisch (MOVE)
    ├── __init__.py
    ├── review_dialog.py  ← Moved from root, unverändert
    ├── gui.py         ← Main Tkinter-GUI
    └── dialogs.py     ← Andere Dialoge (später)
```

**Implementation-Pattern:**
```python
# prefill/api.py (NEU)
from prefill.engine import generate_prefill, accept_prefill_suggestion

@bp.post('/api/cra/prefill')
@require_permission('cra:prefill')
def api_generate_prefill():
    """KI-Vorschläge generieren (pure Python)"""
    data = request.json
    results = generate_prefill(
        db_path=Path('data/cra.sqlite'),
        questions=data['questions'],
        top_k=data.get('top_k', 5)
    )
    return results

@bp.post('/api/cra/prefill/<prefill_id>/accept')
@require_permission('cra:prefill')
def api_accept_prefill(prefill_id):
    """Prefill-Vorschlag übernehmen"""
    data = request.json
    accept_prefill_suggestion(
        db_path=Path('data/cra.sqlite'),
        prefill_id=prefill_id,
        score=data['score'],
        kommentar=data['kommentar']
    )
    return {'status': 'accepted'}

# prefill/tk_ui/review_dialog.py (MOVED, unverändert)
# → Kann noch von Desktop-GUI genutzt werden
```

**Effort:** 3-4 Tage (Refactoring + Tests)  
**Risiko:** MEDIUM (must preserve Desktop-Kompatibilität)  
**Test-Plan:**
- [ ] Desktop-GUI lädt noch und funktioniert
- [ ] engine.py Unit-Tests (ohne Tkinter)
- [ ] api.py Integration-Tests (mit Mock-DB)
- [ ] Keine neuen Tkinter-Abhängigkeiten in engine.py/api.py

---

## 📊 Spezifikations-Issues (6 Issues)

### SPEC-252: API-Contract für CRA-Modul
**Blockt:** #216 (CRA-API), #217 (CRA-Frontend)  
**Effort:** 2 Tage  
**Deliverables:**
- OpenAPI/Swagger-YAML (`server/openapi/cra.yaml`)
- JSON-Schema-Validator (Flask-marshmallow oder Pydantic)
- Mock-Server für Frontend-Testing (optional: Prism)
- Error-Response-Format (Standard: `{"error": "msg", "code": "CODE"}`)

### SPEC-253: DB-Isolation-Strategy
**Blockt:** #220 (DB-Integration), #222 (Audit-Logging)  
**Effort:** 1 Tag  
**Deliverables:**
- `server/config/database.py` (DB-Engine-Registry)
- `server/db/session.py` (Transaction Context-Manager)
- `docs/ARCHITECTURE_DATABASE.md` (Dokumentation)

### SPEC-254: prefill/ Refactoring
**Blockt:** #236 (Prefill-API)  
**Effort:** 3-4 Tage  
**Deliverables:**
- `prefill/api.py` (Flask-Blueprint)
- `prefill/tk_ui/` (Tkinter-spezifisch, moved)
- Unit-Tests für `prefill/engine.py`
- Integration-Tests für `prefill/api.py`

### SPEC-255: shared/audit.py Web-Integration
**Blockt:** #222 (Audit-Logging)  
**Effort:** 2-3 Tage  
**Deliverables:**
- `shared/audit.py` erweitert (log_http_request)
- `server/middleware/audit.py` (Flask-after_request hook)
- `audit.sqlite` Schema (Alembic migration)
- PII-Redaction für HTTP-Logs

### SPEC-256: Frontend-Build-Pipeline
**Blockt:** #242 (Docker-Build)  
**Effort:** 1 Tag  
**Deliverables:**
- `frontend/vite.config.ts` (mit Dev-Proxy, Build-Optimierungen)
- `.env.development`, `.env.production`
- Dockerfile Multi-Stage-Build
- npm scripts (dev, build, preview)

### SPEC-257: RBAC-Permission-Matrix
**Blockt:** #224 (User-Models), #226 (Permission-Decorator)  
**Effort:** 1 Tag  
**Deliverables:**
- `server/models/permission.py` (SQLAlchemy-Modelle)
- Permission-Matrix (docs + code)
- `@require_permission` Decorator
- Tests für Permission-Checking

---

## 🔄 Abhängigkeitsgraph

```
SPEC-253 (DB-Isolation)
    ↓
SPEC-255 (audit.py)  ← Braucht DB-Setup
    ↓
    └─→ #220 (DB-Integration), #222 (Audit-Logging)

SPEC-252 (API-Contract)
    ↓
    └─→ #216 (CRA-API), #217 (CRA-Frontend)

SPEC-254 (prefill/ Refactoring)
    ↓
    └─→ #236 (Prefill-API)

SPEC-256 (Frontend-Build)
    ↓
    └─→ #242 (Docker-Build)

SPEC-257 (RBAC-Matrix)
    ↓
    └─→ #224 (User-Models), #226 (Permission-Decorator)

PARALLEL START (Woche 1):
- SPEC-253 + SPEC-257 (keine Abhängigkeiten)
- SPEC-252 (Spec, braucht keinen Code)
- SPEC-254 (Refactoring, parallel möglich)
```

---

## 📅 Wochenplan Phase-0

### Woche 1 (Start: 2026-05-08)

**Priorität 1 (Tag 1-2):**
- [ ] SPEC-253: DB-Isolation-Strategy finalisieren
  - `server/config/database.py` schreiben
  - Session-Manager implementieren
  - Dokumentation
- [ ] SPEC-257: RBAC-Permission-Matrix finalisieren
  - SQLAlchemy-Modelle definieren
  - Permission-Matrix dokumentieren

**Priorität 2 (Tag 3-5):**
- [ ] SPEC-252: API-Contract schreiben (OpenAPI-YAML)
- [ ] SPEC-254: prefill/ Refactoring starten
  - Verzeichnisstruktur vorbereiten
  - engine.py & api.py Interfaces definieren
- [ ] SPEC-255: shared/audit.py Erweiterung beginnen

**Priorität 3 (Tag 5+):**
- [ ] SPEC-256: Frontend-Build-Pipeline (vite.config.ts)
- [ ] Code-Reviews & Tests

---

## ✅ Definition of Done (Phase-0)

### Pro Spec-Issue
- [ ] Issue-Beschreibung + Akzeptanzkriterien erfüllt
- [ ] Code geschrieben + getestet
- [ ] Dokumentation geschrieben
- [ ] Code-Review bestanden
- [ ] Branch gemerged (mit Squash)

### Gesamt Phase-0
- [ ] Alle 6 Spec-Issues DONE
- [ ] 3 Refactorings DONE
- [ ] `PHASE_0_SUMMARY.md` geschrieben
- [ ] GitHub Project #4 updated (Tags: `phase-0-done`)
- [ ] Phase-1 Kickoff-Doku (Dependency-Chart, Rollen)

---

## 🎯 Erfolgs-KPIs Phase-0

| KPI | Ziel | Status |
|-----|------|--------|
| Alle Issues erstellt | 6/6 | ✅ DONE (252-257) |
| API-Contract ready | YAML vorhanden | ⏳ TODO |
| DB-Setup ready | Config + Session-Manager | ⏳ TODO |
| prefill/ refactored | Decoupled, Tests grün | ⏳ TODO |
| audit.py erweitert | HTTP-Context geloggt | ⏳ TODO |
| Frontend-Build | vite.config.ts ready | ⏳ TODO |
| RBAC definiert | Permission-Matrix + Code | ⏳ TODO |
| Code-Coverage | Unit-Tests > 80% | ⏳ TODO |
| Team-Alignment | Phase-1 Kickoff möglich | ⏳ TODO |

---

## 📝 Nächste Schritte

1. **Commit:** Phase-0 Plan in Git speichern
2. **Issues:** #252-257 zu GitHub Project #4 hinzufügen (mit Label `phase-0`)
3. **Branches:** Für jeden Refactoring einen Feature-Branch
   - `feature/spec-253-db-isolation`
   - `feature/spec-254-prefill-refactor`
   - `feature/spec-255-audit-web`
   - etc.
4. **Kickoff:** Tech-Team Brief über Phase-0-Plan

---

**Plan verfasst:** ai-compliance-engineer Agent  
**Datum:** 2026-05-08
