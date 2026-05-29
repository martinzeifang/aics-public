"""AI Act module – SQLite data access."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from shared.db_security import connect_sqlite


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-32000;

CREATE TABLE IF NOT EXISTS ai_act_projekte (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    organisation TEXT NOT NULL DEFAULT '',
    produkt     TEXT NOT NULL DEFAULT '',
    beschreibung TEXT NOT NULL DEFAULT '',
    meta_json   TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_act_bewertungen (
    id           INTEGER PRIMARY KEY,
    projekt_name TEXT NOT NULL,
    anforderung_id TEXT NOT NULL,
    bewertung    INTEGER NOT NULL DEFAULT 0,
    kommentar    TEXT NOT NULL DEFAULT '',
    massnahme    TEXT NOT NULL DEFAULT '',
    updated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, anforderung_id)
);

CREATE INDEX IF NOT EXISTS idx_aia_bew_projekt ON ai_act_bewertungen(projekt_name);

CREATE TABLE IF NOT EXISTS ai_act_overlay_checks (
    id            INTEGER PRIMARY KEY,
    projekt_name  TEXT NOT NULL,
    overlay_id    TEXT NOT NULL,
    status        INTEGER NOT NULL DEFAULT 0,
    kommentar     TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, overlay_id)
);

CREATE INDEX IF NOT EXISTS idx_aia_overlay_projekt ON ai_act_overlay_checks(projekt_name);

-- ───────────────────────────────────────────────────────────────────
-- Sprint γ Phase A: AI Act Pflicht-Doku-Manager (Issue #583)
-- ───────────────────────────────────────────────────────────────────

-- A1: Technische Dokumentation (Art. 11 + Annex IV)
CREATE TABLE IF NOT EXISTS aiact_system_doku (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    system_name     TEXT NOT NULL DEFAULT '',
    version         TEXT NOT NULL DEFAULT '',
    provider        TEXT NOT NULL DEFAULT '',
    intended_purpose TEXT NOT NULL DEFAULT '',
    architecture    TEXT NOT NULL DEFAULT '',          -- z.B. "Transformer-LLM, 7B Params"
    training_methodology TEXT NOT NULL DEFAULT '',
    computational_resources TEXT NOT NULL DEFAULT '',  -- z.B. "8x A100, 14 Tage"
    performance_metrics_json TEXT NOT NULL DEFAULT '[]',
    test_methodology TEXT NOT NULL DEFAULT '',
    cybersecurity_measures TEXT NOT NULL DEFAULT '',
    accuracy_robustness TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- A2: Data Governance (Art. 10)
CREATE TABLE IF NOT EXISTS aiact_data_governance (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    training_data_source TEXT NOT NULL DEFAULT '',
    training_data_size  TEXT NOT NULL DEFAULT '',
    validation_data_split TEXT NOT NULL DEFAULT '',
    test_data_split    TEXT NOT NULL DEFAULT '',
    data_collection_method TEXT NOT NULL DEFAULT '',
    data_labelling_method TEXT NOT NULL DEFAULT '',
    bias_assessment    TEXT NOT NULL DEFAULT '',
    bias_mitigation    TEXT NOT NULL DEFAULT '',
    data_quality_checks TEXT NOT NULL DEFAULT '',
    personal_data_used INTEGER NOT NULL DEFAULT 0,    -- 0=nein, 1=ja
    legal_basis_gdpr   TEXT NOT NULL DEFAULT '',      -- Art. 6 DSGVO falls personal_data
    representativeness TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- A3: Risk-Management-System (Art. 9)
CREATE TABLE IF NOT EXISTS aiact_risk_management (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    risk_id         TEXT NOT NULL,                    -- z.B. AIA-R-001
    titel           TEXT NOT NULL,
    lifecycle_phase TEXT NOT NULL DEFAULT 'design',   -- design | development | deployment | monitoring
    risk_category   TEXT NOT NULL DEFAULT 'safety',   -- safety | fundamental-rights | bias | security | other
    likelihood      TEXT NOT NULL DEFAULT 'mittel',
    severity        TEXT NOT NULL DEFAULT 'mittel',
    risk_score      INTEGER NOT NULL DEFAULT 0,
    mitigation      TEXT NOT NULL DEFAULT '',
    residual_risk   TEXT NOT NULL DEFAULT 'akzeptabel',
    status          TEXT NOT NULL DEFAULT 'offen',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, risk_id)
);
CREATE INDEX IF NOT EXISTS idx_aiact_rm_projekt ON aiact_risk_management(projekt_name);

-- A4: Human-Oversight (Art. 14)
CREATE TABLE IF NOT EXISTS aiact_human_oversight (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    oversight_mode  TEXT NOT NULL DEFAULT 'human-in-the-loop', -- in-the-loop | on-the-loop | in-command
    oversight_persons TEXT NOT NULL DEFAULT '[]',     -- JSON-Liste (Rolle, Person, Schulung)
    intervention_mechanisms TEXT NOT NULL DEFAULT '', -- z.B. "Stop-Button, Manual-Override"
    monitoring_interface TEXT NOT NULL DEFAULT '',
    output_interpretation_aids TEXT NOT NULL DEFAULT '', -- Erklärungen, Confidence-Scores
    abnormal_behavior_detection TEXT NOT NULL DEFAULT '',
    training_program TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- A5: Post-Market-Monitoring + Incident-Reporting (Art. 72-73)
CREATE TABLE IF NOT EXISTS aiact_post_market_monitoring (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    monitoring_plan TEXT NOT NULL DEFAULT '',
    performance_metrics TEXT NOT NULL DEFAULT '',
    drift_detection TEXT NOT NULL DEFAULT '',
    user_feedback_channel TEXT NOT NULL DEFAULT '',
    incident_threshold TEXT NOT NULL DEFAULT '',     -- Wann melden? z.B. "Genauigkeitsabfall >5%"
    market_surveillance_contact TEXT NOT NULL DEFAULT '', -- nationale Marktaufsicht (BNetzA in DE)
    serious_incident_reporting_sla TEXT NOT NULL DEFAULT '15 Tage', -- Art. 73 (2): 15 Tage
    incident_log_json TEXT NOT NULL DEFAULT '[]',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    con = connect_sqlite(db_path, anchor=Path(__file__))
    con.row_factory = sqlite3.Row
    con.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")
    return con


def ensure_db(db_path: Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def save_projekt(
    db_path: Path,
    *,
    name: str,
    organisation: str = "",
    produkt: str = "",
    beschreibung: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO ai_act_projekte(name, organisation, produkt, beschreibung, meta_json, updated_at)
            VALUES(?,?,?,?,?,datetime('now'))
            ON CONFLICT(name) DO UPDATE SET
              organisation=excluded.organisation,
              produkt=excluded.produkt,
              beschreibung=excluded.beschreibung,
              meta_json=excluded.meta_json,
              updated_at=datetime('now')
            """,
            (
                name,
                organisation,
                produkt,
                beschreibung,
                json.dumps(meta or {}, ensure_ascii=False),
            ),
        )
        con.commit()
    finally:
        con.close()


def load_projekt(db_path: Path, name: str) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM ai_act_projekte WHERE name=?", (name,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["meta"] = json.loads(d.get("meta_json", "{}") or "{}")
        except Exception:
            d["meta"] = {}
        return d
    finally:
        con.close()


def list_projekte(db_path: Path) -> list[str]:
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT name FROM ai_act_projekte ORDER BY updated_at DESC, name").fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def delete_projekt(db_path: Path, name: str) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM ai_act_bewertungen WHERE projekt_name=?", (name,))
        con.execute("DELETE FROM ai_act_projekte WHERE name=?", (name,))
        con.commit()
    finally:
        con.close()


def save_bewertung(
    db_path: Path,
    *,
    projekt_name: str,
    anforderung_id: str,
    bewertung: int,
    kommentar: str = "",
    massnahme: str = "",
) -> None:
    bew = int(bewertung)
    if bew < 0 or bew > 5:
        bew = 0
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO ai_act_bewertungen(projekt_name, anforderung_id, bewertung, kommentar, massnahme, updated_at)
            VALUES(?,?,?,?,?,datetime('now'))
            ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
              bewertung=excluded.bewertung,
              kommentar=excluded.kommentar,
              massnahme=excluded.massnahme,
              updated_at=datetime('now')
            """,
            (projekt_name, anforderung_id, bew, kommentar or "", massnahme or ""),
        )
        con.commit()
    finally:
        con.close()


def load_bewertungen(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT * FROM ai_act_bewertungen WHERE projekt_name=?", (projekt_name,)).fetchall()
        return {str(r["anforderung_id"]): dict(r) for r in rows}
    finally:
        con.close()


def upsert_overlay_check(
    db_path: Path,
    *,
    projekt_name: str,
    overlay_id: str,
    status: int,
    kommentar: str = "",
    evidence: list[dict[str, Any]] | None = None,
) -> None:
    import json

    st = int(status)
    if st < 0 or st > 5:
        st = 0
    ev_json = json.dumps(evidence or [], ensure_ascii=False)
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO ai_act_overlay_checks(projekt_name, overlay_id, status, kommentar, evidence_json, updated_at)
            VALUES(?,?,?,?,?,datetime('now'))
            ON CONFLICT(projekt_name, overlay_id) DO UPDATE SET
              status=excluded.status,
              kommentar=excluded.kommentar,
              evidence_json=excluded.evidence_json,
              updated_at=datetime('now')
            """,
            (projekt_name, overlay_id, st, kommentar or "", ev_json),
        )
        con.commit()
    finally:
        con.close()


def load_overlay_checks(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    import json

    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM ai_act_overlay_checks WHERE projekt_name=?",
            (projekt_name,),
        ).fetchall()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            d = dict(r)
            try:
                d["evidence"] = json.loads(d.get("evidence_json", "[]") or "[]")
            except Exception:
                d["evidence"] = []
            out[str(d.get("overlay_id"))] = d
        return out
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════════════════
# Sprint γ Phase A — AI Act Pflicht-Doku-Helper (Issue #583)
# ═══════════════════════════════════════════════════════════════════════════

import json as _json


def _aiact_jdumps(v):
    return _json.dumps(v or [], ensure_ascii=False)


def _aiact_jloads(s):
    try: return _json.loads(s or '[]')
    except Exception: return []


# ─── A1: System-Doku (1:1) ─────────────────────────────────────────────────

def load_system_doku(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM aiact_system_doku WHERE projekt_name=?", (projekt_name,)).fetchone()
        if not row: return None
        d = dict(row)
        d['performance_metrics'] = _aiact_jloads(d.get('performance_metrics_json', '[]'))
        return d
    finally:
        con.close()


def save_system_doku(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO aiact_system_doku (projekt_name, system_name, version, provider, intended_purpose,
                       architecture, training_methodology, computational_resources, performance_metrics_json,
                       test_methodology, cybersecurity_measures, accuracy_robustness, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(projekt_name) DO UPDATE SET
                 system_name=excluded.system_name, version=excluded.version, provider=excluded.provider,
                 intended_purpose=excluded.intended_purpose, architecture=excluded.architecture,
                 training_methodology=excluded.training_methodology,
                 computational_resources=excluded.computational_resources,
                 performance_metrics_json=excluded.performance_metrics_json,
                 test_methodology=excluded.test_methodology,
                 cybersecurity_measures=excluded.cybersecurity_measures,
                 accuracy_robustness=excluded.accuracy_robustness,
                 notizen=excluded.notizen, updated_at=datetime('now')""",
            (projekt_name, data.get('system_name', ''), data.get('version', ''), data.get('provider', ''),
             data.get('intended_purpose', ''), data.get('architecture', ''),
             data.get('training_methodology', ''), data.get('computational_resources', ''),
             _aiact_jdumps(data.get('performance_metrics')),
             data.get('test_methodology', ''), data.get('cybersecurity_measures', ''),
             data.get('accuracy_robustness', ''), data.get('notizen', '')))
        con.commit()
    finally:
        con.close()


# ─── A2: Data-Governance (1:1) ─────────────────────────────────────────────

def load_data_governance(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM aiact_data_governance WHERE projekt_name=?", (projekt_name,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def save_data_governance(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO aiact_data_governance (projekt_name, training_data_source, training_data_size,
                       validation_data_split, test_data_split, data_collection_method, data_labelling_method,
                       bias_assessment, bias_mitigation, data_quality_checks, personal_data_used,
                       legal_basis_gdpr, representativeness, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(projekt_name) DO UPDATE SET
                 training_data_source=excluded.training_data_source,
                 training_data_size=excluded.training_data_size,
                 validation_data_split=excluded.validation_data_split,
                 test_data_split=excluded.test_data_split,
                 data_collection_method=excluded.data_collection_method,
                 data_labelling_method=excluded.data_labelling_method,
                 bias_assessment=excluded.bias_assessment,
                 bias_mitigation=excluded.bias_mitigation,
                 data_quality_checks=excluded.data_quality_checks,
                 personal_data_used=excluded.personal_data_used,
                 legal_basis_gdpr=excluded.legal_basis_gdpr,
                 representativeness=excluded.representativeness,
                 notizen=excluded.notizen, updated_at=datetime('now')""",
            (projekt_name, data.get('training_data_source', ''), data.get('training_data_size', ''),
             data.get('validation_data_split', ''), data.get('test_data_split', ''),
             data.get('data_collection_method', ''), data.get('data_labelling_method', ''),
             data.get('bias_assessment', ''), data.get('bias_mitigation', ''),
             data.get('data_quality_checks', ''), int(bool(data.get('personal_data_used'))),
             data.get('legal_basis_gdpr', ''), data.get('representativeness', ''),
             data.get('notizen', '')))
        con.commit()
    finally:
        con.close()


# ─── A3: Risk-Management (1:n) ─────────────────────────────────────────────

_AIACT_SEV = {'niedrig': 1, 'mittel': 2, 'hoch': 3, 'kritisch': 4}
_AIACT_LIK = {'unwahrscheinlich': 1, 'mittel': 2, 'wahrscheinlich': 3, 'sehr-wahrscheinlich': 4}


def _calc_aiact_risk_score(severity: str, likelihood: str) -> int:
    return _AIACT_SEV.get(severity, 2) * _AIACT_LIK.get(likelihood, 2)


def list_aiact_risks(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path); con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM aiact_risk_management WHERE projekt_name=? ORDER BY risk_score DESC",
            (projekt_name,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_aiact_risk(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('id') and not data.get('risk_id'):
        raise ValueError("'risk_id' ist Pflicht")
    score = _calc_aiact_risk_score(data.get('severity', 'mittel'), data.get('likelihood', 'mittel'))
    con = _connect(db_path)
    try:
        rid = data.get('id')
        if rid:
            con.execute(
                """UPDATE aiact_risk_management SET titel=?, lifecycle_phase=?, risk_category=?,
                          likelihood=?, severity=?, risk_score=?, mitigation=?, residual_risk=?,
                          status=?, notizen=?, updated_at=datetime('now') WHERE id=?""",
                (data.get('titel', ''), data.get('lifecycle_phase', 'design'),
                 data.get('risk_category', 'safety'), data.get('likelihood', 'mittel'),
                 data.get('severity', 'mittel'), score, data.get('mitigation', ''),
                 data.get('residual_risk', 'akzeptabel'), data.get('status', 'offen'),
                 data.get('notizen', ''), int(rid)))
            con.commit(); return int(rid)
        cur = con.execute(
            """INSERT INTO aiact_risk_management (projekt_name, risk_id, titel, lifecycle_phase,
                  risk_category, likelihood, severity, risk_score, mitigation, residual_risk, status, notizen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (projekt_name, data['risk_id'], data.get('titel', ''),
             data.get('lifecycle_phase', 'design'), data.get('risk_category', 'safety'),
             data.get('likelihood', 'mittel'), data.get('severity', 'mittel'), score,
             data.get('mitigation', ''), data.get('residual_risk', 'akzeptabel'),
             data.get('status', 'offen'), data.get('notizen', '')))
        con.commit(); return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_aiact_risk(db_path: Path, risk_id: int) -> None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        con.execute("DELETE FROM aiact_risk_management WHERE id=?", (int(risk_id),)); con.commit()
    finally:
        con.close()


# ─── A4: Human-Oversight (1:1) ─────────────────────────────────────────────

def load_human_oversight(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM aiact_human_oversight WHERE projekt_name=?", (projekt_name,)).fetchone()
        if not row: return None
        d = dict(row)
        d['oversight_persons'] = _aiact_jloads(d.get('oversight_persons', '[]'))
        return d
    finally:
        con.close()


def save_human_oversight(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO aiact_human_oversight (projekt_name, oversight_mode, oversight_persons,
                       intervention_mechanisms, monitoring_interface, output_interpretation_aids,
                       abnormal_behavior_detection, training_program, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(projekt_name) DO UPDATE SET
                 oversight_mode=excluded.oversight_mode, oversight_persons=excluded.oversight_persons,
                 intervention_mechanisms=excluded.intervention_mechanisms,
                 monitoring_interface=excluded.monitoring_interface,
                 output_interpretation_aids=excluded.output_interpretation_aids,
                 abnormal_behavior_detection=excluded.abnormal_behavior_detection,
                 training_program=excluded.training_program, notizen=excluded.notizen,
                 updated_at=datetime('now')""",
            (projekt_name, data.get('oversight_mode', 'human-in-the-loop'),
             _aiact_jdumps(data.get('oversight_persons')),
             data.get('intervention_mechanisms', ''), data.get('monitoring_interface', ''),
             data.get('output_interpretation_aids', ''), data.get('abnormal_behavior_detection', ''),
             data.get('training_program', ''), data.get('notizen', '')))
        con.commit()
    finally:
        con.close()


# ─── A5: Post-Market-Monitoring (1:1) ──────────────────────────────────────

def load_pmm(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM aiact_post_market_monitoring WHERE projekt_name=?", (projekt_name,)).fetchone()
        if not row: return None
        d = dict(row)
        d['incident_log'] = _aiact_jloads(d.get('incident_log_json', '[]'))
        return d
    finally:
        con.close()


def save_pmm(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO aiact_post_market_monitoring (projekt_name, monitoring_plan, performance_metrics,
                       drift_detection, user_feedback_channel, incident_threshold, market_surveillance_contact,
                       serious_incident_reporting_sla, incident_log_json, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(projekt_name) DO UPDATE SET
                 monitoring_plan=excluded.monitoring_plan, performance_metrics=excluded.performance_metrics,
                 drift_detection=excluded.drift_detection,
                 user_feedback_channel=excluded.user_feedback_channel,
                 incident_threshold=excluded.incident_threshold,
                 market_surveillance_contact=excluded.market_surveillance_contact,
                 serious_incident_reporting_sla=excluded.serious_incident_reporting_sla,
                 incident_log_json=excluded.incident_log_json, notizen=excluded.notizen,
                 updated_at=datetime('now')""",
            (projekt_name, data.get('monitoring_plan', ''), data.get('performance_metrics', ''),
             data.get('drift_detection', ''), data.get('user_feedback_channel', ''),
             data.get('incident_threshold', ''), data.get('market_surveillance_contact', ''),
             data.get('serious_incident_reporting_sla', '15 Tage'),
             _aiact_jdumps(data.get('incident_log')), data.get('notizen', '')))
        con.commit()
    finally:
        con.close()
