"""Anhang I Teil II Nr. 3 — regelmäßig und wirksam testen (#1824).

Das Gate rechnete fünfzehn Punkte und keinen zu dieser Pflicht. Der Testbericht
war ein Haken in der Anhang-VII-Beleg-Matrix: vorhanden oder nicht. Ob er den
ausgelieferten Stand noch beschreibt, rechnete niemand — ein Bericht von 2023
belegte ein Release von 2026, und die Akte zeigte grün.

Die Tests halten fest, was dabei leicht wieder verrutscht:

* Der **erklärte Verzicht wird nicht grün**. Würde er den Punkt schließen, wäre
  er der bequemste Weg um die Prüfung herum (die Fehlerklasse aus #1814/#1751).
* Die Pflichtangaben des Verzichts werden **serverseitig** erzwungen, nicht nur
  im Formular (#1760/#1762).
* Ein **Sicherheitsupdate** überholt einen Testbericht nicht (Erwägungsgrund 39,
  #1792/#1793) — eine Funktionsaktualisierung schon.
* Der **flache Gate-Schlüssel** existiert. Fehlt er, zeigt der Vorgangsbericht
  „nicht geprüft", obwohl gerechnet wurde (#1762/#1773).
* Ein Speichern im Konformitäts-Formular **leert die Felder nicht** (#1805).
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from cra import db as cdb
from cra import konformitaet_db as kdb
from cra import sicherheitstests as st
from cra.konformitaet_gate import evaluate

CRA_DB = Path("data/db/cra.sqlite")
KONF = "/api/cra-konformitaet"
CRA = "/api/cra"
PROJ = "pytest-sicherheitstests-1824"
FIRMA = "pytest-firma-1824"
VER = "2.1.0"
BEGRUENDUNG = ("Das Produkt wird ausschließlich in einem abgeschotteten Netz "
               "betrieben; die Abwägung ist im Risikoregister festgehalten.")
MORGEN = (date.today() + timedelta(days=30)).isoformat()
GESTERN = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture
def projekt():
    cdb.ensure_db(CRA_DB)
    cdb.delete_projekt(CRA_DB, PROJ)
    cdb.save_projekt(CRA_DB, PROJ, unternehmen=FIRMA, produkt="Testprodukt")
    kdb.save_konformitaet(CRA_DB, PROJ, {"bewertungsweg": "A"})
    yield PROJ
    cdb.delete_projekt(CRA_DB, PROJ)


def _testbericht(projekt: str, name: str = "Pentest 2026") -> int:
    """Ein Testnachweis in der CRA-Akte — genau so legt ihn die
    Pentest-Übernahme an (``annex_baustein='testberichte'``)."""
    from cra.traceability_db import create_dokument

    return create_dokument(CRA_DB, projekt, name, doc_type="pentest",
                           annex_baustein="testberichte")


def _mangel_ids(projekt: str, version: str = VER, **kw) -> list[str]:
    return [m["id"] for m in st.befund(CRA_DB, projekt, version, **kw)["maengel"]]


# ── Die vier Befundlagen ─────────────────────────────────────────────────────

def test_ohne_nachweis_ist_der_punkt_offen(projekt):
    """Lage 1: In der Akte steht kein Testbericht."""
    assert _mangel_ids(projekt) == ["kein_nachweis"]
    gate = evaluate(projekt, version=VER)
    punkte = [p for p in gate["release_punkte"] if p["typ"] == "sicherheitstests"]
    assert punkte, "der Prüfpunkt erscheint nicht im Gate"
    assert punkte[0]["ampel_wirkung"] == "bedingt", \
        "ein fehlender Nachweis ist ein Mangel der Akte, keine Nicht-Konformität"
    assert "Anhang I Teil II Nr. 3" in punkte[0]["ref"]


def test_frischer_nachweis_schliesst_den_punkt(projekt):
    """Lage 0: Nachweis vorhanden, aktuell, keine Funktionsänderung seither."""
    _testbericht(projekt)
    assert _mangel_ids(projekt) == []
    assert evaluate(projekt, version=VER)["sicherheitstests_mangel"] == []


def test_nachweis_aelter_als_die_letzte_funktionsaenderung(projekt):
    """Lage 2: Der härtere Maßstab — nicht die Uhr, sondern das Produkt.

    Ein Test belegt den Stand, den er vorgefunden hat. Ist seither eine
    Funktionsaktualisierung herausgegangen, beschreibt er ein anderes Produkt.
    """
    _testbericht(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": "2.0.0"})
    kdb.set_release_art(CRA_DB, projekt, "2.0.0", art="funktionsupdate", von="u1")
    _freigeben_mit_datum(projekt, "2.0.0", (date.today() + timedelta(days=1)).isoformat())

    assert "veraltet" in _mangel_ids(projekt)


def test_sicherheitsupdate_ueberholt_den_nachweis_nicht(projekt):
    """Erwägungsgrund 39: Eine Sicherheitsaktualisierung ist keine wesentliche
    Änderung. Ein Prüfpunkt, der nach jedem Sicherheitsupdate einen neuen
    Pentest verlangt, wird umgangen statt befolgt (#1792/#1793)."""
    _testbericht(projekt)
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": "2.0.1"})
    kdb.set_release_art(CRA_DB, projekt, "2.0.1", art="sicherheitsupdate", von="u1")
    _freigeben_mit_datum(projekt, "2.0.1", (date.today() + timedelta(days=1)).isoformat())

    assert "veraltet" not in _mangel_ids(projekt)


def test_nachweis_aelter_als_der_richtwert(projekt):
    """Lage 3: Die Hausregel zur Regelmäßigkeit (18 Kalendermonate).

    Gemessen wird über ``heute`` — damit der Test nicht vom Kalender des
    Rechners abhängt und 18 Monate nicht als 540 Tage nachgebaut werden.
    """
    _testbericht(projekt)
    spaeter = st._minus_monate(date.today(), -(st.MAX_MONATE + 1))  # +19 Monate
    assert "zu_alt" in _mangel_ids(projekt, heute=spaeter)
    # Einen Tag vor der Grenze noch nicht:
    knapp = st._minus_monate(date.today(), -st.MAX_MONATE) - timedelta(days=1)
    assert "zu_alt" not in _mangel_ids(projekt, heute=knapp)


def _freigeben_mit_datum(projekt: str, version: str, am: str) -> None:
    """Vorgang als herausgegeben markieren. Direkt per SQL, weil die
    Zustandsmaschine aus #1743 zwei verschiedene Personen und einen
    abgeschlossenen Bewertungsweg verlangt — beides ist hier nicht der
    Gegenstand."""
    con = kdb._connect(CRA_DB)
    try:
        con.execute(
            "UPDATE cra_konformitaet SET freigabe_status='freigegeben', "
            "freigegeben_am=? WHERE projekt_name=? AND release_version=?",
            (am, projekt, version))
        con.commit()
    finally:
        con.close()


def test_dieselbe_pruefung_wird_nur_einmal_gezaehlt(projekt):
    """Gefunden auf der Testinstanz: „Nachweise in der Akte: 10" für **einen**
    Penetrationstest.

    Die drei Quellen überlappen — ein übernommener Pentest steht als Zeile in
    ``cra_dokumente`` und als Bericht im Pentest-Modul. Eine Zahl, die der
    Anwender nicht nachvollziehen kann, beschädigt die Aussage mehr als sie
    stützt. Zusammengeführt wird über die Datei-Kennung, nicht über den Namen.
    """
    from cra.traceability_db import create_dokument

    # Dieselbe Zeile zweimal — so lag es im Bestand.
    for _ in range(3):
        create_dokument(CRA_DB, projekt, "Pentest 2026", doc_type="pentest",
                        annex_baustein="testberichte")
    nw = st.nachweise(CRA_DB, projekt)
    assert len(nw) == 1, nw

    # Und derselbe Bericht aus zwei Quellen: Die Übernahme legt die Zeile mit
    # ``doc_path='evidence:<id>'`` an; dann gilt der Prüfzeitraum als Datum.
    bericht = _pentest_bericht(projekt, evidence_doc_id="ev-1824")
    create_dokument(CRA_DB, projekt, "Pentest-Bericht: X", doc_type="pentest",
                    doc_path="evidence:ev-1824", annex_baustein="testberichte")
    nw = st.nachweise(CRA_DB, projekt)
    assert len(nw) == 2, nw
    pentest = [n for n in nw if n["quelle"] == "🛡️ Pentest"]
    assert len(pentest) == 1, pentest
    assert pentest[0]["datum"].isoformat() == "2026-05-20", \
        "nicht der Prüfzeitraum, sondern der Tag des Imports"
    _pentest_aufraeumen(bericht)


def _pentest_bericht(projekt: str, *, evidence_doc_id: str = "") -> int:
    from pentest import db as pdb

    bid = pdb.create_bericht(pdb.DB_PATH, FIRMA, {
        "titel": "Pentest 1824", "art": "anwendung",
        "datum_von": "2026-05-18", "datum_bis": "2026-05-20",
        "cra_projekt": projekt}, evidence_doc_id=evidence_doc_id)
    return int(bid)


def _pentest_aufraeumen(bericht_id: int) -> None:
    from pentest import db as pdb

    pdb.delete_bericht(pdb.DB_PATH, bericht_id)


def test_pentest_ohne_zuordnung_in_der_akte_zaehlt_mit(projekt):
    """Der Test hat stattgefunden, nur die Zuordnung nach Anhang VII fehlt.
    Ihn nicht zu zählen würde den Anwender zu einem zweiten Test auffordern."""
    bericht = _pentest_bericht(projekt)
    try:
        nw = st.nachweise(CRA_DB, projekt)
        assert [n["quelle"] for n in nw] == ["🛡️ Pentest"], nw
        assert _mangel_ids(projekt) == []
    finally:
        _pentest_aufraeumen(bericht)


# ── Der Verzicht ─────────────────────────────────────────────────────────────

def test_verzicht_wird_nicht_gruen(projekt):
    """Die tragende Entscheidung dieses Issues.

    Der Anwender darf erklären, dass nicht getestet wird — der Punkt bleibt
    aber offen und wird ausgewiesen. Würde der Verzicht grün schalten, wäre er
    der Weg um die Prüfung herum (#1814/#1751).
    """
    kdb.set_sicherheitstests(CRA_DB, projekt, "", {
        "testnachweis_art": "kein_test",
        "test_verzicht_begruendung": BEGRUENDUNG,
        "test_verzicht_review": MORGEN}, von="pruefer-1")

    ids = _mangel_ids(projekt)
    assert ids == ["verzicht_erklaert"], ids
    gate = evaluate(projekt, version=VER)
    assert gate["sicherheitstests_mangel"] == ["verzicht_erklaert"]
    assert gate["ampel"] != "gruen", "der Verzicht hat den Punkt geschlossen"
    punkt = next(p for p in gate["release_punkte"] if p["typ"] == "sicherheitstests")
    assert punkt["ampel_wirkung"] == "bedingt"
    assert "pruefer-1" in punkt["hinweis"], \
        "der Ausweis muss nennen, wer die Entscheidung getroffen hat"


def test_verzicht_ohne_begruendung_wird_abgelehnt(projekt):
    """Serverseitig, nicht nur im Formular."""
    with pytest.raises(ValueError) as e:
        kdb.set_sicherheitstests(CRA_DB, projekt, "", {
            "testnachweis_art": "kein_test", "test_verzicht_begruendung": "kurz",
            "test_verzicht_review": MORGEN})
    assert "begründen" in str(e.value).lower()


def test_verzicht_ohne_wiedervorlage_wird_abgelehnt(projekt):
    """Ein Verzicht ohne Ablaufdatum ist eine Dauerentscheidung."""
    with pytest.raises(ValueError) as e:
        kdb.set_sicherheitstests(CRA_DB, projekt, "", {
            "testnachweis_art": "kein_test",
            "test_verzicht_begruendung": BEGRUENDUNG})
    assert "Wiedervorlage" in str(e.value)


def test_unbekannte_art_wird_abgelehnt(projekt):
    with pytest.raises(ValueError):
        kdb.set_sicherheitstests(CRA_DB, projekt, "", {"testnachweis_art": "pentest"})


def test_abgelaufene_wiedervorlage_meldet_sich(projekt):
    con = kdb._connect(CRA_DB)
    try:
        con.execute(
            "UPDATE cra_konformitaet SET testnachweis_art='kein_test', "
            "test_verzicht_begruendung=?, test_verzicht_review=?, "
            "test_verzicht_von='u1', test_verzicht_am='2025-01-01' "
            "WHERE projekt_name=? AND release_version=''",
            (BEGRUENDUNG, GESTERN, projekt))
        con.commit()
    finally:
        con.close()
    ids = _mangel_ids(projekt)
    assert "verzicht_faellig" in ids, ids
    assert st.befund(CRA_DB, projekt, VER)["verzicht"]["faellig"] is True


def test_umstellen_loescht_den_verzicht(projekt):
    """Stünde die Begründung noch da, trüge die Akte eine Erklärung für eine
    Entscheidung, die niemand mehr trifft."""
    kdb.set_sicherheitstests(CRA_DB, projekt, "", {
        "testnachweis_art": "kein_test", "test_verzicht_begruendung": BEGRUENDUNG,
        "test_verzicht_review": MORGEN}, von="u1")
    rec = kdb.set_sicherheitstests(CRA_DB, projekt, "",
                                   {"testnachweis_art": "pentest_extern"}, von="u1")
    assert rec["test_verzicht_begruendung"] == ""
    assert rec["test_verzicht_review"] == ""
    assert not rec["test_verzicht_am"]


# ── Produkt → Release: erben und übersteuern (#1805) ─────────────────────────

def test_release_erbt_die_entscheidung_vom_produkt(projekt):
    kdb.set_sicherheitstests(CRA_DB, projekt, "", {
        "testnachweis_art": "kein_test", "test_verzicht_begruendung": BEGRUENDUNG,
        "test_verzicht_review": MORGEN}, von="u1")
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})

    rec = kdb.get_konformitaet(CRA_DB, projekt, VER)
    assert rec["testnachweis_art"] == "kein_test"
    assert rec["test_verzicht_begruendung"] == BEGRUENDUNG
    assert "testnachweis_art" in rec["geerbt_vom_produkt"]


def test_eigener_wert_am_release_uebersteuert(projekt):
    """Nach einer wesentlichen Änderung kann für ein Release eigens zu
    entscheiden sein."""
    kdb.set_sicherheitstests(CRA_DB, projekt, "", {
        "testnachweis_art": "kein_test", "test_verzicht_begruendung": BEGRUENDUNG,
        "test_verzicht_review": MORGEN}, von="u1")
    kdb.save_konformitaet(CRA_DB, projekt, {"release_version": VER})
    kdb.set_sicherheitstests(CRA_DB, projekt, VER,
                             {"testnachweis_art": "pentest_extern"}, von="u1")

    rec = kdb.get_konformitaet(CRA_DB, projekt, VER)
    assert rec["testnachweis_art"] == "pentest_extern"
    assert "testnachweis_art" not in rec["geerbt_vom_produkt"]
    # Das Produkt bleibt unberührt.
    assert kdb.get_konformitaet(CRA_DB, projekt, "")["testnachweis_art"] == "kein_test"


def test_speichern_im_konformitaets_formular_leert_nichts(projekt):
    """Dieselbe Klasse wie ``notizen`` in #1805, ``artefakt`` in #1771 und
    ``meta_json`` in #1540: Was der Aufrufer nicht nennt, behält seinen Wert.
    Das Konformitäts-Formular nennt die Test-Felder nie."""
    kdb.set_sicherheitstests(CRA_DB, projekt, "", {
        "testnachweis_art": "kein_test", "test_verzicht_begruendung": BEGRUENDUNG,
        "test_verzicht_review": MORGEN}, von="u1")

    kdb.save_konformitaet(CRA_DB, projekt, {"bewertungsweg": "A",
                                            "bewertung_abgeschlossen": True})

    rec = kdb.get_konformitaet(CRA_DB, projekt, "")
    assert rec["testnachweis_art"] == "kein_test"
    assert rec["test_verzicht_begruendung"] == BEGRUENDUNG
    assert rec["test_verzicht_review"] == MORGEN


# ── Die Verdrahtung (die Falle aus #1762/#1773/#1799) ────────────────────────

def test_flacher_gate_schluessel_existiert(projekt):
    """Ohne ihn rechnet die Anwendung richtig und der Vorgangsbericht meldet
    „nicht geprüft" — eine Behauptung über die Akte aus einer vergessenen
    Zeile Code."""
    gate = evaluate(projekt, version=VER)
    assert "sicherheitstests_mangel" in gate
    assert isinstance(gate["sicherheitstests_mangel"], list)
    # Phase 1: nicht geprüft heißt ``None`` und nicht „in Ordnung".
    assert evaluate(projekt)["sicherheitstests_mangel"] is None


def test_katalog_bericht_und_panel_kennen_den_punkt():
    """Der Wächter aus #1773 prüft alle gerechneten Punkte; hier steht der
    neue noch einmal namentlich, damit ein Fehlschlag die Ursache nennt."""
    import re

    from cra.release_bericht import _GERECHNET_AUSWERTUNG
    from cra.release_checkliste import item

    eintrag = item("sicherheitstests")
    assert eintrag is not None and eintrag.art == "gerechnet"
    assert eintrag.quelle == "sicherheitstests_mangel"
    assert eintrag.link == "konformitaet", \
        "der Deep-Link muss auf den Tab zeigen, in dem die Eingabe steht"
    assert eintrag.quelle in _GERECHNET_AUSWERTUNG

    panel = Path("frontend/src/views/cra/ReleasesPanel.vue").read_text(encoding="utf-8")
    assert "case 'sicherheitstests_mangel'" in panel
    assert re.search(r"sicherheitstests_mangel:\s*'sicherheitstests'", panel)


def test_bericht_uebersetzt_den_befund():
    from cra.release_bericht import gerechnetes_ergebnis

    assert gerechnetes_ergebnis("sicherheitstests_mangel", {})[0] == "ungeprueft"
    assert gerechnetes_ergebnis(
        "sicherheitstests_mangel", {"sicherheitstests_mangel": None})[0] == "ungeprueft"
    assert gerechnetes_ergebnis(
        "sicherheitstests_mangel", {"sicherheitstests_mangel": []})[0] == "erfuellt"
    assert gerechnetes_ergebnis(
        "sicherheitstests_mangel",
        {"sicherheitstests_mangel": ["verzicht_erklaert"]})[0] == "offen"


# ── Nachweis und Kundenfassung ───────────────────────────────────────────────

def test_verzicht_steht_im_konformitaetsnachweis(projekt):
    """Ein Nachweis, der den Verzicht verschweigt, ist gegenüber dem Empfänger
    irreführend — und genau dieses Dokument reicht der Kunde weiter."""
    from cra import konformitaet_report as kr

    kdb.set_sicherheitstests(CRA_DB, projekt, "", {
        "testnachweis_art": "kein_test", "test_verzicht_begruendung": BEGRUENDUNG,
        "test_verzicht_review": MORGEN}, von="pruefer-1")

    d = kr.daten(projekt, version=VER)
    assert d["sicherheitstests"]["verzicht_erklaert"] is True
    assert d["sicherheitstests"]["belegt"] is False

    text = _docx_text(kr.build_docx(projekt, version=VER))
    assert "Sicherheitstests (Anhang I Teil II Nr. 3)" in text
    assert "keine gesonderten Sicherheitstests" in text or "verzichtet" in text
    assert BEGRUENDUNG[:40] in text, "die Begründung gehört in den Nachweis"


def test_verzicht_steht_in_der_kundenfassung(projekt):
    """Und er darf die Begriffs-Sperre der Kundenfassung nicht reißen.

    Die **interne Begründung** bleibt bewusst draußen: Dass verzichtet wird,
    ist eine Aussage über das Produkt; *warum*, ist die Abwägung des Hauses und
    steht im Konformitätsnachweis.
    """
    from cra import kundenfassung as kf

    kdb.set_sicherheitstests(CRA_DB, projekt, "", {
        "testnachweis_art": "kein_test", "test_verzicht_begruendung": BEGRUENDUNG,
        "test_verzicht_review": MORGEN}, von="pruefer-1")

    text = _docx_text(kf.build_docx(projekt, version=VER))
    assert "Sicherheitstests" in text
    assert "keine gesonderten Sicherheitstests" in text
    assert MORGEN in text, "die Wiedervorlage gehört in die Aussage"
    assert BEGRUENDUNG[:40] not in text, "die interne Begründung bleibt draußen"
    assert "pruefer-1" not in text, "kein interner Name in der Kundenfassung"
    for begriff in kf.VERBOTENE_BEGRIFFE:
        assert begriff.lower() not in text.lower(), begriff


def test_kundenfassung_nennt_die_art_des_tests(projekt):
    from cra import kundenfassung as kf

    _testbericht(projekt)
    kdb.set_sicherheitstests(CRA_DB, projekt, "",
                             {"testnachweis_art": "pentest_extern"}, von="u1")
    text = _docx_text(kf.build_docx(projekt, version=VER))
    assert "Penetrationstest" in text
    for begriff in kf.VERBOTENE_BEGRIFFE:
        assert begriff.lower() not in text.lower(), begriff


def _docx_text(blob: bytes) -> str:
    from io import BytesIO

    from docx import Document

    doc = Document(BytesIO(blob))
    teile = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            teile += [c.text for c in row.cells]
    return "\n".join(teile)


# ── Offene Befunde: verweisen, nicht doppelt melden ──────────────────────────

def test_offene_schwere_befunde_werden_nicht_doppelt_rot_gemeldet(projekt):
    """Pentest-Befunde liegen als ``cra_vuln`` vor und werden von
    ``offene_kritische_schwachstellen`` rot gemeldet. Zwei Prüfpunkte für
    denselben Sachverhalt wären zwei Wahrheiten (#1726/#1727/#1776)."""
    _testbericht(projekt)
    cdb.upsert_vuln(CRA_DB, projekt, {
        "cve_id": "PT-1-F-01", "titel": "Testbefund", "schwere": "critical",
        "status": "open", "source": "pentest"})

    gate = evaluate(projekt, version=VER)
    assert gate["offene_kritische_schwachstellen"] == 1
    assert gate["ampel"] == "rot"
    rot = [p for p in gate["release_punkte"]
           if p["typ"] == "sicherheitstests" and p["ampel_wirkung"] == "rot"]
    assert not rot, "der Befund wird zweimal gemeldet"


# ── REST ─────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state

    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = "ok", ["*"]
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def api_projekt(client, auth_headers):
    client.delete(f"{CRA}/projekte/{PROJ}", headers=auth_headers)
    client.post(f"{CRA}/projekte", headers=auth_headers,
                json={"name": PROJ, "unternehmen": FIRMA})
    yield PROJ
    client.delete(f"{CRA}/projekte/{PROJ}", headers=auth_headers)


def test_rest_liefert_arten_und_befund(client, auth_headers, api_projekt):
    r = client.get(f"{KONF}/projekte/{api_projekt}/konformitaet/sicherheitstests",
                   headers=auth_headers)
    assert r.status_code == 200, r.json
    assert [a["wert"] for a in r.json["arten"]] == list(st.ARTEN)
    assert r.json["min_begruendung"] == st.MIN_BEGRUENDUNG
    assert "maengel" in r.json["befund"]


def test_rest_lehnt_den_unbegruendeten_verzicht_ab(client, auth_headers, api_projekt):
    """Die Pflichtangabe nur im Browser zu prüfen hieße, sie über die API
    weglassen zu können."""
    r = client.put(f"{KONF}/projekte/{api_projekt}/konformitaet/sicherheitstests",
                   headers=auth_headers,
                   json={"testnachweis_art": "kein_test"})
    assert r.status_code == 400, r.json
    assert "begründ" in r.json["error"].lower()


def test_rest_stempelt_person_und_zeitpunkt(client, auth_headers, api_projekt):
    """Eine Entscheidung, deren Urheber der Browser mitschickt, ist keine."""
    r = client.put(f"{KONF}/projekte/{api_projekt}/konformitaet/sicherheitstests",
                   headers=auth_headers,
                   json={"testnachweis_art": "kein_test",
                         "test_verzicht_begruendung": BEGRUENDUNG,
                         "test_verzicht_review": MORGEN,
                         "test_verzicht_von": "jemand-anders"})
    assert r.status_code == 200, r.json
    vorgang = r.json["vorgang"]
    assert vorgang["test_verzicht_von"] and vorgang["test_verzicht_von"] != "jemand-anders"
    assert vorgang["test_verzicht_am"]
    assert r.json["befund"]["maengel"][0]["id"] == "verzicht_erklaert"
