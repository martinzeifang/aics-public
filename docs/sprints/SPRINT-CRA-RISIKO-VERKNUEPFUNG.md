# Sprint: CRA-Risikoanalyse ↔ Modul Risikobewertung verknüpfen

> Planungsdokument (nicht committet). GitHub-Projekt **#17** "CRA x Risikobewertung Verknuepfung":
> https://github.com/users/martinzeifang/projects/17 · EPIC **#870**.

## 1. Ziel

Die im **CRA-Modul** geforderte Software-Risikoanalyse (CRA Annex I, Teil I, Abs. 1 –
Anforderung **AI1-01** "Risikobasierte Cybersicherheit – Design & Entwicklung") wird
**transparent und nachweisbar** an das dedizierte **Modul Risikobewertung** angebunden.
Die Risikoabschätzung wird dort geführt, wo sie hingehört (STRIDE/TARA/OCTAVE), und im
CRA-Modul nur **referenziert** = Nachweis.

### Fachlicher Leitsatz (verbindlich)
CRA Annex I gilt **produktweit**. Die Verknüpfung dient der **Nachweisbarkeit** der
durchgeführten Risikoabschätzung. Sie darf **niemals** CRA-Anforderungen aus- oder
einblenden – die Anforderungsliste bleibt stets vollständig. Abdeckungs-Kennzahlen
(Stufe 2) sind rein informativ.

## 2. Faktenlage (Datei:Zeile)

### Risikobewertung
- `risikobewertung/db.py:64` – `rb_projekte` (mit `meta_json` Zeile 72).
- `risikobewertung/db.py:77` – `rb_risiken` (`felder_json` Z.84, `risikowert` Z.85, `risiko_label` Z.86).
- `risikobewertung/db.py:227` – `list_projekte_fuer_firma()`.
- `risikobewertung/db.py:291` – Laden parst `meta_json` → `d["meta"]`.
- `risikobewertung/frameworks.py` – STRIDE / TARA / OCTAVE.
- `server/api/risikobewertung.py:200` – `_merge_project_meta()` (verhindert meta-Wipe).
- `frontend/src/views/risikobewertung/RisikobewertungView.vue:665` – Deep-Link `?projekt=<name>` (Issue #433); `?firma=`/`?neu=` ebenfalls vorhanden.

### CRA
- `cra/db.py:17` – `cra_projekte` (mit `meta_json` Z.25); Laden parst meta (Z.245).
- `cra/db.py:124` – `cra_vuln` (CVEs: `cve_id`, `schwere`, `cvss_score`, `status`).
- `cra/db.py:164` – `cra_threatmodel` (`framework` STRIDE/PASTA/LINDDUN, `threats_json`, `mitigations_json`).
- `cra/db.py:264` – `list_projekte_fuer_firma()`.
- `cra/db.py:769 / 789` – `load_threatmodel` / `save_threatmodel`.
- `cra/requirements.py:135` – Anforderung **AI1-01** (ref "Annex I, Part I, Abs. 1"; Hinweis nennt STRIDE/TARA, ISO/IEC 27005, IEC 62443).
- `server/api/cra/__init__.py` – CRA-API-Blueprint.
- `frontend/src/views/cra/CRAView.vue` – Tab-Array (dashboard/pflichtdoku/requirements/owasp/fragebogen/bericht).

### Gemeinsame Klammer
- Beide Module nutzen `unternehmen` (= `firmen.name`) als Firmen-Schlüssel.
- `server/api/firmen.py:55,73` importiert beide `list_projekte_fuer_firma` (cra/rb).
- `meta_json` ist in beiden Projekt-Tabellen der Extension-Punkt (migrationsfrei).
- `shared/issue_links.py:22` – `object_kind` ∈ {`requirement`, `risk`}.
- `frontend/src/components/shared/HelpDialog.vue` – Hilfe-Dialog-Muster.

## 3. Vorhandene Bausteine (was schon da ist)

- **Projekt-meta in beiden Modulen** → keine Migration für Stufe 1 nötig.
- **Firmenbasierte Projektliste** in beiden Modulen → Link-Kandidaten gratis.
- **Deep-Link `?projekt=`** im RB-Frontend → CRA→RB-Sprung sofort möglich.
- **Threat-Model-Tabelle** (`cra_threatmodel`) und **CVE-Tabelle** (`cra_vuln`) → Quellen für optionale Sync (Stufe 2).
- **`felder_json` je Risiko** → Aufnahme von `cra_refs` ohne Migration (Stufe 2).
- **HelpDialog** → Transparenz-Text wiederverwendbar.
- **Vorarbeiten (CLOSED):** #482 (CVEs als Risiko-Quelle), #562 (Threat-Model ↔ RB). Backlog-Sammler #673.

## 4. Stufenplan

| Stufe | Inhalt | Issues |
|------|--------|--------|
| **1 – Verknüpfung** | bidirektionale Projekt-Verknüpfung, Deep-Link, Risiko-Summary, Rück-Badge, Hilfe | #871, #872, #873, #874 |
| **2 – Mapping** | Risiko↔Anforderung-Mapping, Abdeckungs-Sicht, Mapping-UI; optional Threat/CVE-Sync | #875, #876, #877, #878 |
| **3 – Report/Optional** | CRA-Report bindet RB-Summary ein | #879 |

## 5. Issues (je ein Abschnitt)

### #870 — EPIC: CRA-Risikoanalyse mit Risikobewertung verknüpfen
Übersicht/Klammer. Hält den fachlichen Leitsatz, Stufenplan und EPIC-Akzeptanzkriterien.

### #871 — Stufe 1 Datenmodell: bidirektionale Projekt-Verknüpfung (meta_json) · S · Datenmodell
`cra_projekte.meta.linked_risk_projekt` ↔ `rb_projekte.meta.linked_cra_projekt`.
Helper `set_linked_partner(...)` in beiden `db.py`; kein meta-Wipe; keine Schema-Migration.

### #872 — Stufe 1 Backend: Link-Kandidaten + Verknüpfen/Lösen · M · Backend
`GET candidates` (gleicher Firma), `POST/DELETE risk-link` mit beidseitiger Konsistenz,
Firmengrenzen-Validierung, `@jwt_required`, meta-merge zwingend.

### #873 — Stufe 1 Frontend: CRA-Tab "🔍 Risikoanalyse" + RB-Rück-Badge · M · Frontend
Neuer Tab in `CRAView.vue`: verknüpftes RB-Projekt + Risiko-Summary + Deep-Link
(`…/risikobewertung?projekt=<name>`); RB-Modul zeigt Rück-Badge + Deep-Link. Kein Aus-/Einblenden.

### #874 — Stufe 1 Hilfe/Transparenz: AI1-01-Nachweisbezug · S · Doku
HelpDialog erklärt AI1-01, dass die Risikoabschätzung im RB-Modul geführt/nachgewiesen
wird und die Verknüpfung **kein** Filter ist.

### #875 — Stufe 2 Datenmodell: Risiko↔Anforderung-Mapping · M · Datenmodell
Optionen A (`felder_json.cra_refs`) vs. B (Tabelle `risk_requirement_links`).
**Empfehlung: A** für MVP (migrationsfrei, konsistent mit `felder_json`), Upgrade-Pfad zu B dokumentiert.

### #876 — Stufe 2 Backend: Mapping-CRUD + Abdeckungs-Sicht · M · Backend
CRUD + `coverage/by-requirement` + `coverage/by-risk` + informative Abdeckungs-Kennzahl.
Anforderungsquelle: `cra/requirements.py` (+ `cra_anforderungen_custom`).

### #877 — Stufe 2 Frontend: Mapping-UI + Abdeckungs-Indikator · L · Frontend
RB-Risiko-Editor: Anforderungen zuordnen; CRA-Anforderungsliste: Spalte "verknüpfte Risiken";
Abdeckungs-Indikator (informativ; Liste bleibt vollständig).

### #878 — Stufe 2 (optional): Threat-Model/CVE als Risiko-Quelle · L · Backend
STRIDE-Threats (`cra_threatmodel`) → RB-Risiken (idempotent); offene CVEs (`cra_vuln`) → RB-Risiken
(CVSS-Heuristik). Greift #562 und #482 auf (nicht erneut schließen).

### #879 — Stufe 3 (optional): CRA-Report bindet RB-Summary ein · M · Backend
`cra/report_export.py`: Abschnitt "Risikoabschätzung (Modul Risikobewertung)" mit Summary,
AI1-01-Bezug; bei fehlender Verknüpfung klarer Nachweis-Lücken-Hinweis.

## 6. Datenmodell-Optionen mit Empfehlung

### Stufe 1 (Projekt-Verknüpfung) — entschieden: meta_json
`cra_projekte.meta.linked_risk_projekt` ↔ `rb_projekte.meta.linked_cra_projekt`.
Keine Migration, nutzt vorhandenes meta-Pattern + `_merge_project_meta`.

### Stufe 2 (Risiko↔Anforderung-Mapping)
- **Option A — `rb_risiken.felder_json.cra_refs` (Liste von Anforderungs-IDs).**
  Migrationsfrei, konsistent mit bestehendem `felder_json`-Mechanismus; Rückwärtssuche
  per Filter über (kleine) Risikomenge. **EMPFOHLEN für MVP.**
- **Option B — Tabelle `risk_requirement_links`** (n:m, indexierbar, Link-Metadaten,
  in der **RB-DB**, da `risk_id` dort lebt; CRA-Anforderungs-ID = stabiler String).
  Mehr Aufwand (DDL/Migration). **Upgrade-Pfad**, sobald Constraints/projektübergreifende
  Auswertung/Link-Metadaten gebraucht werden.

## 7. Projekt-/Issue-Nummern

- **GitHub-Projekt:** #17 — https://github.com/users/martinzeifang/projects/17
- **Projektfelder (SINGLE_SELECT):** Stufe (Stufe 1 Verknüpfung / Stufe 2 Mapping / Stufe 3 Report/Optional), Aufwand (S/M/L/XL), Komponente (Backend/Frontend/Datenmodell/Doku).
- **Issues:**
  - #870 EPIC
  - #871 Stufe 1 Datenmodell · S · Datenmodell
  - #872 Stufe 1 Backend · M · Backend
  - #873 Stufe 1 Frontend · M · Frontend
  - #874 Stufe 1 Hilfe · S · Doku
  - #875 Stufe 2 Datenmodell · M · Datenmodell
  - #876 Stufe 2 Backend · M · Backend
  - #877 Stufe 2 Frontend · L · Frontend
  - #878 Stufe 2 optional (Threat/CVE) · L · Backend
  - #879 Stufe 3 optional (Report) · M · Backend
- **Referenzen (CLOSED, nicht wieder öffnen):** #482, #562; Backlog #673.
