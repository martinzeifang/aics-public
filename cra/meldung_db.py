"""CRA Art. 14 — Melde-Register (#1192) + Nutzer-Advisory (#1209).

Gestufter Melde-Workflow für aktiv ausgenutzte Schwachstellen UND schwerwiegende
Sicherheitsvorfälle (ENISA Single Reporting Platform). Lifecycle:
``erkannt → early_warning_24h → notification_72h → final_report``.

Tabelle ``cra_meldung`` (projekt-scoped, optionaler FK auf ``cra_vuln.id``).
Reines ``sqlite3``, kein ORM. ``ensure_table`` idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from shared import db as _sdb

DB_PATH = Path("data/db/cra.sqlite")

# Meldungstypen + Status (Single Source of Truth fürs Frontend).
TYPEN = ("vuln_exploited", "serious_incident")
STATUS = ("erkannt", "early_warning_24h", "notification_72h", "final_report")

# Stufen-Reihenfolge für Transition-Validierung.
_STATUS_ORDER = {s: i for i, s in enumerate(STATUS)}

# Status → STAGE_SET-Stufenschlüssel (für „gemeldet-am"-Mapping).
_STATUS_STAGE = {
    "early_warning_24h": "early_warning",
    "notification_72h": "notification",
    "final_report": "final_report",
}


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_meldung (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                vuln_id         INTEGER,                       -- optionaler FK auf cra_vuln.id
                typ             TEXT NOT NULL DEFAULT 'vuln_exploited',
                titel           TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'erkannt',
                erkannt_am      TEXT NOT NULL DEFAULT (aics_now()),
                betroffene_ms   TEXT NOT NULL DEFAULT '',      -- betroffene Mitgliedstaaten
                vermutete_ursache TEXT NOT NULL DEFAULT '',
                mitigation      TEXT NOT NULL DEFAULT '',
                beschreibung    TEXT NOT NULL DEFAULT '',
                -- 'Gemeldet-am' je Stufe (ISO-Timestamps).
                early_warning_gemeldet_am   TEXT,
                notification_gemeldet_am    TEXT,
                final_report_gemeldet_am    TEXT,
                -- Nutzer-Advisory (#1209, Art. 14(8)).
                advisory_json   TEXT NOT NULL DEFAULT '{}',
                created_at      TEXT DEFAULT (aics_now()),
                updated_at      TEXT DEFAULT (aics_now())
            );
            CREATE INDEX IF NOT EXISTS idx_cra_meldung_projekt
                ON cra_meldung(projekt_name);
            """
        )
        con.commit()
    finally:
        con.close()


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    try:
        d["advisory"] = json.loads(d.get("advisory_json") or "{}")
    except Exception:
        d["advisory"] = {}
    return d


def list_meldungen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_meldung WHERE projekt_name=? ORDER BY erkannt_am DESC, id DESC",
            (projekt_name,),
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()


def get_meldung(db_path: Path, meldung_id: int,
                projekt_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    """IDOR-sicher: optional auf projekt_name scopen (#1173-Muster)."""
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        if projekt_name is not None:
            r = con.execute(
                "SELECT * FROM cra_meldung WHERE id=? AND projekt_name=?",
                (meldung_id, projekt_name),
            ).fetchone()
        else:
            r = con.execute(
                "SELECT * FROM cra_meldung WHERE id=?", (meldung_id,)
            ).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def create_meldung(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_table(db_path)
    typ = data.get("typ") or "vuln_exploited"
    if typ not in TYPEN:
        raise ValueError(f"Ungültiger Typ: {typ}")
    erkannt = (data.get("erkannt_am") or "").strip()
    con = _connect(db_path)
    try:
        cur = con.execute(
            """
            INSERT INTO cra_meldung
                (projekt_name, vuln_id, typ, titel, status, erkannt_am,
                 betroffene_ms, vermutete_ursache, mitigation, beschreibung,
                 advisory_json, updated_at)
            VALUES (?, ?, ?, ?, 'erkannt', COALESCE(NULLIF(?, ''), aics_now()),
                    ?, ?, ?, ?, ?, aics_now())
            """,
            (projekt_name, data.get("vuln_id"), typ, data.get("titel", ""),
             erkannt, data.get("betroffene_ms", ""), data.get("vermutete_ursache", ""),
             data.get("mitigation", ""), data.get("beschreibung", ""),
             json.dumps(data.get("advisory") or {}, ensure_ascii=False)),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def update_meldung(db_path: Path, meldung_id: int, projekt_name: str,
                   data: dict) -> bool:
    ensure_table(db_path)
    fields = ["titel", "betroffene_ms", "vermutete_ursache", "mitigation",
              "beschreibung", "vuln_id"]
    sets, vals = [], []
    for f in fields:
        if f in data:
            sets.append(f"{f}=?")
            vals.append(data[f])
    if not sets:
        return True
    vals += [meldung_id, projekt_name]
    con = _connect(db_path)
    try:
        cur = con.execute(
            f"UPDATE cra_meldung SET {', '.join(sets)}, updated_at=aics_now() "
            "WHERE id=? AND projekt_name=?",
            vals,
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def set_stufe(db_path: Path, meldung_id: int, projekt_name: str,
              neuer_status: str) -> dict[str, Any]:
    """Stufen-Transition (nur vorwärts) + 'Gemeldet-am' der erreichten Stufe setzen."""
    if neuer_status not in STATUS:
        raise ValueError(f"Ungültiger Status: {neuer_status}")
    m = get_meldung(db_path, meldung_id, projekt_name)
    if not m:
        raise ValueError("Meldung nicht gefunden")
    cur_idx = _STATUS_ORDER[m["status"]]
    new_idx = _STATUS_ORDER[neuer_status]
    if new_idx <= cur_idx:
        raise ValueError("Stufe kann nur vorwärts gewechselt werden")
    stage_col = _STATUS_STAGE.get(neuer_status)
    con = _connect(db_path)
    try:
        if stage_col:
            con.execute(
                f"UPDATE cra_meldung SET status=?, {stage_col}_gemeldet_am=aics_now(), "
                "updated_at=aics_now() WHERE id=? AND projekt_name=?",
                (neuer_status, meldung_id, projekt_name),
            )
        else:
            con.execute(
                "UPDATE cra_meldung SET status=?, updated_at=aics_now() "
                "WHERE id=? AND projekt_name=?",
                (neuer_status, meldung_id, projekt_name),
            )
        con.commit()
    finally:
        con.close()
    return get_meldung(db_path, meldung_id, projekt_name)


def set_advisory(db_path: Path, meldung_id: int, projekt_name: str,
                 advisory: dict) -> Optional[dict[str, Any]]:
    """Nutzer-Advisory-Record je Meldung speichern (#1209, Art. 14(8))."""
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            "UPDATE cra_meldung SET advisory_json=?, updated_at=aics_now() "
            "WHERE id=? AND projekt_name=?",
            (json.dumps(advisory or {}, ensure_ascii=False), meldung_id, projekt_name),
        )
        con.commit()
        if cur.rowcount == 0:
            return None
    finally:
        con.close()
    return get_meldung(db_path, meldung_id, projekt_name)


def delete_meldung(db_path: Path, meldung_id: int, projekt_name: str) -> bool:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            "DELETE FROM cra_meldung WHERE id=? AND projekt_name=?",
            (meldung_id, projekt_name),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


# ── Strukturierte Meldetexte + ENISA-SRP-Export ─────────────────────────────────

_TYP_LABEL = {
    "vuln_exploited": "Aktiv ausgenutzte Schwachstelle",
    "serious_incident": "Schwerwiegender Sicherheitsvorfall",
}
_STUFE_LABEL = {
    "early_warning": "Frühwarnung (24h)",
    "notification": "Meldung (72h)",
    "final_report": "Abschlussbericht",
}


def build_meldetext(meldung: dict, stufe: str) -> str:
    """Strukturierter Meldetext je Stufe (ENISA-SRP-konforme Felder)."""
    lines = [
        f"Stufe: {_STUFE_LABEL.get(stufe, stufe)}",
        f"Typ: {_TYP_LABEL.get(meldung.get('typ', ''), meldung.get('typ', ''))}",
        f"Titel: {meldung.get('titel', '')}",
        f"Erkannt am: {meldung.get('erkannt_am', '')}",
        f"Betroffene Mitgliedstaaten: {meldung.get('betroffene_ms', '') or '—'}",
    ]
    if stufe in ("notification", "final_report"):
        lines.append(f"Vermutete Ursache: {meldung.get('vermutete_ursache', '') or '—'}")
        lines.append(f"Mitigation: {meldung.get('mitigation', '') or '—'}")
    if stufe == "final_report":
        lines.append(f"Beschreibung/Abschluss: {meldung.get('beschreibung', '') or '—'}")
    return "\n".join(lines)


def build_srp_payload(meldung: dict, deadlines: dict | None = None) -> dict[str, Any]:
    """ENISA-SRP-naher JSON-Payload (maschinenlesbar)."""
    return {
        "report_type": meldung.get("typ"),
        "title": meldung.get("titel"),
        "status": meldung.get("status"),
        "detected_at": meldung.get("erkannt_am"),
        "affected_member_states": meldung.get("betroffene_ms"),
        "suspected_cause": meldung.get("vermutete_ursache"),
        "mitigation": meldung.get("mitigation"),
        "description": meldung.get("beschreibung"),
        "reported_at": {
            "early_warning": meldung.get("early_warning_gemeldet_am"),
            "notification": meldung.get("notification_gemeldet_am"),
            "final_report": meldung.get("final_report_gemeldet_am"),
        },
        "deadlines": deadlines or {},
        "stage_texts": {
            "early_warning": build_meldetext(meldung, "early_warning"),
            "notification": build_meldetext(meldung, "notification"),
            "final_report": build_meldetext(meldung, "final_report"),
        },
        "user_advisory": meldung.get("advisory") or {},
    }
