#!/usr/bin/env python3
"""Handbuch-PDF aus dem BookStack-Wiki bauen.

Holt alle Bücher als HTML (BookStack bettet die Screenshots als data:-URI ein),
setzt sie zu einem Dokument mit Deckblatt, Inhaltsverzeichnis und Seitenzahlen
zusammen und rendert es mit WeasyPrint.

Die Reihenfolge folgt der Nummerierung der Buchtitel („0 · Installation“ …),
nicht der Datenbank-ID: Die Bücher sind zu verschiedenen Zeiten entstanden.
"""
from __future__ import annotations

import html as h
import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = "http://aics.example.com:6875"
TOKEN = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
ZIEL = Path(sys.argv[2])
VERSION = sys.argv[3]
DATUM = sys.argv[4]

#: Das Logo wird **eingebettet**, nicht verlinkt. WeasyPrint löst relative
#: Pfade gegen `base_url` auf — und das ist hier die BookStack-Instanz, nicht
#: das Repository. Ein `<img src="logo.png">` bliebe leer, und zwar lautlos.
def _logo_uri() -> str:
    import base64
    for kandidat in ("logo_transparent.png", "logo_icon_256.png", "logo_icon.png"):
        pfad = Path(__file__).resolve().parents[2] / kandidat
        if pfad.exists():
            roh = base64.b64encode(pfad.read_bytes()).decode("ascii")
            return f"data:image/png;base64,{roh}"
    return ""


LOGO = _logo_uri()


def hol(pfad: str) -> bytes:
    anfrage = urllib.request.Request(
        BASE + pfad,
        headers={"Authorization": "Token " + TOKEN, "Accept": "*/*"})
    with urllib.request.urlopen(anfrage, timeout=180) as r:  # nosec B310 — feste Basis
        return r.read()


buecher = json.loads(hol("/api/books?count=100"))["data"]


def rang(name: str) -> tuple[int, str]:
    m = re.match(r"\s*(\d+)", name)
    return (int(m.group(1)) if m else 999, name)


buecher.sort(key=lambda b: rang(b["name"]))

teile: list[str] = []
toc: list[tuple[str, str]] = []

for i, b in enumerate(buecher, 1):
    print(f"[{i}/{len(buecher)}] {b['name']}", flush=True)
    roh = hol(f"/api/books/{b['id']}/export/html").decode("utf-8", "replace")
    # Nur den Inhalt übernehmen: Das Export-HTML bringt eigenes <head> mit
    # Stilen, die sich im Sammeldokument gegenseitig überschreiben würden.
    m = re.search(r"<body[^>]*>(.*)</body>", roh, re.S)
    inhalt = m.group(1) if m else roh
    # Überschriften eine Stufe tiefer, damit der Buchtitel die H1 bleibt.
    for stufe in (5, 4, 3, 2, 1):
        inhalt = re.sub(rf"<(/?)h{stufe}\b", rf"<\1h{stufe + 1}", inhalt)
    anker = f"buch-{b['id']}"
    toc.append((anker, b["name"]))
    teile.append(
        f'<section class="buch" id="{anker}">'
        f'<h1>{h.escape(b["name"])}</h1>'
        f'<p class="buch-beschreibung">{h.escape(b.get("description") or "")}</p>'
        f'{inhalt}</section>')

toc_html = "\n".join(
    f'<li><a href="#{a}">{h.escape(n)}</a></li>' for a, n in toc)

dokument = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<title>AI Compliance Suite — Handbuch</title>
<style>
  @page {{
    size: A4; margin: 26mm 18mm 22mm 18mm;
    /* Laufende Kapitelzeile: `string-set: kapitel` an h1 füllt sie (siehe
       unten). Eine feste Zeichenkette sagt auf Seite 90 nichts darüber, wo
       man gerade ist. */
    @top-left {{ content: string(kapitel); font: 8pt Arial; color: #607d8b; }}
    @top-right {{ content: "AI Compliance Suite · Handbuch {VERSION}";
                  font: 8pt Arial; color: #90a4ae; }}
    @bottom-left {{ content: "© Cyberwoks"; font: 8pt Arial; color: #b0bec5; }}
    @bottom-right {{ content: "Seite " counter(page) " von " counter(pages);
                     font: 9pt Arial; color: #607d8b; }}
  }}
  /* Deckblatt ohne Rahmen — und ohne Rand, damit das Kopfband bis an die
     Kante läuft. */
  @page :first {{
    margin: 0;
    @top-left {{ content: none; }} @top-right {{ content: none; }}
    @bottom-left {{ content: none; }} @bottom-right {{ content: none; }}
  }}
  body {{ font: 10.5pt/1.45 Arial, sans-serif; color: #263238; margin: 0; }}
  h1 {{ font-size: 20pt; color: #0d47a1; border-bottom: 2px solid #1565c0;
        padding-bottom: 4pt; string-set: kapitel content(); }}
  /* Buchanfang: Titel auf blauem Grund, wie die Modulköpfe der Anwendung. */
  section.buch > h1 {{
    background: #1565c0; color: #fff; border: 0; border-radius: 4pt;
    padding: 7pt 10pt; margin-bottom: 4pt; }}
  h2 {{ font-size: 15pt; color: #1565c0; margin-top: 16pt; }}
  h3 {{ font-size: 12.5pt; color: #37474f; margin-top: 12pt; }}
  h4, h5, h6 {{ font-size: 11pt; color: #455a64; }}
  h1, h2, h3, h4 {{ page-break-after: avoid; }}
  section.buch {{ page-break-before: always; }}
  .buch-beschreibung {{ color: #546e7a; font-style: italic; margin: 0 0 14pt; }}
  img {{ max-width: 100%; height: auto; border: 1px solid #cfd8e3; border-radius: 3px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 9pt;
           page-break-inside: avoid; margin: 8pt 0; }}
  th, td {{ border: 1px solid #cfd8e3; padding: 3pt 5pt; text-align: left;
            vertical-align: top; }}
  th {{ background: #eceff1; }}
  code, pre {{ font-family: "DejaVu Sans Mono", monospace; font-size: 9pt; }}
  pre {{ background: #f5f7f9; border-left: 3px solid #90a4ae; padding: 6pt 8pt;
         white-space: pre-wrap; page-break-inside: avoid; }}
  blockquote {{ border-left: 3px solid #90caf9; margin: 8pt 0; padding: 2pt 10pt;
                color: #37474f; }}
  a {{ color: #1565c0; text-decoration: none; }}
  /* Deckblatt im Suite-Design: dasselbe Blau und dieselbe Anordnung wie der
     Kopfbereich der Anwendung (Logo links, Produktname, Unterzeile). */
  /* 290mm statt 297: Die volle Seitenhöhe plus der Rahmen der inneren Blöcke
     lief um wenige Millimeter über, und der Fußhinweis landete allein auf
     einer zweiten Seite. */
  .deckblatt {{ height: 290mm; display: flex; flex-direction: column;
                overflow: hidden; }}
  .deckblatt .band {{
    background: linear-gradient(135deg, #0d47a1 0%, #1565c0 60%, #1976d2 100%);
    color: #fff; padding: 26mm 18mm 20mm; }}
  .deckblatt .marke {{ display: flex; align-items: center; gap: 7mm; }}
  .deckblatt .marke img {{ width: 26mm; height: auto; border: 0; }}
  .deckblatt .titel {{ font-size: 30pt; font-weight: bold; line-height: 1.1; }}
  .deckblatt .claim {{ font-size: 11.5pt; color: #bbdefb; margin-top: 2mm; }}
  .deckblatt .unter {{ font-size: 19pt; margin-top: 16mm; font-weight: 600; }}
  .deckblatt .rumpf {{ padding: 18mm; flex: 1; color: #37474f; }}
  .deckblatt .meta {{ font-size: 11pt; color: #546e7a; line-height: 1.8; }}
  .deckblatt .meta b {{ color: #263238; }}
  .deckblatt .fuss {{ padding: 0 18mm 16mm; font-size: 9pt; color: #90a4ae;
                      border-top: 1px solid #e0e6ea; padding-top: 6mm; }}
  .toc {{ page-break-before: always; }}
  .toc ol {{ font-size: 12pt; line-height: 2; }}
  .hinweis {{ background: #e3f2fd; border-left: 4px solid #1565c0;
              padding: 8pt 10pt; margin: 14pt 0; font-size: 10pt; }}
</style></head><body>

<div class="deckblatt">
  <div class="band">
    <div class="marke">
      {'<img src="' + LOGO + '" alt="">' if LOGO else ''}
      <div>
        <div class="titel">AI Compliance Suite</div>
        <div class="claim">Compliance Management Platform</div>
      </div>
    </div>
    <div class="unter">Anwenderhandbuch</div>
  </div>
  <div class="rumpf">
    <div class="meta">
      <b>Version</b> {VERSION}<br>
      <b>Stand</b> {DATUM}<br>
      <b>Umfang</b> CRA · NIS2 · EU AI Act · DSGVO · WiBA · Risikobewertung ·
      Compliance-Audit · Firmenverwaltung
    </div>
  </div>
  <div class="fuss">
    Erzeugt aus dem Benutzer-Wiki der Suite. Bei Abweichungen gilt das Wiki.
  </div>
</div>

<div class="toc">
  <h1>Inhalt</h1>
  <ol>{toc_html}</ol>
  <div class="hinweis">
    Dieses Handbuch ist aus dem Benutzer-Wiki der Suite erzeugt. Dort stehen
    dieselben Inhalte durchsuchbar und mit Querverweisen; die PDF-Fassung ist
    für den Druck und zur Weitergabe gedacht. Bei Abweichungen gilt das Wiki.
  </div>
</div>

{"".join(teile)}
</body></html>"""

html_pfad = ZIEL.with_suffix(".html")
html_pfad.write_text(dokument, encoding="utf-8")
print(f"HTML: {html_pfad} ({len(dokument) / 1_000_000:.1f} MB)", flush=True)

from weasyprint import HTML  # noqa: E402 — erst nach dem Sammeln laden

HTML(string=dokument, base_url=BASE).write_pdf(ZIEL)
print(f"PDF:  {ZIEL} ({ZIEL.stat().st_size / 1_000_000:.1f} MB)")
