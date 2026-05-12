# AI-Act-Workflow

## 1. Projekt anlegen

- Modul öffnen: "AI-ACT-Readiness"
- Links `+ Neu` und Projektname vergeben

## 2. Repo verknuepfen

- Tab "Integration"
- Provider: `github` (CI Import ist aktuell GitHub-only)
- Repo: `owner/name`
- Branch: z. B. `ai-act/ai-main`
- Speichern

## 3. CI-Evidenz importieren

- Tab "Integration" -> "CI Artifacts importieren (GitHub)"
- Der Import lädt die Artifacts des letzten erfolgreichen Runs und schreibt sie in die Evidence Library.

## 4. Auto-fill Vorschläge erzeugen

- Tab "Anforderungen"
- "Auto-fill aus Repo" (Datei-/Workflow-Signale via `gh api`)
- "Auto-fill aus CI-Evidenz" (SBOM/OSV/Evidence-Pack Artifacts)
- Danach: "Vorschlaege pruefen..." und akzeptieren/ablehnen

## 5. Report exportieren

- Tab "Bericht" -> "Markdown export"
- Output: `out/ai_act/berichte/ai-act-report_<projekt>.md`
