"""Die aktuelle Version folgt den Releases (#1820).

**Der Befund aus dem Betrieb:** Im Tab „✅ Konformität" stand „Aktuelle
Version: 7.3", während Release 8.0.1 längst freigegeben war.

**Die Ursache:** Zwei Stellen beantworten dieselbe Frage.
``cra_release.aktuelle_version`` schreibt nur ``substantial_modification`` —
der Weg „wesentliche Änderung erfassen". Wer seine Releases über den
Releases-Tab führt, also auf dem normalen Weg, fasst das Feld nie an. Es bleibt
auf dem Stand der letzten erklärten wesentlichen Änderung stehen und wird
trotzdem als „aktuell" ausgegeben.

Dieselbe Fehlerklasse wie #1805 — zwei Zeilen zum selben Sachverhalt, eine
gepflegt, die andere angezeigt. Hier fällt sie später auf, weil nichts
fehlschlägt: Es steht bloß eine falsche Zahl an der Stelle, an der ein Prüfer
sie liest.
"""
from __future__ import annotations

import pytest

from cra import release_db as rdb

PROJ = 'pytest-version-1820'


def _release(db, version: str, status: str) -> None:
    """Einen Release-Vorgang mit Freigabezustand anlegen.

    Der Zustand lässt sich nicht über ``save_konformitaet`` setzen — er gehört
    der Zustandsmaschine (``einreichen``/``freigeben``), und die verlangt eine
    grüne Ampel. Für die Frage, welche Version als aktuell gilt, ist der ganze
    Vorgang nicht nötig; gesetzt wird deshalb direkt, wie in
    ``test_doc_vorlage_1753.py`` bei Altbestand.
    """
    from shared import db as _sdb
    from cra import konformitaet_db as kdb

    kdb.save_konformitaet(db, PROJ, {'release_version': version})
    con = _sdb.connect(db)
    try:
        con.execute(
            "UPDATE cra_konformitaet SET freigabe_status=? "
            "WHERE projekt_name=? AND release_version=?",
            (status, PROJ, version))
        con.commit()
    finally:
        con.close()


# ── Sortierung ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kleiner,groesser", [
    ("7.3", "8.0.1"),       # der gemeldete Fall
    ("7.9", "7.10"),        # als Zeichenkette wäre das Verhältnis umgekehrt
    ("1.0", "1.0.1"),
    ("v2.0", "10.0"),
    ("8.0.1", "8.0.2"),
])
def test_versionen_werden_nach_zahlen_sortiert(kleiner, groesser):
    assert rdb.version_schluessel(kleiner) < rdb.version_schluessel(groesser)


def test_vorabfassung_steht_vor_der_fertigen():
    """#2078: Hier stand ``version_schluessel("1.0") < …("1.0-rc1")``.

    Das war die **falsche** Richtung und widersprach
    ``shared/deploy/kanal.parse_version`` (#1908), die begründet, dass
    ``8.3.0-beta.1`` nach Semver **kleiner** ist als ``8.3.0``. Zwei
    Vergleichsfunktionen für dieselbe Frage mit entgegengesetztem Ergebnis —
    und seit #1908 ist ``beta`` ein offizieller Kanal, der Fall also erreichbar.

    Die Folge war nicht theoretisch: ``abgeleitete_version`` nahm über ``max()``
    die Vorabfassung als aktuelle Produktversion, und ``doc_vorschlag.charge``
    belegte damit **Anhang V Nr. 1** der EU-Konformitätserklärung vor — eine
    falsche Bezeichnung des in Verkehr gebrachten Standes in einem
    unterschriebenen Dokument.

    Die zweite Zusage von damals bleibt: Sortierbar muss **jede** Angabe sein,
    sonst verschwindet eine aus dem Vergleich. Geprüft wird sie jetzt als
    Verhalten statt über die innere Form des Schlüssels.
    """
    assert rdb.version_schluessel("1.0-rc1") < rdb.version_schluessel("1.0")
    assert rdb.version_schluessel("8.3.0-beta.1") < rdb.version_schluessel("8.3.0")
    assert max(["8.3.0", "8.3.0-beta.1"], key=rdb.version_schluessel) == "8.3.0"

    # Eine leere oder unlesbare Angabe verschwindet nicht, sie sortiert unten.
    assert rdb.version_schluessel("") < rdb.version_schluessel("0.1")
    assert rdb.version_schluessel("Stand 3") < rdb.version_schluessel("1.0")


def test_beide_ordnungen_sind_sich_einig():
    """Der Wächter gegen den Rückfall: Kanal und Release-Ordnung rechnen gleich."""
    from shared.deploy.kanal import parse_version

    for kleiner, groesser in (("8.3.0-beta.1", "8.3.0"), ("1.0.0", "1.0.1"),
                              ("2.0.0", "10.0.0")):
        a, b = parse_version(kleiner), parse_version(groesser)
        assert a is not None and b is not None
        assert (a < b) == (rdb.version_schluessel(kleiner)
                           < rdb.version_schluessel(groesser)), (
            f"{kleiner} vs {groesser}: die beiden Ordnungen sind uneins")


# ── Die Ableitung ────────────────────────────────────────────────────────────

def test_ohne_releases_gilt_der_gespeicherte_wert(tmp_path):
    """Installationen ohne Release-Vorgänge verhalten sich unverändert."""
    db = tmp_path / 'cra.sqlite'
    rdb.ensure_table(db)
    assert rdb.abgeleitete_version(db, PROJ, '7.3') == '7.3'


def test_freigegebenes_release_setzt_die_version(tmp_path):
    """Der gemeldete Fall: gespeichert 7.3, freigegeben 8.0.1 → 8.0.1."""
    db = tmp_path / 'cra.sqlite'
    rdb.save_release(db, PROJ, {'aktuelle_version': '7.3'})
    _release(db, '8.0.1', 'freigegeben')

    assert rdb.abgeleitete_version(db, PROJ, '7.3') == '8.0.1'
    rec = rdb.get_release(db, PROJ)
    assert rec['aktuelle_version'] == '8.0.1'
    # Woher die Zahl kommt, bleibt nachvollziehbar.
    assert rec['aktuelle_version_gespeichert'] == '7.3'


def test_entwurf_zaehlt_nicht(tmp_path):
    """Ein Entwurf ist nicht in Verkehr — er darf die Produktversion nicht
    vorziehen. Sonst stünde im Nachweis eine Version, die es nicht gibt."""
    db = tmp_path / 'cra.sqlite'
    rdb.save_release(db, PROJ, {'aktuelle_version': '7.3'})
    _release(db, '9.0.0', 'entwurf')
    assert rdb.abgeleitete_version(db, PROJ, '7.3') == '7.3'


def test_hoechste_version_gewinnt_nicht_die_juengste(tmp_path):
    """Ein Wartungsstand 7.4.9, der nach 8.0.1 erscheint, macht nicht 7.4.9
    zur aktuellen Version des Produkts."""
    db = tmp_path / 'cra.sqlite'
    rdb.save_release(db, PROJ, {'aktuelle_version': '1.0'})
    _release(db, '8.0.1', 'veroeffentlicht')
    _release(db, '7.4.9', 'freigegeben')
    assert rdb.abgeleitete_version(db, PROJ, '1.0') == '8.0.1'


# ── Keine Nebenwirkung beim Speichern ────────────────────────────────────────

def test_speichern_ohne_version_behaelt_sie(tmp_path):
    """Der Reassess-Haken im Frontend schickt die Version nicht mit.

    Vorher setzte jedes Speichern ohne das Feld auf ``v1.0`` zurück —
    dieselbe Klasse wie ``artefakt`` in #1771 und ``meta_json`` in #1540.
    """
    db = tmp_path / 'cra.sqlite'
    rdb.save_release(db, PROJ, {'aktuelle_version': '7.3'})
    rdb.save_release(db, PROJ, {'reassess': {'doc': 'erledigt'}})
    rec = rdb.get_release(db, PROJ)
    assert rec['aktuelle_version_gespeichert'] == '7.3'
    assert rec['reassess'] == {'doc': 'erledigt'}


def test_wesentliche_aenderung_friert_den_echten_stand_ein(tmp_path):
    """Eingefroren wird, was tatsächlich im Feld ist — nicht der stehen
    gebliebene Wert. Sonst trüge der Snapshot eine Version, die das Produkt
    längst hinter sich hat."""
    db = tmp_path / 'cra.sqlite'
    rdb.save_release(db, PROJ, {'aktuelle_version': '7.3'})
    _release(db, '8.0.1', 'veroeffentlicht')
    res = rdb.substantial_modification(db, PROJ, neue_version='9.0',
                                       grund='Neue Funktion mit Netzzugang')
    assert res['eingefrorene_version'] == '8.0.1'


def test_frontend_schickt_die_abgeleitete_version_nicht_zurueck():
    """Ein Reassess-Haken darf die Tabelle nicht mit einem Anzeigewert füllen."""
    from pathlib import Path

    store = Path('frontend/src/stores/craRelease.ts').read_text(encoding='utf-8')
    stelle = store[store.index('async function setReassess'):][:900]
    assert 'aktuelle_version' not in stelle, \
        'Die abgeleitete Version gehoert nicht in den Speicheraufruf'
