# Entwicklungsumgebung einrichten

## Systemvoraussetzungen

| Komponente | Version | Pflicht |
|---|---|---|
| Python | ≥ 3.11 | ✓ |
| Tkinter | (Systempaket) | ✓ |
| Git | beliebig | empfohlen |
| Ollama | beliebig | nur für Compliance-DB + Risikobewertung |

## Python installieren

=== "Windows"

    Python von [python.org](https://www.python.org/downloads/) herunterladen und installieren.
    
    Tkinter ist in der offiziellen Windows-Distribution enthalten.

=== "Ubuntu/Debian"

    ```bash
    sudo apt update
    sudo apt install python3.11 python3.11-venv python3-tk
    ```

=== "Fedora"

    ```bash
    sudo dnf install python3.11 python3-tkinter
    ```

=== "Arch Linux"

    ```bash
    sudo pacman -S python tk
    ```

=== "macOS"

    ```bash
    brew install python@3.11
    brew install tcl-tk
    ```

## Repository klonen

```bash
git clone https://github.com/martinzeifang/AI_Compliance_Suite.git
cd AI_Compliance_Suite
```

## Virtuelle Umgebung erstellen

```bash
python -m venv .venv

# Aktivieren (Windows)
.venv\Scripts\activate

# Aktivieren (Linux/macOS)
source .venv/bin/activate
```

## Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

## Ollama installieren (optional)

Nur notwendig für Compliance-DB (RAG-Suche) und Risikobewertung (KI-Assistent).

=== "Windows"

    ```bat
    install-ollama.bat
    ```

=== "Linux"

    ```bash
    chmod +x install-ollama.sh
    ./install-ollama.sh
    ```

### Modell laden

```bash
ollama pull llama3.1
```

## Suite starten

```bash
python -m bnits_suite
```

=== "Windows (Batch)"

    ```bat
    start-suite.bat
    ```

=== "Linux (Shell)"

    ```bash
    ./start-suite.sh
    ```

## Desktop-Integration (Linux)

```bash
chmod +x install-desktop-entry.sh
./install-desktop-entry.sh
```

Erstellt einen `.desktop`-Eintrag im Anwendungsmenü.

## Datenbankdateien initialisieren

Die SQLite-Datenbanken werden beim ersten Start eines Moduls automatisch angelegt. Es ist keine manuelle Initialisierung nötig.

## Verzeichnisstruktur anlegen

Eingabeverzeichnisse werden ebenfalls automatisch angelegt, können aber auch manuell erstellt werden:

```bash
mkdir -p data/baso/{quelle,neu}
mkdir -p data/ict/{quelle,neu,berichte}
mkdir -p data/compliance/berichte
mkdir -p data/shared/sikos
mkdir -p data/db
mkdir -p out/{baso,ict,compliance,gutachten,risikobewertung}
```

## Dokumentation lokal bauen

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

Die Dokumentation ist dann unter [http://localhost:8000](http://localhost:8000) erreichbar.

## GitHub Pages Deployment

Die Dokumentation wird automatisch bei jedem Push auf `main` per GitHub Actions deployed (`.github/workflows/docs.yml`).

**Voraussetzungen in GitHub:**

1. Repository-Einstellungen → Pages → Source: **GitHub Actions**
2. Branch `main` schützen (optional, empfohlen)

## Abhängigkeiten aktualisieren

```bash
pip install --upgrade -r requirements.txt
```

## Bekannte Einschränkungen

| Plattform | Einschränkung |
|---|---|
| Windows | Tkinter-Fonts können leicht abweichen |
| macOS | Tkinter benötigt ggf. separat installiertes `tcl-tk` |
| Linux Wayland | Tkinter läuft über XWayland (funktioniert, aber kein natives Wayland) |

## Code-Qualität

Das Projekt hat keine formalen Lint/Format-Konfigurationsdateien. Empfohlene Werkzeuge:

```bash
pip install ruff mypy

# Linting
ruff check .

# Typ-Prüfung
mypy --ignore-missing-imports .
```
