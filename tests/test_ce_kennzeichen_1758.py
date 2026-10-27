"""CE-Kennzeichnung: eine Quelle, und gesperrt gegen unzulässige Verwendung.

Die Kennzeichnung ist kein Logo, sondern ein Rechtsakt: Sie erklärt, dass die
Konformitätsbewertung durchlaufen wurde und eine EU-Konformitätserklärung
vorliegt (Art. 29/30 i.V.m. Art. 28). Auf ein Dokument gedruckt, ohne dass
beides zutrifft, ist das unzulässige Verwendung — kein Darstellungsfehler.

Die Grafik selbst hatte in ihrer ersten Fassung (#1671) zwei Fehler, die erst
beim Rendern sichtbar wurden: Der Mittelbalken des E stand frei in der Luft
(damit war es kein E), und als Teil desselben Pfades hob ihn die Füllregel im
Überlappungsbereich auf.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _pfade(svg: str) -> list[str]:
    """Geometrie eines SVG: Pfaddaten und Rechtecke, ohne Kommentare."""
    ohne = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    out = re.findall(r'\sd="([^"]+)"', ohne)
    out += re.findall(r"<rect[^>]*x=\"(\d+)\"[^>]*y=\"(\d+)\"[^>]*"
                      r"width=\"(\d+)\"[^>]*height=\"(\d+)\"", ohne)
    return [str(x) for x in out]


def test_grafik_und_oberflaeche_sind_dieselbe():
    """Zwei Kopien einer Zeichnung laufen auseinander — und die eine, die
    niemand ansieht, ist dann die falsche."""
    asset = (REPO / "cra/assets/ce_kennzeichen.svg").read_text()
    panel = (REPO / "frontend/src/views/cra/KonformitaetPanel.vue").read_text()
    m = re.search(r"const CE_SVG = `(.*?)`", panel, re.S)
    assert m, "CE_SVG im Panel nicht gefunden"
    assert _pfade(asset) == _pfade(m.group(1)), (
        "Die Grafik im Panel weicht von cra/assets/ce_kennzeichen.svg ab")


def test_mittelbalken_ist_ein_eigenes_element():
    """Der Fehler aus #1671: Im selben Pfad hebt die Füllregel den Balken im
    Überlappungsbereich auf — sichtbar als weiße Keile am Ansatz."""
    svg = (REPO / "cra/assets/ce_kennzeichen.svg").read_text()
    assert "<rect x=" in svg, "Mittelbalken fehlt oder steckt im Pfad"
    pfade = re.findall(r'\sd="([^"]+)"', re.sub(r"<!--.*?-->", "", svg, flags=re.S))
    assert len(pfade) == 2, f"erwartet zwei Buchstabenbögen, gefunden {len(pfade)}"
    assert not any(" H" in p and " V" in p for p in pfade), (
        "im Bogen-Pfad steckt noch ein Rechteck")


def test_mittelbalken_beruehrt_den_bogen():
    """Ein Balken, der den Bogen nicht berührt, ergibt kein E.

    Der Innenkreis des zweiten Buchstabens hat den Mittelpunkt x=172 und den
    Radius 38, reicht also bis x=134. Der Balken muss dort beginnen oder davor.
    """
    svg = (REPO / "cra/assets/ce_kennzeichen.svg").read_text()
    m = re.search(r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg)
    assert m, "Balken-Rechteck nicht gefunden"
    x, y, breite, hoehe = (int(g) for g in m.groups())
    assert x <= 134, f"Balken beginnt bei {x}, berührt den Bogen (bis 134) nicht"
    assert hoehe == 18, f"Balkenstärke {hoehe} weicht von der Strichstärke 18 ab"
    # Senkrecht mittig: Buchstabenhöhe 8..120, Mitte 64.
    assert abs((y + hoehe / 2) - 64) < 1, "Balken sitzt nicht auf der Mittellinie"


def test_png_fuer_word_vorhanden():
    """`python-docx` kennt kein SVG — ohne PNG bliebe das Zeichen im Dokument
    unsichtbar, und zwar ohne Fehlermeldung."""
    from cra import ce_mark

    assert ce_mark.PNG.exists(), ce_mark.PNG
    assert ce_mark.PNG.stat().st_size > 2000


# ── Die Sperre ──────────────────────────────────────────────────────────────
def test_ohne_ausgestellte_erklaerung_kein_zeichen():
    from cra import ce_mark

    ja, grund = ce_mark.darf_zeichen({"ce_angebracht_am": "2026-10-22"}, False)
    assert ja is False
    assert "Konformitätserklärung" in grund


def test_ohne_angebrachte_kennzeichnung_kein_zeichen():
    from cra import ce_mark

    ja, grund = ce_mark.darf_zeichen({}, True)
    assert ja is False
    assert "nicht angebracht" in grund


def test_mit_beidem_wird_gedruckt():
    from cra import ce_mark

    ja, grund = ce_mark.darf_zeichen({"ce_angebracht_am": "2026-10-22"}, True)
    assert ja is True and grund == ""


def test_fundstelle_nennt_datum_und_ort():
    from cra import ce_mark

    text = ce_mark.fundstelle({"ce_angebracht_am": "2026-10-22T10:00:00",
                               "ce_ort": "Konformitätserklärung v3",
                               "ce_nachweis": "Screenshot im Anhang"})
    assert "2026-10-22" in text and "Konformitätserklärung v3" in text
    assert "Screenshot" in text


def test_grund_steht_im_dokument_statt_leerer_stelle():
    """Ein Dokument, das die Kennzeichnung stillschweigend weglässt, lässt den
    Leser im Unklaren, ob sie fehlt oder nur nicht gedruckt wurde."""
    from docx import Document

    from cra import ce_mark

    d = Document()
    gedruckt = ce_mark.einfuegen(d, {}, False)
    assert gedruckt is False
    text = "\n".join(p.text for p in d.paragraphs)
    assert "nicht ausweisbar" in text or "nicht angebracht" in text


def test_mindesthoehe_wird_nicht_unterschritten():
    """Anhang II: mindestens 5 mm."""
    from cra import ce_mark

    assert ce_mark.MIN_HOEHE_MM == 5.0
    assert ce_mark.HOEHE_MM >= ce_mark.MIN_HOEHE_MM
