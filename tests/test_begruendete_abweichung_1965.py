"""#1965 — eine Begründung im Kommentarfeld begründet nichts, und das muss man sehen.

Befund aus dem Betrieb: Bei **AI1-04** standen auf Produktiv 2141 Zeichen
Begründung im Kommentarfeld der Anforderung (dazu 999 Zeichen Maßnahme). Die
Bewertung blieb bei 3, und das Release-Gate meldete die Anforderung unverändert
als **offenen Punkt** — als wäre nichts begründet.

Gemessen auf Produktiv: 0 von 117 Risiken trugen ein ``felder._source_id``,
8 waren akzeptiert und **keines** einer Anforderung zugeordnet,
``risk_requirement_links`` hatte 2 Zeilen (AI1-03, AI2-06) und keine für AI1-04.

**Die Regel bleibt.** ``cra/konformitaet_gate._accepted_gap_for`` liest den
Kommentar nicht, und das ist richtig: Eine Abweichung gilt nach CRA nur
risikobasiert begründet als konform (Art. 13 Abs. 2 und 3, #1608/#1613). Zählte
der Kommentar mit, wäre jede Anforderung mit einer Notiz „begründet", und der
Unterschied zwischen *abgewogen* (Kategorie A/B) und *beschrieben*
(Kategorie C) in ``docs/cra/abweichungen.md`` wäre dahin.

Zwei Dinge waren der Mangel:

1. **Nichts sagte es.** Dafür ``anforderungs_befund`` und der ``gate_hinweis``
   an der Speicher-Antwort.
2. **Der Verknüpfungsweg schrieb die Herkunft nicht mit.** Wer ein
   *vorhandenes* Risiko an eine Anforderung verknüpft (``…/req-risks/link``
   aus #1564), erzeugte nur eine Zeile in ``risk_requirement_links`` — und die
   liest das Gate nicht. Jetzt schreibt ``link_risk`` denselben Schlüssel, den
   das Anlegen schreibt: **eine** Quelle statt zweier Zuordnungswahrheiten
   (#1726/#1727).

Tragend ist der **Rundlauf** am Ende: Anforderung auf 3, vorhandenes Risiko
verknüpfen, akzeptieren mit Kategorie und Begründung → das Gate zählt sie als
``begruendet`` und nicht mehr als offenen Punkt. Dazu die Gegenrichtung: ein
Kommentar allein begründet nichts, auch nicht mit 2141 Zeichen.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_WURZEL = Path(__file__).resolve().parents[1]


def _programm(pfad: Path) -> str:
    """Quelltext ohne Kommentare und Docstrings.

    Für Wächter gilt: **das Programm prüfen, nicht die Erzählung** (#1834).
    Diese Datei erklärt den alten Zustand in ihren Kommentaren; ein Prüfer, der
    sie mitliest, bestätigt sich selbst.
    """
    quelle = pfad.read_text(encoding="utf-8")
    zeilen = quelle.splitlines()
    baum = ast.parse(quelle)
    for knoten in ast.walk(baum):
        koerper = getattr(knoten, "body", None)
        if not isinstance(koerper, list) or not koerper:
            continue
        erst = koerper[0]
        if (isinstance(erst, ast.Expr) and isinstance(erst.value, ast.Constant)
                and isinstance(erst.value.value, str)):
            for nr in range(erst.lineno - 1, (erst.end_lineno or erst.lineno)):
                zeilen[nr] = ""
    return re.sub(r"(?m)#.*$", "", "\n".join(zeilen))


# ── die Regel selbst (ohne Datenbank) ────────────────────────────────────────

def test_die_schwelle_steht_nur_einmal() -> None:
    """``shared`` darf nicht von einem Fachmodul abhängen, also ist die Zahl
    dort eine Kopie — dieselbe Entscheidung wie in ``shared/ki_pruefhinweise``
    (#1862). Eine Kopie ohne Prüfer ist die Spiegel-Liste aus #1731/#1735.
    """
    from cra.konformitaet_gate import _ERFUELLT_AB
    from shared.req_risks import GATE_SCHWELLE
    assert GATE_SCHWELLE["cra"] == _ERFUELLT_AB == 4


def test_module_ohne_gate_tragen_keine_schwelle() -> None:
    """Ein Hinweis auf ein Konformitäts-Gate, das es im Modul nicht gibt, wäre
    eine falsche Aussage — NIS2, DSGVO und AI Act führen kein CRA-Gate."""
    from shared.req_risks import GATE_SCHWELLE, MODULE
    assert set(GATE_SCHWELLE) == {"cra"}
    assert set(MODULE) >= {"cra", "nis2", "dsgvo", "aiact"}


def test_akzeptiert_ohne_kategorie_begruendet_nichts() -> None:
    from shared.req_risks import traegt_begruendete_abweichung as traegt
    assert traegt({"behandlung": "akzeptiert", "akzeptanz_kategorie": "restrisiko"})
    assert not traegt({"behandlung": "akzeptiert", "akzeptanz_kategorie": ""})
    assert not traegt({"behandlung": "akzeptiert", "akzeptanz_kategorie": "   "})
    assert not traegt({"behandlung": "reduziert", "akzeptanz_kategorie": "restrisiko"})
    assert not traegt({})


def test_ein_kommentar_ist_keine_begruendung() -> None:
    """Der gemeldete Datensatz: 2141 Zeichen Kommentar, Bewertung 3.

    Die Gegenrichtung des Issues, und sie ist die wichtigere Hälfte: Zählte der
    Freitext mit, wäre jede Anforderung mit einer Notiz begründet.
    """
    from cra.konformitaet_gate import _accepted_gap_for
    from shared.req_risks import traegt_begruendete_abweichung
    kommentar = "Begründung: " + "x" * 2129
    assert len(kommentar) == 2141
    risiko = {"id": 7, "behandlung": "offen", "akzeptanz_kategorie": "",
              "beschreibung": kommentar, "bewertung_text": kommentar,
              "felder": {"_source_id": "cra:requirement:AI1-04"}}
    assert not traegt_begruendete_abweichung(risiko)
    assert _accepted_gap_for("RB", "AI1-04",
                             {"cra:requirement:AI1-04": [risiko]}) is None


def test_die_herkunft_muss_auf_dieses_objekt_zeigen() -> None:
    """``felder`` hält genau **eine** Herkunft, die Verknüpfung ist n:m."""
    from shared.req_risks import quell_id, zaehlt_im_gate
    assert quell_id("cra", "requirement", "AI1-04") == "cra:requirement:AI1-04"
    akzeptiert = {"behandlung": "akzeptiert", "akzeptanz_kategorie": "restrisiko"}
    eigenes = {**akzeptiert, "felder": {"_source_id": "cra:requirement:AI1-04"}}
    fremdes = {**akzeptiert, "felder": {"_source_id": "CVE-2024-0001"}}
    andere = {**akzeptiert, "felder": {"_source_id": "cra:requirement:IMPL-06"}}
    assert zaehlt_im_gate(eigenes, "cra", "requirement", "AI1-04")
    assert not zaehlt_im_gate(fremdes, "cra", "requirement", "AI1-04")
    assert not zaehlt_im_gate(andere, "cra", "requirement", "AI1-04")
    assert not zaehlt_im_gate({**akzeptiert, "felder": {}}, "cra", "requirement", "AI1-04")


def test_gate_und_hinweis_rechnen_mit_derselben_funktion() -> None:
    """Zwei Rechenwege wären zwei Aussagen über dieselbe Anforderung
    (#1726/#1727) — und auffallen würde es erst, wenn die Maske „begründet"
    zeigt und das Gate „offen" meldet."""
    programm = _programm(_WURZEL / "cra" / "konformitaet_gate.py")
    befund = programm.split("def anforderungs_befund", 1)[1].split("\ndef ", 1)[0]
    assert "_accepted_gap_for(" in befund, (
        "`anforderungs_befund` rechnet die Begründung selbst — das ist die "
        "zweite Wahrheit, die #1965 beseitigt hat.")


# ── der Verknüpfungsweg schreibt die Herkunft (Teil 2) ───────────────────────

def test_der_verknuepfungsweg_schreibt_die_herkunft() -> None:
    """Eine Quelle, nicht zwei: Das Gate soll **nicht** zusätzlich über
    ``risk_requirement_links`` auflösen."""
    programm = _programm(_WURZEL / "shared" / "req_risks.py")
    link = programm.split("def link_risk", 1)[1].split("\ndef ", 1)[0]
    assert "setze_risiko_herkunft" in link, (
        "`link_risk` trägt die Herkunft nicht nach — eine Akzeptanz an einem "
        "so verknüpften Risiko zählt dann im Gate nicht (#1965).")
    assert "quell_id(" in link


def test_das_nachtragen_ueberschreibt_keine_fremde_herkunft() -> None:
    """Der Schlüssel trägt die *Herkunft*, nicht die Zuordnung.

    Bei einem CVE-Risiko liest ``cra/risk_import.provenance_key`` ihn zur
    Dubletten-Erkennung; ihn umzuhängen hieße, denselben CVE beim nächsten
    Abgleich doppelt aufzunehmen.
    """
    programm = _programm(_WURZEL / "risikobewertung" / "db.py")
    fn = programm.split("def setze_risiko_herkunft", 1)[1].split("\ndef ", 1)[0]
    assert '_source_id' in fn and "return False" in fn
    assert "UPDATE rb_risiken SET felder_json=" in fn, (
        "Teil-Update: Die Funktion darf nur die Herkunftsschlüssel anfassen "
        "(#1540/#1771/#1805).")


def test_das_nachziehen_der_altdaten_folgt_derselben_regel() -> None:
    """Der Code-Fix wirkt nur nach vorn.

    Für den Bestand gibt es ``scripts/ops/risiko_herkunft_nachtragen.py``
    (#1976) — und es ist **dieselbe** Regel: aus ``risk_requirement_links``
    ableiten, nur in einen leeren Platz schreiben, nichts raten. Zwei
    verschiedene Regeln für Bestand und Neuzugang wären zwei Wahrheiten über
    denselben Datensatz.
    """
    skript = _WURZEL / "scripts" / "ops" / "risiko_herkunft_nachtragen.py"
    assert skript.is_file()
    programm = _programm(skript)
    assert "risk_requirement_links" in programm
    assert 'felder.get("_source_id")' in programm, (
        "Das Werkzeug prüft nicht mehr, ob der Platz frei ist — es würde eine "
        "vorhandene Herkunft überschreiben.")


# ── der gerechnete Widerspruch (ohne Datenbank) ──────────────────────────────

def test_verknuepfte_akzeptanz_mit_fremder_herkunft_wird_benannt(monkeypatch) -> None:
    """Der stille Verlust, den #1965 übrig lässt.

    Ist der Herkunfts-Platz belegt, trägt die Verknüpfung die Akzeptanz nicht —
    der Anwender sieht an der Anforderung ein akzeptiertes Risiko und im Gate
    einen offenen Punkt. Das wird **benannt**, nicht verschwiegen.
    """
    from types import SimpleNamespace
    from shared import risk_req_links
    from cra import konformitaet_gate as kg

    monkeypatch.setattr(
        risk_req_links, "list_for_project",
        lambda *a, **k: [SimpleNamespace(modul="cra", object_kind="requirement",
                                         anforderung_id="AI1-04", risk_id=42)],
        raising=True)
    risiken = {42: {"id": 42, "behandlung": "akzeptiert",
                    "akzeptanz_kategorie": "restrisiko",
                    "felder": {"_source_id": "CVE-2024-0001"}}}
    punkte: list[dict] = []
    assert kg._check_akzeptanz_nicht_gelesen("RB", risiken, punkte) == ["AI1-04"]
    assert len(punkte) == 1
    assert "AI1-04" in punkte[0]["titel"]
    assert "Nichterfüllung" in punkte[0]["hinweis"], (
        "Der Hinweis muss den Weg nennen — sonst verknüpft der Anwender wieder, "
        "und genau das hilft nicht.")


def test_der_normalfall_schlaegt_nicht_an(monkeypatch) -> None:
    """Ein Prüfpunkt, der bei richtigem Verhalten anschlägt, wird abgeschaltet
    (die Lehre aus #1774 und #1877)."""
    from types import SimpleNamespace
    from shared import risk_req_links
    from cra import konformitaet_gate as kg

    monkeypatch.setattr(
        risk_req_links, "list_for_project",
        lambda *a, **k: [SimpleNamespace(modul="cra", object_kind="requirement",
                                         anforderung_id="AI1-04", risk_id=42)],
        raising=True)
    punkte: list[dict] = []
    # richtig verknüpft und richtig akzeptiert
    assert kg._check_akzeptanz_nicht_gelesen("RB", {42: {
        "id": 42, "behandlung": "akzeptiert", "akzeptanz_kategorie": "restrisiko",
        "felder": {"_source_id": "cra:requirement:AI1-04"}}}, punkte) == []
    # gar nicht akzeptiert — das ist der gewöhnliche offene Punkt und
    # Gegenstand der Anforderungsschleife, nicht dieses Punktes
    assert kg._check_akzeptanz_nicht_gelesen("RB", {42: {
        "id": 42, "behandlung": "offen", "akzeptanz_kategorie": "",
        "felder": {}}}, punkte) == []
    assert punkte == []


def test_ohne_akzeptanz_wird_die_tabelle_nicht_gelesen(monkeypatch) -> None:
    from shared import risk_req_links
    from cra import konformitaet_gate as kg

    def _nie(*a, **k):  # pragma: no cover
        raise AssertionError("ohne begründete Akzeptanz kein Tabellen-Zugriff")
    monkeypatch.setattr(risk_req_links, "list_for_project", _nie, raising=True)
    punkte: list[dict] = []
    assert kg._check_akzeptanz_nicht_gelesen("RB", {}, punkte) == []
    assert kg._check_akzeptanz_nicht_gelesen("", {42: {"behandlung": "akzeptiert",
                                                      "akzeptanz_kategorie": "x"}}, punkte) == []
    assert punkte == []


def test_der_nachbar_bleibt_unberuehrt() -> None:
    """#1941 prüft die **andere** Richtung (Akzeptanz ohne Verknüpfung) und hat
    einen Wächter, der verlangt, dass die Tabelle ohne gezählte Akzeptanz nicht
    gelesen wird. Genau deshalb ist #1965 eine eigene Funktion: Der gemeldete
    Fall ist der, in dem **keine** Akzeptanz gezählt wurde.
    """
    from cra import konformitaet_gate as kg
    assert kg._check_akzeptanz_verknuepfung is not kg._check_akzeptanz_nicht_gelesen


# ── der Hinweis an der Maske und beim Speichern ──────────────────────────────

def test_die_oberflaeche_nennt_den_weg() -> None:
    """Ein Hinweis ohne Weg daneben ist eine Sackgasse (#1783).

    Geprüft wird die **Oberfläche**: Die Texte stehen seit #1954 im
    Nachrichten-Katalog, ``vue_text`` löst sie auf.
    """
    from tests.i18n_text import vue_text
    text = vue_text(_WURZEL / "frontend" / "src" / "components" / "shared"
                    / "RequirementRiskLinks.vue")
    assert "offener Punkt" in text, (
        "Die Maske sagt nicht, dass die Bewertung im Release-Gate als offener "
        "Punkt zählt — genau das war der Mangel aus #1965.")
    assert "Notiz" in text, (
        "Die Maske sagt nicht, dass der Kommentar eine Notiz ist und dafür "
        "nicht gelesen wird.")


def test_der_hinweis_steht_in_beiden_sprachen() -> None:
    import json
    schluessel = ["gateOffenerPunkt", "gateKommentarIstNotiz", "gateZaehltNicht"]
    for sprache in ("de", "en"):
        katalog = json.loads((_WURZEL / "frontend" / "src" / "i18n" / sprache
                              / "geteilt.json").read_text(encoding="utf-8"))
        vorhanden = katalog["requirementRiskLinks"]
        for s in schluessel:
            assert vorhanden.get(s), f"{sprache}/{s} fehlt (#1954)"


def test_der_speicherweg_haengt_den_hinweis_an() -> None:
    """Dort fällt die Entscheidung. Und er blockiert nicht: Antwort bleibt 200
    (Muster ``lizenz_hinweis``, #1713/#1819)."""
    programm = _programm(_WURZEL / "server" / "api" / "cra" / "__init__.py")
    fn = programm.split("def save_bewertung", 1)[1].split("\n@cra_bp", 1)[0]
    assert "gate_hinweis" in fn
    assert "200" in fn and "409" not in fn and "428" not in fn


def test_der_endpunkt_rechnet_die_regel_nicht_selbst() -> None:
    programm = _programm(_WURZEL / "server" / "api" / "cra" / "__init__.py")
    fn = programm.split("def _gate_hinweis", 1)[1].split("\n@cra_bp", 1)[0]
    assert "anforderungs_befund" in fn
    assert "akzeptanz_kategorie" not in fn, (
        "Die Regel gehört ins Gate, nicht in den Endpunkt (#1726/#1727).")


# ── mit Datenbank: der Rundlauf ──────────────────────────────────────────────

@pytest.fixture()
def pfade(_pg_isolate):
    """CRA-Projekt mit verknüpfter Risikobewertung und einer Anforderung auf 3.

    Die echten Pfade, wie im Bestand: ``shared/db`` leitet aus dem Stem nur den
    Schema-Namen ab (#15) — die ``.sqlite``-Pfade sind Schlüssel, keine
    Dateien. Damit braucht es kein Umhängen von Modul-Konstanten, und der Test
    läuft durch denselben Code wie die Anwendung.
    """
    from cra.db import save_projekt as cra_save, save_bewertung
    from risikobewertung.db import save_projekt as rb_save
    from cra import konformitaet_gate as kg
    from shared import req_risks

    cra_db = Path("data/db/cra.sqlite")
    rb_db = Path("data/db/risikobewertung.sqlite")
    rb_name = "Akte 1965 – Risikoanalyse"
    rb_save(rb_db, rb_name, "STRIDE", "Rundlauf #1965")
    projekt = "Produkt 1965"
    cra_save(cra_db, projekt, produkt="P", beschreibung="Rundlauf #1965",
             meta={"linked_risk_projekt": rb_name})
    save_bewertung(cra_db, projekt_name=projekt, anforderung_id="AI1-04",
                   bewertung=3, kommentar="Begründung: " + "x" * 2129)
    return {"cra_db": cra_db, "rb_db": rb_db, "projekt": projekt, "rb": rb_name,
            "kg": kg, "req_risks": req_risks}


def test_rundlauf_vorhandenes_risiko_verknuepfen_und_akzeptieren(pfade) -> None:
    """**Der tragende Test.**

    Anforderung auf 3, ein *vorhandenes* Risiko verknüpfen, akzeptieren mit
    Kategorie und Begründung → das Gate zählt sie als ``begruendet`` und nicht
    mehr als offenen Punkt. Vor #1965 blieb sie offen, weil der
    Verknüpfungsweg ``felder._source_id`` nicht schrieb.
    """
    from risikobewertung.db import save_risiko, set_risiko_behandlung, load_risiken
    kg, rr = pfade["kg"], pfade["req_risks"]
    rb_db, projekt, rb = pfade["rb_db"], pfade["projekt"], pfade["rb"]

    # ein Risiko, das es schon gibt — ohne jede Herkunft
    rid = save_risiko(rb_db, {"projekt_name": rb, "risk_name": "Bestandsrisiko",
                              "beschreibung": "vorher angelegt", "framework": "STRIDE"})
    assert not (load_risiken(rb_db, rb)[0].get("felder") or {}).get("_source_id")

    # vorher: nicht begründet
    vorher = kg.anforderungs_befund(projekt, "AI1-04")
    assert vorher["bewertung"] == 3 and vorher["schwelle"] == 4
    assert vorher["begruendet"] is False and vorher["offen"] is True
    assert vorher["hinweis_code"] == kg.HINWEIS_BEGRUENDUNG_FEHLT

    # verknüpfen — der Weg aus #1564
    res = rr.link_risk("cra", projekt, "requirement", "AI1-04", int(rid))
    assert res["herkunft_gesetzt"] is True
    felder = (load_risiken(rb_db, rb)[0].get("felder") or {})
    assert felder["_source_id"] == "cra:requirement:AI1-04"
    assert felder["_source"] == "req-gap"

    # verknüpft, aber noch nicht akzeptiert → weiter offen
    assert kg.anforderungs_befund(projekt, "AI1-04")["offen"] is True

    # akzeptieren mit Kategorie und Begründung
    set_risiko_behandlung(rb_db, int(rid), behandlung="akzeptiert",
                          kategorie="restrisiko",
                          grund="Restrisiko abgewogen, kompensiert durch X.",
                          von="Martin Zeifang")

    nachher = kg.anforderungs_befund(projekt, "AI1-04")
    assert nachher["begruendet"] is True, (
        "Das ist der gemeldete Fall: Verknüpfen + Akzeptieren muss im Gate "
        "ankommen (#1965).")
    assert nachher["offen"] is False and nachher["hinweis_code"] is None
    assert nachher["risiko"]["kategorie"] == "restrisiko"

    # und dasselbe im Gate selbst
    gate = kg.evaluate(projekt)
    offene = [p.get("requirement_id") for p in gate["offene_punkte"]
              if p.get("typ") == "anforderung"]
    assert "AI1-04" not in offene
    assert any(a["requirement_id"] == "AI1-04" and a["art"] == "begruendet"
               for a in gate["abweichungen"])
    assert gate["begruendet_akzeptiert"] >= 1


def test_das_nachtragen_laesst_eine_fremde_herkunft_stehen(pfade) -> None:
    """Ein CVE-Risiko behält seine Herkunft — sonst käme derselbe CVE beim
    nächsten Abgleich doppelt herein."""
    from risikobewertung.db import save_risiko, load_risiken
    rr = pfade["req_risks"]
    rb_db, projekt, rb = pfade["rb_db"], pfade["projekt"], pfade["rb"]

    rid = save_risiko(rb_db, {"projekt_name": rb, "risk_name": "CVE-2024-0001",
                              "framework": "STRIDE",
                              "felder": {"_source": "cra-cve",
                                         "_source_id": "CVE-2024-0001"}})
    res = rr.link_risk("cra", projekt, "requirement", "AI1-04", int(rid))
    assert res["herkunft_gesetzt"] is False
    felder = (load_risiken(rb_db, rb)[0].get("felder") or {})
    assert felder["_source_id"] == "CVE-2024-0001"
    assert felder["_source"] == "cra-cve"


def test_das_nachtragen_laesst_die_bewertungsfelder_stehen(pfade) -> None:
    """Teil-Update (#1540/#1771/#1805): Die Framework-Felder sind die Bewertung
    eines Menschen und gehen nicht verloren."""
    from risikobewertung.db import save_risiko, load_risiken, setze_risiko_herkunft
    rb_db, rb = pfade["rb_db"], pfade["rb"]
    rid = save_risiko(rb_db, {"projekt_name": rb, "risk_name": "Bewertet",
                              "beschreibung": "mit Bewertung", "framework": "STRIDE",
                              "risikowert": 9, "risiko_label": "hoch",
                              "felder": {"impact": 3, "likelihood": 3}})
    assert setze_risiko_herkunft(rb_db, int(rid), source="req-gap",
                                 source_id="cra:requirement:AI1-04") is True
    r = load_risiken(rb_db, rb)[0]
    assert r["felder"] == {"impact": 3, "likelihood": 3, "_source": "req-gap",
                           "_source_id": "cra:requirement:AI1-04"}
    assert r["risk_name"] == "Bewertet" and r["risikowert"] == 9
    assert r["beschreibung"] == "mit Bewertung"
    # idempotent: ein zweiter Lauf ändert nichts
    assert setze_risiko_herkunft(rb_db, int(rid), source="req-gap",
                                 source_id="cra:requirement:IMPL-06") is False
    assert load_risiken(rb_db, rb)[0]["felder"]["_source_id"] == "cra:requirement:AI1-04"


def test_der_kommentar_allein_laesst_die_anforderung_offen(pfade) -> None:
    """Die Gegenrichtung mit Datenbank: 2141 Zeichen Kommentar, kein Risiko."""
    kg, projekt = pfade["kg"], pfade["projekt"]
    befund = kg.anforderungs_befund(projekt, "AI1-04")
    assert befund["offen"] is True and befund["begruendet"] is False
    gate = kg.evaluate(projekt)
    assert "AI1-04" in [p.get("requirement_id") for p in gate["offene_punkte"]
                        if p.get("typ") == "anforderung"]


def test_eine_erfuellte_anforderung_braucht_keinen_hinweis(pfade) -> None:
    from cra.db import save_bewertung
    kg, projekt = pfade["kg"], pfade["projekt"]
    save_bewertung(pfade["cra_db"], projekt_name=projekt, anforderung_id="AI1-04",
                   bewertung=4, kommentar="umgesetzt")
    befund = kg.anforderungs_befund(projekt, "AI1-04")
    assert befund["erfuellt"] is True and befund["hinweis_code"] is None


def test_unpruefbar_ist_nicht_begruendet(pfade, monkeypatch) -> None:
    """#1751 — eine Prüfung, die nicht laufen konnte, gilt nicht als erfüllt."""
    import risikobewertung.db as rdb
    kg, projekt = pfade["kg"], pfade["projekt"]

    def _kaputt(*a, **k):
        raise RuntimeError("Datenquelle weg")
    monkeypatch.setattr(rdb, "load_risiken", _kaputt, raising=True)
    befund = kg.anforderungs_befund(projekt, "AI1-04")
    assert befund["ungeprueft"] is True
    assert befund["begruendet"] is False and befund["offen"] is True
    assert befund["hinweis_code"] == kg.HINWEIS_BEGRUENDUNG_UNGEPRUEFT


def test_die_maske_liest_denselben_stand(pfade) -> None:
    """``object_risks`` liefert ``begruendete_abweichung`` vom Server — die
    Maske baut die Regel nicht nach (#1703/S9)."""
    from risikobewertung.db import save_risiko, set_risiko_behandlung
    rr, kg, projekt = pfade["req_risks"], pfade["kg"], pfade["projekt"]
    rb_db, rb = pfade["rb_db"], pfade["rb"]

    vorher = rr.object_risks("cra", projekt, "requirement", "AI1-04")
    assert vorher["gate_schwelle"] == 4
    assert vorher["begruendete_abweichung"] is False

    rid = save_risiko(rb_db, {"projekt_name": rb, "risk_name": "Bestand",
                              "framework": "STRIDE"})
    rr.link_risk("cra", projekt, "requirement", "AI1-04", int(rid))
    set_risiko_behandlung(rb_db, int(rid), behandlung="akzeptiert",
                          kategorie="kompensierend", grund="Kompensiert durch Y.")

    nachher = rr.object_risks("cra", projekt, "requirement", "AI1-04")
    assert nachher["begruendete_abweichung"] is True
    assert nachher["risks"][0]["zaehlt_im_gate"] is True
    assert nachher["risks"][0]["herkunft"] == "cra:requirement:AI1-04"
    # und derselbe Stand wie im Gate
    assert kg.anforderungs_befund(projekt, "AI1-04")["begruendet"] is True


def test_die_maske_zeigt_die_nicht_angerechnete_akzeptanz(pfade) -> None:
    """Belegter Herkunfts-Platz: Die Maske sagt es, statt „akzeptiert" zu zeigen
    und das Gate „offen" rechnen zu lassen."""
    from risikobewertung.db import save_risiko, set_risiko_behandlung
    rr, projekt = pfade["req_risks"], pfade["projekt"]
    rb_db, rb = pfade["rb_db"], pfade["rb"]

    rid = save_risiko(rb_db, {"projekt_name": rb, "risk_name": "CVE-2024-0002",
                              "framework": "STRIDE",
                              "felder": {"_source": "cra-cve",
                                         "_source_id": "CVE-2024-0002"}})
    rr.link_risk("cra", projekt, "requirement", "AI1-04", int(rid))
    set_risiko_behandlung(rb_db, int(rid), behandlung="akzeptiert",
                          kategorie="restrisiko", grund="Restrisiko angenommen.")

    stand = rr.object_risks("cra", projekt, "requirement", "AI1-04")
    assert stand["begruendete_abweichung"] is False
    assert stand["risks"][0]["behandlung"] == "akzeptiert"
    assert stand["risks"][0]["zaehlt_im_gate"] is False
    assert stand["risks"][0]["herkunft"] == "CVE-2024-0002"


def test_das_gate_benennt_die_nicht_angerechnete_akzeptanz(pfade) -> None:
    from risikobewertung.db import save_risiko, set_risiko_behandlung
    rr, kg, projekt = pfade["req_risks"], pfade["kg"], pfade["projekt"]
    rb_db, rb = pfade["rb_db"], pfade["rb"]

    rid = save_risiko(rb_db, {"projekt_name": rb, "risk_name": "CVE-2024-0003",
                              "framework": "STRIDE",
                              "felder": {"_source": "cra-cve",
                                         "_source_id": "CVE-2024-0003"}})
    rr.link_risk("cra", projekt, "requirement", "AI1-04", int(rid))
    set_risiko_behandlung(rb_db, int(rid), behandlung="akzeptiert",
                          kategorie="restrisiko", grund="Restrisiko angenommen.")

    gate = kg.evaluate(projekt)
    punkte = [p for p in gate["offene_punkte"] if p.get("typ") == "akzeptanz_nicht_gelesen"]
    assert len(punkte) == 1 and "AI1-04" in punkte[0]["titel"]
    # und die Anforderung bleibt offen — sie ist nicht begründet
    assert "AI1-04" in [p.get("requirement_id") for p in gate["offene_punkte"]
                        if p.get("typ") == "anforderung"]
