# Qualitätsmanagement und Change-Management (AIA-GOV-01 · AIA-GOV-02 · Art. 17)

Das QMS der AICS ist schlank und werkzeuggestützt: Es nutzt die Prozesse, die im Repository
ohnehin verbindlich sind (Issue-First, Pull-Request, CI-Gates, Release-Tags), und ergänzt sie um
die KI-spezifischen Prüfpunkte. Die Elemente nach Art. 17 Abs. 1:

| Art. 17 Abs. 1 | Umsetzung |
|---|---|
| a) Konformitätsstrategie | dieses Dossier; jährliche Neubewertung der Suite im eigenen AI-Act-Modul |
| b) Design, Designkontrolle | Issue-First-Workflow mit Akzeptanzkriterien; Pull-Request je Änderung |
| c) Entwicklung, Qualitätskontrolle | CI: pytest (Postgres), Frontend-Build, Typecheck, SAST, Secret-Scan, Dependency-Audit |
| d) Prüfung und Validierung | Tests je Feature (`tests/test_*_<issue>.py`), Firefox-E2E-Smoke (`tools/e2e/`) |
| e) technische Spezifikationen | [Technische Dokumentation](technische-dokumentation.md) |
| f) Datenmanagement | [Daten-Governance](daten-governance.md) |
| g) Risikomanagement | [Risikomanagement](risikomanagement.md) |
| h) Post-Market-Monitoring | [Marktbeobachtung & Vorfälle](marktbeobachtung-vorfaelle.md) |
| i) Meldung schwerwiegender Vorfälle | [Marktbeobachtung & Vorfälle](marktbeobachtung-vorfaelle.md#incident-management-aia-hr-09) |
| j) Kommunikation | Release-Notes (Release-Commit + Tag), öffentliche Doku-Site, GitHub-Issues |
| k) Aufzeichnungen | Git-Historie, Audit-Trail, CI-Artefakte |
| l) Ressourcen | siehe Rollen |
| m) Verantwortlichkeiten | siehe Rollen |

## Rollen

| Rolle | Aufgabe |
|---|---|
| Produktverantwortliche:r | Freigabe von Releases mit KI-Bezug, Akzeptanz von Restrisiken, Pflege dieses Dossiers |
| Entwicklung | Umsetzung über Issues/PRs, Tests, Aktualisierung der Doku |
| Review | Prüfung jedes PRs inkl. KI-Checkliste (unten) |
| Betrieb (je Installation) | Provider-/Modellkonfiguration, Cloud-Freigabe, Aufbewahrung der Audit-Logs |

## Change-Management (AIA-GOV-02)

Jede Änderung läuft über **Issue → Branch → Pull-Request → CI → Merge → Release-Tag**
(`v<major>.<minor>.<patch>`, Container-Image versioniert). Konfiguration ist versioniert
(`*.config.json`-Defaults im Code, Laufzeitkonfiguration je Installation).

**KI-Checkliste im Review** — ein Change ist *KI-relevant*, wenn er eine der folgenden Fragen
mit „ja" beantwortet; dann sind Risikoregister und Dossier zu prüfen:

- [ ] Neue oder geänderte KI-Funktion, Prompt-Vorlage oder Antwort-Parser?
- [ ] Neuer Provider, neues Standardmodell oder geänderte Modellparameter?
- [ ] Geänderte Daten, die in Prompts einfließen (neue Nachweisquellen)?
- [ ] Änderung an Egress-, Redaktions-, Kennzeichnungs- oder Logging-Logik?

Ein **Modellwechsel** in einer Installation ist ein Change im Betrieb: Stichprobenvergleich nach
[Daten-Governance](daten-governance.md#bias-und-fairness-aia-data-02), Dokumentation im Betriebs-Log.

## Interne Audits

Mindestens jährlich: Neubewertung der Suite im eigenen AI-Act-Modul, Abgleich mit diesem Dossier,
offene Lücken als Issues. Ergebnis im Release-Issue des nächsten Releases.

## Freigabe

| Version des Dossiers | Datum | Freigegeben durch |
|---|---|---|
| 1.0 (Sprint #45) | 2026-10-15 | *ausstehend — Produktverantwortliche:r* |

> Das QMS gilt ab Freigabe. Bis dahin beschreibt es die gelebte Praxis im Repository.
