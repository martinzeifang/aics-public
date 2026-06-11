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
import sqlite3
from pathlib import Path
from typing import Any

from security_utils import safe_generated_file, workspace_root_from
from shared.db_security import connect_sqlite
from soc.constants import severity_from_level

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-32000;

CREATE TABLE IF NOT EXISTS soc_connection (
    id             INTEGER PRIMARY KEY,
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
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
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
    id              INTEGER PRIMARY KEY,
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
    source          TEXT NOT NULL DEFAULT 'agent',         -- agent | manuell (#1311)
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
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(agent_id, agent_name)
);

CREATE TABLE IF NOT EXISTS soc_alerts (
    id            INTEGER PRIMARY KEY,
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
    ingested_at   TEXT DEFAULT (datetime('now'))
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
    id            INTEGER PRIMARY KEY,
    rule_id       TEXT NOT NULL DEFAULT '',
    agent_glob    TEXT NOT NULL DEFAULT '',                -- fnmatch-Pattern auf agent_name
    srcip         TEXT NOT NULL DEFAULT '',
    reason        TEXT NOT NULL DEFAULT '',
    created_by    TEXT NOT NULL DEFAULT '',
    expires_at    TEXT,                                    -- NULL = kein Ablauf (zu vermeiden)
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS soc_incidents (
    id              INTEGER PRIMARY KEY,
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
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_soc_incidents_status ON soc_incidents(status);

CREATE TABLE IF NOT EXISTS soc_incident_alerts (
    incident_id   INTEGER NOT NULL,
    alert_uid     TEXT NOT NULL,
    PRIMARY KEY (incident_id, alert_uid)
);

CREATE TABLE IF NOT EXISTS soc_incident_timeline (
    id            INTEGER PRIMARY KEY,
    incident_id   INTEGER NOT NULL,
    ts            TEXT DEFAULT (datetime('now')),
    actor         TEXT NOT NULL DEFAULT '',
    event         TEXT NOT NULL DEFAULT '',
    detail        TEXT NOT NULL DEFAULT '',
    prev_hash     TEXT NOT NULL DEFAULT '',
    entry_hash    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_soc_timeline_incident ON soc_incident_timeline(incident_id);

CREATE TABLE IF NOT EXISTS soc_meldetracks (
    id            INTEGER PRIMARY KEY,
    incident_id   INTEGER NOT NULL,
    regime        TEXT NOT NULL,                           -- dsgvo|nis2|cra|aiact|dora
    legal         TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'offen',           -- offen|in_arbeit|gemeldet|abgeschlossen
    deadlines_json TEXT NOT NULL DEFAULT '[]',             -- [{key,label,due_at,done}]
    target_ref    TEXT NOT NULL DEFAULT '',                -- z.B. dsgvo_datenpannen.id
    notiz         TEXT NOT NULL DEFAULT '',
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(incident_id, regime)
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path = safe_generated_file(db_path, workspace_root_from(Path(__file__)))
    con = connect_sqlite(db_path, anchor=Path(__file__))
    con.row_factory = sqlite3.Row
    con.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")
    return con


def ensure_db(db_path: Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        # Migrationen für Bestands-DBs
        def _addcol(table, col, ddl):
            cols = {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
            if col not in cols:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        _addcol("soc_alerts", "kind", "kind TEXT NOT NULL DEFAULT 'alert'")            # #1294
        _addcol("soc_incidents", "closed_reason", "closed_reason TEXT NOT NULL DEFAULT ''")  # #1296
        _addcol("soc_incidents", "closed_at", "closed_at TEXT")
        _addcol("soc_incidents", "closed_by", "closed_by TEXT NOT NULL DEFAULT ''")
        _addcol("soc_connection", "manager_url", "manager_url TEXT NOT NULL DEFAULT ''")      # #1300
        _addcol("soc_connection", "manager_user", "manager_user TEXT NOT NULL DEFAULT ''")
        _addcol("soc_connection", "manager_secret_enc", "manager_secret_enc TEXT NOT NULL DEFAULT ''")
        _addcol("soc_alerts", "asset_id", "asset_id INTEGER")                                 # #1305
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


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r is not None else None


# ── Verbindung (#1261) ──────────────────────────────────────────────────────

def save_connection(db_path: Path, *, name: str = "default", modus: str = "pull",
                    url: str = "", username: str = "", secret: str | None = None,
                    verify_tls: bool = True, index_pattern: str = "wazuh-alerts-*",
                    min_level: int = 7, push_token: str | None = None,
                    manager_url: str | None = None, manager_user: str | None = None,
                    manager_secret: str | None = None, enabled: bool = True) -> int:
    """Speichert/aktualisiert eine Verbindung; Secrets verschlüsselt at-rest."""
    from shared.crypto_at_rest import encrypt_field
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        existing = con.execute("SELECT * FROM soc_connection WHERE name=?", (name,)).fetchone()
        secret_enc = existing["secret_enc"] if existing else ""
        if secret is not None and secret != "":
            secret_enc = encrypt_field(secret)
        token_enc = existing["push_token_enc"] if existing else ""
        if push_token is not None and push_token != "":
            token_enc = encrypt_field(push_token)
        mgr_secret_enc = existing["manager_secret_enc"] if existing else ""
        if manager_secret is not None and manager_secret != "":
            mgr_secret_enc = encrypt_field(manager_secret)
        mgr_url = manager_url if manager_url is not None else (existing["manager_url"] if existing else "")
        mgr_user = manager_user if manager_user is not None else (existing["manager_user"] if existing else "")
        if existing:
            con.execute(
                """UPDATE soc_connection SET modus=?, url=?, username=?, secret_enc=?,
                   verify_tls=?, index_pattern=?, min_level=?, push_token_enc=?,
                   manager_url=?, manager_user=?, manager_secret_enc=?, enabled=?,
                   updated_at=datetime('now') WHERE name=?""",
                (modus, url, username, secret_enc, 1 if verify_tls else 0, index_pattern,
                 int(min_level), token_enc, mgr_url, mgr_user, mgr_secret_enc,
                 1 if enabled else 0, name))
            cid = existing["id"]
        else:
            cur = con.execute(
                """INSERT INTO soc_connection(name, modus, url, username, secret_enc,
                   verify_tls, index_pattern, min_level, push_token_enc,
                   manager_url, manager_user, manager_secret_enc, enabled)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (name, modus, url, username, secret_enc, 1 if verify_tls else 0,
                 index_pattern, int(min_level), token_enc, mgr_url, mgr_user,
                 mgr_secret_enc, 1 if enabled else 0))
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
               VALUES(?,?,?,datetime('now'),?,?)
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
               raw_json, group_key, status, firmen_id, asset_id)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (alert["alert_uid"], alert.get("rule_id", ""), int(alert.get("rule_level", 0)),
             alert.get("severity") or severity_from_level(alert.get("rule_level")),
             alert.get("kind", "alert"),
             alert.get("description", ""), json.dumps(alert.get("groups", [])),
             json.dumps(alert.get("mitre", {})), alert.get("agent_id", ""),
             alert.get("agent_name", ""), alert.get("srcip", ""), alert.get("location", ""),
             alert.get("full_log", ""), alert.get("event_ts", ""),
             json.dumps(alert.get("raw_json", {})), alert.get("group_key", ""),
             alert.get("status", "new"), alert.get("firmen_id"), alert.get("asset_id")))
        # Gruppe aktualisieren
        gk = alert.get("group_key", "")
        if gk:
            con.execute(
                """INSERT INTO soc_alert_groups(group_key, rule_id, description, severity,
                   agent_name, srcip, count, first_seen, last_seen, status)
                   VALUES(?,?,?,?,?,?,1,?,?,'new')
                   ON CONFLICT(group_key) DO UPDATE SET count=count+1,
                     last_seen=excluded.last_seen,
                     severity=CASE WHEN excluded.severity=severity THEN severity ELSE excluded.severity END""",
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
        con.execute("UPDATE soc_alerts SET status=? WHERE alert_uid=?", (status, alert_uid))
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


def _alert_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    for k in ("groups", "mitre", "raw_json", "analysis_json"):
        try:
            d[k] = json.loads(d.get(k) or ("[]" if k == "groups" else "{}"))
        except Exception:
            d[k] = [] if k == "groups" else {}
    return d


# ── Suppressions (#1268) ────────────────────────────────────────────────────

def list_suppressions(db_path: Path, *, only_enabled: bool = False) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = "SELECT * FROM soc_suppressions"
        if only_enabled:
            q += " WHERE enabled=1 AND (expires_at IS NULL OR expires_at > datetime('now'))"
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
               VALUES(?,?,?,?,?,?)""",
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
                con.execute(f"UPDATE soc_assets SET {sets}, updated_at=datetime('now') WHERE id=?",
                            (*present.values(), row["id"]))
            aid = row["id"]
        else:
            cols = dict(agent_id=asset.get("agent_id", ""), agent_name=asset.get("agent_name", ""), **present)
            ph = ",".join("?" * len(cols))
            cur = con.execute(f"INSERT INTO soc_assets({','.join(cols)}) VALUES({ph})", tuple(cols.values()))
            aid = int(cur.lastrowid)
        con.commit()
        return aid
    finally:
        con.close()


_SEV_WEIGHT = {"critical": 8, "high": 4, "medium": 2, "low": 1}


def asset_risk_score(db_path: Path, asset_id: int, *, kritikalitaet: int | None = None,
                     con: sqlite3.Connection | None = None) -> dict[str, Any]:
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
        con.execute("UPDATE soc_incidents SET asset_id=?, updated_at=datetime('now') WHERE id=?",
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


def _asset_to_dict(r: sqlite3.Row) -> dict[str, Any]:
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
               owner, beschreibung, mitre, firmen_id) VALUES(?,?,?,?,?,?,?,?,?)""",
            (titel, severity, klassifikation, asset_id, agent_name, owner, beschreibung,
             json.dumps(mitre or {}), firmen_id))
        iid = int(cur.lastrowid)
        for uid in (alert_uids or []):
            con.execute("INSERT OR IGNORE INTO soc_incident_alerts(incident_id, alert_uid) VALUES(?,?)",
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
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE soc_incidents SET status='closed', closed_reason=?, closed_by=?,
               closed_at=datetime('now'), updated_at=datetime('now') WHERE id=?""",
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
        con.execute(f"UPDATE soc_incidents SET {', '.join(sets)}, updated_at=datetime('now') WHERE id=?", params)
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
        con.execute("UPDATE soc_incidents SET status=?, updated_at=datetime('now') WHERE id=?",
                    (status, incident_id))
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
        con.execute("UPDATE soc_incidents SET meta_json=?, updated_at=datetime('now') WHERE id=?",
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
        con.execute("UPDATE soc_incidents SET meta_json=?, updated_at=datetime('now') WHERE id=?",
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


def _incident_to_dict(r: sqlite3.Row) -> dict[str, Any]:
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
                 deadlines_json=excluded.deadlines_json, updated_at=datetime('now')""",
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
        con.execute(f"UPDATE soc_meldetracks SET {', '.join(sets)}, updated_at=datetime('now') WHERE id=?", params)
        con.commit()
    finally:
        con.close()


# ── KPIs (Dashboard #1275) ──────────────────────────────────────────────────

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
            "SELECT AVG((julianday(closed_at)-julianday(created_at))*24.0) m "
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
