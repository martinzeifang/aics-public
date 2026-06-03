# AI Act Readiness

Das Modul `ai_act/` bildet eine projektbasierte Readiness-Bewertung fuer den EU AI Act (EU 2024/1689) ab.

## Umfang

- Projektverwaltung (nicht firmenbasiert)
- Anforderungskatalog mit Bewertung (0..5) inkl. Kommentar und Maßnahme
- Dashboard mit gewichteter Readiness-Berechnung
- Integration: Repo-Linking (GitHub/GitLab Settings) und CI-Evidence Import (GitHub)
- Deterministische Auto-fill Vorschlaege aus Repo-Signalen und CI-Evidence (als Prefill-Vorschlaege mit Review)

## Datenhaltung

- Modul-DB: `data/db/ai_act.sqlite`
- Evidence-DB (shared): `data/db/evidence.sqlite`

AI Act scoped Evidence: aktuell wird `firmen_id = <Projektname>` verwendet.

## Auto-fill (deterministisch)

Die Buttons erzeugen Prefill-Vorschlaege (Tabelle `prefill_suggestions`) und schreiben nicht direkt in die Bewertungen.
Über `Vorschlaege pruefen...` können Vorschlaege akzeptiert oder abgelehnt werden.
