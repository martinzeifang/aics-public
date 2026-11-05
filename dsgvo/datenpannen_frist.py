"""DS-P (#1193) — Art.-33-Fristlogik + strukturiertes Aufsichts-Meldeformular.

ERWEITERT die bestehende Datenpannen-Logik (``dsgvo/db.py`` ``dsgvo_datenpannen``,
Art. 33/34) — KEINE Duplizierung des CRUD. Dieses Modul:

* berechnet die **72-h-Frist** (Art. 33(1)) je Datenpanne über die zentrale
  Fristen-Engine ``shared/deadlines.py`` (STAGE_SET ``"dsgvo_art33"``),
  status-aware (gemeldet/abgeschlossen ⇒ kein Alarm),
* reichert ``list_pannen``-Ergebnisse mit ``frist``-Feldern an,
* baut das strukturierte **Art.-33(3)-Behörden-Meldeformular** (a–d) als DOCX/PDF
  mit DSB-Kontakt-Vorbefüllung aus ``dsgvo_dsb``.
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

from dsgvo import deadlines as dl
from dsgvo import db as core_db
from dsgvo import dsb_db
from shared.reports import texte as _rt

DB_PATH = Path("data/db/dsgvo.sqlite")

# Status, in denen kein Frist-Alarm mehr ausgelöst wird.
TERMINAL_STATUS = ("gemeldet", "abgeschlossen")
STAGE_KEY = "dsgvo_art33"


def compute_frist(festgestellt_am: str, status: str,
                  *, now: datetime | None = None) -> dict[str, Any]:
    """Art.-33-72-h-Frist für eine Datenpanne (status-aware).

    Bei Abschluss-Status (gemeldet/abgeschlossen) wird der Alarm unterdrückt
    (overdue=False, ampel='grau'), die berechnete Frist bleibt aber sichtbar.
    """
    res = dl.evaluate(festgestellt_am, STAGE_KEY, now=now)
    if dl.is_terminal(status or "", TERMINAL_STATUS):
        res = {**res, "overdue": False, "ampel": "grau"}
    return res


def enrich_panne(panne: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Reichert einen Datenpannen-Datensatz um das ``frist``-Feld an."""
    d = dict(panne)
    d["frist"] = compute_frist(d.get("festgestellt_am", ""), d.get("status", ""), now=now)
    return d


def list_pannen_mit_frist(db_path: Path, projekt_name: str,
                          *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Wie ``core_db.list_pannen``, aber mit berechneten Art.-33-Frist-Feldern."""
    return [enrich_panne(p, now=now) for p in core_db.list_pannen(db_path, projekt_name)]


def get_panne(db_path: Path, projekt_name: str, panne_pk: int,
              *, now: datetime | None = None) -> dict[str, Any] | None:
    """Projekt-scoped Einzel-Lookup (IDOR-sicher, #1173-Muster)."""
    for p in core_db.list_pannen(db_path, projekt_name):
        if int(p.get("id") or 0) == int(panne_pk):
            return enrich_panne(p, now=now)
    return None


# ── Aggregation für Cockpit/Pflicht-Doku ────────────────────────────────────

def offene_fristen(db_path: Path, projekt_name: str,
                   *, now: datetime | None = None) -> dict[str, Any]:
    """Zählt offene Datenpannen + überfällige Art.-33-Fristen (status-aware)."""
    pannen = list_pannen_mit_frist(db_path, projekt_name, now=now)
    offene = [p for p in pannen if p.get("status") not in TERMINAL_STATUS]
    overdue = [p for p in offene if p.get("frist", {}).get("overdue")]
    return {
        "gesamt": len(pannen),
        "offen": len(offene),
        "overdue": len(overdue),
        "ok": len(overdue) == 0,
    }


# ── Art.-33(3)-Meldeformular ─────────────────────────────────────────────────

#: Die Texte des Meldeformulars je Sprache (#1954).
#:
#: Das Formular geht an die **Aufsichtsbehörde des Mandanten**, nicht an den
#: Bearbeiter — also entscheidet ``firmen.sprache`` über seine Sprache
#: (``shared/reports/texte``). Die deutschen Werte sind zeichengenau die aus
#: 8.3.4; die Fristenrechnung oben bleibt unberührt.
#:
#: **Die Artikelangaben sind nicht übersetzt, nur ihre Schreibweise.** Art. 33
#: und Art. 34 bezeichnen in beiden Fassungen dieselbe Stelle derselben
#: Verordnung; die Ziffern bleiben unangetastet (Lehre aus #1763/#1792).
#: Englisch heißt die Verordnung (EU) 2016/679 amtlich „GDPR", und die
#: Begriffe folgen ihrer englischen Fassung: *personal data breach*,
#: *supervisory authority*, *controller*, *data subject*,
#: *data protection officer*.
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "titel": "Meldung einer Verletzung des Schutzes personenbezogener Daten",
        "untertitel": "an die zuständige Aufsichtsbehörde — Art. 33 DSGVO",
        "l_verantwortlicher": "Verantwortlicher / Organisation: ",
        "l_vorfall_id": "Vorfall-ID: ",
        "l_festgestellt": "Festgestellt am: ",
        "l_meldefrist": "Meldefrist (72 h, Art. 33(1)): ",
        "ueberfaellig": ("⚠ Frist überschritten — Verzögerungsbegründung "
                         "erforderlich (Art. 33(1) Satz 2)."),
        "erstellt_am": "Erstellt am: {wert}",

        "h_a": "a) Art der Verletzung",
        "kategorie": "Kategorie: {wert}",
        "beschreibung": "Beschreibung: {wert}",
        "datenkategorien": "Kategorien betroffener Personen / Daten: {wert}",
        "betroffene_anzahl": "Ungefähre Zahl betroffener Personen: {wert}",
        "risiko": "Risikoeinschätzung: {wert}",

        "h_b": "b) Kontaktstelle (Datenschutzbeauftragte:r)",
        "name": "Name: {wert}",
        "email": "E-Mail: {wert}",
        "funktion": "Funktion: {wert}",

        "h_c": "c) Wahrscheinliche Folgen der Verletzung",
        "ursache": "Ursache: {wert}",
        "folgen_platzhalter": ("(Bitte wahrscheinliche Folgen für die "
                               "Betroffenen beschreiben.)"),

        "h_d": "d) Ergriffene / vorgeschlagene Maßnahmen",
        "lessons_learned": "Lessons Learned: {wert}",
        "meldung_betroffene": "Meldung an Betroffene erforderlich (Art. 34): {wert}",
        "ja": "ja",
        "nein": "nein",
        "leer": "—",

        # Bezeichnungen zu den Datenwerten `art` bzw. `risikoeinschaetzung`.
        # Die **Schlüssel** sind Datenwerte und bleiben unverändert (Regel 7) —
        # übersetzt wird nur, was gedruckt wird.
        "art_vertraulichkeit": "Verletzung der Vertraulichkeit",
        "art_integritaet": "Verletzung der Integrität",
        "art_verfuegbarkeit": "Verletzung der Verfügbarkeit",
        "risiko_gering": "gering",
        "risiko_mittel": "mittel",
        "risiko_hoch": "hoch",
    },
    "en": {
        "titel": "Notification of a personal data breach",
        "untertitel": ("to the competent supervisory authority — Art. 33 GDPR"),
        "l_verantwortlicher": "Controller / organisation: ",
        "l_vorfall_id": "Incident ID: ",
        # Art. 33(1) stellt auf das Bekanntwerden ab („after having become
        # aware of it"), nicht auf ein Eingangsdatum.
        "l_festgestellt": "Became aware on: ",
        "l_meldefrist": "Notification deadline (72 h, Art. 33(1)): ",
        "ueberfaellig": ("⚠ Deadline exceeded — the reasons for the delay must "
                         "be given (Art. 33(1), second sentence)."),
        "erstellt_am": "Created on: {wert}",

        "h_a": "a) Nature of the breach",
        "kategorie": "Category: {wert}",
        "beschreibung": "Description: {wert}",
        "datenkategorien": ("Categories of data subjects and of personal data "
                            "records concerned: {wert}"),
        "betroffene_anzahl": "Approximate number of data subjects concerned: {wert}",
        "risiko": "Risk assessment: {wert}",

        "h_b": "b) Contact point (data protection officer)",
        "name": "Name: {wert}",
        "email": "Email: {wert}",
        "funktion": "Role: {wert}",

        "h_c": "c) Likely consequences of the breach",
        "ursache": "Cause: {wert}",
        "folgen_platzhalter": ("(Please describe the likely consequences for "
                               "the data subjects.)"),

        "h_d": "d) Measures taken or proposed",
        "lessons_learned": "Lessons learned: {wert}",
        "meldung_betroffene": ("Communication to the data subjects required "
                               "(Art. 34): {wert}"),
        "ja": "yes",
        "nein": "no",
        "leer": "—",

        "art_vertraulichkeit": "Breach of confidentiality",
        "art_integritaet": "Breach of integrity",
        "art_verfuegbarkeit": "Breach of availability",
        "risiko_gering": "low",
        "risiko_mittel": "medium",
        "risiko_hoch": "high",
    },
}

_t = _rt.macher(TEXTE)

#: Datenwert → Katalogschlüssel. Ein unbekannter Wert wird **nicht** übersetzt,
#: sondern unverändert gedruckt — so war es vor #1954 (``.get(wert, wert)``),
#: und ein erfundenes Etikett wäre in einer Behördenmeldung schlimmer als der
#: Rohwert.
_ART_KEYS = {"vertraulichkeit": "art_vertraulichkeit",
             "integritaet": "art_integritaet",
             "verfuegbarkeit": "art_verfuegbarkeit"}
_RISIKO_KEYS = {"gering": "risiko_gering", "mittel": "risiko_mittel",
                "hoch": "risiko_hoch"}


def _wert_label(sp: str, keys: dict[str, str], wert: str) -> str:
    schluessel = keys.get(wert or "")
    return _t(sp, schluessel) if schluessel else (wert or "")


def build_meldeformular_docx(db_path: Path, projekt_name: str, panne_pk: int,
                             *, sprache: str | None = None) -> bytes:
    """Strukturiertes Art.-33(3)-Behörden-Meldeformular als DOCX.

    Pflicht-Meldeinhalt nach Art. 33(3) a–d:
    a) Art der Verletzung, Kategorien/Zahl Betroffener und Datensätze,
    b) Name + Kontaktdaten des DSB (aus ``dsgvo_dsb`` vorausgefüllt),
    c) wahrscheinliche Folgen,
    d) ergriffene/vorgeschlagene Maßnahmen + ggf. Verzögerungsbegründung.

    ``sprache`` übersteuert für diesen einen Lauf; ohne Angabe entscheidet der
    Mandant (#1954).
    """
    panne = get_panne(db_path, projekt_name, panne_pk)
    if not panne:
        raise ValueError("Datenpanne nicht gefunden")

    sp = _rt.aufloesen("dsgvo", projekt_name, sprache)
    dsb = dsb_db.get_dsb(db_path, projekt_name) or {}
    frist = panne.get("frist", {})
    leer = _t(sp, "leer")

    from docx import Document
    doc = Document()
    if sp != "de":
        # Dokumentsprache (`w:lang`) nur bei abweichender Sprache: Für Deutsch
        # war sie vor #1954 nicht gesetzt, und „auf Deutsch byte-identisch" ist
        # der Regressionsschutz dieses Vorgangs. Ohne die Angabe unterstreicht
        # Word in einem englischen Formular jedes Wort rot — in einem Dokument
        # für die Aufsichtsbehörde liest sich das als Schlamperei.
        from shared.reports.docx_pdf import set_doc_lang
        set_doc_lang(doc, sp)
    doc.add_heading(_t(sp, "titel"), level=0)
    doc.add_paragraph(_t(sp, "untertitel"))

    p = doc.add_paragraph()
    p.add_run(_t(sp, "l_verantwortlicher")).bold = True
    p.add_run(str(panne.get("_unternehmen") or projekt_name))
    p = doc.add_paragraph()
    p.add_run(_t(sp, "l_vorfall_id")).bold = True
    p.add_run(str(panne.get("panne_id") or ""))
    p = doc.add_paragraph()
    p.add_run(_t(sp, "l_festgestellt")).bold = True
    p.add_run(str(panne.get("festgestellt_am") or ""))
    p = doc.add_paragraph()
    p.add_run(_t(sp, "l_meldefrist")).bold = True
    p.add_run(str(frist.get("due_at") or leer))
    if frist.get("overdue"):
        doc.add_paragraph(_t(sp, "ueberfaellig"))
    doc.add_paragraph(_t(sp, "erstellt_am", wert=datetime.now().date().isoformat()))
    doc.add_paragraph("")

    # a) Art der Verletzung + Kategorien/Zahl
    doc.add_heading(_t(sp, "h_a"), level=1)
    doc.add_paragraph(_t(sp, "kategorie",
                         wert=_wert_label(sp, _ART_KEYS, panne.get("art", ""))))
    doc.add_paragraph(_t(sp, "beschreibung", wert=panne.get("beschreibung") or leer))
    doc.add_paragraph(_t(sp, "datenkategorien",
                         wert=panne.get("datenkategorien") or leer))
    doc.add_paragraph(_t(sp, "betroffene_anzahl",
                         wert=panne.get("betroffene_anzahl", 0)))
    doc.add_paragraph(_t(sp, "risiko",
                         wert=_wert_label(sp, _RISIKO_KEYS,
                                          panne.get("risikoeinschaetzung", ""))))

    # b) DSB-Kontakt (vorausgefüllt)
    doc.add_heading(_t(sp, "h_b"), level=1)
    doc.add_paragraph(_t(sp, "name", wert=dsb.get("name") or leer))
    doc.add_paragraph(_t(sp, "email", wert=dsb.get("kontakt_email") or leer))
    if dsb.get("typ"):
        doc.add_paragraph(_t(sp, "funktion", wert=dsb.get("typ")))

    # c) wahrscheinliche Folgen
    doc.add_heading(_t(sp, "h_c"), level=1)
    doc.add_paragraph(_t(sp, "ursache", wert=panne.get("ursache"))
                      if panne.get("ursache") else "")
    doc.add_paragraph(panne.get("notizen") or _t(sp, "folgen_platzhalter"))

    # d) Maßnahmen
    doc.add_heading(_t(sp, "h_d"), level=1)
    doc.add_paragraph(panne.get("sofortmassnahmen") or leer)
    if panne.get("lessons_learned"):
        doc.add_paragraph(_t(sp, "lessons_learned",
                             wert=panne.get("lessons_learned")))
    doc.add_paragraph(_t(sp, "meldung_betroffene",
                         wert=_t(sp, "ja" if panne.get("meldung_betroffene_pflicht")
                                 else "nein")))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_meldeformular_pdf(db_path: Path, projekt_name: str, panne_pk: int,
                            *, sprache: str | None = None) -> bytes:
    from shared.templates.pdf_converter import convert_docx_to_pdf
    return convert_docx_to_pdf(build_meldeformular_docx(
        db_path, projekt_name, panne_pk, sprache=sprache))
