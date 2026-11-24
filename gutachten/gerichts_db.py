"""G1-1 bis G1-5 — DB-Tabellen für das BISG-Gerichtsgutachten.

Komplett getrennt von den existierenden gutachten_*-Tabellen (Audit-Bericht).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared import db as _sdb

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
    -- gemeinsam:
    thema             TEXT NOT NULL DEFAULT '',
    vertraulichkeit   TEXT NOT NULL DEFAULT 'STRENG VERTRAULICH',
    sv_name           TEXT NOT NULL DEFAULT '',
    sv_zertifizierung TEXT NOT NULL DEFAULT '',
    sv_anschrift      TEXT NOT NULL DEFAULT '',
    sv_kontakt        TEXT NOT NULL DEFAULT '',
    erstellt_am       TEXT NOT NULL DEFAULT (aics_now()),
    erstellt_von      TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'in_bearbeitung',  -- in_bearbeitung|finalisiert|eingereicht
    meta_json         TEXT NOT NULL DEFAULT '{}'
);

-- G1-2: Beweisfragen
CREATE TABLE IF NOT EXISTS gerichtsgutachten_beweisfragen (
    id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    ereignis_datum  TEXT NOT NULL DEFAULT (aics_now()),
    ereignis_typ    TEXT NOT NULL DEFAULT '',
    titel           TEXT NOT NULL DEFAULT '',
    beschreibung    TEXT NOT NULL DEFAULT '',
    empfaenger      TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_verf_projekt ON gerichtsgutachten_verfahrensereignisse(projekt_name, ereignis_datum);

-- #955: Gutachter-Stammdaten (einmalig anlegen, wiederverwendbar)
CREATE TABLE IF NOT EXISTS gutachter_profile (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    zertifizierung  TEXT NOT NULL DEFAULT '',
    anschrift       TEXT NOT NULL DEFAULT '',
    email           TEXT NOT NULL DEFAULT '',
    telefon         TEXT NOT NULL DEFAULT '',
    ust_id          TEXT NOT NULL DEFAULT '',
    bestellungs_url TEXT NOT NULL DEFAULT '',
    benutzer_id     TEXT NOT NULL DEFAULT '',   -- #2129: Kopplung an ein Benutzerkonto (Sichtbarkeit)
    aktiv           INTEGER NOT NULL DEFAULT 1,
    notizen         TEXT NOT NULL DEFAULT '',
    erstellt_am     TEXT NOT NULL DEFAULT (aics_now())
);

-- #955: Hilfspersonen (§ 407a Abs. 2 ZPO)
CREATE TABLE IF NOT EXISTS hilfspersonen (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    rolle           TEXT NOT NULL DEFAULT '',
    qualifikation   TEXT NOT NULL DEFAULT '',
    email           TEXT NOT NULL DEFAULT '',
    telefon         TEXT NOT NULL DEFAULT '',
    aktiv           INTEGER NOT NULL DEFAULT 1,
    notizen         TEXT NOT NULL DEFAULT '',
    erstellt_am     TEXT NOT NULL DEFAULT (aics_now())
);

-- #955: pro Gutachten verlinkte Hilfspersonen (mit konkreter Aufgabe)
CREATE TABLE IF NOT EXISTS gerichtsgutachten_hilfspersonen (
    projekt_name    TEXT NOT NULL,
    hilfsperson_id  INTEGER NOT NULL,
    aufgabe         TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (projekt_name, hilfsperson_id),
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);

-- #969: Final-Archiv — unveränderlich hochgeladene finalisierte Gutachten
CREATE TABLE IF NOT EXISTS gerichtsgutachten_final_export (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    dateiname       TEXT NOT NULL,
    format          TEXT NOT NULL,           -- 'docx' | 'pdf'
    datei_pfad      TEXT NOT NULL,
    datei_groesse   INTEGER NOT NULL DEFAULT 0,
    sha256          TEXT NOT NULL DEFAULT '',
    hochgeladen_am  TEXT NOT NULL DEFAULT (aics_now()),
    hochgeladen_von TEXT NOT NULL DEFAULT '',
    bemerkung       TEXT NOT NULL DEFAULT '',
    deleted_at      TEXT,
    deleted_by      TEXT,
    deletion_reason TEXT,
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_final_export_projekt ON gerichtsgutachten_final_export(projekt_name);

-- #983: Glossar (Fachbegriffe + Normen, alphabetisch, editierbar)
CREATE TABLE IF NOT EXISTS gerichtsgutachten_glossar (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name  TEXT NOT NULL,
    begriff       TEXT NOT NULL,
    erklaerung    TEXT NOT NULL DEFAULT '',
    typ           TEXT NOT NULL DEFAULT 'begriff',   -- begriff|norm|werkzeug|methode
    quelle        TEXT NOT NULL DEFAULT 'manuell',   -- manuell|seed|auto:<feld>|ki
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE,
    UNIQUE(projekt_name, begriff)
);
CREATE INDEX IF NOT EXISTS idx_glossar_projekt ON gerichtsgutachten_glossar(projekt_name);

-- #957: Custom-Word-Vorlagen (Corporate Design)
CREATE TABLE IF NOT EXISTS gutachten_templates (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    gutachten_art   TEXT NOT NULL DEFAULT 'beide',   -- gericht|privat|beide
    datei_pfad      TEXT NOT NULL,
    datei_sha256    TEXT NOT NULL DEFAULT '',
    variablen_json  TEXT NOT NULL DEFAULT '[]',
    mapping_json    TEXT NOT NULL DEFAULT '{}',
    ist_default     INTEGER NOT NULL DEFAULT 0,
    aktiv           INTEGER NOT NULL DEFAULT 1,
    hochgeladen_am  TEXT NOT NULL DEFAULT (aics_now()),
    hochgeladen_von TEXT NOT NULL DEFAULT '',
    notizen         TEXT NOT NULL DEFAULT ''
);

-- #2108: Prüfer-Register je Gutachten (Hauptgutachter/Zweitprüfer/weitere).
-- Additiv zum primären sv_name/gutachter_profil_id am Projekt. Ein Prüfer
-- kommt aus gutachter_profile (profil_id) ODER ist frei benannt (name).
CREATE TABLE IF NOT EXISTS gerichtsgutachten_pruefer (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name        TEXT NOT NULL,
    gutachter_profil_id INTEGER,
    name                TEXT NOT NULL DEFAULT '',
    rolle               TEXT NOT NULL DEFAULT 'zweitpruefer',  -- hauptgutachter|zweitpruefer|weiterer
    benutzer_id         TEXT NOT NULL DEFAULT '',   -- optionale Kopplung an ein Konto (Vier-Augen)
    aktiv               INTEGER NOT NULL DEFAULT 1,
    erstellt_am         TEXT NOT NULL DEFAULT (aics_now()),
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_pruefer_projekt ON gerichtsgutachten_pruefer(projekt_name);

-- #2110: Gegenseitiges Review — ein Prüfer prüft den Inhalt eines ANDEREN
-- Prüfers (Befund/Beurteilung/Beweisfrage). Vier-Augen in der Fachschicht.
CREATE TABLE IF NOT EXISTS gerichtsgutachten_itemreview (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name        TEXT NOT NULL,
    objekt_art          TEXT NOT NULL DEFAULT '',   -- befund|beurteilung|beweisfrage
    objekt_id           INTEGER NOT NULL DEFAULT 0,
    reviewer_pruefer_id INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'offen',  -- offen|ok|nacharbeit
    kommentar           TEXT NOT NULL DEFAULT '',
    erstellt_am         TEXT NOT NULL DEFAULT (aics_now()),
    erledigt_am         TEXT,
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_itemreview_projekt ON gerichtsgutachten_itemreview(projekt_name, objekt_art, objekt_id);

-- #2111: Mehrfach-Selbstprüfung — je Prüfer eine Befangenheits-/Unabhängigkeits-
-- Selbstprüfung; bestaetigt_json hält die gegenseitigen Bestätigungen.
CREATE TABLE IF NOT EXISTS gerichtsgutachten_selbstpruefung (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    pruefer_id      INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'offen',   -- bestanden|hinweis|issues|offen
    headline        TEXT NOT NULL DEFAULT '',
    antworten_json  TEXT NOT NULL DEFAULT '{}',
    bestaetigt_json TEXT NOT NULL DEFAULT '[]',      -- [{pruefer_id, am}]
    erstellt_am     TEXT NOT NULL DEFAULT (aics_now()),
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE,
    UNIQUE (projekt_name, pruefer_id)
);
CREATE INDEX IF NOT EXISTS idx_selbstpruef_projekt ON gerichtsgutachten_selbstpruefung(projekt_name);

-- #2112: am Gutachten hinterlegte Normen (ISO/IEC, DIN EN, BSI IT-Grundschutz).
-- Trägt die Rechts-/Methodengrundlage, insb. beim Privatgutachten (#2113).
CREATE TABLE IF NOT EXISTS gerichtsgutachten_normen (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name  TEXT NOT NULL,
    norm_id       TEXT NOT NULL DEFAULT '',   -- id aus normen.json; leer bei freier Norm
    norm_titel    TEXT NOT NULL DEFAULT '',
    version       TEXT NOT NULL DEFAULT '',
    quelle        TEXT NOT NULL DEFAULT 'bibliothek',  -- bibliothek|frei
    notiz         TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_gnormen_projekt ON gerichtsgutachten_normen(projekt_name);

-- #2115: eigene Referenz-Dokumente je Gutachten (Textkorpus für die KI-Recherche).
-- Getrennt von den Asservaten (die sind gehashte Beweismittel, kein Textkorpus).
CREATE TABLE IF NOT EXISTS gerichtsgutachten_dokumente (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    dateiname       TEXT NOT NULL DEFAULT '',
    mime            TEXT NOT NULL DEFAULT '',
    sha256          TEXT NOT NULL DEFAULT '',
    datei_pfad      TEXT NOT NULL DEFAULT '',
    text            TEXT NOT NULL DEFAULT '',
    zeichen         INTEGER NOT NULL DEFAULT 0,
    hochgeladen_am  TEXT NOT NULL DEFAULT (aics_now()),
    hochgeladen_von TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (projekt_name) REFERENCES gerichtsgutachten(name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_gdok_projekt ON gerichtsgutachten_dokumente(projekt_name);

-- #2130: Eigene, zur Laufzeit angelegte Normen (der Built-in-Katalog
-- gutachten/data/normen.json ist Teil des Image und nicht beschreibbar).
CREATE TABLE IF NOT EXISTS gutachten_custom_normen (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    norm_key    TEXT NOT NULL UNIQUE,                 -- Katalog-ID (slug)
    titel       TEXT NOT NULL,
    version     TEXT NOT NULL DEFAULT '',
    domain      TEXT NOT NULL DEFAULT '',
    soll_kurz   TEXT NOT NULL DEFAULT '',
    framework   TEXT NOT NULL DEFAULT '',             -- Slot für hinterlegten Normtext (CUSTOM_<slug>)
    aktiv       INTEGER NOT NULL DEFAULT 1,
    erstellt_am TEXT NOT NULL DEFAULT (aics_now())
);
"""

EREIGNIS_TYPEN = (
    "akteneinsicht", "parteikommunikation", "ortstermin", "asservat-aufnahme",
    "labor-analyse", "gutachten-versand", "selbstcheck", "befangenheitspruefung",
    "sonstiges",
)


def ensure_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = _sdb.connect(db_path)
    try:
        con.executescript(_SCHEMA)
        # Migrationen für #663 (Privat-Variante) — idempotent
        for new_col in ("gutachten_art", "auftraggeber", "auftrags_art",
                        "auftrags_datum", "auftrags_nummer"):
            default = "'gericht'" if new_col == "gutachten_art" else "''"
            con.execute(f"ALTER TABLE gerichtsgutachten ADD COLUMN IF NOT EXISTS {new_col} TEXT NOT NULL DEFAULT {default}")
        # #955: Referenz aufs Gutachter-Profil
        con.execute("ALTER TABLE gerichtsgutachten ADD COLUMN IF NOT EXISTS gutachter_profil_id INTEGER")
        # #979: manuelle Reihenfolge der Verfahrensereignisse
        con.execute("ALTER TABLE gerichtsgutachten_verfahrensereignisse ADD COLUMN IF NOT EXISTS reihenfolge INTEGER NOT NULL DEFAULT 0")
        # #2109: Autorenschaft auf Inhalten — welcher Prüfer hat es verfasst.
        for _tab in ("gerichtsgutachten_befunde", "gerichtsgutachten_beurteilungen",
                     "gerichtsgutachten_beweisfragen"):
            con.execute(f"ALTER TABLE {_tab} ADD COLUMN IF NOT EXISTS autor_pruefer_id INTEGER")
        # #2129: Gutachter-Profil ↔ Benutzerkonto (Sichtbarkeits-Scoping)
        con.execute("ALTER TABLE gutachter_profile ADD COLUMN IF NOT EXISTS benutzer_id TEXT NOT NULL DEFAULT ''")
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
    # Der Name ist der Routen-Schlüssel (/gerichts/<name>/...). Schrägstriche
    # brechen das URL-Routing → Projekt wäre nach dem Speichern nicht mehr
    # auswählbar (#944). Aktenzeichen/Auftrags-Nr. haben eigene Felder.
    if "/" in name or "\\" in name:
        raise ValueError("name darf keine Schrägstriche (/ oder \\) enthalten")
    ensure_db(db_path)
    cols = [
        "gutachten_art", "gericht", "kammer", "aktenzeichen", "klaeger_name", "klaeger_anwalt",
        "beklagter_name", "beklagter_anwalt", "beweisbeschluss_datum",
        "auftraggeber", "auftrags_art", "auftrags_datum", "auftrags_nummer",
        "thema", "vertraulichkeit", "sv_name", "sv_zertifizierung", "sv_anschrift",
        "sv_kontakt", "erstellt_von", "status",
    ]
    vals = [fields.get(c, "gericht" if c == "gutachten_art" else "") for c in cols]
    meta_json = json.dumps(fields.get("meta", {}) or {}, ensure_ascii=False)

    con = _sdb.connect(db_path)
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
    con = _sdb.connect(db_path)
    try:
        r = con.execute("SELECT * FROM gerichtsgutachten WHERE name=?", (name,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["meta"] = json.loads(d.get("meta_json", "{}") or "{}")
        return d
    finally:
        con.close()


def _sichtbare_namen(con: Any, benutzer_id: str) -> set[str]:
    """#2129: Projektnamen, bei denen das Konto als SV/Prüfer eingetragen ist.

    Eingetragen heißt: das Konto ist mit einem Gutachter-Profil verknüpft, das
    (a) am Projekt als primärer SV hinterlegt ist (``gutachter_profil_id`` oder
    ``sv_name`` = Profilname) oder (b) als Prüfer geführt wird
    (``gerichtsgutachten_pruefer``) — oder das Konto ist dort direkt als Prüfer
    (``benutzer_id``) eingetragen.
    """
    bid = (benutzer_id or "").strip()
    if not bid:
        return set()
    prof = con.execute(
        "SELECT id, name FROM gutachter_profile WHERE benutzer_id=?", (bid,)
    ).fetchall()
    profil_ids = [int(r["id"]) for r in prof]
    profil_namen = [r["name"] for r in prof]
    namen: set[str] = set()
    if profil_ids:
        ph = ", ".join("?" for _ in profil_ids)
        for r in con.execute(
            f"SELECT name FROM gerichtsgutachten WHERE gutachter_profil_id IN ({ph})",
            tuple(profil_ids),
        ).fetchall():
            namen.add(r["name"])
    if profil_namen:
        ph = ", ".join("?" for _ in profil_namen)
        for r in con.execute(
            f"SELECT name FROM gerichtsgutachten WHERE sv_name IN ({ph})",
            tuple(profil_namen),
        ).fetchall():
            namen.add(r["name"])
    bedingungen = ["benutzer_id=?"]
    params: list[Any] = [bid]
    if profil_ids:
        ph = ", ".join("?" for _ in profil_ids)
        bedingungen.append(f"gutachter_profil_id IN ({ph})")
        params.extend(profil_ids)
    for r in con.execute(
        f"SELECT DISTINCT projekt_name FROM gerichtsgutachten_pruefer WHERE {' OR '.join(bedingungen)}",
        tuple(params),
    ).fetchall():
        namen.add(r["projekt_name"])
    return namen


def list_gerichts_projekte(db_path: Path, nur_benutzer: str | None = None) -> list[dict[str, Any]]:
    """Projektliste. Mit ``nur_benutzer`` (#2129) auf die Gutachten gefiltert,
    bei denen das Konto als SV/Prüfer eingetragen ist."""
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT name, aktenzeichen, status, erstellt_am FROM gerichtsgutachten ORDER BY erstellt_am DESC"
        ).fetchall()
        projekte = [dict(r) for r in rows]
        if nur_benutzer is not None:
            sichtbar = _sichtbare_namen(con, nur_benutzer)
            projekte = [p for p in projekte if p["name"] in sichtbar]
        return projekte
    finally:
        con.close()


def projekt_sichtbar(db_path: Path, projekt_name: str, benutzer_id: str) -> bool:
    """#2129: Darf das Konto dieses eine Gutachten sehen/bearbeiten?"""
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        return projekt_name in _sichtbare_namen(con, benutzer_id)
    finally:
        con.close()


def delete_gerichts_projekt(db_path: Path, name: str) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
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
    con = _sdb.connect(db_path)
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


def _autor_id(f: dict[str, Any]) -> int | None:
    """#2109: Autor-Prüfer-ID aus den Feldern. ``None`` heißt „nicht genannt" —
    beim Update erhält COALESCE dann den bestehenden Autor (Lehre #1771/#1805).
    """
    v = f.get("autor_pruefer_id")
    if v in (None, "", 0, "0"):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def save_beweisfrage(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        refs = json.dumps(f.get("referenz_beurteilung_ids") or [], ensure_ascii=False)
        autor = _autor_id(f)  # #2109 Teil-Update-Schutz: None erhält den Autor
        if f.get("id"):
            con.execute(
                """UPDATE gerichtsgutachten_beweisfragen
                   SET nr=?, frage_text=?, antwort_text=?, antwort_kurz=?, referenz_beurteilung_ids=?,
                       autor_pruefer_id=COALESCE(?, autor_pruefer_id)
                   WHERE id=?""",
                (int(f.get("nr", 1)), f.get("frage_text", ""), f.get("antwort_text", ""),
                 f.get("antwort_kurz", ""), refs, autor, int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_beweisfragen
                 (projekt_name, nr, frage_text, antwort_text, antwort_kurz, referenz_beurteilung_ids, autor_pruefer_id)
               VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (f["projekt_name"], int(f.get("nr", 1)), f.get("frage_text", ""),
             f.get("antwort_text", ""), f.get("antwort_kurz", ""), refs, autor),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def list_beweisfragen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    # #2126: nach Nr sortiert — die Nr ist die maßgebliche Reihenfolge (auch im
    # Report), nicht die Anlage-Reihenfolge. Up/Down in der UI tauscht die Nr.
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gerichtsgutachten_beweisfragen WHERE projekt_name=? ORDER BY nr, id",
            (projekt_name,),
        ).fetchall()
        return [_decode_json_fields(dict(r), "gerichtsgutachten_beweisfragen") for r in rows]
    finally:
        con.close()


def delete_beweisfrage(db_path: Path, beweisfrage_id: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_beweisfragen WHERE id=?", (beweisfrage_id,))
        con.commit()
    finally:
        con.close()


def save_befund(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        asset_ids = json.dumps(f.get("asset_ids") or [], ensure_ascii=False)
        autor = _autor_id(f)  # #2109 Teil-Update-Schutz: None erhält den Autor
        if f.get("id"):
            con.execute(
                """UPDATE gerichtsgutachten_befunde SET
                   nr=?, titel=?, beschreibung_text=?, methode=?,
                   werkzeug_name=?, werkzeug_version=?, asset_ids=?,
                   erhebung_datum=?, erhebung_ort=?, zeugen_text=?,
                   non_liquet=?, non_liquet_grund=?,
                   autor_pruefer_id=COALESCE(?, autor_pruefer_id)
                   WHERE id=?""",
                (f.get("nr", ""), f.get("titel", ""), f.get("beschreibung_text", ""),
                 f.get("methode", ""), f.get("werkzeug_name", ""), f.get("werkzeug_version", ""),
                 asset_ids, f.get("erhebung_datum", ""), f.get("erhebung_ort", ""),
                 f.get("zeugen_text", ""), 1 if f.get("non_liquet") else 0,
                 f.get("non_liquet_grund", ""), autor, int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_befunde
                 (projekt_name, nr, titel, beschreibung_text, methode,
                  werkzeug_name, werkzeug_version, asset_ids,
                  erhebung_datum, erhebung_ort, zeugen_text,
                  non_liquet, non_liquet_grund, autor_pruefer_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (f["projekt_name"], f.get("nr", ""), f.get("titel", ""),
             f.get("beschreibung_text", ""), f.get("methode", ""),
             f.get("werkzeug_name", ""), f.get("werkzeug_version", ""), asset_ids,
             f.get("erhebung_datum", ""), f.get("erhebung_ort", ""), f.get("zeugen_text", ""),
             1 if f.get("non_liquet") else 0, f.get("non_liquet_grund", ""), autor),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def list_befunde(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _list_simple(db_path, "gerichtsgutachten_befunde", projekt_name)


def delete_befund(db_path: Path, befund_id: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_befunde WHERE id=?", (befund_id,))
        con.commit()
    finally:
        con.close()


def save_beurteilung(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        befund_ids = json.dumps(f.get("befund_ids") or [], ensure_ascii=False)
        autor = _autor_id(f)  # #2109 Teil-Update-Schutz: None erhält den Autor
        if f.get("id"):
            con.execute(
                """UPDATE gerichtsgutachten_beurteilungen SET
                   nr=?, titel=?, befund_ids=?, norm_referenz=?,
                   soll_text=?, ist_text=?, kausalitaet_text=?, bewertung_text=?,
                   non_liquet=?, non_liquet_grund=?,
                   autor_pruefer_id=COALESCE(?, autor_pruefer_id)
                   WHERE id=?""",
                (f.get("nr", ""), f.get("titel", ""), befund_ids, f.get("norm_referenz", ""),
                 f.get("soll_text", ""), f.get("ist_text", ""), f.get("kausalitaet_text", ""),
                 f.get("bewertung_text", ""), 1 if f.get("non_liquet") else 0,
                 f.get("non_liquet_grund", ""), autor, int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_beurteilungen
                 (projekt_name, nr, titel, befund_ids, norm_referenz,
                  soll_text, ist_text, kausalitaet_text, bewertung_text,
                  non_liquet, non_liquet_grund, autor_pruefer_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (f["projekt_name"], f.get("nr", ""), f.get("titel", ""), befund_ids,
             f.get("norm_referenz", ""), f.get("soll_text", ""), f.get("ist_text", ""),
             f.get("kausalitaet_text", ""), f.get("bewertung_text", ""),
             1 if f.get("non_liquet") else 0, f.get("non_liquet_grund", ""), autor),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def list_beurteilungen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _list_simple(db_path, "gerichtsgutachten_beurteilungen", projekt_name)


def delete_beurteilung(db_path: Path, beurteilung_id: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
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
    con = _sdb.connect(db_path)
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
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def list_assets(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    return _list_simple(db_path, "gerichtsgutachten_assets", projekt_name)


def delete_asset(db_path: Path, asset_id: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
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
    con = _sdb.connect(db_path)
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
        # #979: neues Ereignis ans Ende der manuellen Reihenfolge.
        nxt = con.execute(
            "SELECT COALESCE(MAX(reihenfolge), 0) + 1 FROM gerichtsgutachten_verfahrensereignisse WHERE projekt_name=?",
            (f["projekt_name"],),
        ).fetchone()[0]
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_verfahrensereignisse
                 (projekt_name, ereignis_datum, ereignis_typ, titel, beschreibung, empfaenger, reihenfolge)
               VALUES (?, COALESCE(?, aics_now()), ?, ?, ?, ?, ?) RETURNING id""",
            (f["projekt_name"], f.get("ereignis_datum"), f.get("ereignis_typ", ""),
             f.get("titel", ""), f.get("beschreibung", ""), empf, int(nxt)),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def list_verfahrensereignisse(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            """SELECT * FROM gerichtsgutachten_verfahrensereignisse
               WHERE projekt_name=? ORDER BY reihenfolge, ereignis_datum, id""",
            (projekt_name,),
        ).fetchall()
        return [_decode_json_fields(dict(r), "gerichtsgutachten_verfahrensereignisse") for r in rows]
    finally:
        con.close()


def reorder_verfahrensereignisse(db_path: Path, projekt_name: str, ordered_ids: list[int]) -> None:
    """Setzt reihenfolge=Index gemäß ordered_ids (#979)."""
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        for idx, eid in enumerate(ordered_ids):
            con.execute(
                "UPDATE gerichtsgutachten_verfahrensereignisse SET reihenfolge=? WHERE id=? AND projekt_name=?",
                (idx, int(eid), projekt_name),
            )
        con.commit()
    finally:
        con.close()


def delete_verfahrensereignis(db_path: Path, ereignis_id: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
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


# ─────────────────────────────────────────────────────────
# #969 — Final-Archiv
# ─────────────────────────────────────────────────────────

def save_final_export(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_final_export
                   (projekt_name, dateiname, format, datei_pfad, datei_groesse,
                    sha256, hochgeladen_von, bemerkung)
               VALUES (?,?,?,?,?,?,?,?)""",
            (f["projekt_name"], f.get("dateiname", ""), f.get("format", ""),
             f.get("datei_pfad", ""), int(f.get("datei_groesse", 0)),
             f.get("sha256", ""), f.get("hochgeladen_von", ""), f.get("bemerkung", "")),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def list_final_exports(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gerichtsgutachten_final_export WHERE projekt_name=? ORDER BY hochgeladen_am DESC",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_final_export(db_path: Path, fid: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        row = con.execute("SELECT * FROM gerichtsgutachten_final_export WHERE id=?", (int(fid),)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def soft_delete_final_export(db_path: Path, fid: int, deleted_by: str, reason: str) -> None:
    """Soft-Delete: DB-Zeile bleibt (SHA-256 + Nachweis), Datei wird vom Caller gelöscht."""
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute(
            """UPDATE gerichtsgutachten_final_export
               SET deleted_at=aics_now(), deleted_by=?, deletion_reason=? WHERE id=?""",
            (deleted_by, reason, int(fid)),
        )
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# #955 — Stammdaten: Gutachter-Profile + Hilfspersonen
# ─────────────────────────────────────────────────────────

_GUTACHTER_COLS = ("name", "zertifizierung", "anschrift", "email", "telefon",
                   "ust_id", "bestellungs_url", "benutzer_id", "aktiv", "notizen")
_HILFS_COLS = ("name", "rolle", "qualifikation", "email", "telefon", "aktiv", "notizen")


def _save_stammdaten(db_path: Path, table: str, cols: tuple, fields: dict) -> int:
    name = (fields.get("name") or "").strip()
    if not name:
        raise ValueError("name ist Pflicht")
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        vals = [int(fields.get(c, 1)) if c == "aktiv" else fields.get(c, "") for c in cols]
        rid = fields.get("id")
        if rid:
            set_clause = ", ".join(f"{c}=?" for c in cols)
            con.execute(f"UPDATE {table} SET {set_clause} WHERE id=?", (*vals, int(rid)))
            con.commit()
            return int(rid)
        placeholders = ", ".join("?" for _ in cols)
        cur = con.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})", vals)
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def _list_stammdaten(db_path: Path, table: str, only_active: bool) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        q = f"SELECT * FROM {table}"
        if only_active:
            q += " WHERE aktiv=1"
        q += " ORDER BY name"
        return [dict(r) for r in con.execute(q).fetchall()]
    finally:
        con.close()


def _delete_stammdaten(db_path: Path, table: str, rid: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute(f"DELETE FROM {table} WHERE id=?", (int(rid),))
        con.commit()
    finally:
        con.close()


def list_gutachter(db_path: Path, only_active: bool = False) -> list[dict[str, Any]]:
    return _list_stammdaten(db_path, "gutachter_profile", only_active)


def save_gutachter(db_path: Path, **fields: Any) -> int:
    return _save_stammdaten(db_path, "gutachter_profile", _GUTACHTER_COLS, fields)


def delete_gutachter(db_path: Path, rid: int) -> None:
    _delete_stammdaten(db_path, "gutachter_profile", rid)


# ─────────────────────────────────────────────────────────
# #2130: Eigene Normen (Laufzeit-Katalog neben normen.json)
# ─────────────────────────────────────────────────────────

import re as _re  # noqa: E402


def _norm_slug(titel: str, con: Any) -> str:
    """Eindeutigen Katalog-Schlüssel aus dem Titel ableiten (custom-…)."""
    basis = _re.sub(r"[^a-z0-9]+", "-", (titel or "").lower()).strip("-")[:48] or "norm"
    slug = f"custom-{basis}"
    kandidat = slug
    i = 2
    while con.execute("SELECT 1 FROM gutachten_custom_normen WHERE norm_key=?",
                      (kandidat,)).fetchone():
        kandidat = f"{slug}-{i}"
        i += 1
    return kandidat


def list_custom_normen(db_path: Path, only_active: bool = True) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        q = "SELECT * FROM gutachten_custom_normen"
        if only_active:
            q += " WHERE aktiv=1"
        q += " ORDER BY titel"
        return [dict(r) for r in con.execute(q).fetchall()]
    finally:
        con.close()


def save_custom_norm(db_path: Path, **fields: Any) -> dict[str, Any]:
    """Legt eine eigene Norm an (oder ändert sie). Vergibt norm_key + framework."""
    titel = (fields.get("titel") or "").strip()
    if not titel:
        raise ValueError("titel ist Pflicht")
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rid = fields.get("id")
        version = (fields.get("version") or "").strip()
        domain = (fields.get("domain") or "").strip()
        soll_kurz = (fields.get("soll_kurz") or "").strip()
        if rid:
            con.execute(
                "UPDATE gutachten_custom_normen SET titel=?, version=?, domain=?, soll_kurz=? WHERE id=?",
                (titel, version, domain, soll_kurz, int(rid)))
            con.commit()
            row = con.execute("SELECT * FROM gutachten_custom_normen WHERE id=?", (int(rid),)).fetchone()
            return dict(row) if row else {"id": int(rid)}
        norm_key = _norm_slug(titel, con)   # beginnt mit "custom-"
        framework = norm_key.replace("-", "_").upper()   # → CUSTOM_…
        cur = con.execute(
            "INSERT INTO gutachten_custom_normen (norm_key, titel, version, domain, soll_kurz, framework) "
            "VALUES (?,?,?,?,?,?)",
            (norm_key, titel, version, domain, soll_kurz, framework))
        con.commit()
        new_id = int(cur.lastrowid or 0)
        return {"id": new_id, "norm_key": norm_key, "titel": titel, "version": version,
                "domain": domain, "soll_kurz": soll_kurz, "framework": framework}
    finally:
        con.close()


def get_custom_norm(db_path: Path, norm_key: str) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        r = con.execute("SELECT * FROM gutachten_custom_normen WHERE norm_key=?",
                        (norm_key,)).fetchone()
        return dict(r) if r else None
    finally:
        con.close()


def delete_custom_norm(db_path: Path, rid: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gutachten_custom_normen WHERE id=?", (int(rid),))
        con.commit()
    finally:
        con.close()


def list_hilfspersonen(db_path: Path, only_active: bool = False) -> list[dict[str, Any]]:
    return _list_stammdaten(db_path, "hilfspersonen", only_active)


def save_hilfsperson(db_path: Path, **fields: Any) -> int:
    return _save_stammdaten(db_path, "hilfspersonen", _HILFS_COLS, fields)


def delete_hilfsperson(db_path: Path, rid: int) -> None:
    _delete_stammdaten(db_path, "hilfspersonen", rid)


def link_hilfspersonen(db_path: Path, projekt_name: str, entries: list[dict]) -> None:
    """Setzt die Hilfspersonen-Zuordnung eines Gutachtens (ersetzt bestehende).

    entries: ``[{"hilfsperson_id": int, "aufgabe": str}, ...]``.
    """
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_hilfspersonen WHERE projekt_name=?", (projekt_name,))
        for e in entries or []:
            hid = e.get("hilfsperson_id")
            if not hid:
                continue
            con.execute(
                "INSERT INTO gerichtsgutachten_hilfspersonen (projekt_name, hilfsperson_id, aufgabe) VALUES (?,?,?) "
                "ON CONFLICT(projekt_name, hilfsperson_id) DO UPDATE SET aufgabe=excluded.aufgabe",
                (projekt_name, int(hid), e.get("aufgabe", "")),
            )
        con.commit()
    finally:
        con.close()


def list_hilfspersonen_for_projekt(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Hilfspersonen eines Gutachtens inkl. Stammdaten + projektbezogener Aufgabe."""
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            """SELECT h.id, h.name, h.rolle, h.qualifikation, l.aufgabe
               FROM gerichtsgutachten_hilfspersonen l
               JOIN hilfspersonen h ON h.id = l.hilfsperson_id
               WHERE l.projekt_name=? ORDER BY h.name""",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# #957 — Custom-Word-Vorlagen
# ─────────────────────────────────────────────────────────

def list_templates(db_path: Path, only_active: bool = False) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        q = "SELECT * FROM gutachten_templates"
        if only_active:
            q += " WHERE aktiv=1"
        q += " ORDER BY name"
        return [dict(r) for r in con.execute(q).fetchall()]
    finally:
        con.close()


def get_template(db_path: Path, tid: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        row = con.execute("SELECT * FROM gutachten_templates WHERE id=?", (int(tid),)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def save_template(db_path: Path, **fields: Any) -> int:
    """Insert/Update eines Vorlagen-Metadatensatzes. Pflicht: name, datei_pfad."""
    name = (fields.get("name") or "").strip()
    if not name:
        raise ValueError("name ist Pflicht")
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        cols = ("name", "gutachten_art", "datei_pfad", "datei_sha256",
                "variablen_json", "mapping_json", "ist_default", "aktiv",
                "hochgeladen_von", "notizen")
        vals = []
        for c in cols:
            if c in ("ist_default", "aktiv"):
                vals.append(int(fields.get(c, 1 if c == "aktiv" else 0)))
            elif c == "gutachten_art":
                vals.append(fields.get(c, "beide"))
            else:
                vals.append(fields.get(c, ""))
        tid = fields.get("id")
        if tid:
            set_clause = ", ".join(f"{c}=?" for c in cols)
            con.execute(f"UPDATE gutachten_templates SET {set_clause} WHERE id=?", (*vals, int(tid)))
            con.commit()
            return int(tid)
        placeholders = ", ".join("?" for _ in cols)
        cur = con.execute(
            f"INSERT INTO gutachten_templates ({', '.join(cols)}) VALUES ({placeholders})", vals)
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_template(db_path: Path, tid: int) -> str | None:
    """Löscht den Metadatensatz und liefert den Dateipfad zurück (zum Entfernen der Datei)."""
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        row = con.execute("SELECT datei_pfad FROM gutachten_templates WHERE id=?", (int(tid),)).fetchone()
        con.execute("DELETE FROM gutachten_templates WHERE id=?", (int(tid),))
        con.commit()
        return row["datei_pfad"] if row else None
    finally:
        con.close()


def set_default_template(db_path: Path, tid: int, gutachten_art: str = "beide") -> None:
    """Setzt eine Vorlage als Default für eine Art (entfernt das Flag bei anderen derselben Art)."""
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("UPDATE gutachten_templates SET ist_default=0 WHERE gutachten_art=?", (gutachten_art,))
        con.execute("UPDATE gutachten_templates SET ist_default=1, gutachten_art=? WHERE id=?",
                    (gutachten_art, int(tid)))
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# #983/#984 — Glossar
# ─────────────────────────────────────────────────────────

def list_glossar(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Glossar eines Gutachtens, alphabetisch (case-insensitiv) nach Begriff."""
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gerichtsgutachten_glossar WHERE projekt_name=? ORDER BY LOWER(begriff)",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_glossar_eintrag(db_path: Path, **f: Any) -> int:
    begriff = (f.get("begriff") or "").strip()
    if not begriff:
        raise ValueError("begriff ist Pflicht")
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        if f.get("id"):
            con.execute(
                "UPDATE gerichtsgutachten_glossar SET begriff=?, erklaerung=?, typ=?, quelle=? WHERE id=?",
                (begriff, f.get("erklaerung", ""), f.get("typ", "begriff"),
                 f.get("quelle", "manuell"), int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_glossar (projekt_name, begriff, erklaerung, typ, quelle)
               VALUES (?,?,?,?,?)""",
            (f["projekt_name"], begriff, f.get("erklaerung", ""),
             f.get("typ", "begriff"), f.get("quelle", "manuell")),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_glossar_eintrag(db_path: Path, eid: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_glossar WHERE id=?", (int(eid),))
        con.commit()
    finally:
        con.close()


def upsert_glossar_eintrag(db_path: Path, projekt_name: str, begriff: str,
                           erklaerung: str, typ: str, quelle: str) -> str:
    """Idempotenter Upsert für die Auto-Generierung (#984).

    Bewahrt manuell editierte Einträge: existiert der Begriff bereits mit
    quelle='manuell', wird NICHTS überschrieben. Liefert 'inserted'|'updated'|'kept'.
    """
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        row = con.execute(
            "SELECT id, quelle, erklaerung FROM gerichtsgutachten_glossar WHERE projekt_name=? AND LOWER(begriff)=LOWER(?)",
            (projekt_name, begriff),
        ).fetchone()
        if row is None:
            con.execute(
                "INSERT INTO gerichtsgutachten_glossar (projekt_name, begriff, erklaerung, typ, quelle) VALUES (?,?,?,?,?)",
                (projekt_name, begriff, erklaerung, typ, quelle),
            )
            con.commit()
            return "inserted"
        if row["quelle"] == "manuell":
            return "kept"   # manuelle Bearbeitung niemals überschreiben
        # nur fehlende Erklärung ergänzen, sonst unverändert
        if not (row["erklaerung"] or "").strip() and erklaerung:
            con.execute("UPDATE gerichtsgutachten_glossar SET erklaerung=?, typ=?, quelle=? WHERE id=?",
                        (erklaerung, typ, quelle, row["id"]))
            con.commit()
            return "updated"
        return "kept"
    finally:
        con.close()


def build_glossar_candidates(db_path: Path, projekt_name: str) -> list[dict[str, str]]:
    """Extrahiert Glossar-Kandidaten aus den DB-Daten + Seed-Katalog (#984).

    Quellen: Normen (Beurteilungen.norm_referenz), Werkzeuge (Befunde.werkzeug_name),
    Methoden (Befunde.methode). Seed-Treffer liefern fertige Erklärungen.
    """
    import re as _re
    from gutachten.glossar_seed import lookup as _seed_lookup
    cand: dict[str, dict[str, str]] = {}

    def _add(begriff: str, typ: str, quelle: str):
        begriff = (begriff or "").strip()
        if not begriff:
            return
        seed = _seed_lookup(begriff)
        key = (seed["begriff"] if seed else begriff)
        if key.lower() in {k.lower() for k in cand}:
            return
        cand[key] = {
            "begriff": key,
            "typ": seed["typ"] if seed else typ,
            "erklaerung": seed["erklaerung"] if seed else "",
            "quelle": "seed" if seed else quelle,
        }

    # Normen aus Beurteilungen — können mehrere kommagetrennt sein
    for u in list_beurteilungen(db_path, projekt_name):
        for ref in _re.split(r"[;,]", u.get("norm_referenz", "") or ""):
            _add(ref, "norm", "auto:norm_referenz")
    # Werkzeuge + Methoden aus Befunden
    for b in list_befunde(db_path, projekt_name):
        _add(b.get("werkzeug_name", ""), "werkzeug", "auto:werkzeug")
        _add(b.get("methode", ""), "methode", "auto:methode")
    return sorted(cand.values(), key=lambda x: x["begriff"].lower())


def generate_glossar(db_path: Path, projekt_name: str) -> dict[str, int]:
    """Erzeugt/aktualisiert Glossar-Einträge aus den Kandidaten (idempotent, #984)."""
    stats = {"inserted": 0, "updated": 0, "kept": 0}
    for c in build_glossar_candidates(db_path, projekt_name):
        action = upsert_glossar_eintrag(db_path, projekt_name, c["begriff"],
                                        c["erklaerung"], c["typ"], c["quelle"])
        stats[action] = stats.get(action, 0) + 1
    return stats


# ─────────────────────────────────────────────────────────
# #2108 Prüfer-Register
# ─────────────────────────────────────────────────────────

PRUEFER_ROLLEN = ("hauptgutachter", "zweitpruefer", "weiterer")


def list_pruefer(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gerichtsgutachten_pruefer WHERE projekt_name=? ORDER BY "
            # Hauptgutachter zuerst, dann nach Anlage
            "CASE rolle WHEN 'hauptgutachter' THEN 0 WHEN 'zweitpruefer' THEN 1 ELSE 2 END, id",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_pruefer(db_path: Path, **f: Any) -> int:
    """Legt einen Prüfer an oder ändert ihn. Genau EIN Hauptgutachter je Projekt."""
    ensure_db(db_path)
    projekt = f["projekt_name"]
    rolle = (f.get("rolle") or "zweitpruefer").strip()
    if rolle not in PRUEFER_ROLLEN:
        raise ValueError(f"unbekannte Rolle: {rolle}")
    name = (f.get("name") or "").strip()
    profil_id = f.get("gutachter_profil_id")
    profil_id = int(profil_id) if profil_id not in (None, "", 0, "0") else None
    if not name and profil_id is not None:
        # Name aus dem Profil ziehen, damit die Anzeige nie leer ist
        prof = next((p for p in list_gutachter(db_path) if int(p["id"]) == profil_id), None)
        if prof:
            name = prof.get("name", "")
    if not name:
        raise ValueError("Prüfer braucht einen Namen oder ein Gutachter-Profil")
    con = _sdb.connect(db_path)
    try:
        if rolle == "hauptgutachter":
            # Rollen-Invariante: nur ein Hauptgutachter. Vorhandenen (außer sich
            # selbst) auf 'weiterer' zurückstufen, statt den Anlegevorgang zu
            # verweigern — die Entscheidung des Nutzers gewinnt.
            own = int(f["id"]) if f.get("id") else -1
            con.execute(
                "UPDATE gerichtsgutachten_pruefer SET rolle='weiterer' "
                "WHERE projekt_name=? AND rolle='hauptgutachter' AND id<>?",
                (projekt, own),
            )
        if f.get("id"):
            con.execute(
                "UPDATE gerichtsgutachten_pruefer SET gutachter_profil_id=?, name=?, "
                "rolle=?, benutzer_id=COALESCE(?, benutzer_id), aktiv=? WHERE id=?",
                (profil_id, name, rolle, (f.get("benutzer_id") or None),
                 1 if f.get("aktiv", 1) else 0, int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            "INSERT INTO gerichtsgutachten_pruefer (projekt_name, gutachter_profil_id, "
            "name, rolle, benutzer_id, aktiv) VALUES (?,?,?,?,?,?) RETURNING id",
            (projekt, profil_id, name, rolle, f.get("benutzer_id", ""),
             1 if f.get("aktiv", 1) else 0),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def get_pruefer(db_path: Path, pruefer_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM gerichtsgutachten_pruefer WHERE id=?", (int(pruefer_id),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def delete_pruefer(db_path: Path, pruefer_id: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_pruefer WHERE id=?", (int(pruefer_id),))
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# #2110 Gegenseitiges Review (Item-Level)
# ─────────────────────────────────────────────────────────

ITEMREVIEW_ARTEN = ("befund", "beurteilung", "beweisfrage")
ITEMREVIEW_STATUS = ("offen", "ok", "nacharbeit")

_ITEMREVIEW_TABELLE = {
    "befund": "gerichtsgutachten_befunde",
    "beurteilung": "gerichtsgutachten_beurteilungen",
    "beweisfrage": "gerichtsgutachten_beweisfragen",
}


def objekt_autor_pruefer_id(db_path: Path, objekt_art: str, objekt_id: int) -> int | None:
    """Autor-Prüfer-ID des referenzierten Inhalts (für den Vier-Augen-Riegel)."""
    tab = _ITEMREVIEW_TABELLE.get(objekt_art)
    if not tab:
        return None
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        row = con.execute(f"SELECT autor_pruefer_id FROM {tab} WHERE id=?", (int(objekt_id),)).fetchone()
        if not row:
            return None
        v = row[0]
        return int(v) if v not in (None, "") else None
    finally:
        con.close()


def list_itemreviews(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gerichtsgutachten_itemreview WHERE projekt_name=? ORDER BY id",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_itemreview(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    art = (f.get("objekt_art") or "").strip()
    if art not in ITEMREVIEW_ARTEN:
        raise ValueError(f"unbekannte objekt_art: {art}")
    status = (f.get("status") or "offen").strip()
    if status not in ITEMREVIEW_STATUS:
        raise ValueError(f"unbekannter status: {status}")
    erledigt = "aics_now()" if status in ("ok", "nacharbeit") else "NULL"
    con = _sdb.connect(db_path)
    try:
        if f.get("id"):
            con.execute(
                f"UPDATE gerichtsgutachten_itemreview SET status=?, kommentar=?, "
                f"erledigt_am=CASE WHEN ?='offen' THEN NULL ELSE {erledigt} END WHERE id=?",
                (status, f.get("kommentar", ""), status, int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            f"INSERT INTO gerichtsgutachten_itemreview (projekt_name, objekt_art, objekt_id, "
            f"reviewer_pruefer_id, status, kommentar, erledigt_am) "
            f"VALUES (?,?,?,?,?,?,{erledigt}) RETURNING id",
            (f["projekt_name"], art, int(f.get("objekt_id", 0)),
             int(f.get("reviewer_pruefer_id", 0)), status, f.get("kommentar", "")),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def get_itemreview(db_path: Path, review_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM gerichtsgutachten_itemreview WHERE id=?", (int(review_id),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def delete_itemreview(db_path: Path, review_id: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_itemreview WHERE id=?", (int(review_id),))
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# #2111 Mehrfach-Selbstprüfung
# ─────────────────────────────────────────────────────────

def list_selbstpruefung(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gerichtsgutachten_selbstpruefung WHERE projekt_name=? ORDER BY id",
            (projekt_name,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["antworten"] = json.loads(d.get("antworten_json") or "{}")
            except Exception:
                d["antworten"] = {}
            try:
                d["bestaetigt"] = json.loads(d.get("bestaetigt_json") or "[]")
            except Exception:
                d["bestaetigt"] = []
            out.append(d)
        return out
    finally:
        con.close()


def save_selbstpruefung(db_path: Path, **f: Any) -> int:
    """Legt die Selbstprüfung eines Prüfers ab (ein Datensatz je Prüfer, upsert)."""
    ensure_db(db_path)
    projekt = f["projekt_name"]
    pruefer_id = int(f["pruefer_id"])
    antworten = json.dumps(f.get("antworten") or {}, ensure_ascii=False)
    con = _sdb.connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO gerichtsgutachten_selbstpruefung "
            "(projekt_name, pruefer_id, status, headline, antworten_json) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(projekt_name, pruefer_id) DO UPDATE SET "
            "status=excluded.status, headline=excluded.headline, "
            "antworten_json=excluded.antworten_json, "
            # neue Antworten heben die alten Bestätigungen auf — bestätigt wurde
            # ein anderer Stand (Lehre #1868: setze_marker räumt die Bestätigung mit weg)
            "bestaetigt_json='[]', erstellt_am=aics_now() "
            "RETURNING id",
            (projekt, pruefer_id, f.get("status", "offen"), f.get("headline", ""), antworten),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def get_selbstpruefung(db_path: Path, sp_id: int) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM gerichtsgutachten_selbstpruefung WHERE id=?", (int(sp_id),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def bestaetige_selbstpruefung(db_path: Path, sp_id: int, pruefer_id: int) -> None:
    """Ein ANDERER Prüfer bestätigt die Selbstprüfung (Vier-Augen prüft der Aufrufer)."""
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        row = con.execute(
            "SELECT bestaetigt_json FROM gerichtsgutachten_selbstpruefung WHERE id=?", (int(sp_id),)
        ).fetchone()
        if not row:
            raise ValueError("Selbstprüfung nicht gefunden")
        try:
            best = json.loads(row[0] or "[]")
        except Exception:
            best = []
        if not any(int(b.get("pruefer_id", -1)) == int(pruefer_id) for b in best):
            jetzt = con.execute("SELECT aics_now()").fetchone()[0]
            best.append({"pruefer_id": int(pruefer_id), "am": jetzt})
        con.execute(
            "UPDATE gerichtsgutachten_selbstpruefung SET bestaetigt_json=? WHERE id=?",
            (json.dumps(best, ensure_ascii=False), int(sp_id)),
        )
        con.commit()
    finally:
        con.close()


def delete_selbstpruefung(db_path: Path, sp_id: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_selbstpruefung WHERE id=?", (int(sp_id),))
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# #2112 Projekt-Normen (ISO/BSI hinterlegbar)
# ─────────────────────────────────────────────────────────

def list_projekt_normen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gerichtsgutachten_normen WHERE projekt_name=? ORDER BY id",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_projekt_norm(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        if f.get("id"):
            con.execute(
                "UPDATE gerichtsgutachten_normen SET norm_id=?, norm_titel=?, version=?, "
                "quelle=?, notiz=? WHERE id=?",
                (f.get("norm_id", ""), f.get("norm_titel", ""), f.get("version", ""),
                 f.get("quelle", "bibliothek"), f.get("notiz", ""), int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            "INSERT INTO gerichtsgutachten_normen (projekt_name, norm_id, norm_titel, "
            "version, quelle, notiz) VALUES (?,?,?,?,?,?) RETURNING id",
            (f["projekt_name"], f.get("norm_id", ""), f.get("norm_titel", ""),
             f.get("version", ""), f.get("quelle", "bibliothek"), f.get("notiz", "")),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def delete_projekt_norm(db_path: Path, norm_row_id: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_normen WHERE id=?", (int(norm_row_id),))
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# #2115 Projekt-Dokumente (KI-Suchkorpus)
# ─────────────────────────────────────────────────────────

def list_dokumente(db_path: Path, projekt_name: str, *, mit_text: bool = False) -> list[dict[str, Any]]:
    """Dokument-Liste. Ohne ``mit_text`` ohne den Volltext (für die Übersicht)."""
    ensure_db(db_path)
    spalten = ("id, projekt_name, dateiname, mime, sha256, datei_pfad, zeichen, "
               "hochgeladen_am, hochgeladen_von" + (", text" if mit_text else ""))
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            f"SELECT {spalten} FROM gerichtsgutachten_dokumente WHERE projekt_name=? ORDER BY id",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_dokument(db_path: Path, **f: Any) -> int:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        text = f.get("text", "") or ""
        cur = con.execute(
            "INSERT INTO gerichtsgutachten_dokumente (projekt_name, dateiname, mime, "
            "sha256, datei_pfad, text, zeichen, hochgeladen_von) "
            "VALUES (?,?,?,?,?,?,?,?) RETURNING id",
            (f["projekt_name"], f.get("dateiname", ""), f.get("mime", ""),
             f.get("sha256", ""), f.get("datei_pfad", ""), text, len(text),
             f.get("hochgeladen_von", "")),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def get_dokument(db_path: Path, dok_id: int, *, mit_text: bool = False) -> dict[str, Any] | None:
    ensure_db(db_path)
    spalten = ("id, projekt_name, dateiname, mime, sha256, datei_pfad, zeichen, "
               "hochgeladen_am, hochgeladen_von" + (", text" if mit_text else ""))
    con = _sdb.connect(db_path)
    try:
        row = con.execute(
            f"SELECT {spalten} FROM gerichtsgutachten_dokumente WHERE id=?", (int(dok_id),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def delete_dokument(db_path: Path, dok_id: int) -> None:
    ensure_db(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_dokumente WHERE id=?", (int(dok_id),))
        con.commit()
    finally:
        con.close()
