# Nachweis-zu-Anforderung Mapping

Dieses Dokument beschreibt den ersten Mapping-Schritt: Der konfigurierte KI-Anbieter schlägt vor, welche Evidenz-Chunks eine bestimmte Anforderung unterstützen.

## Implementierung

- Code: `mapping/suggest.py`
- Einstiegspunkt: `suggest_mappings(...)`

## Eingaben

- `requirement_id`, `requirement_title`, `requirement_text`
- `evidence_chunks`: Liste von Dicts mit:
  - `doc_id`
  - `chunk_idx`
  - `text`

Die Evidence-Chunks kommen aus der Evidence-DB (`evidence/db.py`).

## Output-Schema

Der Anbieter wird angewiesen, striktes JSON zurückzugeben:

```json
{
  "requirement_id": "REQ-123",
  "suggestions": [
    {
      "claim": "...",
      "citations": [{"doc_id": "...", "chunk": 1}],
      "confidence": 0.7,
      "rationale": "..."
    }
  ]
}
```

Das Parsing ist strikt: Nicht-JSON-Ausgabe schlägt sofort mit einer verständlichen Fehlermeldung fehl. Damit arbeiten UI/Storage immer mit validierten Strukturen.
