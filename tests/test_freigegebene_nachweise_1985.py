"""Freigegebene Nachweise erreichen die Module (#1985).

DER BEFUND
Meldung aus dem Betrieb: „Es scheint die Vorschläge nicht in die Module zu
übernehmen." Auf Produktiv lagen **67 von Hand freigegebene** Zuordnungen in
``evidence_mappings_approved`` — und keine einzige erreichte je einen Prompt.
Drei Defekte auf demselben Weg, jeder für sich ausreichend:

1. **``approved_mapping_items`` las eine Dataclass als Dict.**
   ``r.get("claim") if isinstance(r, dict) else None`` — und
   ``list_approved_mappings`` liefert ``ApprovedMappingRow``. ``claim`` war
   **immer** ``None``, die Schleife brach bei jeder Zeile ab. Die
   höchstbewertete Nachweisquelle der Anwendung (``relevance=2.0``,
   „human-approved → vorrangig") hat nie etwas geliefert, in keinem Modul.
2. **Zwei Schlüsselräume für dieselbe Firma.** Der Nachweis-Store ist über den
   **Namen** geschlüsselt (``evidence_documents.firmen_id = 'Firma
   Cyberwoks'``, jeder Endpunkt schreibt ``firmen_id=firma_name``);
   ``build_context`` übergab die **Nummer** (500003). Unter PostgreSQL ist das
   nicht einmal ein stiller Fehlschlag, sondern
   ``operator does not exist: text = integer``.
3. **Der Fehler wurde verschluckt.** ``except Exception: return []`` sah aus
   wie „keine Nachweise vorhanden" — deshalb ist das monatelang niemandem
   aufgefallen.

Dazu eine Verengung: ``firm_upload_items`` schnitt mit ``[:limit]`` **vor** der
Textprüfung. Bei 16 Nachweisen, von denen die ersten vier keinen lesbaren Text
haben, war das Ergebnis leer.

WARUM DIESER TEST SO AUSSIEHT
Er geht **durch** ``build_context`` und prüft den gerenderten Block — nicht die
Teilfunktionen einzeln. Genau daran lag es: Jede Teilfunktion war für sich
plausibel, und die Behauptung „die Nachweise kommen an" stand nirgends unter
Prüfung (die Lehre aus #1785 und #1870).
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest


@pytest.fixture()
def nachweis_akte(tmp_path, monkeypatch):
    """Eine Firma mit einem freigegebenen Mapping und einem Nachweis mit Text."""
    from evidence import db as edb
    from shared import evidence_context as ec

    db = tmp_path / "evidence.sqlite"
    firmen_db = tmp_path / "firmen.sqlite"
    monkeypatch.setattr(ec, "_EVIDENCE_DB", db)
    monkeypatch.setattr(ec, "_FIRMEN_DB", firmen_db)

    # Der Nachweis-Store ist über den **Namen** geschlüsselt — so schreiben es
    # die Endpunkte, und so sieht es in der Installation aus.
    datei = tmp_path / "TOM-Nachweis-02_System-und-Netzdokumentation.md"
    datei.write_text("# Netzdokumentation\nVLANs je Zweck.\n", encoding="utf-8")
    doc = edb.add_document(db, datei, store_dir=tmp_path / "store",
                           doc_type="technische_dokumentation",
                           firmen_id="Firma Cyberwoks")
    edb.upsert_extracted_text(db, doc.id, "Das Netz ist in VLANs je Zweck getrennt.")
    edb.save_approved_mapping(
        db, requirement_id="netze-18",
        claim="Die WLAN-Kommunikation ist mit WPA2/WPA3 verschlüsselt.",
        citations=[{"doc_id": doc.id, "chunk": 1}], confidence=0.9,
        rationale="Abschnitt 4 des Dokuments", approved_by="pruefer-1",
        firmen_id="Firma Cyberwoks")
    return {"db": db, "doc_id": doc.id}


def test_das_freigegebene_mapping_steht_im_nachweis_block(nachweis_akte,
                                                          monkeypatch):
    """Der Rundlauf — das ist der Test, der gefehlt hat."""
    from shared import evidence_context as ec

    # Die Firmennummer ist hier nicht auflösbar (eigene Test-DB); maßgeblich
    # für den Nachweis-Store ist der Name aus dem Projekt.
    erg = ec.build_context(
        "wiba", {"unternehmen": "Firma Cyberwoks"}, {"id": "netze-18"},
        include_risks=False)

    block = erg["rendered_block"]
    assert "WPA2/WPA3" in block, (
        "Das von Hand freigegebene Mapping erreicht den Prompt nicht — genau "
        "der gemeldete Befund (#1985).\nBlock war:\n" + block)
    assert any(it.kind == "mapping" for it in erg["items"])
    assert any(r.startswith("mapping:") for r in erg["sources"])


def test_der_hochgeladene_nachweis_steht_im_block(nachweis_akte):
    from shared import evidence_context as ec

    erg = ec.build_context("wiba", {"unternehmen": "Firma Cyberwoks"},
                           {"id": "netze-18"}, include_risks=False)
    assert "VLANs je Zweck" in erg["rendered_block"]
    assert any(it.kind == "upload" for it in erg["items"])


def test_die_firmennummer_allein_genuegt_nicht(nachweis_akte):
    """Die Nummer ist der Schlüssel des Risiko-Cockpits, nicht des Stores.

    Wird nur sie übergeben und ist kein Name auflösbar, darf der Nachweis-Store
    **nicht** mit ihr abgefragt werden — unter PostgreSQL wirft das
    ``operator does not exist: text = integer``, und genau der Fehler wurde
    verschluckt.
    """
    from shared import evidence_context as ec

    # Kein Firmenname im Projekt, nur die Nummer → der Store wird nicht
    # befragt, statt mit dem falschen Typ befragt zu werden.
    assert ec.resolve_firmen_schluessel({}, 500003) is None
    assert ec.approved_mapping_items("netze-18", None) == []
    assert ec.firm_upload_items(None) == []


def test_eine_dataclass_zeile_wird_gelesen():
    """Der Kern von Defekt 1 — isoliert, damit die Ursache benannt bleibt."""
    from shared.evidence_context import _feld
    from evidence.db import ApprovedMappingRow

    zeile = ApprovedMappingRow(requirement_id="netze-18", claim="belegt",
                               citations=[], confidence=0.8, rationale="",
                               approved_by="p", approved_at=int(time.time()))
    assert _feld(zeile, "claim") == "belegt"
    assert _feld({"claim": "belegt"}, "claim") == "belegt"
    assert _feld(zeile, "gibtEsNicht") is None


def test_der_platz_gilt_den_gelieferten_nachweisen(tmp_path, monkeypatch):
    """``limit`` zählt Einträge, nicht Kandidaten.

    Vorher schnitt ``[:limit]`` vor der Textprüfung: Vier Dokumente ohne Text
    belegten alle Plätze, und das fünfte mit Text kam nie vor.
    """
    from evidence import db as edb
    from shared import evidence_context as ec

    db = tmp_path / "evidence.sqlite"
    monkeypatch.setattr(ec, "_EVIDENCE_DB", db)
    datei = tmp_path / "x.md"
    datei.write_text("egal", encoding="utf-8")

    for _ in range(4):  # ohne Volltext
        edb.add_document(db, datei, store_dir=tmp_path / "s",
                         firmen_id="Firma Cyberwoks")
    mit = edb.add_document(db, datei, store_dir=tmp_path / "s",
                           firmen_id="Firma Cyberwoks")
    edb.upsert_extracted_text(db, mit.id, "Der eine lesbare Nachweis.")

    items = ec.firm_upload_items("Firma Cyberwoks", limit=4)
    assert len(items) == 1 and "lesbare" in items[0].text


def test_ein_fehler_wird_nicht_mehr_verschluckt(tmp_path, monkeypatch, caplog):
    """Die Rückgabe bleibt leer — aber der Grund steht im Log.

    Das ist der Teil, der die drei Defekte unsichtbar gemacht hat.
    """
    from shared import evidence_context as ec

    monkeypatch.setattr(ec, "_EVIDENCE_DB", tmp_path / "evidence.sqlite")

    def kaputt(*a, **k):
        raise RuntimeError("Datenbank weg")

    import evidence.db as edb
    monkeypatch.setattr(edb, "list_approved_mappings", kaputt)
    with caplog.at_level("WARNING"):
        assert ec.approved_mapping_items("netze-18", "Firma Cyberwoks") == []
    assert "nicht lesbar" in caplog.text and "Datenbank weg" in caplog.text
