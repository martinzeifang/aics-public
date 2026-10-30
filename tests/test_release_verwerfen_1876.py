"""#1876: Ein nicht veröffentlichter Release-Vorgang lässt sich verwerfen.

Meldung aus dem Betrieb: „Ich muss bei CRA ein nicht veröffentlichtes Release
auch löschen können bzw. archivieren, wenn ich es doch nicht veröffentlichen
will."

Die Zustandsmaschine aus #1743 kannte `entwurf → in_pruefung → freigegeben →
veroeffentlicht` (plus `zurueckgewiesen`) — und **keinen Weg heraus**. Ein
Vorgang aus einem Vertipper stand dauerhaft in der Liste, zählte in der
Quer-Sicht mit und erschien im Vorgangsbericht je Mandant (#1749).

WARUM VERWERFEN UND NICHT LÖSCHEN
Dies ist ein Nachweiswerkzeug. Dass eine Version erwogen und dann nicht in
Verkehr gebracht wurde, ist selbst eine Aussage über das Produkt. Hart
gelöscht wird nur, woran nachweislich nichts hängt.
"""
from __future__ import annotations

import pytest

from cra import konformitaet_db as kdb

PROJEKT = "Verwerfen-Pruefung"
GRUND = "Version wurde durch 8.2.2 ersetzt, nie ausgeliefert."


@pytest.fixture()
def db(tmp_path):
    pfad = tmp_path / "cra.sqlite"
    kdb.ensure_table(pfad)
    return pfad


def _anlegen(db, version: str) -> dict:
    return kdb.save_konformitaet(db, PROJEKT, {"release_version": version})


# ── Der Weg heraus ──────────────────────────────────────────────────────────

def test_entwurf_laesst_sich_verwerfen(db):
    _anlegen(db, "8.2.1")
    rec = kdb.verwerfen(db, PROJEKT, "8.2.1", von="martin", grund=GRUND)
    assert rec["freigabe_status"] == "verworfen"
    assert rec["verworfen_grund"] == GRUND
    assert rec["verworfen_von"] == "martin"
    assert rec["verworfen_am"], "Zeitpunkt muss gestempelt sein"


def test_begruendung_ist_pflicht(db):
    _anlegen(db, "8.2.1")
    with pytest.raises(ValueError, match="Begründung"):
        kdb.verwerfen(db, PROJEKT, "8.2.1", von="martin", grund="zu kurz")


def test_veroeffentlichtes_release_bleibt(db):
    """Ein veröffentlichtes Release ist in Verkehr — seine Akte bleibt
    (Art. 13 Abs. 9 und 13)."""
    _anlegen(db, "8.2.0")
    # `save_konformitaet` nimmt den Status bewusst NICHT an — er gehoert den
    # Uebergangsfunktionen (#1743). Im Test deshalb direkt gesetzt.
    kdb._setze(db, PROJEKT, "8.2.0", "freigabe_status='veroeffentlicht'", ())
    with pytest.raises(ValueError, match="in Verkehr"):
        kdb.verwerfen(db, PROJEKT, "8.2.0", von="martin", grund=GRUND)


def test_produkt_datensatz_ist_tabu(db):
    """Die Zeile mit leerer Version ist der PRODUKT-Datensatz (#1805).

    Sie zu verwerfen nähme dem Produkt seine Konformitätsbewertung, und jedes
    Release erbte anschließend ins Leere.
    """
    kdb.save_konformitaet(db, PROJEKT, {"release_version": ""})
    with pytest.raises(ValueError, match="Produkt-Datensatz"):
        kdb.verwerfen(db, PROJEKT, "", von="martin", grund=GRUND)


def test_verwerfen_ist_idempotent(db):
    _anlegen(db, "8.2.1")
    kdb.verwerfen(db, PROJEKT, "8.2.1", von="m", grund=GRUND)
    # Ein zweiter Klick darf nicht in einen Fehler laufen.
    rec = kdb.verwerfen(db, PROJEKT, "8.2.1", von="m", grund=GRUND)
    assert rec["freigabe_status"] == "verworfen"


def test_wiederaufnehmen_holt_zurueck_und_behaelt_die_spur(db):
    """Ein Irrtum beim Verwerfen soll nicht teurer sein als beim Anlegen —
    aber die Begründung bleibt stehen."""
    _anlegen(db, "8.2.1")
    kdb.verwerfen(db, PROJEKT, "8.2.1", von="m", grund=GRUND)
    rec = kdb.wiederaufnehmen(db, PROJEKT, "8.2.1", von="m")
    assert rec["freigabe_status"] == "entwurf"
    assert rec["verworfen_grund"] == GRUND, (
        "Die Spur des Verwerfens darf nicht still verschwinden")


def test_wiederaufnehmen_nur_aus_verworfen(db):
    _anlegen(db, "8.2.1")
    with pytest.raises(ValueError, match="verworfener"):
        kdb.wiederaufnehmen(db, PROJEKT, "8.2.1", von="m")


# ── Hartes Löschen nur beim Vertipper ───────────────────────────────────────

def test_unberuehrter_entwurf_ist_loeschbar(db):
    _anlegen(db, "8.2.1")
    assert kdb.unberuehrt(db, PROJEKT, "8.2.1") is True
    kdb.loeschen(db, PROJEKT, "8.2.1")
    assert kdb.get_konformitaet(db, PROJEKT, "8.2.1") in (None, {}) or \
        not kdb.get_konformitaet(db, PROJEKT, "8.2.1").get("release_version")


def test_vorgang_mit_angaben_ist_nicht_loeschbar(db):
    """Woran etwas hängt, wird verworfen — nicht entfernt."""
    _anlegen(db, "8.2.1")
    # „art_konsistent" ist GERECHNET und laesst sich zu Recht nicht von Hand
    # setzen (#1744). Hier ein Entscheidungs-Punkt mit Begruendungspflicht.
    kdb.set_release_checkliste(db, PROJEKT, "8.2.1", "advisory_veroeffentlicht",
                               status="erledigt",
                               begruendung="Advisory GHSA-x veroeffentlicht",
                               von="m")
    assert kdb.unberuehrt(db, PROJEKT, "8.2.1") is False
    with pytest.raises(ValueError, match="verworfen"):
        kdb.loeschen(db, PROJEKT, "8.2.1")


def test_nicht_entwurf_ist_nicht_loeschbar(db):
    _anlegen(db, "8.2.1")
    kdb._setze(db, PROJEKT, "8.2.1", "freigabe_status='in_pruefung'", ())
    assert kdb.unberuehrt(db, PROJEKT, "8.2.1") is False


# ── Der neue Zustand ist überall bekannt ────────────────────────────────────

def test_zustand_ist_im_katalog():
    assert "verworfen" in kdb.FREIGABE_STATUS
    assert "veroeffentlicht" not in kdb.VERWERFBAR_AUS, (
        "Ein veröffentlichtes Release darf nie verwerfbar sein")
    assert set(kdb.VERWERFBAR_AUS) <= set(kdb.FREIGABE_STATUS)
