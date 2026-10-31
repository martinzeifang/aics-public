"""#1874: Sind alle Angaben erfasst, enthält der DoC-Entwurf keine Platzhalter.

Meldung aus dem Betrieb: „Der KI-Assistent für EU-Konformitätserklärung holt
sich nicht die notwendigen Infos aus der Datenbank. Stelle sicher, dass wenn
alles ausgefüllt ist, die Erklärung zu 100 % vollständig ist, ohne
Platzhalter."

Der Prompt bekam nur Projekt, Konformitäts-Stammdaten und Normen — den
**erfassten** Datensatz der Erklärung (`doc_json`) nie. Gleichzeitig wies er
die KI an, Fehlendes als ``[zu ergänzen]`` zu markieren. Da die Werte nie
ankamen, war für die KI jedes Anhang-V-Feld fehlend: Der Entwurf **musste**
voller Platzhalter sein.
"""
from __future__ import annotations

from cra.ai_wizards import build_konformitaetserklaerung_prompt
from cra.doc_export import ABGELEITET, EINGABEFELDER

PROJEKT = {"name": "AI Compliance Suite", "unternehmen": "Cyberwoks",
           "beschreibung": "Compliance-Webanwendung", "produktklasse": "default"}


def _voll() -> dict:
    """Ein Datensatz, wie ihn `doc_daten` liefert.

    **Auch die abgeleiteten Felder**: `verantwortungssatz` und
    `konformitaetsaussage` sind Gesetzesformeln, die `doc_daten` selbst setzt —
    sie stehen in `ANHANG_V` (Nr. 3 und Nr. 5) und zählen mit. Ein Test, der
    sie weglässt, prüft einen Zustand, den die Anwendung nie herstellt.
    """
    doc = {f: f"Wert-{f}" for f in EINGABEFELDER}
    doc.update({f: f"abgeleitet-{f}" for f in ABGELEITET})
    doc["normen"] = ["EN 18031-1"]
    doc["datum"] = "2026-10-30"
    return doc


def test_ohne_erfassten_datensatz_bleibt_alles_wie_vorher():
    """Bestandsverhalten: Ohne `doc` verhält sich der Bauer wie bisher.

    Dieselbe Zusage wie bei `evidence_section` (#1483) und `prompt_zusatz`
    (#1832) — sie macht jeden Bestandstest zum Regressionsschutz.
    """
    p = build_konformitaetserklaerung_prompt(PROJEKT, {}, [])
    assert "Annex V verlangt folgende" in p
    assert "[zu ergänzen]" in p


def test_vollstaendig_erfasst_verbietet_platzhalter():
    """Der Kern der Meldung."""
    p = build_konformitaetserklaerung_prompt(PROJEKT, {}, [], doc=_voll(),
                                             nb_pflichtig=False)
    assert "KEINE" in p and "Platzhalter" in p, (
        "Bei vollständiger Erfassung muss der Prompt Platzhalter untersagen")
    assert "[FEHLT]" not in p
    # Und die Werte müssen wirklich drinstehen, nicht nur die Feldnamen.
    assert "Wert-hersteller_adresse" in p
    assert "Wert-unterzeichner_funktion" in p


def test_nur_leere_felder_duerfen_platzhalter_werden():
    doc = _voll()
    doc["ort"] = ""
    doc["unterzeichner_name"] = ""
    p = build_konformitaetserklaerung_prompt(PROJEKT, {}, [], doc=doc,
                                             nb_pflichtig=False)
    assert "Nur diese Felder sind leer" in p
    assert "ort" in p and "unterzeichner_name" in p
    assert "[FEHLT]" in p, "Das leere Feld muss im Datenblock als fehlend stehen"
    # Gefüllte Felder dürfen NICHT als zu ergänzen gelten.
    kopf, _, rest = p.partition("Nur diese Felder sind leer")
    zeile = rest.split(".")[0]
    assert "hersteller_adresse" not in zeile


def test_notifizierte_stelle_nur_wenn_pflichtig():
    """Nr. 7 gilt „soweit zutreffend" — eine Erklärung für ein selbst
    bewertetes Produkt braucht den Block nicht. Ihn trotzdem zu verlangen
    hiesse, eine Rechtspflicht zu erfinden."""
    ohne = build_konformitaetserklaerung_prompt(PROJEKT, {}, [], doc=_voll(),
                                                nb_pflichtig=False)
    mit = build_konformitaetserklaerung_prompt(PROJEKT, {}, [], doc=_voll(),
                                               nb_pflichtig=True)
    assert "nb_kennnummer" not in ohne.split("Antworte")[0]
    assert "nb_kennnummer" in mit.split("Antworte")[0]


def test_pflichtliste_stammt_aus_dem_katalog():
    """Eine zweite Liste für dieselbe Rechtspflicht wäre die Spiegel-Liste aus
    #1731/#1735 — und gepflegt würde nur eine."""
    from cra.doc_export import ANHANG_V

    p = build_konformitaetserklaerung_prompt(PROJEKT, {}, [], doc=_voll(),
                                             nb_pflichtig=True)
    for a in ANHANG_V:
        if a.bedingt == "nb":
            continue
        assert a.bezeichnung in p, f"Anhang-V-Angabe fehlt im Prompt: {a.bezeichnung}"


def test_fehlende_pflichtfelder_ist_die_eine_quelle():
    """Der Prompt benennt genau das, was auch `ausstellen()` prüft (#1814)."""
    from cra.doc_export import fehlende_pflichtfelder

    doc = _voll()
    doc["gegenstand"] = ""
    erwartet = {f for e in fehlende_pflichtfelder(doc, nb_pflichtig=False)
                for f in e["felder"]}
    p = build_konformitaetserklaerung_prompt(PROJEKT, {}, [], doc=doc,
                                             nb_pflichtig=False)
    for feld in erwartet:
        assert feld in p
