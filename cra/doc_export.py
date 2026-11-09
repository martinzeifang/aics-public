"""EU-Konformitätserklärung als Dokument — Anhang V (#1753).

**Was hier neu ist.** Die Erklärung existierte nur als Datensatz
(``cra_konformitaet.doc_json``, versioniert über ``doc_version``). Wer sie als
Dokument brauchte, schrieb sie außerhalb der Suite — und damit war der
strukturierte Datensatz nur noch Beiwerk. Dieses Modul erzeugt das Dokument aus
genau diesem Datensatz.

**Abgrenzung, die diese Datei trägt.** :mod:`cra.konformitaet_report` ist der
Konformitäts*nachweis* (Anforderungen mit Rechtsgrundlage, Verfahren nach
Anhang VIII, begründete Abweichungen, Anhang VII) — ein Bericht über den
Zustand. Die EU-Konformitätserklärung ist etwas anderes: die **Erklärung des
Herstellers**, die er unterschreibt und die dem Produkt beiliegt (Art. 28
i.V.m. Anhang V). Zwei Dokumente, zwei Renderer; der Nachweis wird hier nicht
angefasst und nicht wiederverwendet.

Drei Entscheidungen prägen den Inhalt:

* **Anhang V ist die Struktur, nicht nur eine Checkliste.** :data:`ANHANG_V`
  hält die Pflichtangaben mit ihrer Nummer. Aus derselben Liste kommen der
  Aufbau des Dokuments, die Vollständigkeitsprüfung und — über
  :func:`pflicht_variablen` — die Pflichtvariablen für hochgeladene
  Word-Vorlagen (:mod:`shared.templates.validate`). Eine zweite Liste derselben
  Angaben wäre die Fehlerklasse, die dieses Projekt mehrfach bezahlt hat.
* **Leer wird nicht stillschweigend gedruckt.** Fehlt eine Pflichtangabe, ist
  das Ergebnis ein als **ENTWURF** gekennzeichnetes Dokument, das die Lücken
  benennt. Die ausgestellte Fassung verlangt Vollständigkeit und bricht sonst
  mit der Liste der fehlenden Angaben ab. Eine Erklärung ohne „Ort und Datum“
  sieht aus wie eine Erklärung und ist keine (Linie aus #1741/#1751).
* **Nr. 3 ist Festtext.** Der Satz zur Alleinverantwortung ist keine Eingabe,
  sondern Gesetzeswortlaut. Er steht hier im Renderer; im Formular hätte er
  nichts zu suchen, weil man ihn dort umformulieren könnte.

**Die Sprache gehört dem Mandanten (#1954).** Die Erklärung geht vom Hersteller
an den Markt und an seine Kunden; über ihre Sprache entscheidet deshalb
``firmen.sprache`` und nicht der Bearbeiter, der sie zufällig erzeugt
(aufgelöst in :func:`build_docx` über ``shared.reports.texte.aufloesen``,
fail-open auf Deutsch). Drei Dinge bleiben dabei bewusst **unberührt**:

* :data:`ANHANG_V` ist der Rechtstext. Nummern, Reihenfolge und Pflichtfelder
  sind nicht Anzeige, sondern Struktur — übersetzt wird allein ihre
  **Beschriftung** (:data:`BEZEICHNUNG_EN`), und zwar in einer eigenen
  Zuordnung, damit der Katalog selbst nicht angefasst werden muss.
* :data:`PFLICHT_VORLAGEN` und die ``textbeleg``-Angaben prüfen hochgeladene
  Word-Vorlagen. Sie sind Prüfmaßstab, keine Prosa, und bleiben deutsch
  (siehe den Befund dazu im Issue).
* Die Meldung von :class:`PflichtfelderFehlen` bleibt deutsch: Sie geht an den
  **Bearbeiter**, und seine Sprache ist die Anzeigesprache — nicht die des
  Mandanten (``shared/sprache``: zwei Kanäle, die nicht dasselbe sind).

**Die ausgestellte Fassung liegt in einer eigenen Tabelle** (``cra_doc_final``)
und nicht in ``cra_konformitaet_final``. Begründung: Jene Tabelle ist das
Archiv des **Nachweises**; ihre Zeilen werden als „Archivierte Nachweise“ im
Release-Vorgangsbericht (``cra/release_bericht.py``) und unter
``GET …/nachweis/archiv`` ausgegeben — mit Ampel je Zeile und einem
Download-Namen „CRA-Konformitaetsnachweis…“. Eine Erklärung dort hineinzulegen
hieße, sie in genau diesen Listen als Nachweis auszuweisen (ohne Ampel, also
optisch als mangelhafter Nachweis) und unter falschem Namen zum Download
anzubieten. Dazu fehlt dort der Platz für die eigene Fassungsnummer der
Erklärung (``doc_version``). Gleiche Bauform, eigene Tabelle.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from shared import db as _sdb
from shared.reports import texte as _rt

DB_PATH = Path("data/db/cra.sqlite")

#: Ablage der ausgestellten Fassungen (PDF, unveränderlich).
STORE = Path("data/cra/konformitaetserklaerung")

REGULATION = "Verordnung (EU) 2024/2847 (Cyber Resilience Act)"
RECHTSGRUNDLAGE = "Verordnung (EU) 2024/2847, Art. 28 i.V.m. Anhang V"

#: Kennzeichnung einer unvollständigen oder nicht ausgestellten Fassung. Sie
#: steht im Titel, im Band und in der Kopftabelle — ein Entwurf, der wie eine
#: Erklärung aussieht, ist der Grund, warum später niemand mehr weiß, welche
#: Fassung gilt.
ENTWURF_MARKER = "ENTWURF — nicht ausgestellt"

#: Anhang V Nr. 3 — Festtext, kein Formularfeld (siehe Modul-Docstring).
VERANTWORTUNGSSATZ = ("Die vorliegende EU-Konformitätserklärung wird unter der "
                      "alleinigen Verantwortung des Herstellers ausgestellt.")

#: Bewertungswege, bei denen eine notifizierte Stelle beteiligt ist. Maßgeblich
#: ist der gewählte Weg und nicht die Produktklasse: Die Klasse sagt, welcher
#: Weg zulässig ist, die Erklärung muss aber das nennen, was tatsächlich
#: durchlaufen wurde (Anhang V Nr. 7 „soweit zutreffend“).
WEGE_MIT_NB = ("B+C", "H", "EUCC")

# ── Farben (Muster #1727: Farbe folgt der Aussage, nicht der Dekoration) ────
FARBEN = {"kopf": "1565C0", "entwurf": "C62828", "ausgestellt": "2E7D32"}


@dataclass(frozen=True)
class Angabe:
    """Eine Pflichtangabe aus Anhang V.

    ``nr`` ist die Nummer **in Anhang V** und darum nicht eindeutig: Nr. 8
    verlangt drei verschiedene Dinge (Zusatzangaben, Ort und Datum,
    Unterzeichner). Sie werden getrennt geführt, damit eine Meldung „Nr. 8: Ort
    und Datum fehlt“ sagen kann, was genau fehlt.
    """

    nr: int
    bezeichnung: str
    felder: tuple[str, ...]
    #: Muss im **Dokument** ausgefüllt sein, damit ausgestellt werden darf.
    daten_pflicht: bool = True
    #: Muss eine hochgeladene **Word-Vorlage** benutzen (#1753, Punkt 3).
    vorlage_pflicht: bool = True
    #: Zusätzliche Tokens, die dieselbe Angabe tragen (Vorlagen-Prüfung).
    alternativen: tuple[str, ...] = ()
    #: Textstelle, die die Angabe auch als Fließtext in der Vorlage belegt.
    #: Nr. 3 und Nr. 5 sind Gesetzesformeln; eine Vorlage darf sie wörtlich
    #: enthalten, statt die Variable zu benutzen — eine Variablen-Prüfung
    #: allein würde solche Vorlagen zu Unrecht abweisen.
    #: #1954: Ein Beleg oder mehrere (deutsch und englisch) — einer
    #: genügt. Siehe `shared/templates/validate._angabe_belegt`.
    textbeleg: str | tuple[str, ...] = ""
    #: Nur unter dieser Bedingung Pflichtangabe (``nb`` = notifizierte Stelle
    #: beteiligt).
    bedingt: str = ""


#: Anhang V — eine Quelle für Aufbau, Vollständigkeit und Vorlagen-Prüfung.
ANHANG_V: tuple[Angabe, ...] = (
    Angabe(1, "Produktname und Typ", ("produkt_name", "produkt_typ")),
    Angabe(1, "Charge, Serie oder Version", ("produkt_charge",)),
    Angabe(2, "Name des Herstellers", ("hersteller",)),
    Angabe(2, "Anschrift des Herstellers", ("hersteller_adresse",)),
    Angabe(3, "Erklärung zur Alleinverantwortung", ("verantwortungssatz",),
           textbeleg=("alleinigen Verantwortung", "sole responsibility")),
    Angabe(4, "Gegenstand der Erklärung", ("gegenstand",)),
    Angabe(5, "Konformitätsaussage zur Verordnung (EU) 2024/2847",
           ("konformitaetsaussage",), textbeleg="2024/2847"),
    # Nr. 6: Für die CRA sind noch keine harmonisierten Normen veröffentlicht.
    # Eine Pflichtangabe daraus zu machen hieße, jede Erklärung zu blockieren,
    # obwohl Anhang V nur auf **angewandte** Normen verweisen lässt. Die
    # Vorlage muss den Platz vorsehen, die Daten dürfen leer bleiben.
    Angabe(6, "Angewandte Normen und Spezifikationen", ("normen",),
           daten_pflicht=False,
           alternativen=("doc.normen_text", "doc.normen_satz")),
    # Nr. 7 „soweit zutreffend“: Pflicht nur, wenn eine notifizierte Stelle
    # beteiligt war. Eine Vorlage für ein selbstbewertetes Produkt braucht den
    # Block nicht — die Prüfung an einer Stelle scharf zu machen, an der das
    # Gesetz es nicht ist, würde nur Vorlagen abweisen.
    Angabe(7, "Notifizierte Stelle und Zertifikat",
           ("nb_name", "nb_kennnummer", "nb_zertifikat"),
           daten_pflicht=True, vorlage_pflicht=False, bedingt="nb"),
    Angabe(8, "Zusatzangaben", ("zusatzangaben",),
           daten_pflicht=False, vorlage_pflicht=False),
    Angabe(8, "Ort und Datum", ("ort", "datum")),
    Angabe(8, "Unterzeichner mit Name und Funktion",
           ("unterzeichner_name", "unterzeichner_funktion")),
)

#: Beschriftung der Anhang-V-Angaben auf Englisch (#1954).
#:
#: **Eine eigene Zuordnung und kein Feld am Katalog.** :data:`ANHANG_V` trägt
#: den Rechtstext; ein zusätzliches Feld dort hätte den Katalog angefasst, der
#: gleichzeitig Aufbau, Vollständigkeitsprüfung und Vorlagen-Prüfung speist.
#: Der Schlüssel ist die deutsche Bezeichnung — sie ist über alle 13 Einträge
#: eindeutig, und ein fehlender Eintrag fällt auf die deutsche Beschriftung
#: zurück (Muster ``shared.reports.texte.macher``), statt eine Zeile leer zu
#: lassen.
#:
#: Die Wortwahl folgt der **amtlichen englischen Fassung von Anhang V**:
#: „object of the declaration" (Nr. 4), „notified body" (Nr. 7). Die Nummern
#: werden nicht angefasst (Lehre aus #1763/#1792).
BEZEICHNUNG_EN: dict[str, str] = {
    "Produktname und Typ": "Product name and type",
    "Charge, Serie oder Version": "Batch, series or version",
    "Name des Herstellers": "Name of the manufacturer",
    "Anschrift des Herstellers": "Address of the manufacturer",
    "Erklärung zur Alleinverantwortung": "Statement of sole responsibility",
    "Gegenstand der Erklärung": "Object of the declaration",
    "Konformitätsaussage zur Verordnung (EU) 2024/2847":
        "Statement of conformity with Regulation (EU) 2024/2847",
    "Angewandte Normen und Spezifikationen":
        "Standards and specifications applied",
    "Notifizierte Stelle und Zertifikat": "Notified body and certificate",
    "Zusatzangaben": "Additional information",
    "Ort und Datum": "Place and date",
    "Unterzeichner mit Name und Funktion":
        "Signatory with name and function",
}


def bezeichnung(angabe: Angabe, sprache: str | None = None) -> str:
    """Beschriftung einer Anhang-V-Angabe in der Sprache des Dokuments."""
    from shared import sprache as _sp

    if _sp.oder_standard(sprache) == "en":
        return BEZEICHNUNG_EN.get(angabe.bezeichnung, angabe.bezeichnung)
    return angabe.bezeichnung


#: Felder, die der Anwender erfasst (``doc_json``). Abgeleitete Angaben stehen
#: absichtlich **nicht** hier: ``verantwortungssatz`` und
#: ``konformitaetsaussage`` sind Gesetzesformeln, ``normen_text`` ist nur die
#: lesbare Fassung von ``normen``.
EINGABEFELDER: tuple[str, ...] = (
    "produkt_name", "produkt_typ", "produkt_charge",
    "hersteller", "hersteller_adresse", "bevollmaechtigter",
    "gegenstand", "weiteres_unionsrecht", "normen",
    "nb_name", "nb_kennnummer", "nb_zertifikat", "nb_verfahren",
    "zusatzangaben", "ort", "datum", "unterzeichner_name", "unterzeichner_funktion",
)

#: Schalter — Ja/Nein-Feststellungen, die eine *leere* Angabe von einer
#: *bewussten Verneinung* unterscheiden (#1884/#1885).
#:
#: Ohne sie kennt der Datensatz nur „nichts erfasst", und das Dokument druckte
#: dafür einen Gedankenstrich. Der sagt weder, dass nichts angewandt wurde,
#: noch dass die Angabe fehlt — in einem unterschriebenen Dokument ist er
#: damit **keine Aussage**. Dieselbe Form an zwei Stellen: Nr. 6 (keine
#: harmonisierten Normen angewandt) und Nr. 8 (keine Zusatzangaben).
SCHALTER: tuple[str, ...] = ("keine_harmonisierten", "zusatzangaben_keine")

#: Abgeleitete Felder — immer gefüllt, nie Formulareingabe.
ABGELEITET: tuple[str, ...] = ("verantwortungssatz", "konformitaetsaussage",
                               "normen_text", "normen_satz")

#: Felder, die ausschließlich im Unterschriftsblock erscheinen. Sie zusätzlich
#: in der Aufzählung zu Nr. 8 zu drucken ließe denselben Wert zweimal im
#: Dokument stehen — in einer Erklärung liest sich das wie zwei Aussagen.
UNTERSCHRIFT_FELDER: frozenset[str] = frozenset({
    "ort", "datum", "unterzeichner_name", "unterzeichner_funktion"})


class PflichtfelderFehlen(ValueError):
    """Die ausgestellte Fassung ist nicht erzeugbar: Pflichtangaben fehlen.

    Trägt die Lücken strukturiert mit, damit eine REST-Schicht sie benennen
    kann, statt „Export fehlgeschlagen“ zu melden.
    """

    def __init__(self, fehlend: list[dict[str, Any]]) -> None:
        self.fehlend = list(fehlend)
        super().__init__(
            "Die EU-Konformitätserklärung ist unvollständig und kann nicht "
            "ausgestellt werden. Es fehlen: " + fehlend_text(fehlend))


# ── Pflichtvariablen für Word-Vorlagen ──────────────────────────────────────

def pflicht_variablen() -> list[dict[str, Any]]:
    """Was eine Word-Vorlage der Erklärung mindestens benutzen muss.

    Wird von :mod:`shared.templates.validate` gelesen (guarded import). Bei
    einem Bericht ist eine freie Vorlage Geschmacksfrage, bei der
    Konformitätserklärung ein Rechtsrisiko: Eine Vorlage, die „Ort und Datum“
    weglässt, erzeugt ein Dokument, das aussieht wie eine Erklärung und keine
    ist.
    """
    return [{
        "nr": a.nr,
        "bezeichnung": a.bezeichnung,
        "tokens": [f"doc.{f}" for f in a.felder],
        "alternativen": list(a.alternativen),
        "textbeleg": a.textbeleg,
    } for a in ANHANG_V if a.vorlage_pflicht]


#: Was ``shared.templates.validate`` braucht, um die Vorlage zu erkennen und zu
#: prüfen. ``erkennung`` ist die Wurzel, an der eine Erklärungs-Vorlage sich
#: selbst ausweist: Wer ``doc.*`` benutzt, schreibt eine Erklärung — kein
#: Gesamtbericht des Moduls tut das.
PFLICHT_VORLAGEN: list[dict[str, Any]] = [{
    "dokument": "EU-Konformitätserklärung",
    "rechtsgrundlage": RECHTSGRUNDLAGE,
    "erkennung": "doc",
    "angaben": pflicht_variablen(),
}]


# ── Daten ───────────────────────────────────────────────────────────────────

def _s(wert: Any) -> str:
    """None-sicher zu Text. ``None`` würde Jinja wörtlich drucken."""
    return "" if wert is None else str(wert).strip()


def _bool(wert: Any) -> bool:
    """Schalter aus JSON **oder** Formular. ``"false"`` ist nicht wahr.

    Der Datensatz liegt als JSON in ``doc_json``; ein Formular schickt je nach
    Weg ``true``, ``"true"``, ``1`` oder ``"1"``. Ein nackter ``bool(wert)``
    hätte aus der Zeichenkette ``"false"`` eine Feststellung gemacht — und
    diese Feststellung steht in einer Konformitätserklärung.
    """
    if isinstance(wert, bool):
        return wert
    if isinstance(wert, (int, float)):
        return bool(wert)
    return str(wert or "").strip().lower() in ("1", "true", "ja", "yes", "on")


def _normen_liste(wert: Any) -> list[str]:
    """Normen aus Liste **oder** Mehrzeiler — beides kommt aus dem Formular."""
    if isinstance(wert, (list, tuple)):
        return [_s(n) for n in wert if _s(n)]
    text = _s(wert)
    if not text:
        return []
    teile = [t.strip() for t in text.replace(";", "\n").splitlines()]
    return [t for t in teile if t]


def waehle_record(records: list[dict[str, Any]],
                  release_version: str | None = None) -> dict[str, Any]:
    """Welcher Konformitäts-Record trägt die Erklärung?

    Das Berichts-Center reicht ``version`` durch (#1748); ohne Angabe wird die
    **jüngste ausgestellte** Fassung berichtet, sonst der Produkt-Datensatz
    (leere Version), weil das Formular dort schreibt. Geraten wird nichts: Gibt
    es gar keinen Record, ist das Ergebnis ein leerer Entwurf, der das sagt.
    """
    if release_version is not None and _s(release_version) != "":
        ziel = _s(release_version)
        for r in records:
            if _s(r.get("release_version")) == ziel:
                return r
        return {}
    ausgestellt = [r for r in records if r.get("doc_ausgestellt")]
    if ausgestellt:
        return max(ausgestellt, key=lambda r: (_s(r.get("doc_ausgestellt_am")),
                                               int(r.get("doc_version") or 0)))
    for r in records:
        if _s(r.get("release_version")) == "":
            return r
    return records[0] if records else {}


def doc_daten(db_path: Path | str, projekt_name: str,
              release_version: str | None = None, *,
              sprache: str | None = None) -> dict[str, Any]:
    """Alle Angaben der Erklärung — zusammengeführt aus Record und Stammdaten.

    **Vorbelegung ist keine Erfindung.** Hersteller, Produktname und
    NB-Kennnummer stehen schon in den Projekt- bzw. Konformitäts-Stammdaten;
    sie dort zu lesen erspart die doppelte Erfassung. Was nirgends steht,
    bleibt leer und erscheint als Lücke — gefüllt wird nichts.

    ``sprache`` gilt für die **abgeleiteten** Angaben (Nr. 3 und Nr. 5 sind
    Gesetzesformeln, Nr. 6 ein Satz, ``nb_verfahren`` eine Verfahrensangabe).
    Ohne Angabe deutsch: Diese Funktion hat ein Dutzend Aufrufer — Gate,
    Prüfung, Vorlagen-Kontext, REST —, und nur die **Renderer** wissen, für
    welchen Mandanten gerendert wird. Sie lösen auf und geben den Wert hier
    hinein (Regel 3 des Umbaus: der Renderer löst auf, nicht der Aufrufer).
    """
    from shared import sprache as _sp

    from cra import konformitaet_db as kdb
    from cra.db import load_projekt

    sp = _sp.oder_standard(sprache)

    db_path = Path(db_path)
    proj = {}
    records: list[dict[str, Any]] = []
    try:
        proj = load_projekt(db_path, projekt_name) or {}
    except Exception:  # noqa: BLE001 — ein unbekanntes Projekt ergibt einen Entwurf
        proj = {}
    try:
        records = kdb.list_konformitaet(db_path, projekt_name) or []
    except Exception:  # noqa: BLE001
        records = []

    # #2076: Bei einer **genannten** Version wird die Zeile mit Vererbung
    # gelesen. ``waehle_record`` greift auf die Rohzeilen aus
    # ``list_konformitaet`` zu — damit war die mit #1886 gebaute Vererbung der
    # Erklärung (``_erbe_erklaerung``) für jeden Aufrufer unsichtbar, der eine
    # Version nennt: Der Produkt-Datensatz trägt die vollständige Erklärung,
    # die Release-Zeile hat leeres ``doc_json`` — der #1886-**Normalfall** —,
    # und das Gate schloss daraus „noch keine Erklärung erfasst". Die Prüfung
    # zu Anhang V Nr. 6 lief deshalb für jeden erbenden Vorgang gar nicht.
    #
    # Ohne Version bleibt ``waehle_record`` maßgeblich: Dort gilt die **jüngste
    # ausgestellte** Fassung (Berichts-Semantik, #1748), und die ist eine
    # andere Frage als „welche Erklärung gilt für Version X?".
    rec: dict[str, Any] = {}
    if release_version is not None and _s(release_version) != "":
        try:
            rec = kdb.get_konformitaet(db_path, projekt_name,
                                       _s(release_version), erben=True) or {}
        except Exception:  # noqa: BLE001 — Rückfall auf die Rohauswahl
            rec = {}
    if not rec:
        rec = waehle_record(records, release_version)
    roh = rec.get("doc") if isinstance(rec.get("doc"), dict) else {}

    weg = _s(rec.get("bewertungsweg"))
    nb_pflichtig = weg in WEGE_MIT_NB

    doc: dict[str, Any] = {f: _s(roh.get(f)) for f in EINGABEFELDER}
    doc["normen"] = _normen_liste(roh.get("normen"))
    for schalter in SCHALTER:
        doc[schalter] = _bool(roh.get(schalter))

    # Bestandsdaten gehen nicht verloren: das alte Formular kannte nur
    # ``modell`` und ``hersteller`` (#1201).
    if not doc["produkt_typ"]:
        doc["produkt_typ"] = _s(roh.get("modell"))
    if not doc["produkt_name"]:
        doc["produkt_name"] = _s(proj.get("produkt")) or _s(proj.get("name")) \
            or _s(projekt_name)
    if not doc["hersteller"]:
        doc["hersteller"] = _s(proj.get("unternehmen"))
    if not doc["nb_kennnummer"]:
        doc["nb_kennnummer"] = _s(rec.get("nb_kennnummer"))
    if not doc["nb_verfahren"]:
        doc["nb_verfahren"] = (_t(sp, "nb_verfahren", weg=weg) if weg else "")

    # #1886: Nr. 1 wird abgeleitet, nicht getippt. Bis v8.2.2 war „Charge,
    # Serie oder Version" ein Freitextfeld mit dem Platzhalter „z. B. Version
    # 7.4.8"; niemand hielt es nach, wenn ein Release herausging. Genau so
    # entstand der Fall aus #1885 — Nr. 1 und der Image-Tag nannten 8.2.3, der
    # Text von Nr. 4 noch 8.0.11.
    #
    # Dieselbe Mechanik wie oben: Vorbelegung ist keine Erfindung. Maßgeblich
    # ist die Version **dieser Zeile** (ein Vorgang bezeichnet genau einen
    # Stand); beim Produkt-Datensatz tritt die abgeleitete Version ein (#1820)
    # und nicht der gespeicherte Wert, der nur über „wesentliche Änderung
    # erfassen" fortgeschrieben wird. Eine ausdrückliche Eingabe bleibt stehen
    # — nach einer wesentlichen Änderung kann eine abweichende Bezeichnung
    # nötig sein.
    rec_version = _s(rec.get("release_version")) or _s(release_version)
    abgeleitet = ""
    if not doc["produkt_charge"]:
        from cra.doc_vorschlag import charge as _charge

        if not rec_version:
            try:
                from cra.release_db import get_release

                abgeleitet = _s((get_release(db_path, projekt_name) or {})
                                .get("aktuelle_version"))
            except Exception:  # noqa: BLE001 — ohne Release-Achse bleibt es leer
                abgeleitet = ""
        doc["produkt_charge"] = _charge(release_version=rec_version,
                                        abgeleitete_version=abgeleitet)

    # Abgeleitete Angaben (Nr. 3 und Nr. 5 sind Gesetzesformeln).
    doc["verantwortungssatz"] = _t(sp, "verantwortungssatz")
    doc["konformitaetsaussage"] = _konformitaetsaussage(doc, sp)
    doc["normen_text"] = ", ".join(doc["normen"])
    doc["normen_satz"] = normen_satz(doc, sprache=sp)

    fehlend = fehlende_pflichtfelder(doc, nb_pflichtig=nb_pflichtig)
    ausgestellt = bool(rec.get("doc_ausgestellt")) and not fehlend
    return {
        "projekt_name": projekt_name,
        "projekt": proj,
        "record": rec,
        "doc": doc,
        "release_version": _s(rec.get("release_version")) or _s(release_version),
        "doc_version": int(rec.get("doc_version") or 0),
        "ausgestellt_am": _s(rec.get("doc_ausgestellt_am"))[:19].replace("T", " "),
        "doc_ausgestellt": bool(rec.get("doc_ausgestellt")),
        "nb_pflichtig": nb_pflichtig,
        "bewertungsweg": weg,
        "fehlend": fehlend,
        # Ausgestellt heißt: im Datensatz ausgestellt **und** vollständig. Ein
        # vor dieser Erweiterung ausgestellter Record ist nach Anhang V
        # unvollständig — er bleibt ein Entwurf, bis die Angaben nachgetragen
        # sind. Das ist der Zweck von Punkt 4 des Issues.
        "vollstaendig": not fehlend,
        "ist_entwurf": not ausgestellt,
    }


def _konformitaetsaussage(doc: dict[str, Any], sprache: str | None = None) -> str:
    """Anhang V Nr. 5 — die Aussage selbst, nicht ihre Eingabe.

    Die Verordnung ist immer genannt; weiteres Unionsrecht kommt aus dem
    Formular (eine einzige Erklärung bei mehreren Rechtsakten, Art. 28 Abs. 2).
    """
    from shared import sprache as _sp

    sp = _sp.oder_standard(sprache)
    satz = _t(sp, "konformitaetsaussage", regulation=_t(sp, "regulation"))
    weiter = _s(doc.get("weiteres_unionsrecht"))
    if weiter:
        satz += _t(sp, "konformitaetsaussage_weiter", weiter=weiter)
    return satz


#: Nr. 6 ohne Aussage — die Lücke wird **benannt**, nicht als Strich gedruckt.
NORMEN_FEHLT = ("[fehlt — Anhang V Nr. 6: weder harmonisierte Normen oder "
                "sonstige gemeinsame Spezifikationen noch eine "
                "Cybersicherheitszertifizierung, für die die Konformität "
                "erklärt wird]")

#: Die ausdrückliche Verneinung. Sie ist der Normalfall, solange zur
#: Verordnung (EU) 2024/2847 keine harmonisierte Norm im Amtsblatt steht.
KEINE_HARMONISIERTEN_SATZ = (
    "Es wurden keine harmonisierten Normen im Sinne des Art. 27 der "
    "Verordnung (EU) 2024/2847 angewandt; zu dieser Verordnung sind bislang "
    "keine Fundstellen harmonisierter Normen im Amtsblatt der Europäischen "
    "Union veröffentlicht.")


#: Die Prosa der Erklärung je Sprache (#1954).
#:
#: **Warum der Katalog hier steht und nicht oben:** Fünf der deutschen Werte
#: *sind* die vorhandenen Modul-Konstanten (``RECHTSGRUNDLAGE``,
#: ``ENTWURF_MARKER``, ``VERANTWORTUNGSSATZ``, ``NORMEN_FEHLT``,
#: ``KEINE_HARMONISIERTEN_SATZ``). Sie werden **referenziert und nicht
#: abgeschrieben** — eine Kopie wäre die Spiegel-Liste aus #1731/#1735, und
#: hier mit besonders stillem Ausgang: Zwei Fassungen desselben
#: Gesetzeswortlauts, von denen eine im Dokument und die andere in der
#: Vorlagen-Prüfung gilt. Dafür muss der Katalog hinter den Konstanten liegen.
#:
#: **Nummern und Fundstellen werden nicht übersetzt**, nur die Bezeichnung der
#: Anlage: „Anhang V" heißt im englischen Amtsblatt „Annex V" und bezeichnet
#: dieselbe Anlage derselben Verordnung.
#:
#: Das **Datumsformat** ist Teil des Katalogs, weil ``04.11.2026`` englisch als
#: 11. April gelesen wird. Englisch wird deshalb ISO geschrieben und nicht
#: ``%d %B %Y``: ``%B`` hängt an der Locale des Containers und lieferte in
#: einem deutschen Container deutsche Monatsnamen in einem englischen
#: Dokument.
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "rechtsgrundlage": RECHTSGRUNDLAGE,
        "regulation": REGULATION,
        "entwurf_marker": ENTWURF_MARKER,
        "verantwortungssatz": VERANTWORTUNGSSATZ,
        "normen_fehlt": NORMEN_FEHLT,
        "keine_harmonisierten": KEINE_HARMONISIERTEN_SATZ,

        "titel": "EU-Konformitätserklärung",
        "titel_entwurf": " (ENTWURF)",
        "kopfzeile": "{rechtsgrundlage} · Stand {datum}",
        "datumsformat": "%d.%m.%Y",

        "band_ausgestellt": "Ausgestellte Fassung {version}",
        "band_ausgestellt_am": "Ausgestellt am {am}",
        "band_release": " · Release {version}",
        "entwurfsgrund_fehlend": (
            "Pflichtangaben nach Anhang V fehlen: {fehlend}. Dieses Dokument "
            "ist kein Nachweis und darf nicht unterzeichnet oder dem Produkt "
            "beigefügt werden."),
        "entwurfsgrund_offen": (
            "Die Angaben sind vollständig, die Erklärung ist aber noch nicht "
            "ausgestellt. Dieses Dokument ist ein Entwurf."),

        "k_angabe": "Angabe",
        "k_wert": "Wert",
        "k_projekt": "CRA-Projekt",
        "k_release": "Release / Version der Erklärung",
        "k_produkt_datensatz": "— (Produkt-Datensatz)",
        "k_fassung": " · Fassung {version}",
        "k_produktklasse": "Produktklasse",
        "k_weg": "Konformitätsbewertungsweg (Anhang VIII)",
        "k_status": "Status",
        "status_ausgestellt": "ausgestellt",

        "nb_verfahren": "Modul {weg} (Anhang VIII)",
        "konformitaetsaussage": (
            "Der oben beschriebene Gegenstand der Erklärung entspricht den "
            "einschlägigen Harmonisierungsrechtsvorschriften der Union: "
            "{regulation}."),
        "konformitaetsaussage_weiter": (
            " Darüber hinaus erfüllt der Gegenstand die folgenden weiteren "
            "Rechtsakte der Union: {weiter}."),
        "normen_spezifikationen": (
            " Zum Nachweis der Anforderungen aus Anhang I wurden die folgenden "
            "technischen Spezifikationen herangezogen: {normen}."),
        "normen_angewandt": "Angewandte Normen und Spezifikationen: {normen}.",

        "fehlend_eintrag": "Nr. {nr}: {bezeichnung}",
        "fehlt_nr": "[fehlt — Anhang V Nr. {nr}]",
        "nummer_kopf": "{nr}. {titel}",
        "angabe_label": "{bezeichnung}: ",
        "zusatzangaben_keine": "Keine weiteren Angaben.",
        "bevollmaechtigter": "Bevollmächtigter: {name}",

        "h_unterzeichnung": "Unterzeichnung",
        "ort_datum": "{ort}, {datum}",
        "unterschriftslinie": "_____________________________________",
        "name_funktion": "{name} — {funktion}",
        "fuer_hersteller": "für {hersteller}",
        "entwurf_hinweis": (
            "{marker}. Eine Erklärung, in der Pflichtangaben fehlen, sieht aus "
            "wie eine Erklärung und ist keine — deshalb trägt dieses Dokument "
            "den Entwurfsvermerk."),
        "h_ce": "CE-Kennzeichnung",
        "leer": "—",
    },
    "en": {
        "rechtsgrundlage":
            "Regulation (EU) 2024/2847, Art. 28 in conjunction with Annex V",
        "regulation": "Regulation (EU) 2024/2847 (Cyber Resilience Act)",
        # Unmissverständlich in jeder Sprache: Ein Entwurf, der wie eine
        # Erklärung aussieht, ist der Grund, warum später niemand mehr weiß,
        # welche Fassung gilt (siehe ``ENTWURF_MARKER``).
        "entwurf_marker": "DRAFT — not issued",
        # Anhang V Nr. 3 — die amtliche Formel des EU-Muster-Konformitäts-
        # erklärung (Beschluss Nr. 768/2008/EG, Anhang III), nicht eine
        # Übersetzung des deutschen Satzes.
        "verantwortungssatz": ("This declaration of conformity is issued under "
                               "the sole responsibility of the manufacturer."),
        "normen_fehlt": ("[missing — Annex V No. 6: neither harmonised standards "
                         "or other common specifications nor a cybersecurity "
                         "certification for which conformity is declared]"),
        "keine_harmonisierten": (
            "No harmonised standards within the meaning of Art. 27 of "
            "Regulation (EU) 2024/2847 were applied; to date, no references to "
            "harmonised standards for that Regulation have been published in "
            "the Official Journal of the European Union."),

        "titel": "EU declaration of conformity",
        "titel_entwurf": " (DRAFT)",
        "kopfzeile": "{rechtsgrundlage} · As of {datum}",
        "datumsformat": "%Y-%m-%d",

        "band_ausgestellt": "Issued version {version}",
        "band_ausgestellt_am": "Issued on {am}",
        "band_release": " · Release {version}",
        "entwurfsgrund_fehlend": (
            "Mandatory information under Annex V is missing: {fehlend}. This "
            "document is not evidence of conformity and must not be signed or "
            "accompany the product."),
        "entwurfsgrund_offen": (
            "The information is complete, but the declaration has not been "
            "issued yet. This document is a draft."),

        "k_angabe": "Item",
        "k_wert": "Value",
        "k_projekt": "CRA project",
        "k_release": "Release / version of the declaration",
        "k_produkt_datensatz": "— (product record)",
        "k_fassung": " · version {version}",
        "k_produktklasse": "Product class",
        "k_weg": "Conformity assessment route (Annex VIII)",
        "k_status": "Status",
        "status_ausgestellt": "issued",

        "nb_verfahren": "Module {weg} (Annex VIII)",
        # Anhang V Nr. 5 — amtlicher Wortlaut: „a statement that the object of
        # the declaration described above is in conformity with the relevant
        # Union harmonisation legislation".
        "konformitaetsaussage": (
            "The object of the declaration described above is in conformity "
            "with the relevant Union harmonisation legislation: "
            "{regulation}."),
        "konformitaetsaussage_weiter": (
            " In addition, the object is in conformity with the following "
            "further Union legal acts: {weiter}."),
        "normen_spezifikationen": (
            " The following technical specifications were relied upon as "
            "evidence of the requirements set out in Annex I: {normen}."),
        "normen_angewandt": "Standards and specifications applied: {normen}.",

        "fehlend_eintrag": "No. {nr}: {bezeichnung}",
        "fehlt_nr": "[missing — Annex V No. {nr}]",
        "nummer_kopf": "{nr}. {titel}",
        "angabe_label": "{bezeichnung}: ",
        "zusatzangaben_keine": "No further information.",
        "bevollmaechtigter": "Authorised representative: {name}",

        "h_unterzeichnung": "Signature",
        "ort_datum": "{ort}, {datum}",
        "unterschriftslinie": "_____________________________________",
        "name_funktion": "{name} — {funktion}",
        # Anhang V: „Unterzeichnet für und im Namen von" — amtlich englisch
        # „Signed for and on behalf of".
        "fuer_hersteller": "for and on behalf of {hersteller}",
        "entwurf_hinweis": (
            "{marker}. A declaration that lacks mandatory information looks "
            "like a declaration and is none — which is why this document "
            "carries the draft notice."),
        "h_ce": "CE marking",
        "leer": "—",
    },
}

_t = _rt.macher(TEXTE)

#: Überschrift je Anhang-V-Nummer auf Englisch (#1954) — Gegenstück zu
#: :data:`_NUMMER_TITEL`. Eigene Zuordnung aus demselben Grund wie
#: :data:`BEZEICHNUNG_EN`: Die Nummern gehören dem Rechtstext.
_NUMMER_TITEL_EN: dict[int, str] = {
    1: "Product identification",
    2: "Manufacturer",
    3: "Statement of sole responsibility",
    4: "Object of the declaration",
    5: "Statement of conformity",
    6: "Standards and specifications applied",
    7: "Notified body and certificate",
    8: "Additional information, place and date, signatory",
}


def _nummer_titel(nr: int, sprache: str) -> str:
    tabelle = _NUMMER_TITEL_EN if sprache == "en" else _NUMMER_TITEL
    return tabelle.get(nr, _NUMMER_TITEL.get(nr, str(nr)))


def normen_satz(werte: dict[str, Any], *, sprache: str | None = None) -> str:
    """Anhang V Nr. 6 als Satz — nie ein Gedankenstrich (#1884).

    **Der Befund aus dem Betrieb:** „‚--' wörtlich übernommen". ``_wert()``
    druckt für eine leere, nicht pflichtige Angabe ein „—". Anhang V Nr. 6
    will aber entweder die Fundstellen der angewandten harmonisierten Normen
    bzw. gemeinsamen Spezifikationen — oder, wenn keine angewandt wurden, die
    Spezifikationen, mit denen die Anforderungen aus Anhang I nachgewiesen
    wurden. Ein Strich sagt weder das eine noch das andere, und der Leser kann
    nicht unterscheiden, ob nichts angewandt wurde oder ob die Angabe fehlt.

    Dass die Angabe ``daten_pflicht=False`` trägt, bleibt richtig (die
    Begründung steht am Katalog-Eintrag): Eine Pflichtangabe daraus zu machen
    würde jede Erklärung blockieren, solange es keine harmonisierten Normen
    gibt. Die Lücke war nicht die Pflicht, sondern die fehlende **ausdrückliche
    Verneinung** — und die ist jetzt ein Schalter.

    Die **Vermutungswirkung** wird dabei nicht verwischt: Genannte
    Spezifikationen tragen sie nicht (Art. 27 gilt nur für harmonisierte
    Normen), und der Satz sagt deshalb „zum Nachweis … herangezogen" und nicht
    „angewandte harmonisierte Normen".
    """
    from shared import sprache as _sp

    sp = _sp.oder_standard(sprache)
    normen = [n for n in _normen_liste(werte.get("normen")) if n]
    verneint = _bool(werte.get("keine_harmonisierten"))
    if verneint and normen:
        return (_t(sp, "keine_harmonisierten")
                + _t(sp, "normen_spezifikationen", normen=", ".join(normen)))
    if verneint:
        return _t(sp, "keine_harmonisierten")
    if normen:
        return _t(sp, "normen_angewandt", normen=", ".join(normen))
    return _t(sp, "normen_fehlt")


def fehlende_pflichtfelder(doc: dict[str, Any], *,
                           nb_pflichtig: bool = False) -> list[dict[str, Any]]:
    """Welche Pflichtangaben aus Anhang V im Datensatz fehlen.

    Eine Angabe gilt als vorhanden, wenn **alle** ihre Felder gefüllt sind:
    „Produktname und Typ“ ohne Typ identifiziert das Produkt nicht.
    """
    fehlend: list[dict[str, Any]] = []
    for a in ANHANG_V:
        if not a.daten_pflicht:
            continue
        if a.bedingt == "nb" and not nb_pflichtig:
            continue
        leer = [f for f in a.felder
                if not (doc.get(f) if isinstance(doc.get(f), list) else _s(doc.get(f)))]
        if leer:
            fehlend.append({"nr": a.nr, "bezeichnung": a.bezeichnung,
                            "felder": leer})
    return fehlend


def fehlend_text(fehlend: list[dict[str, Any]],
                 sprache: str | None = None) -> str:
    """„Nr. 8: Ort und Datum“ — die Form, in der eine Lücke benennbar ist.

    Ohne ``sprache`` deutsch. Das ist kein Versehen: Die Funktion speist zwei
    Leser. Im **Dokument** gilt die Sprache des Mandanten; in der Meldung von
    :class:`PflichtfelderFehlen` gilt die des Bearbeiters, und die ist hier
    nicht bekannt (``shared/sprache``: Anzeige- und Inhaltssprache sind zwei
    Kanäle). Der Vorgabewert hält die Meldung bei dem, was sie vor #1954 war.
    """
    from shared import sprache as _sp

    sp = _sp.oder_standard(sprache)
    return "; ".join(
        _t(sp, "fehlend_eintrag", nr=f["nr"],
           bezeichnung=_bezeichnung_text(f, sp)) for f in fehlend) \
        or _t(sp, "leer")


def _bezeichnung_text(fehlt: dict[str, Any], sprache: str) -> str:
    """Beschriftung eines Lücken-Eintrags — über :data:`BEZEICHNUNG_EN`.

    Der Eintrag trägt die deutsche Bezeichnung (so hat sie
    :func:`fehlende_pflichtfelder` aus dem Katalog genommen); übersetzt wird
    hier, nicht dort — sonst hinge die **Datenstruktur** an der Sprache, und
    ein Aufrufer, der sie weiterverarbeitet, bekäme je Mandant andere Werte.
    """
    deutsch = _s(fehlt.get("bezeichnung"))
    if sprache == "en":
        return BEZEICHNUNG_EN.get(deutsch, deutsch)
    return deutsch


# ── Vorlagen-Kontext ────────────────────────────────────────────────────────

def kontext(db_path: Path | str, projekt_name: str,
            release_version: str | None = None, *,
            sprache: str | None = None) -> dict[str, Any]:
    """``doc``-Teilbaum für den CRA-Vorlagen-Kontext (``cra/template_context.py``).

    Keine ``None``-Werte, keine fehlenden Schlüssel: Jede in ``CRA_VARIABLES``
    deklarierte Variable muss hier ankommen, auch für ein Projekt ohne
    Erklärung (Jinja druckt ``None`` wörtlich, und
    ``tests/test_vorlagen_pruefung_1741.py`` prüft das für alle Module).

    Auch hier löst die Funktion selbst auf (#1954): Eine Vorlage **dieses**
    Mandanten (#1778) soll die Gesetzesformeln in **seiner** Sprache
    eingesetzt bekommen. Die Prosa der Vorlage gehört weiter der Vorlage; was
    hier entsteht, sind die eingesetzten Werte.
    """
    sp = _rt.aufloesen("cra", projekt_name, sprache)
    try:
        d = doc_daten(db_path, projekt_name, release_version, sprache=sp)
    except Exception:  # noqa: BLE001 — eine Vorlage darf nie an der Erklärung scheitern
        d = {"doc": {}, "fehlend": [], "ist_entwurf": True, "doc_version": 0,
             "ausgestellt_am": "", "release_version": "", "nb_pflichtig": False}
    doc = dict(d.get("doc") or {})
    for feld in EINGABEFELDER:
        doc.setdefault(feld, "")
    for schalter in SCHALTER:
        doc[schalter] = _bool(doc.get(schalter))
    doc["normen"] = list(doc.get("normen") or [])
    doc["normen_text"] = _s(doc.get("normen_text"))
    # #1884: `normen_satz` ist die druckbare Fassung von Nr. 6 — mit der
    # ausdrücklichen Verneinung, wenn keine harmonisierten Normen angewandt
    # wurden. `normen_text` bleibt die reine Aufzählung: Eine Vorlage, die
    # sie benutzt, soll sich nicht dadurch ändern, dass hier ein Satz dazukommt.
    doc["normen_satz"] = _s(doc.get("normen_satz")) or normen_satz(doc, sprache=sp)
    doc["verantwortungssatz"] = _s(doc.get("verantwortungssatz")) \
        or _t(sp, "verantwortungssatz")
    doc["konformitaetsaussage"] = _s(doc.get("konformitaetsaussage")) \
        or _konformitaetsaussage(doc, sp)
    fehlend = d.get("fehlend") or []
    doc.update({
        "rechtsgrundlage": _t(sp, "rechtsgrundlage"),
        "release_version": _s(d.get("release_version")),
        "version": int(d.get("doc_version") or 0),
        "ausgestellt_am": _s(d.get("ausgestellt_am")),
        "ist_entwurf": bool(d.get("ist_entwurf", True)),
        "fassung": (_t(sp, "entwurf_marker") if d.get("ist_entwurf", True)
                    else _t(sp, "status_ausgestellt")),
        # Die **Struktur** bleibt deutsch beschriftet (siehe
        # `_bezeichnung_text`); übersetzt ist der Satz darunter, den eine
        # Vorlage druckt.
        "fehlende_pflichtfelder": [
            {"nr": f["nr"], "bezeichnung": f["bezeichnung"]} for f in fehlend],
        "fehlende_pflichtfelder_text": (fehlend_text(fehlend, sp)
                                        if fehlend else ""),
        "nb_erforderlich": bool(d.get("nb_pflichtig")),
    })
    return doc


# ── Dokument ────────────────────────────────────────────────────────────────

def _schattieren(zelle, hex_farbe: str) -> None:
    """Zellenhintergrund — python-docx kann das nur über ``w:shd``."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_farbe)
    zelle._tc.get_or_add_tcPr().append(shd)


def _weiss_fett(zelle, text: str) -> None:
    from docx.shared import RGBColor

    run = zelle.paragraphs[0].add_run(text)
    run.bold = True
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def _tabelle(doc, kopf: list[str], zeilen: int):
    tbl = doc.add_table(rows=zeilen + 1, cols=len(kopf))
    tbl.style = "Table Grid"
    for ci, titel in enumerate(kopf):
        z = tbl.cell(0, ci)
        _schattieren(z, FARBEN["kopf"])
        _weiss_fett(z, titel)
    return tbl


def _ueberschrift(doc, text: str, level: int = 1):
    from docx.shared import RGBColor

    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x0D, 0x47, 0xA1)
    return h


def _band(doc, farbe: str, zeile1: str, zeile2: str = "") -> None:
    """Farbiges Band — das Erste, was man sehen soll."""
    from docx.shared import Pt, RGBColor

    tbl = doc.add_table(rows=1, cols=1)
    tbl.style = "Table Grid"
    z = tbl.cell(0, 0)
    _schattieren(z, farbe)
    r = z.paragraphs[0].add_run(zeile1)
    r.bold = True
    r.font.size = Pt(14)
    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    if zeile2:
        r2 = z.add_paragraph().add_run(zeile2)
        r2.font.size = Pt(10)
        r2.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    doc.add_paragraph()


def _wert(werte: dict[str, Any], angabe: Angabe, *, pflicht: bool = True,
          sprache: str = "de") -> str:
    """Anzeigewert einer Angabe — Lücken werden benannt, nicht verschwiegen.

    Auch die **halbe** Lücke: Steht der Produktname, fehlt aber der Typ, wird
    der fehlende Teil ausgewiesen. Würde nur der gefüllte Teil gedruckt, sähe
    die Zeile vollständig aus und wäre es nicht.
    """
    teile: list[str] = []
    for feld in angabe.felder:
        wert = werte.get(feld)
        if isinstance(wert, list):
            wert = ", ".join(_s(w) for w in wert)
        text = _s(wert)
        if text:
            teile.append(text)
        elif pflicht:
            teile.append(_t(sprache, "fehlt_nr", nr=angabe.nr))
    return " · ".join(teile) if teile else _t(sprache, "leer")


def build_docx(projekt: str, *, release_version: str | None = None,
               db_path: Path = DB_PATH,
               nur_ausgestellt: bool = False,
               sprache: str | None = None) -> bytes:
    """Die Erklärung als DOCX-Bytes — in der Sprache des Mandanten (#1954).

    ``nur_ausgestellt`` verlangt Vollständigkeit und bricht sonst mit
    :class:`PflichtfelderFehlen` ab — das ist der Weg für die ausgestellte
    Fassung. Ohne das Kennzeichen entsteht ein Entwurf, auch für ein Projekt
    ohne jede Erfassung: Man braucht das Dokument, um die Lücken zu sehen.
    """
    from docx import Document

    from shared.reports.docx_pdf import apply_base_font, fit_tables, set_a4

    sp = _rt.aufloesen("cra", projekt, sprache)
    d = doc_daten(db_path, projekt, release_version, sprache=sp)
    if nur_ausgestellt and d["fehlend"]:
        raise PflichtfelderFehlen(d["fehlend"])
    doc_werte = d["doc"]

    doc = Document()
    set_a4(doc, sprache=sp)
    apply_base_font(doc, sprache=sp)

    titel = _t(sp, "titel")
    if d["ist_entwurf"]:
        titel += _t(sp, "titel_entwurf")
    _ueberschrift(doc, titel, level=0)
    doc.add_paragraph(_t(sp, "kopfzeile", rechtsgrundlage=_t(sp, "rechtsgrundlage"),
                         datum=date.today().strftime(_t(sp, "datumsformat"))))

    if d["ist_entwurf"]:
        _band(doc, FARBEN["entwurf"], _t(sp, "entwurf_marker"),
              _entwurfsgrund(d, sp))
    else:
        _band(doc, FARBEN["ausgestellt"],
              _t(sp, "band_ausgestellt", version=d['doc_version']),
              _t(sp, "band_ausgestellt_am",
                 am=d['ausgestellt_am'] or _t(sp, "leer"))
              + (_t(sp, "band_release", version=d['release_version'])
                 if d["release_version"] else ""))

    _kopf(doc, d, sp)
    _angaben(doc, d, doc_werte, sp)
    _unterschrift(doc, d, doc_werte, sp)

    fit_tables(doc)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _entwurfsgrund(d: dict[str, Any], sprache: str = "de") -> str:
    """Warum dies (noch) keine Erklärung ist — in einem Satz."""
    if d["fehlend"]:
        return _t(sprache, "entwurfsgrund_fehlend",
                  fehlend=fehlend_text(d['fehlend'], sprache))
    return _t(sprache, "entwurfsgrund_offen")


def _kopf(doc, d: dict[str, Any], sprache: str = "de") -> None:
    proj = d["projekt"] or {}
    leer = _t(sprache, "leer")
    zeilen = [
        (_t(sprache, "k_projekt"), d["projekt_name"]),
        (_t(sprache, "k_release"),
         (d["release_version"] or _t(sprache, "k_produkt_datensatz"))
         + (_t(sprache, "k_fassung", version=d['doc_version'])
            if d["doc_version"] else "")),
        (_t(sprache, "k_produktklasse"), _s(proj.get("produktklasse")) or leer),
        (_t(sprache, "k_weg"), d["bewertungsweg"] or leer),
        (_t(sprache, "k_status"),
         _t(sprache, "status_ausgestellt") if not d["ist_entwurf"]
         else _t(sprache, "entwurf_marker")),
    ]
    tbl = _tabelle(doc, [_t(sprache, "k_angabe"), _t(sprache, "k_wert")], len(zeilen))
    for ri, (k, v) in enumerate(zeilen, start=1):
        tbl.cell(ri, 0).paragraphs[0].add_run(k).bold = True
        tbl.cell(ri, 1).text = str(v)
    doc.add_paragraph()


def _angaben(doc, d: dict[str, Any], werte: dict[str, Any],
             sprache: str = "de") -> None:
    """Die Erklärung selbst — in der Reihenfolge von Anhang V.

    Die Überschrift einer Nummer erscheint erst, wenn darunter wirklich etwas
    gedruckt wird. Vorher stand sie unbedingt da, und Nr. 8 trug ihre
    Überschrift, weil „Zusatzangaben: —" gedruckt wurde — eine Zeile, die den
    Strich nur verbarg. Seit #1885 entfällt diese Zeile, wenn nichts zu sagen
    ist; eine Überschrift ohne Inhalt sähe nach einer verlorenen Angabe aus.
    """
    gesehen: set[int] = set()

    def _kopf(nr: int) -> None:
        if nr not in gesehen:
            _ueberschrift(doc, _t(sprache, "nummer_kopf", nr=nr,
                                  titel=_nummer_titel(nr, sprache)), level=1)
            gesehen.add(nr)

    def _label(a: Angabe) -> str:
        return _t(sprache, "angabe_label", bezeichnung=bezeichnung(a, sprache))

    for a in ANHANG_V:
        if a.bedingt == "nb" and not d["nb_pflichtig"] \
                and not any(_s(werte.get(f)) for f in a.felder):
            # Keine notifizierte Stelle beteiligt und nichts erfasst: Der Block
            # entfällt („soweit zutreffend“), statt mit Platzhaltern zu füllen.
            continue
        if a.felder == ("verantwortungssatz",):
            _kopf(a.nr)
            doc.add_paragraph(_t(sprache, "verantwortungssatz"))
            continue
        if a.felder == ("konformitaetsaussage",):
            _kopf(a.nr)
            doc.add_paragraph(_s(werte.get("konformitaetsaussage")))
            continue
        if a.felder == ("normen",):
            # #1884: Nr. 6 ist ein Satz, nie ein Gedankenstrich. Siehe
            # `normen_satz` — die Angabe ist nicht Pflicht, aber sie muss eine
            # Aussage sein.
            _kopf(a.nr)
            p = doc.add_paragraph()
            p.add_run(_label(a)).bold = True
            p.add_run(_s(werte.get("normen_satz"))
                      or normen_satz(werte, sprache=sprache))
            continue
        if a.felder == ("zusatzangaben",):
            # #1885: „leer" und „bewusst keine" waren nicht unterscheidbar.
            # Die Feststellung gehört ins Dokument — sie ist der Beleg, dass
            # vor der Unterschrift entschieden wurde, dass nichts fehlt.
            text = _s(werte.get("zusatzangaben"))
            if not text and _bool(werte.get("zusatzangaben_keine")):
                text = _t(sprache, "zusatzangaben_keine")
            if not text:
                continue
            _kopf(a.nr)
            p = doc.add_paragraph()
            p.add_run(_label(a)).bold = True
            p.add_run(text)
            continue
        if set(a.felder) <= UNTERSCHRIFT_FELDER:
            continue      # steht im Unterschriftsblock, siehe UNTERSCHRIFT_FELDER
        # Nr. 7 ist nur Pflicht, wenn eine notifizierte Stelle beteiligt war;
        # sonst darf dort kein „[fehlt]“ stehen (Anhang V: „soweit zutreffend“).
        pflicht = a.daten_pflicht and (not a.bedingt or d["nb_pflichtig"])
        _kopf(a.nr)
        p = doc.add_paragraph()
        p.add_run(_label(a)).bold = True
        p.add_run(_wert(werte, a, pflicht=pflicht, sprache=sprache))
    # Bevollmächtigter ist keine Pflichtangabe, gehört aber zu Nr. 2, wenn er
    # erfasst ist (Art. 28 Abs. 1 i.V.m. Art. 22).
    if _s(werte.get("bevollmaechtigter")):
        doc.add_paragraph(_t(sprache, "bevollmaechtigter",
                             name=_s(werte.get('bevollmaechtigter'))))


#: Überschrift je Anhang-V-Nummer (die Angaben darunter sind feiner).
_NUMMER_TITEL: dict[int, str] = {
    1: "Produktidentifikation",
    2: "Hersteller",
    3: "Erklärung zur Alleinverantwortung",
    4: "Gegenstand der Erklärung",
    5: "Konformitätsaussage",
    6: "Angewandte Normen und Spezifikationen",
    7: "Notifizierte Stelle und Zertifikat",
    8: "Zusatzangaben, Ort und Datum, Unterzeichner",
}


def _unterschrift(doc, d: dict[str, Any], werte: dict[str, Any],
                  sprache: str = "de") -> None:
    """Unterschriftsblock — Ort, Datum, Name **und Funktion**.

    Die Funktion ist der Teil, der am häufigsten fehlt und der die Erklärung
    zurechenbar macht: „unterzeichnet von“ ohne Rolle sagt nicht, wer für den
    Hersteller sprechen durfte.
    """
    _ueberschrift(doc, _t(sprache, "h_unterzeichnung"), level=1)
    fehlt8 = _t(sprache, "fehlt_nr", nr=8)
    ort = _s(werte.get("ort")) or fehlt8
    datum = _s(werte.get("datum")) or fehlt8
    doc.add_paragraph(_t(sprache, "ort_datum", ort=ort, datum=datum))
    doc.add_paragraph()
    doc.add_paragraph(_t(sprache, "unterschriftslinie"))
    name = _s(werte.get("unterzeichner_name")) or fehlt8
    funktion = _s(werte.get("unterzeichner_funktion")) or fehlt8
    doc.add_paragraph(_t(sprache, "name_funktion", name=name, funktion=funktion))
    doc.add_paragraph(_t(sprache, "fuer_hersteller",
                         hersteller=_s(werte.get('hersteller'))
                         or _t(sprache, "fehlt_nr", nr=2)))
    if d["ist_entwurf"]:
        doc.add_paragraph(
            _t(sprache, "entwurf_hinweis",
               marker=_t(sprache, "entwurf_marker"))).italic = True

    # CE-Kennzeichnung (Art. 29/30). Bei Software ist die Erklärung der
    # vorgesehene Ort: Am Produkt lässt sich das Zeichen nicht anbringen.
    # Gedruckt wird es nur, wenn die Erklärung ausgestellt **und** die
    # Kennzeichnung angebracht ist — sonst behauptet das Dokument einen
    # Rechtsakt, der nicht stattgefunden hat. Fehlt eine der Bedingungen,
    # steht der Grund da, statt dass das Zeichen wortlos fehlt.
    from cra import ce_mark

    _ueberschrift(doc, _t(sprache, "h_ce"), level=1)
    ce_mark.einfuegen(doc, d.get("record") or {}, not d["ist_entwurf"],
                      sprache=sprache)


def build_pdf(projekt: str, *, release_version: str | None = None,
              db_path: Path = DB_PATH, nur_ausgestellt: bool = False,
              sprache: str | None = None) -> bytes:
    """PDF über denselben DOCX-Weg (#1614) — kein zweiter Renderer."""
    from shared.reports.docx_pdf import docx_bytes_to_pdf

    return docx_bytes_to_pdf(build_docx(projekt, release_version=release_version,
                                        db_path=db_path,
                                        nur_ausgestellt=nur_ausgestellt,
                                        sprache=sprache))


def build(projekt: str, *, fmt: str = "docx", release_version: str | None = None,
          db_path: Path = DB_PATH, nur_ausgestellt: bool = False,
          sprache: str | None = None) -> bytes:
    if (fmt or "docx").lower() == "pdf":
        return build_pdf(projekt, release_version=release_version, db_path=db_path,
                         nur_ausgestellt=nur_ausgestellt, sprache=sprache)
    return build_docx(projekt, release_version=release_version, db_path=db_path,
                      nur_ausgestellt=nur_ausgestellt, sprache=sprache)


# ── Unveränderliche Ablage der ausgestellten Fassung ────────────────────────

def ensure_table(db_path: Path = DB_PATH) -> None:
    """Archiv-Tabelle (idempotent). Eigene Tabelle — Begründung im Modul-Docstring."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _sdb.connect(str(db_path))
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS cra_doc_final (
                   id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                   projekt_name    TEXT NOT NULL,
                   release_version TEXT NOT NULL DEFAULT '',
                   doc_version     INTEGER NOT NULL DEFAULT 0,
                   pdf_path        TEXT NOT NULL DEFAULT '',
                   sha256          TEXT NOT NULL DEFAULT '',
                   angaben_json    TEXT NOT NULL DEFAULT '{}',
                   ausgestellt_von TEXT NOT NULL DEFAULT '',
                   ausgestellt_am  TEXT DEFAULT (aics_now())
               )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_cra_doc_final_proj "
                    "ON cra_doc_final(projekt_name)")
        con.commit()
    finally:
        con.close()


def archiviere(db_path: Path, projekt_name: str, *, pdf_bytes: bytes,
               release_version: str = "", doc_version: int = 0,
               ausgestellt_von: str = "",
               angaben: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ausgestellte Fassung unveränderlich ablegen: PDF + SHA-256.

    Append-only: Jede Ausstellung ist eine eigene Zeile mit eigener Datei. Es
    gibt bewusst kein Überschreiben und kein Update — die Erklärung ist das
    Stück, auf das sich Marktaufsicht und Kunde berufen; sie darf sich nach dem
    Ausstellen nicht ändern. Der Dateiname trägt den Hash, damit zwei Fassungen
    nie dieselbe Datei belegen.
    """
    ensure_table(db_path)
    STORE.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    roh = f"{projekt_name}_{release_version or 'produkt'}_v{int(doc_version or 0)}"
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in roh)
    pfad = STORE / f"{safe}_{sha[:12]}.pdf"
    pfad.write_bytes(pdf_bytes)
    con = _sdb.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO cra_doc_final (projekt_name, release_version, doc_version, "
            "pdf_path, sha256, angaben_json, ausgestellt_von) VALUES (?,?,?,?,?,?,?)",
            (projekt_name, release_version or "", int(doc_version or 0), str(pfad),
             sha, json.dumps(angaben or {}, ensure_ascii=False), ausgestellt_von or ""))
        con.commit()
    finally:
        con.close()
    return {"projekt_name": projekt_name, "release_version": release_version or "",
            "doc_version": int(doc_version or 0), "sha256": sha,
            "pdf_path": str(pfad), "ausgestellt_von": ausgestellt_von or ""}


def list_archiv(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _sdb.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT id, release_version, doc_version, sha256, pdf_path, "
            "ausgestellt_von, ausgestellt_am FROM cra_doc_final "
            "WHERE projekt_name=? ORDER BY ausgestellt_am DESC, id DESC",
            (projekt_name,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_archiv(db_path: Path, projekt_name: str, final_id: int) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _sdb.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT * FROM cra_doc_final WHERE id=? AND projekt_name=?",
            (int(final_id), projekt_name)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def ausstellen(projekt: str, *, release_version: str = "", von: str = "",
               db_path: Path = DB_PATH, bestaetigt: tuple[str, ...] | list[str] = (),
               pdf_bytes: bytes | None = None) -> dict[str, Any]:
    """Ausgestellte Fassung erzeugen und unveränderlich ablegen.

    Bricht mit :class:`PflichtfelderFehlen` ab, wenn Anhang-V-Angaben fehlen —
    **vor** der PDF-Erzeugung, damit die Meldung die Lücken nennt und nicht der
    Konverter nach einer Minute eine unvollständige Erklärung ausliefert.

    Seit #1885 bricht sie außerdem bei einem **Widerspruch** ab: ein
    unvollständiger Digest, eine Versionsangabe, die der eigenen Akte
    widerspricht. Das ist keine Lücke, sondern eine Falschaussage über den
    Gegenstand — und für sie gibt es bewusst **keine** Bestätigungsmöglichkeit.
    ``bestaetigt`` nimmt nur die Schlüssel echter Grenzfälle auf (siehe
    ``cra.doc_pruefung``).

    ``pdf_bytes`` ist für Aufrufer gedacht, die die Datei schon haben (und für
    Tests ohne PDF-Konverter); ohne Angabe wird sie hier erzeugt.
    """
    from cra import doc_pruefung as _pr

    # #1954: Die ausgestellte Fassung ist das Stück, auf das sich Marktaufsicht
    # und Kunde berufen — sie entsteht in der Sprache des Mandanten, und der
    # archivierte Datensatz (`angaben`) trägt dieselben Gesetzesformeln wie die
    # abgelegte PDF. Zwei Sprachen in einem Archiveintrag wären zwei Fassungen
    # derselben Erklärung.
    sp = _rt.aufloesen("cra", projekt, None)
    d = doc_daten(db_path, projekt, release_version or None, sprache=sp)
    if d["fehlend"]:
        raise PflichtfelderFehlen(d["fehlend"])
    befunde = _pr.befunde(db_path, projekt, release_version or "")
    if _pr.blockierend(befunde):
        raise _pr.ErklaerungUnstimmig(_pr.blockierend(befunde))
    offen = [b for b in _pr.bestaetigungen(befunde)
             if b.get("confirm") not in set(bestaetigt or ())]
    if offen:
        raise _pr.BestaetigungErforderlich(offen)
    pdf = pdf_bytes if pdf_bytes is not None else build_pdf(
        projekt, release_version=release_version or None, db_path=db_path,
        nur_ausgestellt=True, sprache=sp)
    return archiviere(db_path, projekt, pdf_bytes=pdf,
                      release_version=d["release_version"],
                      doc_version=d["doc_version"], ausgestellt_von=von,
                      angaben=d["doc"])
