"""NIS2-Modul – SQLite-Datenzugriff."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared import db as _sdb

SCHEMA = """

CREATE TABLE IF NOT EXISTS nis2_projekte (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    unternehmen         TEXT NOT NULL DEFAULT '',
    einrichtungsklasse  TEXT NOT NULL DEFAULT 'wesentlich',
    beschreibung        TEXT NOT NULL DEFAULT '',
    berater             TEXT NOT NULL DEFAULT '',
    meta_json           TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT DEFAULT (aics_now()),
    updated_at          TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS nis2_bewertungen (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    anforderung_id  TEXT NOT NULL,
    bewertung       INTEGER NOT NULL DEFAULT 0,
    kommentar       TEXT NOT NULL DEFAULT '',
    massnahme       TEXT NOT NULL DEFAULT '',
    verantwortlich  TEXT NOT NULL DEFAULT '',
    zieldatum       TEXT NOT NULL DEFAULT '',
    updated_at      TEXT DEFAULT (aics_now()),
    UNIQUE(projekt_name, anforderung_id)
);

CREATE INDEX IF NOT EXISTS idx_nb_projekt ON nis2_bewertungen(projekt_name);

CREATE TABLE IF NOT EXISTS nis2_anforderungen_custom (
    id              TEXT PRIMARY KEY,
    kapitel         TEXT NOT NULL DEFAULT 'NIS5',
    ref             TEXT NOT NULL DEFAULT '',
    titel           TEXT NOT NULL DEFAULT '',
    beschreibung    TEXT NOT NULL DEFAULT '',
    hinweise        TEXT NOT NULL DEFAULT '',
    gewichtung      INTEGER NOT NULL DEFAULT 1,
    ist_override    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now())
);

CREATE TABLE IF NOT EXISTS nis2_dokumente (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    doc_name        TEXT NOT NULL,
    doc_path        TEXT NOT NULL,
    doc_type        TEXT NOT NULL DEFAULT 'resource',
    created_at      TEXT DEFAULT (aics_now())
);

CREATE INDEX IF NOT EXISTS idx_nd_projekt ON nis2_dokumente(projekt_name);

-- ───────────────────────────────────────────────────────────────────
-- Sprint β Phase A: NIS2 Pflicht-Doku-Manager (Issue #579)
-- ───────────────────────────────────────────────────────────────────

-- N1: Asset-Inventar (IT/OT/Daten/Cloud im Scope)
CREATE TABLE IF NOT EXISTS nis2_asset_inventory (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    asset_name      TEXT NOT NULL,
    asset_typ       TEXT NOT NULL DEFAULT 'it',     -- it | ot | daten | cloud-service | netzwerk | personen
    kritikalitaet   TEXT NOT NULL DEFAULT 'mittel', -- niedrig | mittel | hoch | kritisch
    verantwortlich  TEXT NOT NULL DEFAULT '',
    standort        TEXT NOT NULL DEFAULT '',
    beschreibung    TEXT NOT NULL DEFAULT '',
    schutzbedarf_v  INTEGER NOT NULL DEFAULT 1,     -- Vertraulichkeit 1-3
    schutzbedarf_i  INTEGER NOT NULL DEFAULT 1,     -- Integrität 1-3
    schutzbedarf_a  INTEGER NOT NULL DEFAULT 1,     -- Verfügbarkeit 1-3
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now()),
    UNIQUE(projekt_name, asset_name)
);
CREATE INDEX IF NOT EXISTS idx_nis2_asset_projekt ON nis2_asset_inventory(projekt_name);

-- N2: Risiko-Register
CREATE TABLE IF NOT EXISTS nis2_risiko_register (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    risiko_id       TEXT NOT NULL,                  -- z.B. NIS2-R-001
    titel           TEXT NOT NULL,
    asset_ref       TEXT NOT NULL DEFAULT '',       -- FK auf asset_name (lose)
    bedrohung       TEXT NOT NULL DEFAULT '',
    schwachstelle   TEXT NOT NULL DEFAULT '',
    auswirkung      TEXT NOT NULL DEFAULT 'mittel', -- niedrig | mittel | hoch | kritisch
    eintrittswkt    TEXT NOT NULL DEFAULT 'mittel', -- selten | gelegentlich | wahrscheinlich | fast-sicher
    risikoscore     INTEGER NOT NULL DEFAULT 0,     -- 1-25 (5x5-Matrix)
    massnahmen      TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'offen',  -- offen | in-behandlung | akzeptiert | mitigiert
    review_datum    TEXT,
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now()),
    UNIQUE(projekt_name, risiko_id)
);
CREATE INDEX IF NOT EXISTS idx_nis2_risiko_projekt ON nis2_risiko_register(projekt_name);

-- N3: Incident-Response-Plan (1 Eintrag pro Projekt)
CREATE TABLE IF NOT EXISTS nis2_incident_response (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    csirt_kontakt   TEXT NOT NULL DEFAULT '',      -- z.B. CERT-Bund, BSI
    csirt_email     TEXT NOT NULL DEFAULT '',
    early_warning_sla TEXT NOT NULL DEFAULT '24h',  -- NIS2 verlangt 24h
    notification_sla  TEXT NOT NULL DEFAULT '72h',  -- NIS2 verlangt 72h
    final_report_sla  TEXT NOT NULL DEFAULT '1 Monat',
    incident_manager TEXT NOT NULL DEFAULT '',
    eskalation_pfad TEXT NOT NULL DEFAULT '',       -- Markdown-Text
    playbook_url    TEXT NOT NULL DEFAULT '',
    kommunikationsplan TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now())
);

-- N4: Supply-Chain-Security
CREATE TABLE IF NOT EXISTS nis2_supply_chain (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    vendor_name     TEXT NOT NULL,
    leistung        TEXT NOT NULL DEFAULT '',
    kritikalitaet   TEXT NOT NULL DEFAULT 'mittel',
    assessment_datum TEXT,
    assessment_score INTEGER NOT NULL DEFAULT 0,   -- 0-100
    zertifikate     TEXT NOT NULL DEFAULT '[]',    -- JSON-Liste (ISO27001, SOC2, ...)
    sla_url         TEXT NOT NULL DEFAULT '',
    dpa_url         TEXT NOT NULL DEFAULT '',      -- Data-Processing-Agreement
    review_datum    TEXT,
    status          TEXT NOT NULL DEFAULT 'aktiv', -- aktiv | review-faellig | beendet
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now()),
    UNIQUE(projekt_name, vendor_name)
);
CREATE INDEX IF NOT EXISTS idx_nis2_sc_projekt ON nis2_supply_chain(projekt_name);

-- N5: Business-Continuity-Plan
CREATE TABLE IF NOT EXISTS nis2_bcp (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL UNIQUE,
    rpo_minuten     INTEGER NOT NULL DEFAULT 60,   -- Recovery Point Objective
    rto_minuten     INTEGER NOT NULL DEFAULT 240,  -- Recovery Time Objective
    backup_strategie TEXT NOT NULL DEFAULT '',
    backup_haeufigkeit TEXT NOT NULL DEFAULT 'taeglich',
    backup_aufbewahrung TEXT NOT NULL DEFAULT '30 Tage',
    dr_standort     TEXT NOT NULL DEFAULT '',      -- Disaster-Recovery-Standort
    test_datum      TEXT,                          -- letzte BCP-Übung
    test_frequenz   TEXT NOT NULL DEFAULT 'jaehrlich',
    bcp_url         TEXT NOT NULL DEFAULT '',
    krisenstab      TEXT NOT NULL DEFAULT '[]',    -- JSON-Liste
    notizen         TEXT NOT NULL DEFAULT '',
    created_at      TEXT DEFAULT (aics_now()),
    updated_at      TEXT DEFAULT (aics_now())
);
"""


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_db(db_path: Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
        from shared.firmen_link import ensure_firmen_id_column  # S1 (#1071)
        ensure_firmen_id_column(con, "nis2_projekte")
        # #1365: echte Quell-Spalten für importierte N2-Risiken
        # (ersetzt den notizen-Hack 'source_rb_risk_id=…')
        for stmt in (
            "ALTER TABLE nis2_risiko_register ADD COLUMN IF NOT EXISTS source_modul TEXT DEFAULT ''",
            "ALTER TABLE nis2_risiko_register ADD COLUMN IF NOT EXISTS source_ref TEXT DEFAULT ''",
            "ALTER TABLE nis2_risiko_register ADD COLUMN IF NOT EXISTS source_risk_id TEXT DEFAULT ''",
        ):
            try:
                con.execute(stmt)
            except Exception:
                pass
        con.commit()
    finally:
        con.close()


# ── Projekte ──────────────────────────────────────────────────────────────────

def save_projekt(
    db_path: Path,
    name: str,
    unternehmen: str = "",
    einrichtungsklasse: str = "wesentlich",
    beschreibung: str = "",
    berater: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO nis2_projekte
                (name, unternehmen, einrichtungsklasse, beschreibung, berater, meta_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, aics_now())
            ON CONFLICT(name) DO UPDATE SET
                unternehmen        = excluded.unternehmen,
                einrichtungsklasse = excluded.einrichtungsklasse,
                beschreibung       = excluded.beschreibung,
                berater            = excluded.berater,
                meta_json          = excluded.meta_json,
                updated_at         = aics_now()
            """,
            (name, unternehmen, einrichtungsklasse, beschreibung, berater,
             json.dumps(meta or {}, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()


def update_projekt_meta(db_path: Path, name: str, meta: dict[str, Any]) -> None:
    """Nur die ``meta_json``-Spalte eines bestehenden Projekts aktualisieren.

    Bewahrt unternehmen/einrichtungsklasse/beschreibung/berater; genutzt für die
    pro-Projekt-Repository-Konfiguration (#862)."""
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE nis2_projekte SET meta_json=?, updated_at=aics_now() WHERE name=?",
            (json.dumps(meta or {}, ensure_ascii=False), name),
        )
        con.commit()
    finally:
        con.close()


def load_projekt(db_path: Path, name: str) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        cur = con.execute("SELECT * FROM nis2_projekte WHERE name=?", (name,))
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
            "SELECT name FROM nis2_projekte ORDER BY updated_at DESC, name"
        )
        return [r["name"] for r in cur.fetchall()]
    finally:
        con.close()


def delete_projekt(db_path: Path, name: str) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM nis2_bewertungen WHERE projekt_name=?", (name,))
        con.execute("DELETE FROM nis2_dokumente   WHERE projekt_name=?", (name,))
        con.execute("DELETE FROM nis2_projekte    WHERE name=?", (name,))
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
            INSERT INTO nis2_bewertungen
                (projekt_name, anforderung_id, bewertung, kommentar,
                 massnahme, verantwortlich, zieldatum, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, aics_now())
            ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
                bewertung      = excluded.bewertung,
                kommentar      = excluded.kommentar,
                massnahme      = excluded.massnahme,
                verantwortlich = excluded.verantwortlich,
                zieldatum      = excluded.zieldatum,
                updated_at     = aics_now()
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
                INSERT INTO nis2_bewertungen
                    (projekt_name, anforderung_id, bewertung, kommentar,
                     massnahme, verantwortlich, zieldatum, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, aics_now())
                ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET
                    bewertung      = excluded.bewertung,
                    kommentar      = excluded.kommentar,
                    massnahme      = excluded.massnahme,
                    verantwortlich = excluded.verantwortlich,
                    zieldatum      = excluded.zieldatum,
                    updated_at     = aics_now()
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
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM nis2_bewertungen WHERE projekt_name=?", (projekt_name,)
        )
        return {row["anforderung_id"]: dict(row) for row in cur.fetchall()}
    finally:
        con.close()


# ── Benutzerdefinierte Anforderungen ──────────────────────────────────────────

def save_custom_anforderung(db_path: Path, req: dict[str, Any]) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO nis2_anforderungen_custom
                (id, kapitel, ref, titel, beschreibung, hinweise, gewichtung, ist_override, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, aics_now())
            ON CONFLICT(id) DO UPDATE SET
                kapitel      = excluded.kapitel,
                ref          = excluded.ref,
                titel        = excluded.titel,
                beschreibung = excluded.beschreibung,
                hinweise     = excluded.hinweise,
                gewichtung   = excluded.gewichtung,
                ist_override = excluded.ist_override,
                updated_at   = aics_now()
            """,
            (
                req["id"], req.get("kapitel", "NIS5"), req.get("ref", ""),
                req.get("titel", ""), req.get("beschreibung", ""),
                req.get("hinweise", ""), int(req.get("gewichtung", 1)),
                1 if req.get("ist_override") else 0,
            ),
        )
        con.commit()
    finally:
        con.close()


def delete_custom_anforderung(db_path: Path, req_id: str) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM nis2_anforderungen_custom WHERE id=?", (req_id,))
        con.commit()
    finally:
        con.close()


def load_custom_anforderungen(db_path: Path) -> list[dict[str, Any]]:
    con = _connect(db_path)
    try:
        cur = con.execute(
            "SELECT * FROM nis2_anforderungen_custom ORDER BY kapitel, id"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════════════════
# Sprint β Phase A — Pflicht-Doku-Helper (Issue #579)
# ═══════════════════════════════════════════════════════════════════════════

import json as _json


# ─── N1: Asset-Inventar ────────────────────────────────────────────────────

def list_assets(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path); con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM nis2_asset_inventory WHERE projekt_name=? ORDER BY kritikalitaet DESC, asset_name",
            (projekt_name,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_asset(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('asset_name'):
        raise ValueError("'asset_name' ist Pflicht")
    con = _connect(db_path)
    try:
        aid = data.get('id')
        if aid:
            con.execute(
                """UPDATE nis2_asset_inventory SET asset_name=?, asset_typ=?, kritikalitaet=?,
                          verantwortlich=?, standort=?, beschreibung=?, schutzbedarf_v=?,
                          schutzbedarf_i=?, schutzbedarf_a=?, notizen=?, updated_at=aics_now()
                   WHERE id=?""",
                (data['asset_name'], data.get('asset_typ', 'it'), data.get('kritikalitaet', 'mittel'),
                 data.get('verantwortlich', ''), data.get('standort', ''), data.get('beschreibung', ''),
                 int(data.get('schutzbedarf_v', 1)), int(data.get('schutzbedarf_i', 1)),
                 int(data.get('schutzbedarf_a', 1)), data.get('notizen', ''), int(aid)))
            con.commit(); return int(aid)
        cur = con.execute(
            """INSERT INTO nis2_asset_inventory (projekt_name, asset_name, asset_typ, kritikalitaet,
                  verantwortlich, standort, beschreibung, schutzbedarf_v, schutzbedarf_i, schutzbedarf_a, notizen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (projekt_name, data['asset_name'], data.get('asset_typ', 'it'), data.get('kritikalitaet', 'mittel'),
             data.get('verantwortlich', ''), data.get('standort', ''), data.get('beschreibung', ''),
             int(data.get('schutzbedarf_v', 1)), int(data.get('schutzbedarf_i', 1)),
             int(data.get('schutzbedarf_a', 1)), data.get('notizen', '')))
        con.commit(); return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_asset(db_path: Path, asset_id: int) -> None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        con.execute("DELETE FROM nis2_asset_inventory WHERE id=?", (int(asset_id),))
        con.commit()
    finally:
        con.close()


# ─── N2: Risiko-Register ───────────────────────────────────────────────────

_WKT_SCORES = {'selten': 1, 'gelegentlich': 2, 'wahrscheinlich': 3, 'fast-sicher': 4}
_AUSW_SCORES = {'niedrig': 1, 'mittel': 2, 'hoch': 3, 'kritisch': 4}


def _calc_risiko_score(auswirkung: str, wkt: str) -> int:
    return _AUSW_SCORES.get(auswirkung, 2) * _WKT_SCORES.get(wkt, 2)


def list_risiken(db_path: Path, projekt_name: str, status: str | None = None) -> list[dict[str, Any]]:
    ensure_db(db_path); con = _connect(db_path)
    try:
        if status:
            rows = con.execute(
                "SELECT * FROM nis2_risiko_register WHERE projekt_name=? AND status=? ORDER BY risikoscore DESC",
                (projekt_name, status)).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM nis2_risiko_register WHERE projekt_name=? ORDER BY risikoscore DESC, risiko_id",
                (projekt_name,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_risiko(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('id') and not data.get('risiko_id'):
        raise ValueError("'risiko_id' ist Pflicht")
    score = _calc_risiko_score(data.get('auswirkung', 'mittel'), data.get('eintrittswkt', 'mittel'))
    con = _connect(db_path)
    try:
        rid = data.get('id')
        if rid:
            con.execute(
                """UPDATE nis2_risiko_register SET titel=?, asset_ref=?, bedrohung=?,
                          schwachstelle=?, auswirkung=?, eintrittswkt=?, risikoscore=?,
                          massnahmen=?, status=?, review_datum=?, notizen=?, updated_at=aics_now()
                   WHERE id=?""",
                (data.get('titel', ''), data.get('asset_ref', ''), data.get('bedrohung', ''),
                 data.get('schwachstelle', ''), data.get('auswirkung', 'mittel'),
                 data.get('eintrittswkt', 'mittel'), score, data.get('massnahmen', ''),
                 data.get('status', 'offen'), data.get('review_datum'), data.get('notizen', ''), int(rid)))
            # #1365: Quell-Felder nur setzen, wenn explizit übergeben (sonst erhalten)
            if any(k in data for k in ('source_modul', 'source_ref', 'source_risk_id')):
                con.execute(
                    """UPDATE nis2_risiko_register SET source_modul=?, source_ref=?,
                              source_risk_id=? WHERE id=?""",
                    (data.get('source_modul', ''), data.get('source_ref', ''),
                     str(data.get('source_risk_id', '')), int(rid)))
            con.commit(); return int(rid)
        cur = con.execute(
            """INSERT INTO nis2_risiko_register (projekt_name, risiko_id, titel, asset_ref, bedrohung,
                  schwachstelle, auswirkung, eintrittswkt, risikoscore, massnahmen, status, review_datum, notizen,
                  source_modul, source_ref, source_risk_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (projekt_name, data['risiko_id'], data.get('titel', ''), data.get('asset_ref', ''),
             data.get('bedrohung', ''), data.get('schwachstelle', ''),
             data.get('auswirkung', 'mittel'), data.get('eintrittswkt', 'mittel'),
             score, data.get('massnahmen', ''), data.get('status', 'offen'),
             data.get('review_datum'), data.get('notizen', ''),
             data.get('source_modul', ''), data.get('source_ref', ''),
             str(data.get('source_risk_id', ''))))
        con.commit(); return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_risiko(db_path: Path, risk_id: int) -> None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        con.execute("DELETE FROM nis2_risiko_register WHERE id=?", (int(risk_id),)); con.commit()
    finally:
        con.close()


# ─── N3: Incident-Response (1:1) ───────────────────────────────────────────

def load_incident_response(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM nis2_incident_response WHERE projekt_name=?", (projekt_name,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def save_incident_response(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO nis2_incident_response (projekt_name, csirt_kontakt, csirt_email,
                  early_warning_sla, notification_sla, final_report_sla, incident_manager,
                  eskalation_pfad, playbook_url, kommunikationsplan, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,aics_now())
               ON CONFLICT(projekt_name) DO UPDATE SET
                 csirt_kontakt=excluded.csirt_kontakt, csirt_email=excluded.csirt_email,
                 early_warning_sla=excluded.early_warning_sla, notification_sla=excluded.notification_sla,
                 final_report_sla=excluded.final_report_sla, incident_manager=excluded.incident_manager,
                 eskalation_pfad=excluded.eskalation_pfad, playbook_url=excluded.playbook_url,
                 kommunikationsplan=excluded.kommunikationsplan, notizen=excluded.notizen,
                 updated_at=aics_now()""",
            (projekt_name, data.get('csirt_kontakt', ''), data.get('csirt_email', ''),
             data.get('early_warning_sla', '24h'), data.get('notification_sla', '72h'),
             data.get('final_report_sla', '1 Monat'), data.get('incident_manager', ''),
             data.get('eskalation_pfad', ''), data.get('playbook_url', ''),
             data.get('kommunikationsplan', ''), data.get('notizen', '')))
        con.commit()
    finally:
        con.close()


# ─── N4: Supply-Chain ──────────────────────────────────────────────────────

def list_vendors(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path); con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM nis2_supply_chain WHERE projekt_name=? ORDER BY kritikalitaet DESC, vendor_name",
            (projekt_name,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try: d['zertifikate'] = _json.loads(d.get('zertifikate', '[]') or '[]')
            except Exception: d['zertifikate'] = []
            out.append(d)
        return out
    finally:
        con.close()


def save_vendor(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_db(db_path)
    if not data.get('vendor_name'):
        raise ValueError("'vendor_name' ist Pflicht")
    zerti_json = _json.dumps(data.get('zertifikate') or [], ensure_ascii=False)
    con = _connect(db_path)
    try:
        vid = data.get('id')
        if vid:
            con.execute(
                """UPDATE nis2_supply_chain SET vendor_name=?, leistung=?, kritikalitaet=?,
                          assessment_datum=?, assessment_score=?, zertifikate=?, sla_url=?,
                          dpa_url=?, review_datum=?, status=?, notizen=?, updated_at=aics_now()
                   WHERE id=?""",
                (data['vendor_name'], data.get('leistung', ''), data.get('kritikalitaet', 'mittel'),
                 data.get('assessment_datum'), int(data.get('assessment_score', 0)),
                 zerti_json, data.get('sla_url', ''), data.get('dpa_url', ''),
                 data.get('review_datum'), data.get('status', 'aktiv'),
                 data.get('notizen', ''), int(vid)))
            con.commit(); return int(vid)
        cur = con.execute(
            """INSERT INTO nis2_supply_chain (projekt_name, vendor_name, leistung, kritikalitaet,
                  assessment_datum, assessment_score, zertifikate, sla_url, dpa_url, review_datum, status, notizen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (projekt_name, data['vendor_name'], data.get('leistung', ''),
             data.get('kritikalitaet', 'mittel'), data.get('assessment_datum'),
             int(data.get('assessment_score', 0)), zerti_json, data.get('sla_url', ''),
             data.get('dpa_url', ''), data.get('review_datum'),
             data.get('status', 'aktiv'), data.get('notizen', '')))
        con.commit(); return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_vendor(db_path: Path, vendor_id: int) -> None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        con.execute("DELETE FROM nis2_supply_chain WHERE id=?", (int(vendor_id),)); con.commit()
    finally:
        con.close()


# ─── N5: BCP (1:1) ─────────────────────────────────────────────────────────

def load_bcp(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_db(db_path); con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM nis2_bcp WHERE projekt_name=?", (projekt_name,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try: d['krisenstab'] = _json.loads(d.get('krisenstab', '[]') or '[]')
        except Exception: d['krisenstab'] = []
        return d
    finally:
        con.close()


def save_bcp(db_path: Path, projekt_name: str, data: dict) -> None:
    ensure_db(db_path)
    krisenstab_json = _json.dumps(data.get('krisenstab') or [], ensure_ascii=False)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO nis2_bcp (projekt_name, rpo_minuten, rto_minuten, backup_strategie,
                  backup_haeufigkeit, backup_aufbewahrung, dr_standort, test_datum,
                  test_frequenz, bcp_url, krisenstab, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,aics_now())
               ON CONFLICT(projekt_name) DO UPDATE SET
                 rpo_minuten=excluded.rpo_minuten, rto_minuten=excluded.rto_minuten,
                 backup_strategie=excluded.backup_strategie,
                 backup_haeufigkeit=excluded.backup_haeufigkeit,
                 backup_aufbewahrung=excluded.backup_aufbewahrung,
                 dr_standort=excluded.dr_standort, test_datum=excluded.test_datum,
                 test_frequenz=excluded.test_frequenz, bcp_url=excluded.bcp_url,
                 krisenstab=excluded.krisenstab, notizen=excluded.notizen,
                 updated_at=aics_now()""",
            (projekt_name, int(data.get('rpo_minuten', 60)), int(data.get('rto_minuten', 240)),
             data.get('backup_strategie', ''), data.get('backup_haeufigkeit', 'taeglich'),
             data.get('backup_aufbewahrung', '30 Tage'), data.get('dr_standort', ''),
             data.get('test_datum'), data.get('test_frequenz', 'jaehrlich'),
             data.get('bcp_url', ''), krisenstab_json, data.get('notizen', '')))
        con.commit()
    finally:
        con.close()
