"""N-SCOPE (#1210/#1211) — NIS2 Art. 2/3 + Art. 26 Betroffenheits-/Scoping-Register.

Self-contained, additiver DB-Layer auf der gemeinsamen ``data/db/nis2.sqlite``
(via ``nis2.db._connect``). Je Projekt **eine** versionierte Scoping-Bewertung
(``nis2_scoping``, 1:1, Upsert je ``projekt_name``):

- Art. 2/3: Größenschwellen-Nachweis (Mitarbeiterzahl/Umsatz/Bilanzsumme) +
  Sektor/Subsektor (Anhang I/II) + Konzernverbund + **deterministische**
  Klassen-Auswertung (essenziell/wichtig/out-of-scope) mit Auto-Begründung.
- Art. 26: Hauptniederlassung, zuständige Behörde, EU-Niederlassung,
  EU-Vertreter (Pflicht wenn nicht EU-niedergelassen).

Die Größenschwellen-Logik (``evaluate_size_class``) und die kanonische
Klassen-Vereinheitlichung (``canonical_klasse`` essential↔wesentlich) liegen hier
als Single Source of Truth, damit der N6-Klassifikator (Bug #1210) sie nutzt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from nis2.db import _connect

DB_PATH = Path("data/db/nis2.sqlite")

ANHANG = ("I", "II", "keiner")
# Kanonische NIS2-Einrichtungsklassen (DE-Recht: wesentlich/wichtig).
SIZE_CLASS = ("wesentlich", "wichtig", "out-of-scope")

# Klassen-Vereinheitlichung (#1210): EN-Klassifikator-Werte ↔ DE-Spaltenwerte.
_KLASSE_CANON = {
    "essential": "wesentlich", "wesentlich": "wesentlich",
    "important": "wichtig", "wichtig": "wichtig",
    "out-of-scope": "out-of-scope", "out_of_scope": "out-of-scope",
    "oos": "out-of-scope", "nicht-im-scope": "out-of-scope",
}


def canonical_klasse(value: str | None) -> str:
    """Bildet jeden Klassen-Wert auf die kanonische DE-Form ab.

    essential→wesentlich, important→wichtig, sonst out-of-scope. Fixt #1210:
    der N6-Klassifikator schrieb EN-Rohwerte (essential/important) ungeprüft in
    die ``einrichtungsklasse``-Spalte, die nur {wesentlich,wichtig} erlaubt.
    """
    return _KLASSE_CANON.get((value or "").strip().lower(), "out-of-scope")


SCHEMA = """
CREATE TABLE IF NOT EXISTS nis2_scoping (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name        TEXT NOT NULL UNIQUE,
    -- Art. 2/3 Größenschwellen
    mitarbeiterzahl     INTEGER NOT NULL DEFAULT 0,
    jahresumsatz        REAL NOT NULL DEFAULT 0,      -- in Mio. EUR
    bilanzsumme         REAL NOT NULL DEFAULT 0,      -- in Mio. EUR
    sektor              TEXT NOT NULL DEFAULT '',
    subsektor           TEXT NOT NULL DEFAULT '',
    anhang              TEXT NOT NULL DEFAULT 'keiner',
    konzernverbund      TEXT NOT NULL DEFAULT '',
    -- ausgewertete Klasse (deterministisch) + Begründung
    size_class          TEXT NOT NULL DEFAULT 'out-of-scope',
    size_begruendung    TEXT NOT NULL DEFAULT '',
    -- Art. 26 Jurisdiktion / Territorialität
    hauptniederlassung  TEXT NOT NULL DEFAULT '',
    zustaendige_behoerde TEXT NOT NULL DEFAULT 'BSI',
    eu_niedergelassen   INTEGER NOT NULL DEFAULT 1,
    eu_vertreter        TEXT NOT NULL DEFAULT '',
    -- Versionierung
    version             INTEGER NOT NULL DEFAULT 1,
    scoping_datum       TEXT NOT NULL DEFAULT '',
    notizen             TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (aics_now()),
    updated_at          TEXT NOT NULL DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_nis2_scoping_projekt ON nis2_scoping(projekt_name);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row(r: Any | None) -> dict[str, Any] | None:
    return dict(r) if r else None


# ── Deterministische Größenschwellen-Logik (Art. 2/3) ───────────────────────

def evaluate_size_class(
    mitarbeiterzahl: int, jahresumsatz: float, bilanzsumme: float, anhang: str
) -> dict[str, str]:
    """Bestimmt essenziell/wichtig/out-of-scope nach NIS2-Größenschwellen.

    - essenziell (wesentlich): ≥250 MA ODER (>50 Mio€ Umsatz UND >43 Mio€ Bilanz)
    - wichtig: ≥50 MA ODER >10 Mio€ Umsatz/Bilanz (mittleres Unternehmen)
    - sonst (Kleinst-/Kleinunternehmen) bzw. kein Anhang-Sektor: out-of-scope

    Ohne Sektor aus Anhang I/II ist die Einrichtung unabhängig von der Größe
    grundsätzlich out-of-scope. Rückgabe: {size_class, size_begruendung}.
    """
    ma = int(mitarbeiterzahl or 0)
    umsatz = float(jahresumsatz or 0)
    bilanz = float(bilanzsumme or 0)
    anh = (anhang or "keiner").strip()

    if anh not in ("I", "II"):
        return {
            "size_class": "out-of-scope",
            "size_begruendung": (
                "Kein Sektor aus Anhang I/II zugeordnet — außerhalb des "
                "NIS2-Anwendungsbereichs unabhängig von der Größe."),
        }

    gross = ma >= 250 or (umsatz > 50 and bilanz > 43)
    mittel = ma >= 50 or umsatz > 10 or bilanz > 10

    if gross:
        cls = "wesentlich"
        grund = (
            f"Großunternehmen (MA={ma}, Umsatz={umsatz} Mio€, Bilanz={bilanz} Mio€) "
            f"mit Sektor Anhang {anh} → wesentliche Einrichtung (Art. 3 Abs. 1).")
    elif mittel:
        cls = "wichtig"
        grund = (
            f"Mittleres Unternehmen (MA={ma}, Umsatz={umsatz} Mio€, Bilanz={bilanz} Mio€) "
            f"mit Sektor Anhang {anh} → wichtige Einrichtung (Art. 3 Abs. 2).")
    else:
        cls = "out-of-scope"
        grund = (
            f"Kleinst-/Kleinunternehmen (MA={ma}, Umsatz={umsatz} Mio€, Bilanz={bilanz} Mio€) "
            f"unterhalb der Größenschwellen → grundsätzlich out-of-scope "
            f"(Ausnahmen nach Art. 2 Abs. 2 gesondert prüfen).")
    return {"size_class": cls, "size_begruendung": grund}


# ── CRUD ────────────────────────────────────────────────────────────────────

def get_scoping(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        return _row(con.execute(
            "SELECT * FROM nis2_scoping WHERE projekt_name=?",
            (projekt_name,)).fetchone())
    finally:
        con.close()


def save_scoping(db_path: Path, projekt_name: str, data: dict) -> dict[str, Any]:
    """Upsert der 1:1-Scoping-Bewertung; berechnet size_class deterministisch.

    Validiert die EU-Vertreter-Pflicht (Art. 26): wenn nicht EU-niedergelassen,
    ist ``eu_vertreter`` Pflicht. Erhöht ``version`` bei jedem Update.
    """
    ensure_table(db_path)
    eu_nieder = 1 if data.get("eu_niedergelassen", True) else 0
    eu_vertreter = str(data.get("eu_vertreter", "") or "").strip()
    if eu_nieder == 0 and not eu_vertreter:
        raise ValueError(
            "EU-Vertreter ist Pflicht, wenn die Einrichtung nicht in der EU "
            "niedergelassen ist (Art. 26 NIS2).")

    anhang = data.get("anhang", "keiner")
    if anhang not in ANHANG:
        anhang = "keiner"
    ma = int(data.get("mitarbeiterzahl", 0) or 0)
    umsatz = float(data.get("jahresumsatz", 0) or 0)
    bilanz = float(data.get("bilanzsumme", 0) or 0)
    sized = evaluate_size_class(ma, umsatz, bilanz, anhang)

    con = _connect(Path(db_path))
    try:
        existing = con.execute(
            "SELECT version FROM nis2_scoping WHERE projekt_name=?",
            (projekt_name,)).fetchone()
        version = (int(existing["version"]) + 1) if existing else 1
        con.execute(
            """INSERT INTO nis2_scoping
                 (projekt_name, mitarbeiterzahl, jahresumsatz, bilanzsumme,
                  sektor, subsektor, anhang, konzernverbund, size_class,
                  size_begruendung, hauptniederlassung, zustaendige_behoerde,
                  eu_niedergelassen, eu_vertreter, version, scoping_datum, notizen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(projekt_name) DO UPDATE SET
                  mitarbeiterzahl=excluded.mitarbeiterzahl,
                  jahresumsatz=excluded.jahresumsatz,
                  bilanzsumme=excluded.bilanzsumme,
                  sektor=excluded.sektor,
                  subsektor=excluded.subsektor,
                  anhang=excluded.anhang,
                  konzernverbund=excluded.konzernverbund,
                  size_class=excluded.size_class,
                  size_begruendung=excluded.size_begruendung,
                  hauptniederlassung=excluded.hauptniederlassung,
                  zustaendige_behoerde=excluded.zustaendige_behoerde,
                  eu_niedergelassen=excluded.eu_niedergelassen,
                  eu_vertreter=excluded.eu_vertreter,
                  version=excluded.version,
                  scoping_datum=excluded.scoping_datum,
                  notizen=excluded.notizen,
                  updated_at=aics_now()""",
            (projekt_name, ma, umsatz, bilanz,
             data.get("sektor", ""), data.get("subsektor", ""), anhang,
             data.get("konzernverbund", ""), sized["size_class"],
             sized["size_begruendung"], data.get("hauptniederlassung", ""),
             data.get("zustaendige_behoerde", "BSI") or "BSI",
             eu_nieder, eu_vertreter, version,
             data.get("scoping_datum", ""), data.get("notizen", "")))
        con.commit()
    finally:
        con.close()
    return get_scoping(db_path, projekt_name)
