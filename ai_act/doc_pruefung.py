"""Die AI-Act-Erklärung vor dem Ausstellen prüfen (#1889).

Die Fehlerbilder sind dieselben wie beim CRA (#1885) und liegen seit #1893 in
:mod:`shared.formular_pruefung`: Platzhalter, unvollständiger Digest,
Versions-Widerspruch, die drei Wirkungsstufen. Hier steht nur, was die KI-VO
eigen hat.

**Zwei Befunde sind KI-VO-spezifisch:**

* **Nr. 5 ohne Entscheidung.** Verarbeitet das System personenbezogene Daten?
  Der Schalter kennt „nicht entschieden" und „nein" nicht auseinander
  (``INTEGER NOT NULL DEFAULT 0``, die Lehre aus #1805) — gedruckt wird die
  Erklärung nur bei ``True``, und solange niemand entschieden hat, ist das
  ein Hinweis und keine Verneinung.
* **Verfahren und notifizierte Stelle müssen zusammenpassen.** Das Verfahren
  nach Anhang VII setzt eine notifizierte Stelle voraus (Art. 43 Abs. 1 für
  Anhang III Nr. 1); eine Erklärung, die das Verfahren nennt und keine Stelle,
  ist in sich widersprüchlich. Umgekehrt ist eine genannte Stelle bei interner
  Kontrolle nach Anhang VI ein Hinweis — zulässig ist es (freiwillige
  Beteiligung), erklärungsbedürftig auch.

**Keine Digest-Prüfung.** Anhang V der KI-VO verlangt keine Artefakt-Referenz;
der gemeinsame Baustein wird deshalb nicht gerufen. Ihn „sicherheitshalber"
mitzunehmen hieße, eine Pflicht zu suggerieren, die der Rechtstext nicht
nennt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from shared import formular_pruefung as fp
from shared.formular_pruefung import (WIRKUNG_BESTAETIGUNG, WIRKUNG_BLOCKIERT,
                                      WIRKUNG_HINWEIS, bestaetigungen,
                                      blockierend, offene_bestaetigungen,
                                      version_nummer)

DB_PATH = Path("data/db/ai_act.sqlite")

#: Bestätigungsschlüssel, die ein Aufrufer mitschicken kann.
CONFIRM_DATUM = "confirm_datum"

_ZUSATZ_TEXTE: tuple[str, ...] = ("doc_text",)


class ErklaerungUnstimmig(fp.FormularUnstimmig):
    """Die Erklärung trägt eine nachweislich falsche Aussage."""

    def __init__(self, befunde: list[dict[str, Any]]) -> None:
        super().__init__(befunde,
                         einleitung="Die EU-Konformitätserklärung kann nicht "
                                    "ausgestellt werden")


class BestaetigungErforderlich(fp.BestaetigungErforderlich):
    """Ein Grenzfall, den nur ein Mensch verantworten kann."""


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def _pruefbare_felder() -> tuple[str, ...]:
    """Positivliste der Eingabefelder (die Falle aus #1885).

    Abgeleitete Felder tragen absichtlich Texte wie ``[fehlt — Nr. 6 …]``;
    über sie zu prüfen würde jede Erklärung ohne Nr. 6 blockieren.
    """
    from ai_act.doc_export import EINGABEFELDER

    return tuple(EINGABEFELDER) + _ZUSATZ_TEXTE


_KATALOG_CACHE: tuple[dict[str, int], dict[str, str]] | None = None


def _katalog() -> tuple[dict[str, int], dict[str, str]]:
    """Feld → Nummer und Feld → Beschriftung aus Anhang V der KI-VO."""
    global _KATALOG_CACHE
    if _KATALOG_CACHE is not None:
        return _KATALOG_CACHE

    from ai_act.doc_export import ANHANG_V

    _KATALOG_CACHE = fp.katalog_zuordnung(ANHANG_V, zusatz={
        "weiteres_unionsrecht": (4, "Weiteres Unionsrecht"),
        "bevollmaechtigter": (2, "EU-Bevollmächtigter"),
        "zusatzangaben": (8, "Zusatzangaben"),
        "doc_text": (0, "Entwurfstext des Assistenten"),
    })
    return _KATALOG_CACHE


def _nr_fuer(feld: str) -> int:
    return _katalog()[0].get(feld, 0)


def _feld_label(feld: str) -> str:
    return _katalog()[1].get(feld, feld)


def pruefe(doc: dict[str, Any], *, nb_pflichtig: bool = False,
           nb_genannt: bool = False, bewertungsdatum: str = "",
           erlaubte_versionen: set[str] | None = None
           ) -> list[dict[str, Any]]:
    """Widersprüche und Platzhalter in einer AI-Act-Erklärung — ohne Datenbank."""
    doc = dict(doc or {})
    pruefbar = _pruefbare_felder()
    befunde: list[dict[str, Any]] = []

    # Versionen: nur wenn die Akte welche kennt (sonst kein Abgleich, #1805).
    erlaubt = {v for v in (erlaubte_versionen or set()) if v}
    if version_nummer(doc.get("system_kennung")):
        erlaubt.add(version_nummer(doc.get("system_kennung")))
    befunde += fp.version_befunde(
        doc, ("system_kennung", "zusatzangaben"), erlaubt,
        _feld_label, _nr_fuer,
        hinweis="Eine der Angaben ist falsch. Maßgeblich ist die Fassung des "
                "KI-Systems, die in Verkehr gebracht wird.")

    # Nr. 5 — personenbezogene Daten: entschieden oder nicht?
    if "personenbezogene_daten" not in doc or doc.get(
            "personenbezogene_daten") in (None, ""):
        befunde.append(fp.befund(
            "datenschutz_unbestimmt", feld="personenbezogene_daten", nr=5,
            art="unbestaetigt", wirkung=WIRKUNG_HINWEIS,
            text="Zu Nr. 5 ist nicht entschieden, ob das KI-System "
                 "personenbezogene Daten verarbeitet.",
            hinweis="Nur bei „ja“ wird die Erklärung zum Datenschutzrecht "
                    "gedruckt. Solange niemand entschieden hat, fehlt sie — "
                    "und das Fehlen ist dann keine Verneinung."))

    # Nr. 7 — Verfahren und notifizierte Stelle.
    if nb_pflichtig and not _s(doc.get("nb_name")):
        befunde.append(fp.befund(
            "nb_fehlt", feld="nb_name", nr=7, art="widerspruch",
            wirkung=WIRKUNG_BLOCKIERT,
            text="Das Verfahren nach Anhang VII setzt eine notifizierte "
                 "Stelle voraus; in der Erklärung ist keine genannt.",
            hinweis="Trage die Stelle und ihre Kennnummer in der "
                    "Konformitätsbewertung ein — von dort wird die Erklärung "
                    "gefüllt."))
    if not nb_pflichtig and nb_genannt:
        befunde.append(fp.befund(
            "nb_ohne_verfahren", feld="nb_name", nr=7, art="widerspruch",
            wirkung=WIRKUNG_HINWEIS,
            text="Die Erklärung nennt eine notifizierte Stelle, das Verfahren "
                 "ist aber die interne Kontrolle nach Anhang VI.",
            hinweis="Eine freiwillige Beteiligung ist zulässig und "
                    "erklärungsbedürftig — nenne sie in den Zusatzangaben, "
                    "oder stelle das Verfahren richtig."))

    # Nr. 6 — ohne Aussage. Derselbe Gedankenstrich wie im CRA (#1884).
    if not doc.get("keine_harmonisierten") and not (doc.get("normen") or []):
        befunde.append(fp.befund(
            "normen_unbestimmt", feld="normen", nr=6, art="unbestaetigt",
            wirkung=WIRKUNG_HINWEIS,
            text="Nr. 6 trägt weder die Feststellung, dass keine "
                 "harmonisierten Normen angewandt wurden, noch genannte "
                 "Spezifikationen.",
            hinweis="Anhang V Nr. 6 will das eine oder das andere. Zur KI-VO "
                    "ist bislang keine harmonisierte Norm im Amtsblatt "
                    "veröffentlicht (Art. 40)."))

    # Nr. 8 — Zusatzangaben ohne Entscheidung.
    if not _s(doc.get("zusatzangaben")) and not doc.get("zusatzangaben_keine"):
        befunde.append(fp.befund(
            "zusatzangaben_unbestaetigt", feld="zusatzangaben", nr=8,
            art="unbestaetigt", wirkung=WIRKUNG_HINWEIS,
            text="Zu den Zusatzangaben ist nichts erfasst und nicht "
                 "festgestellt, dass keine aufzunehmen sind.",
            hinweis="Rechtlich ist leer zulässig; vor der Unterschrift soll "
                    "aber entschieden sein, dass nichts fehlt."))

    # Nr. 8 — Datum vor dem Abschluss der Bewertung.
    befunde += fp.datum_vor_befund(
        doc.get("datum"), bewertungsdatum, feld="datum", nr=8,
        bid="datum_vor_bewertung", confirm=CONFIRM_DATUM,
        was="Die Erklärung",
        bezug_label="der Abschluss der Konformitätsbewertung")

    platz = fp.platzhalter_befunde(doc, pruefbar, _feld_label, _nr_fuer)
    return ([b for b in platz if b["wirkung"] == WIRKUNG_BLOCKIERT]
            + befunde
            + [b for b in platz if b["wirkung"] != WIRKUNG_BLOCKIERT])


def befunde(db_path: Path | str = DB_PATH, projekt_name: str = "",
            doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Die Befunde zu einer Erklärung — Daten holen und :func:`pruefe` rufen."""
    from ai_act.doc_export import VERFAHREN_MIT_NB, doc_daten

    db_path = Path(db_path)

    def _sicher(fn, standard):
        try:
            return fn()
        except (ImportError, AttributeError):
            raise
        except Exception:  # noqa: BLE001
            return standard

    d = _sicher(lambda: doc_daten(db_path, projekt_name), {})
    zusammen = dict(d.get("doc") or {})
    if doc:
        zusammen.update(doc)
    rec = d.get("record") if isinstance(d.get("record"), dict) else {}
    verfahren = _s(rec.get("verfahren"))
    return pruefe(
        zusammen,
        nb_pflichtig=verfahren in VERFAHREN_MIT_NB,
        nb_genannt=bool(_s(zusammen.get("nb_name"))),
        bewertungsdatum=_s(rec.get("bewertungsdatum")))


__all__ = ["WIRKUNG_BLOCKIERT", "WIRKUNG_BESTAETIGUNG", "WIRKUNG_HINWEIS",
           "CONFIRM_DATUM", "ErklaerungUnstimmig", "BestaetigungErforderlich",
           "pruefe", "befunde", "blockierend", "bestaetigungen",
           "offene_bestaetigungen"]
