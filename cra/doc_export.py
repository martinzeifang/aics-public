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
    textbeleg: str = ""
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
           textbeleg="alleinigen Verantwortung"),
    Angabe(4, "Gegenstand der Erklärung", ("gegenstand",)),
    Angabe(5, "Konformitätsaussage zur Verordnung (EU) 2024/2847",
           ("konformitaetsaussage",), textbeleg="2024/2847"),
    # Nr. 6: Für die CRA sind noch keine harmonisierten Normen veröffentlicht.
    # Eine Pflichtangabe daraus zu machen hieße, jede Erklärung zu blockieren,
    # obwohl Anhang V nur auf **angewandte** Normen verweisen lässt. Die
    # Vorlage muss den Platz vorsehen, die Daten dürfen leer bleiben.
    Angabe(6, "Angewandte Normen und Spezifikationen", ("normen",),
           daten_pflicht=False, alternativen=("doc.normen_text",)),
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

#: Abgeleitete Felder — immer gefüllt, nie Formulareingabe.
ABGELEITET: tuple[str, ...] = ("verantwortungssatz", "konformitaetsaussage",
                               "normen_text")

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
              release_version: str | None = None) -> dict[str, Any]:
    """Alle Angaben der Erklärung — zusammengeführt aus Record und Stammdaten.

    **Vorbelegung ist keine Erfindung.** Hersteller, Produktname und
    NB-Kennnummer stehen schon in den Projekt- bzw. Konformitäts-Stammdaten;
    sie dort zu lesen erspart die doppelte Erfassung. Was nirgends steht,
    bleibt leer und erscheint als Lücke — gefüllt wird nichts.
    """
    from cra import konformitaet_db as kdb
    from cra.db import load_projekt

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

    rec = waehle_record(records, release_version)
    roh = rec.get("doc") if isinstance(rec.get("doc"), dict) else {}

    weg = _s(rec.get("bewertungsweg"))
    nb_pflichtig = weg in WEGE_MIT_NB

    doc: dict[str, Any] = {f: _s(roh.get(f)) for f in EINGABEFELDER}
    doc["normen"] = _normen_liste(roh.get("normen"))

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
        doc["nb_verfahren"] = (f"Modul {weg} (Anhang VIII)" if weg else "")

    # Abgeleitete Angaben (Nr. 3 und Nr. 5 sind Gesetzesformeln).
    doc["verantwortungssatz"] = VERANTWORTUNGSSATZ
    doc["konformitaetsaussage"] = _konformitaetsaussage(doc)
    doc["normen_text"] = ", ".join(doc["normen"])

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


def _konformitaetsaussage(doc: dict[str, Any]) -> str:
    """Anhang V Nr. 5 — die Aussage selbst, nicht ihre Eingabe.

    Die Verordnung ist immer genannt; weiteres Unionsrecht kommt aus dem
    Formular (eine einzige Erklärung bei mehreren Rechtsakten, Art. 28 Abs. 2).
    """
    satz = ("Der oben beschriebene Gegenstand der Erklärung entspricht den "
            "einschlägigen Harmonisierungsrechtsvorschriften der Union: "
            f"{REGULATION}.")
    weiter = _s(doc.get("weiteres_unionsrecht"))
    if weiter:
        satz += (" Darüber hinaus erfüllt der Gegenstand die folgenden weiteren "
                 f"Rechtsakte der Union: {weiter}.")
    return satz


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


def fehlend_text(fehlend: list[dict[str, Any]]) -> str:
    """„Nr. 8: Ort und Datum“ — die Form, in der eine Lücke benennbar ist."""
    return "; ".join(f"Nr. {f['nr']}: {f['bezeichnung']}" for f in fehlend) or "—"


# ── Vorlagen-Kontext ────────────────────────────────────────────────────────

def kontext(db_path: Path | str, projekt_name: str,
            release_version: str | None = None) -> dict[str, Any]:
    """``doc``-Teilbaum für den CRA-Vorlagen-Kontext (``cra/template_context.py``).

    Keine ``None``-Werte, keine fehlenden Schlüssel: Jede in ``CRA_VARIABLES``
    deklarierte Variable muss hier ankommen, auch für ein Projekt ohne
    Erklärung (Jinja druckt ``None`` wörtlich, und
    ``tests/test_vorlagen_pruefung_1741.py`` prüft das für alle Module).
    """
    try:
        d = doc_daten(db_path, projekt_name, release_version)
    except Exception:  # noqa: BLE001 — eine Vorlage darf nie an der Erklärung scheitern
        d = {"doc": {}, "fehlend": [], "ist_entwurf": True, "doc_version": 0,
             "ausgestellt_am": "", "release_version": "", "nb_pflichtig": False}
    doc = dict(d.get("doc") or {})
    for feld in EINGABEFELDER:
        doc.setdefault(feld, "")
    doc["normen"] = list(doc.get("normen") or [])
    doc["normen_text"] = _s(doc.get("normen_text"))
    doc["verantwortungssatz"] = _s(doc.get("verantwortungssatz")) or VERANTWORTUNGSSATZ
    doc["konformitaetsaussage"] = _s(doc.get("konformitaetsaussage")) \
        or _konformitaetsaussage(doc)
    fehlend = d.get("fehlend") or []
    doc.update({
        "rechtsgrundlage": RECHTSGRUNDLAGE,
        "release_version": _s(d.get("release_version")),
        "version": int(d.get("doc_version") or 0),
        "ausgestellt_am": _s(d.get("ausgestellt_am")),
        "ist_entwurf": bool(d.get("ist_entwurf", True)),
        "fassung": ENTWURF_MARKER if d.get("ist_entwurf", True) else "ausgestellt",
        "fehlende_pflichtfelder": [
            {"nr": f["nr"], "bezeichnung": f["bezeichnung"]} for f in fehlend],
        "fehlende_pflichtfelder_text": fehlend_text(fehlend) if fehlend else "",
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


def _wert(werte: dict[str, Any], angabe: Angabe, *, pflicht: bool = True) -> str:
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
            teile.append(f"[fehlt — Anhang V Nr. {angabe.nr}]")
    return " · ".join(teile) if teile else "—"


def build_docx(projekt: str, *, release_version: str | None = None,
               db_path: Path = DB_PATH,
               nur_ausgestellt: bool = False) -> bytes:
    """Die Erklärung als DOCX-Bytes.

    ``nur_ausgestellt`` verlangt Vollständigkeit und bricht sonst mit
    :class:`PflichtfelderFehlen` ab — das ist der Weg für die ausgestellte
    Fassung. Ohne das Kennzeichen entsteht ein Entwurf, auch für ein Projekt
    ohne jede Erfassung: Man braucht das Dokument, um die Lücken zu sehen.
    """
    from docx import Document

    from shared.reports.docx_pdf import apply_base_font, fit_tables, set_a4

    d = doc_daten(db_path, projekt, release_version)
    if nur_ausgestellt and d["fehlend"]:
        raise PflichtfelderFehlen(d["fehlend"])
    doc_werte = d["doc"]

    doc = Document()
    set_a4(doc)
    apply_base_font(doc)

    titel = "EU-Konformitätserklärung"
    if d["ist_entwurf"]:
        titel += " (ENTWURF)"
    _ueberschrift(doc, titel, level=0)
    doc.add_paragraph(f"{RECHTSGRUNDLAGE} · Stand {date.today().strftime('%d.%m.%Y')}")

    if d["ist_entwurf"]:
        _band(doc, FARBEN["entwurf"], ENTWURF_MARKER,
              _entwurfsgrund(d))
    else:
        _band(doc, FARBEN["ausgestellt"],
              f"Ausgestellte Fassung {d['doc_version']}",
              f"Ausgestellt am {d['ausgestellt_am'] or '—'}"
              + (f" · Release {d['release_version']}" if d["release_version"] else ""))

    _kopf(doc, d)
    _angaben(doc, d, doc_werte)
    _unterschrift(doc, d, doc_werte)

    fit_tables(doc)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _entwurfsgrund(d: dict[str, Any]) -> str:
    """Warum dies (noch) keine Erklärung ist — in einem Satz."""
    if d["fehlend"]:
        return ("Pflichtangaben nach Anhang V fehlen: "
                f"{fehlend_text(d['fehlend'])}. Dieses Dokument ist kein "
                "Nachweis und darf nicht unterzeichnet oder dem Produkt "
                "beigefügt werden.")
    return ("Die Angaben sind vollständig, die Erklärung ist aber noch nicht "
            "ausgestellt. Dieses Dokument ist ein Entwurf.")


def _kopf(doc, d: dict[str, Any]) -> None:
    proj = d["projekt"] or {}
    zeilen = [
        ("CRA-Projekt", d["projekt_name"]),
        ("Release / Version der Erklärung",
         (d["release_version"] or "— (Produkt-Datensatz)")
         + (f" · Fassung {d['doc_version']}" if d["doc_version"] else "")),
        ("Produktklasse", _s(proj.get("produktklasse")) or "—"),
        ("Konformitätsbewertungsweg (Anhang VIII)", d["bewertungsweg"] or "—"),
        ("Status", "ausgestellt" if not d["ist_entwurf"] else ENTWURF_MARKER),
    ]
    tbl = _tabelle(doc, ["Angabe", "Wert"], len(zeilen))
    for ri, (k, v) in enumerate(zeilen, start=1):
        tbl.cell(ri, 0).paragraphs[0].add_run(k).bold = True
        tbl.cell(ri, 1).text = str(v)
    doc.add_paragraph()


def _angaben(doc, d: dict[str, Any], werte: dict[str, Any]) -> None:
    """Die Erklärung selbst — in der Reihenfolge von Anhang V."""
    gesehen: set[int] = set()
    for a in ANHANG_V:
        if a.bedingt == "nb" and not d["nb_pflichtig"] \
                and not any(_s(werte.get(f)) for f in a.felder):
            # Keine notifizierte Stelle beteiligt und nichts erfasst: Der Block
            # entfällt („soweit zutreffend“), statt mit Platzhaltern zu füllen.
            continue
        if a.nr not in gesehen:
            _ueberschrift(doc, f"{a.nr}. {_NUMMER_TITEL[a.nr]}", level=1)
            gesehen.add(a.nr)
        if a.felder == ("verantwortungssatz",):
            doc.add_paragraph(VERANTWORTUNGSSATZ)
            continue
        if a.felder == ("konformitaetsaussage",):
            doc.add_paragraph(_s(werte.get("konformitaetsaussage")))
            continue
        if set(a.felder) <= UNTERSCHRIFT_FELDER:
            continue      # steht im Unterschriftsblock, siehe UNTERSCHRIFT_FELDER
        # Nr. 7 ist nur Pflicht, wenn eine notifizierte Stelle beteiligt war;
        # sonst darf dort kein „[fehlt]“ stehen (Anhang V: „soweit zutreffend“).
        pflicht = a.daten_pflicht and (not a.bedingt or d["nb_pflichtig"])
        p = doc.add_paragraph()
        p.add_run(f"{a.bezeichnung}: ").bold = True
        p.add_run(_wert(werte, a, pflicht=pflicht))
    # Bevollmächtigter ist keine Pflichtangabe, gehört aber zu Nr. 2, wenn er
    # erfasst ist (Art. 28 Abs. 1 i.V.m. Art. 22).
    if _s(werte.get("bevollmaechtigter")):
        doc.add_paragraph(f"Bevollmächtigter: {_s(werte.get('bevollmaechtigter'))}")


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


def _unterschrift(doc, d: dict[str, Any], werte: dict[str, Any]) -> None:
    """Unterschriftsblock — Ort, Datum, Name **und Funktion**.

    Die Funktion ist der Teil, der am häufigsten fehlt und der die Erklärung
    zurechenbar macht: „unterzeichnet von“ ohne Rolle sagt nicht, wer für den
    Hersteller sprechen durfte.
    """
    _ueberschrift(doc, "Unterzeichnung", level=1)
    ort = _s(werte.get("ort")) or "[fehlt — Anhang V Nr. 8]"
    datum = _s(werte.get("datum")) or "[fehlt — Anhang V Nr. 8]"
    doc.add_paragraph(f"{ort}, {datum}")
    doc.add_paragraph()
    doc.add_paragraph("_____________________________________")
    name = _s(werte.get("unterzeichner_name")) or "[fehlt — Anhang V Nr. 8]"
    funktion = _s(werte.get("unterzeichner_funktion")) or "[fehlt — Anhang V Nr. 8]"
    doc.add_paragraph(f"{name} — {funktion}")
    doc.add_paragraph(f"für {_s(werte.get('hersteller')) or '[fehlt — Anhang V Nr. 2]'}")
    if d["ist_entwurf"]:
        doc.add_paragraph(
            f"{ENTWURF_MARKER}. Eine Erklärung, in der Pflichtangaben fehlen, "
            "sieht aus wie eine Erklärung und ist keine — deshalb trägt dieses "
            "Dokument den Entwurfsvermerk.").italic = True

    # CE-Kennzeichnung (Art. 29/30). Bei Software ist die Erklärung der
    # vorgesehene Ort: Am Produkt lässt sich das Zeichen nicht anbringen.
    # Gedruckt wird es nur, wenn die Erklärung ausgestellt **und** die
    # Kennzeichnung angebracht ist — sonst behauptet das Dokument einen
    # Rechtsakt, der nicht stattgefunden hat. Fehlt eine der Bedingungen,
    # steht der Grund da, statt dass das Zeichen wortlos fehlt.
    from cra import ce_mark

    _ueberschrift(doc, "CE-Kennzeichnung", level=1)
    ce_mark.einfuegen(doc, d.get("record") or {}, not d["ist_entwurf"])


def build_pdf(projekt: str, *, release_version: str | None = None,
              db_path: Path = DB_PATH, nur_ausgestellt: bool = False) -> bytes:
    """PDF über denselben DOCX-Weg (#1614) — kein zweiter Renderer."""
    from shared.reports.docx_pdf import docx_bytes_to_pdf

    return docx_bytes_to_pdf(build_docx(projekt, release_version=release_version,
                                        db_path=db_path,
                                        nur_ausgestellt=nur_ausgestellt))


def build(projekt: str, *, fmt: str = "docx", release_version: str | None = None,
          db_path: Path = DB_PATH, nur_ausgestellt: bool = False) -> bytes:
    if (fmt or "docx").lower() == "pdf":
        return build_pdf(projekt, release_version=release_version, db_path=db_path,
                         nur_ausgestellt=nur_ausgestellt)
    return build_docx(projekt, release_version=release_version, db_path=db_path,
                      nur_ausgestellt=nur_ausgestellt)


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
               db_path: Path = DB_PATH,
               pdf_bytes: bytes | None = None) -> dict[str, Any]:
    """Ausgestellte Fassung erzeugen und unveränderlich ablegen.

    Bricht mit :class:`PflichtfelderFehlen` ab, wenn Anhang-V-Angaben fehlen —
    **vor** der PDF-Erzeugung, damit die Meldung die Lücken nennt und nicht der
    Konverter nach einer Minute eine unvollständige Erklärung ausliefert.

    ``pdf_bytes`` ist für Aufrufer gedacht, die die Datei schon haben (und für
    Tests ohne PDF-Konverter); ohne Angabe wird sie hier erzeugt.
    """
    d = doc_daten(db_path, projekt, release_version or None)
    if d["fehlend"]:
        raise PflichtfelderFehlen(d["fehlend"])
    pdf = pdf_bytes if pdf_bytes is not None else build_pdf(
        projekt, release_version=release_version or None, db_path=db_path,
        nur_ausgestellt=True)
    return archiviere(db_path, projekt, pdf_bytes=pdf,
                      release_version=d["release_version"],
                      doc_version=d["doc_version"], ausgestellt_von=von,
                      angaben=d["doc"])
