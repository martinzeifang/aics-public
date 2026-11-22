"""Eigene Hinweise je Projekt merken (#1835).

„Der Schwerpunkt dieses Unternehmens liegt in der Fertigung, die IT ist
ausgelagert" gilt für **jede** Bewertung dieses Mandanten, nicht für einen
Klick. Bliebe es beim Ad-hoc-Feld aus #1834, müsste der Berater den Satz bei
120 Anforderungen 120-mal tippen — und täte es nach dem dritten Mal nicht
mehr. Eine Funktion, die nur bei großer Disziplin wirkt, wirkt nicht.

WARUM VORBELEGEN UND NICHT HEIMLICH ANHÄNGEN
Der naheliegende Weg wäre, den gespeicherten Hinweis serverseitig an jeden
Prompt zu hängen. Das wäre falsch: Ein Text, den ein Kollege vor Wochen
gespeichert hat, würde jeden KI-Lauf steuern, ohne dass der Bearbeiter ihn
sieht. Stattdessen **belegt** er das Feld vor — sichtbar, überschreibbar,
löschbar für diesen einen Lauf. Ein Vorschlag, keine Fessel.

Die Auflösung (allgemeiner Hinweis + bereichsbezogener) passiert hier,
serverseitig: Dieselbe Regel im Frontend nachzubauen wäre die zweite
Wahrheit (die Lehre aus #1703/S9).

WARUM EIN REGISTER
Adressiert über ``(modul, projekt_name, bereich)`` — Muster
``shared/ki_herkunft`` (#1765). Je Modultabelle ein Textfeld wären dieselbe
Spiegel-Liste in sieben Fassungen, die Fehlerklasse aus #1731/#1735.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from shared import db as _sdb

DB_PATH = Path("data/db/prompt_hinweise.sqlite")

#: Bereiche, für die ein eigener Hinweis gespeichert werden kann. ``""`` gilt
#: für alle Prompts des Projekts. Die Liste ist bewusst kurz: Sie beschreibt
#: die Arten von Auftrag, die sich fachlich unterscheiden — nicht jede Route.
BEREICHE = ("", "bewertung", "bericht", "dokument", "wasserstand", "assistent")

#: Längengrenze je Eintrag — dieselbe wie beim Ad-hoc-Feld, damit die Summe
#: aus beiden nicht unbemerkt über die Grenze des Prompts hinauswächst.
GRENZE = 2000


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _sdb.connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS prompt_hinweise (
                id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                modul         TEXT NOT NULL,
                projekt_name  TEXT NOT NULL,
                bereich       TEXT NOT NULL DEFAULT '',
                text          TEXT NOT NULL DEFAULT '',
                erstellt_von  TEXT NOT NULL DEFAULT '',
                created_at    TEXT DEFAULT (aics_now()),
                updated_at    TEXT DEFAULT (aics_now()),
                UNIQUE(modul, projekt_name, bereich)
            );
            CREATE INDEX IF NOT EXISTS idx_prompt_hinweise_projekt
                ON prompt_hinweise(modul, projekt_name);
            """
        )
        con.commit()
    finally:
        con.close()


def _saeubere(text: Any) -> str:
    """Begrenzen und säubern — dieselbe Regel wie beim Ad-hoc-Hinweis."""
    from shared.prompt_zusatz import saeubere
    return saeubere(text)


def setze(modul: str, projekt_name: str, text: Any, *, bereich: str = "",
          von: str = "", db_path: Path = DB_PATH) -> dict[str, Any]:
    """Hinweis speichern oder ersetzen.

    ``von`` wird festgehalten, weil der Hinweis künftig **jeden** KI-Lauf
    dieses Projekts vorbelegt — auch die von Kollegen. Wer das gesetzt hat,
    muss in der Akte stehen: Das ist die Antwort auf die Frage, die ein Prüfer
    stellt, wenn ihm die Bewertungen eines Projekts auffallend gleichförmig
    vorkommen.

    Leerer Text löscht den Eintrag — ein Hinweis, der nur aus Leerzeichen
    besteht, wäre ein stiller Platzhalter.
    """
    bereich = str(bereich or "")
    if bereich not in BEREICHE:
        raise ValueError(f"Unbekannter Bereich: {bereich!r}")
    sauber = _saeubere(text)
    if not sauber:
        loesche(modul, projekt_name, bereich=bereich, db_path=db_path)
        return {"modul": modul, "projekt_name": projekt_name, "bereich": bereich,
                "text": "", "erstellt_von": ""}
    ensure_table(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute(
            """INSERT INTO prompt_hinweise
                   (modul, projekt_name, bereich, text, erstellt_von)
               VALUES (?,?,?,?,?)
               ON CONFLICT(modul, projekt_name, bereich) DO UPDATE SET
                   text=excluded.text, erstellt_von=excluded.erstellt_von,
                   updated_at=aics_now()""",
            (modul, projekt_name, bereich, sauber, str(von or "")),
        )
        con.commit()
    finally:
        con.close()
    return hole(modul, projekt_name, bereich=bereich, db_path=db_path) or {}


def hole(modul: str, projekt_name: str, *, bereich: str = "",
         db_path: Path = DB_PATH) -> dict[str, Any] | None:
    """Einen einzelnen Eintrag lesen (ohne Auflösung)."""
    ensure_table(db_path)
    con = _sdb.connect(db_path)
    try:
        r = con.execute(
            """SELECT modul, projekt_name, bereich, text, erstellt_von, updated_at
               FROM prompt_hinweise
               WHERE modul=? AND projekt_name=? AND bereich=?""",
            (modul, projekt_name, str(bereich or "")),
        ).fetchone()
    finally:
        con.close()
    if not r:
        return None
    # `shared.db` setzt eine row_factory — die Zeile ist ein Mapping. Ein
    # `zip(schluessel, r)` liefe über die SCHLÜSSEL und ergäbe
    # {"text": "text"}; Muster ist `dict(r)` wie in ki_herkunft.
    return dict(r)


def liste(modul: str, projekt_name: str, *,
          db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    """Alle Hinweise eines Projekts — allgemeiner zuerst."""
    ensure_table(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            """SELECT modul, projekt_name, bereich, text, erstellt_von, updated_at
               FROM prompt_hinweise
               WHERE modul=? AND projekt_name=?
               ORDER BY (bereich <> '') ASC, bereich ASC""",
            (modul, projekt_name),
        ).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def loesche(modul: str, projekt_name: str, *, bereich: str = "",
            db_path: Path = DB_PATH) -> None:
    ensure_table(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute(
            "DELETE FROM prompt_hinweise WHERE modul=? AND projekt_name=? AND bereich=?",
            (modul, projekt_name, str(bereich or "")),
        )
        con.commit()
    finally:
        con.close()


def aufgeloest(modul: str, projekt_name: str, *, bereich: str = "",
               db_path: Path = DB_PATH) -> dict[str, Any]:
    """Der Text, mit dem das Feld vorbelegt wird — **allgemein zuerst**.

    Reihenfolge, weil der allgemeine Hinweis den Rahmen setzt („Schwerpunkt
    Fertigung") und der bereichsbezogene ihn verengt („für den Bericht
    ausführlicher"). Umgekehrt stünde die Verengung vor dem Rahmen.

    Liefert zusätzlich, **woher** der Text stammt: Der Bearbeiter soll sehen,
    dass die Vorbelegung nicht von ihm ist und wer sie gesetzt hat.
    """
    bereich = str(bereich or "")
    teile: list[str] = []
    quellen: list[dict[str, Any]] = []
    for b in ("", bereich) if bereich else ("",):
        eintrag = hole(modul, projekt_name, bereich=b, db_path=db_path)
        if eintrag and eintrag.get("text"):
            teile.append(str(eintrag["text"]))
            quellen.append({"bereich": b, "erstellt_von": eintrag.get("erstellt_von", ""),
                            "updated_at": eintrag.get("updated_at", "")})
    return {"text": "\n\n".join(teile), "quellen": quellen,
            "bereich": bereich, "grenze": GRENZE}


__all__ = ["BEREICHE", "DB_PATH", "GRENZE", "aufgeloest", "ensure_table", "hole",
           "liste", "loesche", "setze"]
