"""Funde des Schirmlaufs vom 09.11.2026 (#2097/#2098).

Ein Durchgang über **71 Bildschirme** aller zehn Module gegen v8.7.0 auf Dev,
mit Screenshot und Textprüfung je Reiter. Zwei Funde, und beide gehören zu
Klassen, die dieser Sprint schon behandelt hat.

**#2097 — und es war meine eigene Korrektur.** Bis v8.6.3 antwortete
``GET /gerichts/<p>/aufbewahrung`` mit **404**, wenn keine Frist gesetzt war;
der Store machte daraus ``null``, und die Zeile blieb unsichtbar. Mit #2029
liefert derselbe Endpunkt **200 mit ``{}``** — richtig, denn eine nicht
gesetzte Frist ist der Normalzustand jedes neuen Gutachtens und kein Fehler.
Nur ist ``{}`` **wahr**: Der Block rendert, beide Werte sind ``undefined``,
und in der Oberfläche stand wörtlich „Archiv bis: {v0} ({v1} Tage
verbleibend)".

Die Lehre ist nicht „#2029 war falsch", sondern: **Ein geänderter
Antwortvertrag gehört gegen seine Leser geprüft.** Aus 404 wird 200 — und
jedes ``v-if`` auf die Hülle kippt dabei die Bedeutung.

**#2098 — die Ursache verschwand hinter der Meldung.** Im DSGVO-Modul
erschien zweimal „⛔ Laden fehlgeschlagen."; in drei vollständigen
Wiederholungsläufen nicht mehr, und dabei gab es **keine** 4xx/5xx-Antwort.
Nachstellen ließ es sich nicht, weil nirgends steht, woran es lag: 440
``fehlerText``-Aufrufe in 51 Stores, und ``console.error`` stand in **einem**
davon. Jeder Fehler ohne Server-Antwort war in der Oberfläche derselbe Satz
und in der Konsole nichts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tests.i18n_text import ohne_kommentare, vue_text

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "frontend" / "src"
FEHLER = SRC / "utils" / "fehler.ts"
GUTACHTEN = SRC / "views" / "gutachten" / "GerichtsgutachtenView.vue"


# ── #2097: Inhalt statt Hülle ──────────────────────────────────────────────

def test_die_aufbewahrungszeile_prueft_den_inhalt():
    """``v-if`` auf das Objekt ist für ``{}`` wahr — und ``{}`` ist seit #2029
    die richtige Antwort auf „noch nichts erfasst"."""
    quelle = ohne_kommentare(GUTACHTEN.read_text(encoding="utf-8"))
    assert 'v-if="store.aufbewahrung?.archiv_bis_datum"' in quelle
    assert 'v-if="store.aufbewahrung"' not in quelle


def test_der_leere_zustand_wird_benannt():
    """Eine verschwundene Zeile sagt dem Anwender nicht, dass die Frist noch
    aussteht — der Knopf darunter erst, wenn man ihn deutet."""
    text = vue_text(GUTACHTEN)
    assert "Noch keine Aufbewahrungsfrist gesetzt" in text


def test_der_endpunkt_antwortet_weiter_mit_200_und_leer():
    """#2029 bleibt, wie es ist — die Reparatur gehört in die Maske.

    Der naheliegende „Fix" wäre, zu 404 zurückzukehren. Das wäre falsch: Eine
    nicht gesetzte Aufbewahrungsfrist ist der **Normalzustand** jedes neu
    angelegten Gutachtens, und ein Normalzustand ist kein Fehler (#1995).
    Dieser Test hält die Richtung fest, damit der nächste Anlauf nicht am
    falschen Ende repariert.
    """
    from tests.i18n_text import python_programm

    programm = python_programm(REPO / "server/api/gutachten.py")
    assert "jsonify(d or {}), 200" in programm


# **Warum hier kein allgemeiner Wächter steht.**
#
# Der erste Anlauf prüfte jedes ``v-if="x"``, dessen Block ``$t(… x.feld …)``
# enthält — die **Form** des Fehlers. Er fand 26 Stellen, und sie waren
# nahezu alle richtig: ``v-if="createResult"`` schützt ein lokales Ergebnis,
# das bis zur Antwort ``null`` ist, und bleibt es auch.
#
# Gefährlich ist die Form nur dort, wo der Endpunkt **200 mit leerem Objekt**
# antworten kann — und das steht in keinem ``.vue``. Ein Wächter, der 26
# korrekte Stellen meldet, braucht eine Ausnahmeliste, und eine
# Ausnahmeliste wird zum Teppich; seine Ausgabe liest nach dem dritten Mal
# niemand mehr (#1805/#1834).
#
# Die Lehre gehört deshalb hierhin und nicht in eine Prüfung:
# **Wer einen Antwortvertrag von 404 auf 200-mit-leer ändert, prüft seine
# Leser.** Aus „nicht vorhanden" wird „vorhanden und leer", und jedes ``v-if``
# auf die Hülle kippt dabei die Bedeutung.


# ── #2098: die Ursache bleibt lesbar ───────────────────────────────────────

def test_die_ursache_wird_protokolliert():
    """Eine Stelle, 440 Nutznießer — kein Aufrufer muss angefasst werden."""
    quelle = ohne_kommentare(FEHLER.read_text(encoding="utf-8"))
    assert "console.warn" in quelle, "fehlerText verliert die Ursache"
    # In die **Konsole**, nicht in die Oberfläche (#737).
    assert "return t(" in quelle


def test_netzfehler_sind_kein_anwendungsfehler():
    """„Laden fehlgeschlagen" schickt den Anwender ins falsche Haus."""
    quelle = ohne_kommentare(FEHLER.read_text(encoding="utf-8"))
    for marke in ("ERR_NETWORK", "ECONNABORTED", "kein_netz",
                  "zeitueberschreitung"):
        assert marke in quelle, marke
    for spr in ("de", "en"):
        katalog = json.loads(
            (SRC / "i18n" / spr / "fehler.json").read_text(encoding="utf-8"))
        assert katalog.get("kein_netz"), spr
        assert katalog.get("zeitueberschreitung"), spr


def test_eine_servermeldung_hat_weiter_vorrang():
    """Die Reihenfolge bleibt unverändert — sonst wäre diese Erweiterung eine
    Verhaltensänderung, und jeder Bestandstest verlöre seine Aussage."""
    quelle = ohne_kommentare(FEHLER.read_text(encoding="utf-8"))
    i_server = quelle.index("vom_server")
    i_netz = quelle.index("netzfall(e)")
    assert i_server < i_netz, (
        "Der Netzfall darf erst geprüft werden, wenn der Server nichts sagt")


def test_die_konsole_darf_fehlen():
    """Tests und eingebettete Sichten haben nicht immer eine."""
    quelle = ohne_kommentare(FEHLER.read_text(encoding="utf-8"))
    stelle = quelle.index("console.warn")
    umfeld = quelle[max(0, stelle - 200):stelle + 200]
    assert "try {" in umfeld and "catch" in umfeld
