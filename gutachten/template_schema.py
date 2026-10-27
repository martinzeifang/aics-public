"""Kanonisches Variablen-Schema für Gutachten-Word-Vorlagen (#957).

Single Source of Truth für den Mapping-Wizard und die Doku. Beschreibt, welche
``{{ … }}``-Variablen eine hochgeladene DOCX-Vorlage (docxtpl/Jinja2) nutzen darf.
"""
from __future__ import annotations

from typing import Any


# (key, typ, beschreibung, pflicht)
TEMPLATE_VARIABLES: list[dict[str, Any]] = [
    # Projekt-Stammdaten
    {"key": "projekt.name", "typ": "str", "beschreibung": "Projekt-/Aktenname", "pflicht": True},
    {"key": "projekt.gutachten_art", "typ": "str", "beschreibung": "gericht | privat", "pflicht": False},
    {"key": "projekt.gericht", "typ": "str", "beschreibung": "Gericht (nur Gerichtsgutachten)", "pflicht": False},
    {"key": "projekt.kammer", "typ": "str", "beschreibung": "Kammer/Senat", "pflicht": False},
    {"key": "projekt.aktenzeichen", "typ": "str", "beschreibung": "Aktenzeichen", "pflicht": False},
    {"key": "projekt.beweisbeschluss_datum", "typ": "str", "beschreibung": "Datum Beweisbeschluss", "pflicht": False},
    {"key": "projekt.klaeger_name", "typ": "str", "beschreibung": "Kläger", "pflicht": False},
    {"key": "projekt.beklagter_name", "typ": "str", "beschreibung": "Beklagter", "pflicht": False},
    {"key": "projekt.auftraggeber", "typ": "str", "beschreibung": "Auftraggeber (Privatgutachten)", "pflicht": False},
    {"key": "projekt.auftrags_art", "typ": "str", "beschreibung": "Art des Auftrags (Privat)", "pflicht": False},
    {"key": "projekt.thema", "typ": "str", "beschreibung": "Gegenstand/Thema des Gutachtens (als Heading 2 gerendert)", "pflicht": False},
    {"key": "projekt.vertraulichkeit", "typ": "str", "beschreibung": "Vertraulichkeitsstufe", "pflicht": False},
    # Sachverständiger
    {"key": "projekt.sv_name", "typ": "str", "beschreibung": "Name des Sachverständigen", "pflicht": True},
    {"key": "projekt.sv_zertifizierung", "typ": "str", "beschreibung": "Zertifizierung/Bestellung", "pflicht": False},
    {"key": "projekt.sv_anschrift", "typ": "str", "beschreibung": "Anschrift SV", "pflicht": False},
    {"key": "projekt.sv_kontakt", "typ": "str", "beschreibung": "Kontakt SV", "pflicht": False},
    # Listen
    {"key": "beweisfragen", "typ": "list", "beschreibung": "Beweisfragen (.nr, .frage_text, .antwort_text)", "pflicht": False},
    {"key": "befunde", "typ": "list", "beschreibung": "Befunde (.nr, .titel, .beschreibung_text)", "pflicht": False},
    {"key": "beurteilungen", "typ": "list", "beschreibung": "Beurteilungen (.nr, .titel, .bewertung_text)", "pflicht": False},
    {"key": "hilfspersonen", "typ": "list", "beschreibung": "Hilfspersonen (.name, .rolle, .aufgabe)", "pflicht": False},
    {"key": "glossar", "typ": "list", "beschreibung": "Glossar (.begriff, .erklaerung) — alphabetisch", "pflicht": False},
    # Strukturierte Block-Einfügung (mehrere Absätze mit Überschriften/Zitat-Stil)
    {"key": "gutachten_volltext", "typ": "block", "beschreibung": "Kompletter Gutachten-Inhalt (Beweisfragen + Befunde + Beurteilungen, formatiert)", "pflicht": False},
    # Meta
    {"key": "datum", "typ": "str", "beschreibung": "Erstellungsdatum (TT.MM.JJJJ)", "pflicht": False},
]

CANONICAL_KEYS: set[str] = {v["key"] for v in TEMPLATE_VARIABLES}
REQUIRED_KEYS: set[str] = {v["key"] for v in TEMPLATE_VARIABLES if v["pflicht"]}

# Jinja-Konstrukte, die Server-Dateizugriff/Code-Ausführung ermöglichen → verboten (#957 Phase 6).
FORBIDDEN_JINJA = ("{% include", "{% import", "{% extends", "{% from", "{{ config", "__class__", "__globals__", "__import__")


def root_key(token: str) -> str:
    """'projekt.aktenzeichen' → 'projekt.aktenzeichen' (Punkt-Pfad bleibt),
    'beweisfragen' → 'beweisfragen'. Für Listen-Loop-Variablen wie 'f' (in
    {% for f in beweisfragen %}) liefert docxtpl nur die Root-Iterable zurück."""
    return token.strip()


def classify_variables(tokens: set[str]) -> dict[str, list[str]]:
    """Teilt erkannte Template-Tokens in erkannt / frei / ungültig.

    - erkannt: Token == kanonische Variable (oder Punkt-Pfad darunter, z. B.
      'projekt' deckt 'projekt.x' nicht ab — docxtpl liefert i. d. R. den
      Punkt-Pfad bzw. die Root). Wir matchen exakt + Root-Prefix.
    - frei: unbekanntes, syntaktisch valides Token → Wizard fragt Zuordnung.
    - ungültig: leer/whitespace.
    """
    roots = {k.split(".")[0] for k in CANONICAL_KEYS}
    erkannt, frei, ungueltig = [], [], []
    for t in sorted(tokens):
        t = (t or "").strip()
        if not t:
            ungueltig.append(t)
        elif t in CANONICAL_KEYS or t.split(".")[0] in roots:
            erkannt.append(t)
        else:
            frei.append(t)
    return {"erkannt": erkannt, "frei": frei, "ungueltig": ungueltig}
