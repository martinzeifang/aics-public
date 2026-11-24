"""Handgeführte Listen über Zeichenketten, die anderswo entstehen — #2075/#2088/#2090/#2094/#2029.

Die Fehlerklasse aus #1731/#1735 in ihrer leisesten Form (#1870): Nichts
schlägt fehl, die Liste wächst nur nicht mit. Vier Fälle, und in jedem fehlte
etwas, das längst vorhanden war.

Die Reparatur ist überall dieselbe Richtung: **ableiten statt aufzählen**. Wo
das nicht geht, weil die Liste mehr trägt als die Zuordnung (Label, Route,
Argumente), hält dieser Test beide Seiten gegeneinander.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.i18n_text import python_programm


# ══════════════════════════════════════════════════════════════════════════════
# #2075 — die vierte Art der Release-Checkliste
# ══════════════════════════════════════════════════════════════════════════════

def test_arten_sind_aus_dem_literal_abgeleitet():
    import cra.release_checkliste as rc

    assert set(rc.ARTEN) == {i.art for i in rc.KATALOG}, (
        "Literal und Katalog sind uneins")
    assert "neubewertung" in rc.ARTEN


def test_der_vorgangsbericht_iteriert_alle_arten():
    """Drei von vier wurden iteriert. Die vier ``neubewertung``-Punkte waren
    damit **erfüllt unsichtbar** und **offen sichtbar** (über ``offene_punkte``)
    — ein Release als wesentliche Änderung mit vier abgearbeiteten
    Neubewertungen zeigte davon im Dokument nichts, obwohl
    ``BEGRUENDUNG_PFLICHT`` sie ausdrücklich einschließt (#1744)."""
    programm = python_programm("cra/release_bericht.py")
    assert 'for art in (\'gerechnet\', \'entscheidung\', \'gleichbleibend\')' \
        not in programm
    assert "for art in rc.ARTEN" in programm


def test_jede_art_hat_punkte():
    """Sonst wäre ein Abschnitt im Bericht leer — und die Ableitung nutzlos."""
    import cra.release_checkliste as rc

    for art in rc.ARTEN:
        assert [i for i in rc.KATALOG if i.art == art], f"{art} ohne Punkte"


# ══════════════════════════════════════════════════════════════════════════════
# #2088 — die Issue-Übersicht meldete 0 von 117
# ══════════════════════════════════════════════════════════════════════════════

def test_die_uebersicht_kennt_alle_sechs_module():
    """Die Fabrik (#1846) bedient zehn Objektarten in sechs Modulen; DSGVO und
    WiBA fehlten ganz, obwohl die Oberfläche „alle Compliance-Module"
    verspricht."""
    from server.api.issues import MODULE_DBS

    assert {"cra", "nis2", "aiact", "dsgvo", "wiba", "risikobewertung"} \
        <= set(MODULE_DBS), f"es fehlen Module: {sorted(MODULE_DBS)}"


def test_kein_toter_pfad_guard_mehr():
    """``if not db_path.exists(): continue`` sprang unter Postgres **immer** an
    — es gibt keine ``.sqlite``-Dateien (Schema-Mapping seit Migration #15).
    Dieselben toten Guards hat #1511 an anderen Stellen entfernt."""
    programm = python_programm("server/api/issues.py")
    assert "db_path.exists()" not in programm, (
        "der Guard ist zurück — und damit meldet die Übersicht wieder 0")


def test_die_modulliste_ist_abgeleitet():
    from shared.firmen_link import MODULE_PROJECT_TABLES

    from server.api.issues import MODULE_DBS

    for pfad in MODULE_DBS.values():
        assert pfad.name in MODULE_PROJECT_TABLES, (
            f"{pfad.name} steht nicht in MODULE_PROJECT_TABLES")


# ══════════════════════════════════════════════════════════════════════════════
# #2090 — das Firmen-Dashboard kannte Compliance-Audit nicht
# ══════════════════════════════════════════════════════════════════════════════

def test_das_dashboard_kennt_compliance_audit():
    """Grundpreis-Modul seit #1713, Schalter Default an, eigener Reifegrad,
    eigenes Berichts-Center — und im Reiter „Dashboard" keine Kachel, kein
    Umsetzungsgrad, keine Berichte."""
    from firmen.uebersicht import MODULE

    assert "compliance_audit" in MODULE
    label, tabelle, spalte, route = MODULE["compliance_audit"]
    assert tabelle == "gutachten_projects", "Tabellenname ist historisch (#1713)"
    assert route == "/compliance-audit"


def test_dashboard_und_lizenzschalter_sind_sich_einig():
    """Die Gegenseite: Wer einen Schalter hat, gehört ins Dashboard.

    ``gutachten`` ist bewusst **nicht** dabei: Es ist ``EXPLICIT_MODULES`` und
    kein Grundpreis-Modul, und ein Gerichtsgutachten ist kein Umsetzungsgrad —
    es gehört nicht in eine Reifegrad-Kachel. Diese Ausnahme ist benannt, damit
    sie eine Entscheidung bleibt und nicht wieder ein Versehen wird.
    """
    from firmen.uebersicht import MODULE
    from shared.licensing.modules import FIRMEN_MODULE_COLUMNS

    # Der #1169-Alias: `FIRMEN_MODULE_COLUMNS` schreibt `aiact`,
    # `firmen/uebersicht.MODULE` `ai_act`. Beim ersten Anlauf meldete dieser
    # Test deshalb `aiact` als fehlend — ein Fund, der keiner ist, und genau
    # die Art Fehlalarm, nach der man die Ausgabe eines Prüfers nicht mehr
    # liest (#1805/#1834).
    ALIAS = {"aiact": "ai_act"}
    schalter = {ALIAS.get(k, k) for k in FIRMEN_MODULE_COLUMNS}
    fehlen = schalter - set(MODULE) - {"gutachten", "firmen", "pentest"}
    assert not fehlen, (
        f"Module mit Firmen-Schalter, aber ohne Dashboard-Kachel: {sorted(fehlen)}")


def test_jede_dashboard_tabelle_ist_aufloesbar():
    from firmen.uebersicht import MODULE
    from shared.firmen_link import MODULE_PROJECT_TABLES

    bekannte = {t for t, _ in MODULE_PROJECT_TABLES.values()}
    for key, (_label, tabelle, _spalte, _route) in MODULE.items():
        assert tabelle in bekannte, (
            f"{key}: Tabelle {tabelle!r} kennt MODULE_PROJECT_TABLES nicht — "
            "dann ist die firmen_id dort nicht auflösbar")


# ══════════════════════════════════════════════════════════════════════════════
# #2094 — der Warmup deckte 12 von 54 Modulen
# ══════════════════════════════════════════════════════════════════════════════

WICHTIGE_SCHEMATA = [
    ("pentest.db", "das ganze Pentest-Modul (#1581)"),
    ("compliance_audit.db", "das ganze Audit-Modul (#1713)"),
    ("shared.issue_links", "jede Issue-Handlung in sechs Modulen (#1846)"),
    ("shared.ki_herkunft", "jede KI-Bewertung (#1765)"),
    ("shared.prompt_hinweise", "jeder Prompt (#1835)"),
    ("shared.risk_req_links", "Risiko↔Anforderung in vier Modulen (#1564)"),
]


@pytest.mark.parametrize("modul,warum", WICHTIGE_SCHEMATA)
def test_die_heissen_schemata_sind_vorgewaermt(modul, warum):
    from shared.warmup import _PLAN, _entdeckte_schemata

    abgedeckt = {m for m, _f, _a in _PLAN} | {m for m, _f, _a in _entdeckte_schemata()}
    assert modul in abgedeckt, f"{modul} ist nicht vorgewärmt — daran hängt {warum}"


def test_der_plan_wird_aus_dem_baum_abgeleitet():
    """Eine handgeführte Positivliste über Module wächst nicht mit: Seit #1471
    sind 40 Module dazugekommen und keines in die Liste."""
    from shared.warmup import _PLAN, _entdeckte_schemata

    entdeckt = _entdeckte_schemata()
    assert len(entdeckt) > 20, (
        f"die Entdeckung findet nur {len(entdeckt)} Module — greift sie noch?")
    # Keine Dubletten zwischen Hand und Entdeckung.
    doppelt = {(m, f) for m, f, _ in _PLAN} & {(m, f) for m, f, _ in entdeckt}
    assert not doppelt, f"doppelt gewärmt: {sorted(doppelt)}"


def test_nur_argumentlose_funktionen_werden_entdeckt():
    """Den Pfad zu **raten** wäre schlimmer als nicht zu wärmen — ein falscher
    Pfad legt ein Schema am falschen Ort an."""
    import importlib
    import inspect

    from shared.warmup import _entdeckte_schemata

    for modpath, fnname, args in _entdeckte_schemata():
        assert args == (), f"{modpath}.{fnname} bekommt geratene Argumente"
        fn = getattr(importlib.import_module(modpath), fnname)
        pflicht = [p for p in inspect.signature(fn).parameters.values()
                   if p.default is inspect.Parameter.empty
                   and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        assert not pflicht, f"{modpath}.{fnname} braucht {pflicht}"


def test_der_warmup_bleibt_schnell():
    """Ein Warmup, der den Start verlangsamt, verschiebt das Problem nur.

    Gemessen nach der Umstellung: 66 Module in 0,71 s (zweiter Lauf 0,10 s,
    #1396-Cache). Die Grenze hier ist großzügig — sie soll einen Ausrutscher
    fangen, nicht eine Zahl festschreiben.
    """
    import time

    from shared.warmup import warm_schemas

    start = time.monotonic()
    erg = warm_schemas()
    dauer = time.monotonic() - start
    assert erg["ok"] > 40, f"nur {erg['ok']} Schemata gewärmt"
    assert dauer < 20.0, f"Warmup brauchte {dauer:.1f}s"


# ══════════════════════════════════════════════════════════════════════════════
# #2029 — „noch nichts erfasst" ist kein Fehler
# ══════════════════════════════════════════════════════════════════════════════

def test_nicht_gesetzte_aufbewahrungsfrist_ist_kein_404():
    """Der Normalzustand jedes neu angelegten Gutachtens — und der einzige
    HTTP-Fehler im Screenshot-Durchlauf über 91 Bilder. Dieselbe Klasse wie
    #1995, mit umgekehrtem Vorzeichen."""
    programm = python_programm("server/api/gutachten.py")
    assert "jsonify({}), 404" not in programm, (
        "die leere Antwort ist weiter ein Fehler")
    assert "jsonify(d or {}), 200" in programm
