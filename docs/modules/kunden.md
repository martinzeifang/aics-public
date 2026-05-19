# Kundenverwaltung

Das Kunden-Modul (`kunden/`) ist das zentrale Mandanten-Management der AI Compliance Suite. Es verwaltet Kunden- und Produktdaten und steuert die Module-Sichtbarkeit pro Mandant.

## Funktionen

- **Kundenverwaltung**: Anlegen, Bearbeiten und Löschen von Kunden (Mandanten)
- **Produktzuordnung**: Verknüpfung von Produkten mit Kunden
- **Framework-Selektion**: Zuweisung regulatorischer Frameworks pro Kunde (DORA, NIS2, CRA, ISO 27001, DSGVO, AI Act, BSI)
- **Risikomethodik**: Auswahl der Risikobewertungsmethodik (STRIDE, HEAVENS, OCTAVE, TARA, CVSS, FI)
- **Modul-Steuerung**: Aktivieren/Deaktivieren von Compliance-Modulen pro Kunde
- **Mandantentrennung**: Grundlage für die mandantenscharfe Trennung der Nachweisbibliothek (`evidence/`)

## Datenhaltung

| Aspekt | Details |
|---|---|
| **Datenbank** | `data/db/kunden.sqlite` |
| **LLM** | Nicht erforderlich (reines CRUD-Modul) |

## GUI-Start

Das Kunden-Modul ist nur als Tab in der AI Compliance Suite verfügbar (kein Standalone-Start).
