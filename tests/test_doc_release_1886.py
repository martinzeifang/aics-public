"""Die Erklärung gehört ins Release-Management — eine Maske, zwei Einstiege (#1886/#1887).

Die Frage aus dem Betrieb: „Sollte die EU-Konformitätserklärung nicht auch
besser im Release-Management (Tagesgeschäft) aufgerufen werden — zumindest im
Standard, sodass dort auch sichergestellt werden kann, dass sie für die
richtige Version ausgefüllt wird?"

Drei Dinge hielten das auf, und alle drei prüfen die Tests hier:

* ``doc_json`` stand **nicht** in ``GEERBTE_FELDER`` (#1805) — die Zeile eines
  Vorgangs war leer, und eine Eingabestelle dafür gab es nicht.
* Nr. 1 war ein Freitextfeld. Niemand hielt es nach, wenn ein Release
  herausging; genau so entstand der Fall aus #1885.
* Es gab nur „ausstellen", kein Speichern. Wer nicht fertig wurde, verlor
  beim nächsten Laden alles.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cra import db as cdb
from cra import doc_export as de
from cra import konformitaet_db as kdb

CRA_DB = Path("data/db/cra.sqlite")
PROJ = "pytest-doc-release-1886"
VER = "8.2.3"
FRONTEND = Path("frontend/src")


@pytest.fixture
def projekt():
    cdb.ensure_db(CRA_DB)
    cdb.delete_projekt(CRA_DB, PROJ)
    cdb.save_projekt(CRA_DB, PROJ, unternehmen="pytest-firma-1886",
                     produkt="Testprodukt")
    kdb.save_konformitaet(CRA_DB, PROJ, {"bewertungsweg": "A",
                                         "bewertung_abgeschlossen": True})
    yield PROJ
    cdb.delete_projekt(CRA_DB, PROJ)


def _produkt_erklaerung(projekt: str) -> None:
    """Was der Anwender im Tab „✅ Konformität" erfasst — am Produkt."""
    kdb.save_doc(CRA_DB, projekt, {
        "hersteller": "pytest-firma-1886",
        "hersteller_adresse": "Weg 1, 00000 Ort",
        "ort": "Ort", "unterzeichner_name": "A. Person",
        "unterzeichner_funktion": "Geschäftsführung",
        "normen": ["IEC 62443-4-1"], "keine_harmonisierten": True,
        "produkt_charge": "Version 8.0.11",
        "gegenstand": "Testprodukt, Release 8.0.11 – Webanwendung.",
        "datum": "2026-01-01",
    })


# ── Der Inhalt wird geerbt ──────────────────────────────────────────────────

def test_der_vorgang_erbt_die_produktangaben(projekt):
    """Ein neuer Vorgang ist sofort arbeitsfähig: Hersteller, Anschrift,
    Unterzeichner und Normen kommen vom Produkt."""
    _produkt_erklaerung(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    rec = kdb.get_konformitaet(CRA_DB, projekt, VER) or {}
    doc = rec.get("doc") or {}
    assert doc.get("hersteller_adresse") == "Weg 1, 00000 Ort"
    assert doc.get("unterzeichner_name") == "A. Person"
    assert doc.get("normen") == ["IEC 62443-4-1"]
    assert doc.get("keine_harmonisierten") is True


@pytest.mark.parametrize("feld", ["produkt_charge", "gegenstand", "datum"])
def test_stand_bezogene_felder_werden_nicht_geerbt(projekt, feld):
    """Diese drei beschreiben den **einzelnen Stand**. Geerbt stünde in der
    Erklärung für 8.2.3 weiter „Release 8.0.11" — genau der gemeldete Fall aus
    #1885, und ein vordatiertes Ausstellungsdatum dazu."""
    _produkt_erklaerung(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    rec = kdb.get_konformitaet(CRA_DB, projekt, VER) or {}
    assert not (rec.get("doc") or {}).get(feld)
    # `produkt_charge` wird nicht geerbt, aber von `doc_daten` **abgeleitet** —
    # das ist der nächste Test. Die Rohzeile bleibt leer, damit eine spätere
    # Änderung der Version nachzieht statt auf einer Kopie sitzen zu bleiben.


def test_die_version_des_vorgangs_steht_in_nr1(projekt):
    """Die Version tippt niemand mehr."""
    _produkt_erklaerung(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    d = de.doc_daten(CRA_DB, projekt, VER)
    assert d["doc"]["produkt_charge"] == f"Version {VER}"
    assert "8.0.11" not in d["doc"]["produkt_charge"]


def test_der_gegenstand_startet_leer_und_nicht_falsch(projekt):
    """Lieber ein leeres Nr. 4 mit Vorschlagsknopf als ein geerbter Text mit
    der Version des Vorgängers. Ein stiller falscher Wert sieht aus wie eine
    Aussage."""
    _produkt_erklaerung(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    d = de.doc_daten(CRA_DB, projekt, VER)
    assert "8.0.11" not in d["doc"]["gegenstand"]


def test_ein_eigener_wert_am_vorgang_bleibt_stehen(projekt):
    """Geerbt wird nur in ein leeres Feld."""
    _produkt_erklaerung(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    kdb.save_doc(CRA_DB, projekt, {"hersteller_adresse": "Anderer Weg 2"}, VER)
    rec = kdb.get_konformitaet(CRA_DB, projekt, VER) or {}
    assert (rec.get("doc") or {}).get("hersteller_adresse") == "Anderer Weg 2"


def test_das_erben_ist_keine_kopie(projekt):
    """Eine späte Änderung am Produkt zieht nach — solange am Vorgang nichts
    Eigenes steht (Lehre aus #1805)."""
    _produkt_erklaerung(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    kdb.get_konformitaet(CRA_DB, projekt, VER)        # einmal lesen = erben
    kdb.save_doc(CRA_DB, projekt, {"hersteller_adresse": "Neuer Weg 3"})
    rec = kdb.get_konformitaet(CRA_DB, projekt, VER) or {}
    assert (rec.get("doc") or {}).get("hersteller_adresse") == "Neuer Weg 3"


def test_die_fassungsnummer_wird_nicht_geerbt(projekt):
    """Jede Zeile führt ihre eigene ``doc_version``. Geerbt behauptete der
    Vorgang Ausstellungen, die es für ihn nicht gab."""
    _produkt_erklaerung(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    rec = kdb.get_konformitaet(CRA_DB, projekt, VER) or {}
    assert int(rec.get("doc_version") or 0) == 0


# ── Entwurf speichern ───────────────────────────────────────────────────────

def test_der_entwurf_ueberlebt_das_neuladen(projekt):
    """**Der Mangel:** ``doc_json`` schrieb nur ``issue_doc``, und die verlangt
    alle Pflichtangaben. Wer die Erklärung ausfüllte und noch nicht ausstellen
    konnte, verlor alles."""
    kdb.save_doc(CRA_DB, projekt, {"gegenstand": "Halb fertig"})
    rec = kdb.get_konformitaet(CRA_DB, projekt, "") or {}
    assert (rec.get("doc") or {}).get("gegenstand") == "Halb fertig"
    assert not rec.get("doc_ausgestellt")
    assert int(rec.get("doc_version") or 0) == 0


def test_speichern_ist_ein_teil_update(projekt):
    """Wer ein Feld nachreicht, verliert die übrigen nicht (#1540/#1771/#1805)."""
    kdb.save_doc(CRA_DB, projekt, {"ort": "Ort", "gegenstand": "Text"})
    kdb.save_doc(CRA_DB, projekt, {"ort": "Anderer Ort"})
    doc = (kdb.get_konformitaet(CRA_DB, projekt, "") or {}).get("doc") or {}
    assert doc.get("gegenstand") == "Text"
    assert doc.get("ort") == "Anderer Ort"


def test_ausdruecklich_leer_bleibt_leer(projekt):
    """Sonst ließe sich eine Angabe nicht zurücknehmen."""
    kdb.save_doc(CRA_DB, projekt, {"gegenstand": "Text"})
    kdb.save_doc(CRA_DB, projekt, {"gegenstand": ""})
    doc = (kdb.get_konformitaet(CRA_DB, projekt, "") or {}).get("doc") or {}
    assert doc.get("gegenstand") == ""


def test_ein_entwurf_am_vorgang_schreibt_nicht_aufs_produkt(projekt):
    _produkt_erklaerung(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    kdb.save_doc(CRA_DB, projekt, {"gegenstand": "Nur für 8.2.3"}, VER)
    produkt = (kdb.get_konformitaet(CRA_DB, projekt, "", erben=False) or {}).get("doc") or {}
    assert produkt.get("gegenstand") != "Nur für 8.2.3"


# ── Ausstellen je Version ───────────────────────────────────────────────────

def test_die_fassung_wird_unter_ihrer_version_archiviert(projekt):
    _produkt_erklaerung(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    kdb.save_doc(CRA_DB, projekt, {
        "produkt_typ": "Web", "gegenstand": f"Testprodukt, Release {VER}.",
        "datum": "2026-10-30"}, VER)
    erg = de.ausstellen(projekt, release_version=VER, db_path=CRA_DB,
                        pdf_bytes=b"%PDF-")
    assert erg["release_version"] == VER
    archiv = de.list_archiv(CRA_DB, projekt)
    assert any(a["release_version"] == VER for a in archiv)


# ── Eine Maske, zwei Einstiege ──────────────────────────────────────────────

def test_es_gibt_genau_eine_formular_komponente():
    """Eine zweite Eingabemaske am Release wäre die Falle aus #1805: zwei
    Stellen für denselben Sachverhalt, und welche gilt, wüsste niemand."""
    treffer = [p for p in FRONTEND.rglob("*.vue")
               if 'v-model="docForm.' in p.read_text(encoding="utf-8")
               or 'v-model="werte.produkt_charge"' in p.read_text(encoding="utf-8")]
    assert treffer == [FRONTEND / "components/cra/KonformitaetserklaerungForm.vue"], \
        f"Anhang-V-Felder stehen in mehr als einer Datei: {treffer}"


@pytest.mark.parametrize("datei", [
    "views/cra/KonformitaetPanel.vue",
    "views/cra/ReleasesPanel.vue",
])
def test_beide_einstiege_binden_dieselbe_komponente(datei):
    text = (FRONTEND / datei).read_text(encoding="utf-8")
    assert "KonformitaetserklaerungForm" in text


def test_im_releases_tab_ist_die_version_gebunden():
    """Die Version ist dort keine Eingabe — sie kommt aus dem Vorgang."""
    text = (FRONTEND / "views/cra/ReleasesPanel.vue").read_text(encoding="utf-8")
    assert ':release="detail?.vorgang?.release_version' in text


def test_der_konformitaets_tab_bindet_keine_version():
    """Dort gilt der Produkt-Datensatz (#1805)."""
    text = (FRONTEND / "views/cra/KonformitaetPanel.vue").read_text(encoding="utf-8")
    block = text.split("<KonformitaetserklaerungForm", 1)[1].split("/>", 1)[0]
    assert ":release" not in block


def test_es_gibt_nur_eine_pflichtfeld_quelle_im_frontend():
    """Die Anhang-V-Liste stand im Panel ein zweites Mal — eine Spiegel-Liste
    zu ``doc_export.ANHANG_V`` (#1731/#1735)."""
    panel = (FRONTEND / "views/cra/KonformitaetPanel.vue").read_text(encoding="utf-8")
    assert "DOC_PFLICHT" not in panel
    assert "Charge, Serie oder Version" not in panel


def test_der_assistent_erreicht_das_formular():
    """**Der Befund aus #1887:** Den Assistenten gab es, aber sein Ergebnis
    kam nie in den Feldern an — ein Assistent, dessen Ergebnis nicht dort
    landet, wo die Angabe gebraucht wird, ist eine Sackgasse (#1783)."""
    modal = (FRONTEND / "components/cra/DocAssistentModal.vue").read_text(encoding="utf-8")
    assert "uebernehmen" in modal
    form = (FRONTEND / "components/cra/KonformitaetserklaerungForm.vue").read_text(
        encoding="utf-8")
    assert "uebernehmeAusKi" in form and "defineExpose" in form
    for datei in ("views/cra/KonformitaetPanel.vue", "views/cra/ReleasesPanel.vue"):
        text = (FRONTEND / datei).read_text(encoding="utf-8")
        assert "uebernehmeAusKi" in text, datei


def test_die_nicht_geerbten_felder_tragen_eine_begruendung():
    """Eine Ausnahmeliste ohne Grund wird zum Teppich (#1805)."""
    quelle = Path("cra/konformitaet_db.py").read_text(encoding="utf-8")
    block = quelle.split("NICHT_GEERBTE_DOC_FELDER", 1)[0][-2000:]
    for feld in kdb.NICHT_GEERBTE_DOC_FELDER:
        assert feld in block, f"{feld} ist ohne Begründung ausgenommen"
