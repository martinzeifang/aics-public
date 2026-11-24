"""DS-JC (#1216) — Joint-Controller-Register (Art. 26 DSGVO).

Eigenständiges DSMS-Vertikal: Tabelle ``dsgvo_joint_controller`` in der geteilten
``data/db/dsgvo.sqlite`` (``dsgvo.db._connect``). Je Konstellation gemeinsam
Verantwortlicher (Joint Controller):

* Partner + betroffene Verarbeitung(en)/VVT-Referenz + Zweck-/Mittel-Beschreibung
* Verteilung der Pflichten (Betroffenenrechte-Anlaufstelle, Art. 13/14-Information,
  TOM, Datenpannen-Meldung)
* Vereinbarung vorhanden/URL/Datum
* den Betroffenen zugänglich gemachte Zusammenfassung des Wesentlichen (Status/Text)
* Review-Zyklus

Idempotenter Upsert anhand ``(projekt_name, jc_id)``.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")

# Anlaufstelle für Betroffenenrechte (Art. 26 Abs. 1): wer ist zuständig?
ANLAUFSTELLE = ("offen", "wir", "partner", "beide")

# Status der den Betroffenen zugänglich gemachten Zusammenfassung (Art. 26 Abs. 2).
ZUSAMMENFASSUNG_STATUS = ("offen", "entwurf", "veroeffentlicht")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_joint_controller (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name            TEXT NOT NULL,
    jc_id                   TEXT NOT NULL,
    partner                 TEXT NOT NULL DEFAULT '',
    partner_kontakt         TEXT NOT NULL DEFAULT '',
    vvt_ref                 TEXT NOT NULL DEFAULT '',
    verarbeitung            TEXT NOT NULL DEFAULT '',
    zweck_mittel            TEXT NOT NULL DEFAULT '',
    -- Pflichtenverteilung (Art. 26 Abs. 1)
    anlaufstelle_betroffene TEXT NOT NULL DEFAULT 'offen',
    pflicht_information     TEXT NOT NULL DEFAULT '',
    pflicht_tom             TEXT NOT NULL DEFAULT '',
    pflicht_meldung         TEXT NOT NULL DEFAULT '',
    -- Vereinbarung (Art. 26 Abs. 1)
    vereinbarung_vorhanden  INTEGER NOT NULL DEFAULT 0,
    vereinbarung_url        TEXT NOT NULL DEFAULT '',
    vereinbarung_datum      TEXT NOT NULL DEFAULT '',
    -- Zusammenfassung für Betroffene (Art. 26 Abs. 2)
    zusammenfassung_status  TEXT NOT NULL DEFAULT 'offen',
    zusammenfassung_text    TEXT NOT NULL DEFAULT '',
    zusammenfassung_url     TEXT NOT NULL DEFAULT '',
    -- Review
    reviewer                TEXT NOT NULL DEFAULT '',
    review_datum            TEXT NOT NULL DEFAULT '',
    review_zyklus_monate    INTEGER NOT NULL DEFAULT 12,
    naechstes_review        TEXT NOT NULL DEFAULT '',
    notizen                 TEXT NOT NULL DEFAULT '',
    created_at              TEXT NOT NULL DEFAULT (aics_now()),
    updated_at              TEXT NOT NULL DEFAULT (aics_now()),
    UNIQUE(projekt_name, jc_id)
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_jc_projekt
    ON dsgvo_joint_controller(projekt_name);
"""

# Felder, die per Upsert gesetzt werden dürfen (kein projekt_name/jc_id/Timestamps).
_ALLOWED = (
    "partner", "partner_kontakt", "vvt_ref", "verarbeitung", "zweck_mittel",
    "anlaufstelle_betroffene", "pflicht_information", "pflicht_tom",
    "pflicht_meldung", "vereinbarung_vorhanden", "vereinbarung_url",
    "vereinbarung_datum", "zusammenfassung_status", "zusammenfassung_text",
    "zusammenfassung_url", "reviewer", "review_datum", "review_zyklus_monate",
    "notizen",
)
_BOOL = ("vereinbarung_vorhanden",)
_INT = ("review_zyklus_monate",)


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _add_months(d: date, months: int) -> date:
    mi = d.month - 1 + months
    year = d.year + mi // 12
    month = mi % 12 + 1
    last = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(d.day, last[month - 1]))


def _parse(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _compute_review(review_datum: str, zyklus: int) -> str:
    d = _parse(review_datum)
    if d is None or not zyklus:
        return ""
    return _add_months(d, int(zyklus)).isoformat()


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    for b in _BOOL:
        d[b] = int(d.get(b) or 0)
    return d


# ── CRUD ─────────────────────────────────────────────────────────────────────

def list_jc(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM dsgvo_joint_controller WHERE projekt_name=? ORDER BY jc_id",
            (projekt_name,)).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()


def get_jc(db_path: Path, pk: int, projekt_name: str | None = None) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if projekt_name is not None:
            r = con.execute(
                "SELECT * FROM dsgvo_joint_controller WHERE id=? AND projekt_name=?",
                (int(pk), projekt_name)).fetchone()
        else:
            r = con.execute("SELECT * FROM dsgvo_joint_controller WHERE id=?",
                            (int(pk),)).fetchone()
        return _row(r) if r is not None else None
    finally:
        con.close()


def save_jc(db_path: Path, projekt_name: str, data: dict) -> int:
    """Upsert anhand (projekt_name, jc_id)."""
    ensure_table(db_path)
    jc_id = data.get("jc_id")
    if not jc_id:
        raise ValueError("'jc_id' ist Pflicht")
    if data.get("anlaufstelle_betroffene") and \
            data["anlaufstelle_betroffene"] not in ANLAUFSTELLE:
        raise ValueError(f"Ungültige Anlaufstelle: {data['anlaufstelle_betroffene']}")
    if data.get("zusammenfassung_status") and \
            data["zusammenfassung_status"] not in ZUSAMMENFASSUNG_STATUS:
        raise ValueError(f"Ungültiger Zusammenfassungs-Status: {data['zusammenfassung_status']}")

    values = {k: data.get(k) for k in _ALLOWED if k in data}
    for b in _BOOL:
        if b in values:
            values[b] = int(bool(values[b]))
    for i in _INT:
        if i in values:
            values[i] = int(values[i] or 0)
    if "review_datum" in values or "review_zyklus_monate" in values:
        rd = values.get("review_datum", data.get("review_datum", ""))
        zk = values.get("review_zyklus_monate", data.get("review_zyklus_monate", 12))
        values["naechstes_review"] = _compute_review(rd, zk)

    con = _connect(Path(db_path))
    try:
        existing = con.execute(
            "SELECT id FROM dsgvo_joint_controller WHERE projekt_name=? AND jc_id=?",
            (projekt_name, jc_id)).fetchone()
        if existing:
            if values:
                sets = ", ".join(f"{k}=?" for k in values)
                con.execute(
                    f"UPDATE dsgvo_joint_controller SET {sets}, updated_at=aics_now() "
                    f"WHERE id=?",
                    list(values.values()) + [int(existing["id"])])
            pk = int(existing["id"])
        else:
            cols = ["jc_id"] + list(values.keys())
            vals = [jc_id] + list(values.values())
            ph = ",".join("?" for _ in cols)
            cur = con.execute(
                f"INSERT INTO dsgvo_joint_controller (projekt_name, {','.join(cols)}) "
                f"VALUES (?, {ph})",
                [projekt_name] + vals)
            pk = int(cur.lastrowid)
        con.commit()
        return pk
    finally:
        con.close()


def delete_jc(db_path: Path, pk: int, projekt_name: str | None = None) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if projekt_name is not None:
            cur = con.execute(
                "DELETE FROM dsgvo_joint_controller WHERE id=? AND projekt_name=?",
                (int(pk), projekt_name))
        else:
            cur = con.execute("DELETE FROM dsgvo_joint_controller WHERE id=?", (int(pk),))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def cockpit_summary(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Aggregat für das DSMS-Cockpit (#1102): Reifegrad + offene Aufgaben.

    Reifegrad je Konstellation = Anteil erfüllter Pflicht-Bausteine
    (Vereinbarung vorhanden, Anlaufstelle festgelegt, Zusammenfassung
    veröffentlicht). Kein Eintrag ⇒ 'leer' (Art. 26 ist Ausnahmefall).
    """
    rows = list_jc(db_path, projekt_name)
    total = len(rows)
    if not total:
        return {"reifegrad_pct": 0, "status": "leer", "offen": 0, "faellig": 0,
                "aufgaben": []}
    erfuellt = 0.0
    aufgaben: list[dict[str, Any]] = []
    offen = 0
    for r in rows:
        checks = [
            bool(r.get("vereinbarung_vorhanden")),
            str(r.get("anlaufstelle_betroffene") or "offen") != "offen",
            str(r.get("zusammenfassung_status") or "offen") == "veroeffentlicht",
        ]
        erfuellt += sum(checks) / len(checks)
        if not all(checks):
            offen += 1
        label = r.get("partner") or r.get("jc_id")
        if not r.get("vereinbarung_vorhanden"):
            aufgaben.append({"text": f"Art.-26-Vereinbarung fehlt: {label}",
                             "due": "", "overdue": False})
        if str(r.get("anlaufstelle_betroffene") or "offen") == "offen":
            aufgaben.append({"text": f"Betroffenenrechte-Anlaufstelle offen: {label}",
                             "due": "", "overdue": False})
        if str(r.get("zusammenfassung_status") or "offen") != "veroeffentlicht":
            aufgaben.append({"text": f"Zusammenfassung für Betroffene nicht veröffentlicht: {label}",
                             "due": "", "overdue": False})
    pct = max(0, min(100, round(erfuellt / total * 100)))
    status = "leer" if total == 0 else ("rot" if pct < 40 else ("gelb" if pct < 80 else "gruen"))
    return {"reifegrad_pct": pct, "status": status, "offen": offen,
            "faellig": 0, "aufgaben": aufgaben}
