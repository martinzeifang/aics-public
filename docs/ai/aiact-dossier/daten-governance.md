# Daten-Governance (AIA-HR-02 · AIA-DATA-01 · AIA-DATA-02 · Art. 10)

## Grundsatz: kein eigenes Training

Die AICS **trainiert, feintunt oder validiert keine Modelle**. Sie nutzt vortrainierte Modelle
(Ollama-Modelle bzw. Cloud-Modelle) im Inferenzbetrieb. Art. 10 Abs. 2–5 (Trainings-, Validierungs-
und Testdaten) betrifft daher die **Modellanbieter**; die Suite verantwortet die Qualität der
**Eingabedaten** (Prompts) und den Umgang mit ihnen.

## Datenquellen und Lineage (AIA-DATA-01)

| Quelle | Inhalt im Prompt | Herkunft / Nachvollziehbarkeit |
|---|---|---|
| Anforderungskataloge | Anforderungstext, Hinweise, Rubrik | versioniert im Repo (`<modul>/requirements*.py`, BSI-WiBA-Katalog zur Laufzeit geladen) |
| Projekt-/Bewertungsdaten | Bewertung, Kommentar, Maßnahme | Modul-Datenbanken (Postgres, Audit-Trail) |
| App-Nachweise | Register-Auszüge (VVT, TOM, SBOM, Risiken …) | `shared/evidence_context.py`; je Bewertung als `genutzte_nachweise` + Audit `ai.assessment.evidence_used` protokolliert (#1485) |
| Issue-Feedback | Titel/Status/Kommentare verknüpfter Issues | `shared/issue_feedback.py`, Quelle (URL) im Ergebnis |
| Firmen-Uploads | Nachweisdokumente | `firm_upload_items` (Magic-Bytes-Validierung, SHA-256) |

Jede KI-Bewertung kann damit auf die verwendeten Quellen zurückgeführt werden
(Provenienz in Ergebnis + Audit-Trail).

## Datenqualität und Datenschutz (AIA-HR-02)

- **Minimierung:** Prompts enthalten nur die für die jeweilige Anforderung relevanten Daten
  (Provider-Mapping je Anforderung, Ranking + Kürzung in `rank_and_truncate`).
- **Schutz bei Cloud-Nutzung:** als `sensitive` markierte Nachweise (z. B. Datenpannen) werden
  für Cloud-Provider redigiert (`redact_for_cloud`); App-Nachweise gehen nur per Opt-in in die
  Cloud (`ai.include_app_evidence`).
- **Kein Logging von Inhalten:** Audit-Einträge zu KI-Aufrufen enthalten nur Metadaten
  (siehe [Logging](logging.md)).
- **Strukturierte Ausgaben:** Antworten werden gegen ein festes JSON-Schema geparst; ungültige
  Antworten werden verworfen statt teilweise übernommen.

## Bias und Fairness (AIA-DATA-02)

**Risikoeinschätzung:** Die Suite bewertet **Organisationen, Systeme und Prozesse**, keine
natürlichen Personen. Diskriminierende Auswirkungen auf Personen (Art. 10 Abs. 2 f) sind durch die
Zweckbestimmung ausgeschlossen. Relevante Verzerrungen sind fachlicher Natur:

| Verzerrung | Gegenmaßnahme |
|---|---|
| Überbewertung bei viel Text/Nachweisen („Masse statt Substanz") | Rubrik je Anforderung im Prompt, Begründungspflicht, Normbezug; inhaltsbasierte Scores statt Pauschalen (z. B. HR-01 #1561) |
| Sprach-/Formulierungsabhängigkeit | einheitliche Prompt-Vorlagen je Modul, deterministische Temperatur (0.2) |
| Modellabhängigkeit | Provider/Modell je Aufruf protokolliert; Modellwechsel als Change mit Stichprobenvergleich |

**Prüfung:** Bei jedem Modellwechsel und mindestens jährlich wird eine Stichprobe von ≥ 10
Anforderungen je Modul mit dem neuen und dem bisherigen Modell bewertet; Abweichungen > 1
Score-Punkt werden fachlich begutachtet und dokumentiert (Ergebnis im Release-Issue).
