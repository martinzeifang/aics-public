"""Speichern darf nicht löschen, was es nicht nennt — #2069/#2070/#2071/#2092/#2063.

Dieselbe Fehlerklasse zum sechsten Mal in diesem Repo: #1540 (``meta_json``),
#1771 (``artefakt``), #1805 (``notizen``), #1820 (``aktuelle_version``) — und
jetzt vier weitere Speicherfunktionen. Der Schutz gehört **in die
Speicherfunktion**, nicht in die Aufrufer: Beim nächsten Aufrufer fehlt er
sonst wieder, und nichts schlägt fehl.

Die Regel ist überall dieselbe: ``None``/nicht genannt behält den Bestand, eine
**ausdrücklich** leere Zeichenkette leert. Sonst ließe sich ein Zieldatum nicht
mehr entfernen.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

CRA_DB = Path("data/db/cra.sqlite")
DSGVO_DB = Path("data/db/dsgvo.sqlite")
NIS2_DB = Path("data/db/nis2.sqlite")

PROJ = "pytest-teilupdate-2069"


def _quelle_ohne_kommentare(pfad: str) -> str:
    """Quelltext ohne Kommentare — je Sprache mit dem richtigen Werkzeug.

    ``tests.i18n_text.ohne_kommentare`` kennt HTML- und JS-Kommentare, nicht
    Pythons ``#``. Beim ersten Anlauf dieses Tests traf der Wächter deshalb
    **meinen eigenen Kommentar**, der die Reparatur erklärt
    (``# #2071: `massnahme=''` stand hier hart``) — das Programm prüfen, nicht
    die Erzählung, zum fünften Mal (#1834/#1867/#1878/#1903/#1974).

    Für Python läuft es über den Syntaxbaum: ``ast.unparse`` sieht weder
    Kommentare noch Docstrings (die werden eigens entfernt).
    """
    text = Path(pfad).read_text(encoding="utf-8")
    if not pfad.endswith(".py"):
        from tests.i18n_text import ohne_kommentare
        return ohne_kommentare(text)
    baum = ast.parse(text)
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef)):
            if (knoten.body and isinstance(knoten.body[0], ast.Expr)
                    and isinstance(knoten.body[0].value, ast.Constant)
                    and isinstance(knoten.body[0].value.value, str)):
                knoten.body = knoten.body[1:] or [ast.Pass()]
    return ast.unparse(baum)


# ══════════════════════════════════════════════════════════════════════════════
# #2069 — der Abschlussbericht löschte seinen Pflichtinhalt
# ══════════════════════════════════════════════════════════════════════════════

def test_root_cause_ueberlebt_den_abschlussbericht_assistenten():
    """Art. 23 Abs. 4 Buchst. d NIS2 verlangt im Abschlussbericht „Angaben zur
    Art der Bedrohung bzw. zugrunde liegenden Ursache".

    Der Assistent, der diesen Bericht erzeugt, baute eine Nutzlast aus sechs
    Feldern, und ``save_incident`` schrieb neun Spalten — ``root_cause``,
    ``betroffene_assets`` und ``notizen`` wurden geleert.
    """
    from nis2 import incident_db as idb

    idb.save_incident(NIS2_DB, PROJ, {
        "incident_id": "INC-2069", "titel": "Prüffall",
        "root_cause": "Fehlkonfiguration im Reverse-Proxy",
        "betroffene_assets": "web-01, web-02",
        "notizen": "Von Hand erfasst",
        "erheblich": False})

    # Nutzlast wie im Assistenten: sechs Felder, die vier anderen fehlen.
    idb.save_incident(NIS2_DB, PROJ, {
        "incident_id": "INC-2069", "titel": "Prüffall",
        "kenntnis_zeitpunkt": "", "schweregrad": "hoch",
        "grenzueberschreitend": False, "status": "offen"})

    inc = next(i for i in idb.list_incidents(NIS2_DB, PROJ)
               if i["incident_id"] == "INC-2069")
    assert inc["root_cause"] == "Fehlkonfiguration im Reverse-Proxy", (
        "der Assistent hat die Grundursache gelöscht — genau den Pflichtinhalt")
    assert inc["betroffene_assets"] == "web-01, web-02"
    assert inc["notizen"] == "Von Hand erfasst"
    assert not inc["erheblich"], (
        "eine dokumentierte Einschaetzung (nicht erheblich) ist gekippt; an ihr "
        "haengt die Meldepflicht nach Art. 23")


def test_ausdruecklich_leer_leert_auch_bei_vorfaellen():
    """Die Gegenrichtung: Was ausdrücklich leer kommt, wird leer."""
    from nis2 import incident_db as idb

    idb.save_incident(NIS2_DB, PROJ, {
        "incident_id": "INC-2069-b", "titel": "T", "root_cause": "irgendwas"})
    idb.save_incident(NIS2_DB, PROJ, {
        "incident_id": "INC-2069-b", "titel": "T", "root_cause": ""})
    inc = next(i for i in idb.list_incidents(NIS2_DB, PROJ)
               if i["incident_id"] == "INC-2069-b")
    assert inc["root_cause"] == ""


# ══════════════════════════════════════════════════════════════════════════════
# #2070 / #2071 — alle KI-Pfade löschten Verantwortlichen und Zieldatum
# ══════════════════════════════════════════════════════════════════════════════

BEWERTUNGS_MODULE = [
    ("cra.db", CRA_DB, "cra"),
    ("dsgvo.db", DSGVO_DB, "dsgvo"),
]


@pytest.mark.parametrize("modulname,db,kuerzel", BEWERTUNGS_MODULE)
def test_sechs_positionsargumente_loeschen_nichts(modulname, db, kuerzel):
    """So rufen die KI-Pfade: ``save_bewertung(db, projekt, id, score,
    kommentar, massnahme)`` — sechs Positionsargumente.

    In DSGVO taten das **alle vier** KI-Pfade (Copy/Paste-Übernahme,
    automatische Bewertung, Direktlauf, Massenbewertung); CRA und NIS2 hatten
    für denselben Weg längst Helfer, die die Felder nachziehen. Die Asymmetrie
    war der Beleg, dass es ein Versehen ist.
    """
    import importlib

    m = importlib.import_module(modulname)
    aid = f"{kuerzel.upper()}-TU-2070"
    m.save_bewertung(db, PROJ, aid, 3, "Erstbewertung", "Maßnahme A",
                     "Hr. Kaiser", "2027-03-01")
    m.save_bewertung(db, PROJ, aid, 4, "KI-Bewertung", "Maßnahme B")

    zeile = m.load_bewertungen(db, PROJ)[aid]   # {anforderung_id: zeile}
    assert zeile["bewertung"] == 4
    assert zeile["kommentar"] == "KI-Bewertung"
    assert zeile["verantwortlich"] == "Hr. Kaiser", (
        "jede KI-Bewertung hat den Verantwortlichen gelöscht")
    assert zeile["zieldatum"] == "2027-03-01", (
        "jede KI-Bewertung hat das Zieldatum gelöscht")


@pytest.mark.parametrize("modulname,db,kuerzel", BEWERTUNGS_MODULE)
def test_ausdrueckliches_leeren_bleibt_moeglich(modulname, db, kuerzel):
    """Sonst ließe sich ein Zieldatum nicht entfernen."""
    import importlib

    m = importlib.import_module(modulname)
    aid = f"{kuerzel.upper()}-TU-2070-b"
    m.save_bewertung(db, PROJ, aid, 3, "k", "m", "Hr. Kaiser", "2027-03-01")
    m.save_bewertung(db, PROJ, aid, 3, "k", "m", "", "")
    zeile = m.load_bewertungen(db, PROJ)[aid]
    assert zeile["verantwortlich"] == "" and zeile["zieldatum"] == ""


def test_cra_massnahme_ueberlebt_den_prefill_vorschlag():
    """#2071: ``accept_suggestion`` gab ``massnahme=''`` hart mit.

    Der einzige Weg in diese Funktion ist der Knopf „Übernehmen" am
    Repo-Prefill-Vorschlag, und der Store sendet nur
    ``{field_id, score, kommentar, target}``. Gelesen werden die drei Felder vom
    Maßnahmenplan im Konformitätsbericht.
    """
    from cra.db import load_bewertungen, save_bewertung

    aid = "CRA-TU-2071"
    save_bewertung(CRA_DB, PROJ, aid, 3, "k", "Signierte Updates einführen",
                   "Hr. Kaiser", "2027-03-01")
    # Wie `accept_suggestion` heute ruft: nur Bewertung und Kommentar.
    save_bewertung(CRA_DB, PROJ, aid, 4, "Aus Repo-Vorschlag übernommen")
    zeile = load_bewertungen(CRA_DB, PROJ)[aid]
    assert zeile["massnahme"] == "Signierte Updates einführen"
    assert zeile["verantwortlich"] == "Hr. Kaiser"
    assert zeile["zieldatum"] == "2027-03-01"


def test_der_aufrufer_leert_die_massnahme_nicht_mehr_hart():
    """Das Teil-Update allein genügt hier nicht — ein ausdrückliches ``''``
    leert weiterhin, und genau das stand im Aufrufer."""
    quelle = _quelle_ohne_kommentare("server/api/cra/__init__.py")
    assert "massnahme=''" not in quelle.replace(" ", ""), (
        "accept_suggestion leert die Maßnahme weiter hart")


# ══════════════════════════════════════════════════════════════════════════════
# #2092 — der Autodetect leerte ein handgepflegtes Threat-Model
# ══════════════════════════════════════════════════════════════════════════════

def test_threatmodel_inhalte_ueberleben_ein_teil_update():
    from cra.db import load_threatmodel, save_threatmodel

    save_threatmodel(CRA_DB, PROJ, {
        "framework": "STRIDE", "framework_source": "risk_link", "scope": "",
        "assets": [{"name": "DB"}], "threats": [{"id": "T1"}],
        "mitigations": [{"id": "M1"}],
        "diagram_url": "https://example.test/tm.png", "notizen": "handgepflegt"})

    # Wie der Autodetect schickt: Kopffelder, keine Inhalte.
    save_threatmodel(CRA_DB, PROJ, {
        "framework": "STRIDE", "scope": "Threat-Model (auto-detected)",
        "diagram_url": "https://github.test/x", "notizen": "Auto-erkannt"})

    tm = load_threatmodel(CRA_DB, PROJ) or {}
    assert tm.get("assets"), "Assets wurden geleert"
    assert tm.get("threats"), "Bedrohungen wurden geleert"
    assert tm.get("mitigations"), "Maßnahmen wurden geleert"
    assert tm.get("framework_source") == "risk_link", (
        "framework_source fiel auf 'manual' zurück und behauptet damit eine "
        "manuelle Abweichung, die niemand getroffen hat (#938)")


def test_autodetect_schickt_keine_leeren_listen_mehr():
    """Die zweite Hälfte: Ein ausdrückliches ``[]`` leert auch mit Teil-Update."""
    baum = ast.parse(Path("cra/pflicht_doku_autodetect.py").read_text(encoding="utf-8"))
    fn = next(k for k in ast.walk(baum)
              if isinstance(k, ast.FunctionDef) and k.name == "detect_threatmodel")
    schluessel: set[str] = set()
    for knoten in ast.walk(fn):
        if isinstance(knoten, ast.Dict):
            schluessel |= {k.value for k in knoten.keys
                           if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert not {"assets", "threats", "mitigations"} & schluessel, (
        "der Autodetect nennt die Inhalts-Register weiter — ein ausdrückliches "
        "[] leert sie auch über das Teil-Update hinweg")


def test_die_leer_pruefung_betrachtet_auch_die_inhalte():
    """Zweiter Boden: Der Autodetect soll eine gepflegte Akte nicht anfassen."""
    quelle = _quelle_ohne_kommentare("cra/pflicht_doku_autodetect.py")
    assert "hat_inhalt" in quelle, (
        "die Leer-Prüfung sieht weiter nur framework/scope, geschrieben werden "
        "acht Spalten")


# ══════════════════════════════════════════════════════════════════════════════
# #2063 — toter Store-Zustand
# ══════════════════════════════════════════════════════════════════════════════

def test_kein_zweiter_validator_stand_im_store():
    """Zwei Kopien derselben Antwort, von denen eine niemand ansieht."""
    quelle = _quelle_ohne_kommentare("frontend/src/stores/gerichtsgutachten.ts")
    for name in ("validatorErrors", "validatorWarnings"):
        assert name not in quelle, (
            f"{name} wird weiter geschrieben und exportiert, aber von keiner "
            "Maske gelesen")


def test_der_validator_gibt_seine_antwort_weiter_zurueck():
    """Die Reparatur darf die Funktion nicht entkernen."""
    quelle = _quelle_ohne_kommentare("frontend/src/stores/gerichtsgutachten.ts")
    assert "runSchlussValidator" in quelle
    assert "schluss-validator" in quelle
