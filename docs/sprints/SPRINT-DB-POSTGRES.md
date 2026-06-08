# Sprint: PostgreSQL-Migration (AICS Web)

> Vollständiger Umstieg des Webserver-Projekts von **SQLite** auf **PostgreSQL** (eigenes Docker-Image).

- **GitHub-Projekt:** [PostgreSQL-Migration (AICS Web) — Projekt #15](https://github.com/users/martinzeifang/projects/15)
- **EPIC:** [#889](https://github.com/martinzeifang/AI_Compliance_Suite/issues/889)
- **Projekt-Felder:** `Phase` (P1–P5), `Aufwand` (S/M/L/XL), `Risiko` (Niedrig/Mittel/Hoch)

---

## 1. Ziel

Ablösung der 13 SQLite-Datenbanken durch einen zentralen PostgreSQL-Dienst, um:

- die unter mehreren gunicorn-Workern auftretenden **DB-Lock-Probleme** (#837) endgültig zu beseitigen,
- transaktionssichere, gleichzeitige Zugriffe (4 Worker) zu ermöglichen,
- den Datenzugriff hinter einer **SQLAlchemy-Abstraktion** zu vereinheitlichen und wartbar zu machen,
- ein versioniertes Schema (Alembic) und robuste Backups (pg_dump) zu etablieren.

---

## 2. Faktenlage (mit Belegen)

| Befund | Beleg |
|---|---|
| 13 SQLite-DBs: users, cra, risikobewertung, gutachten, baso, dsgvo, nis2, ai_act, evidence, firmen, dora, ict, compliance | `*/db.py` + `server/auth/users_db.py` |
| 555 rohe `sqlite3`-`.execute()`-Aufrufe in 54 Dateien | repo-weiter Grep `import sqlite3` / `.execute(` |
| KEIN ORM real aktiv; SQLAlchemy nur im Server-Config + Tests | `server/config/database.py` |
| `database.py` = per-DB `DbManager` für SQLite, festes Mapping `{users, cra, audit}`, keine `DATABASE_URL`-Auswertung | `server/config/database.py:27-34` (Mapping), `:72-91` (`_create_engine`, `sqlite:///` + `connect_args`), `:152-176` (`get_session`/`transaction`) |
| 4 gunicorn-Worker | `docker-compose.yml:88` (`GUNICORN_WORKERS=4`) |
| Kein DB-Dienst im Compose (Services `web`/`nginx`/`ollama`); `web` hat bereits Healthcheck | `docker-compose.yml:52-145` (`web`), `:127-137` (Healthcheck), `:277-283` (Volumes) |
| Kein `docker-compose.test.yml` vorhanden | Repo-Root |
| CI-Job `test` ohne DB-Service, `pytest --cov` | `.github/workflows/ci.yml:20-44`, `:37-44` |
| Backup = ZIP der `*.sqlite` (inkl. WAL/SHM) + WAL-Checkpoint | `ai_compliance_suite/backup.py:25` (`_DB_GLOB`), `:34` (`_collect_files`), `:56` (`_checkpoint_wal`), `:113` (`create_backup`), `:259` (`restore_backup`) |

### Dialekt-Risiken (verifizierte repo-weite Treffer im Python-Code)

| Konstrukt | Treffer | Postgres-Ersatz |
|---|---|---|
| `datetime('now')` | ~201 | `NOW()` / `func.now()` / Server-Default |
| `PRAGMA` | ~60 | entfernen / Postgres-Settings |
| `ON CONFLICT` (bereits vorhanden) | ~49 | Conflict-Target erforderlich, Syntax prüfen |
| `AUTOINCREMENT` | ~27 | `IDENTITY` / `SERIAL` — z. B. `server/auth/users_db.py:110` |
| `INSERT OR IGNORE/REPLACE` | ~14 | `INSERT ... ON CONFLICT DO NOTHING/UPDATE` — z. B. `server/auth/users_db.py:543` |
| `GLOB` | ~6 | `~` (POSIX-Regex) / `LIKE` / `SIMILAR TO` |
| dynamische/typenlose Spalten | — | konkrete Postgres-Typen |

### Pro-Modul (`.execute()` / Zeilen)

| Modul | Datei | execute | Zeilen |
|---|---|---|---|
| users | `server/auth/users_db.py` | 57* | 199 |
| CRA | `cra/db.py` | 42 | 336 |
| Risikobewertung | `risikobewertung/db.py` | 18 | 345 |
| NIS2 | `nis2/db.py` | 42 | 657 |
| AI Act | `ai_act/db.py` | 21 | 372 |
| DSGVO | `dsgvo/db.py` | 23 | 329 |
| Gutachten | `gutachten/db.py` | 10 | 233 |
| Firmen | `firmen/db.py` | 42 | 420 |
| Evidence | `evidence/db.py` | 14 | 247 |
| BASO | `baso/db.py` | 11 | 263 |
| ICT | `ict/db.py` | 11 | 148 |
| Compliance | `compliance/db.py` | 46 | 131 |

\* `users_db.py` `.execute`-Zählung inkl. SQLAlchemy-`.execute`-Vorkommen.

---

## 3. Migrationsstrategie: modulweise (empfohlen)

**Empfehlung: modulweise hinter einer SQLAlchemy-Abstraktion — kein Big-Bang.**

| | Big-Bang | Modulweise (empfohlen) |
|---|---|---|
| Risiko | Hoch — alles auf einmal, schwer testbar | Verteilt, je Modul isoliert testbar |
| Rollback | Nur global | Pro Modul möglich |
| Aufwand-Spitze | Eine große, riskante PR | Viele kleine, reviewbare PRs |
| Fortschritt | Binär | Inkrementell messbar |

**Vorgehen:** Zuerst Fundament (Engine/Pool + Alembic + Postgres-Dienst, P1). Dann jedes Modul einzeln auf den zentralen Layer portieren (P2), parallel der repo-weite Dialekt-Fix. Anschließend Datenmigration + Tests (P3), kontrollierter Cutover (P4) und Betrieb/Cleanup (P5). Während P2 kann SQLite als Fallback (`DATABASE_URL`) erhalten bleiben.

---

## 4. Phasen P1–P5

- **P1 Fundament:** Postgres-Docker-Service, SQLAlchemy-Engine/Pool, Alembic. → #890, #891, #892
- **P2 DAL/ORM:** Dialekt-Audit (#893) + 12 Modul-Portierungen (#899–#910).
- **P3 Migration:** Datenmigrations-Skript (#894) + Postgres-Tests (#895).
- **P4 Cutover:** Cutover-Plan (#896) + pg_dump/pg_restore-Backup (#897).
- **P5 Betrieb:** Monitoring, Pool-Tuning, Cleanup (#898).

---

## 5. Issues im Detail

### EPIC — [#889](https://github.com/martinzeifang/AI_Compliance_Suite/issues/889) · Aufwand XL · Risiko Hoch
Übersicht der Gesamtmigration; verweist auf diese Plan-Doku und Projekt #15.

### P1 Fundament

**#890 — Postgres-Docker-Service (compose, Healthcheck, Volume, Secrets)** · M · Mittel
Service `db` in `docker-compose.yml`, Volume `aics-pgdata`, `pg_isready`-Healthcheck, `POSTGRES_*`-Secrets, `web` mit `depends_on (service_healthy)` + `DATABASE_URL`. Postgres auch für Test-Setup (kein `docker-compose.test.yml` vorhanden).
AK: Dienst läuft, Volume persistent, Healthcheck grün, keine Klartext-Secrets, `web` erreicht DB.

**#891 — SQLAlchemy-Engine/Session + Connection-Pool** · M · Mittel
`server/config/database.py` auf Postgres umstellen: `DATABASE_URL`-Env einführen (Fallback sqlite nur Dev/Test), `pool_size`/`max_overflow`/`pool_pre_ping`/`pool_recycle`, SQLite-`connect_args` nur im SQLite-Zweig, vollständige Session-Helfer, `psycopg` in requirements.
AK: Pool an 4 Worker angepasst und dokumentiert.

**#892 — Alembic-Migrationsframework** · M · Mittel
`alembic.ini` + `migrations/`, `env.py` an `Base`/`DATABASE_URL`, Baseline-Migration, autogenerate-Workflow, Deploy-Hook.
AK: `alembic upgrade head` baut Schema in leerer DB.

### P2 DAL/ORM

**#893 — SQL-Dialekt-Audit + Fix** · L · Hoch
Repo-weite Beseitigung von `datetime('now')` (~201), `PRAGMA` (~60), `AUTOINCREMENT` (~27), `INSERT OR IGNORE/REPLACE` (~14), `GLOB` (~6); `ON CONFLICT`-Syntax (~49) prüfen; dynamische Typen konkretisieren.
AK: Grep nach Mustern liefert in produktivem Code keine Treffer.

Modul-Portierungen (je: `sqlite3` raus → zentrale Engine/Session, Schema via Alembic, Dialekt-Fix, parametrisierte Queries, Tests grün gegen Postgres):

| Issue | Modul | Aufwand | Risiko |
|---|---|---|---|
| #899 | users (`server/auth/users_db.py`) | M | Hoch |
| #900 | CRA (`cra/db.py`) | L | Mittel |
| #901 | Risikobewertung (`risikobewertung/db.py`) | M | Mittel |
| #902 | NIS2 (`nis2/db.py`) | L | Mittel |
| #903 | AI Act (`ai_act/db.py`) | M | Mittel |
| #904 | DSGVO (`dsgvo/db.py`) | M | Mittel |
| #905 | Gutachten (`gutachten/db.py`) | S | Niedrig |
| #906 | Firmen (`firmen/db.py`) | L | Mittel |
| #907 | Evidence (`evidence/db.py`) | M | Mittel |
| #908 | BASO (`baso/db.py`) | M | Mittel |
| #909 | ICT (`ict/db.py`) | S | Niedrig |
| #910 | Compliance (`compliance/db.py`) | M | Mittel |

> Hinweis: Die DB `dora` (`dora/db.py`) ist nicht als eigenes Portierungs-Issue gelistet; sie wird im Rahmen des Dialekt-Audits (#893) und der Datenmigration (#894) mitgeführt und kann bei Bedarf als zusätzliches P2-Sub-Issue ergänzt werden.

### P3 Migration

**#894 — Datenmigrations-Skript SQLite→Postgres** · L · Hoch
Idempotent, alle 13 DBs, Typkonvertierung, Sequenzen auf Max(id)+1, Zeilenzahl-Verifikation quelle==ziel, `--dry-run`.

**#895 — Test-Suite gegen Postgres** · M · Mittel
CI mit Postgres-`services:`-Container (oder Matrix), `DATABASE_URL`, Fixture-Isolation, Alembic vor Testlauf, `pytest` grün.

### P4 Cutover

**#896 — Cutover-Plan** · M · Hoch
Runbook, Backup vor Cutover, Postgres auf docker02/docker01, Migration + Verifikation, Smoke-Test, getesteter Rollback.

**#897 — Backup/Restore auf pg_dump/pg_restore** · M · Mittel
`ai_compliance_suite/backup.py` von SQLite-ZIP auf `pg_dump`/`pg_restore` umstellen, Retention beibehalten, Roundtrip-Test, Legacy-Pfade markieren/entfernen.

### P5 Betrieb

**#898 — Betrieb/Monitoring + Cleanup** · M · Niedrig
Connection-/Pool-Monitoring, finales Pool-Tuning, tote SQLite-Pfade entfernen, `CLAUDE.md`/README aktualisieren, #837 als behoben verifizieren.

---

## 6. Rollback-Plan

1. **Pro Modul (P2):** SQLite bleibt via `DATABASE_URL`-Fallback nutzbar; eine fehlerhafte Modul-PR wird isoliert revertet.
2. **Cutover (P4):** Vor dem Umschalten vollständiges Backup (SQLite-ZIP + erstes `pg_dump`). Bei Fehlschlag des Smoke-Tests `DATABASE_URL` zurück auf SQLite und Container neu starten — Daten unverändert, da Quelle erhalten bleibt.
3. **Datenmigration:** Idempotenz erlaubt Wiederholung; bei Inkonsistenz Ziel-DB droppen und neu migrieren.
4. **Schema:** Alembic `downgrade` auf vorige Revision.

---

## 7. Risiken

| Risiko | Schwere | Gegenmaßnahme |
|---|---|---|
| Auth-/Session-Logik bricht (users-DB) | Hoch | #899 zuerst, mit Tests; sicherheitskritisch |
| 555 Roh-Queries: übersehene Dialektfälle | Hoch | Systematischer Audit #893 + CI gegen Postgres #895 |
| Datenverlust bei Migration | Hoch | Zeilenzahl-Verifikation + Backups #894/#896 |
| Pool zu klein/groß für 4 Worker | Mittel | Tuning + Monitoring #891/#898 |
| Typkonvertierung (Bool/Datum/Integer) | Mittel | Explizite Typen in Alembic-Schema, Tests |
| CI-Flakiness durch DB-Service | Niedrig | Fixture-Isolation, `pg_isready`-Wait |

---

*Erstellt im Rahmen der Planungsaufgabe — keine Code-Änderungen außer dieser Doku.*
