# Module

Die AI Compliance Suite besteht aus mehreren funktionalen Modulen, die über die zentrale GUI zugänglich sind.

| Modul | Paket | Datenbankdatei | LLM |
|---|---|---|---|
| [BASO Fragebogen](baso.md) | `baso/` | `data/db/baso.sqlite` | ChatGPT (manuell) |
| [ICT Fragebogen](ict.md) | `ict/` | `data/db/ict.sqlite` | ChatGPT (manuell) |
| [DSGVO-Compliance](dsgvo.md) | `dsgvo/` | `data/db/dsgvo.sqlite` | – |
| [NIS2-Umsetzung](nis2.md) | `nis2/` | `data/db/nis2.sqlite` | – |
| [CRA-Readiness](cra.md) | `cra/` | `data/db/cra.sqlite` | optional (Auto-fill via Evidence) |
| [AI Act Readiness](ai-act.md) | `ai_act/` | `data/db/ai_act.sqlite` | optional (deterministic Prefill) |
| [Compliance Bewertung](compliance.md) | `compliance/` | `data/db/compliance.sqlite` | ChatGPT (manuell) |
| [Compliance-DB (RAG)](compliance-db.md) | `compliance_db/` | `data/db/compliance_db.sqlite` | Ollama (lokal) |
| [Gutachten](gutachten.md) | `gutachten/` | `data/db/gutachten.sqlite` | ChatGPT (manuell) |
| [Risikobewertung](risikobewertung.md) | `risikobewertung/` | `data/db/risikobewertung.sqlite` | Ollama (lokal) |
| [Kundenverwaltung](kunden.md) | `kunden/` | `data/db/kunden.sqlite` | – |
