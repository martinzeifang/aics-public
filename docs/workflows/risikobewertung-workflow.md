# Risikobewertung Workflow

Ablauf zur Durchführung einer strukturierten Risikoanalyse mit Framework-Unterstützung und optionalem KI-Assistenten.

## Framework wählen

Wähle das passende Framework für deine Risikoanalyse:

| Framework | Geeignet für |
|---|---|
| **Financial Impact (FI)** | Schnelle Risikopriorisierung, finanzielle Folgenabschätzung |
| **STRIDE** | Software- und Systembedrohungsmodellierung |
| **CVSS** | Schwachstellen-Scoring (Kompatibilität mit CVE-Datenbanken) |
| **OCTAVE** | Organisationsweite Risikobewertung mit Akteur-/Motivanalyse |

## Schritt 1: Suite starten

```bash
python -m bnits_suite
```

Tab **Risikobewertung** auswählen.

## Schritt 2: Neues Risiko anlegen

1. **Neue Bewertung** klicken
2. Framework aus Dropdown wählen
3. Risikobezeichnung eingeben

## Schritt 3: KI-Assistent nutzen (optional)

1. **KI-Assistent** klicken
2. Im Dialog: Risikobeschreibung in natürlicher Sprache eingeben (z.B. "Phishing-Angriff auf Mitarbeiter per E-Mail mit Credential-Diebstahl")
3. Ollama generiert strukturierte Risikofelder
4. Felder werden automatisch ins Formular übertragen
5. Manuell prüfen und ggf. anpassen

!!! note "Ollama erforderlich"
    Der KI-Assistent benötigt ein laufendes Ollama mit llama3.1. Ohne Ollama können alle Felder manuell ausgefüllt werden.

## Schritt 4: Risikofelder ausfüllen

### Financial Impact

| Feld | Werte |
|---|---|
| Wahrscheinlichkeit | 1 (Unwahrscheinlich) – 4 (Sicher) |
| Finanzieller Schaden | 1 (Niedrig) – 4 (Kritisch) |

### STRIDE

Für jede der 6 Bedrohungskategorien:

| Feld | Werte |
|---|---|
| Kategorie | S / T / R / I / D / E |
| Wahrscheinlichkeit | 1–5 |
| Auswirkung | 1–5 |

### CVSS

Exploitability- und Impact-Metriken nach CVSS-Schema (Auswahllisten).

### OCTAVE

| Feld | Optionen |
|---|---|
| Akteur | Intern / Extern / Partner |
| Motiv | Finanziell / Ideologisch / Zufällig / Wettbewerb |
| Zugang | Direkter Zugang / Indirekt / Physisch |
| Wahrscheinlichkeit | 1–5 |
| Auswirkung | 1–5 |

## Schritt 5: Score berechnen

Der Risikoscore wird **automatisch** beim Ausfüllen der Felder berechnet und angezeigt:
- Numerischer Score
- Risikostufe (Niedrig / Mittel / Hoch / Kritisch)
- Detailberechnung

## Schritt 6: Weitere Risiken hinzufügen

1. **Neue Bewertung** klicken → nächstes Risiko erfassen
2. Mit den Navigationspfeilen zwischen Risiken wechseln

## Schritt 7: Bericht exportieren

1. **Exportieren** klicken
2. Format wählen:

=== "Excel (XLSX)"
    Tabellarische Übersicht aller Risiken, sortiert nach Score.

=== "Word (DOCX)"
    Formatierter Bericht mit:
    - Zusammenfassung der kritischsten Risiken
    - Framework-Erläuterungen
    - Detailtabellen
    - Scoring-Legende

=== "JSON"
    Maschinenlesbarer Export für Weiterverarbeitung.

## Beispiel: CVSS-Bewertung einer Schwachstelle

```
Risiko: Ungepatchte RCE-Schwachstelle im Webserver (CVE-2024-XXXX)

CVSS-Felder:
  Angriffsvektor:        Netzwerk
  Angriffskomplexität:   Niedrig
  Benötigte Rechte:      Keine
  Benutzerinteraktion:   Keine
  Umfang:                Verändert
  Vertraulichkeit:       Hoch
  Integrität:            Hoch
  Verfügbarkeit:         Hoch

→ CVSS Score: 10.0 – KRITISCH
```
