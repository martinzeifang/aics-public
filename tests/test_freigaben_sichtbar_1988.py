"""Eine Freigabe ist zu sehen und zurücknehmbar (#1988).

DER BEFUND
Meldung aus dem Betrieb: „Ich hab in Prod gerade 32 WiBA-Fragen übernommen.
Keine einzige wurde geschrieben." Nachgezählt auf Produktiv:

- **36** Ereignisse ``evidence.mapping.approved`` im Revisionspfad ab 10:30,
  jede Antwort HTTP 200;
- ``evidence_mappings_approved`` wuchs von 67 auf **91** — also **+24**;
- über den ganzen Tag: **103** Freigaben, **91** Zeilen.

Es wurde also geschrieben, nur anders als erwartet, und beides blieb unsichtbar:

1. **Zwölf Freigaben ersetzten eine frühere.** Der Primärschlüssel ist
   ``(requirement_id, claim)`` und der Konflikt wird aktualisiert — eine
   gleichlautende Aussage überschreibt die vorige **samt Urheber und
   Zeitpunkt**. Die Antwort war jedes Mal ``{"ok": true}``.
2. **Es gab keine Stelle, die eine Freigabe zeigt.** ``list_approved_mappings``
   fragt immer **eine** Anforderung ab, weil der Nachweis-Block (#1483) das so
   braucht; eine Liste über die Firma existierte nicht, und im Frontend kam
   ``evidence_mappings_approved`` in keiner Datei vor. Die Zeile verschwand aus
   dem Erschließungs-Dialog und erschien nirgends wieder.
3. **Zurücknehmen war nicht möglich.** ``delete_approved_mapping`` lag seit
   #1483 ohne **jeden** Aufrufer im Baum.

Zusammen: Die Freigabe war **schreib-nur**. Das ist die vierte Richtung der
#1805-Familie — nicht ein Knopf ohne Wirkung, sondern eine Wirkung ohne Ort.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
VIEW = WURZEL / "frontend" / "src" / "views" / "firmen" / "FirmenView.vue"
MODAL = (WURZEL / "frontend" / "src" / "components" / "firmen"
         / "NachweisErschliessungModal.vue")


def test_eine_freigabe_sagt_ob_sie_neu_ist(tmp_path):
    """Der Rundlauf: zweimal dieselbe Aussage → einmal neu, einmal ersetzt."""
    from evidence.db import freigegebene_zuordnungen, save_approved_mapping

    db = tmp_path / "evidence.sqlite"
    args = dict(requirement_id="netze-18",
                claim="Die WLAN-Kommunikation ist verschlüsselt.",
                citations=[{"doc_id": "d1", "chunk": 1}], confidence=0.9,
                rationale="Abschnitt 4", firmen_id="Firma Cyberwoks")

    assert save_approved_mapping(db, approved_by="pruefer-1", **args) is True
    assert save_approved_mapping(db, approved_by="pruefer-2", **args) is False, (
        "Eine gleichlautende Freigabe ersetzt die frühere — das muss der "
        "Aufrufer erfahren, sonst zählt er 36 und bekommt 24 (#1988).")

    zeilen = freigegebene_zuordnungen(db, firmen_id="Firma Cyberwoks")
    assert len(zeilen) == 1
    assert zeilen[0]["approved_by"] == "pruefer-2", (
        "Der Konflikt aktualisiert — der zweite Urheber steht in der Zeile. "
        "Genau deshalb darf das nicht stillschweigend passieren.")


def test_die_freigaben_einer_firma_sind_abfragbar(tmp_path):
    """Die Liste, die es nicht gab — und die Mandantentrennung dabei."""
    from evidence.db import freigegebene_zuordnungen, save_approved_mapping

    db = tmp_path / "evidence.sqlite"
    for firma, req in (("Firma A", "netze-1"), ("Firma A", "netze-2"),
                       ("Firma B", "netze-3")):
        save_approved_mapping(db, requirement_id=req, claim=f"belegt {req}",
                              citations=[{"doc_id": "d", "chunk": 1}],
                              confidence=0.8, rationale="", approved_by="p",
                              firmen_id=firma)

    a = freigegebene_zuordnungen(db, firmen_id="Firma A")
    assert {z["requirement_id"] for z in a} == {"netze-1", "netze-2"}, (
        "Die Liste reicht über die Mandantengrenze — dieselbe Preisgabe wie "
        "in #1703/S4.")
    assert len(freigegebene_zuordnungen(db, firmen_id="Firma B")) == 1


def test_eine_freigabe_laesst_sich_zuruecknehmen(tmp_path):
    from evidence.db import (delete_approved_mapping, freigegebene_zuordnungen,
                             save_approved_mapping)

    db = tmp_path / "evidence.sqlite"
    save_approved_mapping(db, requirement_id="netze-18", claim="belegt",
                          citations=[{"doc_id": "d", "chunk": 1}],
                          confidence=0.8, rationale="", approved_by="p",
                          firmen_id="F")
    delete_approved_mapping(db, "netze-18", "belegt")
    assert freigegebene_zuordnungen(db, firmen_id="F") == []


def test_die_endpunkte_sind_verdrahtet():
    """Ohne Route bleibt die Funktion im Baum liegen — wie bisher.

    ``delete_approved_mapping`` lag seit #1483 ohne **jeden** Aufrufer da. Eine
    Funktion ohne Route ist in diesem Haus kein Vorrat, sondern ein Defekt, der
    aussieht wie eine Fähigkeit.
    """
    quelle = (WURZEL / "server" / "api" / "firmen.py").read_text(encoding="utf-8")
    assert "/<firma_name>/evidence/freigegeben'" in quelle, (
        "Kein Endpunkt, der die Freigaben einer Firma listet.")
    assert "freigegeben/zurueckziehen'" in quelle, (
        "Kein Endpunkt, der eine Freigabe zurücknimmt.")
    assert "freigegebene_zuordnungen" in quelle
    assert "delete_approved_mapping" in quelle
    # Das Zurücknehmen ist eine Handlung an einer Nachweisakte und gehört in
    # den Revisionspfad (#1784: mit `user_id`, sonst steht dort „irgendwer").
    block = quelle.split("def evidence_freigabe_zurueckziehen", 1)[1]
    block = block.split("@firmen_bp", 1)[0]
    assert "evidence.mapping.withdrawn" in block
    assert "'user_id': nutzer" in block


def test_die_oberflaeche_zeigt_die_freigaben():
    quelle = VIEW.read_text(encoding="utf-8")
    vorlage = quelle.split("<script setup", 1)[0]
    assert "freigegebeneZuordnungen" in vorlage, (
        "Die Firmenansicht zeigt die freigegebenen Zuordnungen nicht — dann "
        "ist die Freigabe weiter schreib-nur (#1988).")
    assert "onFreigabeZurueckziehen" in vorlage
    programm = quelle.split("<script setup", 1)[1]
    assert "fetchFreigegebene" in programm
    # Nachgeladen wird beim Aufklappen, nicht beim Öffnen der Firma: 91 Zeilen
    # gehören nicht in jeden Seitenaufbau.
    assert "onFreigabenToggle" in programm


def test_der_dialog_nennt_neu_und_ersetzt():
    quelle = MODAL.read_text(encoding="utf-8")
    for name in ("freigabenNeu", "freigabenErsetzt"):
        assert name in quelle, (
            f"{name} fehlt — dann zählt der Anwender wieder 36 und findet 24.")
    assert re.search(r"if\s*\(res\.neu\)", quelle), (
        "Der Rückgabewert der Freigabe wird nicht ausgewertet.")
