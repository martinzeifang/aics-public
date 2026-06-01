"""G1-1 bis G1-5 — DB-Tabellen für das BISG-Gerichtsgutachten.

Komplett getrennt von den existierenden gutachten_*-Tabellen (Audit-Bericht).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

_SCHEMA = """
-- G1-1: Stammdaten Verfahren (mit Privat-Variante #663)
CREATE TABLE IF NOT EXISTS gerichtsgutachten (
    name              TEXT PRIMARY KEY,
    gutachten_art     TEXT NOT NULL DEFAULT 'gericht',   -- gericht|privat (#663)
    gericht           TEXT NOT NULL DEFAULT '',
    kammer            TEXT NOT NULL DEFAULT '',
    aktenzeichen      TEXT NOT NULL DEFAULT '',
    klaeger_name      TEXT NOT NULL DEFAULT '',
    klaeger_anwalt    TEXT NOT NULL DEFAULT '',
    beklagter_name    TEXT NOT NULL DEFAULT '',
    beklagter_anwalt  TEXT NOT NULL DEFAULT '',
    beweisbeschluss_datum TEXT NOT NULL DEFAULT '',
    -- Privat-spezifisch (#663):
    auftraggeber      TEXT NOT NULL DEFAULT '',
    auftrags_art      TEXT NOT NULL DEFAULT '',   -- Beweissicherung|Tauglichkeitsprüfung|Schaden-Gutachten|Sonstiges
    auftrags_datum    TEXT NOT NULL DEFAULT '',
    auftrags_nummer   TEXT NOT NULL DEFAULT '',   -- freier Code statt Aktenzeichen
    honorarvereinbarung TEXT NOT NULL DEFAULT '', -- Privat: freie Vereinbarung
    -- gemeinsam:
    thema             TEXT NOT NULL DEFAULT '',
    vertraulichkeit   TEXT NOT NULL DEFAULT 'STRENG VERTRAULICH',
    sv_name           TEXT NOT NULL DEFAULT '',
    sv_zertifizierung TEXT NOT NULL DEFAULT '',
    sv_anschrift      TEXT NOT NULL DEFAULT '',
    sv_kontakt        TEXT NOT NULL DEFAULT '',
    erstellt_am       TEXT NOT NULL DEFAULT (datetime('now')),
    erstellt_von      TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'in_bearbeitung',  -- in_bearbeitung|finalisiert|eingereicht
    meta_json         TEXT NOT NULL DEFAULT '{}'
);

-- G1-2: Beweisfragen
CREATE TABLE IF NOT EXISTS gerichtsgutachten_beweisfragen (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name             TEXT NOT NULL,
    nr                       INTEGER NOT NULL DEFAULT 1,
    frage_text               TEXT NOT NULL DEFAULT '',
    antwort_text             TEXT NOT NULL DEFAULT '',
    antwort_kurz             TEXT NOT NULL DEFAULT '',  -- ja|nein|teilweise|non-liquet
    referenz_beurteilung_ids TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_bewf_projekt ON gerichtsgutachten_beweisfragen(projekt_name, nr);

-- G1-3: Befunde (Kap. IV — Tatsachen)
CREATE TABLE IF NOT EXISTS gerichtsgutachten_befunde (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name      TEXT NOT NULL,
    nr                TEXT NOT NULL DEFAULT '',       -- z.B. "4.1", "4.2"
    titel             TEXT NOT NULL DEFAULT '',
    beschreibung_text TEXT NOT NULL DEFAULT '',
    methode           TEXT NOT NULL DEFAULT '',       -- statisch|dynamisch|db|netzwerk|interview|live-forensik
    werkzeug_name     TEXT NOT NULL DEFAULT '',
    werkzeug_version  TEXT NOT NULL DEFAULT '',
    asset_ids         TEXT NOT NULL DEFAULT '[]',
    erhebung_datum    TEXT NOT NULL DEFAULT '',
    erhebung_ort      TEXT NOT NULL DEFAULT '',
    zeugen_text       TEXT NOT NULL DEFAULT '',
    non_liquet        INTEGER NOT NULL DEFAULT 0,
    non_liquet_grund  TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_befunde_projekt ON gerichtsgutachten_befunde(projekt_name, nr);

-- G1-4: Beurteilungen (Kap. V)
CREATE TABLE IF NOT EXISTS gerichtsgutachten_beurteilungen (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name    TEXT NOT NULL,
    nr              TEXT NOT NULL DEFAULT '',         -- z.B. "5.1", "5.2"
    titel           TEXT NOT NULL DEFAULT '',
    befund_ids      TEXT NOT NULL DEFAULT '[]',
    norm_referenz   TEXT NOT NULL DEFAULT '',
    soll_text       TEXT NOT NULL DEFAULT '',
    ist_text        TEXT NOT NULL DEFAULT '',
    kausalitaet_text TEXT NOT NULL DEFAULT '',
    bewertung_text  TEXT NOT NULL DEFAULT '',
    non_liquet      INTEGER NOT NULL DEFAULT 0,
    non_liquet_grund TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_beurt_projekt ON gerichtsgutachten_beurteilungen(projekt_name, nr);

-- G1-5a: Assets (Asservaten mit SHA-256)
CREATE TABLE IF NOT EXISTS gerichtsgutachten_assets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name        TEXT NOT NULL,
    bezeichnung         TEXT NOT NULL DEFAULT '',
    sha256              TEXT NOT NULL DEFAULT '',
    akquisitions_utc    TEXT NOT NULL DEFAULT '',
    akquisitions_ort    TEXT NOT NULL DEFAULT '',
    werkzeug_name       TEXT NOT NULL DEFAULT '',
    werkzeug_version    TEXT NOT NULL DEFAULT '',
    parteien_anwesend   TEXT NOT NULL DEFAULT '[]',
    gegengezeichnet_von TEXT NOT NULL DEFAULT '',
    bemerkungen         TEXT NOT NULL DEFAULT '',
    original_dateiname  TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_assets_projekt ON gerichtsgutachten_assets(projekt_name);

-- G1-5b: Verfahrensereignisse (CoC + Verfahrensgang)
CREATE TABLE IF NOT EXISTS gerichtsgutachten_verfahrensereignisse (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name    TEXT NOT NULL,
    ereignis_datum  TEXT NOT NULL DEFAULT (datetime('now')),
    ereignis_typ    TEXT NOT NULL DEFAULT '',
    titel           TEXT NOT NULL DEFAULT '',
    beschreibung    TEXT NOT NULL DEFAULT '',
    empfaenger      TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_verf_projekt ON gerichtsgutachten_verfahrensereignisse(projekt_name, ereignis_datum);
"""

EREIGNIS_TYPEN = (
    "akteneinsicht", "parteikommunikation", "ortstermin", "asservat-aufnahme",
    "labor-analyse", "gutachten-versand", "selbstcheck", "befangenheitspruefung",
    "sonstiges",
)


def ensure_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(_SCHEMA)
        # Migrationen für #663 (Privat-Variante) — idempotent
        cur = con.execute("PRAGMA table_info(gerichtsgutachten)")
        cols = {r[1] for r in cur.fetchall()}
        for new_col in ("gutachten_art", "auftraggeber", "auftrags_art",
                        "auftrags_datum", "auftrags_nummer", "honorarvereinbarung"):
            if new_col not in cols:
                default = "'gericht'" if new_col == "gutachten_art" else "''"
                con.execute(f"ALTER TABLE gerichtsgutachten ADD COLUMN {new_col} TEXT NOT NULL DEFAULT {default}")
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# Projekt
# ─────────────────────────────────────────────────────────

def save_gerichts_projekt(db_path: Path, **fields: Any) -> str:
    name = (fields.get("name") or "").strip()
    if not name:
        raise ValueError("name ist Pflicht")
    ensure_db(db_path)
    cols = [
        "gutachten_art", "gericht", "kammer", "aktenzeichen", "klaeger_name", "klaeger_anwalt",
        "beklagter_name", "beklagter_anwalt", "beweisbeschluss_datum",
        "auftraggeber", "auftrags_art", "auftrags_datum", "auftrags_nummer", "honorarvereinbarung",
        "thema", "vertraulichkeit", "sv_name", "sv_zertifizierung", "sv_anschrift",
        "sv_kontakt", "erstellt_von", "status",
    ]
    vals = [fields.get(c, "gericht" if c == "gutachten_art" else "") for c in cols]
    meta_json = json.dumps(fields.get("meta", {}) or {}, ensure_ascii=False)

    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            f"""INSERT INTO gerichtsgutachten
                  (name, {', '.join(cols)}, meta_json)
                VALUES (?, {', '.join('?' for _ in cols)}, ?)
                ON CONFLICT(name) DO UPDATE SET
                  {', '.join(f'{c}=excluded.{c}' for c in cols)},
                  meta_json=excluded.meta_json""",
            [name, *vals, meta_json],
        )
        con.commit()
    finally:
        con.close()
    return name


def load_gerichts_projekt(db_path: Path, name: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        r = con.execute("SELECT * FROM gerichtsgutachten WHERE name=?", (name,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["meta"] = json.loads(d.get("meta_json", "{}") or "{}")
        return d
    finally:
        con.close()


def list_gerichts_projekte(db_path: Path) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT name, aktenzeichen, status, erstellt_am FROM gerichtsgutachten ORDER BY erstellt_am DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def delete_gerichts_projekt(db_path: Path, name: str) -> None:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DELETE FROM gerichtsgutachten WHERE name=?", (name,))
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# Beweisfragen, Befunde, Beurteilungen
# ─────────────────────────────────────────────────────────

def _list_simple(db_path: Path, table: str, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            f"SELECT * FROM {table} WHERE projekt_name=? ORDER BY id",
            (projekt_name,),
        ).fetchall()
        return [_decode_json_fields(dict(r), table) for r in rows]
    finally:
        con.close()


def _decode_json_fields(d: dict[str, Any], table: str) -> dict[str, Any]:
    json_fields = {
        "gerichtsgutachten_beweisfragen": ["referenz_beurteilung_ids"],
        "gerichtsgutachten_befunde": ["asset_ids"],
        "gerichtsgutachten_beurteilungen": ["befund_ids"],
        "gerichtsgutachten_assets": ["parteien_anwesend"],
        "gerichtsgutachten_verfahrensereignisse": ["empfaenger"],
    }
    for f in json_fields.get(table, []):
        try:
            d[f] = json.loads(d.get(f) or "[]")
        except Exception:
            d[f] = []
    return d


def save_beweisfrage(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        refs = json.dumps(f.get("referenz_beurteilung_ids") or [], ensure_ascii=False)
        if f.get("id"):
            con.execute(
                """UPDATE gerichtsgutachten_beweisfragen
                   SET nr=?, frage_text=?, antwort_text=?, antwort_kurz=?, referenz_beurteilung_ids=?
                   WHERE id=?""",
                (int(f.get("nr", 1)), f.get("frage_text", ""), f.get("antwort_text", ""),
                 f.get("antwort_kurz", ""), refs, int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_beweisfragen
                 (projekt_name, nr, frage_text, antwort_text, antwort_kurz, referenz_beurteilung_ids)
               VALUES (?, ?, ?, ?, ?, ?) RETURNING id""",
            (f["projekt_name"], int(f.get("nr", 1)), f.get("frage_text", ""),
             f.get("antwort_text", ""), f.get("antwort_kurz", ""), refs),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def list_beweisfragen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _list_simple(db_path, "gerichtsgutachten_beweisfragen", projekt_name)


def delete_beweisfrage(db_path: Path, beweisfrage_id: int) -> None:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DELETE FROM gerichtsgutachten_beweisfragen WHERE id=?", (beweisfrage_id,))
        con.commit()
    finally:
        con.close()


def save_befund(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        asset_ids = json.dumps(f.get("asset_ids") or [], ensure_ascii=False)
        if f.get("id"):
            con.execute(
                """UPDATE gerichtsgutachten_befunde SET
                   nr=?, titel=?, beschreibung_text=?, methode=?,
                   werkzeug_name=?, werkzeug_version=?, asset_ids=?,
                   erhebung_datum=?, erhebung_ort=?, zeugen_text=?,
                   non_liquet=?, non_liquet_grund=?
                   WHERE id=?""",
                (f.get("nr", ""), f.get("titel", ""), f.get("beschreibung_text", ""),
                 f.get("methode", ""), f.get("werkzeug_name", ""), f.get("werkzeug_version", ""),
                 asset_ids, f.get("erhebung_datum", ""), f.get("erhebung_ort", ""),
                 f.get("zeugen_text", ""), 1 if f.get("non_liquet") else 0,
                 f.get("non_liquet_grund", ""), int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_befunde
                 (projekt_name, nr, titel, beschreibung_text, methode,
                  werkzeug_name, werkzeug_version, asset_ids,
                  erhebung_datum, erhebung_ort, zeugen_text,
                  non_liquet, non_liquet_grund)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (f["projekt_name"], f.get("nr", ""), f.get("titel", ""),
             f.get("beschreibung_text", ""), f.get("methode", ""),
             f.get("werkzeug_name", ""), f.get("werkzeug_version", ""), asset_ids,
             f.get("erhebung_datum", ""), f.get("erhebung_ort", ""), f.get("zeugen_text", ""),
             1 if f.get("non_liquet") else 0, f.get("non_liquet_grund", "")),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def list_befunde(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _list_simple(db_path, "gerichtsgutachten_befunde", projekt_name)


def delete_befund(db_path: Path, befund_id: int) -> None:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DELETE FROM gerichtsgutachten_befunde WHERE id=?", (befund_id,))
        con.commit()
    finally:
        con.close()


def save_beurteilung(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        befund_ids = json.dumps(f.get("befund_ids") or [], ensure_ascii=False)
        if f.get("id"):
            con.execute(
                """UPDATE gerichtsgutachten_beurteilungen SET
                   nr=?, titel=?, befund_ids=?, norm_referenz=?,
                   soll_text=?, ist_text=?, kausalitaet_text=?, bewertung_text=?,
                   non_liquet=?, non_liquet_grund=?
                   WHERE id=?""",
                (f.get("nr", ""), f.get("titel", ""), befund_ids, f.get("norm_referenz", ""),
                 f.get("soll_text", ""), f.get("ist_text", ""), f.get("kausalitaet_text", ""),
                 f.get("bewertung_text", ""), 1 if f.get("non_liquet") else 0,
                 f.get("non_liquet_grund", ""), int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_beurteilungen
                 (projekt_name, nr, titel, befund_ids, norm_referenz,
                  soll_text, ist_text, kausalitaet_text, bewertung_text,
                  non_liquet, non_liquet_grund)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (f["projekt_name"], f.get("nr", ""), f.get("titel", ""), befund_ids,
             f.get("norm_referenz", ""), f.get("soll_text", ""), f.get("ist_text", ""),
             f.get("kausalitaet_text", ""), f.get("bewertung_text", ""),
             1 if f.get("non_liquet") else 0, f.get("non_liquet_grund", "")),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def list_beurteilungen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _list_simple(db_path, "gerichtsgutachten_beurteilungen", projekt_name)


def delete_beurteilung(db_path: Path, beurteilung_id: int) -> None:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DELETE FROM gerichtsgutachten_beurteilungen WHERE id=?", (beurteilung_id,))
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# Assets + Verfahrensereignisse (G1-5)
# ─────────────────────────────────────────────────────────

def save_asset(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        parteien = json.dumps(f.get("parteien_anwesend") or [], ensure_ascii=False)
        if f.get("id"):
            con.execute(
                """UPDATE gerichtsgutachten_assets SET
                   bezeichnung=?, sha256=?, akquisitions_utc=?, akquisitions_ort=?,
                   werkzeug_name=?, werkzeug_version=?, parteien_anwesend=?,
                   gegengezeichnet_von=?, bemerkungen=?, original_dateiname=?
                   WHERE id=?""",
                (f.get("bezeichnung", ""), f.get("sha256", ""), f.get("akquisitions_utc", ""),
                 f.get("akquisitions_ort", ""), f.get("werkzeug_name", ""),
                 f.get("werkzeug_version", ""), parteien, f.get("gegengezeichnet_von", ""),
                 f.get("bemerkungen", ""), f.get("original_dateiname", ""), int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_assets
                 (projekt_name, bezeichnung, sha256, akquisitions_utc, akquisitions_ort,
                  werkzeug_name, werkzeug_version, parteien_anwesend, gegengezeichnet_von,
                  bemerkungen, original_dateiname)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (f["projekt_name"], f.get("bezeichnung", ""), f.get("sha256", ""),
             f.get("akquisitions_utc", ""), f.get("akquisitions_ort", ""),
             f.get("werkzeug_name", ""), f.get("werkzeug_version", ""), parteien,
             f.get("gegengezeichnet_von", ""), f.get("bemerkungen", ""),
             f.get("original_dateiname", "")),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def list_assets(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _list_simple(db_path, "gerichtsgutachten_assets", projekt_name)


def delete_asset(db_path: Path, asset_id: int) -> None:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DELETE FROM gerichtsgutachten_assets WHERE id=?", (asset_id,))
        con.commit()
    finally:
        con.close()


def save_verfahrensereignis(db_path: Path, **f: Any) -> int:
    if f.get("ereignis_typ") and f["ereignis_typ"] not in EREIGNIS_TYPEN:
        # warning only, no exception — allow user-defined types
        pass
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        empf = json.dumps(f.get("empfaenger") or [], ensure_ascii=False)
        # #677 Edit-Support
        if f.get("id"):
            con.execute(
                """UPDATE gerichtsgutachten_verfahrensereignisse SET
                   ereignis_datum=COALESCE(?, ereignis_datum),
                   ereignis_typ=?, titel=?, beschreibung=?, empfaenger=?
                   WHERE id=?""",
                (f.get("ereignis_datum"), f.get("ereignis_typ", ""),
                 f.get("titel", ""), f.get("beschreibung", ""), empf, int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_verfahrensereignisse
                 (projekt_name, ereignis_datum, ereignis_typ, titel, beschreibung, empfaenger)
               VALUES (?, COALESCE(?, datetime('now')), ?, ?, ?, ?) RETURNING id""",
            (f["projekt_name"], f.get("ereignis_datum"), f.get("ereignis_typ", ""),
             f.get("titel", ""), f.get("beschreibung", ""), empf),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def list_verfahrensereignisse(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """SELECT * FROM gerichtsgutachten_verfahrensereignisse
               WHERE projekt_name=? ORDER BY ereignis_datum, id""",
            (projekt_name,),
        ).fetchall()
        return [_decode_json_fields(dict(r), "gerichtsgutachten_verfahrensereignisse") for r in rows]
    finally:
        con.close()


def delete_verfahrensereignis(db_path: Path, ereignis_id: int) -> None:
    ensure_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DELETE FROM gerichtsgutachten_verfahrensereignisse WHERE id=?", (ereignis_id,))
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# SHA-256 Helper für Asset-Upload
# ─────────────────────────────────────────────────────────

def compute_sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()
