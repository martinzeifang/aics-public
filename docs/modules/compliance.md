# Compliance Bewertung (CVE-Risikoanalyse)

Das Compliance-Modul unterstützt die strukturierte Bewertung von CVE-Schwachstellen und Sicherheitsvorfällen auf Basis von Quartalsberichten und Sicherheitskonzepten.

## Verzeichnisstruktur

```
compliance/
├── __init__.py
├── config.py            # Konfiguration + Risikomatrix-Skalen
├── db.py                # SQLite-Schema + CRUD
├── prompts.py           # PromptSpec + Prompt-Generierung
├── risk_matrix.py       # Risikomatrix-Berechnung
├── dateutil.py          # Datumsverarbeitung
├── word_export.py       # DOCX-Export der Bewertung
├── standalone.py        # Standalone-Einstiegspunkt
└── gui_module.py        # Tkinter-GUI (ComplianceModuleFrame)
```

## Konfiguration

Datei: `compliance.config.json`

=== "Pfade"

    | Schlüssel | Standard |
    |---|---|
    | `paths.reports_dir` | `data/compliance/berichte` |
    | `paths.sikos_dir` | `data/shared/sikos` |
    | `paths.db_path` | `data/db/compliance.sqlite` |
    | `paths.prompts_dir` | `out/compliance/prompts` |
    | `paths.answers_dir` | `out/compliance/answers` |

=== "Risikomatrix"

    | Schlüssel | Werte |
    |---|---|
    | `prompt.likelihood_scale` | `["unwahrscheinlich", "möglich", "wahrscheinlich", "sehr wahrscheinlich"]` |
    | `prompt.impact_scale` | `["niedrig", "mittel", "hoch", "sehr hoch"]` |
    | `prompt.risk_scale` | `["niedrig", "mittel", "hoch"]` |

## Risikomatrix

`compliance/risk_matrix.py` berechnet den Risikoscore aus Eintrittswahrscheinlichkeit und Schadenspotenzial:

|  | Niedrig | Mittel | Hoch | Sehr hoch |
|---|---|---|---|---|
| **Unwahrscheinlich** | Niedrig | Niedrig | Mittel | Mittel |
| **Möglich** | Niedrig | Mittel | Hoch | Hoch |
| **Wahrscheinlich** | Mittel | Hoch | Hoch | Hoch |
| **Sehr wahrscheinlich** | Mittel | Hoch | Hoch | Hoch |

## Datenmodell (Prompt-Spezifikation)

```python
@dataclass
class PromptSpec:
    hersteller: str                  # Betroffener Hersteller/Produkt
    cve_nummern: str                 # CVE-Nummern (z.B. "CVE-2024-1234")
    beschreibung_mitre: str          # MITRE-CVE-Beschreibung
    datum: str | None                # Bewertungsdatum
    beispiel_stellungnahmen: list    # Ähnliche frühere Bewertungen
    beispiel_siko_absaetze: list     # Relevante Siko-Absätze
```

## Gespeicherte Bewertungsstruktur

Jede abgeschlossene Bewertung wird in `compliance_assessments` gespeichert:

```json
{
  "zusammenfassung": "...",
  "stellungnahme": "...",
  "eintrittswahrscheinlichkeit": "möglich",
  "schadenspotenzial": "hoch",
  "risikowert": 3,
  "quellen": ["CVE-2024-1234", "BSI-Advisory-2024-001"]
}
```

## Word-Export

`compliance/word_export.py` erzeugt ein formatiertes DOCX mit:
- Titelseite (Hersteller, CVE-Nummern, Datum)
- Risikomatrix-Visualisierung
- Zusammenfassung
- Detaillierte Stellungnahme
- Quellenverzeichnis

## GUI-Funktionen

- **Berichte einlesen**: Quartalsberichte (DOCX) in DB importieren
- **Sikos einlesen**: Sicherheitskonzepte importieren
- **Neue Bewertung**: CVE-Eingabe → Prompt-Generierung
- **Antwort importieren**: JSON-Antwort von ChatGPT einlesen
- **Als Word exportieren**: DOCX-Bericht erstellen
- **Risikomatrix-Viewer**: Übersicht aller gespeicherten Bewertungen
