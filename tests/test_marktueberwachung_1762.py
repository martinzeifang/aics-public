"""Marktüberwachungsregister und Art.-24-Rolle (#1762, Punkte 5 und 6).

Punkt 6: ``cra/korrektur_db.py`` deckt den Fall ab, in dem **der Hersteller**
aktiv wird. Der umgekehrte Fall — die **Behörde** verlangt Unterlagen, ordnet
Maßnahmen an, setzt eine Frist (Art. 52-56) — hatte keinen Ort und lag in
Postfächern.

Punkt 5: Der Open-Source-Verwalter (Art. 24) fehlte als Rolle. Er ist
ausdrücklich **kein** Hersteller; wer ihn als Händler erfasste, hängte ihm eine
CE-Prüfpflicht an, die er nicht hat.

Zwei Invarianten sind hier wichtiger als das CRUD:

- ``beantwortet`` ist ohne Beleg nicht speicherbar. Ein Haken, hinter dem nichts
  steht, beendet das Nachfragen.
- Eine versäumte Behördenfrist wirkt ``rot`` — dieselbe Kategorie wie die
  versäumte Meldefrist nach Art. 14, nicht die der unvollständigen Akte.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from cra import db as cdb
from cra import marktueberwachung_db as mdb

CRA_DB = Path("data/db/cra.sqlite")
MU = "/api/cra-marktueberwachung"
PROJ = "pytest-marktaufsicht-1762"
VERSION = "1.2.3"


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = "ok", ["*"]
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _leeren(projekt: str) -> None:
    """Unter Postgres überleben Zeilen den Lauf (#1332/#1706) — explizit leeren."""
    mdb.ensure_table(CRA_DB)
    con = cdb._connect(CRA_DB)
    try:
        con.try_execute("DELETE FROM cra_marktaufsicht WHERE projekt_name=?", (projekt,))
        con.commit()
    finally:
        con.close()


@pytest.fixture
def projekt():
    cdb.ensure_db(CRA_DB)
    _leeren(PROJ)
    cdb.delete_projekt(CRA_DB, PROJ)
    cdb.save_projekt(CRA_DB, PROJ, unternehmen="pytest-firma-1762", produkt="Testprodukt")
    yield PROJ
    _leeren(PROJ)
    cdb.delete_projekt(CRA_DB, PROJ)


def _vorgang(projekt: str, **over) -> int:
    daten = {"vorgangsart": "auskunftsverlangen", "behoerde_name": "Bundesnetzagentur",
             "behoerde_land": "DE", "aktenzeichen": "MUE-2026/4711",
             "eingang_am": date.today().isoformat(),
             "frist_am": (date.today() + timedelta(days=14)).isoformat(),
             "gegenstand": "Technische Dokumentation", "verlangen": "Anhang VII vorlegen"}
    daten.update(over)
    return mdb.create_vorgang(CRA_DB, projekt, daten)


# ── Stammdaten ───────────────────────────────────────────────────────────────

def test_vorgang_anlegen_und_lesen(projekt):
    pk = _vorgang(projekt)
    v = mdb.get_vorgang(CRA_DB, pk, projekt)
    assert v["behoerde_name"] == "Bundesnetzagentur"
    assert v["aktenzeichen"] == "MUE-2026/4711"
    assert v["status"] == "offen"
    assert v["unterlagen"] == []
    assert v["frist"]["tage_verbleibend"] == 14
    assert v["frist"]["ampel"] == "gruen"
    assert v["frist_versaeumt"] is False
    assert v["audit_trail"][0]["event"] == "angelegt"


def test_ohne_behoerde_nicht_speicherbar(projekt):
    with pytest.raises(ValueError) as e:
        _vorgang(projekt, behoerde_name="  ")
    assert "Behörde fehlt" in str(e.value)


def test_unbekannte_vorgangsart_wird_abgewiesen(projekt):
    with pytest.raises(ValueError):
        _vorgang(projekt, vorgangsart="hausdurchsuchung")


def test_frist_als_umschreibung_wird_abgewiesen(projekt):
    """Aus „nächste Woche" lässt sich kein Fristenlauf rechnen — und ein
    Datumsfeld, das Prosa annimmt, hat stillschweigend keine Uhr."""
    with pytest.raises(ValueError) as e:
        _vorgang(projekt, frist_am="nächste Woche")
    assert "kein Datum" in str(e.value)


def test_idor_fremdes_projekt_sieht_nichts(projekt):
    pk = _vorgang(projekt)
    assert mdb.get_vorgang(CRA_DB, pk, "pytest-fremdes-projekt-1762") is None


# ── Unterlagen und Antwortzwang ──────────────────────────────────────────────

def test_beantwortet_ohne_beleg_ist_nicht_speicherbar(projekt):
    pk = _vorgang(projekt)
    with pytest.raises(ValueError) as e:
        mdb.set_status(CRA_DB, pk, projekt, "beantwortet")
    text = str(e.value)
    assert "Beleg" in text
    assert "Unterlage" in text
    # Der Stand bleibt, was er war — kein halb gewechselter Zustand.
    assert mdb.get_vorgang(CRA_DB, pk, projekt)["status"] == "offen"


def test_unterlage_traegt_den_statuswechsel(projekt):
    pk = _vorgang(projekt)
    mdb.add_unterlage(CRA_DB, pk, projekt, "Anhang VII, Abschnitt 3",
                      ref="Ablage/CRA/2026/AnhangVII.pdf")
    v = mdb.set_status(CRA_DB, pk, projekt, "beantwortet")
    assert v["status"] == "beantwortet"
    assert v["beantwortet_am"] == date.today().isoformat()
    assert v["unterlagen"][0]["titel"] == "Anhang VII, Abschnitt 3"
    assert v["unterlagen"][0]["uebergeben_am"] == date.today().isoformat()


def test_ergebnistext_traegt_den_statuswechsel_auch(projekt):
    """Wenn nichts vorzulegen war, genügt die Angabe, was mitgeteilt wurde."""
    pk = _vorgang(projekt)
    mdb.update_vorgang(CRA_DB, pk, projekt, {
        "ergebnis": "Behörde über Nichtbetroffenheit des Produkts informiert."})
    v = mdb.set_status(CRA_DB, pk, projekt, "beantwortet")
    assert v["status"] == "beantwortet"


def test_unterlage_ohne_bezeichnung_wird_abgewiesen(projekt):
    pk = _vorgang(projekt)
    with pytest.raises(ValueError):
        mdb.add_unterlage(CRA_DB, pk, projekt, "   ")


# ── Fristen ──────────────────────────────────────────────────────────────────

def test_versaeumte_frist_bei_laufendem_vorgang(projekt):
    pk = _vorgang(projekt, frist_am=(date.today() - timedelta(days=5)).isoformat())
    v = mdb.get_vorgang(CRA_DB, pk, projekt)
    assert v["frist"]["verstrichen"] is True
    assert v["frist_versaeumt"] is True
    u = mdb.uebersicht(CRA_DB, projekt)
    assert u["versaeumt"] == 1
    assert u["versaeumte_vorgaenge"][0]["tage_ueberschritten"] == 5


def test_erledigter_vorgang_mahnt_nicht_weiter(projekt):
    """Nach „beantwortet" ist das Datum Historie, keine Mahnung — sonst zeigt
    das Register dauerhaft Rot für abgearbeitete Vorgänge."""
    pk = _vorgang(projekt, frist_am=(date.today() - timedelta(days=5)).isoformat())
    mdb.add_unterlage(CRA_DB, pk, projekt, "Stellungnahme vom 10.10.")
    mdb.set_status(CRA_DB, pk, projekt, "beantwortet")
    v = mdb.get_vorgang(CRA_DB, pk, projekt)
    assert v["frist"]["verstrichen"] is True      # das Datum ist vorbei …
    assert v["frist_versaeumt"] is False          # … aber nichts ist offen
    assert mdb.uebersicht(CRA_DB, projekt)["versaeumt"] == 0


def test_laufende_vorgaenge_stehen_vorn(projekt):
    """Sortierung: laufend vor erledigt, dringendste Frist zuerst."""
    spaet = _vorgang(projekt, frist_am=(date.today() + timedelta(days=30)).isoformat(),
                     aktenzeichen="SPAET")
    frueh = _vorgang(projekt, frist_am=(date.today() + timedelta(days=2)).isoformat(),
                     aktenzeichen="FRUEH")
    ids = [v["id"] for v in mdb.list_vorgaenge(CRA_DB, projekt)]
    assert ids.index(frueh) < ids.index(spaet)


def test_uebersicht_bei_leerem_register(projekt):
    u = mdb.uebersicht(CRA_DB, projekt)
    assert u == {"gesamt": 0, "laufend": 0, "versaeumt": 0,
                 "versaeumte_vorgaenge": [], "naechste_frist": None,
                 "schlechteste_ampel": "unbekannt"}


# ── Gate ─────────────────────────────────────────────────────────────────────

def test_gate_rot_bei_versaeumter_behoerdenfrist(projekt):
    """Rot, wie bei der versäumten Meldefrist nach Art. 14: Eine unbeantwortet
    verstrichene Behördenfrist ist eine Pflichtverletzung gegenüber der Behörde,
    kein Nachweismangel."""
    from cra.konformitaet_gate import _check_marktaufsicht

    _vorgang(projekt, frist_am=(date.today() - timedelta(days=2)).isoformat())
    befunde, punkte = {}, []
    _check_marktaufsicht(projekt, VERSION, befunde, punkte)
    assert befunde["marktaufsicht_versaeumt"] == 1
    rot = [p for p in punkte if p["ampel_wirkung"] == "rot"]
    assert len(rot) == 1
    assert "versäumt" in rot[0]["titel"]
    assert rot[0]["link"] == "korrektur"


def test_gate_bedingt_bei_laufendem_vorgang(projekt):
    """Ein laufender Vorgang ist Normalbetrieb — ein Signal, keine Sperre."""
    from cra.konformitaet_gate import _check_marktaufsicht

    _vorgang(projekt)
    befunde, punkte = {}, []
    _check_marktaufsicht(projekt, VERSION, befunde, punkte)
    assert befunde["marktaufsicht_versaeumt"] == 0
    assert len(punkte) == 1
    assert punkte[0]["ampel_wirkung"] == "bedingt"


def test_gate_schweigt_ohne_vorgaenge(projekt):
    from cra.konformitaet_gate import _check_marktaufsicht

    befunde, punkte = {}, []
    _check_marktaufsicht(projekt, VERSION, befunde, punkte)
    assert punkte == []
    assert befunde["marktaufsicht_versaeumt"] == 0


# ── Aufräumen beim Projektlöschen ───────────────────────────────────────────

def test_geloeschtes_projekt_laesst_keine_vorgaenge_zurueck(projekt):
    """Behördenname, Aktenzeichen und vorgelegte Unterlagen sind Daten des
    Mandanten — sie gehören zur Löschung (#1752)."""
    _vorgang(projekt)
    cdb.delete_projekt(CRA_DB, projekt)
    assert mdb.list_vorgaenge(CRA_DB, projekt) == []


def test_tabelle_steht_in_der_aufraeum_liste():
    from cra.db import PROJEKT_TABELLEN

    assert ("cra_marktaufsicht", "projekt_name") in PROJEKT_TABELLEN


# ── Endpunkte ────────────────────────────────────────────────────────────────

def test_api_crud(client, auth_headers, projekt):
    r = client.post(f"{MU}/projekte/{projekt}/vorgaenge", headers=auth_headers,
                    json={"vorgangsart": "anordnung", "behoerde_name": "BNetzA",
                          "aktenzeichen": "AN-1", "gegenstand": "Rücknahme",
                          "frist_am": (date.today() + timedelta(days=5)).isoformat()})
    assert r.status_code == 201, r.json
    pk = r.json["id"]
    assert r.json["frist"]["ampel"] == "gelb"      # 5 Tage → kurze Vorlaufzeit

    r = client.get(f"{MU}/projekte/{projekt}/vorgaenge", headers=auth_headers)
    assert r.status_code == 200 and len(r.json) == 1

    r = client.post(f"{MU}/projekte/{projekt}/vorgaenge/{pk}/unterlagen",
                    headers=auth_headers, json={"titel": "Rücknahmeplan"})
    assert r.status_code == 200, r.json
    assert r.json["unterlagen"][0]["titel"] == "Rücknahmeplan"

    r = client.post(f"{MU}/projekte/{projekt}/vorgaenge/{pk}/status",
                    headers=auth_headers, json={"status": "beantwortet"})
    assert r.status_code == 200 and r.json["status"] == "beantwortet"

    r = client.get(f"{MU}/projekte/{projekt}/uebersicht", headers=auth_headers)
    assert r.status_code == 200 and r.json["laufend"] == 0

    r = client.delete(f"{MU}/projekte/{projekt}/vorgaenge/{pk}", headers=auth_headers)
    assert r.status_code == 200


def test_api_meldet_pflichtangaben_als_400(client, auth_headers, projekt):
    r = client.post(f"{MU}/projekte/{projekt}/vorgaenge", headers=auth_headers,
                    json={"behoerde_name": ""})
    assert r.status_code == 400, r.json
    assert "Behörde" in r.json["error"]


def test_api_unbekanntes_projekt_404(client, auth_headers):
    r = client.post(f"{MU}/projekte/gibt-es-nicht-1762/vorgaenge",
                    headers=auth_headers, json={"behoerde_name": "BNetzA"})
    assert r.status_code == 404


def test_api_constants(client, auth_headers):
    r = client.get(f"{MU}/constants", headers=auth_headers)
    assert r.status_code == 200
    assert "anordnung" in r.json["vorgangsarten"]
    assert "beantwortet" in r.json["status"]


# ── Punkt 5: Open-Source-Verwalter (Art. 24) ────────────────────────────────

def test_rolle_art24_existiert():
    from cra import akteure_db as adb

    assert "open_source_verwalter" in adb.ROLLEN
    assert adb.CHECKLISTE["open_source_verwalter"]


def test_art24_checkliste_fordert_keine_ce_pruefung():
    """Der Verwalter bringt nicht in Verkehr — eine CE-/DoC-Prüfpflicht wäre
    falsch angehängt und würde seine Rolle mit der des Herstellers vermischen."""
    from cra import akteure_db as adb

    punkte = adb.CHECKLISTE["open_source_verwalter"]
    assert not any("ce_" in p or p.startswith("doc_") for p in punkte), punkte
    assert "cybersicherheitspolitik_dokumentiert" in punkte
    assert "mitwirkung_marktaufsicht_geregelt" in punkte
    assert "abgrenzung_zur_herstellerrolle_dokumentiert" in punkte


def test_art24_akteur_anlegen(tmp_path):
    from cra import akteure_db as adb

    db = tmp_path / "cra.sqlite"
    aid = adb.create_akteur(db, PROJ, {
        "rolle": "open_source_verwalter", "name": "Beispiel-Stiftung e.V.",
        "aufgabenumfang": "Verwaltung der Bibliothek libbeispiel"})
    a = adb.get_akteur(db, aid, PROJ)
    assert a["rolle"] == "open_source_verwalter"
    assert a["checkliste_vollstaendig"] is False
    adb.update_akteur(db, aid, PROJ, {"checkliste": {n: True for n in a["soll_nachweise"]}})
    assert adb.get_akteur(db, aid, PROJ)["checkliste_vollstaendig"] is True


def test_art24_rolle_ueber_die_api(client, auth_headers, projekt):
    r = client.get("/api/cra-akteure/constants", headers=auth_headers)
    assert r.status_code == 200
    assert "open_source_verwalter" in r.json["rollen"]
    r = client.post(f"/api/cra-akteure/projekte/{projekt}/akteure", headers=auth_headers,
                    json={"rolle": "open_source_verwalter", "name": "Beispiel-Stiftung"})
    assert r.status_code == 201, r.json
    assert r.json["rolle"] == "open_source_verwalter"
