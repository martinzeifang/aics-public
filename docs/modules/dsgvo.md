# DSGVO-Compliance-Prüfung

Das DSGVO-Modul (`dsgvo/`) unterstützt die strukturierte Prüfung der DSGVO-Compliance (EU 2016/679) für Organisationen.

## Funktionen

- **Anforderungsbewertung**: Bewertung von DSGVO-Anforderungen mit Erfüllungsgrad
- **Berichtswesen**: DOCX- und PDF-Berichte zum DSGVO-Reifegrad
- **TOM**: Technische und organisatorische Maßnahmen (Art. 32 DSGVO) als DOCX
- **VVT**: Verarbeitungsverzeichnis-Management
- **Datenschutz-Folgenabschätzung (DPIA)**: Unterstützung für Art. 35 DSGVO
- **Schulungsunterlagen**: Jährliche DSGVO-Schulungsinhalte als DOCX
- **KI-Vorschläge**: Automatische Bewertungsvorschläge basierend auf hochgeladenen Nachweisen (über die `prefill`-Engine mit Ollama oder OpenAI-kompatiblem Backend)

## Datenhaltung

| Aspekt | Details |
|---|---|
| **Datenbank** | `data/db/dsgvo.sqlite` |
| **Eingabeformate** | XLSX (Fragebogen-Import) |
| **Ausgabeformate** | DOCX (Bericht, Datenschutzerklärung, TOM, Schulung), PDF (Bericht) |
| **LLM** | Optional (Ollama / OpenAI via Prefill-Engine) |

## GUI-Start

```bash
python -m dsgvo
```

Oder als Tab in der AI Compliance Suite.
