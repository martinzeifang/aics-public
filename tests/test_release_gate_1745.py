"""Release-Gate: die Pflichten, die sich bei jedem Release stellen (#1745).

Das Gate prüfte bisher den **Produktzustand** (Phase 1): Anforderungen erfüllt oder
begründet, offene kritische Schwachstellen, Annex VII, DoC. Die Release-Pflichten
(Phase 2) fehlten, obwohl die Daten dafür alle schon in der Suite liegen.

Geprüft werden hier die Stellen, an denen die Erweiterung falsch liegen kann:

* Jeder neue Prüfpunkt **einzeln**, mit gesetzten und mit fehlenden Daten — ein
  Prüfpunkt, der nichts findet, sieht aus wie ein erfüllter.
* Die Ampel-Zuordnung: überfällige Meldefrist und Release nach EOL sind ``rot``
  (Pflichtverletzung), fehlendes Advisory/SBOM/PSIRT ist ``bedingt`` (Nachweis offen).
* Ein Prüfpunkt, der wegen eines Datenbankfehlers nicht laufen konnte, erscheint als
  **ungeprüft** und färbt die Ampel nicht grün. Das ist der eigentliche Kern: ein
  stilles ``except: pass`` wäre hier gefährlicher als eine Exception.
* Regression: ``evaluate()`` **ohne** Version verhält sich unverändert — auch dann,
  wenn das Projekt Release-Mängel hat.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from cra import db as cdb
from cra import meldung_db as mdb
from cra import traceability_db as tdb
from cra.konformitaet_gate import _norm_version, evaluate
from cra.requirements import CRA_ANFORDERUNGEN

CRA_DB = Path("data/db/cra.sqlite")
PROJ = "pytest-release-gate-1745"
VERSION = "1.4.0"

# Schlüssel, die ``evaluate()`` vor #1745 geliefert hat. Der Vertrag erlaubt
# ausschließlich additive Ergänzungen — ein fehlender Alt-Schlüssel bricht Panel,
# ``release-check``-Endpunkt und Nachweis-Report gleichzeitig.
_ALTE_SCHLUESSEL = {
    "projekt_name", "version", "ampel", "konform", "erfuellt",
    "begruendet_akzeptiert", "offen", "gesamt_anforderungen",
    "offene_kritische_schwachstellen", "annex_vollstaendig", "doc_ausgestellt",
    "reifegrad_pct", "offene_punkte", "abweichungen",
}
_NEUE_SCHLUESSEL = {"phase", "produkt_punkte", "release_punkte", "release_befunde",
                    # flach, unter den Namen, die der Release-Katalog (#1744) als
                    # ``quelle`` seiner gerechneten Punkte nennt.
                    "behobene_ohne_advisory", "sbom_version_fehlt",
                    "support_ueberschritten", "ueberfaellige_meldungen",
                    # #1759: in beiden Phasen gerechnet
                    "bewertungsweg_unzulaessig",
                    # #1761: Sorgfaltspflicht bei Fremdkomponenten (Art. 13 Abs. 5)
                    # und Meldung an deren Hersteller (Art. 13 Abs. 6)
                    "fremdkomponenten_unbewertet", "upstream_meldung_offen",
                    # #1774: Widerspruch zwischen der Bewertung einer
                    # Fremdkomponente und dem eigenen offenen Befund gegen sie.
                    "komponenten_befund_widerspruch",
                    # #1762: Update-Zusagen, Kaufhinweis, Aufbewahrungsfristen,
                    # Marktüberwachung. Sie wurden gerechnet, standen aber nicht
                    # im flachen Ergebnis — und damit zeigte der Vorgangsbericht
                    # sie stumm als „nicht geprüft".
                    "update_zusagen_fehlen", "kaufhinweis_fehlt",
                    "aufbewahrungsfristen_unbestimmbar", "marktaufsicht_versaeumt",
                    # #1793: erklärte Art des Releases und die Widersprüche
                    # dazu (Sicherheitsupdate gegen Funktionsupdate).
                    "release_art", "release_art_widersprueche"}


# ── Harness ──────────────────────────────────────────────────────────────────

def _leeren(projekt: str) -> None:
    """Projektspuren aus allen beteiligten Tabellen entfernen.

    ``cra.db.delete_projekt`` räumt Vuln/SBOM/PSIRT/Support-Zeitraum **nicht** mit auf,
    und unter Postgres ist das ``unlink()``-Teardown älterer Tests ein No-op — ohne
    explizites Leeren sammeln sich Zeilen über Läufe hinweg an und die Zähler stimmen
    scheinbar grundlos nicht (Altdaten-Falle, #1706).
    """
    con = cdb._connect(CRA_DB)
    try:
        for tbl in ("cra_vuln", "cra_sbom", "cra_sbom_komponenten", "cra_psirt",
                    "cra_support_period",
                    "cra_meldung", "cra_dokumente", "cra_bewertungen",
                    "cra_managed_docs", "cra_konformitaet"):
            con.try_execute(f"DELETE FROM {tbl} WHERE projekt_name=?", (projekt,))
        con.commit()
    finally:
        con.close()


def _phase1_gruen(projekt: str) -> None:
    """Produktzustand so herstellen, dass Phase 1 grün ist.

    Nur mit grüner Phase 1 lässt sich die Wirkung **eines einzelnen** Release-Punktes
    auf die Ampel messen; bei rotem Produktzustand wäre jede Aussage überdeckt.
    """
    for req in CRA_ANFORDERUNGEN:
        cdb.save_bewertung(CRA_DB, projekt, req["id"], 5, kommentar="Test")
    for b in tdb.ANNEX_VII_BAUSTEINE:
        tdb.create_dokument(CRA_DB, projekt, f"Nachweis {b['key']}",
                            doc_type="resource", annex_baustein=b["key"])
    from shared.documents.db import create_document, set_status
    did = create_document(CRA_DB, "cra", projekt=projekt,
                          doc_type="konformitaetserklaerung", titel="EU-DoC",
                          content_html="<p>Konformität erklärt.</p>")
    set_status(CRA_DB, "cra", did, "freigegeben")


def _release_vollstaendig(projekt: str, version: str = VERSION) -> None:
    """Alle Release-Pflichten erfüllen: SBOM zur Version, Support-Zeitraum, PSIRT.

    Seit #1761 gehört zur SBOM eine **Komponentenliste** mit bewerteten
    Komponenten: Eine SBOM, die nur eine Komponenten-Zahl nennt, belegt die
    Sorgfaltspflicht bei Komponenten Dritter nicht (Art. 13 Abs. 5) — die
    Null-Linie dieses Tests wäre sonst keine mehr.
    """
    sid = cdb.save_sbom(CRA_DB, projekt,
                        {"release_version": version, "sbom_format": "spdx",
                         "komponenten_count": 1, "quelle": "manual"})
    from cra import sbom_komponenten as sk
    sk.replace_komponenten(CRA_DB, projekt, sid, [
        {"name": "lodash", "version": "4.17.21", "purl": "pkg:npm/lodash@4.17.21"}])
    sk.set_bewertung(CRA_DB, projekt, [k["id"] for k in
                                       sk.list_komponenten(CRA_DB, projekt, sid)],
                     status="geprueft",
                     notiz="Lieferant, Lizenz und Advisories geprüft", von="pytest")
    cdb.save_support_period(CRA_DB, projekt, {
        "markteintritt_datum": date.today().isoformat(), "support_jahre": 5,
        "update_kanal": "Auto-Update über den Produktkanal",
        # #1762: Zum Release gehören seitdem auch die zwei Zusagen (kostenlose
        # Sicherheitsupdates, getrennte Kanäle) und der Kaufhinweis. „Vollständig"
        # heißt vollständig — sonst wäre die Null-Linie keine.
        "sicherheitsupdate_kanal": "security.example.test/updates",
        "funktionsupdate_kanal": "releases.example.test",
        "sicherheitsupdates_kostenlos": True,
        "kanaele_getrennt": True,
        "support_end_kaufhinweis_url": "https://example.test/support-ende"})
    cdb.save_psirt(CRA_DB, projekt, {
        "disclosure_policy_url": "https://example.test/security",
        "psirt_contacts": ["psirt@example.test"]})


@pytest.fixture
def projekt():
    cdb.ensure_db(CRA_DB)
    mdb.ensure_table(CRA_DB)
    _leeren(PROJ)
    cdb.delete_projekt(CRA_DB, PROJ)
    cdb.save_projekt(CRA_DB, PROJ, unternehmen="pytest-firma-1745", produkt="Testprodukt")
    yield PROJ
    _leeren(PROJ)
    cdb.delete_projekt(CRA_DB, PROJ)


@pytest.fixture
def gruen(projekt):
    """Projekt, bei dem Phase 1 **und** Phase 2 grün sind — die Null-Linie."""
    _phase1_gruen(projekt)
    _release_vollstaendig(projekt)
    g = evaluate(projekt, version=VERSION)
    assert g["ampel"] == "gruen", f"Null-Linie nicht grün: {g['offene_punkte']}"
    return projekt


def _punkte(gate: dict, typ: str) -> list[dict]:
    return [p for p in gate["release_punkte"] if p["typ"] == typ]


# ── Vertrag: Phasen-Trennung ─────────────────────────────────────────────────

def test_phase_und_punkte_getrennt(projekt):
    """Ohne Version ist das Ergebnis Phase 1, mit Version Phase 2 — und die offenen
    Punkte bleiben als Vereinigung lesbar, damit das bestehende Panel weiterläuft."""
    p1 = evaluate(projekt)
    assert p1["phase"] == "produkt"
    assert p1["release_punkte"] == [] and p1["release_befunde"] == {}
    assert p1["offene_punkte"] == p1["produkt_punkte"]

    p2 = evaluate(projekt, version=VERSION)
    assert p2["phase"] == "release"
    assert p2["release_punkte"], "ohne jede Release-Pflege muss Phase 2 Punkte melden"
    assert p2["offene_punkte"] == p2["produkt_punkte"] + p2["release_punkte"]


def test_punkte_behalten_die_panel_form(projekt):
    """Das Frontend baut aus ``typ``/``titel``/``hinweis``/``link`` das „hier pflegen"."""
    gate = evaluate(projekt, version=VERSION)
    gueltige_tabs = {"requirements", "pflichtdoku", "traceability", "konformitaet",
                     "meldungen"}
    for p in gate["offene_punkte"]:
        assert p["typ"] and p["titel"] and p["hinweis"]
        assert p["link"] in gueltige_tabs, p


def test_version_normalisierung():
    """``v1.4.0`` aus dem Repo-Tag und ``1.4.0`` aus der Hand sind dieselbe Version."""
    assert _norm_version("v1.4.0") == _norm_version(" 1.4.0 ") == "1.4.0"
    assert _norm_version(None) == ""
    assert _norm_version("v") == "v"            # einzelnes 'v' ist keine Version


# ── Anhang I Teil II Nr. 4 — Advisory zu behobenen Schwachstellen ────────────

def test_behobene_schwachstelle_ohne_advisory_ist_bedingt(gruen):
    """Ein fehlendes Advisory macht das Release nicht nicht-konform, aber nicht
    nachweisbar — deshalb ``bedingt`` und nicht ``rot``."""
    cdb.save_vuln(CRA_DB, gruen, {"cve_id": "CVE-2026-1001", "titel": "Pfad-Traversal",
                                  "schwere": "high", "status": "fixed",
                                  "fixed_in_version": VERSION})
    gate = evaluate(gruen, version=VERSION)
    assert gate["ampel"] == "bedingt"
    punkte = _punkte(gate, "advisory")
    assert len(punkte) == 1
    assert "CVE-2026-1001" in punkte[0]["hinweis"]
    assert punkte[0]["ampel_wirkung"] == "bedingt"
    assert gate["behobene_ohne_advisory"] == ["CVE-2026-1001"]


def test_mit_advisory_wird_nicht_mehr_gemeldet(gruen):
    vid = cdb.save_vuln(CRA_DB, gruen, {"cve_id": "CVE-2026-1001", "schwere": "high",
                                        "status": "fixed", "fixed_in_version": VERSION})
    cdb.save_vuln(CRA_DB, gruen, {"id": vid, "cve_id": "CVE-2026-1001", "schwere": "high",
                                  "status": "fixed", "fixed_in_version": VERSION,
                                  "advisory_url": "https://example.test/adv/1001"})
    gate = evaluate(gruen, version=VERSION)
    assert _punkte(gate, "advisory") == []
    assert gate["ampel"] == "gruen"


def test_advisory_nur_fuer_dieses_release(gruen):
    """Eine in einer anderen Version behobene Schwachstelle gehört nicht in dieses
    Release — sonst schleppt jedes Release die Historie mit."""
    cdb.save_vuln(CRA_DB, gruen, {"cve_id": "CVE-2026-0001", "schwere": "high",
                                  "status": "fixed", "fixed_in_version": "1.0.0"})
    assert _punkte(evaluate(gruen, version=VERSION), "advisory") == []


def test_wontfix_verlangt_kein_advisory(gruen):
    """``wontfix`` heißt: nichts behoben — also nichts zu veröffentlichen."""
    cdb.save_vuln(CRA_DB, gruen, {"cve_id": "CVE-2026-0002", "schwere": "medium",
                                  "status": "wontfix", "fixed_in_version": VERSION})
    assert _punkte(evaluate(gruen, version=VERSION), "advisory") == []


# ── Anhang I Teil II Nr. 1 — SBOM zur Release-Version ────────────────────────

def test_sbom_zur_version_fehlt_ist_bedingt(projekt):
    _phase1_gruen(projekt)
    _release_vollstaendig(projekt, version="1.0.0")      # SBOM nur zur Altversion
    gate = evaluate(projekt, version=VERSION)
    assert gate["ampel"] == "bedingt"
    punkte = _punkte(gate, "sbom")
    assert len(punkte) == 1 and VERSION in punkte[0]["titel"]
    assert gate["sbom_version_fehlt"] is True


def test_sbom_mit_v_prefix_zaehlt(projekt):
    """Tag ``v1.4.0`` im Repo, ``1.4.0`` in der SBOM-Zeile — dieselbe Version."""
    _phase1_gruen(projekt)
    _release_vollstaendig(projekt, version=VERSION)
    gate = evaluate(projekt, version=f"v{VERSION}")
    assert _punkte(gate, "sbom") == [] and gate["ampel"] == "gruen"


def test_sbom_ohne_versionsbezug_ist_nicht_zuordenbar(projekt):
    """Altbestand ohne Versionsangabe ist kein Fehler, belegt das Release aber nicht —
    der Hinweis muss das sagen, damit niemand eine vorhandene SBOM für verloren hält."""
    _phase1_gruen(projekt)
    _release_vollstaendig(projekt, version="1.0.0")
    con = cdb._connect(CRA_DB)
    try:                                       # Altbestand simulieren
        con.execute("UPDATE cra_sbom SET release_version='' WHERE projekt_name=?", (projekt,))
        con.commit()
    finally:
        con.close()
    gate = evaluate(projekt, version=VERSION)
    assert gate["release_befunde"]["sbom_ohne_versionsbezug"] == 1
    assert "nicht zuordenbar" in _punkte(gate, "sbom")[0]["hinweis"]


# ── Art. 13 Abs. 8 — Support-Zeitraum ────────────────────────────────────────

def test_release_nach_eol_ist_rot(gruen):
    """Der Hersteller verspricht Sicherheitsupdates, die er nicht mehr liefert."""
    vorbei = (date.today() - timedelta(days=30)).isoformat()
    cdb.save_support_period(CRA_DB, gruen, {
        "markteintritt_datum": "2015-01-01", "support_jahre": 5, "eol_datum": vorbei,
        "update_kanal": "Auto-Update"})
    gate = evaluate(gruen, version=VERSION)
    assert gate["ampel"] == "rot" and gate["konform"] is False
    punkte = _punkte(gate, "support")
    assert len(punkte) == 1 and punkte[0]["ampel_wirkung"] == "rot"
    assert vorbei in punkte[0]["titel"]                      # Hinweis auf den Zeitraum
    assert punkte[0]["ref"] == "Art. 13(8)"
    assert gate["support_ueberschritten"] is True


def test_support_zeitraum_nicht_festgelegt_ist_bedingt(projekt):
    """Ohne Markteintritt ist die Frage nicht entscheidbar — Akte unvollständig,
    keine festgestellte Pflichtverletzung."""
    _phase1_gruen(projekt)
    cdb.save_sbom(CRA_DB, projekt, {"release_version": VERSION})
    cdb.save_psirt(CRA_DB, projekt, {"disclosure_policy_url": "https://example.test/s",
                                     "psirt_contacts": ["psirt@example.test"]})
    gate = evaluate(projekt, version=VERSION)
    assert gate["ampel"] == "bedingt"
    titel = [p["titel"] for p in _punkte(gate, "support")]
    assert "Support-Zeitraum nicht festgelegt" in titel
    assert "Update-Kanal nicht dokumentiert" in titel


def test_eol_in_der_zukunft_ist_kein_punkt(gruen):
    # Der Satz überschreibt den Support-Datensatz der Null-Linie vollständig —
    # die Zusagen aus #1762 müssen deshalb mitkommen, sonst prüft dieser Test
    # nicht mehr den EOL, sondern die fehlenden Zusagen.
    cdb.save_support_period(CRA_DB, gruen, {
        "markteintritt_datum": date.today().isoformat(), "support_jahre": 7,
        "update_kanal": "Auto-Update",
        "sicherheitsupdate_kanal": "security.example.test/updates",
        "sicherheitsupdates_kostenlos": True, "kanaele_getrennt": True,
        "support_end_kaufhinweis_url": "https://example.test/support-ende"})
    gate = evaluate(gruen, version=VERSION)
    assert _punkte(gate, "support") == [] and gate["ampel"] == "gruen"


# ── Art. 14 — Meldefristen ───────────────────────────────────────────────────

def _meldung(projekt: str, *, stunden_zurueck: float, typ: str = "vuln_exploited") -> int:
    erkannt = datetime.now(timezone.utc) - timedelta(hours=stunden_zurueck)
    return mdb.create_meldung(CRA_DB, projekt, {
        "typ": typ, "titel": "Aktiv ausgenutzte Schwachstelle",
        "erkannt_am": erkannt.isoformat()})


# #1760: ``set_stufe`` verlangt jetzt den Adressaten der Meldung (CSIRT-
# Koordinator + ENISA mit Einreichungsreferenz). Für das Gate ist nur der
# Zeitstempel interessant — die Angaben sind hier reine Testdaten.
_EMPFAENGER = {"csirt": {"mitgliedstaat": "DE", "referenz": "CB-TEST"},
               "enisa": {"referenz": "SRP-TEST"}}


def test_ueberfaellige_meldefrist_ist_rot(gruen):
    _meldung(gruen, stunden_zurueck=30 * 24)          # alle Stufen längst vorbei
    gate = evaluate(gruen, version=VERSION)
    assert gate["ampel"] == "rot"
    punkte = _punkte(gate, "meldefrist")
    assert punkte and punkte[0]["ampel_wirkung"] == "rot"
    assert punkte[0]["link"] == "meldungen" and punkte[0]["ref"] == "Art. 14"
    assert gate["ueberfaellige_meldungen"]


def test_laufende_meldefrist_ist_bedingt(gruen):
    """Ein Release während der laufenden 24h-Frist ist ein Signal, keine Verletzung.

    Seit #1760 kommt ein **zweiter** Punkt dazu: Die Abschlussfrist läuft ab
    Verfügbarkeit der Korrekturmaßnahme; ist dieser Zeitpunkt nicht erfasst, ist
    sie ``unbestimmt`` und wird getrennt ausgewiesen. Vorher wurde sie ab
    Erkennung gerechnet und erschien als „laufend" — eine Frist, die in
    Wirklichkeit noch gar nicht begonnen hatte. Beide Punkte wirken ``bedingt``.
    """
    _meldung(gruen, stunden_zurueck=1)
    gate = evaluate(gruen, version=VERSION)
    assert gate["ampel"] == "bedingt"
    punkte = _punkte(gate, "meldefrist")
    assert len(punkte) == 2
    assert all(p["ampel_wirkung"] == "bedingt" for p in punkte)
    titel = " | ".join(p["titel"] for p in punkte)
    assert "laufende" in titel and "ohne Fristbeginn" in titel
    assert gate["ueberfaellige_meldungen"] == []


def test_gemeldete_stufe_deckt_die_frueheren_ab(gruen):
    """``set_stufe`` stempelt nur die erreichte Stufe. Ein Sprung von „erkannt" auf
    die 72h-Meldung lässt ``early_warning_gemeldet_am`` leer — das Gate darf daraus
    keine versäumte Frist machen, die der spätere Bericht abgedeckt hat."""
    mid = _meldung(gruen, stunden_zurueck=30 * 24)
    mdb.set_stufe(CRA_DB, mid, gruen, "notification_72h", _EMPFAENGER)
    rest = evaluate(gruen, version=VERSION)["release_befunde"]["meldefristen"]
    stufen = [e["stufe"] for e in rest["ueberfaellig"]]
    assert all("24h" not in s and "72h" not in s for s in stufen), stufen
    # #1760: Der Abschlussbericht ist nach 30 Tagen **nicht** überfällig — seine
    # Frist läuft ab Verfügbarkeit der Korrekturmaßnahme, und die ist hier nicht
    # erfasst. Er steht deshalb unter `unbestimmt`. Genau das war der Einwand:
    # Die alte Rechnung ab Erkennung zeigte zu früh rot.
    assert not any("Abschlussbericht" in s for s in stufen), stufen
    unbestimmt = [e["stufe"] for e in rest["unbestimmt"]]
    assert any("Abschlussbericht" in s for s in unbestimmt), unbestimmt


def test_abgeschlossene_meldung_blockiert_das_release_nicht(gruen):
    mid = _meldung(gruen, stunden_zurueck=30 * 24)
    for stufe in ("early_warning_24h", "notification_72h", "final_report"):
        mdb.set_stufe(CRA_DB, mid, gruen, stufe, _EMPFAENGER)
    gate = evaluate(gruen, version=VERSION)
    assert _punkte(gate, "meldefrist") == [] and gate["ampel"] == "gruen"


def test_unlesbarer_erkennungszeitpunkt_erscheint_als_ungeprueft(gruen):
    """Ohne Basiszeitpunkt ist keine Frist berechenbar. Der Punkt muss sichtbar
    bleiben — nicht als erledigt durchfallen."""
    _meldung(gruen, stunden_zurueck=1)
    con = cdb._connect(CRA_DB)
    try:
        con.execute("UPDATE cra_meldung SET erkannt_am='' WHERE projekt_name=?", (gruen,))
        con.commit()
    finally:
        con.close()
    gate = evaluate(gruen, version=VERSION)
    punkte = _punkte(gate, "meldefrist")
    assert len(punkte) == 1 and punkte[0]["ungeprueft"] is True
    assert gate["ampel"] == "bedingt"


# ── Anhang I Teil II — Schwachstellenbehandlung dokumentiert ─────────────────

def test_fehlende_schwachstellenbehandlung_ist_bedingt(projekt):
    _phase1_gruen(projekt)
    cdb.save_sbom(CRA_DB, projekt, {"release_version": VERSION})
    cdb.save_support_period(CRA_DB, projekt, {
        "markteintritt_datum": date.today().isoformat(), "support_jahre": 5,
        "update_kanal": "Auto-Update"})
    gate = evaluate(projekt, version=VERSION)
    assert gate["ampel"] == "bedingt"
    punkte = _punkte(gate, "vuln_handling")
    assert len(punkte) == 1
    assert "PSIRT-Kontakt" in punkte[0]["hinweis"]
    assert gate["release_befunde"]["vuln_handling"] == {"policy_url": False,
                                                        "psirt_kontakte": 0}


def test_security_md_zaehlt_wie_disclosure_policy(projekt):
    """Beide beantworten dieselbe Pflicht: Wohin melden Dritte eine Schwachstelle?"""
    _phase1_gruen(projekt)
    _release_vollstaendig(projekt)
    cdb.save_psirt(CRA_DB, projekt, {"security_md_url": "https://example.test/SECURITY.md",
                                     "psirt_contacts": ["psirt@example.test"]})
    gate = evaluate(projekt, version=VERSION)
    assert _punkte(gate, "vuln_handling") == [] and gate["ampel"] == "gruen"


# ── Ungeprüft ist nicht erfüllt ──────────────────────────────────────────────

@pytest.mark.parametrize(("ziel", "typ"), [
    ("cra.db.list_vuln", "advisory"),
    ("cra.db.list_sbom", "sbom"),
    ("cra.db.load_support_period", "support"),
    ("cra.db.load_psirt", "vuln_handling"),
    ("cra.meldung_db.list_meldungen", "meldefrist"),
])
def test_defekte_datenquelle_erscheint_als_ungeprueft(gruen, monkeypatch, ziel, typ):
    """Der wichtigste Fall: Fällt eine Nebenquelle aus, darf das Gate weder abstürzen
    noch grün bleiben. Ein stilles ``except: pass`` ließe den Punkt verschwinden und
    der Anwender hielte für geprüft, was niemand geprüft hat."""
    modul, name = ziel.rsplit(".", 1)

    def _kaputt(*_a, **_k):
        raise RuntimeError("DB weg")

    monkeypatch.setattr(f"{modul}.{name}", _kaputt)
    gate = evaluate(gruen, version=VERSION)
    punkte = _punkte(gate, typ)
    assert punkte, f"{ziel} fiel aus, aber kein Punkt gemeldet"
    assert all(p.get("ungeprueft") for p in punkte)
    assert gate["ampel"] == "bedingt" and gate["konform"] is False


def test_defekte_quelle_stoppt_die_uebrigen_pruefungen_nicht(gruen, monkeypatch):
    """Jede Prüfung kapselt ihre Fehler selbst — sonst nimmt der erste Ausfall die
    folgenden Prüfpunkte lautlos mit."""
    def _kaputt(*_a, **_k):
        raise RuntimeError("DB weg")

    monkeypatch.setattr("cra.db.list_vuln", _kaputt)
    cdb.save_psirt(CRA_DB, gruen, {})            # PSIRT bewusst leer
    gate = evaluate(gruen, version=VERSION)
    assert _punkte(gate, "advisory")[0]["ungeprueft"] is True
    assert _punkte(gate, "vuln_handling"), "nachfolgende Prüfung lief nicht"


# ── Regression: Phase 1 unverändert ──────────────────────────────────────────

def test_phase1_bleibt_unveraendert_trotz_release_maengeln(projekt):
    """Release-Mängel dürfen die Phase-1-Bewertung nicht anfassen. Ohne diese Trennung
    zeigt die Produkt-Ampel Release-Mängel an und der Anwender weiß nicht, ob sein
    Produkt oder sein Release das Problem ist (#1742)."""
    _phase1_gruen(projekt)
    vorher = evaluate(projekt)
    assert vorher["ampel"] == "gruen"

    # Jeder Release-Mangel auf einmal — darunter zwei rote.
    cdb.save_vuln(CRA_DB, projekt, {"cve_id": "CVE-2026-9999", "schwere": "high",
                                    "status": "fixed", "fixed_in_version": VERSION})
    cdb.save_support_period(CRA_DB, projekt, {
        "markteintritt_datum": "2010-01-01", "support_jahre": 5,
        "eol_datum": (date.today() - timedelta(days=1)).isoformat()})
    _meldung(projekt, stunden_zurueck=30 * 24)

    nachher = evaluate(projekt)
    assert nachher == vorher, "Phase 1 hat sich durch Release-Mängel verändert"
    assert nachher["phase"] == "produkt" and nachher["release_punkte"] == []
    # Gegenprobe: mit Version schlagen dieselben Daten durch.
    assert evaluate(projekt, version=VERSION)["ampel"] == "rot"


def test_ergebnis_ist_nur_additiv_gewachsen(projekt):
    """Alte Schlüssel bleiben, neue kommen hinzu — ein fehlender Alt-Schlüssel bricht
    Panel, ``release-check`` und Nachweis-Report gleichzeitig."""
    gate = evaluate(projekt)
    assert set(gate) == _ALTE_SCHLUESSEL | _NEUE_SCHLUESSEL


def test_flache_befunde_sind_in_phase1_ungeprueft(projekt):
    """In Phase 1 laufen die Release-Prüfungen nicht. ``None`` sagt „nicht geprüft";
    ein ``False``/``[]`` wäre die Behauptung, es sei geprüft und in Ordnung."""
    gate = evaluate(projekt)
    for key in ("behobene_ohne_advisory", "sbom_version_fehlt",
                "support_ueberschritten", "ueberfaellige_meldungen",
                "fremdkomponenten_unbewertet", "upstream_meldung_offen",
                "komponenten_befund_widerspruch",
                "release_art", "release_art_widersprueche"):
        assert gate[key] is None, key


def test_release_katalog_findet_seine_rechenquellen(projekt):
    """Der Release-Katalog (#1744) benennt je gerechnetem Punkt den Gate-Schlüssel,
    unter dem das Ergebnis steht. Läuft ein Name auseinander, zeigt der Nachweis
    eine leere Zelle statt eines Befundes — und niemand merkt es."""
    rc = pytest.importorskip("cra.release_checkliste",
                             reason="Release-Katalog (#1744) noch nicht vorhanden")
    gate = evaluate(projekt, version=VERSION)
    fehlend = [i["quelle"] for i in rc.katalog()
               if i.get("art") == "gerechnet" and i.get("quelle")
               and i["quelle"] not in gate]
    assert not fehlend, f"Katalog nennt Gate-Schlüssel, die es nicht gibt: {fehlend}"


def test_phase1_punkte_behalten_ihre_felder(projekt):
    """Die Phase-2-Felder ``phase``/``ampel_wirkung`` hängen nur an Release-Punkten.
    An Phase-1-Punkten wären sie eine stille Vertragsänderung für das Frontend."""
    gate = evaluate(projekt)                      # frisches Projekt → viele Punkte
    assert gate["produkt_punkte"]
    for p in gate["produkt_punkte"]:
        assert "phase" not in p and "ampel_wirkung" not in p, p
        assert set(p) <= {"typ", "titel", "hinweis", "link", "requirement_id",
                          "ref", "ungeprueft"}, p   # ungeprueft: #1751
