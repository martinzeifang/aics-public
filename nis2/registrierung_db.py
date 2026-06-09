"""N-REG (#1203) — NIS2 Art. 27 BSI-Registrierungs-Stammdatensatz.

Self-contained, additiver DB-Layer auf ``data/db/nis2.sqlite`` (via
``nis2.db._connect``). Je Projekt **ein** Registrierungs-Datensatz
(``nis2_registrierung``, 1:1) mit den sechs Pflichtangaben nach Art. 27 Abs. 2:

1. Name der Einrichtung
2. Sektor/Subsektor/Einrichtungsart (Anhang I/II)
3. Anschrift Hauptniederlassung + sonstige EU-Niederlassungen/Vertreter
4. Kontakt (E-Mail/Telefon)
5. Mitgliedstaaten der Diensteerbringung
6. IP-Adressbereiche

Plus Übermittlungs-Status (offen/eingereicht/bestätigt), Registrierungsdatum,
Bestätigungsreferenz und Wiedervorlage der jährlichen Bestätigung (3-Monats-Frist).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from nis2.db import _connect

DB_PATH = Path("data/db/nis2.sqlite")

REG_STATUS = ("offen", "eingereicht", "bestaetigt")

# Die sechs Pflichtangaben (für die Vollständigkeits-Validierung).
PFLICHTFELDER = (
    "name", "sektor", "anschrift", "kontakt_email",
    "mitgliedstaaten", "ip_bereiche",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS nis2_registrierung (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name        TEXT NOT NULL UNIQUE,
    -- 6 Pflichtangaben Art. 27 Abs. 2
    name                TEXT NOT NULL DEFAULT '',
    sektor              TEXT NOT NULL DEFAULT '',
    subsektor           TEXT NOT NULL DEFAULT '',
    einrichtungsart     TEXT NOT NULL DEFAULT '',
    anschrift           TEXT NOT NULL DEFAULT '',
    eu_niederlassungen  TEXT NOT NULL DEFAULT '',
    kontakt_email       TEXT NOT NULL DEFAULT '',
    kontakt_telefon     TEXT NOT NULL DEFAULT '',
    mitgliedstaaten     TEXT NOT NULL DEFAULT '',
    ip_bereiche         TEXT NOT NULL DEFAULT '',
    -- Status / Übermittlung
    status              TEXT NOT NULL DEFAULT 'offen',
    registrierungs_datum TEXT NOT NULL DEFAULT '',
    bestaetigungs_referenz TEXT NOT NULL DEFAULT '',
    -- Aktualisierungs-/Jahres-Bestätigungs-Tracking
    naechste_jahres_bestaetigung TEXT NOT NULL DEFAULT '',
    notizen             TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_nis2_registrierung_projekt
    ON nis2_registrierung(projekt_name);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r else None


def missing_fields(data: dict) -> list[str]:
    """Liefert die Liste der noch fehlenden Pflichtangaben (Vollständigkeit)."""
    return [f for f in PFLICHTFELDER if not str(data.get(f, "") or "").strip()]


def get_registrierung(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        d = _row(con.execute(
            "SELECT * FROM nis2_registrierung WHERE projekt_name=?",
            (projekt_name,)).fetchone())
        if d:
            d["fehlende_pflichtfelder"] = missing_fields(d)
            d["vollstaendig"] = not d["fehlende_pflichtfelder"]
        return d
    finally:
        con.close()


def save_registrierung(db_path: Path, projekt_name: str, data: dict) -> dict[str, Any]:
    """Upsert (1:1 je Projekt). Validiert Status, lässt unvollständige Drafts zu.

    Vollständigkeit wird beim GET zurückgemeldet (nicht hart erzwungen, damit
    ein offener Entwurf gespeichert werden kann). Beim Status ``eingereicht``/
    ``bestaetigt`` müssen alle Pflichtangaben vorhanden sein.
    """
    ensure_table(db_path)
    status = data.get("status", "offen")
    if status not in REG_STATUS:
        status = "offen"
    if status in ("eingereicht", "bestaetigt"):
        miss = missing_fields(data)
        if miss:
            raise ValueError(
                "Vor Übermittlung müssen alle Pflichtangaben vorhanden sein. "
                f"Fehlend: {', '.join(miss)}")
    con = _connect(Path(db_path))
    try:
        con.execute(
            """INSERT INTO nis2_registrierung
                 (projekt_name, name, sektor, subsektor, einrichtungsart,
                  anschrift, eu_niederlassungen, kontakt_email, kontakt_telefon,
                  mitgliedstaaten, ip_bereiche, status, registrierungs_datum,
                  bestaetigungs_referenz, naechste_jahres_bestaetigung, notizen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(projekt_name) DO UPDATE SET
                  name=excluded.name, sektor=excluded.sektor,
                  subsektor=excluded.subsektor,
                  einrichtungsart=excluded.einrichtungsart,
                  anschrift=excluded.anschrift,
                  eu_niederlassungen=excluded.eu_niederlassungen,
                  kontakt_email=excluded.kontakt_email,
                  kontakt_telefon=excluded.kontakt_telefon,
                  mitgliedstaaten=excluded.mitgliedstaaten,
                  ip_bereiche=excluded.ip_bereiche,
                  status=excluded.status,
                  registrierungs_datum=excluded.registrierungs_datum,
                  bestaetigungs_referenz=excluded.bestaetigungs_referenz,
                  naechste_jahres_bestaetigung=excluded.naechste_jahres_bestaetigung,
                  notizen=excluded.notizen,
                  updated_at=datetime('now')""",
            (projekt_name, data.get("name", ""), data.get("sektor", ""),
             data.get("subsektor", ""), data.get("einrichtungsart", ""),
             data.get("anschrift", ""), data.get("eu_niederlassungen", ""),
             data.get("kontakt_email", ""), data.get("kontakt_telefon", ""),
             data.get("mitgliedstaaten", ""), data.get("ip_bereiche", ""),
             status, data.get("registrierungs_datum", ""),
             data.get("bestaetigungs_referenz", ""),
             data.get("naechste_jahres_bestaetigung", ""),
             data.get("notizen", "")))
        con.commit()
    finally:
        con.close()
    return get_registrierung(db_path, projekt_name)
