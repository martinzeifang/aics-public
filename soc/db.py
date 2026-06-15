"""SOC-Modul — SQLite-Datenzugriff (``data/db/soc.sqlite``).

Tabellen:
- ``soc_connection``        – Wazuh-Verbindung(en), Secrets verschlüsselt (#1261).
- ``soc_sync_state``        – Polling-Cursor je Verbindung (#1262).
- ``soc_assets``            – Asset-Inventar + Compliance-Tags (#1280).
- ``soc_alerts``            – ingestierte Wazuh-Alarme, idempotent via ``alert_uid``.
- ``soc_alert_groups``      – Dedup-Gruppen (#1265).
- ``soc_suppressions``      – Tuning/False-Positive-Regeln (#1268).
- ``soc_incidents``         – Incident-Records (Status-Maschine, #1271).
- ``soc_incident_alerts``   – n:m Incident↔Alarm.
- ``soc_incident_timeline`` – append-only Audit-Timeline (sha256-Kette).
- ``soc_meldetracks``       – ausgelöste Meldepflicht-Tracks (#1281).

Muster: ``wiba/db.py`` / ``cra/db.py``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from shared import db as _sdb
from soc.constants import severity_from_level

SCHEMA = """

CREATE TABLE IF NOT EXISTS soc_connection (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name           TEXT NOT NULL DEFAULT 'default',
    modus          TEXT NOT NULL DEFAULT 'pull',          -- pull | push
    url            TEXT NOT NULL DEFAULT '',              -- Indexer-URL (pull)
    username       TEXT NOT NULL DEFAULT '',
    secret_enc     TEXT NOT NULL DEFAULT '',              -- verschlüsseltes Passwort/Token
    verify_tls     INTEGER NOT NULL DEFAULT 1,
    index_pattern  TEXT NOT NULL DEFAULT 'wazuh-alerts-*',
    min_level      INTEGER NOT NULL DEFAULT 7,
    push_token_enc TEXT NOT NULL DEFAULT '',              -- Shared-Secret für /ingest (push)
    manager_url    TEXT NOT NULL DEFAULT '',              -- Wazuh-Manager-API (Asset-Sync, #1300)
    manager_user   TEXT NOT NULL DEFAULT '',
    manager_secret_enc TEXT NOT NULL DEFAULT '',
    enabled        INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT DEFAULT (aics_now()),
    updated_at     TEXT DEFAULT (aics_now()),
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS soc_sync_state (
    connection_id  INTEGER PRIMARY KEY,
    cursor_ts      TEXT NOT NULL DEFAULT '',
    cursor_id      TEXT NOT NULL DEFAULT '',
    last_run_at    TEXT,
    last_status    TEXT NOT NULL DEFAULT '',
    last_count     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS soc_assets (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_id        TEXT NOT NULL DEFAULT '',
    agent_name      TEXT NOT NULL DEFAULT '',
    ip              TEXT NOT NULL DEFAULT '',
    hostname        TEXT NOT NULL DEFAULT '',
    organisation    TEXT NOT NULL DEFAULT '',              -- für firmen_link-Backfill
    owner           TEXT NOT NULL DEFAULT '',
    datenklasse     TEXT NOT NULL DEFAULT '',
    kritikalitaet   INTEGER NOT NULL DEFAULT 3,            -- 1 (niedrig) … 5 (kritisch) (#1307)
    umgebung        TEXT NOT NULL DEFAULT '',              -- prod | test | dev
    lifecycle       TEXT NOT NULL DEFAULT 'aktiv',         -- aktiv | ausser_betrieb
    source          TEXT NOT NULL DEFAULT 'agent',         -- agent | manuell (#1311) | syslog (#1347)
    agent_status    TEXT NOT NULL DEFAULT '',              -- active | disconnected | never_connected
    last_keepalive  TEXT NOT NULL DEFAULT '',
    os              TEXT NOT NULL DEFAULT '',
    agent_version   TEXT NOT NULL DEFAULT '',
    -- Compliance-Regime-Flags (steuern den Meldepflicht-Router #1281)
    personenbezogen INTEGER NOT NULL DEFAULT 0,
    nis2_scope      INTEGER NOT NULL DEFAULT 0,
    cra_produkt     INTEGER NOT NULL DEFAULT 0,
    ki_hochrisiko   INTEGER NOT NULL DEFAULT 0,
    dora_scope      INTEGER NOT NULL DEFAULT 0,
    -- Projekt-Verknüpfungen je Modul (Name/Meta)
    cra_projekt     TEXT NOT NULL DEFAULT '',
    aiact_projekt   TEXT NOT NULL DEFAULT '',
    nis2_projekt    TEXT NOT NULL DEFAULT '',
    rb_projekt      TEXT NOT NULL DEFAULT '',
    meta_json       TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now()),
    UNIQUE(agent_id, agent_name)
);

CREATE TABLE IF NOT EXISTS soc_alerts (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alert_uid     TEXT NOT NULL UNIQUE,                    -- Wazuh _id (idempotent)
    rule_id       TEXT NOT NULL DEFAULT '',
    rule_level    INTEGER NOT NULL DEFAULT 0,
    severity      TEXT NOT NULL DEFAULT 'low',
    kind          TEXT NOT NULL DEFAULT 'alert',           -- alert | vulnerability (#1294)
    description   TEXT NOT NULL DEFAULT '',
    groups        TEXT NOT NULL DEFAULT '[]',              -- rule.groups JSON
    mitre         TEXT NOT NULL DEFAULT '{}',              -- {id:[],technique:[],tactic:[]}
    agent_id      TEXT NOT NULL DEFAULT '',
    agent_name    TEXT NOT NULL DEFAULT '',
    srcip         TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',
    full_log      TEXT NOT NULL DEFAULT '',
    event_ts      TEXT NOT NULL DEFAULT '',                -- Wazuh timestamp
    raw_json      TEXT NOT NULL DEFAULT '{}',
    group_key     TEXT NOT NULL DEFAULT '',                -- Dedup-Gruppe
    status        TEXT NOT NULL DEFAULT 'new',
    analysis_json TEXT NOT NULL DEFAULT '{}',              -- AI-Analyse
    firmen_id     INTEGER,
    asset_id      INTEGER,                                 -- Zuordnung zum Asset (#1305)
    ingested_at   TEXT DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_soc_alerts_status ON soc_alerts(status);
CREATE INDEX IF NOT EXISTS idx_soc_alerts_group ON soc_alerts(group_key);
CREATE INDEX IF NOT EXISTS idx_soc_alerts_ts ON soc_alerts(event_ts);

CREATE TABLE IF NOT EXISTS soc_alert_groups (
    group_key     TEXT PRIMARY KEY,
    rule_id       TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    severity      TEXT NOT NULL DEFAULT 'low',
    agent_name    TEXT NOT NULL DEFAULT '',
    srcip         TEXT NOT NULL DEFAULT '',
    count         INTEGER NOT NULL DEFAULT 0,
    first_seen    TEXT NOT NULL DEFAULT '',
    last_seen     TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'new'
);

CREATE TABLE IF NOT EXISTS soc_suppressions (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_id       TEXT NOT NULL DEFAULT '',
    agent_glob    TEXT NOT NULL DEFAULT '',                -- fnmatch-Pattern auf agent_name
    srcip         TEXT NOT NULL DEFAULT '',
    reason        TEXT NOT NULL DEFAULT '',
    created_by    TEXT NOT NULL DEFAULT '',
    expires_at    TEXT,                                    -- NULL = kein Ablauf (zu vermeiden)
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS soc_incidents (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    titel           TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'new',
    severity        TEXT NOT NULL DEFAULT 'medium',
    klassifikation  TEXT NOT NULL DEFAULT '',
    confidence      TEXT NOT NULL DEFAULT '',
    asset_id        INTEGER,
    agent_name      TEXT NOT NULL DEFAULT '',
    owner           TEXT NOT NULL DEFAULT '',
    mitre           TEXT NOT NULL DEFAULT '{}',
    beschreibung    TEXT NOT NULL DEFAULT '',
    response_actions TEXT NOT NULL DEFAULT '',
    lessons_learned TEXT NOT NULL DEFAULT '',
    -- GDPR/Melde-Flags
    personal_data_involved INTEGER NOT NULL DEFAULT 0,
    awareness_at    TEXT,                                  -- startet die Meldefristen
    closed_reason   TEXT NOT NULL DEFAULT '',              -- Pflicht-Begründung beim Schließen (#1296)
    closed_at       TEXT,
    closed_by       TEXT NOT NULL DEFAULT '',
    firmen_id       INTEGER,
    meta_json       TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_soc_incidents_status ON soc_incidents(status);

CREATE TABLE IF NOT EXISTS soc_incident_alerts (
    incident_id   INTEGER NOT NULL,
    alert_uid     TEXT NOT NULL,
    PRIMARY KEY (incident_id, alert_uid)
);

CREATE TABLE IF NOT EXISTS soc_incident_timeline (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id   INTEGER NOT NULL,
    ts            TEXT DEFAULT (aics_now()),
    actor         TEXT NOT NULL DEFAULT '',
    event         TEXT NOT NULL DEFAULT '',
    detail        TEXT NOT NULL DEFAULT '',
    prev_hash     TEXT NOT NULL DEFAULT '',
    entry_hash    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_soc_timeline_incident ON soc_incident_timeline(incident_id);

CREATE TABLE IF NOT EXISTS soc_meldetracks (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id   INTEGER NOT NULL,
    regime        TEXT NOT NULL,                           -- dsgvo|nis2|cra|aiact|dora
    legal         TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'offen',           -- offen|in_arbeit|gemeldet|abgeschlossen
    deadlines_json TEXT NOT NULL DEFAULT '[]',             -- [{key,label,due_at,done}]
    target_ref    TEXT NOT NULL DEFAULT '',                -- z.B. dsgvo_datenpannen.id
    notiz         TEXT NOT NULL DEFAULT '',
    created_at    TEXT DEFAULT (aics_now()),
    updated_at    TEXT DEFAULT (aics_now()),
    UNIQUE(incident_id, regime)
);

CREATE TABLE IF NOT EXISTS soc_sla (
    severity        TEXT PRIMARY KEY,                    -- critical|high|medium|low
    ack_minutes     INTEGER NOT NULL DEFAULT 60,         -- Ziel Reaktionszeit (MTTA)
    resolve_minutes INTEGER NOT NULL DEFAULT 1440        -- Ziel Behebungszeit (MTTR)
);

CREATE TABLE IF NOT EXISTS soc_playbooks (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          TEXT NOT NULL,
    kategorie     TEXT NOT NULL DEFAULT '',
    beschreibung  TEXT NOT NULL DEFAULT '',
    steps_json    TEXT NOT NULL DEFAULT '[]',          -- [{id,text,mandatory}]
    version       INTEGER NOT NULL DEFAULT 1,
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (aics_now()),
    updated_at    TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS soc_incident_playbook (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id   INTEGER NOT NULL,
    playbook_id   INTEGER,
    name          TEXT NOT NULL DEFAULT '',
    steps_json    TEXT NOT NULL DEFAULT '[]',          -- [{id,text,mandatory,done,done_at,done_by}]
    assigned_at   TEXT DEFAULT (aics_now()),
    assigned_by   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_soc_inc_playbook ON soc_incident_playbook(incident_id);

CREATE TABLE IF NOT EXISTS soc_pir (
    incident_id     INTEGER PRIMARY KEY,                 -- 1 PIR je Incident
    root_cause      TEXT NOT NULL DEFAULT '',            -- Ursachenanalyse (NIST/ISO 27035)
    what_went_well  TEXT NOT NULL DEFAULT '',
    what_went_wrong TEXT NOT NULL DEFAULT '',
    lessons         TEXT NOT NULL DEFAULT '',            -- Lessons Learnt
    created_by      TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS soc_pir_actions (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id   INTEGER NOT NULL,                      -- verfolgt über Incident-Abschluss hinaus
    beschreibung  TEXT NOT NULL DEFAULT '',
    owner         TEXT NOT NULL DEFAULT '',
    frist         TEXT NOT NULL DEFAULT '',              -- ISO-Datum (YYYY-MM-DD)
    status        TEXT NOT NULL DEFAULT 'offen',          -- offen | in_arbeit | erledigt
    created_by    TEXT NOT NULL DEFAULT '',
    created_at    TEXT DEFAULT (aics_now()),
    done_at       TEXT,
    done_by       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_soc_pir_actions_status ON soc_pir_actions(status);
CREATE INDEX IF NOT EXISTS idx_soc_pir_actions_inc ON soc_pir_actions(incident_id);

CREATE TABLE IF NOT EXISTS soc_evidence (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id     INTEGER NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'file',      -- file | log_snapshot
    filename        TEXT NOT NULL DEFAULT '',
    stored_name     TEXT NOT NULL DEFAULT '',
    content_type    TEXT NOT NULL DEFAULT '',
    size            INTEGER NOT NULL DEFAULT 0,
    sha256          TEXT NOT NULL DEFAULT '',           -- Integritätssicherung (ISO 27037)
    retention_until TEXT NOT NULL DEFAULT '',           -- Aufbewahrungsfrist (ISO-Datum)
    beschreibung    TEXT NOT NULL DEFAULT '',
    created_by      TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (aics_now()),
    deleted_at      TEXT,                               -- Soft-Delete (CoC bleibt erhalten)
    deleted_by      TEXT NOT NULL DEFAULT '',
    delete_reason   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_soc_evidence_inc ON soc_evidence(incident_id);

CREATE TABLE IF NOT EXISTS soc_custody (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,                  -- Chain of Custody, append-only
    evidence_id   INTEGER NOT NULL,
    action        TEXT NOT NULL,                        -- added|viewed|exported|deleted|frozen
    actor         TEXT NOT NULL DEFAULT '',
    note          TEXT NOT NULL DEFAULT '',
    ts            TEXT DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_soc_custody_ev ON soc_custody(evidence_id);

CREATE TABLE IF NOT EXISTS soc_handover (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,                  -- Schichtübergabe (#1318)
    schicht       TEXT NOT NULL DEFAULT '',             -- Früh | Spät | Nacht | frei
    datum         TEXT NOT NULL DEFAULT '',             -- ISO-Datum
    von_user      TEXT NOT NULL DEFAULT '',
    an_user       TEXT NOT NULL DEFAULT '',
    offene_punkte TEXT NOT NULL DEFAULT '',
    notizen       TEXT NOT NULL DEFAULT '',
    created_by    TEXT NOT NULL DEFAULT '',
    created_at    TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS soc_escalation (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,                  -- Eskalationsmatrix
    severity      TEXT NOT NULL DEFAULT 'high',         -- critical|high|medium|low
    stufe         INTEGER NOT NULL DEFAULT 1,           -- 1,2,3 …
    rolle         TEXT NOT NULL DEFAULT '',
    person        TEXT NOT NULL DEFAULT '',
    kontakt       TEXT NOT NULL DEFAULT '',
    frist_minuten INTEGER NOT NULL DEFAULT 30,
    created_at    TEXT DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_soc_escalation_sev ON soc_escalation(severity, stufe);

CREATE TABLE IF NOT EXISTS soc_raci (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,                  -- RACI je Vorfallstyp
    vorfallstyp   TEXT NOT NULL DEFAULT '',
    rolle         TEXT NOT NULL DEFAULT '',
    raci          TEXT NOT NULL DEFAULT 'R',            -- R|A|C|I
    created_at    TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS soc_iocs (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,                   -- Threat-Intelligence IOCs (#1322)
    typ          TEXT NOT NULL DEFAULT 'ip',            -- ip|domain|hash|url
    wert         TEXT NOT NULL DEFAULT '',
    quelle       TEXT NOT NULL DEFAULT '',
    confidence   INTEGER NOT NULL DEFAULT 50,           -- 0..100
    beschreibung TEXT NOT NULL DEFAULT '',
    gueltig_bis  TEXT NOT NULL DEFAULT '',               -- ISO-Datum, leer = unbegrenzt
    enabled      INTEGER NOT NULL DEFAULT 1,
    created_by   TEXT NOT NULL DEFAULT '',
    created_at   TEXT DEFAULT (aics_now()),
    UNIQUE(typ, wert)
);
CREATE INDEX IF NOT EXISTS idx_soc_iocs_wert ON soc_iocs(wert);

CREATE TABLE IF NOT EXISTS soc_detection_usecases (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,                  -- Detection-Use-Case-Register (#1321)
    name          TEXT NOT NULL DEFAULT '',
    bedrohung     TEXT NOT NULL DEFAULT '',
    attack_techniques TEXT NOT NULL DEFAULT '[]',       -- JSON-Liste ATT&CK-Technik-IDs
    wazuh_rules   TEXT NOT NULL DEFAULT '',             -- Regel-IDs/Gruppen (frei)
    status        TEXT NOT NULL DEFAULT 'geplant',      -- aktiv|tuning|geplant|ausser_betrieb
    datenquelle   TEXT NOT NULL DEFAULT '',
    notizen       TEXT NOT NULL DEFAULT '',
    created_at    TEXT DEFAULT (aics_now()),
    updated_at    TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS soc_assessments (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,               -- SOC-Reifegrad-Self-Assessment (#1326)
    datum            TEXT NOT NULL DEFAULT '',
    durchgefuehrt_von TEXT NOT NULL DEFAULT '',
    notizen          TEXT NOT NULL DEFAULT '',
    gesamt_reifegrad REAL NOT NULL DEFAULT 0,
    created_at       TEXT DEFAULT (aics_now())
);
CREATE TABLE IF NOT EXISTS soc_assessment_scores (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assessment_id INTEGER NOT NULL,
    aspekt_key    TEXT NOT NULL,
    reifegrad     INTEGER NOT NULL DEFAULT 0,            -- 0..5
    bemerkung     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_soc_assess_scores ON soc_assessment_scores(assessment_id);

CREATE TABLE IF NOT EXISTS soc_log_sources (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,                  -- Log-Source-Register (#1324)
    name          TEXT NOT NULL DEFAULT '',             -- Quelle/Agent-Name
    typ           TEXT NOT NULL DEFAULT '',             -- agent|syslog|firewall|cloud|…
    erwartet      INTEGER NOT NULL DEFAULT 1,           -- erwartet einzugehen?
    notizen       TEXT NOT NULL DEFAULT '',
    created_at    TEXT DEFAULT (aics_now()),
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS soc_hunts (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,                  -- Threat-Hunting (#1323)
    hypothese     TEXT NOT NULL DEFAULT '',
    attack_bezug  TEXT NOT NULL DEFAULT '',             -- ATT&CK-Technik-IDs (frei)
    datum         TEXT NOT NULL DEFAULT '',
    jaeger        TEXT NOT NULL DEFAULT '',
    query         TEXT NOT NULL DEFAULT '',             -- ausgeführte Indexer-Query
    findings      TEXT NOT NULL DEFAULT '',
    ergebnis      TEXT NOT NULL DEFAULT 'offen',         -- bestaetigt|verworfen|offen
    status        TEXT NOT NULL DEFAULT 'laufend',       -- laufend|abgeschlossen
    created_by    TEXT NOT NULL DEFAULT '',
    created_at    TEXT DEFAULT (aics_now()),
    updated_at    TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS soc_uebungen (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,                  -- SOC-Übungen/Tests (#1319)
    typ           TEXT NOT NULL DEFAULT 'tabletop',     -- tabletop | detection_test
    titel         TEXT NOT NULL DEFAULT '',
    szenario      TEXT NOT NULL DEFAULT '',
    datum         TEXT NOT NULL DEFAULT '',
    teilnehmer    TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'geplant',      -- geplant | durchgefuehrt | ausgewertet
    erwartete_erkennung     TEXT NOT NULL DEFAULT '',   -- Detection-Test: Soll
    tatsaechliche_erkennung TEXT NOT NULL DEFAULT '',   -- Detection-Test: Ist
    test_alert_uid TEXT NOT NULL DEFAULT '',            -- optionaler Bezug zum Testalarm
    ergebnis      TEXT NOT NULL DEFAULT 'offen',        -- bestanden|teilweise|nicht_bestanden|offen
    auswertung    TEXT NOT NULL DEFAULT '',
    massnahmen    TEXT NOT NULL DEFAULT '',             -- abgeleitete Maßnahmen
    created_by    TEXT NOT NULL DEFAULT '',
    -- ISO-22398-Lebenszyklus + Rollen + AAR (#1351, additiv via _addcol für Bestand)
    lifecycle     TEXT NOT NULL DEFAULT 'design',        -- design|develop|conduct|evaluate|improve
    uebungsleitung TEXT NOT NULL DEFAULT '',             -- Exercise Director
    moderator     TEXT NOT NULL DEFAULT '',              -- Facilitator
    evaluator     TEXT NOT NULL DEFAULT '',              -- Evaluator
    explan        TEXT NOT NULL DEFAULT '',              -- Exercise Plan / Szenario-Rahmen
    aar_staerken  TEXT NOT NULL DEFAULT '',              -- AAR: Stärken
    aar_verbesserung TEXT NOT NULL DEFAULT '',           -- AAR: Verbesserungsbereiche
    aar_lessons   TEXT NOT NULL DEFAULT '',              -- AAR: Lessons Learned (ISO 27035)
    aar_empfehlungen TEXT NOT NULL DEFAULT '',           -- AAR: Empfehlungen
    aar_signoff_by  TEXT NOT NULL DEFAULT '',            -- AAR-Freigabe (optional)
    aar_signoff_at  TEXT,
    created_at    TEXT DEFAULT (aics_now()),
    updated_at    TEXT DEFAULT (aics_now())
);

-- ── ISO-22398-Übungsdetails (#1351) ─────────────────────────────────────────
-- Übungsziele mit Typ (orientation/learning/cooperation/experimenting/testing),
-- Bewertungskriterien je Ziel und Soll/Ist-Bewertung (Performance-Objectives).
CREATE TABLE IF NOT EXISTS soc_uebung_ziele (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uebung_id     INTEGER NOT NULL,
    ziel          TEXT NOT NULL DEFAULT '',
    typ           TEXT NOT NULL DEFAULT 'testing',       -- orientation|learning|cooperation|experimenting|testing
    kriterien     TEXT NOT NULL DEFAULT '',              -- Bewertungskriterien
    soll          TEXT NOT NULL DEFAULT '',              -- Soll-Bewertung
    ist           TEXT NOT NULL DEFAULT '',              -- Ist-Bewertung (im AAR)
    bewertung     TEXT NOT NULL DEFAULT 'offen',         -- erfuellt|teilweise|nicht_erfuellt|offen
    sortierung    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT DEFAULT (aics_now()),
    updated_at    TEXT DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_soc_ueb_ziele ON soc_uebung_ziele(uebung_id);

-- Getaktete Injects = Master Scenario Events List (MSEL) zum EXPLAN.
CREATE TABLE IF NOT EXISTS soc_uebung_injects (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uebung_id     INTEGER NOT NULL,
    zeit          TEXT NOT NULL DEFAULT '',              -- Takt (z.B. 'T+15' oder Uhrzeit)
    beschreibung  TEXT NOT NULL DEFAULT '',              -- Inject/Ereignis
    erwartete_reaktion TEXT NOT NULL DEFAULT '',         -- erwartete Reaktion der Teilnehmer
    tatsaechliche_reaktion TEXT NOT NULL DEFAULT '',     -- beobachtete Reaktion (im Conduct/Evaluate)
    status        TEXT NOT NULL DEFAULT 'geplant',       -- geplant|injiziert|bewaeltigt|verpasst
    sortierung    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT DEFAULT (aics_now()),
    updated_at    TEXT DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_soc_ueb_injects ON soc_uebung_injects(uebung_id);

-- Improvement Plan / Korrekturmaßnahmen je Übung (Owner/Frist/Status, verfolgt
-- bis Erledigung) — analog soc_pir_actions (#1316), aber eigenständig, da nicht
-- an einen Incident gebunden.
CREATE TABLE IF NOT EXISTS soc_uebung_massnahmen (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uebung_id     INTEGER NOT NULL,
    beschreibung  TEXT NOT NULL DEFAULT '',
    owner         TEXT NOT NULL DEFAULT '',
    frist         TEXT NOT NULL DEFAULT '',              -- ISO-Datum (YYYY-MM-DD)
    status        TEXT NOT NULL DEFAULT 'offen',         -- offen|in_arbeit|erledigt
    created_by    TEXT NOT NULL DEFAULT '',
    created_at    TEXT DEFAULT (aics_now()),
    done_at       TEXT,
    done_by       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_soc_ueb_mass_uebung ON soc_uebung_massnahmen(uebung_id);
CREATE INDEX IF NOT EXISTS idx_soc_ueb_mass_status ON soc_uebung_massnahmen(status);

-- ── Schwachstellen-Register (#1343) ─────────────────────────────────────────
-- Asset-zentrisch, gespeist aus dem Wazuh-States-Index (Ist-Zustand der
-- Vulnerability-Detection). Eigenes, leichtes Triage-/Promotion-Modell — NICHT
-- mit soc_alerts/cra_vuln vermischt. Upsert idempotent (Triage erhalten, Schwere
-- nur anheben). Reconcile setzt verschwundene CVEs auf 'Solved' (kein Hard-Delete).
CREATE TABLE IF NOT EXISTS soc_vulnerabilities (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vuln_uid            TEXT NOT NULL UNIQUE,             -- hash(agent_id|cve_id|package_name)
    cve_id              TEXT NOT NULL DEFAULT '',
    severity            TEXT NOT NULL DEFAULT 'low',      -- critical|high|medium|low
    cvss_score          REAL NOT NULL DEFAULT 0,
    cvss_version        TEXT NOT NULL DEFAULT '',
    cvss_vector         TEXT NOT NULL DEFAULT '',
    package_name        TEXT NOT NULL DEFAULT '',
    package_version     TEXT NOT NULL DEFAULT '',
    fixed_version       TEXT NOT NULL DEFAULT '',
    condition           TEXT NOT NULL DEFAULT '',
    wazuh_status        TEXT NOT NULL DEFAULT 'Active',   -- Active | Solved
    detection_time      TEXT NOT NULL DEFAULT '',
    published_at        TEXT NOT NULL DEFAULT '',
    advisory_url        TEXT NOT NULL DEFAULT '',
    external_refs       TEXT NOT NULL DEFAULT '[]',       -- JSON-Liste Referenz-URLs
    agent_id            TEXT NOT NULL DEFAULT '',
    agent_name          TEXT NOT NULL DEFAULT '',
    asset_id            INTEGER,                          -- Auto-Link via find_asset_for_agent
    firmen_id           INTEGER,
    triage_status       TEXT NOT NULL DEFAULT 'new',      -- new|acknowledged|risk_accepted|false_positive|promoted
    triage_kommentar    TEXT NOT NULL DEFAULT '',
    promoted_alert_uid  TEXT NOT NULL DEFAULT '',         -- falls als Alarm aufgenommen
    promoted_incident_id INTEGER,                         -- falls als Incident aufgenommen
    source              TEXT NOT NULL DEFAULT 'wazuh-states',
    first_seen          TEXT DEFAULT (aics_now()),
    last_seen           TEXT DEFAULT (aics_now()),
    last_synced_at      TEXT DEFAULT (aics_now()),
    raw_json            TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT DEFAULT (aics_now()),
    updated_at          TEXT DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_soc_vuln_status ON soc_vulnerabilities(wazuh_status);
CREATE INDEX IF NOT EXISTS idx_soc_vuln_triage ON soc_vulnerabilities(triage_status);
CREATE INDEX IF NOT EXISTS idx_soc_vuln_asset ON soc_vulnerabilities(asset_id);
CREATE INDEX IF NOT EXISTS idx_soc_vuln_cve ON soc_vulnerabilities(cve_id);

-- ── Regelwerk-Cache (#1348) ─────────────────────────────────────────────────
-- Read-only Spiegel des installierten Wazuh-Regelwerks (Manager-API GET /rules).
-- Reiner Such-/Filter-Cache (durchsuchbar ohne Live-Roundtrip). Pro „Regelwerk
-- laden" wird der Bestand atomar ersetzt (replace_rules), damit gelöschte/
-- deaktivierte Regeln verschwinden.
CREATE TABLE IF NOT EXISTS soc_rules (
    rule_id      INTEGER PRIMARY KEY,                    -- Wazuh-Regel-ID
    level        INTEGER NOT NULL DEFAULT 0,
    description  TEXT NOT NULL DEFAULT '',
    groups       TEXT NOT NULL DEFAULT '[]',             -- JSON-Liste rule.groups
    mitre        TEXT NOT NULL DEFAULT '[]',             -- JSON-Liste ATT&CK-Technik-IDs
    filename     TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT '',               -- enabled | disabled
    synced_at    TEXT DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_soc_rules_level ON soc_rules(level);
CREATE INDEX IF NOT EXISTS idx_soc_rules_filename ON soc_rules(filename);

-- Sync-Zeitstempel/Status des Regelwerk-Caches (Singleton-Zeile, #1348)
CREATE TABLE IF NOT EXISTS soc_rules_sync (
    id           INTEGER PRIMARY KEY DEFAULT 1,
    last_run_at  TEXT,
    last_status  TEXT NOT NULL DEFAULT '',
    last_count   INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT NOT NULL DEFAULT ''
);
"""


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_db(db_path: Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        # Migrationen für Bestands-DBs (Postgres: ADD COLUMN IF NOT EXISTS)
        def _addcol(table, col, ddl):
            con.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {ddl}")
        _addcol("soc_alerts", "kind", "kind TEXT NOT NULL DEFAULT 'alert'")            # #1294
        _addcol("soc_incidents", "closed_reason", "closed_reason TEXT NOT NULL DEFAULT ''")  # #1296
        _addcol("soc_incidents", "closed_at", "closed_at TEXT")
        _addcol("soc_incidents", "closed_by", "closed_by TEXT NOT NULL DEFAULT ''")
        _addcol("soc_connection", "manager_url", "manager_url TEXT NOT NULL DEFAULT ''")      # #1300
        _addcol("soc_connection", "manager_user", "manager_user TEXT NOT NULL DEFAULT ''")
        _addcol("soc_connection", "manager_secret_enc", "manager_secret_enc TEXT NOT NULL DEFAULT ''")
        # Schwachstellen-Sync-Konfiguration (#1343)
        _addcol("soc_connection", "vuln_index_pattern",
                "vuln_index_pattern TEXT NOT NULL DEFAULT 'wazuh-states-vulnerabilities-*'")
        _addcol("soc_connection", "vuln_sync_enabled", "vuln_sync_enabled INTEGER NOT NULL DEFAULT 1")
        _addcol("soc_connection", "vuln_min_severity", "vuln_min_severity TEXT NOT NULL DEFAULT 'medium'")
        _addcol("soc_alerts", "asset_id", "asset_id INTEGER")                                 # #1305
        _addcol("soc_incidents", "acknowledged_at", "acknowledged_at TEXT")                   # #1315
        _addcol("soc_incidents", "resolved_at", "resolved_at TEXT")
        _addcol("soc_alerts", "ioc_hits", "ioc_hits TEXT NOT NULL DEFAULT '[]'")              # #1322
        _addcol("soc_alerts", "triaged_at", "triaged_at TEXT")                                # #1350 (Zeit bis Triage)
        for col, ddl in (                                                                    # #1351 ISO-22398
            ("lifecycle", "lifecycle TEXT NOT NULL DEFAULT 'design'"),
            ("uebungsleitung", "uebungsleitung TEXT NOT NULL DEFAULT ''"),
            ("moderator", "moderator TEXT NOT NULL DEFAULT ''"),
            ("evaluator", "evaluator TEXT NOT NULL DEFAULT ''"),
            ("explan", "explan TEXT NOT NULL DEFAULT ''"),
            ("aar_staerken", "aar_staerken TEXT NOT NULL DEFAULT ''"),
            ("aar_verbesserung", "aar_verbesserung TEXT NOT NULL DEFAULT ''"),
            ("aar_lessons", "aar_lessons TEXT NOT NULL DEFAULT ''"),
            ("aar_empfehlungen", "aar_empfehlungen TEXT NOT NULL DEFAULT ''"),
            ("aar_signoff_by", "aar_signoff_by TEXT NOT NULL DEFAULT ''"),
            ("aar_signoff_at", "aar_signoff_at TEXT"),
        ):
            _addcol("soc_uebungen", col, ddl)
        for col, ddl in (                                                                    # #1307/#1309/#1311
            ("kritikalitaet", "kritikalitaet INTEGER NOT NULL DEFAULT 3"),
            ("umgebung", "umgebung TEXT NOT NULL DEFAULT ''"),
            ("lifecycle", "lifecycle TEXT NOT NULL DEFAULT 'aktiv'"),
            ("source", "source TEXT NOT NULL DEFAULT 'agent'"),
            ("agent_status", "agent_status TEXT NOT NULL DEFAULT ''"),
            ("last_keepalive", "last_keepalive TEXT NOT NULL DEFAULT ''"),
            ("os", "os TEXT NOT NULL DEFAULT ''"),
            ("agent_version", "agent_version TEXT NOT NULL DEFAULT ''"),
        ):
            _addcol("soc_assets", col, ddl)
        con.commit()
        from shared.firmen_link import ensure_firmen_id_column
        ensure_firmen_id_column(con, "soc_assets")
    finally:
        con.close()


def _row(r: Any | None) -> dict[str, Any] | None:
    return dict(r) if r is not None else None


# ── Verbindung (#1261) ──────────────────────────────────────────────────────

def save_connection(db_path: Path, *, name: str = "default", modus: str | None = None,
                    url: str | None = None, username: str | None = None, secret: str | None = None,
                    verify_tls: bool | None = None, index_pattern: str | None = None,
                    min_level: int | None = None, push_token: str | None = None,
                    manager_url: str | None = None, manager_user: str | None = None,
                    manager_secret: str | None = None, enabled: bool | None = None,
                    vuln_index_pattern: str | None = None, vuln_sync_enabled: bool | None = None,
                    vuln_min_severity: str | None = None) -> int:
    """Speichert/aktualisiert eine Verbindung; Secrets verschlüsselt at-rest.

    **Partielles Update (#1315-Hotfix):** Nicht übergebene Felder (``None``) behalten
    den bestehenden Wert. So überschreibt das Speichern des Manager-API-Formulars NICHT
    die Indexer-URL/-Benutzer (und umgekehrt) — beide Formulare teilen sich eine Zeile.
    """
    from shared.crypto_at_rest import encrypt_field
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        existing = con.execute("SELECT * FROM soc_connection WHERE name=?", (name,)).fetchone()

        def _keep(val: Any, col: str, default: Any) -> Any:
            if val is not None:
                return val
            return existing[col] if existing else default

        secret_enc = existing["secret_enc"] if existing else ""
        if secret is not None and secret != "":
            secret_enc = encrypt_field(secret)
        token_enc = existing["push_token_enc"] if existing else ""
        if push_token is not None and push_token != "":
            token_enc = encrypt_field(push_token)
        mgr_secret_enc = existing["manager_secret_enc"] if existing else ""
        if manager_secret is not None and manager_secret != "":
            mgr_secret_enc = encrypt_field(manager_secret)
        modus_v = _keep(modus, "modus", "pull")
        url_v = _keep(url, "url", "")
        user_v = _keep(username, "username", "")
        idx_v = _keep(index_pattern, "index_pattern", "wazuh-alerts-*")
        lvl_v = int(_keep(min_level, "min_level", 7))
        tls_v = 1 if _keep(verify_tls, "verify_tls", True) else 0
        en_v = 1 if _keep(enabled, "enabled", True) else 0
        mgr_url = _keep(manager_url, "manager_url", "")
        mgr_user = _keep(manager_user, "manager_user", "")
        vidx_v = _keep(vuln_index_pattern, "vuln_index_pattern", "wazuh-states-vulnerabilities-*")
        vsync_v = 1 if _keep(vuln_sync_enabled, "vuln_sync_enabled", True) else 0
        vsev_v = _keep(vuln_min_severity, "vuln_min_severity", "medium")
        if existing:
            con.execute(
                """UPDATE soc_connection SET modus=?, url=?, username=?, secret_enc=?,
                   verify_tls=?, index_pattern=?, min_level=?, push_token_enc=?,
                   manager_url=?, manager_user=?, manager_secret_enc=?, enabled=?,
                   vuln_index_pattern=?, vuln_sync_enabled=?, vuln_min_severity=?,
                   updated_at=aics_now() WHERE name=?""",
                (modus_v, url_v, user_v, secret_enc, tls_v, idx_v,
                 lvl_v, token_enc, mgr_url, mgr_user, mgr_secret_enc,
                 en_v, vidx_v, vsync_v, vsev_v, name))
            cid = existing["id"]
        else:
            cur = con.execute(
                """INSERT INTO soc_connection(name, modus, url, username, secret_enc,
                   verify_tls, index_pattern, min_level, push_token_enc,
                   manager_url, manager_user, manager_secret_enc, enabled,
                   vuln_index_pattern, vuln_sync_enabled, vuln_min_severity)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                (name, modus_v, url_v, user_v, secret_enc, tls_v,
                 idx_v, lvl_v, token_enc, mgr_url, mgr_user,
                 mgr_secret_enc, en_v, vidx_v, vsync_v, vsev_v))
            cid = int(cur.lastrowid)
        con.commit()
        return cid
    finally:
        con.close()


def list_connections(db_path: Path, *, with_secrets: bool = False) -> list[dict[str, Any]]:
    """Verbindungen ohne Klartext-Secrets (nur `has_secret`-Flags), außer with_secrets."""
    from shared.crypto_at_rest import decrypt_field
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = [dict(r) for r in con.execute("SELECT * FROM soc_connection ORDER BY id").fetchall()]
    finally:
        con.close()
    out = []
    for r in rows:
        item = dict(r)
        item["has_secret"] = bool(r.get("secret_enc"))
        item["has_push_token"] = bool(r.get("push_token_enc"))
        item["has_manager_secret"] = bool(r.get("manager_secret_enc"))
        if with_secrets:
            item["secret"] = decrypt_field(r["secret_enc"]) if r.get("secret_enc") else ""
            item["push_token"] = decrypt_field(r["push_token_enc"]) if r.get("push_token_enc") else ""
            item["manager_secret"] = decrypt_field(r["manager_secret_enc"]) if r.get("manager_secret_enc") else ""
        for k in ("secret_enc", "push_token_enc", "manager_secret_enc"):
            item.pop(k, None)
        item["verify_tls"] = bool(r.get("verify_tls"))
        item["enabled"] = bool(r.get("enabled"))
        if "vuln_sync_enabled" in item:
            item["vuln_sync_enabled"] = bool(r.get("vuln_sync_enabled"))
        out.append(item)
    return out


def load_connection(db_path: Path, name: str = "default", *, with_secret: bool = True) -> dict[str, Any] | None:
    cons = [c for c in list_connections(db_path, with_secrets=with_secret) if c["name"] == name]
    return cons[0] if cons else None


def delete_connection(db_path: Path, name: str) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute("SELECT id FROM soc_connection WHERE name=?", (name,)).fetchone()
        if row:
            con.execute("DELETE FROM soc_sync_state WHERE connection_id=?", (row["id"],))
        con.execute("DELETE FROM soc_connection WHERE name=?", (name,))
        con.commit()
    finally:
        con.close()


# ── Sync-Cursor (#1262) ─────────────────────────────────────────────────────

def get_cursor(db_path: Path, connection_id: int) -> dict[str, Any]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_sync_state WHERE connection_id=?", (connection_id,)).fetchone()
        return _row(r) or {"connection_id": connection_id, "cursor_ts": "", "cursor_id": ""}
    finally:
        con.close()


def set_cursor(db_path: Path, connection_id: int, *, cursor_ts: str, cursor_id: str,
               status: str = "ok", count: int = 0) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO soc_sync_state(connection_id, cursor_ts, cursor_id, last_run_at, last_status, last_count)
               VALUES(?,?,?,aics_now(),?,?)
               ON CONFLICT(connection_id) DO UPDATE SET cursor_ts=excluded.cursor_ts,
                 cursor_id=excluded.cursor_id, last_run_at=excluded.last_run_at,
                 last_status=excluded.last_status, last_count=excluded.last_count""",
            (connection_id, cursor_ts, cursor_id, status, int(count)))
        con.commit()
    finally:
        con.close()


# ── Alarme + Dedup-Gruppen ──────────────────────────────────────────────────

def upsert_alert(db_path: Path, alert: dict[str, Any]) -> bool:
    """Idempotentes Ingest eines normalisierten Alarms. Returns True wenn neu."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        exists = con.execute("SELECT 1 FROM soc_alerts WHERE alert_uid=?", (alert["alert_uid"],)).fetchone()
        if exists:
            return False
        con.execute(
            """INSERT INTO soc_alerts(alert_uid, rule_id, rule_level, severity, kind, description,
               groups, mitre, agent_id, agent_name, srcip, location, full_log, event_ts,
               raw_json, group_key, status, firmen_id, asset_id, ioc_hits)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (alert["alert_uid"], alert.get("rule_id", ""), int(alert.get("rule_level", 0)),
             alert.get("severity") or severity_from_level(alert.get("rule_level")),
             alert.get("kind", "alert"),
             alert.get("description", ""), json.dumps(alert.get("groups", [])),
             json.dumps(alert.get("mitre", {})), alert.get("agent_id", ""),
             alert.get("agent_name", ""), alert.get("srcip", ""), alert.get("location", ""),
             alert.get("full_log", ""), alert.get("event_ts", ""),
             json.dumps(alert.get("raw_json", {})), alert.get("group_key", ""),
             alert.get("status", "new"), alert.get("firmen_id"), alert.get("asset_id"),
             json.dumps(alert.get("ioc_hits", []))))
        # Gruppe aktualisieren
        gk = alert.get("group_key", "")
        if gk:
            con.execute(
                """INSERT INTO soc_alert_groups(group_key, rule_id, description, severity,
                   agent_name, srcip, count, first_seen, last_seen, status)
                   VALUES(?,?,?,?,?,?,1,?,?,'new')
                   ON CONFLICT(group_key) DO UPDATE SET count=soc_alert_groups.count+1,
                     last_seen=excluded.last_seen,
                     severity=CASE WHEN excluded.severity=soc_alert_groups.severity
                              THEN soc_alert_groups.severity ELSE excluded.severity END""",
                (gk, alert.get("rule_id", ""), alert.get("description", ""),
                 alert.get("severity", "low"), alert.get("agent_name", ""),
                 alert.get("srcip", ""), alert.get("event_ts", ""), alert.get("event_ts", "")))
        con.commit()
        return True
    finally:
        con.close()


def list_alerts(db_path: Path, *, status: str | None = None, severity: str | None = None,
                min_level: int | None = None, agent: str | None = None, kind: str | None = None,
                asset_id: int | None = None,
                group_key: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = "SELECT * FROM soc_alerts WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status=?"; params.append(status)
        if severity:
            q += " AND severity=?"; params.append(severity)
        if kind:
            q += " AND kind=?"; params.append(kind)
        if asset_id is not None:
            q += " AND asset_id=?"; params.append(int(asset_id))
        if min_level is not None:
            q += " AND rule_level>=?"; params.append(int(min_level))
        if agent:
            q += " AND agent_name=?"; params.append(agent)
        if group_key:
            q += " AND group_key=?"; params.append(group_key)
        q += " ORDER BY event_ts DESC, id DESC LIMIT ?"
        params.append(int(limit))
        return [_alert_to_dict(r) for r in con.execute(q, params).fetchall()]
    finally:
        con.close()


def get_alert(db_path: Path, alert_uid: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_alerts WHERE alert_uid=?", (alert_uid,)).fetchone()
        return _alert_to_dict(r) if r else None
    finally:
        con.close()


def set_alert_status(db_path: Path, alert_uid: str, status: str) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        # #1350: erster Wechsel weg von 'new' = Triage-Zeitpunkt (für „Zeit bis Triage").
        con.execute(
            "UPDATE soc_alerts SET status=?, "
            "triaged_at=CASE WHEN ? != 'new' AND triaged_at IS NULL THEN aics_now() ELSE triaged_at END "
            "WHERE alert_uid=?", (status, status, alert_uid))
        con.commit()
    finally:
        con.close()


def store_analysis(db_path: Path, alert_uid: str, analysis: dict) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("UPDATE soc_alerts SET analysis_json=? WHERE alert_uid=?",
                    (json.dumps(analysis), alert_uid))
        con.commit()
    finally:
        con.close()


def list_groups(db_path: Path, *, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = "SELECT * FROM soc_alert_groups WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status=?"; params.append(status)
        q += " ORDER BY last_seen DESC LIMIT ?"; params.append(int(limit))
        return [dict(r) for r in con.execute(q, params).fetchall()]
    finally:
        con.close()


def _alert_to_dict(r: Any) -> dict[str, Any]:
    d = dict(r)
    for k in ("groups", "mitre", "raw_json", "analysis_json"):
        try:
            d[k] = json.loads(d.get(k) or ("[]" if k == "groups" else "{}"))
        except Exception:
            d[k] = [] if k == "groups" else {}
    try:  # #1322 IOC-Treffer
        d["ioc_hits"] = json.loads(d.get("ioc_hits") or "[]")
    except Exception:
        d["ioc_hits"] = []
    return d


# ── Suppressions (#1268) ────────────────────────────────────────────────────

def list_suppressions(db_path: Path, *, only_enabled: bool = False) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = "SELECT * FROM soc_suppressions"
        if only_enabled:
            q += " WHERE enabled=1 AND (expires_at IS NULL OR expires_at > aics_now())"
        q += " ORDER BY id DESC"
        return [dict(r) for r in con.execute(q).fetchall()]
    finally:
        con.close()


def add_suppression(db_path: Path, *, rule_id: str = "", agent_glob: str = "", srcip: str = "",
                    reason: str = "", created_by: str = "", expires_at: str | None = None) -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO soc_suppressions(rule_id, agent_glob, srcip, reason, created_by, expires_at)
               VALUES(?,?,?,?,?,?) RETURNING id""",
            (rule_id, agent_glob, srcip, reason, created_by, expires_at))
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def delete_suppression(db_path: Path, sid: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_suppressions WHERE id=?", (sid,))
        con.commit()
    finally:
        con.close()


# ── Assets (#1280) ──────────────────────────────────────────────────────────

_ASSET_FIELDS = ("ip", "hostname", "organisation", "owner", "datenklasse",
                 "cra_projekt", "aiact_projekt", "nis2_projekt", "rb_projekt",
                 "kritikalitaet", "umgebung", "lifecycle", "source",
                 "agent_status", "last_keepalive", "os", "agent_version")
_ASSET_FLAGS = ("personenbezogen", "nis2_scope", "cra_produkt", "ki_hochrisiko", "dora_scope")


def upsert_asset(db_path: Path, asset: dict[str, Any]) -> int:
    """Partieller Upsert: aktualisiert NUR die im ``asset`` vorhandenen Felder.

    Wichtig: Ein Agent-Re-Import (nur Agent-Felder) überschreibt damit NICHT die
    manuell gepflegte Kritikalität/Tags/Owner. Existenz-Match per ``id`` (Edit) oder
    ``agent_name``/``agent_id`` (Import).
    """
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if asset.get("id"):
            row = con.execute("SELECT id FROM soc_assets WHERE id=?", (int(asset["id"]),)).fetchone()
        elif asset.get("agent_name"):
            # agent_name ist der stabile Schlüssel (Asset evtl. zuerst ohne agent_id angelegt)
            row = con.execute("SELECT id FROM soc_assets WHERE agent_name=?",
                              (asset.get("agent_name"),)).fetchone()
        elif asset.get("agent_id"):
            row = con.execute("SELECT id FROM soc_assets WHERE agent_id=?",
                              (asset.get("agent_id"),)).fetchone()
        else:
            row = None
        present: dict[str, Any] = {}
        # agent_id beim Re-Import nachtragen, wenn noch leer
        if asset.get("agent_id"):
            present["agent_id"] = asset["agent_id"]
        for f in _ASSET_FIELDS:
            if f in asset:
                present[f] = int(asset[f]) if f == "kritikalitaet" else asset[f]
        for f in _ASSET_FLAGS:
            if f in asset:
                present[f] = int(bool(asset[f]))
        if "meta" in asset:
            present["meta_json"] = json.dumps(asset["meta"])
        if row:
            if present:
                sets = ", ".join(f"{k}=?" for k in present)
                con.execute(f"UPDATE soc_assets SET {sets}, updated_at=aics_now() WHERE id=?",
                            (*present.values(), row["id"]))
            aid = row["id"]
        else:
            cols = dict(present)  # present kann agent_id bereits enthalten → setdefault statt doppeltem kwarg
            cols.setdefault("agent_id", asset.get("agent_id", ""))
            cols.setdefault("agent_name", asset.get("agent_name", ""))
            ph = ",".join("?" * len(cols))
            cur = con.execute(f"INSERT INTO soc_assets({','.join(cols)}) VALUES({ph}) RETURNING id", tuple(cols.values()))
            aid = int(cur.lastrowid)
        con.commit()
        return aid
    finally:
        con.close()


_SEV_WEIGHT = {"critical": 8, "high": 4, "medium": 2, "low": 1}


def asset_risk_score(db_path: Path, asset_id: int, *, kritikalitaet: int | None = None,
                     con: Any | None = None) -> dict[str, Any]:
    """Risiko-Score eines Assets: offene Incidents × Severity × Kritikalität (#1310)."""
    from soc.constants import INCIDENT_OPEN_STATES
    own = con is None
    if own:
        ensure_db(db_path)
        con = _connect(db_path)
    try:
        if kritikalitaet is None:
            r = con.execute("SELECT kritikalitaet FROM soc_assets WHERE id=?", (asset_id,)).fetchone()
            kritikalitaet = int(r["kritikalitaet"]) if r else 3
        ph = ",".join("?" for _ in INCIDENT_OPEN_STATES)
        rows = con.execute(
            f"SELECT severity FROM soc_incidents WHERE asset_id=? AND status IN ({ph})",
            (asset_id, *INCIDENT_OPEN_STATES)).fetchall()
        base = sum(_SEV_WEIGHT.get((r["severity"] or "medium").lower(), 2) for r in rows)
        score = round(base * (int(kritikalitaet) / 3.0), 1)
        ampel = "rot" if score >= 16 else "orange" if score >= 6 else "gelb" if score > 0 else "gruen"
        return {"score": score, "ampel": ampel, "open_incidents": len(rows), "kritikalitaet": int(kritikalitaet)}
    finally:
        if own:
            con.close()


def list_assets(db_path: Path) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        out = []
        for r in con.execute("SELECT * FROM soc_assets ORDER BY kritikalitaet DESC, agent_name").fetchall():
            d = _asset_to_dict(r)
            d["alert_count"] = con.execute("SELECT COUNT(*) c FROM soc_alerts WHERE asset_id=?", (d["id"],)).fetchone()["c"]
            d["incident_count"] = con.execute("SELECT COUNT(*) c FROM soc_incidents WHERE asset_id=?", (d["id"],)).fetchone()["c"]
            d["risk"] = asset_risk_score(db_path, d["id"], kritikalitaet=d.get("kritikalitaet", 3), con=con)
            out.append(d)
        return out
    finally:
        con.close()


def asset_detail(db_path: Path, asset_id: int) -> dict[str, Any] | None:
    """Asset-zentrische Detailsicht: Alarme, Incidents, offene Meldetracks, Risiko (#1308)."""
    asset = get_asset(db_path, asset_id)
    if not asset:
        return None
    alerts = list_alerts(db_path, asset_id=asset_id, limit=200)
    incidents = [i for i in list_incidents(db_path, include_closed=True, limit=200) if i.get("asset_id") == asset_id]
    tracks = []
    for inc in incidents:
        if inc["status"] != "closed":
            tracks.extend(list_meldetracks(db_path, inc["id"]))
    asset["risk"] = asset_risk_score(db_path, asset_id, kritikalitaet=asset.get("kritikalitaet", 3))
    asset["alerts"] = alerts
    asset["incidents"] = incidents
    asset["meldetracks"] = tracks
    return asset


def assign_alert_asset(db_path: Path, alert_uid: str, asset_id: int | None) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("UPDATE soc_alerts SET asset_id=? WHERE alert_uid=?", (asset_id, alert_uid))
        con.commit()
    finally:
        con.close()


def assign_incident_asset(db_path: Path, incident_id: int, asset_id: int | None, *, actor: str = "") -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("UPDATE soc_incidents SET asset_id=?, updated_at=aics_now() WHERE id=?",
                    (asset_id, incident_id))
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, incident_id, actor=actor, event="incident.asset",
                     detail=f"Asset-Zuordnung → {asset_id}")


def get_asset(db_path: Path, asset_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_assets WHERE id=?", (asset_id,)).fetchone()
        return _asset_to_dict(r) if r else None
    finally:
        con.close()


def find_asset_for_agent(db_path: Path, agent_name: str, agent_id: str = "") -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_assets WHERE agent_name=? OR (agent_id!='' AND agent_id=?)",
                        (agent_name, agent_id)).fetchone()
        return _asset_to_dict(r) if r else None
    finally:
        con.close()


def _asset_to_dict(r: Any) -> dict[str, Any]:
    d = dict(r)
    for f in ("personenbezogen", "nis2_scope", "cra_produkt", "ki_hochrisiko", "dora_scope"):
        d[f] = bool(d.get(f))
    try:
        d["meta"] = json.loads(d.pop("meta_json", "{}") or "{}")
    except Exception:
        d["meta"] = {}
    return d


# ── Incidents (#1271) + Timeline (sha256-Kette) ─────────────────────────────

def create_incident(db_path: Path, *, titel: str, severity: str = "medium",
                    klassifikation: str = "", asset_id: int | None = None,
                    agent_name: str = "", owner: str = "", beschreibung: str = "",
                    mitre: dict | None = None, firmen_id: int | None = None,
                    alert_uids: list[str] | None = None, actor: str = "") -> int:
    ensure_db(db_path)
    # Asset automatisch verknüpfen, wenn für den Agenten eines existiert (#1301)
    if asset_id is None and agent_name:
        a = find_asset_for_agent(db_path, agent_name)
        if a:
            asset_id = a["id"]
            if firmen_id is None:
                firmen_id = a.get("firmen_id")
    con = _connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO soc_incidents(titel, severity, klassifikation, asset_id, agent_name,
               owner, beschreibung, mitre, firmen_id) VALUES(?,?,?,?,?,?,?,?,?) RETURNING id""",
            (titel, severity, klassifikation, asset_id, agent_name, owner, beschreibung,
             json.dumps(mitre or {}), firmen_id))
        iid = int(cur.lastrowid)
        for uid in (alert_uids or []):
            con.execute("INSERT INTO soc_incident_alerts(incident_id, alert_uid) VALUES(?,?) ON CONFLICT DO NOTHING",
                        (iid, uid))
            con.execute("UPDATE soc_alerts SET status='confirmed' WHERE alert_uid=?", (uid,))
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, iid, actor=actor, event="incident.created",
                     detail=f"Incident '{titel}' aus {len(alert_uids or [])} Alarm(en)")
    return iid


def list_incidents(db_path: Path, *, status: str | None = None, include_closed: bool = False,
                   limit: int = 500) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = "SELECT * FROM soc_incidents WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status=?"; params.append(status)
        elif not include_closed:
            q += " AND status != 'closed'"
        q += " ORDER BY updated_at DESC LIMIT ?"; params.append(int(limit))
        return [_incident_to_dict(r) for r in con.execute(q, params).fetchall()]
    finally:
        con.close()


def close_incident(db_path: Path, incident_id: int, *, reason: str, actor: str = "") -> dict[str, Any]:
    """Schließt einen Incident mit Pflicht-Begründung (#1296)."""
    if not reason or len(reason.strip()) < 10:
        return {"ok": False, "error": "Begründung erforderlich (mind. 10 Zeichen)"}
    inc = get_incident(db_path, incident_id)
    if not inc:
        return {"ok": False, "error": "Incident nicht gefunden"}
    # PIR-Pflicht-Gate (#1316): echte (eskalierte) Incidents brauchen vor 'closed' einen
    # Post-Incident-Review mit Ursachenanalyse. False-Positives sind ausgenommen.
    from soc.constants import PIR_REQUIRED_BEFORE_CLOSE_FROM
    if inc["status"] in PIR_REQUIRED_BEFORE_CLOSE_FROM and not pir_complete(db_path, incident_id):
        return {"ok": False, "error": "Post-Incident-Review erforderlich: bitte die "
                "Ursachenanalyse (Root Cause) ausfüllen, bevor der Incident geschlossen wird."}
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE soc_incidents SET status='closed', closed_reason=?, closed_by=?,
               closed_at=aics_now(), updated_at=aics_now() WHERE id=?""",
            (reason.strip(), actor, incident_id))
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, incident_id, actor=actor, event="incident.closed",
                     detail=f"Geschlossen: {reason.strip()}")
    return {"ok": True}


def get_incident(db_path: Path, incident_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_incidents WHERE id=?", (incident_id,)).fetchone()
        if not r:
            return None
        d = _incident_to_dict(r)
        d["alerts"] = [row["alert_uid"] for row in
                       con.execute("SELECT alert_uid FROM soc_incident_alerts WHERE incident_id=?",
                                   (incident_id,)).fetchall()]
        return d
    finally:
        con.close()


def update_incident(db_path: Path, incident_id: int, fields: dict[str, Any], *, actor: str = "") -> dict | None:
    allowed = {"titel", "severity", "klassifikation", "confidence", "owner", "beschreibung",
               "response_actions", "lessons_learned", "personal_data_involved", "awareness_at",
               "asset_id", "firmen_id"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            params.append(int(v) if k == "personal_data_involved" else v)
    if not sets:
        return get_incident(db_path, incident_id)
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        params.append(incident_id)
        con.execute(f"UPDATE soc_incidents SET {', '.join(sets)}, updated_at=aics_now() WHERE id=?", params)
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, incident_id, actor=actor, event="incident.updated",
                     detail=", ".join(fields.keys()))
    return get_incident(db_path, incident_id)


def set_incident_status(db_path: Path, incident_id: int, status: str, *, actor: str = "") -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("UPDATE soc_incidents SET status=?, updated_at=aics_now() WHERE id=?",
                    (status, incident_id))
        # SLA-Zeitstempel (#1315): erste Bearbeitung = acknowledged, resolved = resolved_at
        if status in ("in_review", "confirmed"):
            con.execute("UPDATE soc_incidents SET acknowledged_at=aics_now() "
                        "WHERE id=? AND acknowledged_at IS NULL", (incident_id,))
        if status == "resolved":
            con.execute("UPDATE soc_incidents SET resolved_at=aics_now() WHERE id=?", (incident_id,))
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, incident_id, actor=actor, event="incident.status",
                     detail=f"→ {status}")


def store_incident_analysis(db_path: Path, incident_id: int, analysis: dict) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT meta_json FROM soc_incidents WHERE id=?", (incident_id,)).fetchone()
        meta = {}
        if r and r["meta_json"]:
            try:
                meta = json.loads(r["meta_json"])
            except Exception:
                meta = {}
        meta["analysis"] = analysis
        con.execute("UPDATE soc_incidents SET meta_json=?, updated_at=aics_now() WHERE id=?",
                    (json.dumps(meta), incident_id))
        con.commit()
    finally:
        con.close()


def set_incident_regimes(db_path: Path, incident_id: int, flags: dict, *, actor: str = "") -> None:
    """Speichert die am Incident gewählten Melde-Regelwerke (meta.regime_flags, #1301)."""
    from soc.constants import ASSET_FLAGS
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT meta_json FROM soc_incidents WHERE id=?", (incident_id,)).fetchone()
        meta = {}
        if r and r["meta_json"]:
            try:
                meta = json.loads(r["meta_json"])
            except Exception:
                meta = {}
        meta["regime_flags"] = {f: bool(flags.get(f)) for f in ASSET_FLAGS}
        con.execute("UPDATE soc_incidents SET meta_json=?, updated_at=aics_now() WHERE id=?",
                    (json.dumps(meta), incident_id))
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, incident_id, actor=actor, event="incident.regimes",
                     detail=", ".join(f for f in ASSET_FLAGS if flags.get(f)) or "(keine)")


def get_incident_alerts(db_path: Path, incident_id: int) -> list[dict[str, Any]]:
    """Die vollständigen Alarm-Datensätze eines Incidents."""
    inc = get_incident(db_path, incident_id)
    if not inc:
        return []
    out = []
    for uid in inc.get("alerts", []):
        a = get_alert(db_path, uid)
        if a:
            out.append(a)
    return out


def add_alerts_to_incident(db_path: Path, incident_id: int, alert_uids: list[str], *,
                           actor: str = "", bump_severity: bool = True) -> dict[str, Any]:
    """Verknüpft mehrere (existierende) Alarme idempotent mit einem Incident (#1328)."""
    ensure_db(db_path)
    if not get_incident(db_path, incident_id):
        return {"ok": False, "error": "Incident nicht gefunden"}
    con = _connect(db_path)
    added = 0
    try:
        for uid in alert_uids:
            cur = con.execute(
                "INSERT INTO soc_incident_alerts(incident_id, alert_uid) VALUES(?,?) ON CONFLICT DO NOTHING",
                (incident_id, uid))
            if cur.rowcount:
                added += 1
                con.execute("UPDATE soc_alerts SET status='confirmed' WHERE alert_uid=?", (uid,))
        # Severity des Incidents auf höchste verknüpfte Alarm-Severity anheben
        if bump_severity and added:
            row = con.execute(
                """SELECT a.severity FROM soc_alerts a JOIN soc_incident_alerts ia
                   ON ia.alert_uid = a.alert_uid WHERE ia.incident_id=?""", (incident_id,)).fetchall()
            order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            sevs = [r["severity"] for r in row] + [con.execute(
                "SELECT severity FROM soc_incidents WHERE id=?", (incident_id,)).fetchone()["severity"]]
            top = max(sevs, key=lambda s: order.get(s, 1))
            con.execute("UPDATE soc_incidents SET severity=?, updated_at=aics_now() WHERE id=?",
                        (top, incident_id))
        con.commit()
    finally:
        con.close()
    if added:
        _append_timeline(db_path, incident_id, actor=actor, event="incident.alerts_linked",
                         detail=f"{added} Alarm(e) verknüpft")
    return {"ok": True, "added": added}


def remove_alert_from_incident(db_path: Path, incident_id: int, alert_uid: str, *,
                               actor: str = "") -> dict[str, Any]:
    """Löst einen einzelnen Alarm von einem Incident (#1328)."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute("DELETE FROM soc_incident_alerts WHERE incident_id=? AND alert_uid=?",
                          (incident_id, alert_uid))
        con.commit()
        removed = cur.rowcount
    finally:
        con.close()
    if removed:
        _append_timeline(db_path, incident_id, actor=actor, event="incident.alert_unlinked",
                         detail=f"Alarm {alert_uid} entfernt")
    return {"ok": True, "removed": removed}


def list_timeline(db_path: Path, incident_id: int) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM soc_incident_timeline WHERE incident_id=? ORDER BY id", (incident_id,)).fetchall()]
    finally:
        con.close()


def _append_timeline(db_path: Path, incident_id: int, *, actor: str, event: str, detail: str = "") -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        last = con.execute(
            "SELECT entry_hash FROM soc_incident_timeline WHERE incident_id=? ORDER BY id DESC LIMIT 1",
            (incident_id,)).fetchone()
        prev = last["entry_hash"] if last else ""
        payload = json.dumps({"incident": incident_id, "actor": actor, "event": event,
                              "detail": detail}, sort_keys=True, ensure_ascii=False)
        entry_hash = hashlib.sha256((prev + payload).encode("utf-8")).hexdigest()
        con.execute(
            """INSERT INTO soc_incident_timeline(incident_id, actor, event, detail, prev_hash, entry_hash)
               VALUES(?,?,?,?,?,?)""",
            (incident_id, actor, event, detail, prev, entry_hash))
        con.commit()
    finally:
        con.close()


def add_timeline_note(db_path: Path, incident_id: int, *, actor: str, detail: str) -> None:
    _append_timeline(db_path, incident_id, actor=actor, event="note", detail=detail)


def _incident_to_dict(r: Any) -> dict[str, Any]:
    d = dict(r)
    d["personal_data_involved"] = bool(d.get("personal_data_involved"))
    for k in ("mitre", "meta_json"):
        try:
            d[k] = json.loads(d.get(k) or "{}")
        except Exception:
            d[k] = {}
    return d


# ── Meldetracks (#1281) ─────────────────────────────────────────────────────

def upsert_meldetrack(db_path: Path, incident_id: int, *, regime: str, legal: str,
                      deadlines: list[dict], target_ref: str = "") -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO soc_meldetracks(incident_id, regime, legal, deadlines_json, target_ref)
               VALUES(?,?,?,?,?)
               ON CONFLICT(incident_id, regime) DO UPDATE SET legal=excluded.legal,
                 deadlines_json=excluded.deadlines_json, updated_at=aics_now() RETURNING id""",
            (incident_id, regime, legal, json.dumps(deadlines), target_ref))
        con.commit()
        row = con.execute("SELECT id FROM soc_meldetracks WHERE incident_id=? AND regime=?",
                          (incident_id, regime)).fetchone()
        return int(row["id"]) if row else int(cur.lastrowid or 0)
    finally:
        con.close()


def list_meldetracks(db_path: Path, incident_id: int) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT * FROM soc_meldetracks WHERE incident_id=? ORDER BY id",
                           (incident_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["deadlines"] = json.loads(d.pop("deadlines_json", "[]") or "[]")
            except Exception:
                d["deadlines"] = []
            out.append(d)
        return out
    finally:
        con.close()


def update_meldetrack(db_path: Path, track_id: int, *, status: str | None = None,
                      target_ref: str | None = None, notiz: str | None = None,
                      deadlines: list[dict] | None = None) -> None:
    sets, params = [], []
    if status is not None:
        sets.append("status=?"); params.append(status)
    if target_ref is not None:
        sets.append("target_ref=?"); params.append(target_ref)
    if notiz is not None:
        sets.append("notiz=?"); params.append(notiz)
    if deadlines is not None:
        sets.append("deadlines_json=?"); params.append(json.dumps(deadlines))
    if not sets:
        return
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        params.append(track_id)
        con.execute(f"UPDATE soc_meldetracks SET {', '.join(sets)}, updated_at=aics_now() WHERE id=?", params)
        con.commit()
    finally:
        con.close()


# ── Schwachstellen-Register (#1343) ─────────────────────────────────────────

_VULN_SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _vuln_to_dict(r: Any) -> dict[str, Any]:
    d = dict(r)
    for k in ("external_refs",):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except Exception:
            d[k] = []
    try:
        d["raw_json"] = json.loads(d.get("raw_json") or "{}")
    except Exception:
        d["raw_json"] = {}
    return d


def upsert_vulnerability(db_path: Path, finding: dict[str, Any], *, con: Any | None = None) -> dict[str, Any]:
    """Idempotenter Upsert eines normalisierten States-Findings (#1343).

    - Dedup über ``vuln_uid`` (hash(agent_id|cve_id|package_name)).
    - INSERT setzt ``first_seen``; UPDATE behält ``triage_status``/``triage_kommentar``
      (Analysten-Triage nie überschreiben) und hebt Schwere/CVSS nur an.
    - Jeder Lauf setzt ``last_synced_at`` + ``last_seen`` (Reconcile-Marker) und
      ``wazuh_status='Active'`` (gesehen = aktiv).
    Returns {action: inserted|updated|unchanged, id, vuln_uid}.
    """
    from soc.constants import VULN_WAZUH_ACTIVE
    own = con is None
    if own:
        ensure_db(db_path)
        con = _connect(db_path)
    try:
        uid = finding.get("vuln_uid", "")
        if not uid:
            raise ValueError("Feld 'vuln_uid' ist Pflicht")
        new_sev = (finding.get("severity") or "low").lower()
        new_cvss = float(finding.get("cvss_score") or 0)
        row = con.execute("SELECT * FROM soc_vulnerabilities WHERE vuln_uid=?", (uid,)).fetchone()
        if row is None:
            cur = con.execute(
                """INSERT INTO soc_vulnerabilities(vuln_uid, cve_id, severity, cvss_score,
                   cvss_version, cvss_vector, package_name, package_version, fixed_version,
                   condition, wazuh_status, detection_time, published_at, advisory_url,
                   external_refs, agent_id, agent_name, asset_id, firmen_id, source,
                   raw_json, first_seen, last_seen, last_synced_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,aics_now(),aics_now(),aics_now())
                   RETURNING id""",
                (uid, finding.get("cve_id", ""), new_sev, new_cvss,
                 finding.get("cvss_version", ""), finding.get("cvss_vector", ""),
                 finding.get("package_name", ""), finding.get("package_version", ""),
                 finding.get("fixed_version", ""), finding.get("condition", ""),
                 finding.get("wazuh_status", VULN_WAZUH_ACTIVE), finding.get("detection_time", ""),
                 finding.get("published_at", ""), finding.get("advisory_url", ""),
                 json.dumps(finding.get("external_refs", [])), finding.get("agent_id", ""),
                 finding.get("agent_name", ""), finding.get("asset_id"), finding.get("firmen_id"),
                 finding.get("source", "wazuh-states"), json.dumps(finding.get("raw_json", {}))))
            vid = int(cur.lastrowid)
            if own:
                con.commit()
            return {"action": "inserted", "id": vid, "vuln_uid": uid}
        cur = dict(row)
        keep_sev = (cur.get("severity") or "low").lower()
        sev = new_sev if _VULN_SEV_RANK.get(new_sev, 0) > _VULN_SEV_RANK.get(keep_sev, 0) else keep_sev
        cvss = max(new_cvss, float(cur.get("cvss_score") or 0))
        con.execute(
            """UPDATE soc_vulnerabilities SET severity=?, cvss_score=?, cvss_version=?,
               cvss_vector=?, package_version=?, fixed_version=?, condition=?,
               wazuh_status=?, detection_time=?, published_at=?, advisory_url=?,
               external_refs=?, asset_id=COALESCE(?, asset_id), firmen_id=COALESCE(?, firmen_id),
               raw_json=?, last_seen=aics_now(), last_synced_at=aics_now(), updated_at=aics_now()
               WHERE id=?""",
            (sev, cvss, finding.get("cvss_version") or cur.get("cvss_version", ""),
             finding.get("cvss_vector") or cur.get("cvss_vector", ""),
             finding.get("package_version") or cur.get("package_version", ""),
             finding.get("fixed_version") or cur.get("fixed_version", ""),
             finding.get("condition") or cur.get("condition", ""),
             finding.get("wazuh_status", VULN_WAZUH_ACTIVE),
             finding.get("detection_time") or cur.get("detection_time", ""),
             finding.get("published_at") or cur.get("published_at", ""),
             finding.get("advisory_url") or cur.get("advisory_url", ""),
             json.dumps(finding.get("external_refs", [])) if finding.get("external_refs") else cur.get("external_refs", "[]"),
             finding.get("asset_id"), finding.get("firmen_id"),
             json.dumps(finding.get("raw_json", {})), cur["id"]))
        if own:
            con.commit()
        changed = (sev != keep_sev or cvss != float(cur.get("cvss_score") or 0)
                   or cur.get("wazuh_status") != finding.get("wazuh_status", VULN_WAZUH_ACTIVE))
        return {"action": "updated" if changed else "unchanged", "id": cur["id"], "vuln_uid": uid}
    finally:
        if own:
            con.close()


def reconcile_vulnerabilities(db_path: Path, seen_uids: list[str] | set[str], *,
                              con: Any | None = None) -> int:
    """Setzt zuvor aktive, in diesem Lauf NICHT mehr gesehene CVEs auf 'Solved'.

    Der States-Index ist ein Ist-Zustand: verschwundene Einträge = behoben. Kein
    Hard-Delete — die Historie (Triage, first_seen) bleibt erhalten. Alle aktiven
    Findings, deren ``vuln_uid`` nicht in ``seen_uids`` enthalten ist, werden auf
    'Solved' gesetzt (unabhängig von Zeitstempel-Granularität). Returns #solved.
    """
    from soc.constants import VULN_WAZUH_ACTIVE, VULN_WAZUH_SOLVED
    own = con is None
    if own:
        ensure_db(db_path)
        con = _connect(db_path)
    try:
        seen = set(seen_uids or [])
        active = con.execute(
            "SELECT id, vuln_uid FROM soc_vulnerabilities WHERE wazuh_status=?",
            (VULN_WAZUH_ACTIVE,)).fetchall()
        stale_ids = [r["id"] for r in active if r["vuln_uid"] not in seen]
        for vid in stale_ids:
            con.execute(
                "UPDATE soc_vulnerabilities SET wazuh_status=?, updated_at=aics_now() WHERE id=?",
                (VULN_WAZUH_SOLVED, vid))
        if own:
            con.commit()
        return len(stale_ids)
    finally:
        if own:
            con.close()


def list_vulnerabilities(db_path: Path, *, severity: str | None = None,
                         wazuh_status: str | None = None, triage_status: str | None = None,
                         agent: str | None = None, asset_id: int | None = None,
                         firmen_id: int | None = None, only_active: bool = True,
                         limit: int = 1000) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = "SELECT * FROM soc_vulnerabilities WHERE 1=1"
        params: list[Any] = []
        if severity:
            q += " AND severity=?"; params.append(severity)
        if wazuh_status:
            q += " AND wazuh_status=?"; params.append(wazuh_status)
        elif only_active:
            q += " AND wazuh_status=?"; params.append("Active")
        if triage_status:
            q += " AND triage_status=?"; params.append(triage_status)
        if agent:
            q += " AND agent_name=?"; params.append(agent)
        if asset_id is not None:
            q += " AND asset_id=?"; params.append(int(asset_id))
        if firmen_id is not None:
            q += " AND firmen_id=?"; params.append(int(firmen_id))
        q += " ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, cvss_score DESC, id DESC LIMIT ?"
        params.append(int(limit))
        return [_vuln_to_dict(r) for r in con.execute(q, params).fetchall()]
    finally:
        con.close()


def get_vulnerability(db_path: Path, vuln_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_vulnerabilities WHERE id=?", (vuln_id,)).fetchone()
        return _vuln_to_dict(r) if r else None
    finally:
        con.close()


def set_vulnerability_triage(db_path: Path, vuln_id: int, *, triage_status: str,
                             kommentar: str | None = None) -> bool:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if kommentar is not None:
            cur = con.execute(
                "UPDATE soc_vulnerabilities SET triage_status=?, triage_kommentar=?, updated_at=aics_now() WHERE id=?",
                (triage_status, kommentar, vuln_id))
        else:
            cur = con.execute(
                "UPDATE soc_vulnerabilities SET triage_status=?, updated_at=aics_now() WHERE id=?",
                (triage_status, vuln_id))
        con.commit()
        return bool(cur.rowcount)
    finally:
        con.close()


def set_vulnerability_promotion(db_path: Path, vuln_id: int, *, alert_uid: str | None = None,
                                incident_id: int | None = None) -> None:
    """Schreibt den Promotion-Rückverweis + setzt triage_status='promoted'."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if alert_uid is not None:
            con.execute(
                "UPDATE soc_vulnerabilities SET promoted_alert_uid=?, triage_status='promoted', updated_at=aics_now() WHERE id=?",
                (alert_uid, vuln_id))
        if incident_id is not None:
            con.execute(
                "UPDATE soc_vulnerabilities SET promoted_incident_id=?, triage_status='promoted', updated_at=aics_now() WHERE id=?",
                (int(incident_id), vuln_id))
        con.commit()
    finally:
        con.close()


def count_open_vulnerabilities(db_path: Path) -> dict[str, Any]:
    """Dashboard-KPI: offene (Active) Schwachstellen je Schwere + High/Crit-Summe."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            """SELECT severity, COUNT(*) AS c FROM soc_vulnerabilities
               WHERE wazuh_status='Active' AND triage_status != 'false_positive'
               GROUP BY severity""").fetchall()
        by_sev = {r["severity"]: int(r["c"]) for r in rows}
        return {
            "by_severity": by_sev,
            "critical": by_sev.get("critical", 0),
            "high": by_sev.get("high", 0),
            "critical_high": by_sev.get("critical", 0) + by_sev.get("high", 0),
            "total": sum(by_sev.values()),
        }
    finally:
        con.close()


# ── KPIs (Dashboard #1275) ──────────────────────────────────────────────────

# ── Response-Playbooks / Runbooks (#1314) ───────────────────────────────────

def list_playbooks(db_path: Path, *, only_enabled: bool = False) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = "SELECT * FROM soc_playbooks"
        if only_enabled:
            q += " WHERE enabled=1"
        q += " ORDER BY kategorie, name"
        return [_playbook_to_dict(r) for r in con.execute(q).fetchall()]
    finally:
        con.close()


def get_playbook(db_path: Path, playbook_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_playbooks WHERE id=?", (playbook_id,)).fetchone()
        return _playbook_to_dict(r) if r else None
    finally:
        con.close()


def save_playbook(db_path: Path, *, id: int | None = None, name: str, kategorie: str = "",
                  beschreibung: str = "", steps: list[dict] | None = None, enabled: bool = True) -> int:
    ensure_db(db_path)
    steps = steps or []
    # Schritt-IDs sicherstellen
    for i, s in enumerate(steps):
        s.setdefault("id", i + 1)
        s["mandatory"] = bool(s.get("mandatory"))
    con = _connect(db_path)
    try:
        if id:
            con.execute(
                "UPDATE soc_playbooks SET name=?, kategorie=?, beschreibung=?, steps_json=?, "
                "enabled=?, version=version+1, updated_at=aics_now() WHERE id=?",
                (name, kategorie, beschreibung, json.dumps(steps), 1 if enabled else 0, id))
            pid = id
        else:
            cur = con.execute(
                "INSERT INTO soc_playbooks(name, kategorie, beschreibung, steps_json, enabled) VALUES(?,?,?,?,?) RETURNING id",
                (name, kategorie, beschreibung, json.dumps(steps), 1 if enabled else 0))
            pid = int(cur.lastrowid)
        con.commit()
        return pid
    finally:
        con.close()


def delete_playbook(db_path: Path, playbook_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_playbooks WHERE id=?", (playbook_id,))
        con.commit()
    finally:
        con.close()


def _playbook_to_dict(r: Any) -> dict[str, Any]:
    d = dict(r)
    try:
        d["steps"] = json.loads(d.pop("steps_json", "[]") or "[]")
    except Exception:
        d["steps"] = []
    d["enabled"] = bool(d.get("enabled"))
    return d


def assign_playbook_to_incident(db_path: Path, incident_id: int, playbook_id: int, *, actor: str = "") -> int:
    pb = get_playbook(db_path, playbook_id)
    if not pb:
        raise ValueError("Playbook nicht gefunden")
    steps = [{"id": s["id"], "text": s.get("text", ""), "mandatory": bool(s.get("mandatory")),
              "done": False, "done_at": None, "done_by": None} for s in pb.get("steps", [])]
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO soc_incident_playbook(incident_id, playbook_id, name, steps_json, assigned_by) VALUES(?,?,?,?,?) RETURNING id",
            (incident_id, playbook_id, pb["name"], json.dumps(steps), actor))
        iid = int(cur.lastrowid)
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, incident_id, actor=actor, event="playbook.assigned", detail=pb["name"])
    return iid


def list_incident_playbooks(db_path: Path, incident_id: int) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT * FROM soc_incident_playbook WHERE incident_id=? ORDER BY id",
                           (incident_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["steps"] = json.loads(d.pop("steps_json", "[]") or "[]")
            except Exception:
                d["steps"] = []
            total = len(d["steps"]); done = sum(1 for s in d["steps"] if s.get("done"))
            d["progress"] = {"done": done, "total": total}
            out.append(d)
        return out
    finally:
        con.close()


def toggle_playbook_step(db_path: Path, instance_id: int, step_id: int, done: bool, *, actor: str = "") -> dict | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT incident_id, steps_json, name FROM soc_incident_playbook WHERE id=?",
                        (instance_id,)).fetchone()
        if not r:
            return None
        steps = json.loads(r["steps_json"] or "[]")
        label = ""
        for s in steps:
            if s.get("id") == step_id:
                s["done"] = bool(done)
                s["done_at"] = "now" if done else None
                s["done_by"] = actor if done else None
                label = s.get("text", "")
        con.execute("UPDATE soc_incident_playbook SET steps_json=? WHERE id=?",
                    (json.dumps(steps), instance_id))
        con.commit()
        incident_id = r["incident_id"]
    finally:
        con.close()
    _append_timeline(db_path, incident_id, actor=actor,
                     event="playbook.step", detail=f"{'✓' if done else '○'} {label}")
    return {"ok": True}


def incident_mandatory_open(db_path: Path, incident_id: int) -> int:
    """Anzahl noch offener Pflicht-Schritte über alle Playbooks eines Incidents."""
    open_n = 0
    for pb in list_incident_playbooks(db_path, incident_id):
        open_n += sum(1 for s in pb["steps"] if s.get("mandatory") and not s.get("done"))
    return open_n


# ── Post-Incident-Review (PIR) + Maßnahmen-Tracking (#1316) ─────────────────

def get_pir(db_path: Path, incident_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_pir WHERE incident_id=?", (incident_id,)).fetchone()
        return dict(r) if r else None
    finally:
        con.close()


def save_pir(db_path: Path, incident_id: int, *, root_cause: str = "", what_went_well: str = "",
             what_went_wrong: str = "", lessons: str = "", actor: str = "") -> None:
    """Upsert des PIR-Datensatzes eines Incidents."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO soc_pir(incident_id, root_cause, what_went_well, what_went_wrong,
               lessons, created_by) VALUES(?,?,?,?,?,?)
               ON CONFLICT(incident_id) DO UPDATE SET root_cause=excluded.root_cause,
               what_went_well=excluded.what_went_well, what_went_wrong=excluded.what_went_wrong,
               lessons=excluded.lessons, updated_at=aics_now()""",
            (incident_id, root_cause, what_went_well, what_went_wrong, lessons, actor))
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, incident_id, actor=actor, event="pir.saved",
                     detail="Post-Incident-Review aktualisiert")


def pir_complete(db_path: Path, incident_id: int) -> bool:
    """True, wenn ein PIR mit ausgefüllter Ursachenanalyse vorliegt (Close-Gate)."""
    pir = get_pir(db_path, incident_id)
    return bool(pir and (pir.get("root_cause") or "").strip())


def list_pir_actions(db_path: Path, *, incident_id: int | None = None,
                     only_open: bool = False) -> list[dict[str, Any]]:
    """Maßnahmen — je Incident oder zentral über alle (mit Incident-Titel)."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = ("SELECT a.*, i.titel AS incident_titel, i.severity AS incident_severity, "
             "i.status AS incident_status FROM soc_pir_actions a "
             "LEFT JOIN soc_incidents i ON i.id = a.incident_id")
        clauses, params = [], []
        if incident_id is not None:
            clauses.append("a.incident_id=?"); params.append(incident_id)
        if only_open:
            clauses.append("a.status != 'erledigt'")
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY (a.status='erledigt'), a.frist, a.id"
        return [dict(r) for r in con.execute(q, params).fetchall()]
    finally:
        con.close()


def save_pir_action(db_path: Path, *, id: int | None = None, incident_id: int,
                    beschreibung: str, owner: str = "", frist: str = "",
                    status: str = "offen", actor: str = "") -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if id:
            done_at = "aics_now()" if status == "erledigt" else "done_at"
            con.execute(
                f"""UPDATE soc_pir_actions SET beschreibung=?, owner=?, frist=?, status=?,
                    done_at=CASE WHEN ?='erledigt' AND status!='erledigt' THEN aics_now()
                                 WHEN ?!='erledigt' THEN NULL ELSE done_at END,
                    done_by=CASE WHEN ?='erledigt' THEN ? ELSE done_by END WHERE id=?""",
                (beschreibung, owner, frist, status, status, status, status, actor, id))
            aid = id
        else:
            cur = con.execute(
                """INSERT INTO soc_pir_actions(incident_id, beschreibung, owner, frist, status,
                   created_by) VALUES(?,?,?,?,?,?) RETURNING id""",
                (incident_id, beschreibung, owner, frist, status, actor))
            aid = int(cur.lastrowid)
        con.commit()
    finally:
        con.close()
    _append_timeline(db_path, incident_id, actor=actor, event="pir.action",
                     detail=f"Maßnahme {'aktualisiert' if id else 'angelegt'}: {beschreibung[:60]}")
    return aid


def set_pir_action_status(db_path: Path, action_id: int, status: str, *, actor: str = "") -> dict[str, Any]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT incident_id, beschreibung FROM soc_pir_actions WHERE id=?",
                        (action_id,)).fetchone()
        if not r:
            return {"ok": False, "error": "Maßnahme nicht gefunden"}
        con.execute(
            """UPDATE soc_pir_actions SET status=?,
               done_at=CASE WHEN ?='erledigt' THEN aics_now() ELSE NULL END,
               done_by=CASE WHEN ?='erledigt' THEN ? ELSE '' END WHERE id=?""",
            (status, status, status, actor, action_id))
        con.commit()
        iid, desc = r["incident_id"], r["beschreibung"]
    finally:
        con.close()
    _append_timeline(db_path, iid, actor=actor, event="pir.action",
                     detail=f"Maßnahme → {status}: {desc[:60]}")
    return {"ok": True}


def delete_pir_action(db_path: Path, action_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_pir_actions WHERE id=?", (action_id,))
        con.commit()
    finally:
        con.close()


def control_evidence(db_path: Path) -> dict[str, Any]:
    """Kennzahlen als Nachweis der Fähigkeit „Incident-Handling/Detektion" (#1285).

    Belegt für NIS2 Art. 21(2)(b) / AI-Act Art. 72, dass die Detektions-/
    Reaktions-Fähigkeit tatsächlich existiert und arbeitet.
    """
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        handled = con.execute(
            "SELECT COUNT(*) c FROM soc_alerts WHERE status != 'new'").fetchone()["c"]
        total_alerts = con.execute("SELECT COUNT(*) c FROM soc_alerts").fetchone()["c"]
        closed = con.execute("SELECT COUNT(*) c FROM soc_incidents WHERE status='closed'").fetchone()["c"]
        from soc.constants import INCIDENT_OPEN_STATES
        ph = ",".join("?" for _ in INCIDENT_OPEN_STATES)
        open_inc = con.execute(
            f"SELECT COUNT(*) c FROM soc_incidents WHERE status IN ({ph})",
            tuple(INCIDENT_OPEN_STATES)).fetchone()["c"]
        # MTTR (Stunden) über geschlossene Incidents mit closed_at
        row = con.execute(
            "SELECT AVG(EXTRACT(EPOCH FROM (closed_at::timestamp - created_at::timestamp))/3600.0) m "
            "FROM soc_incidents WHERE status='closed' AND closed_at IS NOT NULL").fetchone()
        mttr = round(row["m"], 1) if row and row["m"] is not None else None
        return {
            "alerts_handled": handled,
            "alerts_total": total_alerts,
            "handled_ratio": round(handled / total_alerts, 3) if total_alerts else 0.0,
            "incidents_closed": closed,
            "incidents_open": open_inc,
            "mttr_hours": mttr,
            "control": "incident_handling",
            "legal": ["NIS2 Art. 21(2)(b)", "AI-Act Art. 72"],
        }
    finally:
        con.close()


def incident_frequency(db_path: Path, *, agent: str | None = None,
                       rule_id: str | None = None) -> dict[str, Any]:
    """Empirische Häufigkeit (Alarme/Incidents) → Eintrittswahrscheinlichkeits-
    Vorschlag für die Risikobewertung (#1284). Read-only.
    """
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = "SELECT COUNT(*) c FROM soc_alerts WHERE status IN ('confirmed','in_review','new')"
        params: list[Any] = []
        if agent:
            q += " AND agent_name=?"; params.append(agent)
        if rule_id:
            q += " AND rule_id=?"; params.append(rule_id)
        alerts = con.execute(q, params).fetchone()["c"]
        iq = "SELECT COUNT(*) c FROM soc_incidents WHERE 1=1"
        ip: list[Any] = []
        if agent:
            iq += " AND agent_name=?"; ip.append(agent)
        incidents = con.execute(iq, ip).fetchone()["c"]
    finally:
        con.close()
    # Vorschlag 1–5 aus der beobachteten Frequenz
    n = incidents if incidents else 0
    if n >= 10:
        stufe, label = 5, "sehr hoch"
    elif n >= 5:
        stufe, label = 4, "hoch"
    elif n >= 2:
        stufe, label = 3, "mittel"
    elif n >= 1:
        stufe, label = 2, "niedrig"
    else:
        stufe, label = 1, "sehr niedrig"
    return {
        "agent": agent, "rule_id": rule_id,
        "alerts": alerts, "incidents": incidents,
        "eintrittswahrscheinlichkeit_stufe": stufe,
        "eintrittswahrscheinlichkeit_label": label,
        "basis": "empirisch aus SOC-Incident-/Alarm-Frequenz",
    }


# ── SLA-/KPI-Management (#1315) ─────────────────────────────────────────────

_SLA_DEFAULTS = {"critical": (15, 240), "high": (30, 480), "medium": (60, 1440), "low": (240, 4320)}


def seed_sla(db_path: Path) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        have = {r["severity"] for r in con.execute("SELECT severity FROM soc_sla").fetchall()}
        for sev, (ack, res) in _SLA_DEFAULTS.items():
            if sev not in have:
                con.execute("INSERT INTO soc_sla(severity, ack_minutes, resolve_minutes) VALUES(?,?,?)",
                            (sev, ack, res))
        con.commit()
    finally:
        con.close()


def list_sla(db_path: Path) -> dict[str, dict[str, int]]:
    seed_sla(db_path)
    con = _connect(db_path)
    try:
        return {r["severity"]: {"ack_minutes": r["ack_minutes"], "resolve_minutes": r["resolve_minutes"]}
                for r in con.execute("SELECT * FROM soc_sla").fetchall()}
    finally:
        con.close()


def save_sla(db_path: Path, severity: str, ack_minutes: int, resolve_minutes: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("INSERT INTO soc_sla(severity, ack_minutes, resolve_minutes) VALUES(?,?,?) "
                    "ON CONFLICT(severity) DO UPDATE SET ack_minutes=excluded.ack_minutes, "
                    "resolve_minutes=excluded.resolve_minutes",
                    (severity, int(ack_minutes), int(resolve_minutes)))
        con.commit()
    finally:
        con.close()


def _minutes_between(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    from datetime import datetime
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        return (datetime.strptime(b[:19], fmt) - datetime.strptime(a[:19], fmt)).total_seconds() / 60.0
    except ValueError:
        return None


def sla_kpis(db_path: Path) -> dict[str, Any]:
    sla = list_sla(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT severity, created_at, acknowledged_at, resolved_at FROM soc_incidents").fetchall()
    finally:
        con.close()
    mtta, mttr = [], []
    resolved = breached = within = 0
    for r in rows:
        m = _minutes_between(r["created_at"], r["acknowledged_at"])
        if m is not None:
            mtta.append(m)
        mr = _minutes_between(r["created_at"], r["resolved_at"])
        if mr is not None:
            mttr.append(mr)
            resolved += 1
            target = sla.get((r["severity"] or "medium"), {}).get("resolve_minutes")
            if target and mr > target:
                breached += 1
            else:
                within += 1

    def _avg(xs):
        return round(sum(xs) / len(xs) / 60.0, 1) if xs else None  # Stunden
    return {
        "mtta_hours": _avg(mtta),
        "mttr_hours": _avg(mttr),
        "resolved": resolved,
        "sla_breached": breached,
        "sla_within": within,
        "sla_compliance": round(within / resolved, 3) if resolved else None,
        "sla_config": sla,
    }


def incident_sla(db_path: Path, incident: dict) -> dict[str, Any]:
    """SLA-Status eines einzelnen Incidents."""
    sla = list_sla(db_path).get((incident.get("severity") or "medium"), {})
    mtta = _minutes_between(incident.get("created_at"), incident.get("acknowledged_at"))
    mttr = _minutes_between(incident.get("created_at"), incident.get("resolved_at"))
    ack_target = sla.get("ack_minutes")
    res_target = sla.get("resolve_minutes")
    # Bei offenem Incident: laufende Zeit gegen Ziel
    from datetime import datetime, timezone
    now_min = None
    if not incident.get("resolved_at") and incident.get("created_at"):
        now_min = _minutes_between(incident["created_at"],
                                   datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    res_breached = (mttr is not None and res_target and mttr > res_target) or \
                   (mttr is None and now_min is not None and res_target and now_min > res_target)
    return {
        "ack_minutes": round(mtta, 1) if mtta is not None else None,
        "resolve_minutes": round(mttr, 1) if mttr is not None else None,
        "ack_target": ack_target, "resolve_target": res_target,
        "resolve_breached": bool(res_breached),
    }


def kpis(db_path: Path) -> dict[str, Any]:
    from soc.constants import INCIDENT_OPEN_STATES
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        total_alerts = con.execute("SELECT COUNT(*) c FROM soc_alerts").fetchone()["c"]
        new_alerts = con.execute("SELECT COUNT(*) c FROM soc_alerts WHERE status='new'").fetchone()["c"]
        fp = con.execute("SELECT COUNT(*) c FROM soc_alerts WHERE status='false_positive'").fetchone()["c"]
        vuln = con.execute("SELECT COUNT(*) c FROM soc_alerts WHERE kind='vulnerability'").fetchone()["c"]
        inc_rows = con.execute("SELECT status, COUNT(*) c FROM soc_incidents GROUP BY status").fetchall()
        by_status = {r["status"]: r["c"] for r in inc_rows}
        open_inc = sum(c for s, c in by_status.items() if s in INCIDENT_OPEN_STATES)
        sev = con.execute(
            "SELECT severity, COUNT(*) c FROM soc_alerts WHERE status IN ('new','in_review','confirmed') GROUP BY severity"
        ).fetchall()
        return {
            "alerts_total": total_alerts,
            "alerts_new": new_alerts,
            "alerts_false_positive": fp,
            "alerts_vulnerability": vuln,
            "fp_rate": round(fp / total_alerts, 3) if total_alerts else 0.0,
            "incidents_open": open_inc,
            "incidents_by_status": by_status,
            "open_by_severity": {r["severity"]: r["c"] for r in sev},
        }
    finally:
        con.close()


# ── Regelwerk-Cache (#1348) ─────────────────────────────────────────────────

def upsert_rule(db_path: Path, rule: dict[str, Any], *, con: Any | None = None) -> None:
    """Idempotenter Upsert einer einzelnen Regel in den Cache."""
    own = con is None
    if own:
        ensure_db(db_path)
        con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO soc_rules(rule_id, level, description, groups, mitre, filename, status, synced_at)
               VALUES(?,?,?,?,?,?,?,aics_now())
               ON CONFLICT(rule_id) DO UPDATE SET level=excluded.level,
                 description=excluded.description, groups=excluded.groups,
                 mitre=excluded.mitre, filename=excluded.filename,
                 status=excluded.status, synced_at=aics_now()""",
            (int(rule.get("id", 0)), int(rule.get("level", 0)), rule.get("description", ""),
             json.dumps(rule.get("groups", [])), json.dumps(rule.get("mitre", [])),
             rule.get("filename", ""), rule.get("status", "")))
        if own:
            con.commit()
    finally:
        if own:
            con.close()


def replace_rules(db_path: Path, rules: list[dict[str, Any]]) -> int:
    """Ersetzt den kompletten Regelwerk-Cache atomar (Truncate + Bulk-Insert).

    Per „Regelwerk laden": gelöschte/deaktivierte Regeln verschwinden so aus dem
    Cache. Aktualisiert zugleich den Sync-Zeitstempel. Returns #Regeln.
    """
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_rules")
        for r in rules:
            upsert_rule(db_path, r, con=con)
        _set_rules_sync(con, status="ok", count=len(rules), error="")
        con.commit()
        return len(rules)
    finally:
        con.close()


def _set_rules_sync(con: Any, *, status: str, count: int, error: str) -> None:
    con.execute(
        """INSERT INTO soc_rules_sync(id, last_run_at, last_status, last_count, last_error)
           VALUES(1, aics_now(), ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET last_run_at=aics_now(),
             last_status=excluded.last_status, last_count=excluded.last_count,
             last_error=excluded.last_error""",
        (status, int(count), error))


def record_rules_sync_error(db_path: Path, error: str) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        _set_rules_sync(con, status="error", count=0, error=error)
        con.commit()
    finally:
        con.close()


def rules_sync_state(db_path: Path) -> dict[str, Any]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        r = con.execute("SELECT * FROM soc_rules_sync WHERE id=1").fetchone()
        return _row(r) or {"last_run_at": None, "last_status": "", "last_count": 0, "last_error": ""}
    finally:
        con.close()


def _rule_to_dict(r: Any) -> dict[str, Any]:
    d = dict(r)
    d["id"] = d.pop("rule_id")
    for k in ("groups", "mitre"):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except (TypeError, ValueError):
            d[k] = []
    return d


def list_rules(db_path: Path, *, group: str | None = None, mitre: str | None = None,
               min_level: int | None = None, status: str | None = None,
               q: str | None = None, limit: int = 2000) -> dict[str, Any]:
    """Read-only Such-/Filtersicht auf den Regelwerk-Cache.

    Filter: ``group`` (Substring in groups), ``mitre`` (Substring in ATT&CK-IDs),
    ``min_level``, ``status``, ``q`` (Volltext über Beschreibung/ID/Datei).
    JSON-Spalten werden als Text-LIKE gefiltert (genügt für Substring-Suche).
    """
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        sql = "SELECT * FROM soc_rules WHERE 1=1"
        params: list[Any] = []
        if group:
            sql += " AND groups LIKE ?"; params.append(f"%{group}%")
        if mitre:
            sql += " AND mitre LIKE ?"; params.append(f"%{mitre}%")
        if min_level is not None:
            sql += " AND level >= ?"; params.append(int(min_level))
        if status:
            sql += " AND status = ?"; params.append(status)
        if q:
            sql += (" AND (LOWER(description) LIKE LOWER(?) OR LOWER(filename) LIKE LOWER(?)"
                    " OR CAST(rule_id AS TEXT) LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        sql += " ORDER BY level DESC, rule_id ASC LIMIT ?"
        params.append(int(limit))
        rows = [_rule_to_dict(r) for r in con.execute(sql, params).fetchall()]
        total = con.execute("SELECT COUNT(*) c FROM soc_rules").fetchone()["c"]
        return {"rules": rows, "total": total, "shown": len(rows),
                "sync": rules_sync_state(db_path)}
    finally:
        con.close()
