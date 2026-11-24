#!/usr/bin/env python3
"""Erzeugt die Haus-Vorlage für Modul-Dokumente (#1997).

    python3 tools/vorlagen/dokument_vorlage.py [--out DATEI] [--titel TEXT]

**Warum ein Generator und keine eingecheckte Datei.** Eine DOCX im Baum ist ein
Binärklotz: Man sieht in keinem Diff, was sich geändert hat, und man kann nicht
begründen, warum eine Zeile so aussieht. Hier steht beides lesbar, und die Datei
lässt sich jederzeit neu erzeugen. Dasselbe Vorgehen wie bei den
Berichtsvorlagen (``~/Dokumente/SITS``).

**Warum sie nicht beim Start angelegt wird.** Eine Vorlage, die von selbst
entsteht und als Standard gilt, ist eine stehende Entscheidung ohne Entscheider
— dieselbe Überlegung wie bei den Standardgruppen in #1780: vorschlagen, nicht
anlegen. Hochgeladen wird sie über *Administration → Word-Vorlagen*, wie jede
andere.

**Was die Vorlage bewusst NICHT tut:** kein Logo, keine Hausfarbe, keine
Schriftart aus einer Markenrichtlinie. Sie ist der neutrale Rahmen, den ein Haus
anschließend in Word nach seinem Briefkopf umbaut — genau dafür ist der
Vorlagen-Weg da. Was sie dagegen fest mitbringt, ist alles, was ein
herausgegebenes Dokument **belegbar** macht: wer es ausstellt, zu welchem
Projekt es gehört, auf welcher Rechtsgrundlage, in welcher Fassung, mit welcher
Prüfsumme.
"""
from __future__ import annotations

import argparse
from pathlib import Path

#: Die Variable, ohne die eine Dokument-Vorlage abgewiesen wird: der Ort der
#: Prosa. Steht hier als Konstante, damit der Generator und die Prüfung
#: (``shared.documents.vorlage.pruefe_datei``) dasselbe meinen.
INHALT = "{{ inhalt }}"


def _rand(absatz) -> None:
    """Dünne Linie unter einem Absatz — der Trenner unter dem Kopf."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    pPr = absatz._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    unten = OxmlElement("w:bottom")
    unten.set(qn("w:val"), "single")
    unten.set(qn("w:sz"), "6")
    unten.set(qn("w:color"), "999999")
    borders.append(unten)
    pPr.append(borders)


def _feld(absatz, anweisung: str) -> None:
    """Ein Word-Feld (``PAGE``, ``NUMPAGES``) in einen Absatz setzen.

    Als Feld und nicht als Text: Eine ausgedruckte „Seite 1 von 1" wäre bei
    jedem mehrseitigen Dokument falsch. Die feldbewusste Ersetzung des
    Vorlagen-Renderers lässt solche Absätze stehen (#1007).
    """
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    run = absatz.add_run()
    anfang = OxmlElement("w:fldChar")
    anfang.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {anweisung} "
    ende = OxmlElement("w:fldChar")
    ende.set(qn("w:fldCharType"), "end")
    for el in (anfang, instr, ende):
        run._r.append(el)


def baue(ziel: Path, *, titel: str = "Dokumentvorlage") -> Path:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    d = Document()

    # A4 und Arial — dieselbe Grundeinstellung wie bei den Berichten (#1617),
    # damit ein Dokument neben einem Bericht desselben Hauses nicht fremd wirkt.
    for abschnitt in d.sections:
        abschnitt.page_width = Pt(595.3)
        abschnitt.page_height = Pt(841.9)
    normal = d.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(11)

    # ── Kopf: wer stellt das Dokument aus ───────────────────────────────────
    # Nach #1778 ist das der **Hersteller**, nicht der Dienstleister. Die
    # Angaben kommen daher aus dem Mandanten (#1892) und werden nicht getippt.
    kopf = d.sections[0].header.paragraphs[0]
    kopf.text = "{{ firma.unternehmen }}{% if firma.rechtsform %} {{ firma.rechtsform }}{% endif %}"
    kopf.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    kopf.runs[0].font.size = Pt(9)

    # ── Fuß: Projekt, Fassung, Seitenzahl ───────────────────────────────────
    fuss = d.sections[0].footer.paragraphs[0]
    fuss.text = ("{{ projekt.modul_label }} · {{ projekt.name }} · "
                 "Fassung {{ dokument.version }} · ")
    _feld(fuss, "PAGE")
    fuss.add_run(" / ")
    _feld(fuss, "NUMPAGES")
    fuss.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in fuss.runs:
        r.font.size = Pt(8)

    # ── Vertraulichkeit, falls gekennzeichnet ───────────────────────────────
    # Nur dann: Ein Dokument, auf dem immer „Vertraulich" steht, sagt nichts.
    vt = d.add_paragraph(
        "{% if dokument.vertraulich %}VERTRAULICH{% endif %}")
    vt.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    vt.runs[0].bold = True
    vt.runs[0].font.size = Pt(9)

    # ── Titel und Einordnung ────────────────────────────────────────────────
    d.add_heading("{{ dokument.titel }}", level=0)

    einordnung = d.add_paragraph(
        "{% if dokument.typ_titel %}{{ dokument.typ_titel }}{% endif %}"
        "{% if dokument.rechtsgrundlage %} — {{ dokument.rechtsgrundlage }}"
        "{% endif %}")
    einordnung.runs[0].italic = True
    _rand(einordnung)

    # ── Herausgeber ─────────────────────────────────────────────────────────
    d.add_heading("Herausgeber", level=2)
    # `anschrift_text` formatiert die Anschrift an einer Stelle (#1892); leere
    # Teile entfallen dort, es entsteht kein Platzhalter.
    d.add_paragraph("{{ firma.anschrift_text }}")
    d.add_paragraph(
        "{% if firma.vertreter_name %}Vertreten durch: {{ firma.vertreter_name }}"
        "{% if firma.vertreter_funktion %}, {{ firma.vertreter_funktion }}"
        "{% endif %}{% endif %}")

    # ── Angaben zum Dokument ────────────────────────────────────────────────
    d.add_heading("Angaben zum Dokument", level=2)
    zeilen = [
        ("Projekt", "{{ projekt.name }}"),
        ("Rechtsgrundlage", "{{ dokument.rechtsgrundlage }}"),
        ("Fassung", "{{ dokument.version }}"),
        ("Stand", "{{ dokument.stand }}"),
        ("Status", "{{ dokument.status_label }}"),
        ("Bearbeitet von", "{{ dokument.geaendert_von }}"),
        # Nur bei Freigabe gefüllt: Der Kontext liefert die Prüfsumme nur für
        # ein freigegebenes Dokument — an einem Entwurf wäre sie eine Zusage,
        # die nicht gilt.
        ("Prüfsumme (SHA-256)",
         "{% if dokument.sha256 %}{{ dokument.sha256 }}{% else %}—{% endif %}"),
    ]
    tab = d.add_table(rows=0, cols=2)
    try:
        tab.style = "Table Grid"
    except KeyError:
        pass
    for bez, wert in zeilen:
        zellen = tab.add_row().cells
        zellen[0].text = bez
        zellen[1].text = wert
        for p in zellen[0].paragraphs:
            for r in p.runs:
                r.bold = True

    d.add_paragraph("")

    # ── Der Inhalt ──────────────────────────────────────────────────────────
    # Dieser Absatz ist die Stelle, an der die geschriebene Prosa hineinläuft.
    # Sie trägt dabei die Formatvorlagen DIESES Dokuments.
    d.add_paragraph(INHALT)

    ziel.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(ziel))
    return ziel


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="out/vorlagen/dokument_haus_vorlage.docx")
    ap.add_argument("--titel", default="Dokumentvorlage")
    args = ap.parse_args()
    pfad = baue(Path(args.out), titel=args.titel)
    print(f"geschrieben: {pfad} ({pfad.stat().st_size} Bytes)")
    # Gegenprobe: Taugt die eigene Datei als Dokument-Vorlage?
    try:
        from shared.documents.vorlage import pruefe_datei
        pruefe_datei(pfad)
        print("Prüfung: enthält {{ inhalt }} — als Dokument-Vorlage geeignet")
    except Exception as exc:  # noqa: BLE001
        print(f"Prüfung FEHLGESCHLAGEN: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
