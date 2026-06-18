# CRA-Readiness (Cyber Resilience Act)

Das CRA-Modul unterstützt die strukturierte Gap-Analyse für Produkte
mit digitalen Elementen gemäß **Regulation (EU) 2024/2847**.

## Funktionen

- **Anforderungsbewertung**: 32 CRA-Anforderungen mit Erfüllungsgrad,
  Kommentaren und Evidenz-Verknüpfungen
- **OWASP Security by Design**: Eingebaute Checkliste der OWASP
  Proactive Controls (10 Punkte) mit Status + Kommentaren + Quellen
- **Repo-Scan**: Deterministische Prüfung verknüpfter GitHub-/GitLab-Repos
  auf typische CRA-Signale (`SECURITY.md`, `CODEOWNERS`, `dependabot.yml`,
  CI-Workflows, SBOM/OSV-Artefakte)
- **CI-Evidenzen importieren**: Letzte erfolgreiche CI-Artefakte
  (SBOM/OSV/Evidence Pack) automatisch als Nachweise einlesen
- **Berichte**: DOCX- und PDF-Berichte zum CRA-Reifegrad

## Datenhaltung

| Aspekt | Details |
|---|---|
| **Datenbank** | `data/db/cra.sqlite` (Projekte, Bewertungen, OWASP-Checks) |
| **Evidence-Store** | `data/db/evidence.sqlite` (Chunks, Quellen, Mappings) |
| **Eingabe** | XLSX-Fragebogen-Import, GitHub-/GitLab-Repo-Anbindung |
| **Ausgabe** | DOCX, PDF, JSON, Markdown |
| **KI** | optional (Auto-fill aus Evidence) |

## Linked App (GitHub/GitLab)

CRA-Projekte können mit einem Repo oder GitLab-Projekt verknüpft werden:

- **GitHub**: `provider: github`, `repo: org/repo`, `branch: main`
- **GitLab**: zusätzlich `base_url` (z. B. `https://gitlab.com`) und
  `token_env` (Name der Env-Var mit dem Token)

Die Einstellungen werden pro Projekt in `cra_projekte.meta_json.linked_app`
gespeichert.

## CRA-Compliance-Pack (Inhalte)

Das Modul ist auf folgende Compliance-Bausteine zugeschnitten:

| Bereich | CRA-Bezug | Was die Suite unterstützt |
|---|---|---|
| Security-by-Design / Secure Development | Annex I Part I | OWASP-Checkliste, Repo-Abgleich, Status + Kommentar |
| Vulnerability Handling (PSIRT / CVD) | Annex I Part II, Art. 13/14 | Prozess-Anker via `SECURITY.md`-Prüfung |
| Update- und Patch-Policy | Annex I + Art. 13 | Releases/Tags-Auswertung |
| SBOM & Dependency Management | Annex I Part II | CI-Artefakt-Import (CycloneDX/SPDX, OSV) |
| Vulnerability Monitoring & Remediation | Annex I Part II | OSV-Scan-Auswertung |
| Incident / Exploited Vulnerability Reporting | Art. 14 | Evidence-Pack-Ablage, Issue-Verknüpfung |

> Hinweis: Die Prozessbeschreibungen sind technische Guidance und
> keine Rechtsberatung.
