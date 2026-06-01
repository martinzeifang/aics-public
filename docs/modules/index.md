# Module

Die AI Compliance Suite besteht aus mehreren Web-Modulen, die über die zentrale Oberfläche zugänglich sind.

| Modul | Paket | Datenbankdatei | KI-Unterstützung |
|---|---|---|---|
| [CRA-Readiness](cra.md) | `cra/` | `data/db/cra.sqlite` | optional (Auto-fill via Evidence) |
| [NIS2-Umsetzung](nis2.md) | `nis2/` | `data/db/nis2.sqlite` | – |
| [DSGVO-Compliance](dsgvo.md) | `dsgvo/` | `data/db/dsgvo.sqlite` | – |
| [AI Act Readiness](ai-act.md) | `ai_act/` | `data/db/ai_act.sqlite` | optional (deterministic Prefill) |
| [Risikobewertung](risikobewertung.md) | `risikobewertung/` | `data/db/risikobewertung.sqlite` | Ollama (lokal) |
| [Gutachten](gutachten.md) | `gutachten/` | `data/db/gutachten.sqlite` | optional |
| [Kundenverwaltung](kunden.md) | `kunden/` | `data/db/kunden.sqlite` | – |

Alle Module teilen ein gemeinsames Authentifizierungs-, Audit- und Backup-System
sowie die zentrale KI-Anbieter-Schnittstelle.
