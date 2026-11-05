"""Die Konformitätserklärung vor dem Ausstellen prüfen — gerechnet, nicht bemerkt (#1885).

DER BEFUND AUS DEM BETRIEB
--------------------------
Nach dem Erzeugen einer Erklärung kamen Bemerkungen der KI zurück: der Digest
sei mit ``sha256:…`` unvollständig, der Text nenne „Release 8.0.11" während
Nr. 1 und der Image-Tag 8.2.3 nennen, der Satz zur Versionsanzeige stehe ohne
Grundlage, die Zusatzangaben seien als ``[FEHLT]`` übergeben, das
Ausstellungsdatum liege vor der Freigabe des Release.

**Alle fünf sind rechenbar.** Dass sie als KI-Bemerkung erschienen, ist das
eigentliche Problem: Sie kommen **nach** dem Dokument, kosten einen Lauf und
erscheinen nicht zuverlässig wieder — ein zweiter Lauf kann andere Bemerkungen
liefern oder dieselbe weglassen. Ein Prüfer, der sich darauf verlässt, verlässt
sich auf eine Wahrscheinlichkeit. In einem Dokument, das der Hersteller unter
seiner Alleinverantwortung unterschreibt, ist das die falsche
Instrumentenwahl.

WAS VORHER GEPRÜFT WURDE
------------------------
``doc_export.fehlende_pflichtfelder()`` prüft **ausschließlich Leere**. Ein
Feld, das gefüllt ist und einen Platzhalter oder eine falsche Zahl enthält, war
für diese Prüfung vollständig. Genau dort liegen vier der fünf Bemerkungen.

WAS HIER STEHT UND WAS IN ``shared``
------------------------------------
Die drei wiederkehrenden Fehlerbilder — Platzhalter, unvollständiger Digest,
Versions-Widerspruch — und die drei Wirkungsstufen liegen seit #1893 in
:mod:`shared.formular_pruefung`; die AI-Act-Erklärung (#1889) und das DSGVO-VVT
(#1890) benutzen dieselben. Hier steht nur, was CRA-eigen ist: die Quellen
(SBOM-Verzeichnis, Release-Historie, Freigabedatum des Vorgangs) und die drei
Befunde, die Anhang V eigen sind (Versionsanzeige, Zusatzangaben, Nr. 6).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from shared import formular_pruefung as fp
from shared.formular_pruefung import (WIRKUNG_BESTAETIGUNG, WIRKUNG_BLOCKIERT,
                                      WIRKUNG_HINWEIS, bestaetigungen,
                                      blockierend, version_nummer,
                                      versionen_im_kontext)

DB_PATH = Path("data/db/cra.sqlite")

#: Bestätigungsschlüssel, die ein Aufrufer mitschicken kann.
CONFIRM_DATUM = "confirm_datum"

#: Zusätzlich geprüft, obwohl kein Feld der Erklärung: der Entwurfstext des
#: KI-Assistenten. Ein „[zu ergänzen]" darin fällt sonst erst auf, wenn jemand
#: das Dokument liest.
_ZUSATZ_TEXTE: tuple[str, ...] = ("doc_text",)

#: Der Satz zur Versionsanzeige — eine Behauptung über das Produkt.
_SATZ_VERSIONSANZEIGE = re.compile(r"installierte\s+Version", re.IGNORECASE)


class ErklaerungUnstimmig(fp.FormularUnstimmig):
    """Die Erklärung trägt eine nachweislich falsche Aussage.

    Erbt über :class:`shared.formular_pruefung.FormularUnstimmig` von
    ``ValueError``, weil die REST-Schicht Fachfehler bereits als 409
    ausliefert (Muster :class:`cra.doc_export.PflichtfelderFehlen`).
    """

    def __init__(self, befunde: list[dict[str, Any]]) -> None:
        super().__init__(befunde,
                         einleitung="Die EU-Konformitätserklärung kann nicht "
                                    "ausgestellt werden")


class BestaetigungErforderlich(fp.BestaetigungErforderlich):
    """Ein Grenzfall, den nur ein Mensch verantworten kann."""


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def _pruefbare_felder() -> tuple[str, ...]:
    """Welche Werte überhaupt geprüft werden — eine **Positivliste**.

    **Der Fehler, den das verhindert, war meiner.** Die erste Fassung ging über
    *alle* Schlüssel des Dicts, und darin stehen auch die abgeleiteten Felder.
    ``normen_satz`` trägt bei fehlender Angabe absichtlich den Text
    ``[fehlt — Anhang V Nr. 6 …]`` — den hat die Platzhalter-Prüfung gefunden
    und **jede** Erklärung ohne Nr. 6 blockiert. Der Prüfer schlug auf seinen
    eigenen Hinweistext an; dieselbe Klasse wie der Wächter, der einen
    Kommentar las (#1834/#1867/#1878), nur diesmal blockierend.

    Eine Negativliste („alles außer ``normen_satz``") wäre die falsche
    Richtung: Das nächste abgeleitete Feld bringt sie wieder zum Anschlagen.
    Geprüft wird, was ein Mensch eingegeben hat.
    """
    from cra.doc_export import EINGABEFELDER

    return tuple(EINGABEFELDER) + _ZUSATZ_TEXTE


_KATALOG_CACHE: tuple[dict[str, int], dict[str, str]] | None = None


def _katalog() -> tuple[dict[str, int], dict[str, str]]:
    """Feld → Anhang-V-Nummer und Feld → Beschriftung.

    Gelesen wird ``doc_export.ANHANG_V``, nicht eine eigene Tabelle: Eine
    zweite Zuordnung wäre die Spiegel-Liste aus #1731/#1735, und sie würde in
    einer Fehlermeldung stehen — also genau da, wo ein Anwender sich auf sie
    verlässt.
    """
    global _KATALOG_CACHE
    if _KATALOG_CACHE is not None:
        return _KATALOG_CACHE

    from cra.doc_export import ANHANG_V

    _KATALOG_CACHE = fp.katalog_zuordnung(ANHANG_V, zusatz={
        "weiteres_unionsrecht": (5, "Weiteres Unionsrecht"),
        "bevollmaechtigter": (2, "EU-Bevollmächtigter"),
        "nb_verfahren": (7, "Durchgeführtes Verfahren"),
        # Kein Feld der Erklärung, sondern der Entwurfstext des Assistenten.
        "doc_text": (0, "Entwurfstext des Assistenten"),
    })
    return _KATALOG_CACHE


def _nr_fuer(feld: str) -> int:
    return _katalog()[0].get(feld, 0)


def _feld_label(feld: str) -> str:
    return _katalog()[1].get(feld, feld)


# ── Die Prüfung ─────────────────────────────────────────────────────────────

def pruefe(doc: dict[str, Any], *, nb_pflichtig: bool = False,
           version: str = "", erlaubte_versionen: set[str] | None = None,
           freigegeben_am: str = "", release_label: str = "",
           versionsanzeige_erfasst: bool = False,
           belegte_normen: set[str] | None = None,
           katalog_normen: set[str] | None = None) -> list[dict[str, Any]]:
    """Widersprüche und Platzhalter in einer Erklärung — ohne Datenbank.

    ``erlaubte_versionen`` sind die Versionen, die die Akte für diesen Stand
    kennt: die Version des Vorgangs, die in Nr. 1 erfasste und die Tags der
    zugeordneten Images. Ist die Menge leer, findet **kein** Abgleich statt —
    ohne Vergleichsmaßstab wäre jede genannte Version „falsch", und das wäre
    die Art Fehlalarm, die einen Prüfer unglaubwürdig macht (#1805).
    """
    doc = dict(doc or {})
    pruefbar = _pruefbare_felder()
    befunde: list[dict[str, Any]] = []

    # 1 — Der unvollständige Digest, der die Meldung ausgelöst hat. Eigener
    # Befund, weil er eine eigene Behebung hat („SBOM vom Image holen").
    befunde += fp.digest_befunde(
        doc, pruefbar, _feld_label, _nr_fuer,
        hinweis="Der Digest bezeichnet das Artefakt, das in Verkehr geht. "
                "„SBOM vom Image holen“ im C1-Abschnitt löst ihn auf; der "
                "Vorschlag für Nr. 4 setzt ihn dann vollständig ein.")

    # 2 — Widerspruch in der Versionsangabe. Nennt der Text eine Version, die
    # die Akte für diesen Stand nicht kennt, ist eine der Angaben falsch —
    # welche, kann die Anwendung nicht entscheiden, aber **dass** sie
    # auseinanderfallen, kann sie.
    erlaubt = {v for v in (erlaubte_versionen or set()) if v}
    if version_nummer(version):
        erlaubt.add(version_nummer(version))
    # Die eigene Angabe aus Nr. 1 gilt als bekannt: Eine Erklärung darf für
    # einen Stand geschrieben werden, den die Release-Historie noch nicht
    # führt. Damit kann Nr. 1 diese Prüfung aber **nie** reißen — den
    # Widerspruch zwischen Nr. 1 und Nr. 4 findet erst die Prüfung darunter.
    if version_nummer(doc.get("produkt_charge")):
        erlaubt.add(version_nummer(doc.get("produkt_charge")))
    befunde += fp.version_befunde(
        doc, ("gegenstand", "produkt_charge", "zusatzangaben"), erlaubt,
        _feld_label, _nr_fuer,
        hinweis="Eine der Angaben ist falsch. Maßgeblich ist die Version, die "
                "herausgegeben wird — der Vorschlag für Nr. 4 setzt sie aus "
                "der Release-Historie und dem Image-Tag ein.")

    # 2b — Nr. 1 gegen Nr. 4 (#1901). Die Prüfung darüber fragt jedes Feld
    # **gegen die Akte**; der gemeldete Fall nannte in Nr. 1 die Version
    # 8.0.11 und in Nr. 4 „Release 8.0.1" — beide der Akte bekannt, also jede
    # einzeln plausibel. Zusammen bezeichnen sie nicht denselben Stand, und
    # das sah nur das Sprachmodell **nach** dem Dokument.
    befunde += fp.versions_konflikt_befunde(
        [("produkt_charge", [version_nummer(doc.get("produkt_charge"))]),
         ("gegenstand", versionen_im_kontext(doc.get("gegenstand")))],
        _feld_label, _nr_fuer,
        hinweis="Nr. 1 bezeichnet die Charge, Serie oder Version, Nr. 4 den "
                "Gegenstand — sie müssen denselben Stand nennen. „⚙ Aus den "
                "Quellen füllen“ setzt in beide die Version ein, die "
                "herausgegeben wird.")

    # 3 — Unbelegte Aussage über das Produkt.
    if _SATZ_VERSIONSANZEIGE.search(_s(doc.get("gegenstand"))) \
            and not versionsanzeige_erfasst:
        befunde.append(fp.befund(
            "versionsanzeige_unbelegt", feld="gegenstand", nr=4, art="unbelegt",
            wirkung=WIRKUNG_HINWEIS,
            text="Der Gegenstand sagt, wo die installierte Version angezeigt "
                 "wird — in den Projekt-Stammdaten ist das nicht erfasst.",
            hinweis="Die Aussage ist nur haltbar, wenn die Anzeige im Produkt "
                    "wirklich existiert. Trage sie in den Stammdaten ein oder "
                    "streiche den Satz."))

    # 4 — Optionale Angabe ohne Entscheidung. „Leer" und „bewusst keine" sind
    # im Datensatz nicht unterscheidbar; genau das war bei Nr. 6 der
    # Gedankenstrich (#1884).
    if not _s(doc.get("zusatzangaben")) and not doc.get("zusatzangaben_keine"):
        befunde.append(fp.befund(
            "zusatzangaben_unbestaetigt", feld="zusatzangaben", nr=8,
            art="unbestaetigt", wirkung=WIRKUNG_HINWEIS,
            text="Zu den Zusatzangaben (Nr. 8) ist nichts erfasst und nicht "
                 "festgestellt, dass keine aufzunehmen sind.",
            hinweis="Rechtlich ist leer zulässig. Vor der Unterschrift soll "
                    "aber entschieden sein, dass nichts fehlt — dafür ist der "
                    "Schalter „keine Zusatzangaben“ da."))

    # 5 — Nr. 6 ohne Aussage. Der gemeldete Gedankenstrich.
    if not doc.get("keine_harmonisierten") and not (doc.get("normen") or []):
        befunde.append(fp.befund(
            "normen_unbestimmt", feld="normen", nr=6, art="unbestaetigt",
            wirkung=WIRKUNG_HINWEIS,
            text="Nr. 6 trägt weder die ausdrückliche Feststellung, dass keine "
                 "harmonisierten Normen angewandt wurden, noch genannte "
                 "Spezifikationen.",
            hinweis="Anhang V Nr. 6 will das eine oder das andere. Im Dokument "
                    "stand dafür bisher ein Gedankenstrich — der sagt weder, "
                    "dass nichts angewandt wurde, noch dass die Angabe fehlt."))

    # 5b — Nr. 6 nennt, was die Akte nicht belegt (#1901). Gemeldet kam
    # „CycloneDX, SLSA, Sigstore/cosign, OWASP Top 10", belegt waren OWASP
    # Proactive Controls und SPDX. Hinweis und nicht Sperre: Ein Haus darf
    # eine Spezifikation anwenden, die diese Anwendung nicht führt — dann ist
    # die Angabe richtig und die Akte unvollständig.
    befunde += fp.unbelegte_angaben_befunde(
        doc.get("normen") or [],
        belegt=belegte_normen or (), katalog=katalog_normen or (),
        feld="normen", nr=6, bid="normen_unbelegt",
        was="Nr. 6 nennt Spezifikationen",
        akte=(", ".join(sorted(belegte_normen or ())) or
              "nach dieser Akte nichts"),
        hinweis="Belegt ist, was OWASP-Register, Bedrohungsmodell, "
                "SBOM-Format und ein verknüpftes WiBA-Projekt hergeben. "
                "Entweder die Angabe darauf zurückführen oder den Nachweis "
                "erfassen — sonst trägt die unterschriebene Erklärung eine "
                "unbelegte Aussage.")

    # 6 — Ausstellungsdatum vor der Freigabe des erklärten Release.
    befunde += fp.datum_vor_befund(
        doc.get("datum"), freigegeben_am, feld="datum", nr=8,
        bid="datum_vor_freigabe", confirm=CONFIRM_DATUM, was="Die Erklärung",
        bezug_label=(f"die Freigabe des Release {release_label}".rstrip()
                     if release_label else "die Freigabe des Release"))

    # 7 — Platzhalter: die blockierenden nach vorn, die schwachen Anzeichen
    # nach hinten, damit sie die harten Befunde nicht verdecken.
    platz = fp.platzhalter_befunde(doc, pruefbar, _feld_label, _nr_fuer)
    return ([b for b in platz if b["wirkung"] == WIRKUNG_BLOCKIERT]
            + befunde
            + [b for b in platz if b["wirkung"] != WIRKUNG_BLOCKIERT])


# ── Der eine Ort, an dem gelesen wird ───────────────────────────────────────

def befunde(db_path: Path | str = DB_PATH, projekt_name: str = "",
            release_version: str = "",
            doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Die Befunde zu einer Erklärung — Daten holen und :func:`pruefe` rufen.

    ``doc`` übersteuert den gespeicherten Datensatz: Der Ausstellungsweg prüft
    den Stand, der **gespeichert werden soll**, nicht den davor.
    """
    from cra.db import list_sbom
    from cra.doc_export import doc_daten
    from cra.doc_vorschlag import _artefakte_aus_sbom

    db_path = Path(db_path)

    def _sicher(fn, standard):
        try:
            return fn()
        except Exception:  # noqa: BLE001
            return standard

    d = _sicher(lambda: doc_daten(db_path, projekt_name,
                                  release_version or None), {})
    zusammen = dict((d.get("doc") or {}))
    if doc:
        zusammen.update(doc)

    version = _s(d.get("release_version")) or _s(release_version)

    # Erlaubte Versionen: die des Vorgangs und die Tags der zugeordneten
    # Images. Mehr nicht — geraten wird nichts.
    erlaubt: set[str] = set()
    sboms = _sicher(lambda: list_sbom(db_path, projekt_name) or [], [])
    for z in sboms:
        if version and version_nummer(z.get("release_version")) != version_nummer(version):
            continue
        if version_nummer(z.get("release_version")):
            erlaubt.add(version_nummer(z.get("release_version")))
    for a in _sicher(lambda: _artefakte_aus_sbom(sboms, version), []):
        tag = _s(a.get("referenz")).rsplit(":", 1)[-1]
        if version_nummer(tag):
            erlaubt.add(version_nummer(tag))

    proj = d.get("projekt") if isinstance(d.get("projekt"), dict) else {}
    meta = proj.get("meta") if isinstance(proj.get("meta"), dict) else {}
    doc_meta = meta.get("doc") if isinstance(meta.get("doc"), dict) else {}

    rec = d.get("record") if isinstance(d.get("record"), dict) else {}
    frei = _s(rec.get("freigegeben_am")) or _s(rec.get("veroeffentlicht_am"))

    # Was die Akte für Nr. 6 belegt (#1901). Die Zusammenstellung kommt aus
    # `doc_vorschlag` — dieselbe, die der Vorschlag zum Anhaken anbietet. Eine
    # zweite Herleitung wäre eine zweite Aussage darüber, was belegt ist.
    from cra import normen_katalog as _nk
    from cra.doc_vorschlag import belegte_normen as _belegte

    return pruefe(
        zusammen, nb_pflichtig=bool(d.get("nb_pflichtig")), version=version,
        erlaubte_versionen=erlaubt, freigegeben_am=frei,
        release_label=version,
        versionsanzeige_erfasst=bool(_s(doc_meta.get("versionsanzeige"))),
        belegte_normen=set(_sicher(lambda: _belegte(db_path, projekt_name), [])),
        katalog_normen={n.bezeichnung for n in _nk.ALLE})


__all__ = ["WIRKUNG_BLOCKIERT", "WIRKUNG_BESTAETIGUNG", "WIRKUNG_HINWEIS",
           "CONFIRM_DATUM", "ErklaerungUnstimmig", "BestaetigungErforderlich",
           "pruefe", "befunde", "blockierend", "bestaetigungen",
           "versionen_im_kontext", "version_nummer"]
