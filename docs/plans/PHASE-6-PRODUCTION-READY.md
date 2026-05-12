# Phase 6: Production Readiness

**Ziel:** Die Suite produktionsreif machen — Sicherheit, Deployment, Dokumentation.

## Phasenübersicht

| Phase | Inhalt | Issues |
|-------|--------|--------|
| **6.1** | Security Hardening (Critical Bugs) | #263, #264, #265, #266, #267, #268, #269 |
| **6.2** | Dependency-CVEs + Account-Sicherheit | #228, #274, #275, #276, #277 |
| **6.3** | Deployment (Docker, Compose, Reverse-Proxy, Auto-HTTPS) | #242, #243, #271 |
| **6.4** | Backup & Monitoring | #244 |
| **6.5** | Dokumentation (OpenAPI, Architektur, Deployment) | #245, #251 |
| **6.6** | Optional: LDAP/AD-Integration | #270 |

---

## Phase 6.1: Security Hardening (DRINGEND)

### 🔴 CRITICAL Issues
- **#263** Hardcoded JWT Secret in Production → ENV-Pflicht + Validation beim Start
- **#264** CORS allows any origin → Whitelist + per-Env-Konfiguration
- **#265** Demo-Credentials publicly exposed → Endpoint entfernen / nur in DEV

### 🟠 HIGH Issues
- **#266** No Token Invalidation on Logout → Token-Blacklist (DB-basiert)
- **#267** No input validation / rate limiting → Flask-Limiter
- **#268** Frontend Sensitive Data Exposure → keine Tokens/Secrets im localStorage

### 🟡 MEDIUM
- **#269** No HTTPS/TLS Enforcement → HSTS-Header + http→https Redirect

---

## Phase 6.2: Dependencies + Account-Sicherheit

- **#274** Cryptography Library Vulnerabilities → Pin auf neueste Version
- **#275** urllib3 HTTPS Connection (CVE-2024-37891) → Upgrade
- **#276** PyYAML Arbitrary Code Execution → Upgrade auf 6.0.1+
- **#277** Multiple Transitive Dependency CVEs → pip-audit, automatischer Scan
- **#228** Account-Sicherheit: Rate-Limiting, Password-Policies, Lockout

---

## Phase 6.3: Deployment

- **#242** Dockerfile Multi-Stage-Build (Frontend + Backend in einem Image)
- **#243** docker-compose.yml + Nginx Reverse-Proxy + HTTPS
- **#271** Self-Signed HTTPS Certificate Auto-Generation

---

## Phase 6.4: Backup & Monitoring

- **#244** Datenbank-Backup + Auto-Migration + Health-Monitoring

---

## Phase 6.5: Dokumentation

- **#245** OpenAPI/Swagger-Dokumentation der REST-API
- **#251** Architektur-Doku, API-Doku, Deployment-Guide, Sicherheits-Konzept

---

## Phase 6.6: Optional

- **#270** LDAP/AD Authentication Integration

---

## Geschätzte Reihenfolge

1. **6.1 Critical Security** (DRINGEND) — produktionsblockierend
2. **6.2 Dependencies** — schnell, aber mit Tests
3. **6.3 Deployment** — Voraussetzung für reale Nutzung
4. **6.4 Backup/Monitoring** — Operational
5. **6.5 Dokumentation** — finale Produktreife
6. **6.6 LDAP** — Bonus

Total: ~14 Issues, ca. 8-12 Tage geschätzt.
