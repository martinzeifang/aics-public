# NIS2-Umsetzungsprüfung

Das NIS2-Modul unterstützt die Umsetzungsprüfung der NIS2-Richtlinie
(EU 2022/2555) für Organisationen.

## Funktionen

- **Anforderungsbewertung**: NIS2-Anforderungen differenziert nach
  Einrichtungstyp („wesentlich" / „erheblich")
- **Berichtswesen**: DOCX- und PDF-Berichte zum Umsetzungsstand
- **Klassifizierung**: Unterstützung für die Einstufung nach
  §§ 28–31 NIS2-Umsetzungsgesetz (NIS2UmsuCG)
- **KI-Vorschläge**: Automatische Bewertungsvorschläge auf Basis hochgeladener
  Nachweise (Prefill-Engine, Ollama oder OpenAI-kompatibel)

## Datenhaltung

| Aspekt | Details |
|---|---|
| **Datenbank** | `data/db/nis2.sqlite` |
| **Eingabe** | XLSX-Fragebogen, manuelle Erfassung im Editor |
| **Ausgabe** | DOCX (Bericht), PDF (Bericht) |
| **KI** | optional (Ollama oder OpenAI via Prefill-Engine) |

Erreichbar in der Web-App unter `/nis2`.
