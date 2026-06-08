"""Tests für DSFA ↔ Risikobewertung-Verknüpfung (#1084 S14, #1085 S15).

Deckt ab:
- Neues Risikobewertungs-Framework `DSGVO-DSFA` (Felder, Scoring likelihood×severity,
  Pflichtfelder Art. 35 Abs. 7 c+d), ohne EU-AI-Act/andere zu verändern.
- DB-Migration: `dsgvo_dpia.rb_projekt_id` vorhanden + Setter/Getter.
- Bei DSFA-Anlage wird automatisch ein verknüpftes rb_projekt (DSGVO-DSFA) erzeugt
  und dessen Name in `dsgvo_dpia.rb_projekt_id` gespeichert.
- Compliance-Aufteilung: notwendigkeit_grund (Art. 35(7)b), konsultation_* (Art. 36),
  naechstes_review (Art. 35(11)) BLEIBEN im dsgvo_dpia.
- risk-link-Endpoint liefert Risiken(c)+Maßnahmen(d) READ-ONLY aus dem rb_projekt.

Kein Netz: rein lokale SQLite-Cross-Module-Verknüpfung.
"""
from __future__ import annotations

import pytest

from risikobewertung import frameworks as fw
from dsgvo.db import (
    save_projekt, delete_projekt,
    save_dpia, get_dpia, set_dpia_rb_projekt, list_dpia, delete_dpia,
)
from server.api.dsgvo import DB_PATH, _RB_DB_PATH, _dsfa_rb_name
from risikobewertung.db import (
    load_projekt as rb_load, save_risiko as rb_save_risiko,
    delete_projekt as rb_delete_projekt,
)

PROJEKT = "ZZ-Test-DSFA-1084"


# ── Lizenz defensiv freischalten ────────────────────────────────────

@pytest.fixture(autouse=True)
def _license_ok(monkeypatch):
    fake = {"state": "ok", "modules": ["*"]}
    try:
        import server.license_state as m
        if hasattr(m, "get_state"):
            monkeypatch.setattr(m, "get_state", lambda: dict(fake), raising=False)
    except Exception:
        pass
    yield


# ════════════════════════════════════════════════════════════════════
# Framework: DSGVO-DSFA (reine Logik, ohne App)
# ════════════════════════════════════════════════════════════════════

def test_framework_registriert():
    assert "DSGVO-DSFA" in fw.FRAMEWORK_IDS
    assert "DSGVO-DSFA" in fw.FRAMEWORK_LABELS
    assert "DSGVO-DSFA" in fw.FRAMEWORK_ERKLAERUNG


def test_framework_pflichtfelder_art_35_7_c_d():
    felder = fw.framework_felder("DSGVO-DSFA")
    keys = {f["key"] for f in felder}
    # Art. 35 Abs. 7 lit. c — Bedrohung für Rechte/Freiheiten
    assert "bedrohung_rechte_freiheiten" in keys
    # Art. 35 Abs. 7 lit. d — technische/organisatorische Maßnahme
    assert "massnahme" in keys
    # Scoring-Eingaben likelihood × severity
    assert "eintrittswahrscheinlichkeit" in keys
    assert "schwere" in keys


def test_framework_scoring_likelihood_mal_severity():
    score, label, detail = fw.berechne_risiko("DSGVO-DSFA", {
        "eintrittswahrscheinlichkeit": "Maximal",   # 4
        "schwere": "Maximal",                        # 4
    })
    assert score == 16
    assert label == "Sehr hoch"
    assert "4" in detail

    score, label, _ = fw.berechne_risiko("DSGVO-DSFA", {
        "eintrittswahrscheinlichkeit": "Vernachlässigbar",  # 1
        "schwere": "Begrenzt",                               # 2
    })
    assert score == 2
    assert label == "Niedrig"


def test_framework_scoring_unvollstaendig_none():
    score, label, detail = fw.berechne_risiko("DSGVO-DSFA", {
        "eintrittswahrscheinlichkeit": "Maximal",
    })
    assert score is None


def test_eu_ai_act_unveraendert():
    """Regression: EU-AI-Act darf durch die DSFA-Erweiterung nicht kaputtgehen."""
    assert "EU-AI-Act" in fw.FRAMEWORK_IDS
    score, label, _ = fw.berechne_risiko("EU-AI-Act", {
        "eintrittswahrscheinlichkeit": "Sehr wahrscheinlich",  # 5
        "auswirkung": "Kritisch",                              # 5
    })
    assert score == 25
    assert label == "Kritisch"


# ════════════════════════════════════════════════════════════════════
# DB-Migration + Setter/Getter
# ════════════════════════════════════════════════════════════════════

def _cleanup_projekt(name: str) -> None:
    """DSFA-Zeilen + verknüpfte rb_projekte + dsgvo-Projekt entfernen.

    dsgvo.delete_projekt cascaded NICHT auf dsgvo_dpia, daher explizit löschen,
    sonst kollidiert die UNIQUE(projekt_name, dpia_id)-Constraint bei Re-Runs."""
    try:
        for d in list_dpia(DB_PATH, name):
            rbname = (d.get("rb_projekt_id") or "").strip()
            if rbname:
                try:
                    rb_delete_projekt(_RB_DB_PATH, rbname)
                except Exception:
                    pass
            try:
                delete_dpia(DB_PATH, d["id"])
            except Exception:
                pass
    except Exception:
        pass
    try:
        delete_projekt(DB_PATH, name)
    except Exception:
        pass


@pytest.fixture
def projekt():
    _cleanup_projekt(PROJEKT)
    save_projekt(DB_PATH, name=PROJEKT, unternehmen="Test GmbH", berater="Berater X")
    yield PROJEKT
    _cleanup_projekt(PROJEKT)


def test_dpia_hat_rb_projekt_id_spalte(projekt):
    rid = save_dpia(DB_PATH, projekt, {
        "dpia_id": "DSFA-001", "titel": "Test-DSFA",
        "notwendigkeit_grund": "systematische Überwachung",
    })
    row = get_dpia(DB_PATH, rid)
    assert row is not None
    assert "rb_projekt_id" in row
    assert row["rb_projekt_id"] == ""  # Default leer (DB-Ebene)

    set_dpia_rb_projekt(DB_PATH, rid, "DSFA: X / Y")
    assert get_dpia(DB_PATH, rid)["rb_projekt_id"] == "DSFA: X / Y"


# ════════════════════════════════════════════════════════════════════
# API: Auto-Anlage des verknüpften rb_projekts (#1084)
# ════════════════════════════════════════════════════════════════════

def test_dsfa_create_legt_rb_projekt_an(client, auth_headers, projekt):
    r = client.post(
        f"/api/dsgvo/projekte/{projekt}/dpia",
        json={
            "dpia_id": "DSFA-002", "titel": "Profiling-DSFA",
            "beschreibung_verarbeitung": "Scoring der Kunden",   # Art. 35(7)a
            "notwendigkeit_grund": "Profiling großen Umfangs",   # Art. 35(7)b — bleibt lokal
            "konsultation_aufsicht": True,                       # Art. 36 — bleibt lokal
            "naechstes_review": "2027-01-01",                    # Art. 35(11) — bleibt lokal
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    rid = body["id"]
    rb_name = body["rb_projekt_id"]
    assert rb_name == _dsfa_rb_name(projekt, "DSFA-002")

    # rb_projekt existiert mit Framework DSGVO-DSFA
    rbp = rb_load(_RB_DB_PATH, rb_name)
    assert rbp is not None
    assert rbp["framework"] == "DSGVO-DSFA"
    assert rbp["meta"].get("linked_dsgvo_projekt") == projekt
    assert rbp["meta"].get("linked_dsgvo_dpia_id") == "DSFA-002"

    # rb_projekt_id ist im dsgvo_dpia gespeichert
    row = get_dpia(DB_PATH, rid)
    assert row["rb_projekt_id"] == rb_name

    # COMPLIANCE: Art. 35(7)b / Art. 36 / Art. 35(11) bleiben im dsgvo_dpia
    assert row["notwendigkeit_grund"] == "Profiling großen Umfangs"
    assert int(row["konsultation_aufsicht"]) == 1
    assert row["naechstes_review"] == "2027-01-01"


def test_dsfa_update_legt_kein_zweites_rb_projekt_an(client, auth_headers, projekt):
    r = client.post(
        f"/api/dsgvo/projekte/{projekt}/dpia",
        json={"dpia_id": "DSFA-003", "titel": "Erstanlage"},
        headers=auth_headers,
    )
    rid = r.get_json()["id"]
    rb_name = r.get_json()["rb_projekt_id"]

    # Update (id gesetzt) → kein neues rb_projekt, rb_projekt_id bleibt erhalten
    r2 = client.post(
        f"/api/dsgvo/projekte/{projekt}/dpia",
        json={"id": rid, "dpia_id": "DSFA-003", "titel": "Geändert"},
        headers=auth_headers,
    )
    assert r2.status_code == 201
    assert r2.get_json().get("rb_projekt_id") is None  # Update verknüpft nicht neu
    assert get_dpia(DB_PATH, rid)["rb_projekt_id"] == rb_name


def test_risk_link_endpoint_liest_risiken_readonly(client, auth_headers, projekt):
    # DSFA anlegen → rb_projekt
    r = client.post(
        f"/api/dsgvo/projekte/{projekt}/dpia",
        json={
            "dpia_id": "DSFA-004", "titel": "Mit Risiken",
            "beschreibung_verarbeitung": "Verarbeitung A",   # Art. 35(7)a lokal
            "notwendigkeit_grund": "Grund A",                # Art. 35(7)b lokal
        },
        headers=auth_headers,
    )
    rid = r.get_json()["id"]
    rb_name = r.get_json()["rb_projekt_id"]

    # Risiko(c) + Maßnahme(d) im rb_projekt anlegen
    rb_save_risiko(_RB_DB_PATH, {
        "projekt_name": rb_name,
        "risk_name": "Identitätsdiebstahl",
        "framework": "DSGVO-DSFA",
        "felder": {
            "bedrohung_rechte_freiheiten": "Verlust der Vertraulichkeit",  # lit. c
            "eintrittswahrscheinlichkeit": "Erheblich",
            "schwere": "Maximal",
            "massnahme": "Verschlüsselung + Zugriffskontrolle",            # lit. d
        },
        "risikowert": 12,
        "risiko_label": "Sehr hoch",
    })

    r2 = client.get(
        f"/api/dsgvo/projekte/{projekt}/dpia/{rid}/risk-link",
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.get_data(as_text=True)
    data = r2.get_json()
    assert data["rb_projekt_id"] == rb_name
    assert data["framework"] == "DSGVO-DSFA"
    # Art. 35(7)a+b lokal mitgeliefert
    assert data["beschreibung_verarbeitung"] == "Verarbeitung A"
    assert data["notwendigkeit_grund"] == "Grund A"
    # Risiken(c)+Maßnahmen(d) read-only aus rb_projekt
    assert len(data["risiken"]) == 1
    risk = data["risiken"][0]
    assert risk["bedrohung_rechte_freiheiten"] == "Verlust der Vertraulichkeit"
    assert risk["massnahme"] == "Verschlüsselung + Zugriffskontrolle"
    assert risk["risiko_label"] == "Sehr hoch"


def test_risk_link_404_fuer_fremde_dsfa(client, auth_headers, projekt):
    r = client.get(
        f"/api/dsgvo/projekte/{projekt}/dpia/99999999/risk-link",
        headers=auth_headers,
    )
    assert r.status_code == 404
