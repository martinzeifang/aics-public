"""Zwei Fundstellen-Befunde: Anhang-VII-Anrechnung und NIS-2-Registrierung.

**#2003 — acht Dokumentarten wurden nie angerechnet.**
``cra/annex_evidence._FIRMA_DOC_BAUSTEIN`` war eine **von Hand geführte** Liste
mit 9 Einträgen, während ``cra/annex_vii.PUNKTE`` 17 Dokumentarten erklärt. Ein
firmenweiter Nachweis der fehlenden acht erschien in **keiner** Beleg-Zeile der
Matrix — dieselbe Angabe über ``cra_dokumente`` zählte dagegen. Getroffen waren
die Produktbeschreibung (Anhang VII Nr. 1) und der PSIRT-Prozess (Nr. 2
Buchst. b). Nichts schlug fehl; der Nachweis lag in der Akte und wurde nur
nicht gezählt — die leise Form der Spiegel-Liste aus #1731/#1735 (#1870).

**#2004 — die Registrierung zitierte für jeden Sektor Art. 27 Abs. 2.**
Gegen die amtliche Fassung gelesen (``data/nis2_resources/32022L2555_DEU.pdf``):
Art. 27 Abs. 2 verlangt die Angaben von „den in **Absatz 1** genannten
Einrichtungen" — DNS, TLD, Domänennamen-Registrierung, Cloud, Rechenzentren,
CDN, verwaltete Dienste, verwaltete Sicherheitsdienste, Online-Marktplätze,
Suchmaschinen, soziale Netzwerke. Ein Energieversorger ist nicht darunter; für
ihn gilt **Art. 3 Abs. 4**. Der Text wird in den Nachweis gedruckt, und eine
falsche Fundstelle ist dort schlimmer als keine — zum sechsten Mal dieselbe
Klasse (#1763, #1792, #1884, #1953).
"""
from __future__ import annotations

import pytest

from cra import annex_evidence as ae
from cra.annex_vii import PUNKTE
from nis2 import registrierung_recht as rr


# ── #2003 ───────────────────────────────────────────────────────────────────

def _annex_doc_types() -> set[str]:
    return {str(d) for p in PUNKTE for d in (getattr(p, "doc_types", None) or [])}


def test_jede_erklaerte_dokumentart_wird_angerechnet():
    """**Der Wächter.** Beide Seiten gegeneinander — genau das fehlte."""
    fehlt = sorted(_annex_doc_types() - set(ae._FIRMA_DOC_BAUSTEIN))
    assert not fehlt, (
        "Diese im Anhang-VII-Katalog erklärten Dokumentarten werden im "
        f"firmenweiten Nachweis-Store nicht angerechnet (#2003): {fehlt}")


def test_die_acht_vorher_fehlenden_sind_zugeordnet():
    """Namentlich, damit der Test sagt, worum es ging."""
    erwartet = {
        "produktbeschreibung": "produktbeschreibung",
        "description": "produktbeschreibung",
        "psirt": "vuln_handling",
        "vuln": "vuln_handling",
        "advisory": "vuln_handling",
        "doc": "doc",
        "konformitaetserklaerung": "doc",
        "test": "testberichte",
    }
    for art, baustein in erwartet.items():
        assert ae._FIRMA_DOC_BAUSTEIN.get(art) == baustein, art


def test_die_zuordnung_ist_abgeleitet_und_nicht_getippt():
    """Eine abgeleitete Liste kann nicht auseinanderlaufen.

    Geprüft über das **Programm**, nicht über die Erzählung (#1834): Die
    Zuordnung muss sich aus dem Katalog ergeben, sonst ist sie wieder eine
    zweite Liste.
    """
    import ast
    import inspect

    quelle = inspect.getsource(ae._firma_doc_baustein)
    baum = ast.parse(quelle.lstrip())
    assert "PUNKTE" in ast.unparse(baum), (
        "`_firma_doc_baustein` leitet nicht mehr aus `annex_vii.PUNKTE` ab — "
        "dann ist es wieder eine Spiegel-Liste (#2003).")


def test_kurze_stichwoerter_treffen_nur_genau():
    """``doc`` als Teilstring fände „dokumentation".

    Eine **falsche** Anrechnung ist schlimmer als eine fehlende: Sie sieht aus
    wie ein Nachweis. Deshalb matchen die kurzen Stichwörter nur genau.
    """
    assert "doc" in ae._NUR_GENAU
    assert "test" in ae._NUR_GENAU
    # Und die langen bleiben Teilstring-fähig — sonst fände „pentest-bericht"
    # den Baustein nicht mehr.
    assert "pentest" not in ae._NUR_GENAU
    assert "produktbeschreibung" not in ae._NUR_GENAU


def test_jeder_baustein_existiert_im_katalog():
    """Eine Zuordnung auf einen Baustein, den es nicht gibt, zählt nirgends."""
    bausteine = {str(getattr(p, "baustein_key", "") or getattr(p, "key", ""))
                 for p in PUNKTE}
    for art, b in ae._FIRMA_DOC_BAUSTEIN.items():
        assert b in bausteine, f"{art} → {b!r} gibt es im Katalog nicht"


# ── #2004 ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("daten,erwartet", [
    ({"sektor": "Energie", "subsektor": "Elektrizität"}, rr.ART3),
    ({"sektor": "Verkehr"}, rr.ART3),
    ({"sektor": "Gesundheitswesen"}, rr.ART3),
    ({"subsektor": "Cloud-Computing"}, rr.ART27),
    ({"einrichtungsart": "Anbieter von Rechenzentrumsdiensten"}, rr.ART27),
    ({"subsektor": "TLD-Namenregister"}, rr.ART27),
    ({"einrichtungsart": "Online-Marktplatz"}, rr.ART27),
])
def test_die_grundlage_haengt_an_der_einrichtungsart(daten, erwartet):
    assert rr.grundlage(daten)["artikel"] == erwartet


def test_energie_ist_keine_art27_einrichtung():
    """**Der gemeldete Fall.** Art. 27 Abs. 1 zählt digitale Einrichtungen auf."""
    g = rr.grundlage({"sektor": "Energie", "subsektor": "Elektrizität"})
    assert g["artikel"] == rr.ART3
    assert "Art. 27 Abs. 1" in g["hinweis"]
    # Und die beiden Angaben, die nur Art. 27 verlangt, werden hier nicht
    # eingefordert.
    assert g["nur_art27_felder"] == []


def test_vertrauensdienste_sind_keine_art27_einrichtung():
    """Die Falle beim Bauen: ``dvo2690.is_dvo_relevant`` hätte hier ``True``
    gesagt — seine Stichwortliste enthält „vertrauensdienst" und
    „kommunikation", die in Art. 27 Abs. 1 **nicht** stehen. Zwei verschiedene
    Rechtslisten; sie zusammenzuführen hätte eine Pflicht ausgedehnt."""
    from nis2.dvo2690 import is_dvo_relevant

    assert is_dvo_relevant("Vertrauensdienste") is True
    assert rr.grundlage({"subsektor": "Vertrauensdienste"})["artikel"] == rr.ART3
    assert is_dvo_relevant("Anbieter öffentlicher elektronischer Kommunikation") is True
    assert rr.grundlage(
        {"subsektor": "Anbieter öffentlicher elektronischer Kommunikation"}
    )["artikel"] == rr.ART3


def test_ohne_angabe_wird_nicht_geraten():
    """Eine fehlende Angabe beweist nicht, dass Art. 27 nicht gilt."""
    g = rr.grundlage({})
    assert g["unbestimmt"] is True
    assert g["artikel"] == ""
    assert "nicht erfasst" in g["hinweis"]


def test_die_fundstellen_je_feld_passen_zum_artikel():
    for feld, fs in rr.FUNDSTELLE[rr.ART27].items():
        assert fs.startswith("Art. 27 Abs. 2"), feld
    for feld, fs in rr.FUNDSTELLE[rr.ART3].items():
        assert fs.startswith("Art. 3 Abs. 4"), feld
    # Art. 3 Abs. 4 kennt „Art der Einrichtung" und die sonstigen
    # Unionsniederlassungen nicht — sie stehen nur in Art. 27 Abs. 2 Buchst. b/c.
    for feld in rr.NUR_ART27:
        assert feld in rr.FUNDSTELLE[rr.ART27]
        assert feld not in rr.FUNDSTELLE[rr.ART3]


def test_die_aenderungsfrist_zitiert_nicht_mehr_absatz_4():
    """Art. 27 Abs. 4 regelt die Weiterleitung durch die zentrale Anlaufstelle
    an die ENISA — nicht die Pflicht der Einrichtung. Die Änderungsmeldung
    binnen drei Monaten steht in **Abs. 3**."""
    assert rr.aenderungsfrist_fundstelle({"subsektor": "Cloud-Computing"}) == "Art. 27 Abs. 3"
    assert "Art. 3 Abs. 3" in rr.aenderungsfrist_fundstelle({"sektor": "Energie"})
    for daten in ({}, {"sektor": "Energie"}, {"subsektor": "Cloud-Computing"}):
        assert "Abs. 4" not in rr.aenderungsfrist_fundstelle(daten)


def test_die_feldmenge_wird_nicht_beschnitten():
    """Art. 3 Abs. 4 nennt Sektor und Mitgliedstaaten nur „gegebenenfalls" —
    sie hier fallen zu lassen würde Datensätze als vollständig ausweisen, die
    es heute nicht sind. Das ist bei einer Nachweisführung die falsche Richtung
    (#1751)."""
    from nis2.registrierung_db import PFLICHTFELDER, missing_fields

    assert set(PFLICHTFELDER) == {"name", "sektor", "anschrift", "kontakt_email",
                                  "mitgliedstaaten", "ip_bereiche"}
    assert missing_fields({}) == list(PFLICHTFELDER)
    voll = {f: "x" for f in PFLICHTFELDER}
    assert missing_fields(voll) == []


def test_keine_erfundene_nationale_fundstelle():
    """Die Übermittlung geht an die nationale Behörde; eine Paragrafennummer
    des umsetzenden Gesetzes steht hier nicht, weil sie nicht geprüft ist
    (#1763)."""
    import re
    from pathlib import Path

    quelle = Path("nis2/registrierung_recht.py").read_text(encoding="utf-8")
    treffer = re.findall(r"§\s*\d+[a-z]?\s*(?:Abs\.?\s*\d+)?\s*BSIG", quelle)
    assert not treffer, f"erfundene BSIG-Fundstelle: {treffer}"
