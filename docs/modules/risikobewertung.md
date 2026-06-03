# Risikobewertung-Modul

Strukturierte Risikoanalysen nach vier etablierten Frameworks
(Financial Impact, STRIDE, CVSS, OCTAVE) mit optionalem KI-Assistenten.

## Konfiguration

| Einstellung | Standard | Beschreibung |
|---|---|---|
| Datenbank | `data/db/risikobewertung.sqlite` | Bewertungen, Risiken, Projekte |
| Ollama-URL | `http://localhost:11434` | Lokaler LLM-Endpunkt (optional) |
| Ollama-Modell | `llama3.1` | Default-Modell für KI-Assistent |

Einstellbar im Admin-Bereich → **KI-Modelle** oder per Environment-Variable.

## Export: JSON + Markdown

Im Bericht-Panel kann ein diff-freundlicher Export erzeugt werden:

- `out/risikobewertung/exports/<projekt>/risk-export.json`
- `out/risikobewertung/exports/<projekt>/risk-export.md`

Schema: `ai-compliance-suite/risk-export/v1`.

## Publishing nach GitHub/GitLab

Im Bericht-Panel können erzeugte Reports direkt in ein verknüpftes
Repo/Projekt gepublisht werden:

1. **Einstellungen…**: Provider/Repo/Branch/Path; für GitLab zusätzlich
   `base_url` + `token_env`.
2. **Senden**: Upload via GitHub-API (`gh api`) oder GitLab REST API.

Persistenz pro Projekt: `rb_projekte.meta_json.vcs_publish`.

## Scoring-Frameworks

### Financial Impact (FI)

Risikoscore aus **Wahrscheinlichkeit × Schaden**:

| | Niedrig (1) | Mittel (2) | Hoch (3) | Kritisch (4) |
|---|---|---|---|---|
| **Unwahrscheinlich (1)** | 1 – Niedrig | 2 – Niedrig | 3 – Mittel | 4 – Mittel |
| **Möglich (2)** | 2 – Niedrig | 4 – Mittel | 6 – Hoch | 8 – Hoch |
| **Wahrscheinlich (3)** | 3 – Mittel | 6 – Hoch | 9 – Hoch | 12 – Kritisch |
| **Sicher (4)** | 4 – Mittel | 8 – Hoch | 12 – Kritisch | 16 – Kritisch |

### STRIDE

Bewertet Bedrohungen nach sechs Kategorien (jeweils
Wahrscheinlichkeit 1–5 × Auswirkung 1–5):

| Kategorie | Beschreibung |
|---|---|
| **S**poofing | Identitätsvortäuschung |
| **T**ampering | Manipulation von Daten |
| **R**epudiation | Abstreitbarkeit von Aktionen |
| **I**nformation Disclosure | Informationspreisgabe |
| **D**enial of Service | Dienstverweigerung |
| **E**levation of Privilege | Rechteeskalation |

### CVSS

Score 0–10 aus folgenden Metriken:

| Metrik | Optionen |
|---|---|
| Angriffsvektor | Netzwerk / Benachbart / Lokal / Physisch |
| Angriffskomplexität | Niedrig / Hoch |
| Benötigte Rechte | Keine / Niedrig / Hoch |
| Benutzerinteraktion | Keine / Erforderlich |
| Umfang | Unverändert / Verändert |
| Vertraulichkeit | Keine / Niedrig / Hoch |
| Integrität | Keine / Niedrig / Hoch |
| Verfügbarkeit | Keine / Niedrig / Hoch |

**Score-Interpretation:** 0.1–3.9 Niedrig · 4.0–6.9 Mittel ·
7.0–8.9 Hoch · 9.0–10.0 Kritisch

### OCTAVE

Bewertet Bedrohungsszenarien nach:

| Faktor | Beschreibung |
|---|---|
| Akteur | Intern / Extern / Partner |
| Motiv | Finanziell / Ideologisch / Zufällig |
| Zugang | Direkt / Indirekt / Physisch |
| Wahrscheinlichkeit | 1–5 (Likert-Skala) |
| Auswirkung | 1–5 (Likert-Skala) |

## KI-Assistent

Ein Wizard nimmt eine Risikobeschreibung in natürlicher Sprache
entgegen, sendet sie an Ollama (lokal) oder einen OpenAI-kompatiblen
Endpunkt und befüllt das Bewertungsformular mit vorgeschlagenen Werten.

## Export-Formate

| Format | Inhalt |
|---|---|
| **XLSX** | Strukturierte Tabelle mit allen Risiken und Scores |
| **DOCX** | Formatierter Bericht inkl. Risikomatrix-Diagramm |
| **JSON** | Maschinenlesbarer Export aller Bewertungsdaten |

Erreichbar in der Web-App unter `/risikobewertung`. Für die
KI-Unterstützung siehe [Ollama-Setup](../web/ollama-setup.md).
