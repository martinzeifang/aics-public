# DSGVO-Compliance-Prüfung

Das DSGVO-Modul unterstützt die strukturierte Prüfung der
DSGVO-Compliance (EU 2016/679) für Organisationen.

## Funktionen

- **Anforderungsbewertung**: DSGVO-Anforderungen mit Erfüllungsgrad
- **TOM-Generator**: Technische und organisatorische Maßnahmen
  (Art. 32 DSGVO) als DOCX
- **Datenschutzerklärung (DSE)**: Vorlage + Generator
- **VVT**: Verarbeitungsverzeichnis-Management
- **DPIA**: Unterstützung für Datenschutz-Folgenabschätzungen (Art. 35)
- **Schulungsunterlagen**: jährliche DSGVO-Schulungsinhalte als DOCX
- **KI-Vorschläge**: Automatische Bewertungsvorschläge auf Basis
  hochgeladener Nachweise (Prefill-Engine, Ollama oder OpenAI)

## Datenhaltung

| Aspekt | Details |
|---|---|
| **Datenbank** | `data/db/dsgvo.sqlite` |
| **Eingabe** | XLSX-Fragebogen, manuelle Erfassung im Editor |
| **Ausgabe** | DOCX (Bericht, Datenschutzerklärung, TOM, Schulung), PDF |
| **KI** | optional (Ollama oder OpenAI via Prefill-Engine) |

Erreichbar in der Web-App unter `/dsgvo`.
