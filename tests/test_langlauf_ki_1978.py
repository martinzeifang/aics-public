"""Der Client gibt nicht vor dem Server auf — auch bei KI-Läufen (#1978).

DER BEFUND
Auf Produktiv meldete die Maske „⛔ Der Erschließungslauf ist fehlgeschlagen",
während der Lauf **gelungen** war: nginx protokollierte **499** (client closed
request), und 84 Sekunden später standen **31 Vorschläge** in
``evidence_mappings_vorschlag`` — derselbe ``doc_id``, ``provider=cloud``.

Der Browser hatte nach **30 Sekunden** aufgegeben (Vorgabe des ``apiClient``),
der Aufruf setzte keine eigene Grenze. Gerechnet für genau diesen Vorgang: Der
WiBA-Katalog (257 Prüffragen, 31 509 Zeichen) ergibt **3 Katalog-Scheiben**, das
Dokument (7 Abschnitte) **1 Dok-Scheibe** — also **3 KI-Läufe nacheinander**,
zusammen 114 Sekunden.

WARUM ES EINEN WÄCHTER BRAUCHT
``frontend/src/utils/langlauf.ts`` ist seit #1940/#1943 genau dafür gebaut und
hatte **drei** Aufrufer, alle im Issue-Weg. Die beiden synchronen KI-Läufe sind
nie umgestellt worden und trugen weiter das Muster, das der Dateikopf von
``langlauf.ts`` ausdrücklich als Defekt beschreibt
(``e?.response?.data?.error || ersatz``). Das ist die Spiegel-Liste aus
#1731/#1735 in ihrer leisesten Form: Der Mechanismus ist da, die Verdrahtung
wächst nicht von selbst mit — und es schlägt nichts fehl, es steht nur die
falsche Aussage an der Stelle, an der ein Bearbeiter entscheidet, ob er den Lauf
(und damit die Kosten) wiederholt.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.i18n_text import ohne_kommentare

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend" / "src"
LANGLAUF = FRONTEND / "utils" / "langlauf.ts"

#: Jede Stelle, die **synchron** mit der KI spricht (``ki_lauf(...)`` statt
#: eines Streams), mit der Entscheidung dazu. Ein neuer Eintrag lässt diesen
#: Test rot werden — und zwar mit Absicht: Ein synchroner KI-Lauf ohne
#: Bedienstelle ist harmlos, einer **mit** Bedienstelle braucht eine
#: Zeitgrenze, sonst ist er genau der gemeldete Defekt.
SYNCHRONE_KI_LAEUFE = {
    "cra/aktenpruefung.py":
        "Bedienstelle AktenpruefungModal.vue → Zeitgrenze gesetzt (#1978)",
    "evidence/erschliessung.py":
        "Bedienstelle NachweisErschliessungModal.vue → Zeitgrenze gesetzt (#1978)",
    "mapping/suggest.py":
        "keine Bedienstelle — kein Web-Pfad ruft suggest_mappings auf (Dateikopf)",
    "shared/ki_mehrlauf.py":
        "kein eigener Endpunkt — Kontrolllauf innerhalb von auto_bewertung (#1863)",
    "server/services/auto_bewertung.py":
        "läuft über SSE (…/auto-bewertung/stream), kein wartender POST",
    "shared/reports/summary.py":
        "läuft über SSE (…/berichte/ki-summary/stream)",
    "shared/issue_feedback.py":
        "Zeitgrenze seit #1943 gesetzt (OBJEKT_LAUF_MS / PROJEKT_LAUF_MS)",
}

#: Die Bedienstellen, die auf einen solchen Lauf **warten**.
#:
#: ``aufruf`` ist die Datei, die die Zeitgrenze setzt, ``meldung`` die, die den
#: Fehlertext bildet. Beim Erschließungslauf sind das zwei: Der Store wirft
#: durch, die Maske entscheidet über die Meldung. Ein Test, der beides in einer
#: Datei sucht, prüft die falsche.
WARTENDE_LAEUFE = {
    "aktenpruefung": {
        "aufruf": "components/cra/AktenpruefungModal.vue",
        "aufrufFunktion": "lauf",
        "meldung": "components/cra/AktenpruefungModal.vue",
        "funktion": "lauf",
    },
    "erschliessen": {
        "aufruf": "stores/firmen.ts",
        "aufrufFunktion": "erschliessen",
        "meldung": "components/firmen/NachweisErschliessungModal.vue",
        "funktion": "direktLauf",
    },
}


def _quelle(pfad: Path) -> str:
    return ohne_kommentare(pfad.read_text(encoding="utf-8"))


def _funktion(quelle: str, name: str) -> str:
    """Der Rumpf **einer** Funktion.

    Geschnitten wird am nächsten Funktionsanfang am Zeilenrand, nicht per
    ``.*?`` über die Datei: Ein nicht-greedy Ausdruck mit DOTALL greift über
    frühere Knöpfe hinweg, und ein ``[^}]*`` endet an der ersten schließenden
    Klammer im Rumpf — beide Fallen sind in #1805/#1901 belegt.
    """
    # Die Grenze ist ein Funktions**kopf**, nicht jede `const`-Zuweisung:
    # `const res = await apiClient.post(…)` steht mitten im Rumpf und schnitt
    # ihn beim ersten Anlauf vor der Stelle ab, auf die es ankommt.
    kopf = r"(?:async\s+)?(?:function\s+{0}\b|const\s+{0}\s*=\s*(?:async\s+)?\()"
    anfang = re.search(r"(?m)^\s*" + kopf.format(name), quelle)
    assert anfang, f"Funktion {name} nicht gefunden."
    rest = quelle[anfang.end():]
    naechste = re.search(r"(?m)^\s*" + kopf.format(r"\w+"), rest)
    return rest[:naechste.start()] if naechste else rest


def test_kein_neuer_synchroner_ki_lauf_ohne_entscheidung():
    """Wer ``ki_lauf`` ruft, steht in der Liste oben — mit Begründung.

    Nicht ``ki_lauf_sse``: Ein Stream liefert von der ersten Sekunde an Daten,
    an ihm läuft keine Wartezeit des Browsers ab.
    """
    gefunden: set[str] = set()
    for p in WURZEL.rglob("*.py"):
        teile = p.relative_to(WURZEL).parts
        # ``.claude`` muss mit heraus: Darunter liegen Agenten-Worktrees,
        # also **Arbeitskopien des Repos**. Ohne den Ausschluss meldet
        # dieser Wächter dieselben Dateien ein zweites Mal und wird rot,
        # ohne dass sich im Baum etwas geändert hat — in der CI grün, auf
        # dem Entwicklungsrechner rot. Ein Prüfer, dessen Ausgabe man
        # nicht mehr liest, prüft nichts (die Lehre aus #1805/#1870).
        if teile[0] in {"tests", "node_modules", ".git", "frontend",
                        ".claude"}:
            continue
        if p.name == "ki_engine.py":
            continue
        quelle = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"(?<![_\w])ki_lauf\s*\(", quelle):
            gefunden.add(p.relative_to(WURZEL).as_posix())

    neu = gefunden - set(SYNCHRONE_KI_LAEUFE)
    assert not neu, (
        "Neue synchrone KI-Läufe ohne Entscheidung: "
        + ", ".join(sorted(neu))
        + ". Hat die Stelle eine Bedienstelle, die auf sie wartet, braucht "
          "diese eine Zeitgrenze (KI_LAUF_MS) und laufFehlerText — sonst "
          "meldet die Maske „fehlgeschlagen\" für einen Lauf, der gelang "
          "(#1978). Trage die Stelle mit ihrem Grund in SYNCHRONE_KI_LAEUFE ein."
    )
    weg = set(SYNCHRONE_KI_LAEUFE) - gefunden
    assert not weg, (
        "Liste nennt Stellen, die nicht mehr synchron mit der KI sprechen: "
        + ", ".join(sorted(weg)) + " — Eintrag entfernen, sonst wird die "
        "Liste zum Teppich.")


@pytest.mark.parametrize("endpunkt", sorted(WARTENDE_LAEUFE))
def test_jeder_wartende_ki_lauf_hat_eine_zeitgrenze(endpunkt: str):
    datei = WARTENDE_LAEUFE[endpunkt]["aufruf"]
    name = WARTENDE_LAEUFE[endpunkt]["aufrufFunktion"]
    quelle = _quelle(FRONTEND / datei)
    assert endpunkt in quelle, (
        f"{datei} ruft „{endpunkt}\" nicht mehr — Liste nachziehen.")
    # Im **Rumpf**, nicht in der Datei: Die Import-Zeile allein hat beim
    # ersten Anlauf genügt, und der Wächter blieb grün, nachdem ich die
    # Zeitgrenze am Aufruf zum Gegenbeweis wieder entfernt hatte.
    rumpf = _funktion(quelle, name)
    assert "KI_LAUF_MS" in rumpf, (
        f"{datei} → {name}() wartet auf einen synchronen KI-Lauf, setzt aber "
        f"keine Zeitgrenze. Die Vorgabe des apiClient ist 30 s; gemessen "
        f"wurden 114 s für ein Dokument gegen den WiBA-Katalog (#1978).")


@pytest.mark.parametrize("endpunkt", sorted(WARTENDE_LAEUFE))
def test_der_zeitueberlauf_wird_benannt_und_nicht_als_fehlschlag(endpunkt: str):
    """``laufFehlerText`` statt ``e?.response?.data?.error || ersatz``.

    Ein Abbruch hat **keine** ``response``, also fiel die alte Form auf den
    Ersatztext zurück und behauptete „fehlgeschlagen" für einen gelungenen
    Lauf. Geprüft wird die Datei ohne Kommentare — das Programm, nicht die
    Erzählung (#1834/#1867/#1903).
    """
    datei = WARTENDE_LAEUFE[endpunkt]["meldung"]
    name = WARTENDE_LAEUFE[endpunkt]["funktion"]
    rumpf = _funktion(_quelle(FRONTEND / datei), name)
    assert "laufFehlerText" in rumpf, (
        f"{datei} → {name}() unterscheidet den Zeitüberlauf nicht von einem "
        f"Fehlschlag.")
    # Geprüft wird **dieser** Rumpf, nicht die Datei: Die kurzen Aufrufe
    # derselben Maske (Prompt holen, Vorschlag freigeben) tragen die alte Form
    # zu Recht weiter — bei ihnen läuft keine Wartezeit ab.
    assert "response?.data?.error" not in rumpf.replace(" ", ""), (
        f"{datei} → {name}() trägt noch `e?.response?.data?.error || ersatz` — "
        f"die Form behauptet bei einem Abbruch „fehlgeschlagen\".")


def test_die_maske_laedt_nach_einem_zeitueberlauf_nach():
    """Beim Erschließungslauf ist das Ergebnis **da**, wenn die Zeit abläuft.

    Der Server schreibt die Vorschläge, auch wenn niemand mehr wartet. Ohne das
    Nachladen stand „fehlgeschlagen" über einer leeren Liste, während 31
    Vorschläge in der Datenbank lagen — und sichtbar wurden sie erst beim
    erneuten Öffnen des Dialogs.
    """
    quelle = _quelle(FRONTEND / "components" / "firmen"
                     / "NachweisErschliessungModal.vue")
    fang = quelle.split("catch", 1)
    assert len(fang) > 1, "Fehlerzweig nicht gefunden."
    assert "istZeitueberlauf" in quelle and "ladeStand" in quelle, (
        "Nach einem Zeitüberlauf muss der Stand nachgeladen werden (#1978).")


def test_der_katalogwechsel_laedt_den_stand_nach():
    """Gefunden beim Nachsehen zu #1978, gleiche Richtung.

    ``ladeStand`` filtert beim **Holen** auf das gewählte Modul und legt das
    Ergebnis ab. Lief es nur beim Öffnen (Vorgabe ``cra``) und nach einem Lauf,
    zeigte die Maske nach einem Katalogwechsel die Vorschläge des **vorigen** —
    auf Produktiv lagen 31 freigebbare WiBA-Vorschläge in der Datenbank und
    waren in der Oberfläche nirgends zu sehen.
    """
    quelle = _quelle(FRONTEND / "components" / "firmen"
                     / "NachweisErschliessungModal.vue")
    assert re.search(r"watch\(\s*modul\b", quelle), (
        "Ein Katalogwechsel muss den Stand nachladen — sonst sind vorhandene "
        "Vorschläge in der Oberfläche unerreichbar.")


def test_die_zeitgrenze_liegt_unter_den_grenzen_des_servers():
    """Die Regel, um die es geht: **der Client gibt nie vor dem Server auf.**

    Dieselbe Prüfung über zwei Schichten wie in #1903 — eine Grenze, die nur
    in der Anwendung angehoben wird, ist keine Einstellung, sondern ein Defekt
    mit Folgen.
    """
    ts = LANGLAUF.read_text(encoding="utf-8")
    treffer = re.search(r"KI_LAUF_MS\s*=\s*([\d_]+)", ts)
    assert treffer, "KI_LAUF_MS steht nicht in langlauf.ts."
    client_s = int(treffer.group(1).replace("_", "")) / 1000

    entry = (WURZEL / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
    gunicorn = re.search(r"GUNICORN_TIMEOUT:-(\d+)", entry)
    assert gunicorn, "GUNICORN_TIMEOUT nicht gefunden."

    nginx = (WURZEL / "docker" / "nginx.conf").read_text(encoding="utf-8")
    lesegrenzen = [int(m) for m in re.findall(r"proxy_read_timeout\s+(\d+)s", nginx)]
    assert lesegrenzen, "proxy_read_timeout nicht gefunden."

    assert client_s <= int(gunicorn.group(1)), (
        f"Client wartet {client_s:.0f} s, gunicorn bricht nach "
        f"{gunicorn.group(1)} s ab.")
    assert client_s <= min(lesegrenzen), (
        f"Client wartet {client_s:.0f} s, nginx bricht nach "
        f"{min(lesegrenzen)} s ab.")


def test_der_rat_nach_einem_zeitueberlauf_passt_zu_dem_was_der_lauf_schreibt():
    """Drei Rat-Varianten, weil die Läufe drei verschiedene Dinge hinterlassen.

    Die Aktenprüfung **schreibt nichts** (``cra/aktenpruefung.py`` legt keinen
    Datensatz an) — „Lade die Ansicht neu, um den Stand zu sehen" wäre dort
    eine Wegbeschreibung ins Leere.
    """
    ts = ohne_kommentare(LANGLAUF.read_text(encoding="utf-8"))
    for schluessel in ("ratIdempotent", "ratPruefen", "ratOhneStand"):
        assert f"langlauf.{schluessel}" in ts, f"{schluessel} fehlt."

    akte = _quelle(FRONTEND / "components" / "cra" / "AktenpruefungModal.vue")
    assert "'ohneStand'" in akte, (
        "Die Aktenprüfung speichert ihr Ergebnis nicht — der Rat darf nicht "
        "zum Nachladen auffordern (#1978).")

    quelle = (WURZEL / "cra" / "aktenpruefung.py").read_text(encoding="utf-8")
    assert "ersetze_" not in quelle and "save_" not in quelle, (
        "cra/aktenpruefung.py schreibt inzwischen — dann ist „ohneStand\" der "
        "falsche Rat und die Maske muss nachladen.")
