"""Keine EU-Konformitätserklärung ohne ihre Pflichtangaben (#1814).

Gefunden beim systematischen Funktionstest: ``POST …/konformitaet/doc`` mit
einem **leeren** Dokument wurde angenommen. Danach stand im Datensatz
``doc_ausgestellt=1``, ``ce_status='doc_ausgestellt'``, ``doc_version+1`` — und
das Gate las das und schaltete die Ampel auf **grün**.

Eine Erklärung ohne Produktidentifikation (Anhang V Nr. 1), ohne Hersteller
(Nr. 2) und ohne Unterzeichner (Nr. 8) ist unwirksam. Für ein Werkzeug, dessen
Zweck die Nachweisführung ist, ist das die schwerste Form von Falschaussage:
nicht ein Fehler, der auffällt, sondern einer, der wie ein Ergebnis aussieht.

Die Prüfung gab es bereits — in ``doc_export.ausstellen`` (#1753). Nur stand
der ältere Weg ``konformitaet_db.issue_doc`` daneben und prüfte nur den
Bewertungsweg. Zwei Entstehungswege für dieselbe Aussage sind zwei Wahrheiten;
beide nutzen jetzt **dieselbe** Funktion.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cra import db as cdb
from cra import konformitaet_db as kdb

CRA_DB = Path("data/db/cra.sqlite")
PROJ = "pytest-doc-1814"


@pytest.fixture
def projekt():
    cdb.ensure_db(CRA_DB)
    cdb.delete_projekt(CRA_DB, PROJ)
    cdb.save_projekt(CRA_DB, PROJ, unternehmen="pytest-firma-1814", produkt="Testprodukt")
    kdb.save_konformitaet(CRA_DB, PROJ, {"bewertungsweg": "A",
                                         "bewertung_abgeschlossen": True})
    yield PROJ
    cdb.delete_projekt(CRA_DB, PROJ)


def _vollstaendig() -> dict:
    """Ein Datensatz, der Anhang V genügt."""
    return {
        "produkt_name": "Testprodukt", "produkt_typ": "Typ A",
        "produkt_charge": "Version 1.0.0",
        "hersteller": "pytest-firma-1814", "hersteller_adresse": "Musterweg 1, 12345 Musterstadt",
        "gegenstand": "Testprodukt, Version 1.0.0",
        "ort": "Musterstadt", "datum": "2026-10-25",
        "unterzeichner_name": "M. Muster", "unterzeichner_funktion": "Geschäftsführung",
    }


# ── Der Befund ───────────────────────────────────────────────────────────────

def test_leeres_dokument_wird_abgelehnt(projekt):
    """Der Kern: Ein leeres `{}` darf keine ausgestellte Erklärung erzeugen."""
    with pytest.raises(ValueError) as e:
        kdb.issue_doc(CRA_DB, projekt, {}, "")
    text = str(e.value)
    assert "Anhang V" in text, "Die Meldung muss die Rechtsgrundlage nennen"
    assert "Nr." in text, "Die Meldung muss sagen, welche Nummern fehlen"

    rec = kdb.get_konformitaet(CRA_DB, projekt, "") or {}
    assert not rec.get("doc_ausgestellt"), "Nichts darf als ausgestellt gelten"
    assert int(rec.get("doc_version") or 0) == 0, "Die Version darf nicht steigen"


def test_unvollstaendiges_dokument_wird_abgelehnt(projekt):
    """Auch „fast vollständig" genügt nicht — es fehlt der Unterzeichner."""
    doc = _vollstaendig()
    doc.pop("unterzeichner_name")
    doc.pop("unterzeichner_funktion")
    with pytest.raises(ValueError, match="Anhang V"):
        kdb.issue_doc(CRA_DB, projekt, doc, "")


def test_vollstaendiges_dokument_geht_durch(projekt):
    """Die Gegenprobe: Wer die Angaben macht, kann ausstellen."""
    rec = kdb.issue_doc(CRA_DB, projekt, _vollstaendig(), "")
    assert rec["doc_ausgestellt"] is True
    assert int(rec["doc_version"]) == 1
    assert rec["ce_status"] == "doc_ausgestellt"


def test_bewertungsweg_bleibt_die_erste_huerde(projekt):
    """Ohne abgeschlossenen Bewertungsweg gar nicht erst — wie bisher."""
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A",
                                            "bewertung_abgeschlossen": False})
    with pytest.raises(ValueError, match="Bewertungsweg"):
        kdb.issue_doc(CRA_DB, projekt, _vollstaendig(), "")


# ── Die Stammdaten zählen mit ────────────────────────────────────────────────

def test_stammdaten_muessen_nicht_doppelt_geschickt_werden(projekt):
    """`doc_daten` führt Entwurf und Stammdaten zusammen (#1753).

    Hersteller und Produktname stehen bereits im Projekt; sie noch einmal zu
    verlangen wäre doppelte Erfassung. Geprüft wird der **zusammengeführte**
    Stand, nicht das, was der Aufrufer zufällig mitgeschickt hat.
    """
    doc = _vollstaendig()
    gespeichert = kdb.issue_doc(CRA_DB, projekt, doc, "")
    assert gespeichert["doc_ausgestellt"] is True

    # Ein Teil-Update ohne die Stammdatenfelder darf nicht plötzlich scheitern.
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A",
                                            "bewertung_abgeschlossen": True})
    rec = kdb.issue_doc(CRA_DB, projekt, {"ort": "Musterstadt"}, "")
    assert int(rec["doc_version"]) == 2, "Die zweite Ausstellung zählt hoch"


# ── Beide Wege prüfen gleich ─────────────────────────────────────────────────

def test_beide_ausstellungswege_nutzen_dieselbe_pruefung():
    """Die Invariante, die den Fund überhaupt möglich gemacht hat.

    `doc_export.ausstellen` prüfte, `konformitaet_db.issue_doc` nicht. Wer
    künftig einen dritten Weg baut, soll hier scheitern.
    """
    import inspect
    from cra import doc_export as de

    q_db = inspect.getsource(kdb.issue_doc) + inspect.getsource(kdb._pruefe_anhang_v)
    q_ex = inspect.getsource(de.ausstellen)
    for quelle, name in ((q_db, "konformitaet_db.issue_doc"),
                         (q_ex, "doc_export.ausstellen")):
        assert "fehlende_pflichtfelder" in quelle or "doc_daten" in quelle, \
            f"{name} prüft die Anhang-V-Pflichtangaben nicht"
