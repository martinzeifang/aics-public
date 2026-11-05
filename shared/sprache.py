"""Die eine Stelle, an der die Sprache bestimmt wird (#1954).

ZWEI KANÄLE, DIE NICHT DASSELBE SIND
Das ist die wichtigste Unterscheidung dieses Moduls, und sie folgt aus der
Arbeitsweise des Hauses: Ein Berater betreut viele Mandanten. Er selbst
arbeitet auf Deutsch — aber die Akte eines internationalen Mandanten muss auf
Englisch herauskommen.

  * **Anzeigesprache** (``anzeige``) ist die des *Bearbeiters*. Sie kommt aus
    dem Browser (``localStorage['aics_locale']`` → ``Accept-Language``) und
    gilt für Menüs, Schaltflächen und Fehlermeldungen. Sie ist eine Vorliebe,
    keine Eigenschaft der Daten.

  * **Inhaltssprache** (``inhalt``) ist die des *Mandanten*. Sie steht an der
    Firma (``firmen.sprache``) und gilt für alles, was für diesen Mandanten
    entsteht: Berichte, Dokumente, KI-Entwürfe. Sie ist eine Eigenschaft der
    Akte und hat mit der Vorliebe des Bearbeiters nichts zu tun.

Wer die beiden vermischt, baut genau den Fehler ein, der sich am schlechtesten
findet: Ein Bericht, dessen Sprache davon abhängt, wer ihn gerade erzeugt hat.
Zwei Fassungen desselben Nachweises in zwei Sprachen, je nach Bearbeiter —
derselbe Sachverhalt, zwei Dokumente (die Klasse aus #1726/#1727).

NICHT GESETZT IST NICHT DEUTSCH
``normalisiere`` liefert für Unbekanntes ``""``, nicht ``"de"``. Der
Unterschied zählt: Die Spalte ``firmen.sprache`` steht bei Bestandsmandanten
leer, und „leer" heißt „nie entschieden" — erst der Aufrufer macht daraus die
Standardsprache. Eine Spalte, die „nein" und „nicht gesetzt" nicht
unterscheiden kann, war die Falle in #1805.

FAIL-OPEN, UND ZWAR BEWUSST
Lässt sich die Firma nicht bestimmen (Projekt unbekannt, Spalte fehlt, Modul
nicht zugeordnet), kommt die Standardsprache zurück — nicht ein Fehler. Das
folgt ``shared/firmen_link.projekt_firmen_id`` (dort ausdrücklich fail-open)
und dem Verhalten von ``shared/reports/vorlagen``. Eine Anwendung, die keinen
Bericht mehr erzeugt, weil eine Sprachzuordnung fehlt, ist schlechter als eine,
die ihn auf Deutsch erzeugt.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

#: Die Sprachen, die es gibt. Eine Stelle — Oberfläche, REST und Wächter lesen
#: sie. Das Gegenstück im Frontend ist ``frontend/src/i18n/index.ts:SPRACHEN``;
#: ``tests/test_sprache_firma_1954.py`` hält beide gegeneinander.
SPRACHEN: tuple[str, ...] = ("de", "en")

#: Was gilt, wenn nichts entschieden ist.
STANDARD: str = "de"

#: Anzeigenamen der Sprachen, je Anzeigesprache. Für das Auswahlfeld.
NAMEN: dict[str, dict[str, str]] = {
    "de": {"de": "Deutsch", "en": "Englisch"},
    "en": {"de": "German", "en": "English"},
}

#: Sprachkennung für die DOCX-Dokumentsprache (``w:lang``).
#:
#: Ohne sie unterstreicht Word in einem englischen Bericht jedes Wort rot, weil
#: python-docx keine Sprache setzt und die Vorlage ``de-DE`` erbt. Bis 8.3.4
#: setzte das **nur** ``gutachten/gerichtsgutachten_gen.py``, und zwar hart auf
#: ``de-DE`` (#701).
DOCX_LANG: dict[str, str] = {"de": "de-DE", "en": "en-GB"}


@dataclass(frozen=True)
class Sprachen:
    """Was für einen Vorgang gilt — und woher es kommt.

    ``quelle`` ist nicht Zierde: Sie steht in der Oberfläche („Inhaltssprache:
    Englisch (Mandant Nordlicht)") und beantwortet die Frage, die sonst
    unbeantwortbar ist — warum ist dieser Bericht englisch?
    """

    anzeige: str = STANDARD
    inhalt: str = STANDARD
    quelle: str = "Standard"

    def as_dict(self) -> dict[str, str]:
        return {"anzeige": self.anzeige, "inhalt": self.inhalt, "quelle": self.quelle}


def normalisiere(wert: object) -> str:
    """Prüft einen Sprachcode. Unbekannt oder leer → ``""``.

    Eine Positivliste, keine Negativliste: Was nicht ausdrücklich erlaubt ist,
    fällt durch — auch in einer Schreibweise, an die niemand gedacht hat (die
    Lehre aus ``_backup_pfad`` in #1784). ``de-DE`` und ``DE`` werden dabei
    bewusst angenommen: Sie kommen so aus ``Accept-Language``.
    """
    if not isinstance(wert, str):
        return ""
    kurz = wert.strip().lower().replace("_", "-").split("-", 1)[0]
    return kurz if kurz in SPRACHEN else ""


def oder_standard(wert: object) -> str:
    """Wie ``normalisiere``, aber mit der Standardsprache statt ``""``."""
    return normalisiere(wert) or STANDARD


def docx_lang(sprache: object) -> str:
    """Die ``w:lang``-Kennung für ein erzeugtes Word-Dokument."""
    return DOCX_LANG.get(oder_standard(sprache), DOCX_LANG[STANDARD])


def name(sprache: object, *, in_sprache: object = None) -> str:
    """Anzeigename einer Sprache, in der gewünschten Anzeigesprache."""
    ziel = oder_standard(in_sprache if in_sprache is not None else STANDARD)
    code = oder_standard(sprache)
    return NAMEN.get(ziel, NAMEN[STANDARD]).get(code, code)


def auswahl(in_sprache: object = None) -> list[dict[str, str]]:
    """Die Sprachen als Auswahlliste für die Oberfläche."""
    return [{"code": c, "name": name(c, in_sprache=in_sprache)} for c in SPRACHEN]


# --- Anzeigesprache: aus dem Browser ---------------------------------------


def anzeige_sprache() -> str:
    """Die Sprache des Bearbeiters, aus dem laufenden Request.

    Gelesen wird ``Accept-Language``. Das Frontend setzt die Kopfzeile aus
    ``localStorage['aics_locale']`` (``frontend/src/api/client.ts``), also aus
    der ausdrücklichen Wahl des Anwenders — nicht aus der Browsereinstellung.
    Das ist der Unterschied, auf den es ankommt: Wer in der Oberfläche auf EN
    stellt, will auch die Fehlermeldungen auf Englisch.

    Ohne Request-Kontext (Zeitplan, CLI, Tests) gilt die Standardsprache.
    """
    try:
        from flask import has_request_context, request

        if not has_request_context():
            return STANDARD
        # `Accept-Language` kann eine Liste mit Gewichten sein
        # (`en-GB,en;q=0.9,de;q=0.8`). Die erste bekannte Sprache gewinnt.
        roh = request.headers.get("Accept-Language", "") or ""
        for teil in roh.split(","):
            code = normalisiere(teil.split(";", 1)[0])
            if code:
                return code
    except Exception:  # pragma: no cover - fail-open, siehe Modul-Docstring
        log.debug("Anzeigesprache nicht bestimmbar", exc_info=True)
    return STANDARD


# --- Inhaltssprache: aus der Firma ----------------------------------------


def firma_sprache(firmen_db: Path | str, firmen_id: int | None) -> str:
    """Die Inhaltssprache eines Mandanten. Nicht gesetzt → ``""``."""
    if not firmen_id:
        return ""
    try:
        from firmen import db as _fdb

        for zeile in _fdb.list_firmen_rows(Path(firmen_db)):
            if int(zeile.get("id") or 0) == int(firmen_id):
                return normalisiere(zeile.get("sprache"))
    except Exception:
        log.debug("Firmensprache nicht lesbar", exc_info=True)
    return ""


def firma_sprache_nach_name(firmen_db: Path | str, firma_name: str) -> str:
    """Wie ``firma_sprache``, aber über den Firmennamen."""
    if not firma_name:
        return ""
    try:
        from firmen import db as _fdb

        for zeile in _fdb.list_firmen_rows(Path(firmen_db)):
            if str(zeile.get("name") or "") == firma_name:
                return normalisiere(zeile.get("sprache"))
    except Exception:
        log.debug("Firmensprache nicht lesbar", exc_info=True)
    return ""


def _modul_db(modul: str) -> Path | None:
    """Modulschlüssel → Pfad der Modul-Datenbank.

    Über ``shared/templates/schema.MODULE_DB``, also dieselbe Zuordnung, die
    ``shared/reports/vorlagen.projekt_firma`` benutzt. Eine zweite Kopie wäre
    die Spiegel-Liste aus #1731/#1735.
    """
    try:
        from shared.reports.vorlagen import engine_modul
        from shared.templates import schema

        return schema.MODULE_DB.get(engine_modul(modul))
    except Exception:
        log.debug("Modul-DB für %r nicht bestimmbar", modul, exc_info=True)
        return None


def fuer_projekt(modul: str, projekt_name: str) -> Sprachen:
    """Was für ein Modulprojekt gilt — Anzeige und Inhalt.

    Der Weg ist der aus ``shared/nachziehen.py``: Projekt → ``firmen_id`` →
    Firmenzeile. ``projekt_firmen_id`` nimmt den **DB-Pfad**, nicht den
    Modulnamen — das war der Fehler aus #1892, und er kostete dort zwei
    stillschweigend leere Herstellerangaben.
    """
    anzeige = anzeige_sprache()
    if not projekt_name:
        return Sprachen(anzeige=anzeige, inhalt=STANDARD, quelle="Standard")
    modul_db = _modul_db(modul)
    if modul_db is None:
        return Sprachen(anzeige=anzeige, inhalt=STANDARD, quelle="Standard")
    try:
        from firmen import db as _fdb
        from shared.firmen_link import firmen_db_path, projekt_firmen_id

        fid = projekt_firmen_id(modul_db, projekt_name)
        if not fid:
            return Sprachen(anzeige=anzeige, inhalt=STANDARD,
                            quelle="Standard (keine Firma zugeordnet)")
        for zeile in _fdb.list_firmen_rows(firmen_db_path(modul_db)):
            if int(zeile.get("id") or 0) == int(fid):
                gesetzt = normalisiere(zeile.get("sprache"))
                firma = str(zeile.get("name") or "")
                return Sprachen(
                    anzeige=anzeige,
                    inhalt=gesetzt or STANDARD,
                    quelle=firma if gesetzt else f"Standard (bei {firma} nicht gesetzt)",
                )
    except Exception:
        log.debug("Sprache für %s/%s nicht bestimmbar", modul, projekt_name, exc_info=True)
    return Sprachen(anzeige=anzeige, inhalt=STANDARD, quelle="Standard")


def inhalt_fuer_projekt(modul: str, projekt_name: str) -> str:
    """Kurzform: nur die Inhaltssprache eines Modulprojekts."""
    return fuer_projekt(modul, projekt_name).inhalt


def inhalt_aus_request() -> str:
    """Die Inhaltssprache des Mandanten, aus dem laufenden Request.

    WARUM ES DIESE FUNKTION BRAUCHT
    ``KiAuftrag`` trägt ``modul`` und ``projekt``, aber ``shared/sse.py`` setzt
    ``projekt`` **nicht** — auf dem SSE-Weg (die rund 45 Assistenten und
    ``/api/ai/run-stream``) kennt die Engine den Projektnamen also nicht. Ihn
    durch alle Aufrufer zu reichen wäre eine Signaturänderung an Dutzenden
    Stellen, und bei der nächsten fehlte er wieder. Stattdessen wird er aus dem
    Request gelesen — derselbe Weg, den ``prompt_zusatz.modul_aus_pfad`` für
    das Modul schon geht.

    Aufgelöst wird über ``firma_acl.request_firmen_id``: Das ist die
    vorhandene, dreistufige Auflösung (``firmen_id`` im Pfad → Firmenname →
    Projektname) und damit keine vierte Kopie derselben Logik (#1731/#1735).
    Ergänzt um den JSON-Rumpf, weil der Projektname auf dem SSE-Weg dort steht
    und nicht in der URL.

    Fail-open: Was sich nicht bestimmen lässt, ergibt ``""`` — der Aufrufer
    macht daraus die Standardsprache und damit das bisherige Verhalten.
    """
    try:
        from flask import has_request_context, request

        if not has_request_context():
            return ""

        from server.middleware.firma_acl import firma_id_by_name, request_firmen_id
        from shared.licensing.modules import module_for_path

        modul = module_for_path(request.path) or ""
        argumente = dict(request.view_args or {})

        # Der SSE-Weg schickt Projekt bzw. Firma im Rumpf, nicht im Pfad.
        if not any(argumente.get(k) for k in
                   ("firmen_id", "firma_id", "firma_name", "firma",
                    "projekt_name", "projekt")):
            rumpf = request.get_json(silent=True) or {}
            if isinstance(rumpf, dict):
                for quelle, ziel in (("projekt", "projekt_name"),
                                     ("projekt_name", "projekt_name"),
                                     ("firma", "firma_name"),
                                     ("firma_name", "firma_name")):
                    wert = rumpf.get(quelle)
                    if wert and not argumente.get(ziel):
                        argumente[ziel] = str(wert)
                # `modul` aus dem Rumpf nur als Rückfall: Der Pfad ist
                # verlässlicher, der Rumpf kommt vom Client.
                if not modul and rumpf.get("modul"):
                    modul = str(rumpf["modul"])

        fid = request_firmen_id(modul, argumente)
        if fid is None and argumente.get("firma_name"):
            fid = firma_id_by_name(str(argumente["firma_name"]))
        if not fid:
            return ""

        from server.middleware.firma_acl import _FIRMEN_DB

        return firma_sprache(_FIRMEN_DB, fid)
    except Exception:
        log.debug("Inhaltssprache nicht aus dem Request bestimmbar", exc_info=True)
    return ""


def fuer_lauf(modul: object = "", projekt: object = "") -> str:
    """Die Inhaltssprache eines KI-Laufs. ``""`` wenn nicht bestimmbar.

    Nimmt zuerst, was der Aufrufer weiss (``KiAuftrag.modul``/``.projekt``),
    und fällt sonst auf den Request zurück. Beides, weil die Engine auf dem
    synchronen Weg das Projekt kennt und auf dem SSE-Weg nicht.
    """
    if projekt:
        gesetzt = normalisiere(fuer_projekt(str(modul or ""), str(projekt)).inhalt)
        if gesetzt:
            return gesetzt
    return inhalt_aus_request()
