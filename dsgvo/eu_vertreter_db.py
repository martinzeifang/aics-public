"""DS-EUV (#1219) — EU-Vertreter-Benennung (Art. 27 DSGVO).

Eigenständiges DSMS-Vertikal: Tabelle ``dsgvo_eu_vertreter`` in der geteilten
``data/db/dsgvo.sqlite`` (``dsgvo.db._connect``). EIN Datensatz pro Projekt
(Upsert über ``projekt_name``), analog zum DSB-Bereich (#1112).

Inhalt:

* Anwendbarkeitsprüfung Art. 3(2): Niederlassung außerhalb der EU? Angebot an
  EU-Betroffene und/oder Verhaltensbeobachtung? → Art. 3(2) einschlägig
  (``einschlaegig`` wird abgeleitet).
* Benennungs-Mini-Register: Vertreter-Name/Kontakt/Anschrift, schriftliches
  Mandat (Mandatsvertrag + Datum), Angabe in den Datenschutzhinweisen bestätigt.

Die Pflicht (Art. 27) besteht nur, wenn der Verantwortliche/Auftragsverarbeiter
NICHT in der EU niedergelassen ist UND unter Art. 3(2) fällt — daher die
Anwendbarkeitsprüfung vor der Benennung.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_eu_vertreter (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name             TEXT NOT NULL UNIQUE,
    -- Anwendbarkeitsprüfung Art. 3(2)
    niederlassung_ausserhalb_eu INTEGER NOT NULL DEFAULT 0,
    angebot_eu_betroffene    INTEGER NOT NULL DEFAULT 0,
    verhaltensbeobachtung    INTEGER NOT NULL DEFAULT 0,
    ausnahme_art27_2         INTEGER NOT NULL DEFAULT 0,
    pruefung_notiz           TEXT NOT NULL DEFAULT '',
    -- Benennungs-Mini-Register
    vertreter_name           TEXT NOT NULL DEFAULT '',
    vertreter_anschrift      TEXT NOT NULL DEFAULT '',
    vertreter_kontakt        TEXT NOT NULL DEFAULT '',
    mandat_vorhanden         INTEGER NOT NULL DEFAULT 0,
    mandat_datum             TEXT NOT NULL DEFAULT '',
    in_datenschutzhinweis    INTEGER NOT NULL DEFAULT 0,
    notizen                  TEXT NOT NULL DEFAULT '',
    created_at               TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at               TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_euv_projekt
    ON dsgvo_eu_vertreter(projekt_name);
"""

_ALLOWED = (
    "niederlassung_ausserhalb_eu", "angebot_eu_betroffene", "verhaltensbeobachtung",
    "ausnahme_art27_2", "pruefung_notiz", "vertreter_name", "vertreter_anschrift",
    "vertreter_kontakt", "mandat_vorhanden", "mandat_datum",
    "in_datenschutzhinweis", "notizen",
)
_BOOL = (
    "niederlassung_ausserhalb_eu", "angebot_eu_betroffene", "verhaltensbeobachtung",
    "ausnahme_art27_2", "mandat_vorhanden", "in_datenschutzhinweis",
)


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def is_einschlaegig(rec: dict[str, Any]) -> bool:
    """Art. 3(2): einschlägig, wenn keine EU-Niederlassung UND (Angebot an
    EU-Betroffene ODER Verhaltensbeobachtung) UND keine Ausnahme nach Art. 27(2)."""
    if not rec:
        return False
    return (
        bool(rec.get("niederlassung_ausserhalb_eu"))
        and (bool(rec.get("angebot_eu_betroffene")) or bool(rec.get("verhaltensbeobachtung")))
        and not bool(rec.get("ausnahme_art27_2"))
    )


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    for b in _BOOL:
        d[b] = int(d.get(b) or 0)
    d["einschlaegig"] = is_einschlaegig(d)
    # Benennung vollständig? (Name + Anschrift + Mandat + Angabe im Hinweis)
    d["benennung_vollstaendig"] = bool(
        str(d.get("vertreter_name") or "").strip()
        and str(d.get("vertreter_anschrift") or "").strip()
        and d.get("mandat_vorhanden")
        and d.get("in_datenschutzhinweis")
    )
    return d


def get_vertreter(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        r = con.execute(
            "SELECT * FROM dsgvo_eu_vertreter WHERE projekt_name=?",
            (projekt_name,)).fetchone()
        return _row(r) if r is not None else None
    finally:
        con.close()


def upsert_vertreter(db_path: Path, projekt_name: str, data: dict) -> dict[str, Any]:
    """Upsert (ein Datensatz pro Projekt)."""
    ensure_table(db_path)
    values = {k: data.get(k) for k in _ALLOWED if k in data}
    for b in _BOOL:
        if b in values:
            values[b] = int(bool(values[b]))
    con = _connect(Path(db_path))
    try:
        existing = con.execute(
            "SELECT id FROM dsgvo_eu_vertreter WHERE projekt_name=?",
            (projekt_name,)).fetchone()
        if existing:
            if values:
                sets = ", ".join(f"{k}=?" for k in values)
                con.execute(
                    f"UPDATE dsgvo_eu_vertreter SET {sets}, updated_at=datetime('now') "
                    f"WHERE projekt_name=?",
                    list(values.values()) + [projekt_name])
        else:
            cols = list(values.keys())
            ph = ",".join("?" for _ in cols)
            col_sql = (", " + ",".join(cols)) if cols else ""
            con.execute(
                f"INSERT INTO dsgvo_eu_vertreter (projekt_name{col_sql}) "
                f"VALUES (?{(', ' + ph) if cols else ''})",
                [projekt_name] + list(values.values()))
        con.commit()
    finally:
        con.close()
    return get_vertreter(db_path, projekt_name)  # type: ignore[return-value]


def delete_vertreter(db_path: Path, projekt_name: str) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "DELETE FROM dsgvo_eu_vertreter WHERE projekt_name=?", (projekt_name,))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def cockpit_summary(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Aggregat für das DSMS-Cockpit (#1102) — Pflicht-Check NUR wenn einschlägig.

    Nicht einschlägig oder keine Prüfung erfasst ⇒ 'leer' (kein Druck auf rein
    EU-ansässige Stellen). Einschlägig + unvollständige Benennung ⇒ offene Aufgabe.
    """
    rec = get_vertreter(db_path, projekt_name)
    if not rec or not rec.get("einschlaegig"):
        return {"reifegrad_pct": 0, "status": "leer", "offen": 0, "faellig": 0,
                "aufgaben": []}
    if rec.get("benennung_vollstaendig"):
        return {"reifegrad_pct": 100, "status": "gruen", "offen": 0, "faellig": 0,
                "aufgaben": []}
    aufgaben: list[dict[str, Any]] = []
    if not str(rec.get("vertreter_name") or "").strip():
        aufgaben.append({"text": "EU-Vertreter (Art. 27) noch nicht benannt",
                         "due": "", "overdue": False})
    if not rec.get("mandat_vorhanden"):
        aufgaben.append({"text": "Schriftliches Mandat des EU-Vertreters fehlt (Art. 27 Abs. 1)",
                         "due": "", "overdue": False})
    if not rec.get("in_datenschutzhinweis"):
        aufgaben.append({"text": "EU-Vertreter nicht in den Datenschutzhinweisen angegeben (Art. 13(1)(a))",
                         "due": "", "overdue": False})
    return {"reifegrad_pct": 30, "status": "rot", "offen": 1, "faellig": 0,
            "aufgaben": aufgaben}
