# Risikobewertung-Modul

Das Risikobewertung-Modul bietet strukturierte Risikoanalysen nach vier etablierten Frameworks: Financial Impact, STRIDE, CVSS und OCTAVE. Ein KI-Assistent (Ollama) unterstützt bei der Risikobeschreibung.

## Verzeichnisstruktur

```
risikobewertung/
├── __init__.py
├── __main__.py
├── config.py            # Ollama-Konfiguration
├── db.py                # SQLite-Schema
├── frameworks.py        # Scoring-Frameworks (FI, STRIDE, CVSS, OCTAVE)
├── prompts.py           # Ollama-Prompt-Generierung
├── io_xlsx.py           # Excel-Import/-Export
├── report_export.py     # Berichte (XLSX, DOCX, JSON)
└── gui_module.py        # Tkinter-GUI (RisikobewertungModuleFrame)
```

## Konfiguration

Datei: `risikobewertung.config.json` (Defaults in `risikobewertung/config.py`)

| Einstellung | Standard | Beschreibung |
|---|---|---|
| Ollama URL | `http://localhost:11434` | Lokaler LLM-Endpunkt |
| Ollama Modell | `llama3.1` | Verwendetes Modell |
| DB-Pfad | `data/db/risikobewertung.sqlite` | Datenbank |

## Export: JSON + Markdown

Im Bericht-Panel kann ein diff-freundlicher Export erzeugt werden:

- `out/risikobewertung/exports/<projekt>/risk-export.json`
- `out/risikobewertung/exports/<projekt>/risk-export.md`

Schema: `ai-compliance-suite/risk-export/v1` (siehe `risikobewertung/risk_export.py`).

## Publishing nach GitHub/GitLab

Im Bericht-Panel gibt es Publishing-Funktionen:

1. **Einstellungen…**: Provider/Repo/Branch/Path; für GitLab zusätzlich `base_url` + `token_env`.
2. **Senden**: Upload via GitHub (`gh api`) oder GitLab REST API.

Persistenz pro Projekt: `rb_projekte.meta_json.vcs_publish`.

## Scoring-Frameworks

`risikobewertung/frameworks.py`

### Financial Impact (FI)

Berechnet den Risikoscore aus **Wahrscheinlichkeit × Schaden**:

| | Niedrig (1) | Mittel (2) | Hoch (3) | Kritisch (4) |
|---|---|---|---|---|
| **Unwahrscheinlich (1)** | 1 – Niedrig | 2 – Niedrig | 3 – Mittel | 4 – Mittel |
| **Möglich (2)** | 2 – Niedrig | 4 – Mittel | 6 – Hoch | 8 – Hoch |
| **Wahrscheinlich (3)** | 3 – Mittel | 6 – Hoch | 9 – Hoch | 12 – Kritisch |
| **Sicher (4)** | 4 – Mittel | 8 – Hoch | 12 – Kritisch | 16 – Kritisch |

### STRIDE

Bewertet Bedrohungen nach sechs Kategorien:

| Kategorie | Beschreibung |
|---|---|
| **S**poofing | Identitätsvortäuschung |
| **T**ampering | Manipulation von Daten |
| **R**epudiation | Abstreitbarkeit von Aktionen |
| **I**nformation Disclosure | Informationspreisgabe |
| **D**enial of Service | Dienstverweigerung |
| **E**levation of Privilege | Rechteeskalation |

Jede Kategorie wird mit **Wahrscheinlichkeit (1–5) × Auswirkung (1–5)** bewertet.

### CVSS (Common Vulnerability Scoring System)

Berechnet einen Score 0–10 aus:

| Metrik | Optionen |
|---|---|
| **Angriffvektor** | Netzwerk / Benachbart / Lokal / Physisch |
| **Angriffskomplexität** | Niedrig / Hoch |
| **Benötigte Rechte** | Keine / Niedrig / Hoch |
| **Benutzerinteraktion** | Keine / Erforderlich |
| **Umfang** | Unverändert / Verändert |
| **Vertraulichkeit** | Keine / Niedrig / Hoch |
| **Integrität** | Keine / Niedrig / Hoch |
| **Verfügbarkeit** | Keine / Niedrig / Hoch |

**Score-Interpretation:**
- 0.0 – Kein Risiko
- 0.1–3.9 – Niedrig
- 4.0–6.9 – Mittel
- 7.0–8.9 – Hoch
- 9.0–10.0 – Kritisch

### OCTAVE (Operationally Critical Threat, Asset, and Vulnerability Evaluation)

Bewertet Bedrohungsszenarien nach:

| Faktor | Beschreibung |
|---|---|
| **Akteur** | Intern / Extern / Partner |
| **Motiv** | Finanziell / Ideologisch / Zufällig |
| **Zugang** | Direkter Zugang / Indirekt / Physisch |
| **Wahrscheinlichkeit** | 1–5 (Likert-Skala) |
| **Auswirkung** | 1–5 (Likert-Skala) |

## Framework-API

```python
def framework_felder(fw: str) -> list[dict]:
    """Gibt Eingabefeld-Definitionen für ein Framework zurück.
    
    Jedes dict enthält: key, label, type, options (bei Auswahl)
    """

def berechne_risiko(fw: str, d: dict) -> tuple[int, str, str]:
    """Berechnet Risikoscore.
    
    Returns:
        (score: int, label: str, detail: str)
        z.B. (9, "Hoch", "Wahrscheinlichkeit: 3, Auswirkung: 3")
    """
```

## KI-Assistent

`risikobewertung/_AssistentDialog` (in `gui_module.py`)

Ein modaler Dialog, der:
1. Risikobeschreibung vom Benutzer entgegennimmt
2. Strukturierten Prompt an Ollama sendet
3. Ollamas Antwort als vorausgefüllte Felder in das Hauptformular überträgt

```python
class _AssistentDialog(tk.Toplevel):
    """Modaler Wizard für KI-gestützte Risikobeschreibung."""
```

## Export-Formate

`risikobewertung/report_export.py`

| Format | Inhalt |
|---|---|
| **XLSX** | Strukturierte Tabelle mit allen Risiken und Scores |
| **DOCX** | Formatierter Bericht mit Risikomatrix-Diagramm |
| **JSON** | Maschinenlesbarer Export aller Bewertungsdaten |

### DOCX-Bericht enthält:
- Deckblatt
- Zusammenfassung (höchste Risiken)
- Framework-Erläuterungen
- Detailtabellen je Risiko
- Scoring-Legende

## GUI-Funktionen

| Funktion | Beschreibung |
|---|---|
| Neue Bewertung | Leeres Formular für neue Risikoerfassung |
| KI-Assistent | Öffnet `_AssistentDialog` für Ollama-Unterstützung |
| Framework wechseln | Wechselt zwischen FI / STRIDE / CVSS / OCTAVE |
| Navigation | Vor/Zurück zwischen gespeicherten Risiken |
| Exportieren | Wählt Format (XLSX / DOCX / JSON) |

## Voraussetzungen

Ollama muss laufen. Das Modul versucht beim Start Ollama zu erkennen und zeigt ggf. einen Hinweis.

```bash
# Ollama starten (Windows)
install-ollama.bat

# Ollama starten (Linux)
./install-ollama.sh

# Modell laden
ollama pull llama3.1
```
