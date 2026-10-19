"""CRA Art. 32 / Annex VIII — Konformitätsbewertung + DoC/CE-Record (#1201).

Pro Projekt/Release ein Konformitätsbewertungs-Record: gewählter Bewertungsweg
(Modul A | B+C | H | EUCC), Nachweis-Checkliste je Modul, Notified-Body-Kennnummer/
EUCC-Level, CE-Status, strukturierter Annex-V-DoC-Record (versioniert). Gate:
DoC erst ausstellbar, wenn der Bewertungsweg abgeschlossen ist.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from shared import db as _sdb

DB_PATH = Path("data/db/cra.sqlite")

# Konformitätsbewertungs-Wege (Annex VIII).
WEGE = ("A", "B+C", "H", "EUCC")

# Nachweis-Checkliste je Modul (Soll-Nachweise).
CHECKLISTE: dict[str, list[str]] = {
    "A": ["technische_dokumentation", "interne_fertigungskontrolle"],
    "B+C": ["technische_dokumentation", "eu_baumusterpruefung", "konformitaet_mit_baumuster",
            "nb_zertifikat"],
    "H": ["technische_dokumentation", "umfassendes_qm_system", "nb_zertifikat"],
    "EUCC": ["technische_dokumentation", "eucc_zertifikat", "eucc_level"],
}

# CE-Status-Werte.
CE_STATUS = ("offen", "in_bewertung", "bewertung_abgeschlossen", "doc_ausgestellt", "ce_angebracht")


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_konformitaet (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                release_version TEXT NOT NULL DEFAULT '',
                bewertungsweg   TEXT NOT NULL DEFAULT 'A',
                produktklasse   TEXT NOT NULL DEFAULT 'default',
                checkliste_json TEXT NOT NULL DEFAULT '{}',   -- {nachweis: bool}
                bewertung_abgeschlossen INTEGER NOT NULL DEFAULT 0,
                nb_kennnummer   TEXT NOT NULL DEFAULT '',      -- Notified-Body-Kennnummer
                eucc_level      TEXT NOT NULL DEFAULT '',
                ce_status       TEXT NOT NULL DEFAULT 'offen',
                doc_json        TEXT NOT NULL DEFAULT '{}',    -- strukturierter Annex-V-DoC
                doc_version     INTEGER NOT NULL DEFAULT 0,
                doc_ausgestellt INTEGER NOT NULL DEFAULT 0,
                doc_ausgestellt_am TEXT,
                notizen         TEXT NOT NULL DEFAULT '',
                created_at      TEXT DEFAULT (aics_now()),
                updated_at      TEXT DEFAULT (aics_now()),
                UNIQUE(projekt_name, release_version)
            );
            CREATE INDEX IF NOT EXISTS idx_cra_konformitaet_projekt
                ON cra_konformitaet(projekt_name);
            """
        )
        # #1220-A: Sign-off-/Lock-Spalten idempotent ergänzen (Bestands-DBs).
        for ddl in (
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS freigabe_status TEXT NOT NULL DEFAULT 'entwurf'",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS freigegeben_von TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS freigegeben_am TEXT",
        ):
            con.execute(ddl)
        con.commit()
    finally:
        con.close()


# #1220-A: Freigabe-Status-Werte (Governance-Gate).
FREIGABE_STATUS = ("entwurf", "freigegeben")


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    for col, key in (("checkliste_json", "checkliste"), ("doc_json", "doc")):
        try:
            d[key] = json.loads(d.get(col) or "{}")
        except Exception:
            d[key] = {}
    d["bewertung_abgeschlossen"] = bool(d.get("bewertung_abgeschlossen"))
    d["doc_ausgestellt"] = bool(d.get("doc_ausgestellt"))
    d["soll_nachweise"] = CHECKLISTE.get(d.get("bewertungsweg", "A"), [])
    d.setdefault("freigabe_status", "entwurf")
    d["gesperrt"] = d.get("freigabe_status") == "freigegeben"  # #1220-A Lock
    return d


def get_konformitaet(db_path: Path, projekt_name: str,
                     release_version: str = "") -> Optional[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        r = con.execute(
            "SELECT * FROM cra_konformitaet WHERE projekt_name=? AND release_version=?",
            (projekt_name, release_version),
        ).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def save_konformitaet(db_path: Path, projekt_name: str, data: dict) -> dict[str, Any]:
    ensure_table(db_path)
    weg = data.get("bewertungsweg") or "A"
    if weg not in WEGE:
        raise ValueError(f"Ungültiger Bewertungsweg: {weg}")
    release = data.get("release_version", "")
    ce_status = data.get("ce_status") or "offen"
    if ce_status not in CE_STATUS:
        raise ValueError(f"Ungültiger CE-Status: {ce_status}")
    abgeschlossen = 1 if data.get("bewertung_abgeschlossen") else 0
    # #1220-A: freigegebener Record ist gesperrt (Lock) — erst reopen nötig.
    existing = get_konformitaet(db_path, projekt_name, release)
    if existing and existing.get("freigabe_status") == "freigegeben":
        raise ValueError("Record ist freigegeben und gesperrt — erst zurücksetzen (reopen)")
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_konformitaet
                   (projekt_name, release_version, bewertungsweg, produktklasse,
                    checkliste_json, bewertung_abgeschlossen, nb_kennnummer, eucc_level,
                    ce_status, notizen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,aics_now())
               ON CONFLICT(projekt_name, release_version) DO UPDATE SET
                   bewertungsweg=excluded.bewertungsweg,
                   produktklasse=excluded.produktklasse,
                   checkliste_json=excluded.checkliste_json,
                   bewertung_abgeschlossen=excluded.bewertung_abgeschlossen,
                   nb_kennnummer=excluded.nb_kennnummer,
                   eucc_level=excluded.eucc_level,
                   ce_status=excluded.ce_status,
                   notizen=excluded.notizen,
                   updated_at=aics_now()""",
            (projekt_name, release, weg, data.get("produktklasse", "default"),
             json.dumps(data.get("checkliste") or {}, ensure_ascii=False),
             abgeschlossen, data.get("nb_kennnummer", ""), data.get("eucc_level", ""),
             ce_status, data.get("notizen", "")),
        )
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release)


def issue_doc(db_path: Path, projekt_name: str, doc: dict,
              release_version: str = "") -> dict[str, Any]:
    """Annex-V-DoC ausstellen — Gate: nur bei abgeschlossenem Bewertungsweg.

    Erhöht ``doc_version``, setzt CE-Status auf ``doc_ausgestellt``.
    """
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    if not rec.get("bewertung_abgeschlossen"):
        raise ValueError("DoC erst ausstellbar, wenn der Bewertungsweg abgeschlossen ist")
    new_version = int(rec.get("doc_version") or 0) + 1
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_konformitaet SET doc_json=?, doc_version=?, doc_ausgestellt=1,
                      doc_ausgestellt_am=aics_now(), ce_status='doc_ausgestellt',
                      updated_at=aics_now()
               WHERE projekt_name=? AND release_version=?""",
            (json.dumps(doc or {}, ensure_ascii=False), new_version,
             projekt_name, release_version),
        )
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release_version)


def freigeben(db_path: Path, projekt_name: str, release_version: str,
              von: str) -> dict[str, Any]:
    """#1220-A: Konformitäts-Record freigeben (Governance-Sign-off, CRA_APPROVE).

    Gate: nur bei abgeschlossenem Bewertungsweg. Setzt freigabe_status + Freigeber/Zeit;
    danach ist der Record gesperrt (Lock) bis zum reopen.
    """
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    if rec.get("freigabe_status") == "freigegeben":
        raise ValueError("Record ist bereits freigegeben")
    if not rec.get("bewertung_abgeschlossen"):
        raise ValueError("Freigabe erst möglich, wenn der Bewertungsweg abgeschlossen ist")
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_konformitaet
                   SET freigabe_status='freigegeben', freigegeben_von=?,
                       freigegeben_am=aics_now(), updated_at=aics_now()
                   WHERE projekt_name=? AND release_version=?""",
            (von or "", projekt_name, release_version),
        )
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release_version)


def reopen(db_path: Path, projekt_name: str, release_version: str) -> dict[str, Any]:
    """#1220-A: Freigabe zurücksetzen (entsperren) → erneut editierbar."""
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_konformitaet
                   SET freigabe_status='entwurf', freigegeben_von='', freigegeben_am=NULL,
                       updated_at=aics_now()
                   WHERE projekt_name=? AND release_version=?""",
            (projekt_name, release_version),
        )
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release_version)


def list_konformitaet(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_konformitaet WHERE projekt_name=? ORDER BY release_version",
            (projekt_name,),
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()
