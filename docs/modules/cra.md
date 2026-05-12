# CRA-Readiness (Cyber Resilience Act)

Das CRA-Modul unterstützt die strukturierte Gap-Analyse für Produkte mit digitalen Elementen gemäß **Regulation (EU) 2024/2847**.

## Verzeichnisstruktur

```
cra/
├── __main__.py
├── config.py
├── db.py
├── requirements.py
├── io_xlsx.py
├── report_export.py
├── repo_alignment.py
├── ci_evidence_ingest.py
├── ci_autoanswer.py
└── gui_module.py
```

## Datenhaltung

- CRA-Projekte und Bewertungen: `data/db/cra.sqlite`
- Evidence Library (Nachweise, Chunks, Mappings): `data/db/evidence.sqlite`

CRA-DB Tabellen (Auszug):

- `cra_projekte` (inkl. `meta_json`)
- `cra_bewertungen`
- `cra_owasp_checks`

## OWASP Security by Design

Im Tab **"OWASP SbD"** ist eine OWASP Proactive Controls Checkliste integriert.

- Dataset (minimal, mit Referenzen): `cra/owasp_proactive_controls.py`
- Persistenz: `cra_owasp_checks`

### Repo-Abgleich (GitHub)

Der Button **"Abgleichen"** nutzt `gh api` und prüft deterministische Repo-Signale (z.B. `SECURITY.md`, `CODEOWNERS`, `dependabot.yml`, `.github/workflows`).

Code: `cra/repo_alignment.py`

## Linked App (GitHub/GitLab)

CRA-Projekte können mit einem Repo/Projekt verknüpft werden. Die Einstellungen liegen unter:

- `cra_projekte.meta_json.linked_app`

Felder (v1):

- `provider`: `github` | `gitlab`
- `repo`: `org/repo` oder URL (GitHub) bzw. `group/project` oder Projekt-ID/URL (GitLab)
- `branch`: z.B. `cra/ai-main`
- `base_url` (GitLab, optional): z.B. `https://gitlab.com`
- `token_env` (GitLab, optional): z.B. `GITLAB_TOKEN`

## CI Evidenzen importieren

Über **"CI Evidenzen importieren"** werden die letzten erfolgreichen CI-Artefakte (SBOM/OSV/Evidence Pack) heruntergeladen und als Nachweise in die Evidence Library importiert.

- GitHub: Download via `gh run list/download`
- Import: als `ci-artifact` + sofortiges Extract/Chunking

Code: `cra/ci_evidence_ingest.py`

## CRA Auto-fill aus CI

Über **"CRA Auto-fill aus CI"** werden deterministische Prefill-Vorschläge aus CI-Evidenzen erzeugt (z.B. SBOM vorhanden, OSV Scan vorhanden) und in `prefill_suggestions` geschrieben.

Code: `cra/ci_autoanswer.py`

## Bericht: Send-to GitHub/GitLab

Im CRA-Bericht-Panel gibt es Buttons zum Senden des zuletzt erzeugten Reports in das verknüpfte Repo/Projekt.

Zielpfad (v1): `compliance/cra/reports/<projekt>/...`

## CRA-Dokumentation (CRA-ready)

Dieses Kapitel beschreibt die **dokumentarischen Erwartungen** für CRA-Readiness: „was ist gefordert“, „wie wird es im Projekt umgesetzt“, „welche Evidenz wird erwartet“.

> Hinweis: Prozessbeschreibungen sind technische Guidance und keine Rechtsberatung.

### 1) Security-by-Design / Secure Development (Annex I Part I)

**Anforderungen (typisch):** SDLC, Security Requirements, Threat Modeling, Secure Defaults, Access Control, Logging/Monitoring.

**Umsetzung im Projekt (Beispiele):**
- OWASP SbD Checkliste im CRA-Modul (Status + Kommentar + Evidenzverweise)
- deterministischer Repo-Abgleich (z.B. `SECURITY.md`, `CODEOWNERS`, Workflows)

**Erwartete Evidenz (Beispiele):**
- Architektur-/Datenfluss-Doku: `docs/architecture/*`
- Security-by-Design Status: `data/db/cra.sqlite` (`cra_owasp_checks`)
- Reifegrad/Bewertungen: `data/db/cra.sqlite` (`cra_bewertungen`)

### 2) Vulnerability Handling / PSIRT + CVD (Annex I Part II + Art. 13/14)

**Anforderungen (typisch):** definierter Intake-/Triage-/Fix-/Release-Prozess, Kommunikationskanäle, Disclosure.

**Umsetzung:**
- Prozessgrundlage in `SECURITY.md` (Vulnerability Reporting + CVD)

**Erwartete Evidenz:**
- Security Advisory / privates Ticket
- Fix-PR + Release Notes

### 3) Update- und Patch-Policy (Annex I + Art. 13)

**Anforderungen (typisch):** Support-Zeiträume, Update-Kanäle, Integrität/Signierung, Rollback, Advisories.

**Erwartete Evidenz (Beispiele):**
- Releases/Tags + Changelog
- CI-Artefakte (z.B. Evidence Pack)

### 4) SBOM & Dependency Management (Annex I Part II)

**Anforderungen (typisch):** SBOM-Erzeugung (CycloneDX/SPDX), Ablageort, Aktualisierung.

**Umsetzung:**
- GitHub Actions Workflows (siehe CRA-Workflow) erzeugen SBOM/OSV/Evidence Pack.

**Erwartete Evidenz:**
- Workflow-Dateien: `.github/workflows/cra-*.yml`
- Importierte CI-Artefakte in Evidence Library: `data/db/evidence.sqlite`

### 5) Vulnerability Monitoring & Remediation (Annex I Part II)

**Anforderungen (typisch):** kontinuierliche Überwachung (z.B. OSV/Dependency Scans), Reaktionszeiten, Ticketing.

**Umsetzung:**
- OSV/Scan-Artefakte können per CRA-Modul importiert werden.

**Erwartete Evidenz:**
- Scan-Reports (CI)
- Issues/PRs zur Behebung

### 6) Incident / Exploited Vulnerability Reporting (Art. 14)

**Technischer Prozess (Beispiel):**
1. Incident Intake (Quelle, Zeitpunkt, betroffene Version)
2. Triage (Auswirkung, Exploitbarkeit, Daten/Scope)
3. Mitigation (Workaround/Fix)
4. Kommunikation (Advisory/Release Notes)
5. Nachweisablage (Evidence Pack / Issue-Verknüpfung)

### 7) CRA Compliance Pack (Template)

Für Review/Audit: nutze das Template als strukturierte Nachweisablage.

- Template: `docs/templates/cra-compliance-pack.md`
