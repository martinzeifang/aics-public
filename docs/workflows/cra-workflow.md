# CRA-Workflow

Dieser Workflow beschreibt die empfohlene Nutzung des CRA-Readiness Moduls inklusive CI-Evidence und Publishing.

## 1. CRA-Projekt anlegen

1. Modul **CRA-Readiness** öffnen.
2. Projekt auswählen oder **"+ Neu"**.

Die operativen Daten liegen in `data/db/cra.sqlite`.

## 2. OWASP SbD + Repo verknüpfen

1. Tab **"OWASP SbD"** öffnen.
2. `Plattform` wählen (GitHub/GitLab).
3. `Repo / Projekt` und `Branch/Ref` setzen.
4. Optional (GitLab): `GitLab URL` + `Token Env` setzen.

## 3. Repo-Abgleich (GitHub)

1. **"Abgleichen"** ausführen.
2. Ergebnisse werden in `cra_owasp_checks` gespeichert.

Hinweis: Der Abgleich ist deterministisch und basiert auf Repo-Dateien/Settings, nicht auf KI.

## 4. CI Evidenzen importieren

1. **"CI Evidenzen importieren"** ausführen.
2. Artifacts (SBOM/OSV/Evidence Pack) werden in `data/db/evidence.sqlite` importiert.

Für GitHub ist eine `gh`-Session erforderlich (`gh auth login`).

## 5. CRA Auto-fill aus CI

1. **"CRA Auto-fill aus CI"** ausführen.
2. Prefill-Vorschläge werden erzeugt.
3. Über **"Vorschläge prüfen…"** können Vorschläge übernommen werden.

## 6. Bericht erzeugen + senden

1. Tab **"Bericht erstellen"** öffnen.
2. Word/PDF erzeugen.
3. Optional: **"Nach GitHub senden"** / **"Nach GitLab senden"**.

## 7. CRA Compliance Pack (Nachweisstruktur)

Für Audit/Review empfiehlt sich ein „CRA Compliance Pack“ (Mapping CRA-Anforderung → Artefakte/Evidenz).

- Template: `docs/templates/cra-compliance-pack.md`

## GitHub Actions (CRA Automation)

Auf Branch `cra/ai-main` existieren Workflows für:

- SBOM: `.github/workflows/cra-sbom.yml`
- Evidence Pack: `.github/workflows/cra-evidence-pack.yml`
- OSV Scan: `.github/workflows/cra-osv-scan.yml`
- Risk Export Artifacts: `.github/workflows/cra-risk-export-artifact.yml`
