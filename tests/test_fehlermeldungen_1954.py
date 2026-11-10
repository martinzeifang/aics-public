"""Eine Fehlermeldung je Handlung — und sie kommt aus dem Katalog (#1954).

DER BEFUND
In den 51 Stores stand **420-mal** dieselbe Form::

    error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'

mit **201 verschiedenen** Rückfalltexten. Vier Schreibweisen für dasselbe
(„Fehler beim Löschen" · „Löschen fehlgeschlagen." · „Löschen fehlgeschlagen" ·
„Fehler beim Löschen des Produkts") — und **93-mal** nur das Wort „Fehler", das
dem Anwender nicht einmal sagt, welche Handlung gescheitert ist. Dazu stand in
``auth.ts`` ein englisches „Login failed" mitten in der deutschen Oberfläche.

Das ist die Spiegel-Liste aus #1731/#1735 in ihrer leisesten Form: Niemandem
fällt es auf, weil **nichts fehlschlägt** — die Oberfläche sagt nur an jeder
Stelle etwas anderes.

WAS DIESER TEST FESTHÄLT
Dass kein Store wieder einen eigenen Rückfalltext mitbringt, dass jeder
benutzte Fall im Katalog beider Sprachen steht, und dass die Typ-Union mit dem
Katalog übereinstimmt. Der letzte Punkt ist der, den der Typprüfer **nicht**
abdeckt: Ein Schlüssel im Katalog, den die Union nicht kennt, fällt dem
Typprüfer auf — ein Fall in der Union, den der Katalog nicht hat, nicht. Dann
steht im Knopf wörtlich ``fehler.anmelden``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend" / "src"
STORES = FRONTEND / "stores"
HELFER = FRONTEND / "utils" / "fehler.ts"
SPRACHEN = ("de", "en")

#: Die alte Form. Sie darf nicht zurückkommen — mit ihr kommen die 201 Texte.
ALTE_FORM = re.compile(r"\?\.response\?\.data\?\.error\s*\|\|\s*['\"]")

#: Wortstämme, die einen deutschen Rückfalltext verraten. Bewusst eng: Der
#: Test soll die **Fehlermeldungen** treffen, nicht jede deutsche Zeichenkette
#: im Store (Feldnamen, Statuswerte und Überschriften sind eigene Vorgänge).
DEUTSCHE_FEHLERTEXTE = re.compile(
    r"['\"][^'\"]*(?:fehlgeschlagen|Fehler beim|Fehler bei |konnte nicht|"
    r"konnten nicht|nicht lesbar|nicht abrufbar)[^'\"]*['\"]")


def _katalog(code: str) -> dict[str, str]:
    """Nur die **Fälle** — die flachen Schlüssel.

    Verschachteltes ist etwas anderes: ``zusatz.fehlendeFelder`` ist ein
    Textbaustein mit Platzhalter („fehlt: {felder}"), kein Fehlerfall. Ihn in
    die Typ-Union zu nehmen hieße, ``fehlerText(e, 'fehlendeFelder')`` erlauben
    — ein Satzfragment als ganze Meldung.
    """
    roh = json.loads((FRONTEND / "i18n" / code / "fehler.json")
                     .read_text(encoding="utf-8"))
    return {k: v for k, v in roh.items() if isinstance(v, str)}


def _ohne_kommentare(text: str) -> str:
    """Kommentare entfernen — das Programm prüfen, nicht die Erzählung.

    Die Lehre aus #1834/#1867/#1878/#1903, hier zum fünften Mal: Der Dateikopf
    von ``utils/fehler.ts`` **zitiert** die alten Meldungen, um zu erklären,
    warum es diesen Katalog gibt. Ohne diesen Schritt würde der Test daran rot.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(z for z in text.split("\n")
                     if not z.lstrip().startswith(("//", "*")))


def _stores() -> list[Path]:
    return sorted(STORES.glob("*.ts"))


# ── Katalog ──────────────────────────────────────────────────────────────────

def test_katalog_ist_paritaetisch():
    mengen = {code: set(_katalog(code)) for code in SPRACHEN}
    erste = mengen["de"]
    for code, menge in mengen.items():
        assert menge == erste, f"{code} weicht ab: {menge ^ erste}"
    assert len(erste) >= 15, f"unerwartet klein: {sorted(erste)}"


def test_keine_leeren_texte():
    for code in SPRACHEN:
        for schluessel, wert in _katalog(code).items():
            assert wert.strip(), f"{code}/{schluessel} ist leer"


def test_die_typ_union_stimmt_mit_dem_katalog():
    """Beide Richtungen.

    Ein Katalog-Schlüssel ohne Union-Eintrag fällt dem Typprüfer auf, sobald
    ihn jemand benutzt. Umgekehrt nicht: Ein Fall in der Union, den der Katalog
    nicht führt, ergibt zur Laufzeit einen Knopf mit der Aufschrift
    ``fehler.<fall>`` — `strictTemplates` ist aus (#1858), und ein fehlender
    i18n-Schlüssel ist kein Typfehler. Genau so ist mir beim Bauen `anmelden`
    durchgegangen, nur in der anderen Richtung.
    """
    quelle = _ohne_kommentare(HELFER.read_text(encoding="utf-8"))
    union = re.search(r"export type FehlerFall\s*=([^\n]*(?:\n\s*\|[^\n]*)*)",
                      quelle)
    assert union, "FehlerFall nicht gefunden"
    faelle = set(re.findall(r"'(\w+)'", union.group(1)))
    assert faelle == set(_katalog("de")), (
        f"Union und Katalog weichen ab: {faelle ^ set(_katalog('de'))}")


def test_jeder_benutzte_fall_steht_im_katalog():
    bekannt = set(_katalog("de"))
    verstoesse: list[str] = []
    for p in _stores():
        for m in re.finditer(r"fehlerText\([^,)]+,\s*'(\w+)'\)",
                             _ohne_kommentare(p.read_text(encoding="utf-8"))):
            if m.group(1) not in bekannt:
                verstoesse.append(f"{p.name}: '{m.group(1)}'")
    assert not verstoesse, f"unbekannte Fälle: {verstoesse}"


# ── Die Stores ───────────────────────────────────────────────────────────────

def test_kein_store_baut_die_meldung_selbst():
    """Die alte Form darf nicht zurückkommen.

    Mit ihr kommt der eigene Rückfalltext, und beim nächsten Store steht wieder
    eine fünfte Schreibweise für „Löschen fehlgeschlagen".
    """
    verstoesse: list[str] = []
    for p in _stores():
        inhalt = _ohne_kommentare(p.read_text(encoding="utf-8"))
        for zeile in inhalt.splitlines():
            if ALTE_FORM.search(zeile):
                verstoesse.append(f"{p.name}: {zeile.strip()[:88]}")
    assert not verstoesse, (
        "Rückfalltext am Aufrufort statt im Katalog — `fehlerText(e, '<fall>')` "
        "benutzen:\n  " + "\n  ".join(verstoesse))


def test_kein_store_traegt_noch_einen_deutschen_fehlertext():
    """Die Gegenrichtung: auch nicht in einer **anderen** Form.

    Der Test oben kennt nur die eine Bauweise. Ein eigener Helfer mit
    ``fallback: string`` — davon gab es fünf — hätte ihn nicht ausgelöst, und
    die Meldungen wären weiter unübersetzbar gewesen.
    """
    verstoesse: list[str] = []
    for p in _stores():
        inhalt = _ohne_kommentare(p.read_text(encoding="utf-8"))
        for treffer in DEUTSCHE_FEHLERTEXTE.findall(inhalt):
            verstoesse.append(f"{p.name}: {treffer[:80]}")
    assert not verstoesse, (
        "deutsche Fehlermeldungen in den Stores:\n  " + "\n  ".join(verstoesse))


def test_jeder_store_mit_fehlertext_nutzt_den_helfer():
    for p in _stores():
        inhalt = p.read_text(encoding="utf-8")
        if "fehlerText(" in inhalt:
            assert "from '../utils/fehler'" in inhalt, (
                f"{p.name}: benutzt fehlerText ohne Import — zur Laufzeit ein "
                f"ReferenceError, den der Build nicht beanstandet (#1854)")


def test_der_helfer_faellt_nicht_auf_e_message_zurueck():
    """``e.message`` wäre „Network Error" — englischer Jargon in jeder Sprache.

    Dazu würde der Rückfall damit vom Browser bestimmt und nicht vom Katalog;
    eine Meldung, die sich nicht übersetzen lässt, ist genau das Problem, das
    hier behoben wurde.
    """
    quelle = _ohne_kommentare(HELFER.read_text(encoding="utf-8"))
    assert "message" not in quelle, (
        "fehler.ts greift auf `message` zu — der Rückfall gehört in den Katalog")


def test_die_servermeldung_hat_vorrang():
    """Die Reihenfolge ist die bisherige: erst der Server, dann der Rückfall.

    Umgekehrt verschluckte die Umstellung jede Fachmeldung des Servers — und
    das wären 420 Stellen auf einmal.
    """
    quelle = _ohne_kommentare(HELFER.read_text(encoding="utf-8"))
    vom_server = quelle.index("response")
    vom_katalog = quelle.index("t(`fehler.")
    assert vom_server < vom_katalog, (
        "der Katalog-Rückfall steht vor der Servermeldung")
