# Sprint #28 / Milestone #30 — Pflichtdokumente-Ausbau · Umsetzungsstatus

**Milestone:** „Sprint #28: Pflichtdokumente-Ausbau — Wizards · Web-Verknüpfung · Konformitäts-Checklisten (CRA/NIS2/AI-Act)"
**Branch:** `feat/pflichtdokumente-ausbau-1246` (nur lokal — nicht gepusht/gemergt/deployed)
**Basis:** main @ `53bc584` (v6.9.0)
**Stand:** geprüft am 2026-06-10

## Gesamtbild

Der Meilenstein umfasst **18 Issues**: 1 EPIC (#1246), 13 ursprüngliche Implementierungs-Issues (#1233–#1245) und **4 nachträglich ergänzte** (#1247–#1250).

| Gruppe | Issues | Status |
|---|---|---|
| S0 Fundament (shared/documents) | #1233, #1234, #1235 | ✅ umgesetzt |
| CRA Pflichtdokumente | #1236, #1237, #1238, #1239 | ✅ umgesetzt |
| NIS2 Pflichtdokumente | #1240, #1241 | ✅ umgesetzt |
| AI-Act Pflichtdokumente | #1242, #1243, #1244, #1245 | ✅ umgesetzt |
| Nachzügler (nach Sprint-Start ergänzt) | #1247, #1248, #1249, #1250 | ✅ umgesetzt |
| EPIC (Tracking) | #1246 | — (kein Code) |

**Ergebnis: alle 17 Implementierungs-Issues umgesetzt** (#1233–#1245, #1247–#1250); EPIC #1246 ist reines Tracking. 19 Commits auf dem Branch. Boot OK · `vite build` Exit 0.

## Verifikation (umgesetzte 13)

- **Boot:** `create_app()` → OK (gemeinsamer Stand aller Batches).
- **Frontend:** `vite build` → Exit 0.
- **Tests:** je Batch grün vom Agenten verifiziert (S0 45 · CRA 147 · NIS2 164 · AI-Act 192 Dokument-/Modul-Tests); kombinierter Cross-Modul-Lauf läuft als finale Bestätigung.

### Issue ↔ Commit (umgesetzt)

| Issue | Commit | Kurzbeschreibung |
|---|---|---|
| #1233 | `10b4c26` | Web-Verknüpfung (extern/inapp) + SSRF-validierte URL + manueller Erreichbarkeits-Check |
| #1234 | `54af096` | Konformitäts-Checkliste je Dokument (eigene Tabelle `<modul>_doc_checklist`, Soll-Ist + Fortschritt + KI-Prompt) |
| #1235 | `756b249` | Wizard-Ergebnis → editier-/freigabe-/exportierbares `managed_doc` (`createFromAssistant`, `produces_document`) |
| #1236 | `3d57de2` | CRA Technische Doku (Annex VII): Checkliste + Querverweis-Bausteine |
| #1237 | `a4434d2` | CRA EU-Konformitätserklärung-Wizard (Annex V) — KI (Copy/Paste) |
| #1238 | `28946e6` | CRA Benutzerinformationen (Annex II): Web-Link + Checkliste |
| #1239 | `80ed0f2` | CRA SBOM-Begleitdokument-Wizard (Annex I Teil II) |
| #1240 | `c17a995` | NIS2 KI-Assistenten je Pflichtdokument (7 DocSpecs) |
| #1241 | `f1030f8` | NIS2 Web-Verknüpfung + Verweise statt bloßem Editor |
| #1242 | `4bcf3e1` | AI-Act AI-Literacy-Ausfüll-Assistent (Art. 4) |
| #1243 | `6f1c328` | AI-Act Konformitätsbewertung (Art. 43/48) + optionale CRA-Verknüpfung |
| #1244 | `b82b650` | AI-Act GPAI-KI-Assistent funktionsfähig (Fix) + Doc-Generatoren (Art. 53–55) |
| #1245 | `c0d90fc` | AI-Act Web-Link + Wizards (Annex IV / Betriebsanleitung / FRIA) |

### Issue ↔ Commit (Nachzügler #1247–#1250)

| Issue | Commit(s) | Kurzbeschreibung |
|---|---|---|
| #1247 | `e06b0a0` | CRA Produktklasse manuell editierbar + C6/C7-Ergebnis im Doku-Tab (sticky manual_override, Audit) |
| #1248 | `b684f0f` | CRA Versions-Import GitHub/GitLab (Releases/Tags/Compare, `vcs/repo_changes.py`) |
| #1249 | `76a2d82` | CRA KI-Wizard „Wesentliche Änderungen je Version" → DoC/Techn. Doku (Copy/Paste) |
| #1250 | `…` ×3 | Einheitliche `ModuleDashboard.vue` + `useModuleDashboard.ts` in CRA/NIS2/AI-Act/DSGVO; DSGVO-DSMS-Cockpit ins Dashboard konsolidiert |

## Bewusste Scope-Auslegungen / Folge-Hinweise (umgesetzte Issues)

- **#1241 (NIS2):** optionale Art.-21(2)-Checkliste je Buchstabe bewusst nicht umgesetzt (im Issue als „sofern Aufwand vertretbar; sonst Folge-Issue" markiert) — additiv nachrüstbar analog CRA-Checklisten.
- **PDF-Export** hängt am Gotenberg/soffice-Konverter (Umgebung); DOCX immer verfügbar, PDF-Tests tolerieren 503.
- Vorbekannte Test-Isolations-Schwäche `tests/test_cra_threat_framework_938.py` (nutzt echte `data/db/cra.sqlite`) — separat, nicht durch diesen Sprint verursacht.
