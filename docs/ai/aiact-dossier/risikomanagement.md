# Risikomanagement-System (AIA-HR-01 · Art. 9)

Das Risikomanagement der KI-Funktionen läuft über den gesamten Lebenszyklus in vier Schritten
(Art. 9 Abs. 2 a–d): **identifizieren → bewerten → behandeln → überprüfen**.

## Verfahren

1. **Identifikation** — bei jeder neuen oder geänderten KI-Funktion (Issue-First-Workflow,
   Pflichtfeld „KI-relevant" im Review, siehe [Change-Management](qms-change-management.md)).
2. **Bewertung** — Eintrittswahrscheinlichkeit × Auswirkung nach der Bewertungsart **EU-AI-Act**
   (5×5) im Modul *Risikobewertung* der Suite (Dogfooding). Das Register unten ist der Stand
   dieses Dossiers; maßgeblich ist das verknüpfte Risikobewertungs-Projekt der AI-Act-Bewertung
   der Suite (Verknüpfung direkt an AIA-HR-01, #1561).
3. **Behandlung** — Maßnahmen werden als Issues umgesetzt und im Register referenziert.
4. **Überprüfung** — bei jedem Release mit KI-Bezug und mindestens jährlich; Restrisiken werden
   dokumentiert und vom Produktverantwortlichen akzeptiert (Art. 9 Abs. 5).

## KI-Risikoregister

| # | Risiko | Phase | Behandlung (im Code nachweisbar) | Restrisiko |
|---|---|---|---|---|
| R1 | **Halluzinierte/falsche Bewertung** wird ungeprüft übernommen | Betrieb | KI-Ausgaben sind gekennzeichnet („🤖 KI-generiert — fachlich zu prüfen"), automatisch gespeicherte Bewertungen tragen eine Kennzeichnung mit Provider + Datum (`ki_kennzeichnung`, #1551); Score-Vorschläge mit Begründung und Normbezug (#1419); geschlossene Issues setzen keinen Auto-Score (#1526) | mittel — erfordert fachliche Prüfung durch Nutzende |
| R2 | **Datenabfluss** sensibler Projektdaten an Cloud-Anbieter | Betrieb | Standard lokal (Ollama); Cloud nur mit `allow_data_egress`; Bestätigungsdialog vor jedem Direktaufruf + Audit `ai.egress.confirmed` (#1519); Redaktion sensibler Nachweise für Cloud (`redact_for_cloud`, #1483 ff.); kein stiller Fallback | niedrig |
| R3 | **Prompt-Injection** über importierte Inhalte (Issues, Dokumente, Repos) | Betrieb | Antworten nur als JSON in festes Schema geparst (`parse_chatgpt_json`), keine Tool-/Code-Ausführung aus KI-Antworten, Jinja-Vorlagen nur in `SandboxedEnvironment`, HTML aus KI-Text wird sanitisiert | mittel |
| R4 | **Automation Bias** — Nutzende vertrauen dem KI-Score zu stark | Betrieb | Human-in-the-Loop-Workflows (Copy/Paste, Vorschau vor Übernahme bei Massenbewertung #1528), „Neubewertung erforderlich"-Marker, KI-Kompetenz über Literacy-Register (Art. 4) | mittel |
| R5 | **Modellwechsel/Drift** verändert Bewertungsqualität unbemerkt | Wartung | Modell ist Konfiguration (`ai.on_prem.model` / `ai.cloud.model`), jeder Aufruf protokolliert Modell + Provider (`ai.on_prem.request`, `ai.on_prem.stream`, `ai.cloud.request`); Modellwechsel = Change nach [QMS](qms-change-management.md) | mittel |
| R6 | **Verfügbarkeit** (Ollama-Kaltstart, Timeouts) führt zu Abbruch/Teilergebnissen | Betrieb | Streaming mit Fortschritt, Abbruch-Protokollierung (`aborted`), robuste Parser für abgeschnittene Antworten (#1419), klarer Fehlerstatus statt Fallback | niedrig |
| R7 | **Unbefugte Nutzung** der KI-Funktionen | Betrieb | RBAC-Permissions je Modul, JWT, Audit-Trail append-only mit Integritätskette (#1338) | niedrig |
| R8 | **Verzerrte Ergebnisse** (Bias) bei Bewertungen | Betrieb | siehe [Daten-Governance — Bias](daten-governance.md#bias-und-fairness-aia-data-02); Bewertungsgegenstand sind Organisationen/Systeme, keine natürlichen Personen | niedrig |

## Verbindung zu Threat-Modeling

Sicherheitsbedrohungen der Gesamtanwendung werden im CRA-Modul (Threat-Model C5, Vulnerability-Sync
C3) geführt; KI-spezifische Bedrohungen der OWASP-LLM-Top-10 im AI-Act-OWASP-LLM-Register. Beide
fließen über das Risiko-Cockpit in dieselbe Sicht.
