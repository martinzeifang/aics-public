"""N-INC (#1194) — NIS2 Art. 23 Vorfall-/Meldungs-Register mit Fristen-Lifecycle.

Self-contained, additiver DB-Layer auf der gemeinsamen ``data/db/nis2.sqlite``
(via ``nis2.db._connect``). Modelliert je **erheblichem Vorfall** (``nis2_incident``)
die drei verbundenen Melde-Stufen (``nis2_incident_meldung``):

- Frühwarnung (24h ab Kenntnis)              — Art. 23 Abs. 4 lit. a
- Vorfallmeldung (72h ab Kenntnis)           — Art. 23 Abs. 4 lit. b
- Zwischenbericht (auf Ersuchen, optional)   — Art. 23 Abs. 4
- Abschlussbericht (1 Monat ab 72h-Meldung)  — Art. 23 Abs. 4 lit. c

Die Fristberechnung selbst liegt in ``shared.deadlines`` (STAGE_SET ``nis2_art23``);
dieser Layer speichert nur die Roh-Zeitpunkte (``kenntnis_zeitpunkt`` /
``ist_zeitpunkt`` je Stufe) und Status.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from nis2.db import _connect

DB_PATH = Path("data/db/nis2.sqlite")

INCIDENT_STATUS = ("offen", "in_bearbeitung", "abgeschlossen")
MELDUNG_STATUS = ("offen", "uebermittelt", "ueberfaellig")
# Kanonische Melde-Stufen-Typen (gespiegelt zu shared.deadlines STAGE_SET nis2_art23
# + 'zwischen' für den optionalen Zwischenbericht auf Ersuchen).
MELDUNG_TYPEN = ("24h", "72h", "zwischen", "1M")
SCHWEREGRADE = ("niedrig", "mittel", "hoch", "kritisch")

# Mapping Stufen-Typ → deadlines.DeadlineStage.key (für Ampel-Auswertung).
TYP_TO_STAGE_KEY = {
    "24h": "fruehwarnung",
    "72h": "meldung",
    "1M": "abschlussbericht",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS nis2_incident (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name        TEXT NOT NULL,
    incident_id         TEXT NOT NULL,
    titel               TEXT NOT NULL DEFAULT '',
    kenntnis_zeitpunkt  TEXT NOT NULL DEFAULT '',
    erheblich           INTEGER NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'offen',
    schweregrad         TEXT NOT NULL DEFAULT 'mittel',
    betroffene_assets   TEXT NOT NULL DEFAULT '',
    root_cause          TEXT NOT NULL DEFAULT '',
    grenzueberschreitend INTEGER NOT NULL DEFAULT 0,
    notizen             TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (aics_now()),
    updated_at          TEXT NOT NULL DEFAULT (aics_now()),
    UNIQUE(projekt_name, incident_id)
);
CREATE INDEX IF NOT EXISTS idx_nis2_incident_projekt ON nis2_incident(projekt_name);

CREATE TABLE IF NOT EXISTS nis2_incident_meldung (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_pk     INTEGER NOT NULL,
    typ             TEXT NOT NULL DEFAULT '24h',
    status          TEXT NOT NULL DEFAULT 'offen',
    ist_zeitpunkt   TEXT NOT NULL DEFAULT '',
    text            TEXT NOT NULL DEFAULT '',
    bsi_referenz    TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (aics_now()),
    updated_at      TEXT NOT NULL DEFAULT (aics_now()),
    UNIQUE(incident_pk, typ)
);
CREATE INDEX IF NOT EXISTS idx_nis2_incident_meldung_pk ON nis2_incident_meldung(incident_pk);
"""


def _normalize_ts(value: str | None) -> str:
    """ISO-Zeitstempel auf Sekunden-Präzision normalisieren.

    Die zentrale ``shared.deadlines``-Engine (Phase 0) parst keine Mikrosekunden;
    Eingaben aus ``datetime.isoformat()`` enthalten diese aber. Wir schneiden den
    Mikrosekunden-Anteil ab und behalten einen evtl. TZ-Offset bei. Nicht parsbare
    Werte werden unverändert durchgereicht.
    """
    s = (value or "").strip()
    if not s:
        return ""
    try:
        norm = s.replace("Z", "+00:00")
        dt = __import__("datetime").datetime.fromisoformat(norm)
        return dt.replace(microsecond=0).isoformat()
    except ValueError:
        return s


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row(r: Any | None) -> dict[str, Any] | None:
    return dict(r) if r else None


# ── Vorfälle ────────────────────────────────────────────────────────────────

def list_incidents(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM nis2_incident WHERE projekt_name=? "
            "ORDER BY kenntnis_zeitpunkt DESC, id DESC", (projekt_name,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["meldungen"] = _list_meldungen(con, d["id"])
            out.append(d)
        return out
    finally:
        con.close()


def get_incident(db_path: Path, projekt_name: str, pk: int) -> dict[str, Any] | None:
    """Projekt-scoped Einzel-Lookup (IDOR-Schutz, analog #1173)."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        d = _row(con.execute(
            "SELECT * FROM nis2_incident WHERE id=? AND projekt_name=?",
            (int(pk), projekt_name)).fetchone())
        if d:
            d["meldungen"] = _list_meldungen(con, d["id"])
        return d
    finally:
        con.close()


def save_incident(db_path: Path, projekt_name: str, data: dict) -> int:
    """Upsert anhand (projekt_name, incident_id)."""
    ensure_table(db_path)
    iid = str(data.get("incident_id") or "").strip()
    if not iid:
        raise ValueError("'incident_id' ist Pflicht")
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            """INSERT INTO nis2_incident
                 (projekt_name, incident_id, titel, kenntnis_zeitpunkt, erheblich,
                  status, schweregrad, betroffene_assets, root_cause,
                  grenzueberschreitend, notizen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(projekt_name, incident_id) DO UPDATE SET
                  titel=excluded.titel,
                  kenntnis_zeitpunkt=excluded.kenntnis_zeitpunkt,
                  erheblich=excluded.erheblich,
                  status=excluded.status,
                  schweregrad=excluded.schweregrad,
                  betroffene_assets=excluded.betroffene_assets,
                  root_cause=excluded.root_cause,
                  grenzueberschreitend=excluded.grenzueberschreitend,
                  notizen=excluded.notizen,
                  updated_at=aics_now()""",
            (projekt_name, iid, data.get("titel", ""),
             _normalize_ts(data.get("kenntnis_zeitpunkt", "")),
             1 if data.get("erheblich", True) else 0,
             data.get("status", "offen") if data.get("status") in INCIDENT_STATUS else "offen",
             data.get("schweregrad", "mittel"),
             data.get("betroffene_assets", ""), data.get("root_cause", ""),
             1 if data.get("grenzueberschreitend") else 0,
             data.get("notizen", "")))
        if cur.lastrowid:
            pk = int(cur.lastrowid)
        else:
            pk = int(con.execute(
                "SELECT id FROM nis2_incident WHERE projekt_name=? AND incident_id=?",
                (projekt_name, iid)).fetchone()["id"])
        con.commit()
        return pk
    finally:
        con.close()


def delete_incident(db_path: Path, projekt_name: str, pk: int) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        row = con.execute(
            "SELECT id FROM nis2_incident WHERE id=? AND projekt_name=?",
            (int(pk), projekt_name)).fetchone()
        if not row:
            return False
        con.execute("DELETE FROM nis2_incident_meldung WHERE incident_pk=?", (int(pk),))
        con.execute("DELETE FROM nis2_incident WHERE id=?", (int(pk),))
        con.commit()
        return True
    finally:
        con.close()


# ── Meldungen (Stufen) ──────────────────────────────────────────────────────

def _list_meldungen(con: Any, incident_pk: int) -> list[dict[str, Any]]:
    rows = con.execute(
        "SELECT * FROM nis2_incident_meldung WHERE incident_pk=? ORDER BY id",
        (int(incident_pk),)).fetchall()
    return [dict(r) for r in rows]


def list_meldungen(db_path: Path, incident_pk: int) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        return _list_meldungen(con, incident_pk)
    finally:
        con.close()


def get_meldung(db_path: Path, meldung_id: int) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        return _row(con.execute(
            "SELECT * FROM nis2_incident_meldung WHERE id=?", (int(meldung_id),)).fetchone())
    finally:
        con.close()


def save_meldung(db_path: Path, incident_pk: int, data: dict) -> int:
    """Upsert einer Meldestufe je (incident_pk, typ)."""
    ensure_table(db_path)
    typ = str(data.get("typ") or "").strip()
    if typ not in MELDUNG_TYPEN:
        raise ValueError(f"'typ' muss eines von {MELDUNG_TYPEN} sein")
    status = data.get("status", "offen")
    if status not in MELDUNG_STATUS:
        status = "offen"
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            """INSERT INTO nis2_incident_meldung
                 (incident_pk, typ, status, ist_zeitpunkt, text, bsi_referenz)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(incident_pk, typ) DO UPDATE SET
                  status=excluded.status,
                  ist_zeitpunkt=excluded.ist_zeitpunkt,
                  text=excluded.text,
                  bsi_referenz=excluded.bsi_referenz,
                  updated_at=aics_now()""",
            (int(incident_pk), typ, status, _normalize_ts(data.get("ist_zeitpunkt", "")),
             data.get("text", ""), data.get("bsi_referenz", "")))
        if cur.lastrowid:
            pk = int(cur.lastrowid)
        else:
            pk = int(con.execute(
                "SELECT id FROM nis2_incident_meldung WHERE incident_pk=? AND typ=?",
                (int(incident_pk), typ)).fetchone()["id"])
        con.commit()
        return pk
    finally:
        con.close()


def delete_meldung(db_path: Path, meldung_id: int) -> None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        con.execute("DELETE FROM nis2_incident_meldung WHERE id=?", (int(meldung_id),))
        con.commit()
    finally:
        con.close()


# ── Fristen-Auswertung (nutzt shared.deadlines) ─────────────────────────────

def evaluate_incident_deadlines(incident: dict, *, now=None) -> dict:
    """Berechnet je Vorfall die Ampel/Countdown der drei Pflicht-Stufen.

    24h/72h ab ``kenntnis_zeitpunkt``; 1M (Abschluss) ab dem **tatsächlichen**
    72h-Meldezeitpunkt (Fallback: 72h-Soll ab Kenntnis), gem. Art. 23 Abs. 4 lit. c.
    """
    from datetime import timedelta

    from shared import deadlines as dl

    meldungen = {m.get("typ"): m for m in incident.get("meldungen", [])}
    fulfilled: dict[str, str] = {}
    for typ, key in TYP_TO_STAGE_KEY.items():
        m = meldungen.get(typ)
        if m and m.get("status") == "uebermittelt" and m.get("ist_zeitpunkt"):
            fulfilled[key] = m["ist_zeitpunkt"]

    base = incident.get("kenntnis_zeitpunkt") or ""
    # Frühwarnung + Meldung relativ zur Kenntnis (Engine STAGE_SET).
    fw_meld = dl.evaluate(
        base,
        [s for s in dl.stages_for("nis2_art23")
         if s.key in ("fruehwarnung", "meldung")],
        fulfilled=fulfilled, now=now)

    # Abschlussbericht: 1 Monat ab tatsächlicher 72h-Meldung (sonst 72h-Soll).
    meldung_72 = meldungen.get("72h")
    if meldung_72 and meldung_72.get("ist_zeitpunkt"):
        abschluss_base = meldung_72["ist_zeitpunkt"]
    else:
        meld_due = dl.parse_dt(base)
        abschluss_base = (
            (meld_due + timedelta(hours=72)).isoformat() if meld_due else ""
        )
    abschluss_stage = dl.DeadlineStage(
        "abschlussbericht", "Abschlussbericht (1 Monat)", 30 * 24.0)
    abschluss = dl.evaluate(
        abschluss_base, [abschluss_stage], fulfilled=fulfilled, now=now)

    stages = fw_meld["stages"] + abschluss["stages"]
    any_overdue = fw_meld["any_overdue"] or abschluss["any_overdue"]
    if any_overdue:
        overall = "red"
    elif any(s["ampel"] == "amber" for s in stages):
        overall = "amber"
    elif stages and all(s["fulfilled"] for s in stages):
        overall = "green"
    elif not any(s["due_at"] for s in stages):
        overall = "grey"
    else:
        overall = "green"
    open_stages = [s for s in stages if not s["fulfilled"] and s["due_at"]]
    next_due = None
    if open_stages:
        next_due = sorted(
            open_stages,
            key=lambda s: (s["status"] != "overdue", s.get("hours_left") or 0))[0]
    return {"stages": stages, "overall_ampel": overall,
            "any_overdue": any_overdue, "next_due": next_due}


def derive_meldung_status(incident: dict, *, now=None) -> dict[str, str]:
    """Liefert je Stufen-Typ einen abgeleiteten Status (offen/uebermittelt/ueberfaellig).

    Übermittelte Stufen bleiben übermittelt; offene überfällige Stufen werden
    ``ueberfaellig`` (für die Status-Pille im Panel).
    """
    ev = evaluate_incident_deadlines(incident, now=now)
    key_to_typ = {v: k for k, v in TYP_TO_STAGE_KEY.items()}
    out: dict[str, str] = {}
    for st in ev["stages"]:
        typ = key_to_typ.get(st["key"])
        if not typ:
            continue
        if st["fulfilled"]:
            out[typ] = "uebermittelt"
        elif st["status"] == "overdue":
            out[typ] = "ueberfaellig"
        else:
            out[typ] = "offen"
    return out
