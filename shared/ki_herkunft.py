"""Herkunft und fachliche Prüfung KI-erzeugter Inhalte (#1765).

Bis v8.0.0 hängte ``server/services/auto_bewertung.ki_kennzeichnung`` die
Kennzeichnung **an den gespeicherten Text**:

    — 🤖 KI-generiert (ollama, 2026-10-22) — fachlich zu prüfen.

Damit stand sie in jedem Bericht, der den Text druckt — auch in der
Konformitätserklärung und in der Fassung für den Kunden. Die Pflicht aus dem
AI-Act-Dossier (#1551/#1552) ist richtig, sie gilt aber gegenüber **denen, die
mit dem System arbeiten**, nicht gegenüber dem Empfänger eines
Konformitätsdokuments. Und „fachlich zu prüfen" in einem freigegebenen
Dokument nimmt diesem seine Aussage: Entweder die Bewertung steht, dann gehört
der Vorbehalt nicht hinein — oder sie steht nicht, dann gehört sie nicht in
ein freigegebenes Dokument.

Hier steht deshalb, was der Text nicht mehr trägt: Anbieter, Zeitpunkt und —
das Feld, das bisher ganz fehlte — **wer die Bewertung wann fachlich geprüft
hat**.

WARUM EIN GEMEINSAMES REGISTER
Sechs Module speichern KI-Bewertungen (CRA, NIS2, AI Act, DSGVO, WiBA,
Risikobewertung), dazu DSGVO-TOM und das Compliance-Audit. Je Modultabelle vier
Spalten wären dieselbe Spiegel-Liste in acht Fassungen — die Fehlerklasse, die
dieses Projekt schon mehrfach bezahlt hat (#1731, #1735). Muster ist
``shared/issue_links``: ein Register, das Objekte über
``(modul, projekt, art, id)`` adressiert.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from shared import db as _sdb

DB_PATH = Path("data/db/ki_herkunft.sqlite")

#: Der alte Inline-Marker. Bleibt bekannt, weil er in Bestandsdaten steht und
#: beim Lesen entfernt wird.
ALTER_MARKER = "🤖 KI-generiert"

_MARKER_RE = re.compile(
    r"\n*\s*[—-]\s*" + re.escape(ALTER_MARKER) + r".*?(?:\.\s*)?$",
    re.S)


def ohne_marker(text: Any) -> str:
    """Entfernt die alte Inline-Kennzeichnung aus einem Text.

    Wird von den Berichts-Renderern aufgerufen. Bestandstexte tragen den
    Marker; ihn beim Drucken stehen zu lassen hieße, den Fehler weiter
    auszuliefern, bis jede Bewertung einmal angefasst wurde.
    """
    s = str(text or "")
    if ALTER_MARKER not in s:
        return s
    return _MARKER_RE.sub("", s).rstrip()


def hat_alten_marker(text: Any) -> bool:
    """Trägt der Text die alte Kennzeichnung? Dann ist er ein KI-Entwurf."""
    return ALTER_MARKER in str(text or "")


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _sdb.connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS ki_herkunft (
                id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                modul         TEXT NOT NULL,
                projekt_name  TEXT NOT NULL,
                objekt_art    TEXT NOT NULL,
                objekt_id     TEXT NOT NULL,
                provider      TEXT NOT NULL DEFAULT '',
                erzeugt_am    TEXT DEFAULT (aics_now()),
                geprueft_von  TEXT NOT NULL DEFAULT '',
                geprueft_am   TEXT,
                created_at    TEXT DEFAULT (aics_now()),
                updated_at    TEXT DEFAULT (aics_now()),
                UNIQUE(modul, projekt_name, objekt_art, objekt_id)
            );
            CREATE INDEX IF NOT EXISTS idx_ki_herkunft_projekt
                ON ki_herkunft(modul, projekt_name);
            """
        )
        con.commit()
    finally:
        con.close()


def vermerken(modul: str, projekt_name: str, objekt_art: str, objekt_id: str,
              *, provider: str = "", db_path: Path = DB_PATH) -> None:
    """Eine KI-Erzeugung festhalten — und eine frühere Prüfung **aufheben**.

    Wird eine Bewertung neu erzeugt, ist die alte Prüfung erledigt: Geprüft
    wurde ein anderer Text. Das stillschweigend stehen zu lassen wäre die
    gefährlichere Variante — ein Dokument würde einen ungeprüften Inhalt als
    geprüft ausweisen.
    """
    ensure_table(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute(
            """INSERT INTO ki_herkunft
                   (modul, projekt_name, objekt_art, objekt_id, provider)
               VALUES (?,?,?,?,?)
               ON CONFLICT(modul, projekt_name, objekt_art, objekt_id) DO UPDATE SET
                   provider=excluded.provider, erzeugt_am=aics_now(),
                   geprueft_von='', geprueft_am=NULL, updated_at=aics_now()""",
            (modul, projekt_name, objekt_art, objekt_id, provider or ""),
        )
        con.commit()
    finally:
        con.close()


def pruefen(modul: str, projekt_name: str, objekt_art: str, objekt_id: str,
            *, von: str, db_path: Path = DB_PATH) -> dict[str, Any]:
    """Fachliche Prüfung festhalten. Ohne Person keine Prüfung."""
    if not str(von or "").strip():
        raise ValueError("Eine Prüfung braucht die Person, die sie vorgenommen hat")
    ensure_table(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute(
            """UPDATE ki_herkunft SET geprueft_von=?, geprueft_am=aics_now(),
                      updated_at=aics_now()
               WHERE modul=? AND projekt_name=? AND objekt_art=? AND objekt_id=?""",
            (von, modul, projekt_name, objekt_art, objekt_id),
        )
        con.commit()
    finally:
        con.close()
    return status(modul, projekt_name, objekt_art, objekt_id, db_path=db_path)


def vermerken_viele(modul: str, projekt_name: str, objekt_art: str,
                    objekt_ids: list[str], *, provider: str = "",
                    uebernommen_von: str = "", db_path: Path = DB_PATH) -> int:
    """Herkunft für viele Objekte in **einer** Verbindung festhalten (#1773).

    Gedacht für den Fall, dass ein Mensch einen KI-Entwurf für eine **Gruppe**
    gleichartiger Objekte übernimmt — bei einer SBOM können das 150
    Komponenten sein. Einzelaufrufe wären 150 Verbindungen für einen Klick.

    ``uebernommen_von`` ist der Grund, warum diese Funktion die Prüfung
    **mitsetzen** darf, während :func:`vermerken` sie aufhebt: Der Entwurf wird
    hier nicht erzeugt, sondern von einer namentlich bekannten Person
    übernommen, nachdem sie ihn gelesen hat. Dieser Akt ist die fachliche
    Prüfung — dieselbe Handlung, die der Haken „fachlich geprüft" an einer
    einzelnen Bewertung festhält. Ohne ``uebernommen_von`` bleiben die
    Einträge ungeprüft.
    """
    ids = [str(i) for i in (objekt_ids or []) if str(i or "").strip()]
    if not ids:
        return 0
    ensure_table(db_path)
    person = str(uebernommen_von or "").strip()
    con = _sdb.connect(db_path)
    try:
        for oid in ids:
            con.execute(
                """INSERT INTO ki_herkunft
                       (modul, projekt_name, objekt_art, objekt_id, provider,
                        geprueft_von, geprueft_am)
                   VALUES (?,?,?,?,?,?,
                           CASE WHEN ?='' THEN NULL ELSE aics_now() END)
                   ON CONFLICT(modul, projekt_name, objekt_art, objekt_id) DO UPDATE SET
                       provider=excluded.provider, erzeugt_am=aics_now(),
                       geprueft_von=excluded.geprueft_von,
                       geprueft_am=excluded.geprueft_am,
                       updated_at=aics_now()""",
                (modul, projekt_name, objekt_art, oid, provider or "",
                 person, person),
            )
        con.commit()
    finally:
        con.close()
    return len(ids)


def status(modul: str, projekt_name: str, objekt_art: str, objekt_id: str,
           *, db_path: Path = DB_PATH) -> dict[str, Any]:
    """Herkunft eines Objekts. Kein Eintrag = nicht KI-erzeugt."""
    ensure_table(db_path)
    con = _sdb.connect(db_path)
    try:
        r = con.execute(
            """SELECT * FROM ki_herkunft
               WHERE modul=? AND projekt_name=? AND objekt_art=? AND objekt_id=?""",
            (modul, projekt_name, objekt_art, objekt_id)).fetchone()
    finally:
        con.close()
    if not r:
        return {"ki": False, "geprueft": True, "provider": "", "geprueft_von": ""}
    d = dict(r)
    return {"ki": True, "geprueft": bool(d.get("geprueft_am")),
            "provider": d.get("provider") or "",
            "erzeugt_am": d.get("erzeugt_am"),
            "geprueft_von": d.get("geprueft_von") or "",
            "geprueft_am": d.get("geprueft_am")}


def fuer_projekt(modul: str, projekt_name: str, objekt_art: str = "",
                 *, db_path: Path = DB_PATH) -> dict[str, dict[str, Any]]:
    """Alle Einträge eines Projekts, nach ``objekt_id`` — ein Abruf statt N.

    Die Oberfläche zeigt eine Liste von Anforderungen; je Zeile einzeln zu
    fragen wären bei 32 CRA-Anforderungen 32 Abfragen.
    """
    ensure_table(db_path)
    con = _sdb.connect(db_path)
    try:
        if objekt_art:
            rows = con.execute(
                """SELECT * FROM ki_herkunft
                   WHERE modul=? AND projekt_name=? AND objekt_art=?""",
                (modul, projekt_name, objekt_art)).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM ki_herkunft WHERE modul=? AND projekt_name=?",
                (modul, projekt_name)).fetchall()
    finally:
        con.close()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        out[str(d.get("objekt_id"))] = {
            "ki": True, "geprueft": bool(d.get("geprueft_am")),
            "provider": d.get("provider") or "",
            "erzeugt_am": d.get("erzeugt_am"),
            "geprueft_von": d.get("geprueft_von") or "",
            "geprueft_am": d.get("geprueft_am")}
    return out


#: Vorsatz für einen ungeprüften Entwurf **im Bericht** (nicht im Datenbestand).
#: Der Unterschied zur alten Lösung ist genau dieser: Die Kennzeichnung ist eine
#: Entscheidung beim Drucken, nicht ein Anhängsel am gespeicherten Text. Deshalb
#: kann sie im internen Bericht stehen und in der EU-Konformitätserklärung
#: fehlen — dort wird der Inhalt stattdessen weggelassen.
ENTWURF_VORSATZ = "[KI-Entwurf, fachlich nicht geprüft] "


def bericht_text(text: Any, eintrag: dict[str, Any] | None) -> str:
    """Text für einen **internen** Bericht aufbereiten.

    ``eintrag`` ist der Datensatz aus :func:`fuer_projekt` für dieses Objekt
    (``None`` = kein Eintrag = nicht KI-erzeugt). Ein ungeprüfter Entwurf wird
    gedruckt, aber als solcher ausgewiesen; ein geprüfter Text steht für sich.

    Für Dokumente, die das Haus verlassen — Konformitätserklärung,
    Kundenfassung, Nachweis —, ist nicht dieser Weg zu nehmen, sondern
    :func:`ist_druckbar`: Dort hat ein ungeprüfter Entwurf nichts zu suchen,
    auch nicht mit Vorsatz.
    """
    s = ohne_marker(text)
    if not s or not eintrag or eintrag.get("geprueft"):
        return s
    return ENTWURF_VORSATZ + s


def ist_druckbar(modul: str, projekt_name: str, objekt_art: str, objekt_id: str,
                 text: Any = "", *, db_path: Path = DB_PATH) -> bool:
    """Darf dieser Inhalt in ein Dokument?

    Nein, solange er ein ungeprüfter KI-Entwurf ist. Bestandstexte mit dem
    alten Inline-Marker gelten als ungeprüft — sie wurden nie bestätigt, der
    Marker sagt es selbst („fachlich zu prüfen").
    """
    if hat_alten_marker(text):
        return False
    return bool(status(modul, projekt_name, objekt_art, objekt_id,
                       db_path=db_path).get("geprueft", True))
