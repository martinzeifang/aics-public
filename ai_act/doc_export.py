"""EU-Konformitätserklärung nach Art. 47 i.V.m. Anhang V der KI-VO (#1889).

DER BEFUND
----------
Die Erklärung existierte in der Suite **nur als Prompt**
(``ai_act/ai_wizards.build_konformitaetserklaerung_prompt``, A8). Kein
Datensatz, keine Felder, keine Vollständigkeitsprüfung, kein Ausstellen, kein
Archiv. ``aiact_conformity`` führt den **Verfahrensweg** (interne Kontrolle
nach Anhang VI bzw. notifizierte Stelle nach Anhang VII) — nicht die
Erklärung.

Art. 47 Abs. 1 der Verordnung (EU) 2024/1689 verlangt sie für **jedes**
Hochrisiko-KI-System; Abs. 2 verlangt, sie zehn Jahre nach dem
Inverkehrbringen für die zuständigen Behörden bereitzuhalten. Die Anwendung
erzeugte einen KI-Entwurf, den der Anwender außerhalb weiterverarbeitete —
womit der strukturierte Nachweis fehlte und :mod:`shared.ki_herkunft` ihn als
ungeprüften Entwurf führte.

Das ist dieselbe Klasse wie #1814, eine Stufe früher: Dort galt eine **leere**
Erklärung als ausgestellt, hier gab es **nichts zu füllen**.

ZUR NUMMERIERUNG — GEPRÜFT
--------------------------
Anhang V der KI-VO ist **nicht** Anhang V der CRA: Die Inhalte und ihre
Reihenfolge unterscheiden sich, und Nr. 5 (Datenschutz-Erklärung) hat in der
CRA keine Entsprechung. :data:`ANHANG_V` folgt dem Verordnungstext und wurde
**nicht** aus dem CRA-Modul übernommen; wer eine Nummer kopiert, druckt sie
später in ein unterschriebenes Dokument (die Lehre aus #1763/#1792).

**Nachgeprüft am 30.10.2026** gegen zwei voneinander unabhängige
Wiedergaben des Verordnungstextes: Anhang V hat **acht** Nummern, und die
Zuordnung unten stimmt — insbesondere ist Nr. 5 die Datenschutz-Erklärung
(Verordnung (EU) 2016/679, Verordnung (EU) 2018/1725, Richtlinie (EU)
2016/680) „soweit das System personenbezogene Daten verarbeitet", Nr. 6 die
angewandten Normen und Nr. 7 die notifizierte Stelle mit Kennnummer,
Verfahrensbeschreibung und Bescheinigung.

**Maßgeblich bleibt die amtliche Fassung im Amtsblatt** — beide geprüften
Quellen weisen ausdrücklich darauf hin, dass sie keine Rechtswirkung haben.
Die Verordnung gehört deshalb in die Installation, so wie der CRA-Text dort
unter ``data/cra_resources/32024R2847_DEU.pdf`` liegt: Der Download-Dialog des
Gutachten-Moduls holt CELEX ``32024R1689`` nach
:data:`VERORDNUNG_VERZEICHNIS` (``data/ai_act_resources/``). Liegt sie dort,
ist die Nummerierung am Original nachlesbar, ohne sie zu suchen.

WAS VON WO KOMMT
----------------
Der Bauplan ist der aus #1884–#1887; die gemeinsamen Teile liegen seit #1893
in :mod:`shared.formular_vorschlag` und :mod:`shared.formular_pruefung`. Hier
steht nur das KI-VO-Eigene: der Katalog, die Quellen (KI-System, Mandant,
Konformitätsbewertung) und die Erklärungstexte.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from shared import db as _sdb

DB_PATH = Path("data/db/ai_act.sqlite")

#: Ablage der ausgestellten Fassungen (PDF, unveränderlich).
STORE = Path("data/aiact/konformitaetserklaerung")

#: Wo die amtliche Fassung der Verordnung in der Installation liegt. Dasselbe
#: Verzeichnis, das der Download-Dialog des Gutachten-Moduls befüllt
#: (``ai_act_dir``, CELEX ``32024R1689``) — eine zweite Ablage wäre eine
#: zweite Wahrheit über denselben Text.
VERORDNUNG_VERZEICHNIS = Path("data/ai_act_resources")
VERORDNUNG_CELEX = "32024R1689"

REGULATION = "Verordnung (EU) 2024/1689 (KI-Verordnung)"
RECHTSGRUNDLAGE = "Verordnung (EU) 2024/1689, Art. 47 i.V.m. Anhang V"

#: Kennzeichnung einer unvollständigen oder nicht ausgestellten Fassung.
ENTWURF_MARKER = "ENTWURF — nicht ausgestellt"

#: Anhang V Nr. 3 — Festtext, kein Formularfeld.
VERANTWORTUNGSSATZ = ("Die vorliegende EU-Konformitätserklärung wird unter der "
                      "alleinigen Verantwortung des Anbieters ausgestellt.")

#: Anhang V Nr. 5 — die Datenschutz-Erklärung, soweit das System
#: personenbezogene Daten verarbeitet. Sie ist der Punkt, den die CRA nicht
#: kennt; als Festtext, weil es Gesetzeswortlaut ist und kein Formularfeld.
DATENSCHUTZSATZ = (
    "Soweit das KI-System personenbezogene Daten verarbeitet, entspricht es "
    "der Verordnung (EU) 2016/679, der Verordnung (EU) 2018/1725 und der "
    "Richtlinie (EU) 2016/680.")

#: Verfahren, bei denen eine notifizierte Stelle beteiligt ist.
VERFAHREN_MIT_NB = ("annex_vii_nb",)


@dataclass(frozen=True)
class Angabe:
    """Eine Pflichtangabe aus Anhang V der KI-VO.

    Gleiche Bauform wie ``cra.doc_export.Angabe``, damit
    ``shared.formular_pruefung.katalog_zuordnung`` beide lesen kann — aber ein
    **eigener Katalog**: Die Inhalte sind verschieden.
    """

    nr: int
    bezeichnung: str
    felder: tuple[str, ...]
    daten_pflicht: bool = True
    #: Nur unter dieser Bedingung Pflichtangabe (``nb`` = notifizierte Stelle).
    bedingt: str = ""
    rechtsbezug: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"nr": self.nr, "bezeichnung": self.bezeichnung,
                "felder": list(self.felder), "pflicht": self.daten_pflicht,
                "bedingt": self.bedingt, "rechtsbezug": self.rechtsbezug}


#: Anhang V der KI-VO — eine Quelle für Aufbau und Vollständigkeit.
ANHANG_V: tuple[Angabe, ...] = (
    Angabe(1, "Name und Typ des KI-Systems", ("system_name", "system_typ"),
           rechtsbezug="Anhang V Nr. 1"),
    Angabe(1, "Eindeutige Kennung zur Rückverfolgbarkeit", ("system_kennung",),
           rechtsbezug="Anhang V Nr. 1"),
    Angabe(2, "Name des Anbieters", ("anbieter",),
           rechtsbezug="Anhang V Nr. 2"),
    Angabe(2, "Anschrift des Anbieters", ("anbieter_adresse",),
           rechtsbezug="Anhang V Nr. 2"),
    # Nr. 2 nennt den Bevollmächtigten ausdrücklich mit („and that of any
    # authorised representative"), aber nur „falls zutreffend" — deshalb
    # Katalog-Eintrag ohne Datenpflicht. Als loser Absatz außerhalb des
    # Katalogs hatte er keine Nummer, und die Vollständigkeitsanzeige kannte
    # ihn nicht.
    Angabe(2, "EU-Bevollmächtigter (falls vorhanden)", ("bevollmaechtigter",),
           daten_pflicht=False, rechtsbezug="Anhang V Nr. 2"),
    Angabe(3, "Erklärung zur Alleinverantwortung", ("verantwortungssatz",),
           rechtsbezug="Anhang V Nr. 3"),
    Angabe(4, "Konformitätsaussage zur Verordnung (EU) 2024/1689",
           ("konformitaetsaussage",), rechtsbezug="Anhang V Nr. 4"),
    # Nr. 5 greift nur, wenn das System personenbezogene Daten verarbeitet.
    # Als Pflichtangabe für jedes System wäre es eine erfundene Rechtspflicht;
    # der Schalter entscheidet, und der Satz ist Gesetzeswortlaut.
    Angabe(5, "Erklärung zum Datenschutzrecht", ("datenschutzsatz",),
           daten_pflicht=False, rechtsbezug="Anhang V Nr. 5"),
    # Nr. 6: Zur KI-VO sind nach heutigem Stand keine harmonisierten Normen im
    # Amtsblatt veröffentlicht — dieselbe Lage wie beim CRA (#1884). Eine
    # Pflichtangabe daraus zu machen hieße, jede Erklärung zu blockieren; die
    # Lücke ist nicht die Pflicht, sondern die fehlende **ausdrückliche
    # Verneinung**, und die ist ein Schalter.
    Angabe(6, "Angewandte Normen und Spezifikationen", ("normen",),
           daten_pflicht=False, rechtsbezug="Anhang V Nr. 6, Art. 40/41"),
    # Nr. 7 verlangt drei Dinge: Name und Kennnummer der notifizierten Stelle,
    # eine **Beschreibung des durchgeführten Verfahrens** und die Bescheinigung
    # — und zwar „soweit zutreffend". Das Verfahren wird aber **immer**
    # durchgeführt (interne Kontrolle nach Anhang VI oder notifizierte Stelle
    # nach Anhang VII); nur die Stelle und ihre Bescheinigung gibt es nicht
    # immer. Beides in einer Angabe hätte entweder das Verfahren verschwiegen,
    # wenn keine Stelle beteiligt ist, oder eine Stelle behauptet, wo keine ist.
    Angabe(7, "Durchgeführtes Konformitätsbewertungsverfahren",
           ("nb_verfahren",), daten_pflicht=False,
           rechtsbezug="Anhang V Nr. 7, Art. 43"),
    Angabe(7, "Notifizierte Stelle und Bescheinigung",
           ("nb_name", "nb_kennnummer", "nb_bescheinigung"),
           bedingt="nb", rechtsbezug="Anhang V Nr. 7, Anhang VII"),
    Angabe(8, "Ort und Datum", ("ort", "datum"),
           rechtsbezug="Anhang V Nr. 8"),
    Angabe(8, "Unterzeichner mit Name und Funktion",
           ("unterzeichner_name", "unterzeichner_funktion"),
           rechtsbezug="Anhang V Nr. 8"),
    Angabe(8, "In wessen Namen unterzeichnet wird", ("unterzeichner_fuer",),
           rechtsbezug="Anhang V Nr. 8"),
)

#: Felder, die der Anwender erfasst (``doc_json``).
EINGABEFELDER: tuple[str, ...] = (
    "system_name", "system_typ", "system_kennung",
    "anbieter", "anbieter_adresse", "bevollmaechtigter",
    "weiteres_unionsrecht", "normen",
    "nb_name", "nb_kennnummer", "nb_verfahren", "nb_bescheinigung",
    "zusatzangaben", "ort", "datum",
    "unterzeichner_name", "unterzeichner_funktion", "unterzeichner_fuer",
)

#: Schalter — sie unterscheiden eine *leere* Angabe von einer *bewussten
#: Verneinung* (#1884/#1885). ``personenbezogene_daten`` entscheidet über
#: Nr. 5: Die Erklärung dort zu drucken, ohne dass das System solche Daten
#: verarbeitet, wäre eine Aussage über etwas, das nicht stattfindet.
SCHALTER: tuple[str, ...] = ("keine_harmonisierten", "zusatzangaben_keine",
                             "personenbezogene_daten")

#: Abgeleitete Felder — immer gefüllt, nie Formulareingabe.
ABGELEITET: tuple[str, ...] = ("verantwortungssatz", "konformitaetsaussage",
                               "datenschutzsatz", "normen_text", "normen_satz")

#: Felder, die ausschließlich im Unterschriftsblock erscheinen.
UNTERSCHRIFT_FELDER: frozenset[str] = frozenset({
    "ort", "datum", "unterzeichner_name", "unterzeichner_funktion",
    "unterzeichner_fuer"})

#: Nr. 6 ohne Aussage — die Lücke wird **benannt**, nicht als Strich gedruckt.
NORMEN_FEHLT = ("[fehlt — Anhang V Nr. 6: weder die Feststellung, dass keine "
                "harmonisierten Normen angewandt wurden, noch die zum "
                "Nachweis herangezogenen Spezifikationen]")

KEINE_HARMONISIERTEN_SATZ = (
    "Es wurden keine harmonisierten Normen im Sinne des Art. 40 der "
    "Verordnung (EU) 2024/1689 angewandt; zu dieser Verordnung sind bislang "
    "keine Fundstellen harmonisierter Normen im Amtsblatt der Europäischen "
    "Union veröffentlicht.")


class PflichtfelderFehlen(ValueError):
    """Die ausgestellte Fassung ist nicht erzeugbar: Pflichtangaben fehlen."""

    def __init__(self, fehlend: list[dict[str, Any]]) -> None:
        self.fehlend = list(fehlend)
        super().__init__(
            "Die EU-Konformitätserklärung ist unvollständig und kann nicht "
            "ausgestellt werden. Es fehlen: " + fehlend_text(fehlend))


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def _bool(wert: Any) -> bool:
    """Schalter aus JSON **oder** Formular. ``"false"`` ist nicht wahr."""
    if isinstance(wert, bool):
        return wert
    if isinstance(wert, (int, float)):
        return bool(wert)
    return str(wert or "").strip().lower() in ("1", "true", "ja", "yes", "on")


def _normen_liste(wert: Any) -> list[str]:
    if isinstance(wert, (list, tuple)):
        return [_s(n) for n in wert if _s(n)]
    text = _s(wert)
    if not text:
        return []
    return [t.strip() for t in text.replace(";", "\n").splitlines() if t.strip()]


def fehlend_text(fehlend: list[dict[str, Any]]) -> str:
    return "; ".join(f"Nr. {f['nr']}: {f['bezeichnung']}" for f in fehlend) or "—"


def normen_satz(werte: dict[str, Any]) -> str:
    """Anhang V Nr. 6 als Satz — nie ein Gedankenstrich (#1884/#1889).

    Die **Vermutungswirkung** wird nicht verwischt: Nach Art. 40 löst nur eine
    harmonisierte Norm sie aus; genannte Spezifikationen sind Nachweismittel.
    Der Satz sagt deshalb „zum Nachweis … herangezogen".
    """
    normen = [n for n in _normen_liste(werte.get("normen")) if n]
    verneint = _bool(werte.get("keine_harmonisierten"))
    if verneint and normen:
        return (KEINE_HARMONISIERTEN_SATZ + " Zum Nachweis der Anforderungen "
                "aus Kapitel III Abschnitt 2 wurden die folgenden technischen "
                "Spezifikationen herangezogen: " + ", ".join(normen) + ".")
    if verneint:
        return KEINE_HARMONISIERTEN_SATZ
    if normen:
        return "Angewandte Normen und Spezifikationen: " + ", ".join(normen) + "."
    return NORMEN_FEHLT


def _konformitaetsaussage(doc: dict[str, Any]) -> str:
    """Anhang V Nr. 4 — die Aussage selbst, nicht ihre Eingabe."""
    satz = ("Das oben bezeichnete KI-System entspricht den Anforderungen der "
            f"{REGULATION}.")
    weiter = _s(doc.get("weiteres_unionsrecht"))
    if weiter:
        satz += (" Darüber hinaus erfüllt es die folgenden weiteren Rechtsakte "
                 f"der Union, die eine EU-Konformitätserklärung vorsehen: "
                 f"{weiter}.")
    return satz


def fehlende_pflichtfelder(doc: dict[str, Any], *,
                           nb_pflichtig: bool = False) -> list[dict[str, Any]]:
    """Welche Pflichtangaben aus Anhang V im Datensatz fehlen.

    Eine Angabe gilt als vorhanden, wenn **alle** ihre Felder gefüllt sind:
    „Name und Typ" ohne Typ identifiziert das System nicht.
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
                            "felder": leer, "rechtsbezug": a.rechtsbezug})
    return fehlend


# ── Daten ───────────────────────────────────────────────────────────────────

def doc_daten(db_path: Path | str = DB_PATH,
              projekt_name: str = "") -> dict[str, Any]:
    """Alle Angaben der Erklärung — zusammengeführt aus Record und Stammdaten.

    **Vorbelegung ist keine Erfindung** (die Linie aus ``cra.doc_export``):
    Anbietername, Systembezeichnung und die NB-Kennnummer stehen schon in den
    Projekt- bzw. Konformitäts-Stammdaten. Was nirgends steht, bleibt leer und
    erscheint als Lücke.
    """
    from ai_act import conformity as conf
    from ai_act.db import load_projekt

    db_path = Path(db_path)
    try:
        proj = load_projekt(db_path, projekt_name) or {}
    except Exception:  # noqa: BLE001 — ein unbekanntes Projekt ergibt einen Entwurf
        proj = {}
    try:
        rec = conf.get_or_empty(db_path, projekt_name) or {}
    except Exception:  # noqa: BLE001
        rec = {}

    roh = rec.get("doc") if isinstance(rec.get("doc"), dict) else {}
    verfahren = _s(rec.get("verfahren"))
    nb_pflichtig = verfahren in VERFAHREN_MIT_NB

    doc: dict[str, Any] = {f: _s(roh.get(f)) for f in EINGABEFELDER}
    doc["normen"] = _normen_liste(roh.get("normen"))
    for schalter in SCHALTER:
        doc[schalter] = _bool(roh.get(schalter))

    meta = proj.get("meta") if isinstance(proj.get("meta"), dict) else {}
    aiact_meta = meta.get("aiact") if isinstance(meta.get("aiact"), dict) else {}

    if not doc["system_name"]:
        doc["system_name"] = _s(proj.get("produkt")) or _s(proj.get("name")) \
            or _s(projekt_name)
    if not doc["anbieter"]:
        doc["anbieter"] = _s(proj.get("organisation"))
    if not doc["unterzeichner_fuer"]:
        doc["unterzeichner_fuer"] = doc["anbieter"]
    if not doc["nb_kennnummer"]:
        doc["nb_kennnummer"] = _s(rec.get("notified_body_kennnummer"))
    if not doc["nb_name"]:
        doc["nb_name"] = _s(rec.get("notified_body_name"))
    if not doc["nb_verfahren"] and verfahren:
        doc["nb_verfahren"] = _s(conf.VERFAHREN.get(verfahren, verfahren))
    # Die eindeutige Kennung: Produkt und Risikoeinstufung aus A1 bezeichnen
    # das System so, wie die Akte es führt. Erfunden wird nichts — ohne
    # Einstufung bleibt die Kennung leer und erscheint als Lücke.
    if not doc["system_kennung"] and _s(aiact_meta.get("risk_tier")):
        doc["system_kennung"] = (f"{doc['system_name']} "
                                 f"({_s(aiact_meta.get('risk_tier'))})")

    doc["verantwortungssatz"] = VERANTWORTUNGSSATZ
    doc["konformitaetsaussage"] = _konformitaetsaussage(doc)
    doc["datenschutzsatz"] = (DATENSCHUTZSATZ
                              if doc["personenbezogene_daten"] else "")
    doc["normen_text"] = ", ".join(doc["normen"])
    doc["normen_satz"] = normen_satz(doc)

    fehlend = fehlende_pflichtfelder(doc, nb_pflichtig=nb_pflichtig)
    ausgestellt = bool(rec.get("doc_ausgestellt")) and not fehlend
    return {
        "projekt_name": projekt_name,
        "projekt": proj,
        "record": rec,
        "doc": doc,
        "doc_version": int(rec.get("doc_version") or 0),
        "ausgestellt_am": _s(rec.get("doc_ausgestellt_am"))[:19].replace("T", " "),
        "doc_ausgestellt": bool(rec.get("doc_ausgestellt")),
        "nb_pflichtig": nb_pflichtig,
        "verfahren": verfahren,
        "doc_allowed": bool(rec.get("doc_allowed")),
        "fehlend": fehlend,
        "vollstaendig": not fehlend,
        "ist_entwurf": not ausgestellt,
    }


# ── Dokument ────────────────────────────────────────────────────────────────

_NUMMER_TITEL: dict[int, str] = {
    1: "Bezeichnung des KI-Systems",
    2: "Anbieter",
    3: "Erklärung zur Alleinverantwortung",
    4: "Konformitätsaussage",
    5: "Datenschutzrecht",
    6: "Angewandte Normen und Spezifikationen",
    7: "Konformitätsbewertungsverfahren und notifizierte Stelle",
    8: "Ort, Datum und Unterzeichner",
}


def _wert(werte: dict[str, Any], angabe: Angabe, *, pflicht: bool) -> str:
    """Anzeigewert — Lücken werden benannt, auch die halben.

    Steht der Systemname, fehlt aber der Typ, wird der fehlende Teil
    ausgewiesen. Würde nur der gefüllte Teil gedruckt, sähe die Zeile
    vollständig aus und wäre es nicht.
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


def build_docx(projekt: str, *, db_path: Path | str = DB_PATH,
               nur_ausgestellt: bool = False) -> bytes:
    """Die Erklärung als DOCX. A4 und Arial über den geteilten Helfer (#1617)."""
    from docx import Document

    from shared.reports.docx_pdf import apply_base_font, set_a4

    d = doc_daten(db_path, projekt)
    if nur_ausgestellt and d["ist_entwurf"]:
        raise PflichtfelderFehlen(d["fehlend"])

    doc = Document()
    set_a4(doc)
    apply_base_font(doc)
    werte = d["doc"]

    titel = "EU-Konformitätserklärung"
    if d["ist_entwurf"]:
        titel += f" ({ENTWURF_MARKER})"
    doc.add_heading(titel, level=0)
    doc.add_paragraph(RECHTSGRUNDLAGE).italic = True
    if d["ist_entwurf"]:
        doc.add_paragraph(
            f"{ENTWURF_MARKER}. Eine Erklärung, in der Pflichtangaben fehlen, "
            "sieht aus wie eine Erklärung und ist keine — deshalb trägt "
            "dieses Dokument den Entwurfsvermerk.").italic = True

    gesehen: set[int] = set()

    def _kopf(nr: int) -> None:
        if nr not in gesehen:
            doc.add_heading(f"{nr}. {_NUMMER_TITEL[nr]}", level=1)
            gesehen.add(nr)

    for a in ANHANG_V:
        if a.bedingt == "nb" and not d["nb_pflichtig"] \
                and not any(_s(werte.get(f)) for f in a.felder):
            continue
        if a.felder == ("verantwortungssatz",):
            _kopf(a.nr)
            doc.add_paragraph(VERANTWORTUNGSSATZ)
            continue
        if a.felder == ("konformitaetsaussage",):
            _kopf(a.nr)
            doc.add_paragraph(_s(werte.get("konformitaetsaussage")))
            continue
        if a.felder == ("datenschutzsatz",):
            # Nur drucken, wenn das System personenbezogene Daten verarbeitet.
            # Eine Erklärung über etwas, das nicht stattfindet, wäre eine
            # Aussage ohne Gegenstand.
            if not _s(werte.get("datenschutzsatz")):
                continue
            _kopf(a.nr)
            doc.add_paragraph(_s(werte.get("datenschutzsatz")))
            continue
        if a.felder == ("normen",):
            _kopf(a.nr)
            p = doc.add_paragraph()
            p.add_run(f"{a.bezeichnung}: ").bold = True
            p.add_run(_s(werte.get("normen_satz")) or normen_satz(werte))
            continue
        if set(a.felder) <= UNTERSCHRIFT_FELDER:
            continue
        if a.felder == ("bevollmaechtigter",) and not _s(werte.get("bevollmaechtigter")):
            # „Falls zutreffend": Ohne Bevollmächtigten entfällt die Zeile,
            # statt einen Gedankenstrich zu drucken (die Lehre aus #1884).
            continue
        pflicht = a.daten_pflicht and (not a.bedingt or d["nb_pflichtig"])
        _kopf(a.nr)
        p = doc.add_paragraph()
        p.add_run(f"{a.bezeichnung}: ").bold = True
        p.add_run(_wert(werte, a, pflicht=pflicht))

    # Zusatzangaben: „leer" und „bewusst keine" sind nicht dasselbe (#1885).
    zusatz = _s(werte.get("zusatzangaben"))
    if not zusatz and _bool(werte.get("zusatzangaben_keine")):
        zusatz = "Keine weiteren Angaben."
    if zusatz:
        _kopf(8)
        p = doc.add_paragraph()
        p.add_run("Zusatzangaben: ").bold = True
        p.add_run(zusatz)

    _kopf(8)
    ort = _s(werte.get("ort")) or "[fehlt — Anhang V Nr. 8]"
    datum = _s(werte.get("datum")) or "[fehlt — Anhang V Nr. 8]"
    doc.add_paragraph(f"{ort}, {datum}")
    doc.add_paragraph()
    doc.add_paragraph("_____________________________________")
    name = _s(werte.get("unterzeichner_name")) or "[fehlt — Anhang V Nr. 8]"
    funktion = _s(werte.get("unterzeichner_funktion")) or "[fehlt — Anhang V Nr. 8]"
    doc.add_paragraph(f"{name} — {funktion}")
    doc.add_paragraph(
        f"für {_s(werte.get('unterzeichner_fuer')) or '[fehlt — Anhang V Nr. 8]'}")

    # CE-Kennzeichnung (Art. 48). Gedruckt wird nur, was stattgefunden hat.
    ce = _s((d.get("record") or {}).get("ce_angebracht_am"))
    doc.add_heading("CE-Kennzeichnung (Art. 48)", level=1)
    doc.add_paragraph(
        f"CE-Kennzeichnung angebracht am {ce}." if ce else
        "Die CE-Kennzeichnung ist noch nicht als angebracht vermerkt.")

    puffer = BytesIO()
    doc.save(puffer)
    return puffer.getvalue()


def build_pdf(projekt: str, *, db_path: Path | str = DB_PATH,
              nur_ausgestellt: bool = False) -> bytes:
    """PDF über denselben DOCX-Weg (#1614) — kein zweiter Renderer."""
    from shared.reports.docx_pdf import docx_bytes_to_pdf

    return docx_bytes_to_pdf(build_docx(projekt, db_path=db_path,
                                        nur_ausgestellt=nur_ausgestellt))


def build(projekt: str, *, fmt: str = "docx", db_path: Path | str = DB_PATH,
          nur_ausgestellt: bool = False) -> bytes:
    if (fmt or "docx").lower() == "pdf":
        return build_pdf(projekt, db_path=db_path, nur_ausgestellt=nur_ausgestellt)
    return build_docx(projekt, db_path=db_path, nur_ausgestellt=nur_ausgestellt)


# ── Unveränderliche Ablage ──────────────────────────────────────────────────

def ensure_table(db_path: Path | str = DB_PATH) -> None:
    """Archiv-Tabelle (idempotent).

    Eigene Tabelle und nicht die des Zertifikats-Uploads: Jene hält die
    Bescheinigung der notifizierten Stelle — ein fremdes Dokument. Die
    Erklärung ist unsere, mit eigener Fassungsnummer.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _sdb.connect(str(db_path))
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS aiact_doc_final (
                   id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                   projekt_name    TEXT NOT NULL,
                   doc_version     INTEGER NOT NULL DEFAULT 0,
                   pdf_path        TEXT NOT NULL DEFAULT '',
                   sha256          TEXT NOT NULL DEFAULT '',
                   angaben_json    TEXT NOT NULL DEFAULT '{}',
                   ausgestellt_von TEXT NOT NULL DEFAULT '',
                   ausgestellt_am  TEXT DEFAULT (aics_now())
               )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_aiact_doc_final_proj "
                    "ON aiact_doc_final(projekt_name)")
        con.commit()
    finally:
        con.close()


def archiviere(db_path: Path | str, projekt_name: str, *, pdf_bytes: bytes,
               doc_version: int = 0, ausgestellt_von: str = "",
               angaben: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ausgestellte Fassung unveränderlich ablegen: PDF + SHA-256.

    Append-only: Jede Ausstellung ist eine eigene Zeile mit eigener Datei. Die
    Erklärung ist das Stück, auf das sich Marktaufsicht und Kunde berufen
    (Art. 47 Abs. 2: zehn Jahre bereitzuhalten); sie darf sich nach dem
    Ausstellen nicht ändern.
    """
    ensure_table(db_path)
    STORE.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    roh = f"{projekt_name}_v{int(doc_version or 0)}"
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in roh)
    pfad = STORE / f"{safe}_{sha[:12]}.pdf"
    pfad.write_bytes(pdf_bytes)
    con = _sdb.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO aiact_doc_final (projekt_name, doc_version, pdf_path, "
            "sha256, angaben_json, ausgestellt_von) VALUES (?,?,?,?,?,?)",
            (projekt_name, int(doc_version or 0), str(pfad), sha,
             json.dumps(angaben or {}, ensure_ascii=False),
             ausgestellt_von or ""))
        con.commit()
    finally:
        con.close()
    return {"projekt_name": projekt_name, "doc_version": int(doc_version or 0),
            "sha256": sha, "pdf_path": str(pfad),
            "ausgestellt_von": ausgestellt_von or ""}


def list_archiv(db_path: Path | str, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _sdb.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT id, doc_version, sha256, pdf_path, ausgestellt_von, "
            "ausgestellt_am FROM aiact_doc_final WHERE projekt_name=? "
            "ORDER BY ausgestellt_am DESC, id DESC", (projekt_name,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_archiv(db_path: Path | str, projekt_name: str,
               final_id: int) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _sdb.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT * FROM aiact_doc_final WHERE id=? AND projekt_name=?",
            (int(final_id), projekt_name)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def ausstellen(projekt: str, *, von: str = "", db_path: Path | str = DB_PATH,
               bestaetigt: tuple[str, ...] | list[str] = (),
               pdf_bytes: bytes | None = None) -> dict[str, Any]:
    """Ausgestellte Fassung erzeugen und unveränderlich ablegen.

    Bricht **vor** der PDF-Erzeugung ab, damit die Meldung die Lücken nennt
    und nicht der Konverter nach einer Minute eine unvollständige Erklärung
    ausliefert. Geprüft wird dreifach: Gate (Bewertungsweg abgeschlossen),
    Pflichtangaben, Widersprüche (#1885).
    """
    from ai_act import doc_pruefung as _pr

    d = doc_daten(db_path, projekt)
    if not d["doc_allowed"]:
        raise ValueError(
            "Die Erklärung ist erst ausstellbar, wenn die Konformitäts"
            "bewertung abgeschlossen ist (Art. 43).")
    if d["fehlend"]:
        raise PflichtfelderFehlen(d["fehlend"])
    befunde = _pr.befunde(db_path, projekt)
    if _pr.blockierend(befunde):
        raise _pr.ErklaerungUnstimmig(_pr.blockierend(befunde))
    offen = _pr.offene_bestaetigungen(befunde, bestaetigt)
    if offen:
        raise _pr.BestaetigungErforderlich(offen)
    pdf = pdf_bytes if pdf_bytes is not None else build_pdf(
        projekt, db_path=db_path, nur_ausgestellt=True)
    return archiviere(db_path, projekt, pdf_bytes=pdf,
                      doc_version=d["doc_version"], ausgestellt_von=von,
                      angaben=d["doc"])


__all__ = ["ANHANG_V", "EINGABEFELDER", "SCHALTER", "ABGELEITET",
           "UNTERSCHRIFT_FELDER", "VERFAHREN_MIT_NB", "RECHTSGRUNDLAGE",
           "NORMEN_FEHLT", "KEINE_HARMONISIERTEN_SATZ", "DATENSCHUTZSATZ",
           "PflichtfelderFehlen", "normen_satz", "fehlende_pflichtfelder",
           "fehlend_text", "doc_daten", "build", "build_docx", "build_pdf",
           "ensure_table", "archiviere", "list_archiv", "get_archiv",
           "ausstellen"]
