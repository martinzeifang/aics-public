"""Die englischen Felder des Dokumenten-Katalogs kommen an (#2089).

DER BEFUND
----------
``shared/documents/catalog.py`` führt je ``DocSpec`` fünf englische Felder
(``titel_en``, ``beschreibung_en``, ``erklaerung_en``, ``kategorie_en``,
``rechtsgrundlage_en``) und je ``ChecklistItem`` zwei (``label_en``,
``rechtsbezug_en``) — **170 von 212 gefüllt**, DSGVO vollständig.

Gelesen hat sie **niemand**. ``get_catalog``/``get_doc_spec``/``get_checklist``
hatten keinen ``sprache``-Parameter, und die Übersetzungsschicht war
ausdrücklich für diesen Katalog erweitert worden
(``katalog_sprache.UEBERSETZBAR`` nennt ``erklaerung``, ``kategorie``,
``rechtsgrundlage``, ``rechtsbezug`` mit genau dieser Begründung im
Kommentar). Dieselbe Fehlerklasse wie #1735 (die Vorlage wirkte nur im
Test-Export) und #1841 (das Budget kam nie an): Die Arbeit war getan, sie kam
nur nirgends an.

**Zwei Sprachkanäle, die auseinanderlaufen dürfen** (#1954): Die Oberfläche
folgt dem Bediener, das **gedruckte** Dokument dem Mandanten. Ein deutscher
Bearbeiter arbeitet für einen englischen Mandanten — deshalb nimmt der
REST-Layer ``anzeige_sprache()`` und der Export-/Vorlagenweg
``inhalt_fuer_projekt``.
"""
from __future__ import annotations

import ast
import io
import zipfile
from pathlib import Path

import pytest

from shared.documents import catalog as dcat
from tests.i18n_text import python_programm

REPO = Path(__file__).resolve().parents[1]
MODULE = ("cra", "nis2", "ai_act", "dsgvo", "wiba")


def test_ohne_sprache_ist_der_katalog_unveraendert():
    """Die Zusage, die jeden Bestandstest zum Regressionsschutz macht."""
    for modul in MODULE:
        assert dcat.get_catalog(modul) == dcat.get_catalog(modul, "")
        assert dcat.get_catalog(modul) == dcat.get_catalog(modul, "de")


def test_die_englischen_felder_kommen_an():
    """Vorher: 170 gefüllte Felder, 0 Leser."""
    getroffen = 0
    for modul in MODULE:
        for spec in dcat.get_catalog(modul, "en"):
            de = dcat.get_doc_spec(modul, spec["doc_type"]) or {}
            for feld in ("titel", "beschreibung", "erklaerung", "kategorie",
                         "rechtsgrundlage"):
                if de.get(f"{feld}_en"):
                    assert spec.get(feld) == de[f"{feld}_en"], (
                        f"{modul}/{spec['doc_type']}.{feld}")
                    getroffen += 1
    assert getroffen >= 100, f"nur {getroffen} Felder wirken"


def test_auch_die_checkliste():
    getroffen = 0
    for modul in MODULE:
        for spec in dcat.get_catalog(modul):
            de = dcat.get_checklist(modul, spec["doc_type"])
            en = dcat.get_checklist(modul, spec["doc_type"], "en")
            assert len(de) == len(en)
            for a, b in zip(de, en):
                assert a["id"] == b["id"], "die ID ist ein Schlüssel"
                for feld in ("label", "rechtsbezug"):
                    if a.get(f"{feld}_en"):
                        assert b.get(feld) == a[f"{feld}_en"]
                        getroffen += 1
    assert getroffen >= 20, f"nur {getroffen} Checklisten-Felder wirken"


def test_doc_type_und_id_bleiben_unberuehrt():
    """Sie sind **Schlüssel** in ``<modul>_managed_docs``.

    Ein übersetzter ``doc_type`` lässt jedes gespeicherte Dokument verwaisen —
    dieselbe Klasse wie eine übersetzte Anforderungs-ID (#1954).
    """
    for modul in MODULE:
        de = {s["doc_type"] for s in dcat.get_catalog(modul)}
        en = {s["doc_type"] for s in dcat.get_catalog(modul, "en")}
        assert de == en, modul


def test_eine_fehlende_uebersetzung_faellt_auf_deutsch_zurueck():
    """Nicht auf leer: Ein Dokumenttyp ohne Titel wäre eine Zeile ohne Namen."""
    for modul in MODULE:
        for spec in dcat.get_catalog(modul, "en"):
            assert str(spec.get("titel") or "").strip(), (
                f"{modul}/{spec['doc_type']} ohne Titel")


def test_der_rest_layer_nimmt_die_anzeigesprache():
    """Die Oberfläche folgt dem Bediener, nicht dem Mandanten."""
    programm = python_programm(REPO / "server/api/documents/__init__.py")
    assert "anzeige_sprache" in programm
    baum = ast.parse(programm)
    ohne: list[str] = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        fn = knoten.func
        name = getattr(fn, "attr", None)
        if name in ("get_catalog", "get_doc_spec", "get_checklist"):
            if len(knoten.args) < (2 if name == "get_catalog" else 3):
                ohne.append(ast.unparse(knoten)[:70])
    assert not ohne, f"Katalog-Zugriff ohne Sprache: {ohne}"


def test_das_gedruckte_dokument_folgt_dem_mandanten():
    """Nicht dem Bediener — das Papier gibt der Mandant heraus (#1778)."""
    programm = python_programm(REPO / "server/api/documents/__init__.py")
    assert "inhalt_fuer_projekt" in programm
    for modul in MODULE:
        prog = python_programm(REPO / modul / "template_context.py")
        assert "_dok_sprache" in prog, modul
    vorl = python_programm(REPO / "shared/documents/vorlage.py")
    assert "_inhalt_sprache" in vorl and "_anzeige_sprache" in vorl


@pytest.mark.parametrize("sprache,erwartet,nicht", [
    ("de", "Rechtsgrundlage", "Legal basis"),
    ("en", "Legal basis", "Rechtsgrundlage"),
])
def test_die_kopfzeile_des_dokuments_ist_uebersetzt(sprache, erwartet, nicht):
    """Sie stand als deutsches Literal im f-String — in einem Papier für den
    Mandanten. Geprüft wird im **erzeugten DOCX**, nicht am Katalog: Ein
    Katalog, der nicht gedruckt wird, ist der Befund selbst."""
    from shared.documents.export import render_document_docx

    rohdaten = render_document_docx({
        "titel": "X", "content_html": "<p>a</p>", "rechtsgrundlage": "Art. 30",
        "status": "freigegeben", "version": 2, "sprache": sprache,
        "meta": {"projekt": "P", "vertraulich": True}})
    xml = zipfile.ZipFile(io.BytesIO(rohdaten)).read(
        "word/document.xml").decode("utf-8")
    assert erwartet in xml
    assert nicht not in xml
