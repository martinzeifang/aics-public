# Firmenverwaltung

Das Firmen-Modul (`firmen/`) ist das zentrale Mandanten-Management der AI Compliance Suite. Es verwaltet Firmen- und Produktdaten und steuert die Module-Sichtbarkeit pro Mandant.

## Funktionen

- **Firmenverwaltung**: Anlegen, Bearbeiten und Löschen von Firmen (Mandanten)
- **Produktzuordnung**: Verknüpfung von Produkten mit Firmen
- **Framework-Selektion**: Zuweisung regulatorischer Frameworks pro Firma (DORA, NIS2, CRA, ISO 27001, DSGVO, AI Act, BSI)
- **Risikomethodik**: Auswahl der Risikobewertungsmethodik (STRIDE, HEAVENS, OCTAVE, TARA, CVSS, FI)
- **Modul-Steuerung**: Aktivieren/Deaktivieren von Compliance-Modulen pro Firma
- **Mandantentrennung**: Grundlage für die mandantenscharfe Trennung der Nachweisbibliothek (`evidence/`)

## Datenhaltung

| Aspekt | Details |
|---|---|
| **Datenbank** | `data/db/firmen.sqlite` |
| **LLM** | Nicht erforderlich (reines CRUD-Modul) |

## GUI-Start

Das Firmen-Modul ist nur als Tab in der AI Compliance Suite verfügbar (kein Standalone-Start).
