# Technische Dokumentation (AIA-HR-03 · Art. 11 · Anhang IV)

Die technische Dokumentation der AICS ist über die bestehende Projektdokumentation verteilt.
Diese Seite ordnet sie den Punkten von Anhang IV zu.

| Anhang IV | Inhalt | Fundstelle |
|---|---|---|
| Nr. 1 a | Zweckbestimmung, Anbieter, Version | [Dossier-Übersicht](index.md); Version in `frontend/package.json`, im Image (`APP_VERSION`) und unter *Einstellungen → Version & Updates* |
| Nr. 1 b–d | Zusammenspiel mit Hardware/Software, Versionen, Bereitstellungsform | [Architektur](../../architecture/overview.md), [Docker-Deployment](../../web/deployment.md), SBOM-Workflows (`.github/workflows/*-sbom.yml`) |
| Nr. 1 e–h | Benutzeroberfläche, Gebrauchsanweisung | Modul-Dokumentation (`docs/modules/`), In-App-Hilfe, Benutzer-Wiki |
| Nr. 2 a, b | Entwicklungsmethoden, Systemarchitektur, Integration vortrainierter Modelle | [KI-Anbieter-Schnittstelle](../provider-interface.md), [On-Prem](../on-prem.md), [Cloud](../cloud.md) |
| Nr. 2 d | Daten | [Daten-Governance](daten-governance.md) |
| Nr. 2 e | Menschliche Aufsicht | [Menschliche Aufsicht](menschliche-aufsicht.md) |
| Nr. 2 g, h | Validierung, Tests, Cybersicherheit | [Robustheit & Cybersicherheit](robustheit-cybersicherheit.md); pytest-Suite (`tests/`), CI (`.github/workflows/ci.yml`) |
| Nr. 3 | Überwachung, Funktionsweise, Grenzen | [Wie funktionieren die KI-Funktionen?](../../ki-funktionen.md), [Transparenz](transparenz.md) |
| Nr. 5 | Risikomanagement | [Risikomanagement](risikomanagement.md) |
| Nr. 6 | Änderungen über den Lebenszyklus | [QMS & Change-Management](qms-change-management.md); Git-Historie, Release-Tags, GitHub-Issues |
| Nr. 9 | Post-Market-Monitoring | [Marktbeobachtung & Vorfälle](marktbeobachtung-vorfaelle.md) |

## Evidence-Pack

Die Workflows `ai-act-evidence-pack.yml`, `ai-act-sbom.yml` und `ai-act-osv-scan.yml` erzeugen
reproduzierbare Nachweispakete (SBOM, Schwachstellen-Scan, Dokumentation) als CI-Artefakte.

## Aufbewahrung

Technische Dokumentation und Release-Artefakte werden über das Git-Repository und die
veröffentlichten Container-Images (versioniert, `ghcr.io`) aufbewahrt; Art. 18 (10 Jahre) wird
über die Repository- und Registry-Aufbewahrung des Anbieters sichergestellt.
