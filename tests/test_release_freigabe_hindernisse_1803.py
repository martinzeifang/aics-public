"""Was die Freigabe verhindert, hält schon die Einreichung auf (#1803).

Aus dem Betrieb: „Warum kann ich Release 8.0.1 nicht freigeben?" Der Vorgang
stand auf ``in_pruefung``, und beide Sperren griffen zu Recht — der
Bewertungsweg war nicht als abgeschlossen vermerkt, und eingereicht hatte
dieselbe Person. Falsch war nicht die Regel, sondern **wann** die Anwendung sie
nennt: erst nach einem Klick auf einen Knopf, der vollmundig „Release
freigeben" heißt, und mit einem Haken, der in einem anderen Tab sitzt.

Zwei Änderungen, eine Haltung: Eine Bedingung, die eine spätere Handlung
**ausnahmslos** verhindert, gehört an die frühere Handlung.

* ``einreichen`` lehnt einen Vorgang ohne abgeschlossenen Bewertungsweg ab.
  Sonst wartet eine Prüfperson auf etwas, das sie nur zurückweisen kann, und
  der Einreicher erfährt den Grund über den Umweg einer Zurückweisung.
* Die **Ampel** bleibt davon unberührt: Ein rotes Gate darf eingereicht
  werden — darüber soll die Prüfung ja gerade entscheiden (die Freigabe
  verlangt dafür ``confirm_rot``).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cra import db as cdb
from cra import konformitaet_db as kdb

CRA_DB = Path("data/db/cra.sqlite")
PROJ = "pytest-freigabe-1803"
VER = "1.2.3"
ENTWICKLER = "11111111-1111-1111-1111-111111111111"
PRUEFER = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def vorgang():
    cdb.ensure_db(CRA_DB)
    cdb.delete_projekt(CRA_DB, PROJ)
    cdb.save_projekt(CRA_DB, PROJ, unternehmen="pytest-firma-1803", produkt="Testprodukt")
    kdb.save_konformitaet(CRA_DB, PROJ, {"release_version": VER})
    yield PROJ
    cdb.delete_projekt(CRA_DB, PROJ)


def _bewertungsweg_abschliessen(projekt: str) -> None:
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER,
                                            "bewertung_abgeschlossen": True})


# ── Die Sperre sitzt jetzt vorn ──────────────────────────────────────────────

def test_einreichen_ohne_abgeschlossenen_bewertungsweg(vorgang):
    """Vorher ging das durch — und scheiterte erst bei der Freigabe."""
    with pytest.raises(ValueError) as e:
        kdb.einreichen(CRA_DB, vorgang, VER, von=ENTWICKLER)
    text = str(e.value)
    assert "Bewertungsweg" in text
    assert "Konformität" in text, "Die Meldung muss sagen, wo der Haken sitzt"
    # Nichts geschrieben: Der Vorgang bleibt im Entwurf.
    assert (kdb.get_konformitaet(CRA_DB, vorgang, VER) or {})["freigabe_status"] == "entwurf"


def test_mit_abgeschlossenem_bewertungsweg_geht_das_einreichen(vorgang):
    _bewertungsweg_abschliessen(vorgang)
    rec = kdb.einreichen(CRA_DB, vorgang, VER, von=ENTWICKLER)
    assert rec["freigabe_status"] == "in_pruefung"
    assert rec["erstellt_von"] == ENTWICKLER


def test_rote_ampel_darf_eingereicht_werden(vorgang):
    """Die Abgrenzung, die diese Änderung tragbar macht: Gesperrt ist nur, was
    die Freigabe **ausnahmslos** verhindert — nicht der Prüfgegenstand."""
    _bewertungsweg_abschliessen(vorgang)
    rec = kdb.einreichen(CRA_DB, vorgang, VER, von=ENTWICKLER,
                         gate={"ampel": "rot", "offene_punkte": [{"typ": "advisory"}]})
    assert rec["freigabe_status"] == "in_pruefung"
    assert (rec.get("gate") or {}).get("ampel") == "rot"


# ── Die Freigabe bleibt fail-closed ──────────────────────────────────────────

def test_vier_augen_gilt_weiterhin(vorgang):
    _bewertungsweg_abschliessen(vorgang)
    kdb.einreichen(CRA_DB, vorgang, VER, von=ENTWICKLER)
    from shared.vier_augen import VierAugenVerletzt

    with pytest.raises(VierAugenVerletzt) as e:
        kdb.freigeben(CRA_DB, vorgang, VER, von=ENTWICKLER)
    assert "zweite Person" in str(e.value)


def test_zweite_person_gibt_frei(vorgang):
    _bewertungsweg_abschliessen(vorgang)
    kdb.einreichen(CRA_DB, vorgang, VER, von=ENTWICKLER)
    rec = kdb.freigeben(CRA_DB, vorgang, VER, von=PRUEFER)
    assert rec["freigabe_status"] == "freigegeben"
    assert rec["freigegeben_von"] == PRUEFER


def test_freigabe_prueft_den_bewertungsweg_weiterhin_selbst(vorgang):
    """Der Vorzug beim Einreichen ersetzt die Prüfung nicht: Ein Altvorgang
    steht schon in der Prüfung, und der Haken kann dazwischen fallen."""
    _bewertungsweg_abschliessen(vorgang)
    kdb.einreichen(CRA_DB, vorgang, VER, von=ENTWICKLER)
    kdb.save_konformitaet(CRA_DB, vorgang, {"release_version": VER,
                                            "bewertung_abgeschlossen": False})
    with pytest.raises(ValueError) as e:
        kdb.freigeben(CRA_DB, vorgang, VER, von=PRUEFER)
    assert "Bewertungsweg" in str(e.value)


# ── Der Produkt-Datensatz (Phase 1) bleibt unberührt ─────────────────────────

def test_produkt_datensatz_kennt_kein_einreichen(vorgang):
    """Der Datensatz ohne Version ist kein Release (#1743) — er behält den
    Phase-1-Ablauf und darf von dieser Änderung nichts merken."""
    with pytest.raises(ValueError) as e:
        kdb.einreichen(CRA_DB, vorgang, "", von=ENTWICKLER)
    assert "Release-Version" in str(e.value)


# ── Die Anzeige im Panel nennt beide Gründe ──────────────────────────────────

def test_panel_weist_beide_hindernisse_aus():
    """Die Liste ist reine Anzeige — entschieden wird serverseitig. Sie muss
    aber dieselben zwei Gründe kennen, sonst steht der Anwender wieder vor
    einem Knopf, der nichts tut."""
    quelle = Path("frontend/src/views/cra/ReleasesPanel.vue").read_text(encoding="utf-8")
    assert "freigabeHindernisse" in quelle
    assert "einreichHindernisse" in quelle
    assert "bewertung_abgeschlossen" in quelle
    assert "Vier-Augen" in quelle
    # Der Sprung dorthin, wo sich der Haken setzen lässt.
    assert "ziel: 'konformitaet'" in quelle
    # Beide Knöpfe sind gesperrt, solange ein Hindernis besteht.
    assert "einreichHindernisse.length > 0" in quelle
    assert "freigabeHindernisse.length > 0" in quelle
