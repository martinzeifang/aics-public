# Architektur

Dieser Abschnitt beschreibt die technische Architektur der AI Compliance Suite.

- [Datenbankschemas](database-schemas.md) – Alle SQLite-Tabellen im Detail

## Überblick

Die Suite ist eine modulare Web-Anwendung:

- **Backend**: Flask + SQLAlchemy + SQLite (eine Datei pro Compliance-Modul)
- **Frontend**: Vue 3 + Pinia + Vite, ausgeliefert über Nginx
- **KI-Anbindung**: Adapter-Schicht für lokale (Ollama) und Cloud-Anbieter
- **Auslieferung**: Docker Compose Stack (Backend + Frontend + Nginx + optional Ollama)

Jedes Compliance-Modul (CRA, NIS2, AI Act, DSGVO, …) folgt dem gleichen Pattern:

1. **Fragenkatalog** aus YAML/SQLite laden
2. **Antworten** strukturiert erfassen (manuell oder KI-unterstützt)
3. **Evidence** als Datei-Anhänge oder Issue-Links zuordnen
4. **Berichte** als DOCX/XLSX/PDF exportieren

Details zu den Datenbankstrukturen findest du auf der Seite [Datenbankschemas](database-schemas.md).
