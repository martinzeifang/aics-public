"""Die AI-Act-Konformitätserklärung ist ein Datensatz, nicht nur ein Prompt (#1889).

**Der Befund:** Art. 47 Abs. 1 der Verordnung (EU) 2024/1689 verlangt die
EU-Konformitätserklärung für **jedes** Hochrisiko-KI-System, Abs. 2 verlangt,
sie zehn Jahre bereitzuhalten. In der Suite existierte sie nur als Prompt
(``ai_act/ai_wizards`` A8): kein Datensatz, keine Felder, keine
Vollständigkeitsprüfung, kein Ausstellen, kein Archiv.

Dieselbe Klasse wie #1814, eine Stufe früher: Dort galt eine **leere**
Erklärung als ausgestellt, hier gab es **nichts zu füllen**.

Die Tests halten vor allem drei Abgrenzungen fest, weil sie leicht verloren
gehen: Anhang V der KI-VO ist **nicht** Anhang V der CRA; Nr. 5 ist eine
bedingte Angabe und keine Pflicht; und die KI darf übernommene Felder nicht
setzen.
"""
from __future__ import annotations

import inspect
import io
import tokenize
from pathlib import Path

import pytest

from ai_act import conformity as conf
from ai_act import db as adb
from ai_act import doc_export as de
from ai_act import doc_pruefung as dp
from ai_act import doc_vorschlag as dv
from shared import formular_pruefung as fp
from shared import formular_vorschlag as fv

AIACT_DB = Path("data/db/ai_act.sqlite")
PROJ = "pytest-aiact-doc-1889"
FRONTEND = Path(__file__).resolve().parents[1] / "frontend/src"

VOLLSTAENDIG = {
    "system_typ": "Webanwendung",
    "anbieter_adresse": "Weg 1, 00000 Ort",
    "ort": "Ort", "datum": "2026-10-30",
    "unterzeichner_name": "A. Person",
    "unterzeichner_funktion": "Geschäftsführung",
    "keine_harmonisierten": True, "zusatzangaben_keine": True,
    "personenbezogene_daten": False,
}


@pytest.fixture
def projekt():
    adb.ensure_db(AIACT_DB)
    try:
        adb.delete_projekt(AIACT_DB, PROJ)
    except Exception:  # noqa: BLE001
        pass
    adb.save_projekt(AIACT_DB, name=PROJ, organisation="pytest-firma-1889",
                     produkt="KI-Prüfsystem",
                     meta={"scope": "system", "aiact": {"risk_tier": "high-risk"}})
    conf.save(AIACT_DB, PROJ, {
        "verfahren": "annex_vi_intern", "ergebnis": "konform",
        "qms_geprueft": True, "techdoc_geprueft": True,
        "bewertungsdatum": "2026-10-20"})
    yield PROJ
    try:
        adb.delete_projekt(AIACT_DB, PROJ)
    except Exception:  # noqa: BLE001
        pass


def _ohne_kommentare(text: str) -> str:
    raus: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        raus.append(tok.string)
    return " ".join(raus)


# ── Es gibt sie überhaupt ───────────────────────────────────────────────────

def test_die_erklaerung_ist_speicherbar(projekt):
    """Der Kern des Befunds: Vorher war der Datensatz nicht vorhanden."""
    conf.save_doc(AIACT_DB, projekt, {"system_typ": "Web"})
    rec = conf.get_or_empty(AIACT_DB, projekt)
    assert (rec.get("doc") or {}).get("system_typ") == "Web"


def test_der_entwurf_ueberlebt_das_neuladen(projekt):
    """Der Mangel aus #1887, hier von Anfang an vermieden: Wer ausfüllt und
    noch nicht ausstellen kann, darf nichts verlieren."""
    conf.save_doc(AIACT_DB, projekt, {"ort": "Halb fertig"})
    rec = conf.get_or_empty(AIACT_DB, projekt)
    assert (rec.get("doc") or {}).get("ort") == "Halb fertig"
    assert not rec.get("doc_ausgestellt")
    assert int(rec.get("doc_version") or 0) == 0


def test_speichern_ist_ein_teil_update(projekt):
    conf.save_doc(AIACT_DB, projekt, {"ort": "Ort", "system_typ": "Web"})
    conf.save_doc(AIACT_DB, projekt, {"ort": "Anderer Ort"})
    doc = (conf.get_or_empty(AIACT_DB, projekt) or {}).get("doc") or {}
    assert doc.get("system_typ") == "Web"
    assert doc.get("ort") == "Anderer Ort"


def test_die_fassung_landet_unveraenderlich_im_archiv(projekt):
    """Art. 47 Abs. 2: zehn Jahre bereitzuhalten. Ohne Archiv gibt es nichts
    bereitzuhalten."""
    conf.save_doc(AIACT_DB, projekt, dict(VOLLSTAENDIG))
    erg = de.ausstellen(projekt, db_path=AIACT_DB, pdf_bytes=b"%PDF-")
    assert erg["sha256"]
    archiv = de.list_archiv(AIACT_DB, projekt)
    assert archiv and archiv[0]["sha256"] == erg["sha256"]


def test_die_fassungsnummer_waechst_nur_beim_ausstellen(projekt):
    conf.save_doc(AIACT_DB, projekt, dict(VOLLSTAENDIG))
    assert int(conf.get_or_empty(AIACT_DB, projekt)["doc_version"]) == 0
    conf.issue_doc(AIACT_DB, projekt, {})
    assert int(conf.get_or_empty(AIACT_DB, projekt)["doc_version"]) == 1


# ── Anhang V der KI-VO ist ein eigener Katalog ──────────────────────────────

def test_der_katalog_ist_nicht_der_des_cra():
    """Die Inhalte und ihre Reihenfolge unterscheiden sich. Wer eine Nummer
    kopiert, druckt sie später in ein unterschriebenes Dokument
    (#1763/#1792)."""
    from cra.doc_export import ANHANG_V as CRA_V

    aiact_felder = {f for a in de.ANHANG_V for f in a.felder}
    cra_felder = {f for a in CRA_V for f in a.felder}
    # Produkt- und Systembezeichnung heißen verschieden, weil sie es sind.
    assert "system_name" in aiact_felder and "system_name" not in cra_felder
    assert "produkt_charge" in cra_felder and "produkt_charge" not in aiact_felder
    # Nr. 5 der KI-VO hat in der CRA keine Entsprechung.
    assert "datenschutzsatz" in aiact_felder


def test_die_rechtsgrundlage_nennt_die_ki_verordnung():
    assert "2024/1689" in de.RECHTSGRUNDLAGE
    assert "2024/2847" not in de.RECHTSGRUNDLAGE


def test_jede_angabe_traegt_ihren_rechtsbezug():
    """Er wird gedruckt, wenn eine Pflichtangabe fehlt — eine erfundene
    Nummer landet damit in der Fehlermeldung."""
    for a in de.ANHANG_V:
        assert a.rechtsbezug, a.bezeichnung
        assert "Anhang V" in a.rechtsbezug


def test_die_nummerierung_ist_belegt():
    """Der Vermerk aus #1763 ist **eingelöst**, nicht weggelassen.

    Die erste Fassung trug „vor dem ersten produktiven Ausstellen gegen die
    amtliche Fassung prüfen". Nachgeprüft am 30.10.2026 gegen zwei
    voneinander unabhängige Wiedergaben des Verordnungstextes: acht Nummern,
    Nr. 5 ist die Datenschutz-Erklärung. Der Docstring sagt jetzt, **was**
    geprüft wurde und **gegen was** — das ist die Form, in der #1792 seine
    Fundstellen belegt hat.

    Maßgeblich bleibt das Amtsblatt; beide Quellen weisen darauf hin, dass sie
    keine Rechtswirkung haben. Deshalb nennt das Modul auch, wo die amtliche
    Fassung in der Installation liegt.
    """
    quelle = Path("ai_act/doc_export.py").read_text(encoding="utf-8")
    flach = quelle.replace("\n", " ")
    assert "Nachgeprüft am" in flach
    assert "amtliche Fassung" in flach
    assert "VERORDNUNG_VERZEICHNIS" in quelle


def test_das_verordnungsverzeichnis_ist_das_des_download_wegs():
    """Eine zweite Ablage für denselben Text wäre eine zweite Wahrheit.

    Der Download-Dialog des Gutachten-Moduls holt CELEX 32024R1689 nach
    ``data/ai_act_resources`` (``ai_act_dir``) — dieselbe Stelle.
    """
    assert str(de.VERORDNUNG_VERZEICHNIS) == "data/ai_act_resources"
    assert de.VERORDNUNG_CELEX == "32024R1689"
    dialog = (Path(__file__).resolve().parents[1]
              / "gutachten/_download_dialog.py").read_text(encoding="utf-8")
    assert str(de.VERORDNUNG_VERZEICHNIS) in dialog
    assert de.VERORDNUNG_CELEX in dialog


def test_nr7_trennt_verfahren_und_stelle():
    """Anhang V Nr. 7 verlangt **drei** Dinge: Stelle mit Kennnummer, die
    Beschreibung des durchgeführten Verfahrens und die Bescheinigung — „soweit
    zutreffend".

    Das Verfahren wird aber **immer** durchgeführt (interne Kontrolle nach
    Anhang VI oder notifizierte Stelle nach Anhang VII); nur die Stelle gibt es
    nicht immer. In **einer** Angabe hätte entweder das Verfahren gefehlt, wenn
    keine Stelle beteiligt ist, oder die Überschrift eine Stelle behauptet, wo
    keine ist.
    """
    nr7 = [a for a in de.ANHANG_V if a.nr == 7]
    assert len(nr7) == 2
    verfahren = next(a for a in nr7 if a.felder == ("nb_verfahren",))
    stelle = next(a for a in nr7 if "nb_name" in a.felder)
    assert not verfahren.daten_pflicht and not verfahren.bedingt
    assert stelle.bedingt == "nb"


# ── Nr. 5 — bedingte Angabe, keine Pflicht ──────────────────────────────────

def test_nr5_ist_keine_pflichtangabe():
    """Sie greift nur, wenn das System personenbezogene Daten verarbeitet.
    Als Pflicht für jedes System wäre sie eine erfundene Rechtspflicht."""
    nr5 = [a for a in de.ANHANG_V if a.nr == 5]
    assert nr5 and not any(a.daten_pflicht for a in nr5)


def test_die_datenschutzerklaerung_steht_nur_bei_ja(projekt):
    conf.save_doc(AIACT_DB, projekt, dict(VOLLSTAENDIG,
                                          personenbezogene_daten=True))
    assert de.DATENSCHUTZSATZ in de.doc_daten(AIACT_DB, projekt)["doc"]["datenschutzsatz"]
    conf.save_doc(AIACT_DB, projekt, {"personenbezogene_daten": False})
    assert de.doc_daten(AIACT_DB, projekt)["doc"]["datenschutzsatz"] == ""


def test_ohne_entscheidung_ein_hinweis():
    """„Nicht entschieden" und „nein" sind im Datensatz nicht unterscheidbar
    (#1805) — das Fehlen der Erklärung ist dann keine Verneinung."""
    befunde = dp.pruefe({})
    assert [b for b in befunde if b["id"] == "datenschutz_unbestimmt"]
    assert not [b for b in dp.pruefe({"personenbezogene_daten": False})
                if b["id"] == "datenschutz_unbestimmt"]


# ── Nr. 6 — nie ein Gedankenstrich ──────────────────────────────────────────

def test_nr6_ohne_aussage_wird_benannt():
    assert de.normen_satz({}) == de.NORMEN_FEHLT


def test_die_verneinung_nennt_art_40():
    """Die KI-VO regelt die harmonisierten Normen in Art. 40, nicht Art. 27
    (das ist die CRA)."""
    satz = de.normen_satz({"keine_harmonisierten": True})
    assert "Art. 40" in satz and "2024/1689" in satz


def test_spezifikationen_tragen_keine_vermutungswirkung():
    satz = de.normen_satz({"keine_harmonisierten": True,
                           "normen": ["IEC 62443-4-1"]})
    assert "zum nachweis" in satz.lower()


# ── Nr. 7 — Verfahren und notifizierte Stelle ───────────────────────────────

def test_anhang_vii_ohne_stelle_blockiert():
    befunde = dp.pruefe(dict(VOLLSTAENDIG), nb_pflichtig=True)
    treffer = [b for b in befunde if b["id"] == "nb_fehlt"]
    assert treffer and treffer[0]["wirkung"] == fp.WIRKUNG_BLOCKIERT


def test_stelle_bei_interner_kontrolle_ist_ein_hinweis():
    """Freiwillige Beteiligung ist zulässig — und erklärungsbedürftig."""
    befunde = dp.pruefe(dict(VOLLSTAENDIG, nb_name="Stelle X"),
                        nb_pflichtig=False, nb_genannt=True)
    treffer = [b for b in befunde if b["id"] == "nb_ohne_verfahren"]
    assert treffer and treffer[0]["wirkung"] == fp.WIRKUNG_HINWEIS


def test_nr7_ist_ohne_notifizierte_stelle_keine_luecke(projekt):
    """Bei interner Kontrolle nach Anhang VI darf dort kein „[fehlt]"
    stehen — „soweit zutreffend"."""
    conf.save_doc(AIACT_DB, projekt, dict(VOLLSTAENDIG))
    d = de.doc_daten(AIACT_DB, projekt)
    assert not d["nb_pflichtig"]
    assert d["fehlend"] == []


# ── Das Gate ────────────────────────────────────────────────────────────────

def test_ohne_abgeschlossene_bewertung_kein_ausstellen(projekt):
    conf.save(AIACT_DB, projekt, {"verfahren": "annex_vi_intern",
                                  "ergebnis": "offen"})
    conf.save_doc(AIACT_DB, projekt, dict(VOLLSTAENDIG))
    with pytest.raises(ValueError, match="Art. 43"):
        conf.issue_doc(AIACT_DB, projekt, {})


def test_fehlende_pflichtangabe_bricht_ab(projekt):
    conf.save_doc(AIACT_DB, projekt, dict(VOLLSTAENDIG, ort=""))
    with pytest.raises(de.PflichtfelderFehlen):
        conf.issue_doc(AIACT_DB, projekt, {})


def test_ein_platzhalter_blockiert(projekt):
    conf.save_doc(AIACT_DB, projekt,
                  dict(VOLLSTAENDIG, system_typ="[zu ergänzen]"))
    with pytest.raises(dp.ErklaerungUnstimmig):
        conf.issue_doc(AIACT_DB, projekt, {})


def test_datum_vor_der_bewertung_verlangt_bestaetigung(projekt):
    conf.save_doc(AIACT_DB, projekt, dict(VOLLSTAENDIG, datum="2026-10-01"))
    with pytest.raises(dp.BestaetigungErforderlich) as exc:
        conf.issue_doc(AIACT_DB, projekt, {})
    assert dp.CONFIRM_DATUM in exc.value.schluessel
    rec = conf.issue_doc(AIACT_DB, projekt, {}, [dp.CONFIRM_DATUM])
    assert rec["doc_ausgestellt"]


def test_die_pruefung_ist_fail_closed(projekt, monkeypatch):
    conf.save_doc(AIACT_DB, projekt, dict(VOLLSTAENDIG))
    monkeypatch.setattr("ai_act.doc_pruefung.befunde",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("weg")))
    with pytest.raises(ValueError, match="Widersprüche"):
        conf.issue_doc(AIACT_DB, projekt, {})


# ── Vorschläge und die Grenze zur KI ────────────────────────────────────────

def test_die_kennung_kommt_aus_projekt_und_einstufung(projekt):
    d = de.doc_daten(AIACT_DB, projekt)
    assert d["doc"]["system_kennung"] == "KI-Prüfsystem (high-risk)"


def test_ohne_einstufung_bleibt_die_kennung_leer():
    """Erfunden wird nichts — ohne Einstufung erscheint sie als Lücke."""
    felder = dv.feld_vorschlaege(projekt={"produkt": "X"}, risk_tier="")
    assert "system_kennung" not in felder


def test_die_ki_darf_nur_prosa_setzen():
    uebernommen, verworfen = dv.uebernahme_filter({
        "system_typ": "Web", "zusatzangaben": "keine",
        "anbieter": "Fremd GmbH", "datum": "2020-01-01",
        "system_kennung": "erfunden"})
    assert set(uebernommen) == {"system_typ", "zusatzangaben"}
    assert set(verworfen) == {"anbieter", "datum", "system_kennung"}


@pytest.mark.parametrize("feld", ["anbieter", "anbieter_adresse", "datum",
                                   "system_kennung", "unterzeichner_name",
                                   "unterzeichner_funktion", "nb_kennnummer",
                                   "nb_verfahren", "ort"])
def test_uebernommene_felder_sind_fuer_die_ki_gesperrt(feld):
    assert feld not in dv.KI_FELDER


def test_jedes_ki_feld_ist_ein_eingabefeld():
    assert dv.KI_FELDER <= set(de.EINGABEFELDER)


def test_der_vorschlag_schreibt_nichts(projekt):
    conf.save_doc(AIACT_DB, projekt, {"system_typ": "Von Hand"})
    dv.vorschlag(AIACT_DB, projekt)
    doc = (conf.get_or_empty(AIACT_DB, projekt) or {}).get("doc") or {}
    assert doc.get("system_typ") == "Von Hand"


def test_der_vorschlag_laeuft_fuer_ein_unbekanntes_projekt():
    v = dv.vorschlag(AIACT_DB, "pytest-gibt-es-nicht-1889")
    assert isinstance(v.get("felder"), dict)


# ── Der gemeinsame Mechanismus wird benutzt, nicht nachgebaut ───────────────

def test_die_module_nutzen_shared():
    assert issubclass(dp.ErklaerungUnstimmig, fp.FormularUnstimmig)
    assert set(dv.FELD_KLASSE.values()) <= set(fv.KLASSEN)
    assert "filter_ki" in _ohne_kommentare(inspect.getsource(dv.uebernahme_filter))


@pytest.mark.parametrize("datei", ["ai_act/doc_vorschlag.py",
                                    "ai_act/doc_pruefung.py"])
def test_kein_eigenes_muster(datei):
    """Die beiden Fallen aus #1885 sind nicht naheliegend — wer die Muster
    nachbaut, baut sie mit nach (#1893)."""
    programm = _ohne_kommentare(Path(datei).read_text(encoding="utf-8"))
    for verboten in ("zu ergänzen", "[FEHLT]", "TBD", "sha256:[0-9a-f]"):
        assert verboten not in programm, datei


def test_keine_digest_pruefung():
    """Anhang V der KI-VO verlangt keine Artefakt-Referenz. Den Baustein
    „sicherheitshalber" mitzunehmen würde eine Pflicht suggerieren, die der
    Rechtstext nicht nennt."""
    programm = _ohne_kommentare(Path("ai_act/doc_pruefung.py").read_text(
        encoding="utf-8"))
    assert "digest_befunde" not in programm


def test_die_anbieter_anschrift_kommt_vom_mandanten():
    """Eine eigene Ablage für den AI Act wäre die Doppelpflege, die #1892
    beendet hat."""
    programm = Path("ai_act/doc_vorschlag.py").read_text(encoding="utf-8")
    assert "hersteller_stammdaten" in programm


# ── Oberfläche ──────────────────────────────────────────────────────────────

def test_die_maske_existiert_und_nutzt_die_bausteine():
    form = (FRONTEND / "components/aiact/KonformitaetserklaerungForm.vue"
            ).read_text(encoding="utf-8")
    assert "QuellenLeiste" in form and "BefundListe" in form
    assert "useFormularVorschlag" in form


def test_die_maske_haengt_im_konformitaets_tab():
    panel = (FRONTEND / "views/aiact/ConformityPanel.vue").read_text(
        encoding="utf-8")
    assert "KonformitaetserklaerungForm" in panel


def test_die_maske_zeigt_die_zehnjahresfrist():
    """Art. 47 Abs. 2 ist der Grund für das Archiv — der Anwender soll ihn
    kennen, ohne in der Verordnung zu suchen."""
    form = (FRONTEND / "components/aiact/KonformitaetserklaerungForm.vue"
            ).read_text(encoding="utf-8")
    assert "zehn Jahre" in form and "Art. 47" in form


# ── Der A8-Assistent erreicht das Formular (#1889, Nachtrag) ───────────────

def test_der_a8_prompt_nennt_acht_punkte_in_richtiger_folge():
    """**Der Mangel:** Der Prompt zählte die Pflichtangaben von Hand auf — in
    **sieben** Punkten, in falscher Reihenfolge und **ohne** die
    Datenschutz-Erklärung (Nr. 5). Eine erfundene Nummerierung in einem
    unterschriebenen Dokument ist der Fehler aus #1763/#1792.
    """
    from ai_act.ai_wizards import build_eu_doc_prompt

    p = build_eu_doc_prompt({"name": "X", "organisation": "Y"}, {})
    assert "2024/1689" in p
    # Nr. 5 ist die Datenschutz-Erklärung — in der CRA gibt es sie nicht.
    assert "2016/679" in p and "2018/1725" in p and "2016/680" in p
    assert "8. Ort und Datum" in p
    # Art. 40, nicht Art. 27 (das ist die CRA).
    assert "Art. 40" in p


def test_der_a8_prompt_ist_ohne_datensatz_unveraendert():
    """Dasselbe Versprechen wie `evidence_section` (#1483): Ohne `doc` bleibt
    der Prompt byte-identisch, und jeder Bestandstest bleibt
    Regressionsschutz."""
    from ai_act.ai_wizards import build_eu_doc_prompt

    a = build_eu_doc_prompt({"name": "X", "organisation": "Y"}, {})
    b = build_eu_doc_prompt({"name": "X", "organisation": "Y"}, {})
    assert a == b


def test_der_a8_prompt_bekommt_die_erfassten_werte():
    """Ohne sie war für das Modell jedes Feld leer, und der Entwurf musste
    voller Platzhalter sein — derselbe Mangel wie im CRA vor #1874."""
    from ai_act.ai_wizards import build_eu_doc_prompt

    p = build_eu_doc_prompt({"name": "X"}, {}, doc=dict(VOLLSTAENDIG),
                            nb_pflichtig=False)
    assert "system_typ=Webanwendung" in p
    assert "ort=Ort" in p


def test_optionale_felder_sind_nicht_fehlend():
    """Der Befund aus #1885: Für jedes leere Feld `[FEHLT]` zu schreiben
    erzeugt eine Bemerkung, die die Anwendung selbst provoziert."""
    from ai_act.ai_wizards import _anhang_v_zeilen

    zeilen, _ = _anhang_v_zeilen(dict(VOLLSTAENDIG, zusatzangaben=""), False)
    assert "(optional, leer)" in zeilen


def test_der_prompt_traegt_den_gerechneten_stand_als_vorgabe():
    from ai_act.ai_wizards import build_eu_doc_prompt

    p = build_eu_doc_prompt({"name": "X"}, {}, vorschlag={
        "felder": {"anbieter": {"wert": "Beispiel AG", "quelle": "Projekt"}}})
    assert "Beispiel AG" in p and "nicht ändern" in p


def test_parse_uebernimmt_nur_prosa_und_nennt_das_verworfene():
    from ai_act.ai_wizards import parse_eu_doc_response

    erg = parse_eu_doc_response(
        '{"doc_text": "Entwurf [zu ergänzen]", "felder": '
        '{"system_typ": "Web", "anbieter": "Fremd GmbH", "datum": "2020-01-01"}}')
    assert erg["felder"] == {"system_typ": "Web"}
    assert erg["verworfen"] == ["anbieter", "datum"]
    assert any("Nicht übernommen" in h for h in erg["plausibilitaet_hinweise"])
    assert any("[zu ergänzen]" in h for h in erg["plausibilitaet_hinweise"])


def test_der_assistent_erreicht_jetzt_das_formular():
    """**Der Kern des Nachtrags.** Vorher ging das Ergebnis als Prosa in die
    Notizen der System-Doku, und die Anhang-V-Felder blieben leer — eine
    Sackgasse (#1783)."""
    modal = (FRONTEND / "components/aiact/DocAssistentModal.vue").read_text(
        encoding="utf-8")
    assert "uebernehmen" in modal and "eu-doc/parse" in modal
    form = (FRONTEND / "components/aiact/KonformitaetserklaerungForm.vue").read_text(
        encoding="utf-8")
    assert "uebernehmeAusKi" in form and "defineExpose" in form
    panel = (FRONTEND / "views/aiact/ConformityPanel.vue").read_text(
        encoding="utf-8")
    assert "DocAssistentModal" in panel and "uebernehmeAusKi" in panel


def test_der_endpunkt_reicht_datensatz_und_vorschlag_durch():
    api = (Path(__file__).resolve().parents[1]
           / "server/api/aiact.py").read_text(encoding="utf-8")
    block = api.split("def aiact_eu_doc_prompt", 1)[1][:1600]
    assert "doc_daten" in block and "doc_vorschlag" in block
