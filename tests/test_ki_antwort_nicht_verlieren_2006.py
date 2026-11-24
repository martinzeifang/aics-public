"""Eine KI-Antwort geht nicht mehr an einem Zeichen verloren (#2006/#2007).

**#2006 — ein unescaptes Anführungszeichen kostete die ganze Antwort.**
Aus dem Betrieb, Cloud-Provider, 590 Tokens, 32 Sekunden:

    ⚠ JSON-Parse: Expecting ',' delimiter: line 7 column 1309 (char 1481)

Die Antwort war inhaltlich vollständig — vier Absätze Begründung, fünf
Empfehlungen, drei genutzte Nachweise. Verloren an **einem Zeichen**: Das
Modell schrieb ``wird als „Wahrscheinlich" eingestuft`` — typografisch
geöffnet, mit einem **geraden** Anführungszeichen geschlossen. Innerhalb eines
JSON-Strings beendet das die Zeichenkette.

Auf dem Cloud-Weg gibt es dagegen keine strukturelle Zusicherung: ``force_json``
wirkt bei Ollama und OpenAI-kompatiblen Endpunkten, **Anthropic kennt keinen
solchen Modus** (#1841/E3). Das Modell wird nur *gebeten*, JSON zu liefern.

**#2007 — gespeichert, und die Maske meldete einen Fehler.**
``KiBewertungsBlock`` erkennt eine Übernahme an ``bewertung``/``score``/
``status``/``ok``/``applied``. ``POST …/risiken/<id>/parse-response`` lieferte
``risikowert``/``risiko_label``/``saved`` — keinen davon. Die Bewertung war
**geschrieben** (2327 Zeichen Begründung, ``felder`` gesetzt), und der Anwender
sah „Die Antwort konnte nicht ausgewertet werden."
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from shared import json_io

WURZEL = Path(__file__).resolve().parents[1]

#: Der gemeldete Fall, so knapp wie er noch scheitert.
GEMELDET = ('{"felder": {"stride_kategorie": "Repudiation (R) \u2013 Abstreitbarkeit von Aktionen", "eintrittswahrscheinlichkeit": "M\u00f6glich", "auswirkung": "Mittel"}, '
            '"bewertung": "Die Eintrittswahrscheinlichkeit wird als '
            '„Wahrscheinlich" eingestuft, da OT-Prozessnetze bekannte '
            'Angriffsziele sind.", "empfehlungen": ["IDS einfuehren"]}')


# ── #2006 · die Reparatur ───────────────────────────────────────────────────

def test_der_gemeldete_fall_ist_ohne_reparatur_kaputt():
    """Erst den Befund festhalten, dann die Behebung."""
    with pytest.raises(json.JSONDecodeError):
        json.loads(GEMELDET)


def test_der_gemeldete_fall_wird_gerettet():
    wert, berichte = json_io.lade_mit_bericht(GEMELDET, context="test")
    assert "Wahrscheinlich" in wert["bewertung"]
    # Alles **nach** dem Zeichen ist erhalten — darum geht es.
    assert "Angriffsziele" in wert["bewertung"]
    assert wert["empfehlungen"] == ["IDS einfuehren"]
    assert "Repudiation" in wert["felder"]["stride_kategorie"]
    assert berichte and "Anführungszeichen" in berichte[0]


def test_eine_gueltige_antwort_wird_nicht_angefasst():
    """Kein Bericht, kein Eingriff — sonst wäre jede Antwort „repariert"."""
    gut = '{"a": 1, "b": "Text mit \\"escapten\\" Zeichen"}'
    wert, berichte = json_io.lade_mit_bericht(gut, context="test")
    assert berichte == []
    assert wert["b"] == 'Text mit "escapten" Zeichen'


def test_das_kriterium_ist_das_naechste_zeichen():
    """Ein ``"`` beendet die Zeichenkette nur vor ``,`` ``}`` ``]`` ``:``."""
    for roh, erwartet in [
        ('{"a": "x" }', "x"),
        ('{"a": "x"}', "x"),
        ('{"a": "x" , "b": 1}', "x"),
        ('{"a": "sagte "hallo" weiter"}', 'sagte "hallo" weiter'),
    ]:
        wert, _ = json_io.lade_mit_bericht(roh, context="test")
        assert wert["a"] == erwartet, roh


def test_abgeschnittene_antwort_wird_geschlossen():
    """Die zweite bekannte Beschädigung — bisher nur im Anforderungs-Pfad."""
    roh = '{"felder": {"a": 1}, "bewertung": "Der Text bricht mitten im Sa'
    wert, berichte = json_io.lade_mit_bericht(roh, context="test")
    assert wert["felder"] == {"a": 1}
    assert wert["bewertung"].startswith("Der Text bricht")
    assert any("abgeschnitten" in b for b in berichte)


def test_wirklich_unlesbares_bleibt_ein_fehler():
    """Der Riegel bleibt — er war nur zu scharf, nicht falsch (die Lehre
    aus #1995)."""
    for roh in ("", "kein json", "[[[", "{{{{"):
        with pytest.raises(ValueError):
            json_io.lade_mit_bericht(roh, context="test")


def test_die_grenze_der_heuristik_ist_benannt():
    """Ein Zitat vor einem Komma ist von einem Zeichenkettenende nicht zu
    unterscheiden. Dass die Reparatur das nicht löst, muss im Code stehen —
    eine Heuristik, deren Grenze verschwiegen wird, wird für eine Garantie
    gehalten."""
    quelle = (WURZEL / "shared" / "json_io.py").read_text(encoding="utf-8")
    assert "unauflösbar" in quelle or "unaufloesbar" in quelle


def test_alle_ki_pfade_benutzen_die_gemeinsame_reparatur():
    """Drei Module parsen KI-JSON. Eine Reparatur in einem von drei ist die
    Spiegel-Liste aus #1731 — nur dass hier die Antwort verloren geht."""
    for pfad in ("risikobewertung/prompts.py", "wiba/prompts.py",
                 "server/services/anforderung_prompt.py"):
        quelle = (WURZEL / pfad).read_text(encoding="utf-8")
        programm = re.sub(r"(?m)^\s*#.*$", "", quelle)
        assert "lade_mit_bericht" in programm, (
            f"{pfad} benutzt die gemeinsame Reparatur nicht (#2006)")


def test_die_reparatur_wird_weitergegeben():
    """Der Aufrufer muss erfahren, dass am Text gearbeitet wurde."""
    from risikobewertung.prompts import parse_json_antwort

    data = parse_json_antwort(GEMELDET)
    assert data.get("_reparaturen"), (
        "parse_json_antwort verschweigt die Reparatur — dann sieht sie aus "
        "wie ein glatter Treffer (#2006)")


# ── #2007 · die Antwortform ─────────────────────────────────────────────────

def _erkannte_schluessel() -> set[str]:
    """Die Schlüssel, an denen die geteilte Maske eine Übernahme erkennt.

    Aus der Maske gelesen, nicht abgetippt — sonst prüft der Test seine eigene
    Kopie (die Lehre aus #1731).
    """
    quelle = (WURZEL / "frontend" / "src" / "components" / "shared"
              / "KiBewertungsBlock.vue").read_text(encoding="utf-8")
    i = quelle.index("const uebernommen =")
    block = quelle[i:i + 1200]
    block = re.sub(r"(?m)^\s*//.*$", "", block)
    return set(re.findall(r"res\.data\?\.(\w+)", block))


def test_die_maske_erkennt_die_schluessel_der_risikobewertung():
    erkannt = _erkannte_schluessel()
    assert "risikowert" in erkannt or "saved" in erkannt, (
        "Die Maske erkennt die Antwortform der Risikobewertung nicht (#2007)")


def test_jeder_parse_endpunkt_liefert_einen_erkannten_schluessel():
    """**Der Wächter.** Vier von fünf Modulen hatten einen — die
    Risikobewertung nicht, und das fiel erst im Betrieb auf.

    Geprüft über den Syntaxbaum: welche Zeichenketten der Endpunkt als
    Dict-Schlüssel benutzt. Das ist das Programm, nicht die Erzählung (#1834).
    Ein echter HTTP-Rundlauf über alle fünf Module wäre stärker und braucht
    fünf Vorrichtungen; für die Risikobewertung steht er unten.
    """
    import ast

    erkannt = _erkannte_schluessel()
    ziele = [
        ("server/api/risikobewertung.py", "parse_response"),
        ("server/api/cra/__init__.py", "anf_parse_response"),
        ("server/api/cra/__init__.py", "owasp_parse_response"),
        ("server/api/wiba/__init__.py", "parse_control_response"),
        ("server/api/aiact.py", "anf_parse"),
        ("server/api/nis2.py", "anf_parse"),
        ("server/api/dsgvo.py", "anf_parse_response"),
    ]
    fehlt = []
    for pfad, fn in ziele:
        baum = ast.parse((WURZEL / pfad).read_text(encoding="utf-8"))
        knoten = next((k for k in ast.walk(baum)
                       if isinstance(k, ast.FunctionDef) and k.name == fn), None)
        assert knoten is not None, f"{pfad}:{fn} gibt es nicht mehr"
        schluessel = {s.value for d in ast.walk(knoten)
                      if isinstance(d, ast.Dict)
                      for s in d.keys
                      if isinstance(s, ast.Constant) and isinstance(s.value, str)}
        if not (schluessel & erkannt):
            fehlt.append(f"{pfad}:{fn}")
    assert not fehlt, (
        "Diese parse-response-Endpunkte liefern keinen Schlüssel, den die "
        f"geteilte Maske erkennt — sie melden „konnte nicht ausgewertet "
        f"werden\", auch wenn sie gespeichert haben (#2007): {fehlt}")


def test_rundlauf_die_bewertung_wird_uebernommen_und_gemeldet(pg, client, auth_headers):
    """**Der Rundlauf.** Gespeichert **und** als übernommen gemeldet."""
    from risikobewertung import db as rdb

    DB = Path("data/db/risikobewertung.sqlite")
    projekt = "pytest-ki-antwort-2006"
    # `risikobewertung.db` hat kein `ensure_db` — das Schema legt der
    # Warmup der App an, und die `client`-Vorrichtung hat ihn gelaufen.
    rdb.delete_projekt(DB, projekt)
    rdb.save_projekt(DB, projekt, "STRIDE", "Testprojekt")
    try:
        rid = rdb.save_risiko(DB, {
            "projekt_name": projekt, "risk_name": "Testrisiko",
            "beschreibung": "Beschreibung", "framework": "STRIDE"})
        res = client.post(
            f"/api/risikobewertung/projekte/{projekt}/risiken/{rid}/parse-response",
            json={"raw": GEMELDET, "apply": True}, headers=auth_headers)
        assert res.status_code == 200, res.get_data(as_text=True)
        body = res.get_json()

        # #2007: Die Maske erkennt die Übernahme.
        erkannt = _erkannte_schluessel()
        assert any(k in body for k in erkannt), (
            f"keiner der erkannten Schlüssel {sorted(erkannt)} in {sorted(body)}")
        assert body.get("ok") is True and body.get("applied") is True

        # #2006: Die Reparatur wird genannt.
        assert body.get("reparaturen"), "die Reparatur wird verschwiegen"

        # Und gespeichert ist sie auch.
        risiken = rdb.load_risiken(DB, projekt) or []
        gespeichert = next(r for r in risiken if str(r.get("id")) == str(rid))
        assert "Wahrscheinlich" in str(gespeichert.get("bewertung_text") or "")
        assert gespeichert.get("risikowert")
    finally:
        rdb.delete_projekt(DB, projekt)
