# CRA Compliance Pack (Template)

> Zweck: Ausfüllbare Struktur, um CRA-Nachweise konsistent abzulegen und für Reviews/Audits auffindbar zu machen.
>
> Hinweis: Technische Vorlage, keine Rechtsberatung.

## 0. Meta

| Feld | Wert |
|---|---|
| Produkt/Projekt |  |
| Betreiber/Organisation |  |
| Repository/Artefakt-Ort |  |
| Version/Release |  |
| Datum |  |
| Owner (Rolle) |  |

## 1. Scope & Annahmen

- Produktbeschreibung (kurz):
- Erwartete Einsatzumgebung (On-Prem/Cloud/Hybrid):
- Datenklassen (PII, Credentials, Telemetrie):
- Abgrenzung (was ist nicht im Scope?):

## 2. Evidence-Index (Wo liegen Nachweise?)

| Kategorie | Speicherort | Beispiel |
|---|---|---|
| Policies/Prozesse | `docs/` / `SECURITY.md` |  |
| CI Artefakte | GitHub Actions / Releases | SBOM, OSV, Evidence Pack |
| CRA-DB Bewertungen | `data/db/cra.sqlite` | `cra_bewertungen`, `cra_owasp_checks` |
| Evidence Library | `data/db/evidence.sqlite` | `ci-artifact` Imports |
| Tickets/PRs | GitHub/GitLab Issues/PRs | Links je Control |

## 3. Mapping: CRA Themenblock → Umsetzung → Evidenz

> Fülle pro Block mindestens 1–3 konkrete Links/Artefakte aus.

### 3.1 Security-by-Design / Secure Development (Annex I Part I)

**Umsetzung (Kurz):**

**Evidenz (Links/Artefakte):**
- 

### 3.2 Vulnerability Handling / PSIRT + CVD (Annex I Part II + Art. 13/14)

**Umsetzung (Kurz):**

**Evidenz:**
- `SECURITY.md` (Kontakt + Prozess)
- Beispiel-Advisory / Ticket: 

### 3.3 Update- und Patch-Policy (Annex I + Art. 13)

**Umsetzung (Kurz):**

**Evidenz:**
- Release Notes / Changelog: 
- Signierung/Integrität (falls vorhanden): 

### 3.4 SBOM & Dependency Management (Annex I Part II)

**Umsetzung (Kurz):**

**Evidenz:**
- Workflow: `.github/workflows/cra-sbom.yml`
- SBOM Artefakt-Link: 

### 3.5 Vulnerability Monitoring & Remediation (Annex I Part II)

**Umsetzung (Kurz):**

**Evidenz:**
- Workflow: `.github/workflows/cra-osv-scan.yml`
- Fix-PR/Issue-Beispiele: 

### 3.6 Incident / Exploited Vulnerability Reporting (Art. 14)

**Umsetzung (Kurz):**

**Evidenz:**
- Incident-Runbook/Prozessdoku: 

## 4. Review / Audit Trail

| Datum | Reviewer | Ergebnis | Link |
|---|---|---|---|
|  |  |  |  |

## 5. Offene Punkte

- [ ] 
