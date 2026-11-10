"""Die Rechtskataloge sind umschaltbar — und zwar vollständig (#1954).

WORUM ES GEHT
Die Anforderungskataloge der Module (CRA, NIS2, DSGVO, AI Act) sind
Modul-Literale mit ``id``, ``kapitel``, ``ref``, ``titel``, ``beschreibung``.
Die englische Fassung steht additiv als ``titel_en``/``beschreibung_en`` im
selben Eintrag; ``shared/katalog_sprache.uebersetze`` tauscht sie aus.

DREI DINGE, DIE HIER SCHIEFGEHEN KÖNNEN

1. **Eine Lücke bleibt unbemerkt.** Fehlt ``titel_en``, gilt der deutsche
   Titel — das ist die richtige Zusage (eine Anforderung ohne Namen wäre
   schlimmer), aber sie macht die Lücke unsichtbar. Darum wird sie hier
   gezählt und benannt.
2. **Ein Bezeichner wird übersetzt.** ``id`` und ``kapitel`` sind Schlüssel;
   eine übersetzte ID bricht jede Verknüpfung — Issue-Links, Bewertungen,
   Evidence-Mappings, das Release-Gate. Dieselbe Klasse wie der Fehlercode
   im Sprachkatalog (#1954) und ``OWASP-PC-`` als Katalogwert.
3. **Die Fundstelle wandert.** ``ref`` wird in den Nachweis gedruckt. Eine
   falsche Fundstelle dort sieht aus wie eine Feststellung (#1763/#1792).
   Sie darf eine englische Fassung haben (``Annex I Part II No. 3``), aber
   die **Ziffern** müssen dieselben bleiben.
"""
from __future__ import annotations

import importlib
import re

import pytest

from shared import katalog_sprache as ks

#: (Modulpfad, Name des Katalog-Literals, Modulschlüssel)
KATALOGE = [
    ("cra.requirements", "CRA_ANFORDERUNGEN", "cra"),
    ("nis2.requirements", "NIS2_ANFORDERUNGEN", "nis2"),
    ("dsgvo.requirements", "DSGVO_ANFORDERUNGEN", "dsgvo"),
    ("ai_act.requirements", "AI_ACT_REQUIREMENTS", "aiact"),
]

#: Felder, die **niemals** eine Sprachfassung bekommen dürfen.
BEZEICHNER = ("id", "kapitel", "gewichtung")

ZIFFERN = re.compile(r"\d+")


def _katalog(modulpfad: str, name: str):
    mod = importlib.import_module(modulpfad)
    eintraege = getattr(mod, name, None)
    if not eintraege:
        pytest.skip(f"{modulpfad}.{name} nicht vorhanden")
    return eintraege


@pytest.mark.parametrize("modulpfad,name,modul", KATALOGE)
def test_kein_bezeichner_hat_eine_sprachfassung(modulpfad, name, modul):
    """``id_en`` oder ``kapitel_en`` wäre ein gebrochener Schlüssel."""
    verstoesse = []
    for e in _katalog(modulpfad, name):
        for feld in BEZEICHNER:
            if f"{feld}_en" in e:
                verstoesse.append(f"{e.get('id')}: {feld}_en")
    assert not verstoesse, (
        f"{modul}: Bezeichner mit Sprachfassung — eine übersetzte ID bricht "
        f"jede Verknüpfung:\n  " + "\n  ".join(verstoesse))


@pytest.mark.parametrize("modulpfad,name,modul", KATALOGE)
def test_die_fundstelle_behaelt_ihre_ziffern(modulpfad, name, modul):
    """``Anhang I Teil II Nr. 3`` → ``Annex I Part II No. 3`` — nicht Nr. 4.

    Die Fundstelle darf übersetzt werden, aber die Ziffern sind der
    Rechtsbezug. Aus ``Art. 3 Nr. 30`` ein ``Art. 3 No. 31`` zu machen wäre
    genau der Fehler aus #1792, nur in der englischen Fassung — und dort
    fällt er niemandem auf, der nur die deutsche liest.
    """
    verstoesse = []
    for e in _katalog(modulpfad, name):
        de, en = e.get("ref"), e.get("ref_en")
        if not (isinstance(de, str) and isinstance(en, str) and en.strip()):
            continue
        if ZIFFERN.findall(de) != ZIFFERN.findall(en):
            verstoesse.append(
                f"{e.get('id')}: {de!r} -> {en!r} "
                f"({ZIFFERN.findall(de)} gegen {ZIFFERN.findall(en)})")
    assert not verstoesse, (
        f"{modul}: Die Ziffern der Fundstelle haben sich geändert:\n  "
        + "\n  ".join(verstoesse))


@pytest.mark.parametrize("modulpfad,name,modul", KATALOGE)
def test_uebersetzung_laesst_den_katalog_unberuehrt(modulpfad, name, modul):
    """``uebersetze`` liefert Kopien, nicht geänderte Einträge.

    Der Katalog ist ein Modul-Literal und wird von mehreren Anfragen
    gleichzeitig gelesen. Ihn an Ort und Stelle zu ändern wäre ein
    Datenrennen, das sich als sprunghaft falsche Sprache zeigt — und das
    fällt im Betrieb erst auf, wenn ein Anwender es meldet.
    """
    eintraege = _katalog(modulpfad, name)
    vorher = [dict(e) for e in eintraege]
    ks.uebersetze_viele(eintraege, "en")
    assert [dict(e) for e in eintraege] == vorher, \
        f"{modul}: uebersetze_viele hat den Katalog verändert"


@pytest.mark.parametrize("modulpfad,name,modul", KATALOGE)
def test_jeder_eintrag_hat_eine_englische_fassung(modulpfad, name, modul):
    """Die Lücke wird **benannt**, nicht verschwiegen.

    Fehlt ``titel_en``, erscheint der deutsche Titel in einer englischen
    Liste. Das ist der richtige Rückfall und macht die Lücke unsichtbar —
    deshalb dieser Test. Er ist der Fortschrittsbalken der Übersetzung des
    jeweiligen Katalogs.
    """
    eintraege = _katalog(modulpfad, name)
    fehlt = ks.fehlende(eintraege, "en")
    if fehlt and len(fehlt) == len(eintraege):
        # Noch gar nicht angefangen: Der Katalog ist offene Arbeit, nicht ein
        # Defekt. Sobald **ein** Eintrag übersetzt ist, wird der Test scharf
        # und nennt die Lücke — so bleibt die Teilübersetzung nicht liegen.
        pytest.skip(
            f"{modul}: Katalog noch nicht übersetzt "
            f"({len(eintraege)} Anforderungen offen)")
    assert not fehlt, (
        f"{modul}: {len(fehlt)} von {len(eintraege)} Anforderungen ohne "
        f"englischen Titel — sie erscheinen deutsch in der englischen "
        f"Liste:\n  " + ", ".join(fehlt[:40])
        + (f"\n  … und {len(fehlt) - 40} weitere" if len(fehlt) > 40 else ""))


def test_selbst_angelegte_anforderungen_bleiben_unberuehrt():
    """Der eigene Text des Mandanten wird nicht maschinell übersetzt.

    Eine selbst angelegte Anforderung trägt kein ``titel_en``; der Rückfall
    liefert, was der Anwender getippt hat. ``fehlende`` lässt sie außen vor,
    weil das Fehlen dort der **Normalfall** ist und kein Befund — ein
    Prüfpunkt, der bei richtigem Verhalten anschlägt, wird abgeschaltet
    (#1774/#1877).
    """
    eigen = {"id": "EIGEN-01", "kapitel": "IMPL",
             "titel": "Unsere Hausregel", "beschreibung": "Nur bei uns.",
             "_quelle": "custom"}
    assert ks.uebersetze(eigen, "en")["titel"] == "Unsere Hausregel"
    assert ks.fehlende([eigen], "en") == []
    # Ohne den Filter wäre sie ein Befund — das hält die Begründung fest.
    assert ks.fehlende([eigen], "en", nur_standard=False) == ["EIGEN-01"]
