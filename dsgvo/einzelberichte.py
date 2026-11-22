"""DS-B (#1135–#1137) — Einzelberichte je DSMS-Bereich als DOCX/PDF.

Generischer Area-Report-Renderer: liest die Bereichs-Tabelle und rendert einen
formatierten DOCX-Bericht (PDF über den zentralen Konverter). Deckt VVT, TOM,
Löschkonzept, Betroffenenrechte, Drittlandtransfer, Einwilligung, DSFA und DSB ab.
"""
from __future__ import annotations

import datetime
import io
from pathlib import Path
from typing import Any

from dsgvo.db import _connect
from shared.reports import texte as _rt

DB_PATH = Path("data/db/dsgvo.sqlite")

# area-key → {titel, rechtsgrundlage, table, columns:[(db_col,label)]}
#
# #1954: Dazu ``titel_en``, ``norm_en`` und ``labels_en`` (db_col → englisches
# Spaltenetikett). Die Übersetzung steht **bei ihrem Bereich** und nicht in
# einem zweiten Katalog: Wer eine Spalte ergänzt, sieht ihr Etikett im selben
# Atemzug (dieselbe Begründung wie der Dateikopf von ``shared/reports/texte``).
# Ein fehlender Eintrag fällt auf den deutschen zurück — eine Tabelle mit einer
# namenlosen Spalte wäre schlimmer als eine mit einer deutschen.
#
# ``norm_en`` übersetzt **nicht die Fundstelle**, nur ihre Schreibweise: Die
# Ziffern bleiben, und die Verordnung (EU) 2016/679 heißt englisch amtlich
# „GDPR". DIN 66398 bleibt DIN 66398 (Bezeichner, Regel 5).
AREA_REPORTS: dict[str, dict[str, Any]] = {
    "vvt": {
        "titel": "Verzeichnis von Verarbeitungstätigkeiten",
        "norm": "Art. 30 DSGVO", "norm_en": "Art. 30 GDPR", "table": "dsgvo_vvt_pflicht",
        "columns": [("vvt_id", "ID"), ("name", "Verarbeitung"), ("rolle", "Rolle"),
                    ("zweck", "Zweck"), ("rechtsgrundlage", "Rechtsgrundlage"),
                    ("datenkategorien", "Datenkategorien"), ("empfaenger", "Empfänger"),
                    ("loeschfrist", "Löschfrist")],
        # „Record of processing activities" ist die amtliche englische
        # Bezeichnung in Art. 30; die Kurzform RoPA bleibt der Oberfläche.
        "titel_en": "Record of processing activities",
        "norm_en": "Art. 30 GDPR",
        "labels_en": {"vvt_id": "ID", "name": "Processing activity", "rolle": "Role",
                      "zweck": "Purpose", "rechtsgrundlage": "Legal basis",
                      "datenkategorien": "Categories of data",
                      "empfaenger": "Recipients", "loeschfrist": "Erasure period"},
    },
    "tom": {
        "titel": "Technisch-organisatorische Maßnahmen", "norm": "Art. 32 DSGVO (SDM)", "norm_en": "Art. 32 GDPR (SDM)",
        "table": "dsgvo_tom_katalog",
        "columns": [("ziel", "Gewährleistungsziel"), ("titel", "Maßnahme"),
                    ("status", "Reifegrad (0–5)"), ("status_quelle", "Quelle (WiBA/manuell)"),
                    ("umsetzung", "Umsetzung"), ("verantwortlich", "Verantwortlich"),
                    ("wirksamkeit_ergebnis", "Wirksamkeit")],
        "titel_en": "Technical and organisational measures",
        "norm_en": "Art. 32 GDPR (SDM)",
        # „Warranty goal" ist der Begriff der englischen Fassung des
        # Standard-Datenschutzmodells. **Die Werte der Spalte bleiben deutsch**
        # (`dsgvo/tom_katalog.ZIELE` prüft sie als Datenwerte) — übersetzt ist
        # die Spaltenüberschrift, nicht ihr Inhalt.
        "labels_en": {"ziel": "Warranty goal", "titel": "Measure",
                      "status": "Maturity (0–5)",
                      "status_quelle": "Source (WiBA/manual)",
                      "umsetzung": "Implementation",
                      "verantwortlich": "Responsible",
                      "wirksamkeit_ergebnis": "Effectiveness"},
    },
    "loeschkonzept": {
        "titel": "Löschkonzept", "norm": "Art. 17 DSGVO / DIN 66398", "norm_en": "Art. 17 GDPR / DIN 66398",
        "table": "dsgvo_loeschkonzept",
        "columns": [("regel_id", "Regel"), ("datenkategorie", "Datenkategorie"),
                    ("aufbewahrungsfrist", "Frist"), ("rechtsgrundlage_frist", "Grundlage"),
                    ("loesch_trigger", "Trigger"), ("status", "Status")],
        "titel_en": "Erasure concept",
        "norm_en": "Art. 17 GDPR / DIN 66398",
        "labels_en": {"regel_id": "Rule", "datenkategorie": "Category of data",
                      "aufbewahrungsfrist": "Retention period",
                      "rechtsgrundlage_frist": "Basis",
                      "loesch_trigger": "Trigger", "status": "Status"},
    },
    "betroffenenrechte": {
        "titel": "Betroffenenrechte", "norm": "Art. 15–22 DSGVO", "norm_en": "Art. 15–22 GDPR",
        "table": "dsgvo_betroffenenrechte",
        "columns": [("antrag_id", "Antrag"), ("typ", "Typ"), ("eingang_datum", "Eingang"),
                    ("frist_datum", "Frist"), ("status", "Status"), ("bearbeiter", "Bearbeiter"),
                    # #1218 (Art. 19): Empfänger-Benachrichtigung als Nachweis.
                    ("empfaenger_status", "Art. 19"), ("empfaenger_datum", "Mitteilung am")],
        "titel_en": "Data subject rights",
        "norm_en": "Art. 15–22 GDPR",
        "labels_en": {"antrag_id": "Request", "typ": "Type",
                      "eingang_datum": "Received", "frist_datum": "Deadline",
                      "status": "Status", "bearbeiter": "Handler",
                      "empfaenger_status": "Art. 19",
                      "empfaenger_datum": "Notified on"},
    },
    "transfer": {
        "titel": "Drittlandtransfers & TIA", "norm": "Art. 44–49 DSGVO", "norm_en": "Art. 44–49 GDPR",
        "table": "dsgvo_transfer",
        "columns": [("transfer_id", "ID"), ("empfaenger", "Empfänger"), ("drittland", "Drittland"),
                    ("grundlage", "Grundlage"), ("tia_status", "TIA-Status")],
        "titel_en": "Third-country transfers & TIA",
        "norm_en": "Art. 44–49 GDPR",
        "labels_en": {"transfer_id": "ID", "empfaenger": "Recipient",
                      "drittland": "Third country", "grundlage": "Basis",
                      "tia_status": "TIA status"},
    },
    "einwilligung": {
        "titel": "Einwilligungen", "norm": "Art. 7 DSGVO", "norm_en": "Art. 7 GDPR",
        "table": "dsgvo_einwilligung",
        "columns": [("einwilligung_id", "ID"), ("zweck", "Zweck"), ("kanal", "Kanal"),
                    ("zeitpunkt", "Zeitpunkt"), ("status", "Status")],
        "titel_en": "Consents",
        "norm_en": "Art. 7 GDPR",
        "labels_en": {"einwilligung_id": "ID", "zweck": "Purpose",
                      "kanal": "Channel", "zeitpunkt": "Time", "status": "Status"},
    },
    "dsfa": {
        "titel": "Datenschutz-Folgenabschätzungen", "norm": "Art. 35 DSGVO", "norm_en": "Art. 35 GDPR",
        "table": "dsgvo_dpia",
        "columns": [("dpia_id", "ID"), ("titel", "Titel"), ("restrisiko", "Restrisiko"),
                    ("status", "Status"), ("naechstes_review", "Review")],
        "titel_en": "Data protection impact assessments",
        "norm_en": "Art. 35 GDPR",
        "labels_en": {"dpia_id": "ID", "titel": "Title",
                      "restrisiko": "Residual risk", "status": "Status",
                      "naechstes_review": "Review"},
    },
    "dsb": {
        "titel": "Datenschutzbeauftragte:r", "norm": "Art. 37–39 DSGVO", "norm_en": "Art. 37–39 GDPR",
        "table": "dsgvo_dsb",
        "columns": [("typ", "Typ"), ("name", "Name"), ("organisation", "Organisation"),
                    ("email", "E-Mail"), ("telefon", "Telefon"), ("aufsichtsbehoerde", "Aufsichtsbehörde")],
        "titel_en": "Data protection officer",
        "norm_en": "Art. 37–39 GDPR",
        "labels_en": {"typ": "Type", "name": "Name", "organisation": "Organisation",
                      "email": "Email", "telefon": "Phone",
                      "aufsichtsbehoerde": "Supervisory authority"},
    },
}

#: Die Rahmentexte des Bereichsberichts je Sprache (#1954).
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "rechtsgrundlage": "Rechtsgrundlage: {wert}",
        "organisation": "Organisation: {wert}",
        "projekt": "Projekt: {wert}",
        "erstellt_am": "Erstellt am: {wert}",
        "eintraege": "Einträge: {wert}",
        "leer": "— Keine Einträge erfasst —",
    },
    "en": {
        "rechtsgrundlage": "Legal basis: {wert}",
        "organisation": "Organisation: {wert}",
        "projekt": "Project: {wert}",
        "erstellt_am": "Created on: {wert}",
        "eintraege": "Entries: {wert}",
        "leer": "— No entries recorded —",
    },
}

_t = _rt.macher(TEXTE)


def _titel(cfg: dict[str, Any], sprache: str) -> str:
    """Bereichstitel in der gewünschten Sprache; ohne Übersetzung deutsch."""
    return (cfg.get("titel_en") or cfg["titel"]) if sprache != "de" else cfg["titel"]


def _norm(cfg: dict[str, Any], sprache: str) -> str:
    return (cfg.get("norm_en") or cfg.get("norm", "")) if sprache != "de" \
        else cfg.get("norm", "")


def _label(cfg: dict[str, Any], db_col: str, sprache: str) -> str:
    """Spaltenetikett in der gewünschten Sprache; ohne Übersetzung deutsch."""
    deutsch = next((lbl for c, lbl in cfg["columns"] if c == db_col), db_col)
    if sprache == "de":
        return deutsch
    return (cfg.get("labels_en") or {}).get(db_col) or deutsch


def available_reports(sprache: str | None = None) -> list[dict[str, str]]:
    """Der Katalog für die **Auswahlliste** der Oberfläche.

    Diese Liste ist Bedienoberfläche und folgt deshalb der **Anzeigesprache
    des Bearbeiters**, nicht der des Mandanten — anders als der Titel *im
    Dokument*, den :func:`build_docx` auflöst. Dieselbe Trennung wie
    ``shared.reports.core.ReportSpec.as_dict`` (#1954): Ein deutschsprachiger
    Berater erzeugt einen englischen Bericht für seinen Mandanten.
    """
    from shared import sprache as _sp

    sp = _sp.oder_standard(sprache) if sprache else _sp.anzeige_sprache()
    return [{"key": k, "titel": _titel(v, sp), "norm": _norm(v, sp)}
            for k, v in AREA_REPORTS.items()]


def _cols(con: Any, table: str) -> set[str]:
    try:
        return {r[0] for r in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ?", (table,))}
    except Exception:
        return set()


def _rows(con: Any, table: str, projekt_name: str,
          columns) -> tuple[list[list[str]], list[str]]:
    """Zeilen + die **tatsächlich vorhandenen** DB-Spalten (nicht die Etiketten).

    #1954: Vorher kamen hier die deutschen Etiketten zurück. Zurückgegeben wird
    jetzt die Spaltenkennung, damit der Renderer das Etikett in der Sprache des
    Mandanten auflösen kann — die Auswahl der Spalten bleibt unverändert.
    """
    have = _cols(con, table)
    if not have or "projekt_name" not in have:
        return [], []
    sel = [c for c, _ in columns if c in have]
    rows = con.execute(
        f"SELECT {','.join(sel)} FROM {table} WHERE projekt_name=?", (projekt_name,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        out.append(["" if d.get(c) is None else str(d.get(c)) for c, _ in columns if c in have])
    return out, sel


def build_docx(db_path: Path, projekt_name: str, area: str,
               *, sprache: str | None = None) -> bytes:
    cfg = AREA_REPORTS.get(area)
    if not cfg:
        raise ValueError(f"Unbekannter Bericht: {area}")
    sp = _rt.aufloesen("dsgvo", projekt_name, sprache)
    from docx import Document
    con = _connect(Path(db_path))
    try:
        rows, spalten = _rows(con, cfg["table"], projekt_name, cfg["columns"])
        headers = [_label(cfg, c, sp) for c in spalten]
        # Projekt-Stammdaten
        unternehmen = projekt_name
        try:
            pr = con.execute("SELECT unternehmen FROM dsgvo_projekte WHERE name=?",
                             (projekt_name,)).fetchone()
            if pr and dict(pr).get("unternehmen"):
                unternehmen = dict(pr)["unternehmen"]
        except Exception:
            pass
    finally:
        con.close()

    doc = Document()
    if sp != "de":
        # Dokumentsprache (`w:lang`) nur bei abweichender Sprache: Für Deutsch
        # war sie vor #1954 nicht gesetzt, und „auf Deutsch byte-identisch" ist
        # der Regressionsschutz dieses Vorgangs.
        from shared.reports.docx_pdf import set_doc_lang
        set_doc_lang(doc, sp)
    doc.add_heading(_titel(cfg, sp), level=0)
    doc.add_paragraph(_t(sp, "rechtsgrundlage", wert=_norm(cfg, sp)))
    doc.add_paragraph(_t(sp, "organisation", wert=unternehmen))
    doc.add_paragraph(_t(sp, "projekt", wert=projekt_name))
    doc.add_paragraph(_t(sp, "erstellt_am", wert=datetime.date.today().isoformat()))
    doc.add_paragraph(_t(sp, "eintraege", wert=len(rows)))
    doc.add_paragraph("")
    if not rows:
        doc.add_paragraph(_t(sp, "leer"))
    else:
        t = doc.add_table(rows=1, cols=len(headers))
        try:
            t.style = "Light Grid Accent 1"
        except Exception:  # noqa: BLE001
            pass
        for i, h in enumerate(headers):
            t.rows[0].cells[i].text = str(h)
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = v
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_pdf(db_path: Path, projekt_name: str, area: str,
              *, sprache: str | None = None) -> bytes:
    from shared.templates.pdf_converter import convert_docx_to_pdf
    return convert_docx_to_pdf(build_docx(db_path, projekt_name, area,
                                          sprache=sprache))
