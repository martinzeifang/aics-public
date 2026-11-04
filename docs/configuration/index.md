# Konfigurationsreferenz

Jedes Modul speichert seine Konfiguration in einer JSON-Datei im Projektstamm. Die Dateien werden beim ersten Start mit Standardwerten angelegt und können direkt bearbeitet oder über die GUI angepasst werden.

## Übersicht der Konfigurationsdateien

| Datei | Modul | Beschreibung |
|---|---|---|
| `ai_compliance_suite.config.json` | Zentraler Launcher | Erscheinungsbild, Fenstergeometrie |
| `baso.config.json` | BASO | Pfade, Prompt-Einstellungen, Batch-Größe |
| `ict.config.json` | ICT | Pfade, Reifegrad-Skala |
| `compliance.config.json` | Compliance Bewertung | Pfade, Risikomatrix-Skalen |
| `compliance_db.config.json` | Compliance-DB | Ollama-Einstellungen, FTS5-Top-K |
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

## baso.config.json

```json
{
  "paths": {
    "source_dir": "data/baso/quelle",
    "new_dir": "data/baso/neu",
    "sikos_dir": "data/shared/sikos",
    "db_path": "data/db/baso.sqlite",
    "prompts_dir": "out/baso/prompts",
    "answers_dir": "out/baso/answers",
    "filled_dir": "out/baso/filled"
  },
  "ui": {
    "evaluated_by": "Martin Zeifang",
    "top_k": 3,
    "batch_size": 20,
    "test_mode": false,
    "debug_mode": true
  },
  "prompt": {
    "header": "...",
    "style_system": "...",
    "style_service": "...",
    "system_statuses": [
      "vollständig umgesetzt",
      "nicht relevant",
      "überwiegend umgesetzt",
      "teilweise umgesetzt",
      "nicht umgesetzt"
    ],
    "service_contract_values": ["Ja", "Nein", "Nicht anwendbar"],
    "service_ops_values": ["Ja", "Nein", "Nicht anwendbar", "In Umsetzung"]
  }
}
```

### `ui`-Parameter

| Parameter | Typ | Standard | Beschreibung |
|---|---|---|---|
| `evaluated_by` | string | `"Martin Zeifang"` | Prüferkürzel in Ausgaben |
| `top_k` | integer | `3` | Ähnliche Beispiele im Prompt |
| `batch_size` | integer | `20` | Fragen pro Prompt-Datei |
| `test_mode` | boolean | `false` | Nur erste N Elemente verarbeiten |
| `debug_mode` | boolean | `true` | Debug-Log schreiben |

---

## ict.config.json

```json
{
  "paths": { "..." : "..." },
  "ui": {
    "top_k": 3,
    "batch_size": 20,
    "test_mode": false
  },
  "prompt": {
    "header": "...",
    "answer_values": ["Ja", "Nein"],
    "maturity_values": [1, 2, 3, 4]
  }
}
```

---

## compliance.config.json

```json
{
  "paths": { "..." : "..." },
  "ui": {
    "test_mode": false,
    "top_k_examples": 3
  },
  "prompt": {
    "header": "...",
    "likelihood_scale": [
      "unwahrscheinlich", "möglich", "wahrscheinlich", "sehr wahrscheinlich"
    ],
    "impact_scale": [
      "niedrig", "mittel", "hoch", "sehr hoch"
    ],
    "risk_scale": ["niedrig", "mittel", "hoch"],
    "output_schema_hint": true
  }
}
```

---

## compliance_db.config.json

```json
{
  "paths": {
    "gutachten_db_path": "data/db/gutachten.sqlite",
    "index_db_path": "data/db/compliance_db.sqlite",
    "debug_log_path": "out/compliance_db/debug.log"
  },
  "llm": {
    "provider": "ollama",
    "base_url": "http://localhost:11434",
    "model": "llama3.1",
    "timeout_s": 120,
    "top_k": 8
  },
  "ui": {
    "test_mode": false,
    "debug_mode": false
  }
}
```

### `llm`-Parameter

| Parameter | Typ | Standard | Beschreibung |
|---|---|---|---|
| `provider` | string | `"ollama"` | LLM-Provider (nur `"ollama"` unterstützt) |
| `base_url` | string | `http://localhost:11434` | Ollama API-Basis-URL |
| `model` | string | `"llama3.1"` | Ollama-Modellname |
| `timeout_s` | integer | `120` | Anfrage-Timeout in Sekunden |
| `top_k` | integer | `8` | Anzahl Kontextabschnitte für LLM |

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
