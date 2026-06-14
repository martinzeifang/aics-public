# CRA-Umsetzungsplan — AI Compliance Suite als Produkt

> **Zweck:** Strukturierter Umsetzungsplan für die Cyber-Resilience-Act-Anforderungen (CRA, VO (EU) 2024/2847) an die AI Compliance Suite **selbst** als Produkt mit digitalen Elementen.
> Jede Anforderung mit **Fragenkatalog** (was zu klären/erheben ist) und **Umsetzungsidee** (wie konkret in AICS umsetzbar).
>
> **GitHub-Projekt:** [CRA-Konformität – AICS als Produkt (#14)](https://github.com/users/martinzeifang/projects/14)
> **Bezug:** CRA-Gap-Issues #756–#762 und #838–#861.

## Lesehilfe / Klassifikation

| Feld | Werte | Bedeutung |
|------|-------|-----------|
| **Typ** | Code · Doku · Prozess · Gemischt | Was die Lücke schließt |
| **Aufwand** | S/M/L/XL | grobe Größenordnung |
| **Sprint** | 1 Code/Technik · 2 Doku/Nachweise · 3 Prozesse/Governance | Reihenfolge-Empfehlung |
| **Status** | ✅ erledigt · 🟡 teilweise · 🔲 offen | aktueller Stand (Triage) |

**Bereits geschlossen (vollständig belegt):** AI1-03 Secure by Default (#840), AI2-02 SBOM (#844), AI2-04 Regelmäßige Sicherheitstests (#846), AI2-05 CVD-Policy (#847). Als Referenz erwähnt, nicht mehr zu tun.

---

# Sprint 1 — Code / Technik

Technische Lücken im Produkt selbst. Höchster Hebel, gut testbar.

## AI1-01 — Risikobasierte Cybersicherheit (Design & Entwicklung) · #838
**Typ:** Gemischt · **Aufwand:** M · **Status:** 🟡
CRA Annex I Teil I (1): Produkt muss auf Basis einer Risikoabschätzung entworfen/entwickelt werden.

**Fragenkatalog**
- Existiert ein dokumentiertes Threat-Model für AICS (Trust-Boundaries, Datenflüsse, Angreifermodell)?
- Welche STRIDE-/OWASP-Kategorien sind pro Komponente (Backend, Frontend, LLM-Anbindung, Persistenz) abgedeckt?
- Wie wird die Risikoabschätzung bei Architekturänderungen aktualisiert (Trigger, Verantwortliche)?
- Gibt es Traceability zwischen identifizierten Risiken und umgesetzten Maßnahmen?

**Umsetzungsidee**
- `docs/security/threat-model.md` mit Datenfluss-Diagramm + STRIDE-Tabelle je Komponente; AICS' eigenes Risikobewertungs-Modul (OCTAVE/STRIDE) auf das Produkt anwenden und exportieren.
- Traceability-Matrix Risiko → Maßnahme → Test (Verweis auf Härtungs-Epic #747).
- PR-Template-Checkbox „Architektur-Review nötig?" bei Änderungen an `server/`, `shared/`, `frontend/`.

## AI1-02 — Keine bekannten ausnutzbaren Schwachstellen bei Markteinführung · #839
**Typ:** Code · **Aufwand:** M · **Status:** 🟡
Annex I Teil I (2)(a): Auslieferung ohne bekannte ausnutzbare Schwachstellen.

**Fragenkatalog**
- Gibt es ein Release-Gate, das einen Release bei offenen kritischen/hohen CVEs blockiert?
- Welche Quellen (pip-audit, OSV, npm-audit, Bandit) mit welchem Schweregrad-Schwellwert?
- Wie werden „akzeptierte" Findings dokumentiert (Risk-Acceptance mit Begründung/Ablaufdatum)?

**Umsetzungsidee**
- Vorhandene Scans (`deps-audit.yml`, `sast.yml`, `secret-scan.yml`) zu einem **Release-Gate** bündeln: Tag/Release-Workflow bricht bei High/Critical ab.
- `SECURITY-RELEASE-CHECKLIST.md` + „pre-release vuln report" als Release-Asset.
- Risk-Acceptance-Datei (`.security/accepted-findings.yml`) mit Ablaufdatum; Gate liest sie ein.

## AI1-04 — Vertraulichkeit gespeicherter & übertragener Daten · #841
**Typ:** Code · **Aufwand:** M · **Status:** 🟡
Annex I Teil I (2)(e): Schutz durch Verschlüsselung at-rest und in-transit.

**Fragenkatalog**
- In-transit ist via nginx-TLS abgedeckt — wird at-rest für **alle** sensiblen Artefakte erfüllt?
- Welche Daten liegen aktuell unverschlüsselt (SQLite-DBs, Reports DOCX/PDF/XLSX/JSON, Backups)?
- Voll-Verschlüsselung (Volume/DB) oder feldweise (`crypto_at_rest`) — Performance/Suche?

**Umsetzungsidee**
- `shared/crypto_at_rest` auf Report-/Backup-Artefakte ausweiten (opt-in via `AICS_AT_REST_KEY`), analog VCS-Tokens.
- Doku „Daten-Schutzklassen"; Produktiv-Default-Hinweis (verschlüsseltes Volume).
- Test: Report-Export erzeugt verschlüsselte Datei wenn Key gesetzt; Roundtrip.

## AI1-05 — Integrität / Schutz vor unautorisierten Änderungen · #842
**Typ:** Code · **Aufwand:** M · **Status:** 🟡
Annex I Teil I (2)(d): Schutz der Integrität von Daten, Befehlen, Konfiguration.

**Fragenkatalog**
- Config-Integrität ist via HMAC/sha256 abgedeckt — fehlt sie für **exportierte Reports**?
- Reports signieren (Detached-Signatur) oder mit Prüfsumme begleiten?
- Wie wird Manipulation nach Erzeugung erkannt/gemeldet?

**Umsetzungsidee**
- Begleit-`.sha256` (oder Detached-Signatur) je Report-Export; optionale Signatur mit dem at-rest-Key.
- Image-Integrität ist via cosign abgedeckt (dokumentieren).
- Verifikations-CLI/Endpoint „Report-Integrität prüfen".

## AI1-07 — Verfügbarkeit / Schutz wesentlicher Funktionen · #756
**Typ:** Code · **Aufwand:** M · **Status:** 🟡
Annex I Teil I (2)(f): Resilienz gegen DoS, Schutz wesentlicher Funktionen.

**Fragenkatalog**
- Rate-Limiting (flask-limiter) deckt alle teuren Endpunkte (LLM, Export, Upload) ab?
- Ist der Rate-Limit-Store persistent/geteilt (mehrere Worker) oder in-memory pro Prozess?
- Graceful Degradation bei LLM-/Dienst-Ausfall? Dokumentierte BC-Tests?

**Umsetzungsidee**
- Rate-Limit-Store auf Redis/SQLite (workerübergreifend); dedizierte Limits für LLM/Export/Upload.
- Resource-Limits (compose `deploy.resources`) dokumentieren; Healthcheck + Auto-Restart (robust via #836).
- Lasttest-Skript + kurzer BC-Test-Nachweis in `docs/security/`.

## AI1-08 — Sicherheitsrelevantes Logging & Monitoring · #757
**Typ:** Code · **Aufwand:** M · **Status:** 🟡
Annex I Teil I (2)(g): Aufzeichnung/Überwachung sicherheitsrelevanter Aktivitäten.

**Fragenkatalog**
- Deckt `shared/audit.py` Auth, Autorisierung, Config-Änderungen, Exporte vollständig ab?
- Definierte **Aufbewahrungsdauer** + Rotation? Manipulationsschutz der Logs?
- SIEM-Anbindung (Syslog/JSON-Export) gewünscht/nötig?

**Umsetzungsidee**
- Audit-Event-Abdeckung als Checkliste verifizieren; Retention konfigurierbar (`AICS_AUDIT_RETENTION_DAYS`) + Rotation.
- Append-only/Hash-Chain für `audit.sqlite` (Tamper-Evidence).
- Optionaler JSON-Lines-Export für SIEM; Doku „Monitoring-Integration".

## AI1-09 — Updatefähigkeit / Sicherheitsupdates ermöglichen · #758
**Typ:** Gemischt · **Aufwand:** L · **Status:** 🟡
Annex I Teil I (2)(c): Schwachstellen durch Updates behebbar.

**Fragenkatalog**
- Wie erfährt ein Betreiber von einem verfügbaren Sicherheitsupdate (In-App-Hinweis, Watchtower, Release-Feed)?
- Sicherheitsupdates von Funktionsupdates getrennt (eigener Kanal/Tag)?
- Authentizität des Updates erzwungen (cosign-Verifikation beim Pull)?

**Umsetzungsidee**
- In-App-Versions-/Update-Hinweis: Backend vergleicht laufende Version mit GHCR-`latest`/Release-Feed → Banner.
- Getrennte Tags `:security` vs `:latest`; Release-Notes mit Security-Sektion.
- Deployment-Doku: cosign-Verify im Pull erzwingen.

## AI1-10 — Datenschutz by Design · #759
**Typ:** Gemischt · **Aufwand:** M · **Status:** 🟡
Annex I Teil I (2)(h)/(i): Datenminimierung, datenschutzfreundliche Defaults.

**Fragenkatalog**
- Welche personenbezogenen Daten verarbeitet/überträgt AICS (insb. an Cloud-LLM)?
- Greift Datenminimierung vor Cloud-Versand (PII-Redaction über Regex hinaus)?
- Sind die Defaults „privacy-friendly" (kein Cloud-Egress ohne Opt-in, lokale Ollama-Verarbeitung)?

**Umsetzungsidee**
- Verarbeitungsverzeichnis `docs/privacy/datenflüsse.md` (Art. 25 DSGVO-Bezug).
- PII-Erkennung vor Cloud-Versand erweitern (Namen/Adressen/Telefon) als opt-in-Filter; `allow_data_egress=false` als Default bestätigen.
- Test: Cloud-Pfad redigiert PII; Default blockiert Egress.

## AI2-01 — Schwachstellenidentifikation & -verfolgung · #843
**Typ:** Gemischt · **Aufwand:** M · **Status:** 🟡
Annex I Teil II (1): Komponenten identifizieren + Schwachstellen dokumentieren/behandeln.

**Fragenkatalog**
- Tooling ist da — wo werden offene Findings **verfolgt** (Tracker, Status, Owner, Frist)?
- Wird die SBOM mit den Findings korreliert (betroffene Komponente)?
- Gibt es einen wöchentlichen Triage-Rhythmus?

**Umsetzungsidee**
- GitHub Security Advisories + Issues als Tracker; Label-Schema `vuln:critical|high|...` + Owner + Frist.
- CVE-Watch-Job (täglicher OSV-Check gegen SBOM) öffnet/aktualisiert Tracking-Issues.
- Doku „Vulnerability-Management-Prozess".

## AI2-07 — Mechanismen für sichere Software-Updates · #849
**Typ:** Code · **Aufwand:** L · **Status:** 🟡
Annex I Teil II (7): sichere Update-Verteilung mit Authentizität/Integrität.

**Fragenkatalog**
- Images sind cosign-signiert — wird die Signatur beim Deployment **erzwungen**?
- Rollback bei fehlgeschlagenem Update? Integritätsprüfung zur Laufzeit?
- In-Product-Update-Trigger oder betreiberseitig (Portainer/Compose)?

**Umsetzungsidee**
- Deployment-Härtung: `cosign verify` + optionaler Sigstore-Policy-Controller; Compose-Wrapper mit Verify-Gate.
- Healthcheck-gestützter Auto-Rollback (robust via #836; Rollback-Recipe dokumentieren).
- Bewusste Design-Entscheidung dokumentieren: Verteilung via GHCR, kein In-Product-Autoupdate.

## IMPL-02 — Sicherer Entwicklungsprozess (Secure SDLC) · #859
**Typ:** Gemischt · **Aufwand:** M · **Status:** 🟡
Querschnitt: nachgewiesener sicherer Entwicklungsprozess.

**Fragenkatalog**
- Welche Security-Gates laufen in CI — sind sie verpflichtend (Branch-Protection)?
- Gibt es eine dokumentierte SDLC-Beschreibung (Phasen, Review-Kriterien, Threat-Modeling-Trigger)?
- Wie werden Security-Findings im PR-Prozess behandelt?

**Umsetzungsidee**
- `docs/security/secure-sdlc.md`: Phasenmodell, verpflichtende Gates, Review-Checkliste.
- Branch-Protection für `main` mit Required-Checks dokumentieren/aktivieren.
- PR-Template mit Security-Checkliste.

## IMPL-03 — Lieferkettensicherheit (Supply Chain) · #860
**Typ:** Gemischt · **Aufwand:** M · **Status:** 🟡
Querschnitt: Absicherung der Software-Lieferkette.

**Fragenkatalog**
- SBOM + cosign sind da — sind Base-Images auf **Digests gepinnt** (statt floating Tags)?
- Werden Dependencies gepinnt (Lockfiles) und regelmäßig erneuert?
- Wird die Signatur von Drittabhängigkeiten/Images verifiziert?

**Umsetzungsidee**
- Base-Images im `Dockerfile` auf `@sha256:`-Digests pinnen; Renovate/Dependabot aktualisiert.
- SBOM-Veröffentlichung als Release-Asset + Doku „Supply-Chain-Sicherheit".
- Optional: SLSA-Provenance-Attestation im Build.

---

# Sprint 2 — Doku / Nachweise

Herstellerpflichten, primär dokumentierte Nachweise (Annex V, Art. 13).

## ART13-01 — Cybersicherheits-Risikoabschätzung · #851
**Typ:** Doku · **Aufwand:** M · **Status:** 🔲

**Fragenkatalog**
- Liegt eine formale, versionierte Risikoabschätzung für AICS als Produkt vor?
- Ist sie Teil der technischen Doku und mit Maßnahmen verknüpft?
- Wer pflegt sie in welchem Rhythmus?

**Umsetzungsidee**
- AICS' Risikobewertungs-Modul auf das Produkt anwenden → `docs/cra/risikoabschätzung.md` (versioniert), verknüpft mit Threat-Model (AI1-01).

## ART13-02 — Technische Dokumentation & EU-Konformitätserklärung · #852
**Typ:** Doku · **Aufwand:** L · **Status:** 🔲

**Fragenkatalog**
- Welche Annex-V-Bestandteile fehlen (Beschreibung, Risikoabschätzung, SBOM, Tests, Support-Periode)?
- Wer ist Hersteller/Verantwortlicher für die EU-Konformitätserklärung (Annex VI)?
- Welche harmonisierten Normen werden referenziert?

**Umsetzungsidee**
- `docs/cra/technische-dokumentation/` als Annex-V-Struktur; pro Abschnitt vorhandene Artefakte verlinken (SBOM, Tests, Threat-Model).
- DoC-Template `docs/cra/EU-Konformitätserklärung.md` (Annex VI), generierbar.

## ART13-03 — Support-Zeitraum definieren & kommunizieren · #853
**Typ:** Doku · **Aufwand:** S · **Status:** 🔲

**Fragenkatalog**
- Welche Support-Periode wird zugesagt (Start ab Inverkehrbringen, Mindestdauer ≥ 5 Jahre)?
- Wie werden End-of-Life und Sicherheits-Support pro Version kommuniziert?
- Wo öffentlich sichtbar (README, SECURITY.md)?

**Umsetzungsidee**
- `SUPPORT.md` mit Support-Periode, Versions-Lifecycle-Tabelle, EOL-Daten; Verweis aus README/SECURITY.md.

## IMPL-04 — Produktklassifizierung & Konformitätsbewertungsweg · #761
**Typ:** Doku · **Aufwand:** M · **Status:** 🔲

**Fragenkatalog**
- Fällt AICS unter „Default", „Important" (Annex III) oder „Critical" (Annex IV)?
- Welcher Konformitätsbewertungsweg (Selbstbewertung vs. Notified Body)?
- Überprüfung bei wesentlichen Änderungen?

**Umsetzungsidee**
- `docs/cra/produktklassifizierung.md`: Mapping gegen Annex III/IV mit Begründung; abgeleiteter Bewertungsweg; Re-Review-Trigger.

## IMPL-05 — Technische Dokumentation: Lebenszyklus & Archivierung · #762
**Typ:** Doku · **Aufwand:** M · **Status:** 🔲

**Fragenkatalog**
- Wie/wo wird die technische Doku versioniert und ≥ 10 Jahre revisionssicher archiviert?
- Wie lange werden SBOMs/Testberichte/Release-Artefakte aufbewahrt (GitHub-Default 90 Tage genügt nicht)?
- Wer ist für Vollständigkeit/Backup zuständig?

**Umsetzungsidee**
- Archivierungs-Policy `docs/cra/archivierung.md` (10-Jahre-Retention, Speicherort, Verantwortliche).
- Release-Artefakte dauerhaft speichern (Release-Assets + externes Backup) statt CI-Default.

---

# Sprint 3 — Prozesse / Governance

Organisatorische Pflichten (Meldewege, Governance, Schulung). Nicht durch App-Code lösbar.

## ART14-01 — Meldung aktiv ausgenutzter Schwachstellen an ENISA · #855
**Typ:** Prozess · **Aufwand:** M · **Status:** 🔲
Art. 14: Frühwarnung (24h) / Meldung (72h) / Abschlussbericht.

**Fragenkatalog**
- Wer ist meldepflichtig/-berechtigt? ENISA-Single-Reporting-Platform-Zugänge eingerichtet?
- Welche Kriterien lösen eine Meldung aus? Eskalationskette?
- Wie werden die Fristen (24h/72h/14 Tage) sichergestellt?

**Umsetzungsidee**
- `docs/security/art14-meldeprozess.md`: Auslöser, Fristen, Meldekette, Vorlagen, ENISA-Kontoverwaltung; Integration mit Incident-Response (ART14-02).

## ART14-02 — Meldung schwerwiegender Cybersicherheitsvorfälle · #856
**Typ:** Prozess · **Aufwand:** M · **Status:** 🔲

**Fragenkatalog**
- Wie werden Vorfälle klassifiziert (Schweregrad, „schwerwiegend")?
- Triage-SLA („unverzüglich"), Eskalationspfade, Runbook?
- Wie greift das mit NIS2-Pflichten ineinander?

**Umsetzungsidee**
- `docs/security/incident-response-policy.md`: Klassifizierung, Runbook, Rollen, Kommunikationsvorlagen, Verknüpfung NIS2/ART14-01.

## ART14-03 — Kooperation mit CSIRT & Behörden · #857
**Typ:** Prozess · **Aufwand:** S · **Status:** 🔲

**Fragenkatalog**
- Welche CSIRTs/Behörden sind zuständig (BSI-CERT, ENISA, nationale CSIRTs)?
- Benannter Security-Ansprechpartner (24/7)?
- Übergabe-Checkliste für Behördenanfragen?

**Umsetzungsidee**
- `docs/security/csirt-kooperation.md`: Kontaktregister, Ansprechpartner, Übergabe-Checkliste.

## ART13-05 — Marktüberwachungs-Kooperation · #854
**Typ:** Prozess · **Aufwand:** S · **Status:** 🔲

**Fragenkatalog**
- Welche Informationen müssen kurzfristig bereitstellbar sein (Tech-Doku, DoC)?
- Welche SLA für Behördenanfragen? Wer koordiniert?

**Umsetzungsidee**
- `docs/cra/marktüberwachung.md`; nutzt Tech-Doku (ART13-02) als Audit-Pack (1-Klick-Export aus AICS denkbar).

## AI2-03 — Schnelle Behebung von Schwachstellen (Security Patches) · #845
**Typ:** Prozess · **Aufwand:** S · **Status:** 🟡

**Fragenkatalog**
- Gibt es CVSS-abhängige Patch-SLAs (z. B. Critical 24–72h, High 7 Tage)?
- Eskalationspfade, Verantwortliche, Notfall-Release-Prozess?

**Umsetzungsidee**
- SECURITY.md um CVSS-spezifische SLAs + Patch-/Eskalationsprozess ergänzen; Notfall-Release-Runbook.

## AI2-06 — Öffentliche Offenlegung behobener Schwachstellen · #848
**Typ:** Prozess · **Aufwand:** S · **Status:** 🟡

**Fragenkatalog**
- Wo werden behobene Schwachstellen veröffentlicht (GitHub Security Advisories, CHANGELOG-Security-Sektion)?
- Werden CVE-IDs vergeben/referenziert?

**Umsetzungsidee**
- Prozess „GitHub Security Advisory + Release-Notes-Security-Sektion" je behobener Schwachstelle; Doku in SECURITY.md.

## AI2-08 — Informationsaustausch zu Schwachstellen in Drittkomponenten · #850
**Typ:** Prozess · **Aufwand:** S · **Status:** 🟡

**Fragenkatalog**
- Wie werden Schwachstellen an Upstream-Projekte gemeldet (Coordinated Disclosure)?
- Wie werden Betreiber über betroffene Drittkomponenten informiert?

**Umsetzungsidee**
- Kurzprozess `docs/security/drittkomponenten.md`; SBOM + Advisories als Informationsbasis.

## IMPL-01 — Governance & Verantwortlichkeiten · #858
**Typ:** Prozess · **Aufwand:** M · **Status:** 🔲

**Fragenkatalog**
- Wer trägt die Cybersicherheits-Verantwortung (Product Security Owner, PSIRT)?
- Dokumentiertes Governance-Modell + Reporting-Cadence?

**Umsetzungsidee**
- `docs/security/governance.md` + `CODEOWNERS`; Rollen, Eskalation, Review-Rhythmus.

## IMPL-06 — Schulung & Awareness · #861
**Typ:** Prozess · **Aufwand:** S · **Status:** 🔲

**Fragenkatalog**
- Welche Schulungsinhalte (Secure Coding, Threat Modeling, Incident Response)?
- Wie wird Teilnahme nachgewiesen?

**Umsetzungsidee**
- Schulungskonzept + Nachweis-Tracker `docs/security/awareness.md`; AICS' DSGVO-Schulungsgenerator ggf. um CRA-Inhalte erweitern.

---

## Sprint-Übersicht

| Sprint | Fokus | Issues |
|--------|-------|--------|
| **1 — Code/Technik** | Produkt-Härtung, testbar | #838, #839, #841, #842, #756, #757, #758, #759, #843, #849, #859, #860 |
| **2 — Doku/Nachweise** | Annex V, Art. 13 | #851, #852, #853, #761, #762 |
| **3 — Prozesse/Governance** | Meldewege, Governance | #855, #856, #857, #854, #845, #848, #850, #858, #861 |

**Bereits erledigt:** #840 (AI1-03), #844 (AI2-02), #846 (AI2-04), #847 (AI2-05).

> Pflege erfolgt über das GitHub-Projekt **#14 „CRA-Konformität – AICS als Produkt"** (Felder: CRA-Bereich, Umsetzungstyp, Aufwand, Sprint, Status).
