# AI Act

## Zweck

Das AI-Act-Modul unterstützt die Einordnung von KI-Systemen und KI-Modellen entlang des risikobasierten Ansatzes des EU AI Act und leitet daraus die jeweils geltenden Pflichten ab. Es dokumentiert die Risikoklassifizierung, prüft Hochrisiko-Anforderungen und verfolgt die regulatorischen Fristen.

## Rechtsgrundlage

Verordnung (EU) 2024/1689 (EU AI Act) zur Festlegung harmonisierter Vorschriften für Künstliche Intelligenz.

Der AI Act verfolgt einen risikobasierten Ansatz und stuft KI je nach Gefährdungspotenzial in verbotene Praktiken, Hochrisiko, begrenztes Risiko und minimales Risiko ein. Je Klasse gelten unterschiedliche Pflichten; für General-Purpose-AI-Modelle (GPAI) bestehen eigene Regelungen.

Maßgebliche Vorschriften:

- **Art. 5** — verbotene Praktiken (z. B. manipulatives Verhalten, Social Scoring, ungezieltes Scraping zur Gesichtsdatenbank-Erstellung).
- **Art. 6, Annex III / Annex I** — Hochrisiko-Einstufung (u. a. biometrische Identifizierung, kritische Infrastruktur, Beschäftigung, Bildung) sowie sicherheitsrelevante Produkte.
- **Art. 9–15** — Pflichten für Hochrisiko-Systeme: Risikomanagementsystem (9), Daten-Governance (10), technische Dokumentation nach Annex IV (11), Logging (12), Transparenz/Information an Betreiber (13), menschliche Aufsicht (14), Genauigkeit/Robustheit/Cybersicherheit (15).
- **Art. 50** — Transparenzpflichten bei begrenztem Risiko (Offenlegung der KI-Interaktion, Kennzeichnung synthetischer/Deepfake-Inhalte).
- **Art. 49 / 71** — Konformitätsbewertung, EU-Konformitätserklärung und Registrierung in der EU-Datenbank.
- **Art. 51, 53, 55** — GPAI-Modelle: technische Dokumentation, Urheberrechts-Policy, Trainingsdaten-Zusammenfassung; zusätzliche Pflichten bei systemischem Risiko.

## Workflow

Das Modul ist projektbasiert und wird in der Web-Oberfläche bedient:

1. **Projekt anlegen** und den Use Case beschreiben.
2. **Risikoklasse bestimmen** — Use Case zuerst gegen die verbotenen Praktiken (Art. 5) prüfen, dann gegen Annex III und die Ausnahmen nach Art. 6 Abs. 3.
3. **Rolle zuordnen** — Anbieter vs. Betreiber/Deployer, da sich die Pflichten unterscheiden.
4. **Pflichten-Checkliste abarbeiten** — für Hochrisiko die Anforderungen Art. 9–15 Punkt für Punkt mit Nachweisen/Evidenzen belegen; bei begrenztem Risiko die Transparenzpflichten nach Art. 50.
5. **Anforderungen bewerten** (0–5 inkl. Kommentar und Maßnahme); ein Dashboard berechnet eine gewichtete Readiness.
6. **Bericht exportieren** und Klassifizierung, Begründung und Evidenzen versioniert ablegen.

### Risiko-Stufen

| Klasse | Konsequenz |
|---|---|
| Verbotene Praktiken | Untersagt (Art. 5) |
| Hochrisiko | Pflichten Art. 9–15, Konformitätsbewertung, EU-Registrierung |
| Begrenztes Risiko | Transparenzpflichten (Art. 50) |
| Minimales Risiko | Keine besonderen Pflichten |

Anwendungsfristen: Verbote seit 2. Februar 2025, GPAI-Regeln seit 2. August 2025, Hochrisiko nach Annex III ab 2. August 2026, eingebettete Hochrisiko-Produkte (Annex I) ab 2. August 2027.

## Bedienung

- **Klassifizierungs-Wizard** — zentraler Einstieg: ermittelt die Risiko-Stufe aus der Use-Case-Beschreibung; Pflichten werden anschließend klassenspezifisch ausgespielt (nur einschlägige Anforderungen werden angeboten).
- **Hochrisiko-Checkliste** — orientiert an Art. 9–15 und Annex IV (`high_risk_checklist.json`).
- **GPAI-Modul (Tab „🧠 Art. 51-55 GPAI")** — eigene Vertikale für General-Purpose-AI-Modelle: Klassifizierung mit Trainings-Rechenleistung (FLOP) und automatischer Bewertung des 10^25-FLOP-Schwellenwerts für systemisches Risiko (Art. 51), Kommissions-Notifikation mit 2-Wochen-Fristenuhr (Art. 52), Pflicht-Register (AIA-GPAI-IDs: Annex-XI-Modell-Doku, Annex-XII-Downstream-Doku, Urheberrechts-/TDM-Opt-out-Policy, öffentliche Trainingsdaten-Zusammenfassung) sowie — nur für systemische Modelle — Red-Teaming, Systemic-Risk-Assessment, Cybersicherheit, GPAI-Code-of-Practice (Art. 55) und AI-Office-Incident-Tracking.

### KI-Wizards

Die Assistenten erzeugen einen Prompt zum Einfügen in ChatGPT; die JSON-Antwort wird zurück ins Modul übernommen:

- **Risk-Tier-Wizard** — schlägt die Risiko-Stufe vor.
- **EU-Dokumentation / Hochrisiko-Doku** — generiert technische Dokumentation nach Annex IV.
- **Transparenz-Hinweise** (Art. 50), **LLM-Model-Card**, **Prompt-Injection-Test**, **Human-in-the-Loop-Workflow** und **EU-Datenbank-Registrierung**.

Use-Case-Templates erleichtern den Einstieg.

### Evidence-Bindung

Das Modul integriert Repo-Linking (GitHub/GitLab) und CI-Evidence-Import. Aus Repo-Signalen und CI-Evidence erzeugen die Auto-fill-Buttons **deterministische Prefill-Vorschläge** (Tabelle `prefill_suggestions`); sie schreiben nicht direkt in die Bewertungen. Über „Vorschläge prüfen…" werden sie akzeptiert oder abgelehnt. Evidence wird projekt-scoped abgelegt (`firmen_id = <Projektname>` in der geteilten `data/db/evidence.sqlite`).

## Export

- **DOCX** — Readiness-/Konformitätsbericht (`export_docx`).
- **PDF** — Bericht als PDF (`export_pdf`).

Datenhaltung: Modul-DB `data/db/ai_act.sqlite`, Evidence-DB (shared) `data/db/evidence.sqlite`.

## Weiterführend

- [NIS2-Modul](nis2.md) — Cybersicherheits-Anforderungen.
- [DSGVO-Modul](dsgvo.md) — Datenschutz-Compliance.
- [Risikobewertung](risikobewertung.md) — STRIDE-LLM-Framework für KI-/LLM-Risiken.
- [CRA-Modul](cra.md) — Cyber Resilience Act und Evidence-Sync.
- [Verordnung (EU) 2024/1689 (EUR-Lex)](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)
