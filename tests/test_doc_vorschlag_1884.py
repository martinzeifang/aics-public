"""Anhang-V-Angaben aus den Quellen — ohne KI (#1884/#1887).

Der Wunsch aus dem Betrieb war knapp: „Nr. 4 — Gegenstand der Erklärung per
Knopfdruck füllen. Das geht meines Erachtens ohne KI nur aus den Quellen."
Dazu Nr. 1 (Charge/Version) und Nr. 6, wo ein Gedankenstrich stand.

Die Tests halten vor allem die **Grenzen** fest, weil die den Wert ausmachen:
Was nicht in der Akte steht, erscheint nicht; ein unvollständiger Digest wird
weggelassen statt angedeutet; die KI darf gerechnete Felder nicht anfassen; und
die harmonisierten Normen werden nie hergeleitet.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from cra import db as cdb
from cra import doc_export as de
from cra import doc_vorschlag as dv
from cra import konformitaet_db as kdb
from cra import normen_katalog as nk

CRA_DB = Path("data/db/cra.sqlite")
PROJ = "pytest-vorschlag-1884"
VER = "8.2.3"
DIGEST = "sha256:" + "ab" * 32


@pytest.fixture
def projekt():
    cdb.ensure_db(CRA_DB)
    cdb.delete_projekt(CRA_DB, PROJ)
    cdb.save_projekt(CRA_DB, PROJ, unternehmen="pytest-firma-1884",
                     produkt="Testprodukt",
                     beschreibung="Webanwendung für Prüfzwecke")
    yield PROJ
    cdb.delete_projekt(CRA_DB, PROJ)


# ── Nr. 1 — Charge, Serie oder Version ──────────────────────────────────────

def test_charge_nimmt_die_version_des_vorgangs():
    assert dv.charge(release_version="8.2.3") == "Version 8.2.3"


def test_charge_faellt_auf_die_abgeleitete_version_zurueck():
    assert dv.charge(abgeleitete_version="v1.0") == "Version 1.0"


def test_der_vorgang_hat_vorrang_vor_der_abgeleiteten_version():
    """Ein Vorgang bezeichnet genau einen Stand — die abgeleitete Version ist
    die des Produkts und wäre im Vorgang die falsche Angabe."""
    assert dv.charge(release_version="8.2.3",
                     abgeleitete_version="9.0.0") == "Version 8.2.3"


def test_ohne_version_bleibt_die_charge_leer():
    """Kein Platzhalter. Eine erfundene Version in einer unterschriebenen
    Erklärung ist schlimmer als ein leeres Feld."""
    assert dv.charge() == ""


def test_die_charge_wird_in_doc_daten_abgeleitet(projekt):
    """#1886: Die Version tippt niemand mehr — sie kommt aus der Zeile."""
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A"})
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    d = de.doc_daten(CRA_DB, projekt, VER)
    assert d["doc"]["produkt_charge"] == f"Version {VER}"


def test_eine_ausdrueckliche_charge_bleibt_stehen(projekt):
    """Nach einer wesentlichen Änderung kann eine abweichende Bezeichnung nötig
    sein. Vorbelegen heißt nicht überschreiben."""
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A"})
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    kdb.save_doc(CRA_DB, projekt, {"produkt_charge": "Serie B"}, VER)
    d = de.doc_daten(CRA_DB, projekt, VER)
    assert d["doc"]["produkt_charge"] == "Serie B"


# ── Nr. 4 — Gegenstand der Erklärung ────────────────────────────────────────

def test_gegenstand_nennt_produkt_release_zweck_und_artefakt():
    g = dv.gegenstand(
        produkt="AI Compliance Suite", beschreibung="Webanwendung",
        version=VER, bereitstellung="Container-Image (On-Premises)",
        versionsanzeige="Über",
        artefakte=[{"name": "aics", "referenz": "ghcr.io/x/aics:8.2.3",
                    "digest": DIGEST, "format": "spdx"}])
    t = g["text"]
    assert "AI Compliance Suite" in t and f"Release {VER}" in t
    assert "Webanwendung" in t and "Container-Image (On-Premises)" in t
    assert "ghcr.io/x/aics:8.2.3" in t and DIGEST in t
    assert "SPDX" in t and "Attestierung" in t
    assert "Über" in t
    assert g["fehlend"] == []


def test_alle_artefakte_erscheinen():
    """#1771: Ein Produkt besteht oft aus Anwendung, Webserver und Agent. Nur
    das erste zu nennen wäre eine unvollständige Bezeichnung des Gegenstands."""
    g = dv.gegenstand(produkt="P", version=VER, artefakte=[
        {"name": "app", "referenz": "ghcr.io/x/app:8.2.3", "digest": DIGEST},
        {"name": "nginx", "referenz": "ghcr.io/x/nginx:8.2.3", "digest": DIGEST}])
    assert "app" in g["text"] and "nginx" in g["text"]


def test_ein_unvollstaendiger_digest_wird_weggelassen_und_benannt():
    """Der erste Befund aus #1885: „sha256:…" ist ein Platzhalter. Er darf im
    Vorschlag nicht entstehen — und die Auslassung muss sichtbar sein."""
    g = dv.gegenstand(produkt="P", version=VER, artefakte=[
        {"name": "app", "referenz": "ghcr.io/x/app:8.2.3", "digest": "sha256:kurz"}])
    assert "sha256:kurz" not in g["text"]
    assert "Digest" not in g["text"]
    assert any(f["feld"] == "digest" for f in g["fehlend"])


def test_ohne_digest_keine_aussage_zur_sbom_bindung():
    """Belegt ist die Bindung über den Abrufweg (cosign-Tag am Digest). Ohne
    gespeicherten Digest gibt es keinen Beleg — und damit keinen Satz."""
    g = dv.gegenstand(produkt="P", version=VER, artefakte=[
        {"name": "app", "referenz": "ghcr.io/x/app:8.2.3", "digest": ""}])
    assert "Attestierung" not in g["text"]


def test_ohne_erfasste_versionsanzeige_entfaellt_der_satz():
    """Zweiter Befund aus #1885: eine Behauptung über das Produkt braucht eine
    Grundlage in der Akte."""
    g = dv.gegenstand(produkt="P", version=VER)
    assert "installierte Version" not in g["text"]
    assert any(f["feld"] == "versionsanzeige" for f in g["fehlend"])


def test_jede_aussage_traegt_eine_fundstelle():
    g = dv.gegenstand(produkt="P", beschreibung="B", version=VER,
                      bereitstellung="Container", versionsanzeige="Über",
                      artefakte=[{"name": "a", "referenz": "ghcr.io/x/a:8.2.3",
                                  "digest": DIGEST, "format": "spdx"}])
    quellen = {f["quelle"] for f in g["fundstellen"]}
    assert {"projekt", "release", "sbom", "registry"} <= quellen


# ── Nr. 6 — Normen und Spezifikationen ──────────────────────────────────────

def test_nr6_ist_nie_ein_gedankenstrich():
    """Der gemeldete Befund: „‚--' wörtlich übernommen". Ein Strich sagt weder,
    dass nichts angewandt wurde, noch dass die Angabe fehlt."""
    assert de.normen_satz({}) == de.NORMEN_FEHLT
    assert "—" != de.normen_satz({})


def test_die_verneinung_ist_eine_aussage():
    satz = de.normen_satz({"keine_harmonisierten": True})
    assert "keine harmonisierten Normen" in satz
    assert "Art. 27" in satz


def test_verneinung_und_spezifikationen_stehen_zusammen():
    satz = de.normen_satz({"keine_harmonisierten": True,
                           "normen": ["IEC 62443-4-1"]})
    assert "keine harmonisierten Normen" in satz
    assert "IEC 62443-4-1" in satz
    # Die Spezifikationen tragen **keine** Vermutungswirkung — der Satz darf sie
    # nicht als harmonisierte Normen ausgeben.
    assert "angewandte harmonisierte Normen: IEC" not in satz


def test_der_katalog_trennt_vermutungswirkung():
    """Eine harmonisierte Norm trägt Konformitätsvermutung (Art. 27), eine
    sonstige Spezifikation nicht. Beides in eine Liste zu werfen ließe die
    Erklärung eine Rechtswirkung behaupten, die nicht besteht."""
    gruppen = {g["id"]: g for g in nk.katalog()["gruppen"]}
    assert set(gruppen) == {"harmonisiert", "spezifikation"}
    assert all(n["vermutung"] for n in gruppen["harmonisiert"]["normen"])
    assert not any(n["vermutung"] for n in gruppen["spezifikation"]["normen"])


def test_zur_cra_ist_keine_harmonisierte_norm_gelistet():
    """Nach heutigem Stand gibt es keine. Ein Eintrag hier wäre eine erfundene
    Rechtsgrundlage (die Lehre aus #1763/#1792)."""
    assert nk.HARMONISIERT == ()
    assert nk.STAND


def test_kein_eintrag_behauptet_eine_amtsblatt_fundstelle():
    """Die Bezeichnung ist eine Tatsache, eine Fundstelle eine Rechtsaussage.
    Solange die zweite nicht geprüft ist, steht sie nicht im Katalog."""
    for n in nk.ALLE:
        assert "Amtsblatt" not in n.bezeichnung
        assert "ABl." not in n.bezeichnung


def test_en18031_ist_fuer_die_cra_keine_harmonisierte_norm():
    """Sie ist unter der Funkanlagen-Richtlinie harmonisiert, nicht unter der
    CRA — die Unterscheidung entscheidet über die Vermutungswirkung."""
    n = nk.nach_id("en-18031")
    assert n is not None and not n.vermutung
    assert "2014/53/EU" in n.hinweis


def test_kandidaten_kommen_nur_aus_belegen():
    kand = dv.normen_kandidaten(owasp_bewertet=3, sbom_formate=("spdx",))
    ids = {k["id"] for k in kand}
    assert "owasp-pc" in ids and "spdx" in ids
    assert all(k["herkunft"] for k in kand)


def test_ohne_belege_keine_kandidaten():
    assert dv.normen_kandidaten() == []


def test_harmonisierte_normen_werden_nie_hergeleitet():
    """Der folgenschwerste Fehler, den dieses Modul machen könnte."""
    kand = dv.normen_kandidaten(owasp_bewertet=9, sbom_formate=("spdx", "cyclonedx"),
                                threat_framework="STRIDE", wiba_projekt="X")
    assert all(k["gruppe"] == nk.GRUPPE_SPEZIFIKATION for k in kand)


def test_wiba_belegt_kein_iso_27001():
    """WiBA ist das BSI-Vorgehen zur Basis-Absicherung und kein Nachweis einer
    ISO-27001-Anwendung. Eine solche Herleitung wäre eine stille Behauptung."""
    ids = {k["id"] for k in dv.normen_kandidaten(wiba_projekt="X")}
    assert "iso-iec-27001" not in ids


# ── Feldvorschläge und die Grenze zur KI (#1887) ────────────────────────────

def test_jedes_feld_mit_quelle_traegt_wert_quelle_und_klasse():
    f = dv.feld_vorschlaege(
        projekt={"produkt": "P", "unternehmen": "U"},
        hersteller_stamm={"anschrift": "A", "ort": "O"},
        bewertungsweg="A", release_version=VER, heute="2026-10-30")
    for feld, eintrag in f.items():
        assert eintrag["wert"], feld
        assert eintrag["quelle"], feld
        assert eintrag["klasse"] in ("gerechnet", "uebernommen", "auswahl", "ki"), feld


def test_ein_feld_ohne_quelle_erscheint_nicht():
    """Ein leerer Vorschlag mit Quellenangabe wäre ein Angebot ins Nichts."""
    f = dv.feld_vorschlaege(projekt={})
    assert "hersteller_adresse" not in f
    assert "produkt_charge" not in f


def test_die_ki_darf_nur_prosa_setzen():
    """Die wichtigste Grenze: Ein Modell, das „Release 8.0.11" plausibel
    findet, erzeugt genau den Fall aus #1885 — nur sieht es wie eine Aussage
    aus."""
    uebernommen, verworfen = dv.uebernahme_filter({
        "produkt_typ": "Webanwendung", "zusatzangaben": "keine",
        "gegenstand": "Text", "produkt_charge": "Version 9.9.9",
        "hersteller": "Fremd GmbH", "datum": "2020-01-01",
        "unterzeichner_name": "Niemand"})
    assert set(uebernommen) == {"produkt_typ", "zusatzangaben", "gegenstand"}
    assert set(verworfen) == {"produkt_charge", "hersteller", "datum",
                              "unterzeichner_name"}


@pytest.mark.parametrize("feld", ["produkt_charge", "hersteller",
                                  "hersteller_adresse", "datum",
                                  "unterzeichner_name", "unterzeichner_funktion",
                                  "nb_kennnummer", "nb_verfahren", "ort"])
def test_gerechnete_und_uebernommene_felder_sind_fuer_die_ki_gesperrt(feld):
    """Wächter: Wandert eines dieser Felder in ``KI_FELDER``, wird dieser Test
    rot. Sonst fiele die Grenze unbemerkt."""
    assert feld not in dv.KI_FELDER


def test_jedes_ki_feld_ist_ein_eingabefeld():
    assert dv.KI_FELDER <= set(de.EINGABEFELDER)


# ── Der Weg ist ohne KI ─────────────────────────────────────────────────────

@pytest.mark.parametrize("modul", [dv, nk])
def test_kein_eigener_ki_transport(modul):
    """Der Wunsch war ausdrücklich „ohne KI". Ein Wächter, der das festhält,
    verhindert, dass hier später ein Lauf einzieht (Muster
    ``test_hilfe_fragen_1878``)."""
    quelle = inspect.getsource(modul)
    for verboten in ("requests.post", "ki_lauf", "generate_text", "ollama",
                     "run-stream"):
        assert verboten not in quelle, f"{modul.__name__} spricht mit der KI"


def test_der_vorschlag_schreibt_nichts(projekt):
    """Rein lesend. Ein gefülltes Feld ist die Aussage eines Menschen; es beim
    Öffnen zu ersetzen wäre der Fehler aus #1769/#1773."""
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A"})
    kdb.save_doc(CRA_DB, projekt, {"gegenstand": "Von Hand erfasst"})
    dv.vorschlag(CRA_DB, projekt, "")
    rec = kdb.get_konformitaet(CRA_DB, projekt, "") or {}
    assert (rec.get("doc") or {}).get("gegenstand") == "Von Hand erfasst"


def test_vorschlag_liefert_felder_katalog_und_klassen(projekt):
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A"})
    v = dv.vorschlag(CRA_DB, projekt, "")
    assert "felder" in v and "katalog" in v and "unionsrecht" in v
    assert v["klassen"] and v["ki_felder"] == sorted(dv.KI_FELDER)


def test_vorschlag_laeuft_auch_fuer_ein_unbekanntes_projekt():
    """Jede Teilquelle ist einzeln abgesichert — eine Erklärung muss auch dann
    vorbereitbar sein, wenn ein Register leer ist."""
    v = dv.vorschlag(CRA_DB, "pytest-gibt-es-nicht-1884", "")
    assert isinstance(v.get("felder"), dict)


# ── Der Digest wird behalten ────────────────────────────────────────────────

def test_der_digest_wird_gespeichert_und_bleibt_bei_teil_updates(projekt):
    """Der Komponenten-Import zieht ``komponenten_count`` mit einem Teil-Dict
    nach. Ohne Schutz wäre der Digest danach weg und der Gegenstand der
    Erklärung nicht mehr belegt (dieselbe Falle wie ``artefakt`` in #1771)."""
    sid = cdb.save_sbom(CRA_DB, projekt, {
        "release_version": VER, "sbom_format": "spdx", "artefakt": "app",
        "blob_path": "ghcr.io/x/app:8.2.3", "image_digest": DIGEST})
    cdb.save_sbom(CRA_DB, projekt, {"id": sid, "release_version": VER,
                                    "komponenten_count": 7})
    zeile = next(z for z in cdb.list_sbom(CRA_DB, projekt) if z["id"] == sid)
    assert zeile["image_digest"] == DIGEST
    assert zeile["artefakt"] == "app"


def test_der_gegenstand_nutzt_den_gespeicherten_digest(projekt):
    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A"})
    cdb.save_sbom(CRA_DB, projekt, {
        "release_version": VER, "sbom_format": "spdx", "artefakt": "app",
        "blob_path": "ghcr.io/martinzeifang/app:8.2.3", "image_digest": DIGEST})
    v = dv.vorschlag(CRA_DB, projekt, VER)
    assert DIGEST in v["gegenstand"]["text"]


# ── Die Migration, die dabei auffiel ────────────────────────────────────────

def test_neue_spalten_ueberleben_die_eindeutigkeits_migration(projekt):
    """**Der latente Defekt, den #1884 gefunden hat.**

    ``_migrate_sbom_unique`` fing den Fehler von ``ADD CONSTRAINT`` ab — in
    PostgreSQL ist die Transaktion danach aber **abgebrochen**, und mit ihr
    fiel alles weg, was ``_migrate_columns`` vorher getan hatte. Jede neue
    Spalte dieser Tabelle wurde angelegt und sofort wieder verworfen. Es fiel
    erst auf, als mit ``image_digest`` die erste neue Spalte seit #1771 kam.

    Der Test ruft ``ensure_db`` **zweimal** — beim zweiten Mal steht die
    Eindeutigkeitsregel schon, also schlägt ``ADD CONSTRAINT`` fehl. Genau
    dann muss die Spalte noch da sein.
    """
    cdb.ensure_db(CRA_DB)
    cdb.ensure_db(CRA_DB)
    sid = cdb.save_sbom(CRA_DB, projekt, {
        "release_version": VER, "image_digest": DIGEST})
    zeile = next(z for z in cdb.list_sbom(CRA_DB, projekt) if z["id"] == sid)
    assert zeile["image_digest"] == DIGEST


# ── Vierfache Verdrahtung des gerechneten Punktes ───────────────────────────

def test_der_gate_punkt_ist_vierfach_verdrahtet():
    """Ein gerechneter Punkt steht an vier Stellen — Katalog, flacher Schlüssel
    in ``evaluate()``, Auswertung in ``release_bericht`` und Fall im
    ``ReleasesPanel``. Fehlt eine, rechnet die Anwendung richtig und der
    Vorgangsbericht meldet „nicht geprüft" (#1762/#1773/#1799/#1824)."""
    from cra.release_bericht import _GERECHNET_AUSWERTUNG
    from cra.release_checkliste import KATALOG

    item = next((i for i in KATALOG if i.id == "normen_konsistent"), None)
    assert item is not None and item.quelle == "normen_widerspruch"
    assert item.art == "gerechnet"
    assert "normen_widerspruch" in _GERECHNET_AUSWERTUNG

    gate = Path("cra/konformitaet_gate.py").read_text(encoding="utf-8")
    assert '"normen_widerspruch": release_befunde.get' in gate

    panel = Path("frontend/src/views/cra/ReleasesPanel.vue").read_text(encoding="utf-8")
    assert "normen_widerspruch: 'normen_konsistent'" in panel
    assert "case 'normen_widerspruch'" in panel
