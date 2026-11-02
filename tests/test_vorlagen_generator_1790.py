"""Der Vorlagen-Generator deckt jeden Berichtstyp ab (#1790).

Für Cyberwoks gab es zwei Vorlagen, beide **ohne** Berichtstyp und damit
modulweit. Seit #1777 wählt das Berichts-Center je Bericht; eine modulweite
liefert für alle sieben CRA-Dokumente dasselbe Papier — bis hin zur
EU-Konformitätserklärung, deren Aufbau dem Rechtstext gehört.

Geprüft wird das, was beim nächsten neuen Berichtstyp schiefgehen würde: dass
der Generator ihn kennt. Eine Vorlage, die es nicht gibt, fällt sonst erst auf,
wenn jemand den Bericht aufruft und das Standardpapier bekommt.
"""
from __future__ import annotations

import importlib

import pytest


def _katalog(modul: str, pfad: str) -> list:
    return importlib.import_module(pfad).catalog()


_PROVIDER = {
    "cra": "cra.berichte_provider",
    "compliance_audit": "compliance_audit.berichte_provider",
    "nis2": "nis2.berichte_provider",
    "aiact": "ai_act.berichte_provider",
    "dsgvo": "dsgvo.berichte_provider",
    "wiba": "wiba.berichte_provider",
    "risikobewertung": "risikobewertung.berichte_provider",
}


def test_jeder_berichtstyp_hat_einen_bauplan():
    from tools.vorlagen.cyberwoks_plaene import PLAENE

    fehlend = []
    for modul, pfad in _PROVIDER.items():
        for spec in _katalog(modul, pfad):
            if (modul, spec.key) not in PLAENE:
                fehlend.append(f"{modul}/{spec.key}")
    assert not fehlend, (
        "Für diese Berichtstypen fehlt ein Bauplan — der Bericht bekäme das "
        f"Standardpapier statt des Hausdesigns: {fehlend}")


def test_kein_bauplan_ohne_berichtstyp():
    """Die Gegenrichtung: ein Bauplan für einen Typ, den es nicht mehr gibt."""
    from tools.vorlagen.cyberwoks_plaene import PLAENE

    bekannt = {(m, s.key) for m, p in _PROVIDER.items() for s in _katalog(m, p)}
    ueberzaehlig = sorted(set(PLAENE) - bekannt)
    assert not ueberzaehlig, f"Baupläne ohne Berichtstyp: {ueberzaehlig}"


def test_pflichtdokumente_sind_als_solche_gebaut():
    """Für Nachweis und Erklärung sind Angaben vorgeschrieben (#1777).

    Fehlt eine, lässt sich die Vorlage nicht als Standard setzen — der Fehler
    fiele erst beim Einspielen auf.
    """
    from tools.vorlagen.cyberwoks_plaene import PLAENE

    for typ in ("konformitaetsnachweis", "konformitaetserklaerung"):
        assert ("cra", typ) in PLAENE


@pytest.mark.parametrize("modul,typ", [("cra", "gesamt"), ("cra", "konformitaetsnachweis"),
                                       ("dsgvo", "vvt"), ("wiba", "massnahmen")])
def test_bauplan_traegt_titel_und_rechtsgrundlage(modul, typ):
    from tools.vorlagen.cyberwoks_plaene import PLAENE

    dokumentart, titel, _zeile, untertitel, inhalt = PLAENE[(modul, typ)]
    assert dokumentart and not dokumentart.isupper(), "Dokumentart gehört lesbar gesetzt"
    assert "{{" in titel, "Der Titel muss aus den Projektdaten kommen"
    assert untertitel, "Die Rechtsgrundlage gehört unter den Titel"
    assert callable(inhalt)
