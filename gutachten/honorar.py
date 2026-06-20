"""G0-4 — Geteilter Honorar-Tracker (Zeitbuch).

Erfasst Tätigkeiten pro Gutachten (Audit oder Gericht) + Auslagen.
JVEG-Mapping für gerichtliche Gutachten, freie Stundensätze für privat.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from shared import db as _sdb

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gutachten_zeitbuch (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sv_user         TEXT NOT NULL DEFAULT '',
    projekt_typ     TEXT NOT NULL DEFAULT 'gerichts',    -- audit|gerichts
    projekt_name    TEXT NOT NULL,
    datum           TEXT NOT NULL DEFAULT (aics_now()),
    kategorie       TEXT NOT NULL,                       -- aktenstudium|asservaten|labor|bericht|kommunikation|ortstermin|fortbildung|sonstiges
    dauer_minuten   INTEGER NOT NULL DEFAULT 0,
    beschreibung    TEXT NOT NULL DEFAULT '',
    tarif_modell    TEXT NOT NULL DEFAULT 'jveg',        -- jveg|privat|pauschal
    stundensatz_eur REAL NOT NULL DEFAULT 0.0,
    auslage_eur     REAL NOT NULL DEFAULT 0.0,
    abgerechnet     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_zeitbuch_projekt ON gutachten_zeitbuch(projekt_typ, projekt_name);
CREATE INDEX IF NOT EXISTS idx_zeitbuch_datum   ON gutachten_zeitbuch(datum);
"""

# JVEG-Honorargruppen für IT-SV (Stand 2026)
JVEG_TARIFE = {
    "HG-11": {"name": "Honorargruppe 11 — Standard-IT", "stundensatz_eur": 105.00},
    "HG-12": {"name": "Honorargruppe 12 — komplexe IT", "stundensatz_eur": 115.00},
    "HG-13": {"name": "Honorargruppe 13 — IT-Forensik / Spezial", "stundensatz_eur": 130.00},
}

KATEGORIEN = (
    "aktenstudium", "asservaten", "labor", "bericht", "kommunikation",
    "ortstermin", "fortbildung", "sonstiges",
)


def _ensure(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = _sdb.connect(db_path)
    try:
        con.executescript(_SCHEMA)
        con.commit()
    finally:
        con.close()


def save_eintrag(
    db_path: Path,
    sv_user: str,
    projekt_typ: str,
    projekt_name: str,
    kategorie: str,
    dauer_minuten: int,
    beschreibung: str = "",
    tarif_modell: str = "jveg",
    stundensatz_eur: float = 0.0,
    auslage_eur: float = 0.0,
    datum: str | None = None,
) -> int:
    if kategorie not in KATEGORIEN:
        raise ValueError(f"kategorie '{kategorie}' unbekannt — erlaubt: {KATEGORIEN}")
    if projekt_typ not in ("audit", "gerichts"):
        raise ValueError("projekt_typ muss 'audit' oder 'gerichts' sein")
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        if datum:
            cur = con.execute(
                """INSERT INTO gutachten_zeitbuch
                     (sv_user, projekt_typ, projekt_name, datum, kategorie, dauer_minuten,
                      beschreibung, tarif_modell, stundensatz_eur, auslage_eur)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   RETURNING id""",
                (sv_user, projekt_typ, projekt_name, datum, kategorie, int(dauer_minuten),
                 beschreibung, tarif_modell, float(stundensatz_eur), float(auslage_eur)),
            )
        else:
            cur = con.execute(
                """INSERT INTO gutachten_zeitbuch
                     (sv_user, projekt_typ, projekt_name, kategorie, dauer_minuten,
                      beschreibung, tarif_modell, stundensatz_eur, auslage_eur)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   RETURNING id""",
                (sv_user, projekt_typ, projekt_name, kategorie, int(dauer_minuten),
                 beschreibung, tarif_modell, float(stundensatz_eur), float(auslage_eur)),
            )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def list_eintraege(
    db_path: Path,
    projekt_typ: str | None = None,
    projekt_name: str | None = None,
    sv_user: str | None = None,
) -> list[dict[str, Any]]:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        where = []
        params: list[Any] = []
        if projekt_typ:
            where.append("projekt_typ = ?")
            params.append(projekt_typ)
        if projekt_name:
            where.append("projekt_name = ?")
            params.append(projekt_name)
        if sv_user:
            where.append("sv_user = ?")
            params.append(sv_user)
        sql = "SELECT * FROM gutachten_zeitbuch"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY datum DESC, id DESC"
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def delete_eintrag(db_path: Path, eintrag_id: int) -> None:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gutachten_zeitbuch WHERE id = ?", (eintrag_id,))
        con.commit()
    finally:
        con.close()


def summary(
    db_path: Path,
    projekt_typ: str | None = None,
    projekt_name: str | None = None,
) -> dict[str, Any]:
    """Aggregierte Übersicht: Gesamt-Minuten, Honorar (h*stundensatz), Auslagen, Abrechnungs-Status."""
    eintraege = list_eintraege(db_path, projekt_typ, projekt_name)
    total_min = sum(int(e["dauer_minuten"]) for e in eintraege)
    honorar_eur = sum((int(e["dauer_minuten"]) / 60.0) * float(e["stundensatz_eur"]) for e in eintraege)
    auslagen_eur = sum(float(e["auslage_eur"]) for e in eintraege)
    abgerechnet_eur = sum(
        ((int(e["dauer_minuten"]) / 60.0) * float(e["stundensatz_eur"])) + float(e["auslage_eur"])
        for e in eintraege if e.get("abgerechnet")
    )
    offen_eur = (honorar_eur + auslagen_eur) - abgerechnet_eur
    return {
        "eintraege_anzahl": len(eintraege),
        "total_stunden": round(total_min / 60.0, 2),
        "honorar_eur": round(honorar_eur, 2),
        "auslagen_eur": round(auslagen_eur, 2),
        "summe_brutto_eur": round(honorar_eur + auslagen_eur, 2),
        "abgerechnet_eur": round(abgerechnet_eur, 2),
        "offen_eur": round(offen_eur, 2),
        "tarife_in_use": sorted(set(e.get("tarif_modell", "") for e in eintraege)),
    }


def list_jveg_tarife() -> dict[str, dict[str, Any]]:
    return JVEG_TARIFE


def list_kategorien() -> list[str]:
    return list(KATEGORIEN)
