"""Das Konformitäts-Gate darf bei einem Quellenausfall nicht grün werden (#1751).

Gefunden beim Bau der Release-Prüfungen: Die Schwachstellen-Abfrage war in
``try/except Exception: pass`` gekapselt. Fiel sie aus, blieb der Zähler auf 0
und die Ampel wurde **grün** — der gefährlichste Fehler in einem Gate, weil er
wie ein gutes Ergebnis aussieht und niemand nachsieht.

Der Annex-VII-Block daneben war nie betroffen (``annex_ok`` blieb ``False``).
Genau dieser Unterschied belegt, dass es ein Versehen war und keine
Entscheidung — und dass die Korrektur keine neue Strenge einführt, sondern eine
bestehende wiederherstellt.
"""
from __future__ import annotations

import pytest

from cra import konformitaet_gate as gate


def _alles_in_ordnung(monkeypatch):
    """Alle Quellen außer den Schwachstellen auf „nichts offen" stellen.

    ``konformitaet_gate`` importiert funktionslokal (``from cra.db import …``),
    deshalb wird an der **Quelle** gepatcht und nicht am Gate-Modul — ein Patch
    auf das Gate würde wirkungslos bleiben und der Test grün aussehen, ohne zu
    prüfen.
    """
    import cra.db as cdb
    import cra.requirements as creq
    import cra.traceability_db as ctdb

    monkeypatch.setattr(creq, "CRA_ANFORDERUNGEN", [])
    monkeypatch.setattr(cdb, "load_bewertungen", lambda *a, **k: {})
    monkeypatch.setattr(cdb, "load_projekt", lambda *a, **k: {"name": "P", "meta": {}})
    monkeypatch.setattr(ctdb, "annex_vii_status",
                        lambda *a, **k: {"vollstaendig": True, "bausteine": []})


def test_ausfall_der_schwachstellen_abfrage_verhindert_gruen(monkeypatch):
    """Alles andere grün, nur die Schwachstellen nicht lesbar → nicht grün."""
    import cra.db as cdb

    def _kaputt(*a, **k):
        raise RuntimeError("Verbindung verloren")

    _alles_in_ordnung(monkeypatch)
    monkeypatch.setattr(cdb, "list_vuln", _kaputt)

    res = gate.evaluate("P")
    assert res["ampel"] != "gruen", (
        "ungeprüft ist nicht erfüllt — ein Datenbankfehler darf nicht wie "
        "„keine Schwachstellen gefunden\" wirken")
    assert res["konform"] is False
    ungeprueft = [p for p in res["offene_punkte"] if p.get("ungeprueft")]
    assert ungeprueft, "der Ausfall muss als Punkt sichtbar sein, nicht verschluckt"
    assert "RuntimeError" in ungeprueft[0]["hinweis"], (
        "die Fehlerklasse gehört in den Hinweis, sonst sucht der Anwender blind")


def test_ausfall_ist_kein_verstoss(monkeypatch):
    """`bedingt`, nicht `rot`: Ein Datenbankfehler ist eine fehlende Prüfung,
    keine festgestellte Nicht-Konformität. Die Unterscheidung entscheidet, ob
    jemand ein Release stoppt oder eine Datenquelle repariert."""
    import cra.db as cdb

    _alles_in_ordnung(monkeypatch)
    monkeypatch.setattr(cdb, "list_vuln",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))

    assert gate.evaluate("P")["ampel"] == "bedingt"
