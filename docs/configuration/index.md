# Konfigurationsreferenz

Jedes Modul speichert seine Konfiguration in einer JSON-Datei im Projektstamm. Die Dateien werden beim ersten Start mit Standardwerten angelegt und können direkt bearbeitet oder über die GUI angepasst werden.

## Übersicht der Konfigurationsdateien

| Datei | Modul | Beschreibung |
|---|---|---|
| `ai_compliance_suite.config.json` | Zentraler Launcher | Erscheinungsbild, Fenstergeometrie |
| `gutachten.config.json` | Gutachten | Framework-Pfade, Bewertungsskala |

---

## ai_compliance_suite.config.json

```json
{
  "appearance": {
    "dark_mode": false
  },
  "windows": {
    "main_geometry": "1500x1300",
    "main_minsize": [1280, 820]
  }
}
```

| Schlüssel | Typ | Beschreibung |
|---|---|---|
| `appearance.dark_mode` | boolean | Dark Mode aktivieren |
| `windows.main_geometry` | string | Fenstergröße (`"BREITExHÖHE"`) |
| `windows.main_minsize` | array | Mindestgröße `[Breite, Höhe]` |

---

## gutachten.config.json

```json
{
  "paths": {
    "dora_dir": "data/dora_downloads",
    "cra_dir": "data/cra_resources",
    "nis2_dir": "data/nis2_resources",
    "iso_dir": "data/iso27001_questionnaires",
    "dsgvo_dir": "data/dsgvo_resources",
    "ai_act_dir": "data/ai_act_resources",
    "bsi_dir": "data/bsi_resources",
    "db_path": "data/db/gutachten.sqlite",
    "prompts_dir": "out/gutachten/prompts",
    "answers_dir": "out/gutachten/answers",
    "fragebogen_dir": "out/gutachten/fragebogen",
    "ausgefuellt_dir": "out/gutachten/ausgefuellt",
    "gutachten_dir": "out/gutachten/gutachten"
  },
  "ui": {
    "projekt_name": "Testprojekt",
    "frameworks": ["CRA", "ISO27001"],
    "pruefungsfokus": "...",
    "debug_mode": false,
    "test_mode": false
  },
  "prompt": {
    "fragen_header": "...",
    "gutachten_header": "...",
    "bewertung_skala": [
      "erfüllt",
      "teilweise erfüllt",
      "nicht erfüllt",
      "nicht anwendbar"
    ],
    "fragen_batch_size": 15
  }
}
```

---

## Konfiguration über die GUI

Alle konfigurierbaren Parameter können über **Bearbeiten** → **Projekteinstellungen** bzw. **Prompt-Einstellungen** in der GUI angepasst werden, ohne die JSON-Dateien direkt zu bearbeiten. Änderungen werden sofort gespeichert.

!!! tip "Tipp: Pfade"
    Alle Pfade können relativ (zum Projektstamm) oder absolut angegeben werden. Relative Pfade werden empfohlen, da die Suite dann von beliebigen Speicherorten ausführbar bleibt.
