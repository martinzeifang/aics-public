# NIS2-Umsetzungsprüfung

Das NIS2-Modul (`nis2/`) unterstützt die Umsetzungsprüfung der NIS2-Richtlinie (EU 2022/2555) für Organisationen.

## Funktionen

- **Anforderungsbewertung**: Bewertung von NIS2-Anforderungen differenziert nach Einrichtungstyp ("wesentlich" / "erheblich")
- **Berichtswesen**: DOCX- und PDF-Berichte zum NIS2-Umsetzungsstand
- **Klassifizierung**: Unterstützung für die Einstufung nach §§ 28–31 NIS2-Umsetzungsgesetz (NIS2UmsuCG)
- **KI-Vorschläge**: Automatische Bewertungsvorschläge basierend auf hochgeladenen Nachweisen (über die `prefill`-Engine mit Ollama oder OpenAI-kompatiblem Backend)

## Datenhaltung

| Aspekt | Details |
|---|---|
| **Datenbank** | `data/db/nis2.sqlite` |
| **Eingabeformate** | XLSX (Fragebogen-Import) |
| **Ausgabeformate** | DOCX (Bericht), PDF (Bericht) |
| **LLM** | Optional (Ollama / OpenAI via Prefill-Engine) |

## GUI-Start

```bash
python -m nis2
```

Oder als Tab in der AI Compliance Suite.
