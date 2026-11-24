# Sprint: KI-Transparenz & einheitliche KI-UX

> Planungsdokument (nicht committet). Stand: 2026-05-31
> GitHub-Projekt: **#16** — <https://github.com/users/martinzeifang/projects/16>
> Issues: **#865–#878** (Titel-Präfix `AICS · KI-UX:`)

## 1. Ziel

Nutzer sollen über **alle** Module hinweg eindeutig verstehen, **wo und wie** KI in der
AI Compliance Suite einfließt. Heute existiert keine gemeinsame KI-Komponente; jedes
Modul löst Prompt-Anzeige, JSON-Eingabe und Hinweise etwas anders. Dieser Sprint
schafft eine einheitliche, transparente KI-UX:

- **(a)** sichtbar machen, *dass* KI im Spiel ist,
- **(b)** sichtbar machen, *welche* Daten in den Prompt gehen (Projekt/Repo/PII),
- **(c)** sichtbar machen, *wohin* die Antwort gespeichert wird und welche Wirkung sie hat,
- **(d)** sichtbar machen, ob **lokal (Ollama)** oder **Cloud** genutzt wird (Daten-Egress).

## 2. Faktenlage (verifiziert, Datei:Zeile)

Grundmuster „human-in-the-loop / copy-paste" — das Modul-Docstring `cra/ai_wizards.py:3`
beschreibt es wörtlich: „Backend baut Prompt mit JSON-Schema, User kopiert nach ChatGPT,
Antwort wird per parse_*_response zurück-geparsed und ins Modell übernommen."

Verifizierte ~45 KI-Funktionen (je Paar `build_*_prompt` / `parse_*_response`):

| Modul | Datei | Funktionen (Beispiele mit Zeile) |
|---|---|---|
| CRA (3 Wizards) | `cra/ai_wizards.py` | `build_klassifikator_prompt:53` / `parse_klassifikator_response:84`, `build_vuln_policy_prompt:173`, `build_update_policy_prompt:219` |
| AI-Act (10 Wizards) | `ai_act/ai_wizards.py` | `build_risk_tier_prompt:49`, `build_eu_doc_prompt:176`, `build_transparency_prompt:227`, `build_llm_card_prompt:289`, `build_high_risk_doc_prompt:342`, `build_prompt_injection_test_prompt:424`, `build_hitl_workflow_prompt:479`, `build_eu_db_registration_prompt:541`, `build_aiact_chat_prompt:613`, `build_eu_office_report_prompt:670` |
| NIS2 (9 Wizards) | `nis2/ai_wizards.py` | `build_klassifikator_prompt:30`, `build_incident_notification_prompt:150`, `build_supply_chain_assessment_prompt:188`, `build_incident_24h_prompt:241`, `build_incident_72h_prompt:305`, `build_incident_final_prompt:369`, `build_cyberhygiene_quiz_prompt:446`, `build_vendor_tiering_prompt:513` |
| DSGVO (3 Wizards) | `dsgvo/ai_wizards.py` | `build_rechtsgrundlage_prompt:37`, `build_datenpanne_meldung_prompt:153`, `build_betroffenenrechte_prompt:204` |
| Risikobewertung | `risikobewertung/prompts.py` | `build_discovery_prompt:101` / `parse_discovery_antwort:178`, `build_prompt:288`, `build_re_assessment_prompt:360`, `parse_json_antwort:500` |
| Gutachten | `gutachten/wizards.py`, `gutachten/audit_to_pg.py`, `gutachten/ideen.py` | `build_beurteilung_prompt:256` / `parse_beurteilung_response:320`; `build_pg_questions_prompt:440`, `build_smart_suggestions_prompt:622`; `build_drittgutachter_prompt:123` |

**JSON-Robustheit:** jedes Modul hat `_extract_json(...)` (z. B. `cra/ai_wizards.py:266`,
`ai_act/ai_wizards.py:729`, `nis2/ai_wizards.py:575`, `dsgvo/ai_wizards.py:251`).

**Ausnahme (direkter lokaler LLM-Call statt copy-paste):** Risikobewertung-Bulk nutzt
einen direkten Ollama-Call — `risikobewertung/prompts.py`, `risikobewertung/_massen_dialog.py`,
Frontend `frontend/src/views/risikobewertung/MassenBewertungDialog.vue` und `RisikoAssistent.vue`.

**Provider / Egress (Backend):**

- `allow_data_egress` referenziert in `ai_compliance_suite/config.py`,
  `ai_compliance_suite/ai/providers/cloud.py`, `ai_compliance_suite/gui.py`,
  `server/services/prefill.py`, `server/api/admin.py`.
- Lokaler Provider: `ai_compliance_suite/ai/providers/on_prem.py`; Cloud: `…/providers/cloud.py`.

**Frontend-Stellen:**

- Gemeinsame KI-Aktionsleiste: `frontend/src/components/shared/RequirementActions.vue`
  (enthält bereits Legend „🤖 KI-Bewertung", Buttons „💬 Prompt erstellen" /
  „📋 JSON-Antwort einfügen" sowie Prompt- und JSON-Modal inline).
- Eingebunden in: `frontend/src/views/cra/CRAView.vue`,
  `frontend/src/views/aiact/AIActView.vue`, `frontend/src/views/nis2/NIS2View.vue`,
  `frontend/src/views/dsgvo/DSGVOView.vue`, `frontend/src/views/dora/DORAView.vue`.
- PflichtDoku-Panels je Modul: `frontend/src/views/cra/PflichtDokuPanel.vue`,
  `frontend/src/views/aiact/AIActPflichtDokuPanel.vue`,
  `frontend/src/views/nis2/NIS2PflichtDokuPanel.vue`,
  `frontend/src/views/dsgvo/DSGVOPflichtDokuPanel.vue`.
- Risikobewertung-eigene Dialoge: `frontend/src/views/risikobewertung/RisikoAssistent.vue`,
  `frontend/src/views/risikobewertung/MassenBewertungDialog.vue`.

**Transparenz-Lücken:** Das Modal in `RequirementActions.vue` zeigt nur den Prompt-Text
(`<pre class="prompt-text">`) und einen kurzen Hinweis. Es fehlt: strukturierte
Daten-Vorschau (welche Felder gehen raus), Markierung sensibler Felder, Hinweis auf Zielfeld/
Wirkung der Antwort, sowie ein global sichtbarer Provider-/Egress-Status. Gutachten und
Risikobewertung nutzen die gemeinsame Leiste teils gar nicht.

## 3. KI-Inventar (modulweise)

| Modul | KI-Funktionen | UI-Ort | lokal / cloud / copy-paste | Transparenz-Lücke |
|---|---|---|---|---|
| CRA | 3 (Klassifikator, Vuln-Policy, Update-Policy) | `cra/CRAView.vue` via `RequirementActions.vue` | copy-paste | b, c, d |
| AI-Act | 10 (Risk-Tier, EU-Doc, Transparency, LLM-Card, High-Risk-Doc, Prompt-Injection-Test, HITL, EU-DB, Chat, EU-Office-Report) | `aiact/AIActView.vue` + `AIActPflichtDokuPanel.vue` via `RequirementActions.vue` | copy-paste | a, b, c, d |
| NIS2 | 9 (Klassifikator, Incident 24h/72h/final/Notification, Supply-Chain, Cyberhygiene-Quiz, Vendor-Tiering) | `nis2/NIS2View.vue` + `NIS2PflichtDokuPanel.vue` via `RequirementActions.vue` | copy-paste | b, c, d |
| DSGVO | 3 (Rechtsgrundlage, Datenpanne-Meldung, Betroffenenrechte) | `dsgvo/DSGVOView.vue` + `DSGVOPflichtDokuPanel.vue` via `RequirementActions.vue` | copy-paste | b, c, d |
| Risikobewertung | Discovery, Einzel-Assistent (`build_prompt`), Re-Assessment, Bulk | `RisikoAssistent.vue`, `MassenBewertungDialog.vue` | Bulk = lokal (Ollama); übrige copy-paste | a, b, c, d |
| Gutachten | Beurteilung, PG-Questions, Smart-Suggestions, Drittgutachter | `gutachten/GutachtenView.vue` (eigene Flows) | copy-paste | a, b, c, d |
| Shared/Global | zentrale Provider/Policy | `ai_compliance_suite/ai/providers/*`, `server/api/admin.py` | lokal & cloud (Policy/Egress) | d (Egress nicht sichtbar) |

Summe ~45 KI-Funktionen; nahezu alle copy-paste, einzige direkte LLM-Anbindung ist
Risikobewertung-Bulk (Ollama).

## 4. Phasenplan

| Phase | Inhalt | Issues |
|---|---|---|
| **P1 Shared-Komponente** | Gemeinsame KI-Bausteine bauen | #866, #867 |
| **P2 Transparenz-Layer** | Daten-Vorschau, Ziel-Hinweis, Kennzeichnung | #868, #869, #870 |
| **P3 Modul-Migration** | Module auf gemeinsame Komponente umstellen | #871–#876 |
| **P4 Provider/Settings** | Lokal/Cloud-Wahl, Egress-Transparenz, Doku | #877, #878 |

## 5. Geplante gemeinsame Komponenten

- `frontend/src/components/shared/WizardPromptModal.vue` — Prompt anzeigen/kopieren, JSON einfügen + validieren, Schema-Hinweis (ersetzt das inline-Modal in `RequirementActions.vue`).
- `frontend/src/components/shared/AIProviderBadge.vue` — aktiver Provider (🏠 Ollama lokal / ☁️ Cloud) + Konfig-/Egress-Status; in Topbar/AppLayout.
- `frontend/src/components/shared/DataPreviewWarning.vue` — „Diese Daten gehen an die KI" inkl. Markierung sensibler Felder + Bestätigung; Backend liefert `get_*_data_used()` neben `build_*_prompt`.
- `frontend/src/components/shared/OutputDestinationHint.vue` — „So wird die Antwort verwendet/gespeichert" (Zielfeld + Wirkung) je Wizard.
- Einheitliche KI-Kennzeichnung (🤖-Label, konsistente Begriffe, Disclaimer „KI-generiert, fachlich zu prüfen").

## 6. Issues im Detail

### #865 — EPIC: Einheitliche & transparente KI-Funktionen (Übersicht)
Bereich: Global · Aufwand: XL · Phase: — (Klammer-EPIC)
Bündelt P1–P4; Akzeptanz: KI durchgängig gekennzeichnet, Daten-/Ziel-/Provider-Transparenz,
mind. 6 Module nutzen `WizardPromptModal.vue`, zentrale Hilfe-Seite verlinkt.

### #866 — WizardPromptModal.vue (gemeinsame Prompt/JSON-Komponente)
Bereich: Shared-Komponente · Aufwand: L · Phase: P1
Neue Komponente mit Prompt-Anzeige/Kopieren, JSON-Eingabe + Validierung, Schema-Hinweis;
Slots für Transparenz-Bausteine; Referenz-Integration in CRA. Löst das inline-Modal in
`RequirementActions.vue` ab.

### #867 — AIProviderBadge.vue (aktiver Provider in Topbar)
Bereich: Shared-Komponente · Aufwand: S · Phase: P1
Badge 🏠 lokal / ☁️ Cloud inkl. Konfig- und Egress-Status; Backend liefert Provider-Status
(read-only, basierend auf `ai_compliance_suite/ai/providers/*` + `allow_data_egress`);
Einbindung in Topbar/AppLayout.

### #868 — DataPreviewWarning.vue (Welche Daten gehen an die KI?)
Bereich: Shared-Komponente · Aufwand: M · Phase: P2
Vorschau der gesendeten Daten, Markierung sensibler Felder, Pflicht-Bestätigung;
Backend `get_*_data_used()` neben `build_*_prompt` (gleiche Module wie Inventar).

### #869 — OutputDestinationHint.vue (Wohin geht die KI-Antwort?)
Bereich: Shared-Komponente · Aufwand: S · Phase: P2
Hinweis auf Zielfeld + Wirkung je Wizard; Integration in `WizardPromptModal.vue`.

### #870 — Einheitliche Kennzeichnung der KI-Buttons + Disclaimer
Bereich: Global · Aufwand: M · Phase: P2
🤖-Label + konsistente Terminologie für alle KI-Aktionen; Disclaimer
„KI-generiert, fachlich zu prüfen" an jedem Ergebnis. Konsolidierung über
`RequirementActions.vue` / `WizardPromptModal.vue`.

### #871 — CRA: KI-Funktionen migrieren
Bereich: CRA · Aufwand: M · Phase: P3 — `cra/ai_wizards.py`, `frontend/src/views/cra/CRAView.vue`.

### #872 — AI-Act: KI-Funktionen migrieren
Bereich: AI-Act · Aufwand: M · Phase: P3 — `ai_act/ai_wizards.py`, `aiact/AIActView.vue`, `AIActPflichtDokuPanel.vue`.

### #873 — NIS2: KI-Funktionen migrieren
Bereich: NIS2 · Aufwand: M · Phase: P3 — `nis2/ai_wizards.py`, `nis2/NIS2View.vue`, `NIS2PflichtDokuPanel.vue`.

### #874 — DSGVO: KI-Funktionen migrieren
Bereich: DSGVO · Aufwand: M · Phase: P3 — `dsgvo/ai_wizards.py`, `dsgvo/DSGVOView.vue`, `DSGVOPflichtDokuPanel.vue`.

### #875 — Risikobewertung: KI-Funktionen migrieren
Bereich: Risikobewertung · Aufwand: M · Phase: P3 — `risikobewertung/prompts.py`,
`RisikoAssistent.vue`, `MassenBewertungDialog.vue` (Sonderfall: lokaler Ollama-Bulk-Call).

### #876 — Gutachten: KI-Funktionen migrieren
Bereich: Gutachten · Aufwand: M · Phase: P3 — `gutachten/wizards.py`, `gutachten/audit_to_pg.py`,
`gutachten/ideen.py`, `gutachten/GutachtenView.vue`.

### #877 — Lokal/Cloud bewusst wählbar + Egress-Transparenz
Bereich: Global · Aufwand: M · Phase: P4
Admin-Settings-Eintrag „KI-Provider"; `allow_data_egress` (`ai_compliance_suite/config.py`,
`server/api/admin.py`) sichtbar machen; Cloud-Egress mit klarer Zustimmung/Hinweis.

### #878 — Zentrale Hilfe-Seite „Wie funktionieren die KI-Funktionen?"
Bereich: Global · Aufwand: S · Phase: P4
Doku-Seite in `docs/` (verlinkt in `mkdocs.yml`): Copy-Paste-Workflow, lokal vs. cloud,
Datenschutz/Egress; aus dem UI verlinkt.

## 7. Projekt-/Issue-Übersicht

| # | Titel (Kurz) | Bereich | Aufwand | Phase |
|---|---|---|---|---|
| 865 | EPIC Übersicht | Global | XL | — |
| 866 | WizardPromptModal.vue | Shared-Komponente | L | P1 |
| 867 | AIProviderBadge.vue | Shared-Komponente | S | P1 |
| 868 | DataPreviewWarning.vue | Shared-Komponente | M | P2 |
| 869 | OutputDestinationHint.vue | Shared-Komponente | S | P2 |
| 870 | KI-Buttons + Disclaimer | Global | M | P2 |
| 871 | CRA migrieren | CRA | M | P3 |
| 872 | AI-Act migrieren | AI-Act | M | P3 |
| 873 | NIS2 migrieren | NIS2 | M | P3 |
| 874 | DSGVO migrieren | DSGVO | M | P3 |
| 875 | Risikobewertung migrieren | Risikobewertung | M | P3 |
| 876 | Gutachten migrieren | Gutachten | M | P3 |
| 877 | Lokal/Cloud + Egress | Global | M | P4 |
| 878 | Zentrale Hilfe-Seite | Global | S | P4 |
