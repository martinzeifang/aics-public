# Phase 7: Quality & Polish

**Ziel:** Qualität, Wartbarkeit und UX der Suite verbessern.

## Phasenübersicht

| Phase | Inhalt | Aufwand |
|-------|--------|---------|
| **7.1** | OpenAPI 3.0 + Swagger-UI | 1-2 Tage |
| **7.2** | Test-Suite (pytest + Vitest) | 2-3 Tage |
| **7.3** | 2FA (TOTP) für Admin-Accounts | 1-2 Tage |
| **7.4** | Dark Mode (Theme-Toggle) | 0.5-1 Tag |
| **7.5** | i18n (DE/EN) | 1-2 Tage |

---

## Phase 7.1: OpenAPI + Swagger-UI

- `flasgger` integrieren (decorator-basiert, geringinvasiv)
- Spec-Generierung aus bestehenden Endpoints
- Swagger-UI unter `/api/docs`
- Authentifizierte Endpoint-Dokumentation

## Phase 7.2: Test-Suite

**Backend (pytest)**:
- `pytest`, `pytest-flask`, `pytest-cov` einrichten
- `conftest.py` mit Test-DBs (Temp-Verzeichnisse)
- Auth-Tests (Login, Logout, Token-Blacklist)
- CRUD-Tests pro Modul (mind. ein Endpoint pro Modul)
- Reifegrad-Berechnungs-Tests (mit fixtures)

**Frontend (Vitest)**:
- `vitest` + `@vue/test-utils` einrichten
- Store-Tests (Pinia)
- Smoke-Tests für Komponenten (RequirementEditor, RequirementActions)

## Phase 7.3: 2FA (TOTP)

- `pyotp` integrieren
- DB-Tabelle `user_2fa(user_id, secret, enabled, backup_codes_json)`
- Setup-Flow: QR-Code generieren, Secret zeigen, Backup-Codes
- Login-Flow erweitern: nach Password ggf. TOTP-Eingabe
- Admin-Toggle: 2FA für Account aktivieren

## Phase 7.4: Dark Mode

- Settings-Toggle persistieren in localStorage
- CSS-Variablen für Light/Dark
- Component-Coverage prüfen

## Phase 7.5: i18n

- `vue-i18n` integrieren
- Deutsch (default) + Englisch
- Strings aus Templates extrahieren
- Locale-Switch in Settings
