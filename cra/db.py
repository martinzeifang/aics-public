"""CRA-Modul – SQLite-Datenzugriff."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from security_utils import safe_generated_file, workspace_root_from
from shared.db_security import connect_sqlite

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-32000;

CREATE TABLE IF NOT EXISTS cra_projekte (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    unternehmen     TEXT NOT NULL DEFAULT '',
    produkt         TEXT NOT NULL DEFAULT '',
    produktklasse   TEXT NOT NULL DEFAULT 'default',
    beschreibung    TEXT NOT NULL DEFAULT '',
    berater         TEXT NOT NULL DEFAULT '',
    meta_json       TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cra_bewertungen (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    anforderung_id  TEXT NOT NULL,
    bewertung       INTEGER NOT NULL DEFAULT 0,
    kommentar       TEXT NOT NULL DEFAULT '',
    massnahme       TEXT NOT NULL DEFAULT '',
    verantwortlich  TEXT NOT NULL DEFAULT '',
    zieldatum       TEXT NOT NULL DEFAULT '',
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, anforderung_id)
);

CREATE INDEX IF NOT EXISTS idx_cb_projekt ON cra_bewertungen(projekt_name);

CREATE TABLE IF NOT EXISTS cra_anforderungen_custom (
    id              TEXT PRIMARY KEY,
    kapitel         TEXT NOT NULL DEFAULT 'IMPL',
    ref             TEXT NOT NULL DEFAULT '',
    titel           TEXT NOT NULL DEFAULT '',
    beschreibung    TEXT NOT NULL DEFAULT '',
    hinweise        TEXT NOT NULL DEFAULT '',
    gewichtung      INTEGER NOT NULL DEFAULT 1,
    ist_override    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cra_dokumente (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    doc_name        TEXT NOT NULL,
    doc_path        TEXT NOT NULL,
    doc_type        TEXT NOT NULL DEFAULT 'resource',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cd_projekt ON cra_dokumente(projekt_name);

-- OWASP Security-by-Design (Proactive Controls) checklist results
CREATE TABLE IF NOT EXISTS cra_owasp_checks (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    owasp_id        TEXT NOT NULL,
    status          INTEGER NOT NULL DEFAULT 0, -- 0..5 (aligned with BEWERTUNG_SKALA)
    kommentar       TEXT NOT NULL DEFAULT '',
    evidence_json   TEXT NOT NULL DEFAULT '[]',
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, owasp_id)
);

CREATE INDEX IF NOT EXISTS idx_coc_projekt ON cra_owasp_checks(projekt_name);

-- ───────────────────────────────────────────────────────────────────
-- Phase A: CRA-Pflicht-Doku-Manager (Issues #472-#476)
-- ───────────────────────────────────────────────────────────────────

-- C1: SBOM-Verzeichnis (pro Projekt + Release)
CREATE TABLE IF NOT EXISTS cra_sbom (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    release_version TEXT NOT NULL,
    sbom_format     TEXT NOT NULL DEFAULT 'spdx',  -- spdx | cyclonedx
    sbom_datum      TEXT NOT NULL DEFAULT (datetime('now')),
    komponenten_count INTEGER NOT NULL DEFAULT 0,
    lizenzen_json   TEXT NOT NULL DEFAULT '[]',
    quelle          TEXT NOT NULL DEFAULT '',     -- z.B. "ci-artifact:gh-run-12345" oder "manual"
    blob_path       TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, release_version, sbom_format)
);

CREATE INDEX IF NOT EXISTS idx_cra_sbom_projekt ON cra_sbom(projekt_name);

-- C2: PSIRT-Prozess-Doku (1 Eintrag pro Projekt)
CREATE TABLE IF NOT EXISTS cra_psirt (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    intake_kanal    TEXT NOT NULL DEFAULT '',
    triage_sla      TEXT NOT NULL DEFAULT '',     -- z.B. "24h"
    fix_sla_critical TEXT NOT NULL DEFAULT '',    -- z.B. "7 Tage"
    fix_sla_high    TEXT NOT NULL DEFAULT '',
    fix_sla_medium  TEXT NOT NULL DEFAULT '',
    disclosure_policy_url TEXT NOT NULL DEFAULT '',
    security_md_url TEXT NOT NULL DEFAULT '',
    psirt_contacts  TEXT NOT NULL DEFAULT '[]',   -- JSON-Liste
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- C3: Vulnerability-Handling-Tracker (offene CVEs pro Projekt)
CREATE TABLE IF NOT EXISTS cra_vuln (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    cve_id          TEXT NOT NULL,              -- z.B. CVE-2024-12345
    titel           TEXT NOT NULL DEFAULT '',
    schwere         TEXT NOT NULL DEFAULT 'unknown',  -- low|medium|high|critical|unknown
    cvss_score      REAL NOT NULL DEFAULT 0.0,
    cvss_vector     TEXT NOT NULL DEFAULT '',
    affected_component TEXT NOT NULL DEFAULT '',
    affected_versions  TEXT NOT NULL DEFAULT '',
    fixed_in_version   TEXT NOT NULL DEFAULT '',
    advisory_url    TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'open',  -- open|triaging|fixed|disclosed|wontfix
    triage_kommentar TEXT NOT NULL DEFAULT '',
    discovered_at   TEXT DEFAULT (datetime('now')),
    fixed_at        TEXT,
    disclosed_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(projekt_name, cve_id)
);

CREATE INDEX IF NOT EXISTS idx_cra_vuln_projekt ON cra_vuln(projekt_name);
CREATE INDEX IF NOT EXISTS idx_cra_vuln_status ON cra_vuln(projekt_name, status);

-- C4: Support-Period-Calculator (1 Eintrag pro Projekt)
CREATE TABLE IF NOT EXISTS cra_support_period (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    markteintritt_datum TEXT,                   -- "Date placed on market"
    support_jahre   INTEGER NOT NULL DEFAULT 5, -- CRA Default: 5 J. (oder erwartete Lebensdauer)
    eol_datum       TEXT,                       -- Berechnet oder manuell
    update_kanal    TEXT NOT NULL DEFAULT '',
    rationale       TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- C5: Threat-Model-Doku (1 Eintrag pro Projekt, mit Framework-Wahl)
CREATE TABLE IF NOT EXISTS cra_threatmodel (
    id              INTEGER PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    framework       TEXT NOT NULL DEFAULT 'STRIDE',  -- STRIDE | PASTA | LINDDUN
    scope           TEXT NOT NULL DEFAULT '',
    assets_json     TEXT NOT NULL DEFAULT '[]',
    threats_json    TEXT NOT NULL DEFAULT '[]',
    mitigations_json TEXT NOT NULL DEFAULT '[]',
    diagram_url     TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path = safe_generated_file(db_path, workspace_root_from(Path(__file__)))
    con = connect_sqlite(db_path, anchor=Path(__file__))

    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")
    return con


def ensure_db(db_path: Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


# ── Projekte ──────────────────────────────────────────────────────────────────

def save_projekt(
    db_path: Path,
    name: str,
    unternehmen: str = "",
    produkt: str = "",
    produktklasse: str = "default",
    beschreibung: str = "",
    berater: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO cra_projekte
                (name, unternehmen, produkt, produktklasse, beschreibung, berater, meta_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(name) DO UPDATE SET
                unternehmen   = excluded.unternehmen,
                produkt       = excluded.produkt,
                produktklasse = excluded.produktklasse,
                beschreibung  = excluded.beschreibung,
                berater       = excluded.berater,
                meta_json     = excluded.meta_json,
                updated_at    = datetime('now')
            """,
            (name, unternehmen, produkt, produktklasse, beschreibung, berater,
             json.dumps(meta or {}, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()


def load_projekt(db_path: Path, name: str) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        cur = con.execute("SELECT * FROM cra_projekte WHERE name=?", (name,))
        row = cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["meta"] = json.loads(d.get("meta_json", "{}"))
        except Exception:
            d["meta"] = {}
        return d
    finally:
        con.close()


def list_projekte(db_path: Path) -> list[str]:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT name FROM cra_projekte ORDER BY updated_at DESC, name"
        )
        return [r["name"] for r in cur.fetchall()]
    finally:
        con.close()


def list_projekte_fuer_kunde(db_path: Path, kunde_name: str) -> list[dict]:
    """Issue #435: Liefert volle CRA-Projekt-Records fuer einen Kunden,
    via `unternehmen`-Match."""
    if not kunde_name:
        return []
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM cra_projekte WHERE unternehmen=? ORDER BY name COLLATE NOCASE",
            (kunde_name,),
        )
        out: list[dict] = []
        for r in cur.fetchall():
            d = dict(r)
            try:
                d["meta"] = json.loads(d.get("meta_json", "{}") or "{}")
            except Exception:
                d["meta"] = {}
            out.append(d)
        return out
    finally:
        con.close()


def delete_projekt(db_path: Path, name: str) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM cra_bewertungen WHERE projekt_name=?", (name,))
        con.execute("DELETE FROM cra_dokumente   WHERE projekt_name=?", (name,))
        con.execute("DELETE FROM cra_projekte    WHERE name=?", (name,))
        con.commit()
    finally:
        con.close()


# ── Bewertungen ───────────────────────────────────────────────────────────────

def save_bewertung(
    db_path: Path,
    projekt_name: str,
    anforderung_id: str,
    bewertung: int,
    kommentar: str = "",
    massnahme: str = "",
    verantwortlich: str = "",
    zieldatum: str = "",
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO cra_bewertungen
                (projekt_name, anforderung_id, bewertung, kommentar,
                 massnahme, verantwortlich, zieldatum, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
                bewertung      = excluded.bewertung,
                kommentar      = excluded.kommentar,
                massnahme      = excluded.massnahme,
                verantwortlich = excluded.verantwortlich,
                zieldatum      = excluded.zieldatum,
                updated_at     = datetime('now')
            """,
            (projekt_name, anforderung_id, bewertung, kommentar,
             massnahme, verantwortlich, zieldatum),
        )
        con.commit()
    finally:
        con.close()


def bulk_save_bewertungen(
    db_path: Path,
    projekt_name: str,
    rows: list[dict[str, Any]],
) -> int:
    con = _connect(db_path)
    try:
        count = 0
        for r in rows:
            aid = str(r.get("anforderung_id", "")).strip()
            if not aid:
                continue
            bew = int(r.get("bewertung", 0))
            if bew < 0 or bew > 5:
                bew = 0
            con.execute(
                """
                INSERT INTO cra_bewertungen
                    (projekt_name, anforderung_id, bewertung, kommentar,
                     massnahme, verantwortlich, zieldatum, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
                    bewertung      = excluded.bewertung,
                    kommentar      = excluded.kommentar,
                    massnahme      = excluded.massnahme,
                    verantwortlich = excluded.verantwortlich,
                    zieldatum      = excluded.zieldatum,
                    updated_at     = datetime('now')
                """,
                (projekt_name, aid, bew,
                 str(r.get("kommentar", "")),
                 str(r.get("massnahme", "")),
                 str(r.get("verantwortlich", "")),
                 str(r.get("zieldatum", ""))),
            )
            count += 1
        con.commit()
        return count
    finally:
        con.close()


def load_bewertungen(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    """Gibt {anforderung_id: {bewertung, kommentar, massnahme, ...}} zurück."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM cra_bewertungen WHERE projekt_name=?", (projekt_name,)
        )
        return {row["anforderung_id"]: dict(row) for row in cur.fetchall()}
    finally:
        con.close()


# ── OWASP checklist ───────────────────────────────────────────────────────────

def upsert_owasp_check(
    db_path: Path,
    projekt_name: str,
    owasp_id: str,
    status: int,
    kommentar: str = "",
    evidence: list[dict[str, Any]] | None = None,
) -> None:
    status = int(status)
    if status < 0 or status > 5:
        status = 0
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO cra_owasp_checks
                (projekt_name, owasp_id, status, kommentar, evidence_json, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(projekt_name, owasp_id) DO UPDATE SET
                status        = excluded.status,
                kommentar     = excluded.kommentar,
                evidence_json = excluded.evidence_json,
                updated_at    = datetime('now')
            """,
            (
                projekt_name,
                str(owasp_id).strip(),
                status,
                str(kommentar or ""),
                json.dumps(evidence or [], ensure_ascii=False),
            ),
        )
        con.commit()
    finally:
        con.close()


def load_owasp_checks(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    """Gibt {owasp_id: rowdict} zurück (inkl. evidence parsed)."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM cra_owasp_checks WHERE projekt_name=?",
            (projekt_name,),
        )
        out: dict[str, dict[str, Any]] = {}
        for row in cur.fetchall():
            d = dict(row)
            try:
                d["evidence"] = json.loads(d.get("evidence_json", "[]"))
            except Exception:
                d["evidence"] = []
            out[str(d.get("owasp_id", "")).strip()] = d
        return out
    finally:
        con.close()


# ── Benutzerdefinierte Anforderungen ──────────────────────────────────────────

def save_custom_anforderung(db_path: Path, req: dict[str, Any]) -> None:
    """Speichert eine benutzerdefinierte Anforderung oder überschreibt eine Standardanforderung."""
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO cra_anforderungen_custom
                (id, kapitel, ref, titel, beschreibung, hinweise, gewichtung, ist_override, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                kapitel      = excluded.kapitel,
                ref          = excluded.ref,
                titel        = excluded.titel,
                beschreibung = excluded.beschreibung,
                hinweise     = excluded.hinweise,
                gewichtung   = excluded.gewichtung,
                ist_override = excluded.ist_override,
                updated_at   = datetime('now')
            """,
            (
                req["id"], req.get("kapitel", "IMPL"), req.get("ref", ""),
                req.get("titel", ""), req.get("beschreibung", ""),
                req.get("hinweise", ""), int(req.get("gewichtung", 1)),
                1 if req.get("ist_override") else 0,
            ),
        )
        con.commit()
    finally:
        con.close()


def delete_custom_anforderung(db_path: Path, req_id: str) -> None:
    """Löscht einen benutzerdefinierten Eintrag oder eine Override-Definition."""
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM cra_anforderungen_custom WHERE id=?", (req_id,))
        con.commit()
    finally:
        con.close()


def load_custom_anforderungen(db_path: Path) -> list[dict[str, Any]]:
    """Lädt alle benutzerdefinierten / überschriebenen Anforderungen."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM cra_anforderungen_custom ORDER BY kapitel, id"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════════════════
# Phase A — Pflicht-Doku-Helper (Issues #472-#476)
# ═══════════════════════════════════════════════════════════════════════════

import json as _json


def _row_with_json(row, json_fields: tuple[str, ...]) -> dict:
    d = dict(row)
    for f in json_fields:
        try:
            d[f] = _json.loads(d.get(f) or '[]') if f.endswith('_json') or 'json' in f else d[f]
        except Exception:
            d[f] = []
    return d


# ─── C1: SBOM ──────────────────────────────────────────────────────────────

def list_sbom(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_sbom WHERE projekt_name=? ORDER BY sbom_datum DESC",
            (projekt_name,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d['lizenzen'] = _json.loads(d.get('lizenzen_json', '[]') or '[]')
            except Exception:
                d['lizenzen'] = []
            out.append(d)
        return out
    finally:
        con.close()


def save_sbom(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('release_version'):
        raise ValueError("Feld 'release_version' ist Pflicht")
    from datetime import datetime as _dt
    sbom_datum = data.get('sbom_datum') or _dt.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    lizenzen_json = _json.dumps(data.get('lizenzen') or [], ensure_ascii=False)
    con = _connect(db_path)
    try:
        sid = data.get('id')
        if sid:
            con.execute(
                """UPDATE cra_sbom SET release_version=?, sbom_format=?, sbom_datum=?,
                          komponenten_count=?, lizenzen_json=?, quelle=?, blob_path=?,
                          notizen=?, updated_at=datetime('now') WHERE id=?""",
                (data['release_version'], data.get('sbom_format', 'spdx'),
                 sbom_datum, int(data.get('komponenten_count', 0)),
                 lizenzen_json, data.get('quelle', ''), data.get('blob_path', ''),
                 data.get('notizen', ''), int(sid)),
            )
            con.commit()
            return int(sid)
        cur = con.execute(
            """INSERT INTO cra_sbom (projekt_name, release_version, sbom_format, sbom_datum,
                       komponenten_count, lizenzen_json, quelle, blob_path, notizen)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (projekt_name, data['release_version'], data.get('sbom_format', 'spdx'),
             sbom_datum, int(data.get('komponenten_count', 0)),
             lizenzen_json, data.get('quelle', ''), data.get('blob_path', ''),
             data.get('notizen', '')),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_sbom(db_path: Path, sbom_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM cra_sbom WHERE id=?", (int(sbom_id),))
        con.commit()
    finally:
        con.close()


# ─── C2: PSIRT ─────────────────────────────────────────────────────────────

def load_psirt(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM cra_psirt WHERE projekt_name=?", (projekt_name,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['psirt_contacts'] = _json.loads(d.get('psirt_contacts', '[]') or '[]')
        except Exception:
            d['psirt_contacts'] = []
        return d
    finally:
        con.close()


def save_psirt(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path)
    contacts_json = _json.dumps(data.get('psirt_contacts') or [], ensure_ascii=False)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_psirt (projekt_name, intake_kanal, triage_sla,
                       fix_sla_critical, fix_sla_high, fix_sla_medium,
                       disclosure_policy_url, security_md_url, psirt_contacts, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(projekt_name) DO UPDATE SET
                   intake_kanal=excluded.intake_kanal,
                   triage_sla=excluded.triage_sla,
                   fix_sla_critical=excluded.fix_sla_critical,
                   fix_sla_high=excluded.fix_sla_high,
                   fix_sla_medium=excluded.fix_sla_medium,
                   disclosure_policy_url=excluded.disclosure_policy_url,
                   security_md_url=excluded.security_md_url,
                   psirt_contacts=excluded.psirt_contacts,
                   notizen=excluded.notizen,
                   updated_at=datetime('now')""",
            (projekt_name, data.get('intake_kanal', ''), data.get('triage_sla', ''),
             data.get('fix_sla_critical', ''), data.get('fix_sla_high', ''),
             data.get('fix_sla_medium', ''), data.get('disclosure_policy_url', ''),
             data.get('security_md_url', ''), contacts_json, data.get('notizen', '')),
        )
        con.commit()
    finally:
        con.close()


# ─── C3: Vulnerability-Tracker ─────────────────────────────────────────────

_VULN_ALLOWED_STATUS = {'open', 'triaging', 'fixed', 'disclosed', 'wontfix'}


def list_vuln(db_path: Path, projekt_name: str, status: str | None = None) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if status:
            rows = con.execute(
                "SELECT * FROM cra_vuln WHERE projekt_name=? AND status=? ORDER BY cvss_score DESC, cve_id",
                (projekt_name, status),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM cra_vuln WHERE projekt_name=? ORDER BY status, cvss_score DESC, cve_id",
                (projekt_name,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_vuln(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('id') and not data.get('cve_id'):
        raise ValueError("Feld 'cve_id' ist Pflicht")
    status = data.get('status', 'open')
    if status not in _VULN_ALLOWED_STATUS:
        raise ValueError(f"status muss eines sein von: {sorted(_VULN_ALLOWED_STATUS)}")
    con = _connect(db_path)
    try:
        vid = data.get('id')
        if vid:
            con.execute(
                """UPDATE cra_vuln SET titel=?, schwere=?, cvss_score=?, cvss_vector=?,
                          affected_component=?, affected_versions=?, fixed_in_version=?,
                          advisory_url=?, status=?, triage_kommentar=?, fixed_at=?,
                          disclosed_at=?, updated_at=datetime('now') WHERE id=?""",
                (data.get('titel', ''), data.get('schwere', 'unknown'),
                 float(data.get('cvss_score') or 0), data.get('cvss_vector', ''),
                 data.get('affected_component', ''), data.get('affected_versions', ''),
                 data.get('fixed_in_version', ''), data.get('advisory_url', ''),
                 status, data.get('triage_kommentar', ''),
                 data.get('fixed_at'), data.get('disclosed_at'), int(vid)),
            )
            con.commit()
            return int(vid)
        cur = con.execute(
            """INSERT INTO cra_vuln (projekt_name, cve_id, titel, schwere, cvss_score, cvss_vector,
                       affected_component, affected_versions, fixed_in_version, advisory_url,
                       status, triage_kommentar, fixed_at, disclosed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (projekt_name, data['cve_id'], data.get('titel', ''), data.get('schwere', 'unknown'),
             float(data.get('cvss_score') or 0), data.get('cvss_vector', ''),
             data.get('affected_component', ''), data.get('affected_versions', ''),
             data.get('fixed_in_version', ''), data.get('advisory_url', ''),
             status, data.get('triage_kommentar', ''),
             data.get('fixed_at'), data.get('disclosed_at')),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_vuln(db_path: Path, vuln_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM cra_vuln WHERE id=?", (int(vuln_id),))
        con.commit()
    finally:
        con.close()


# ─── C4: Support-Period ────────────────────────────────────────────────────

def load_support_period(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM cra_support_period WHERE projekt_name=?", (projekt_name,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def save_support_period(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path)
    from datetime import datetime, timedelta
    # eol_datum aus markteintritt + support_jahre berechnen, falls nicht gesetzt
    eol = data.get('eol_datum')
    if not eol and data.get('markteintritt_datum'):
        try:
            mt = datetime.fromisoformat(data['markteintritt_datum'][:10])
            jahre = int(data.get('support_jahre', 5))
            eol = (mt + timedelta(days=jahre * 365)).date().isoformat()
        except Exception:
            eol = None
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_support_period (projekt_name, markteintritt_datum,
                       support_jahre, eol_datum, update_kanal, rationale, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(projekt_name) DO UPDATE SET
                   markteintritt_datum=excluded.markteintritt_datum,
                   support_jahre=excluded.support_jahre,
                   eol_datum=excluded.eol_datum,
                   update_kanal=excluded.update_kanal,
                   rationale=excluded.rationale,
                   notizen=excluded.notizen,
                   updated_at=datetime('now')""",
            (projekt_name, data.get('markteintritt_datum'), int(data.get('support_jahre', 5)),
             eol, data.get('update_kanal', ''), data.get('rationale', ''),
             data.get('notizen', '')),
        )
        con.commit()
    finally:
        con.close()


# ─── C5: Threat-Model ──────────────────────────────────────────────────────

def load_threatmodel(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM cra_threatmodel WHERE projekt_name=?", (projekt_name,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for f in ('assets_json', 'threats_json', 'mitigations_json'):
            try:
                d[f.replace('_json', '')] = _json.loads(d.get(f, '[]') or '[]')
            except Exception:
                d[f.replace('_json', '')] = []
        return d
    finally:
        con.close()


def save_threatmodel(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_threatmodel (projekt_name, framework, scope,
                       assets_json, threats_json, mitigations_json, diagram_url, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(projekt_name) DO UPDATE SET
                   framework=excluded.framework, scope=excluded.scope,
                   assets_json=excluded.assets_json, threats_json=excluded.threats_json,
                   mitigations_json=excluded.mitigations_json,
                   diagram_url=excluded.diagram_url, notizen=excluded.notizen,
                   updated_at=datetime('now')""",
            (projekt_name, data.get('framework', 'STRIDE'), data.get('scope', ''),
             _json.dumps(data.get('assets') or [], ensure_ascii=False),
             _json.dumps(data.get('threats') or [], ensure_ascii=False),
             _json.dumps(data.get('mitigations') or [], ensure_ascii=False),
             data.get('diagram_url', ''), data.get('notizen', '')),
        )
        con.commit()
    finally:
        con.close()
