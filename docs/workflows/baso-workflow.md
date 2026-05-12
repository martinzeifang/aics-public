# BASO Workflow

Vollständiger Ablauf zum Befüllen eines BASO/ForumISM-Fragebogens mit KI-Unterstützung.

## Voraussetzungen

- [ ] Python und Abhängigkeiten installiert (`pip install -r requirements.txt`)
- [ ] Mindestens ein bereits ausgefüllter BASO-Fragebogen als Referenz (XLSX)
- [ ] Neuer BASO-Fragebogen (XLSX, noch nicht ausgefüllt)
- [ ] ChatGPT-Zugang (Web)

## Schritt 1: Datenbank aufbauen

Lese bereits ausgefüllte Fragebögen ein, damit das System auf frühere Antworten zugreifen kann.

=== "GUI"

    1. Suite starten: `python -m bnits_suite`
    2. Tab **BASO** auswählen
    3. **Fragebögen einlesen** klicken
    4. **Sikos einlesen** klicken (sofern Sicherheitskonzepte vorhanden)

=== "CLI"

    ```bash
    python -m baso ingest \
        --source data/baso/quelle \
        --db data/db/baso.sqlite

    python -m baso ingest-sikos \
        --sikos data/shared/sikos \
        --db data/db/baso.sqlite
    ```

!!! tip "Einmalig nötig"
    Dieser Schritt muss nur einmal (oder nach Hinzufügen neuer Quelldaten) durchgeführt werden.

## Schritt 2: Neuen Fragebogen ablegen

1. Neuen BASO-Fragebogen (XLSX) in `data/baso/neu/` ablegen
2. Dateiname ist beliebig, Endung muss `.xlsx` sein

## Schritt 3: Prompts erstellen

Das System analysiert den neuen Fragebogen und sucht ähnliche, bereits beantwortete Fragen als Kontext.

=== "GUI"

    1. **Prompts erstellen** klicken
    2. Fortschrittsanzeige abwarten

=== "CLI"

    ```bash
    python -m baso prepare \
        --new data/baso/neu \
        --db data/db/baso.sqlite \
        --out out/baso/prompts \
        --answers-out out/baso/answers \
        --top 3 \
        --batch-size 20
    ```

**Ergebnis:**
- `out/baso/prompts/<dateiname>.part001.md` (Prompt-Datei)
- `out/baso/prompts/<dateiname>.part002.md` (falls mehr als 20 Fragen)
- `out/baso/answers/<dateiname>.part001.json` (leere Antwortdatei)

## Schritt 4: Prompt in ChatGPT einfügen

1. Prompt-Datei (`*.md`) öffnen
2. Gesamten Inhalt kopieren
3. In ChatGPT (Web) einfügen und absenden
4. JSON-Antwort von ChatGPT kopieren

!!! info "Mehrteilige Prompts"
    Falls der Fragebogen mehr als `batch_size` Fragen hat, entstehen mehrere `.partNNN.md`-Dateien. Jede muss separat in ChatGPT eingefügt werden.

## Schritt 5: JSON-Antwort speichern

Die JSON-Antwort von ChatGPT in die zugehörige Antwortdatei einfügen:

- `out/baso/answers/<dateiname>.part001.json` ← JSON hier einfügen
- `out/baso/answers/<dateiname>.part002.json` ← JSON für Teil 2

Die leere Antwortdatei wurde in Schritt 3 automatisch angelegt.

## Schritt 6: Fragebogen befüllen

=== "GUI"

    1. **Fragebögen befüllen** klicken (grüner Button)
    2. Ausgabe prüfen

=== "CLI"

    ```bash
    python -m baso apply \
        --new data/baso/neu \
        --answers out/baso/answers \
        --out out/baso/filled \
        --by "M. Zeifang"
    ```

**Ergebnis:** Befüllter Fragebogen in `out/baso/filled/<dateiname>.xlsx`

## Ergebnis-XLSX

Der befüllte Fragebogen enthält:
- Original-Fragen und -Struktur unverändert
- Ausgefüllte Antwortfelder (Umsetzungsstatus, Bemerkungen)
- Schutzziel-Zuordnungen (bei Service-Layout in Bemerkung-Spalte)
- Prüferkürzel (`--by`-Parameter)

## Häufige Probleme

| Problem | Lösung |
|---|---|
| Prompt-Datei zu groß für ChatGPT | `--batch-size` auf `10` oder `15` reduzieren |
| JSON-Antwort ungültig | JSON in Validator prüfen; ChatGPT ggf. erneut befragen |
| Falsche Spalten erkannt | Layout prüfen: "system" vs. "service" |
| Keine ähnlichen Beispiele | Mehr Quelldaten einlesen (`ingest`) |
