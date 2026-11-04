"""Eigene Hinweise je Projekt merken (#1835).

„Der Schwerpunkt dieses Unternehmens liegt in der Fertigung, die IT ist
ausgelagert" gilt für **jede** Bewertung dieses Mandanten. Ohne Gedächtnis
müsste der Berater den Satz bei 120 Anforderungen 120-mal tippen — und täte es
nach dem dritten Mal nicht mehr. Eine Funktion, die nur bei großer Disziplin
wirkt, wirkt nicht.

Die tragende Entscheidung ist **vorbelegen statt heimlich anhängen**: Ein Text,
den ein Kollege vor Wochen gespeichert hat, würde sonst jeden KI-Lauf steuern,
ohne dass der Bearbeiter ihn sieht. Deshalb prüft dieser Test auch, dass die
Engine den gespeicherten Hinweis **nicht** von sich aus verwendet.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared import prompt_hinweise as ph

WURZEL = Path(__file__).resolve().parents[1]
SRC = WURZEL / "frontend" / "src"

MODUL = "cra"
PROJ = "pytest-1835"


@pytest.fixture(autouse=True)
def _leer(tmp_path):
    """Eigene Registerdatei je Test — die Test-DB sammelt sonst über Läufe."""
    db = tmp_path / "ph.sqlite"
    ph.ensure_table(db)
    yield db


@pytest.fixture(autouse=True)
def _volle_lizenz():
    from server import license_state
    cur = license_state._current
    vorher = (cur.state, list(cur.modules))
    cur.state, cur.modules = "ok", ["*"]
    yield
    cur.state, cur.modules = vorher[0], vorher[1]


# ── Das Register ────────────────────────────────────────────────────────────

def test_setzen_und_lesen(_leer):
    ph.setze(MODUL, PROJ, "Schwerpunkt Fertigung.", von="user-1", db_path=_leer)
    e = ph.hole(MODUL, PROJ, db_path=_leer)
    assert e["text"] == "Schwerpunkt Fertigung."
    # #1784: Wer die Vorbelegung gesetzt hat, muss in der Akte stehen — sie
    # steuert künftig auch die Läufe von Kollegen.
    assert e["erstellt_von"] == "user-1"


def test_leerer_text_loescht(_leer):
    ph.setze(MODUL, PROJ, "etwas", von="u", db_path=_leer)
    ph.setze(MODUL, PROJ, "   ", von="u", db_path=_leer)
    assert ph.hole(MODUL, PROJ, db_path=_leer) is None


def test_unbekannter_bereich_wird_abgewiesen(_leer):
    with pytest.raises(ValueError):
        ph.setze(MODUL, PROJ, "x", bereich="erfunden", db_path=_leer)


def test_allgemeiner_hinweis_steht_vor_dem_bereichsbezogenen(_leer):
    """Der allgemeine setzt den Rahmen, der bereichsbezogene verengt ihn."""
    ph.setze(MODUL, PROJ, "Fertigungsbetrieb.", von="u", db_path=_leer)
    ph.setze(MODUL, PROJ, "Für den Bericht ausführlicher.", bereich="bericht",
             von="u", db_path=_leer)
    auf = ph.aufgeloest(MODUL, PROJ, bereich="bericht", db_path=_leer)
    assert auf["text"].index("Fertigungsbetrieb.") < auf["text"].index("ausführlicher")
    assert len(auf["quellen"]) == 2


def test_ohne_bereich_nur_der_allgemeine(_leer):
    ph.setze(MODUL, PROJ, "allgemein", von="u", db_path=_leer)
    ph.setze(MODUL, PROJ, "nur Bericht", bereich="bericht", von="u", db_path=_leer)
    auf = ph.aufgeloest(MODUL, PROJ, db_path=_leer)
    assert auf["text"] == "allgemein"


def test_laenge_wird_begrenzt(_leer):
    ph.setze(MODUL, PROJ, "A" * 5000, von="u", db_path=_leer)
    e = ph.hole(MODUL, PROJ, db_path=_leer)
    assert "gekürzt" in e["text"]
    assert e["text"].count("A") == ph.GRENZE


def test_projekte_trennen_sich(_leer):
    ph.setze(MODUL, PROJ, "A", von="u", db_path=_leer)
    ph.setze(MODUL, "anderes", "B", von="u", db_path=_leer)
    assert ph.hole(MODUL, PROJ, db_path=_leer)["text"] == "A"
    assert ph.hole(MODUL, "anderes", db_path=_leer)["text"] == "B"


def test_module_trennen_sich(_leer):
    ph.setze("cra", PROJ, "CRA", von="u", db_path=_leer)
    ph.setze("nis2", PROJ, "NIS2", von="u", db_path=_leer)
    assert ph.hole("cra", PROJ, db_path=_leer)["text"] == "CRA"
    assert ph.hole("nis2", PROJ, db_path=_leer)["text"] == "NIS2"


# ── Die Engine hängt gespeicherte Hinweise NICHT von selbst an ─────────────

def test_die_engine_nutzt_gespeicherte_hinweise_nicht_heimlich(monkeypatch, _leer):
    """Sonst steuerte ein fremder Text den Lauf, ohne dass ihn jemand sieht.

    Der gespeicherte Hinweis belegt das **Feld** vor; was gesendet wird, ist
    immer der Feldinhalt. Diese Grenze ist der Grund, warum die Funktion
    überhaupt vertretbar ist.
    """
    import ai_compliance_suite.ai.dispatch as d
    import server.services.prefill as prefill
    from flask import Flask

    from shared.ki_engine import OHNE_OBJEKT, KiAuftrag, ki_lauf

    ph.setze("cra", PROJ, "HEIMLICHER HINWEIS", von="u", db_path=_leer)
    monkeypatch.setattr(prefill, "is_ai_available", lambda: (True, ""))
    gesehen: dict = {}

    class _Resp:
        text = "ok"
        provider = "on_prem"

    monkeypatch.setattr(d, "generate_text",
                        lambda **kw: (gesehen.update(kw), _Resp())[1])
    monkeypatch.setattr(d, "current_provider_name", lambda: "on_prem")

    app = Flask(__name__)
    with app.test_request_context("/api/cra/x", method="POST", json={}):
        ki_lauf(KiAuftrag(prompt="Basis", herkunft=OHNE_OBJEKT,
                          modul="cra", projekt=PROJ))
    assert "HEIMLICHER HINWEIS" not in gesehen["prompt"]
    assert gesehen["prompt"] == "Basis"


# ── REST ────────────────────────────────────────────────────────────────────

def test_rest_setzen_lesen_loeschen(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ph, "DB_PATH", Path("data/db/prompt_hinweise_test.sqlite"))
    basis = f"/api/cra/projekte/{PROJ}/prompt-hinweise"

    r = client.put(basis, headers=auth_headers,
                   json={"text": "Schwerpunkt OT-Sicherheit."})
    assert r.status_code == 200
    assert "OT-Sicherheit" in r.get_json()["text"]

    r = client.get(basis, headers=auth_headers)
    assert r.status_code == 200
    d = r.get_json()
    assert "OT-Sicherheit" in d["text"]
    assert d["grenze"] == ph.GRENZE
    assert "" in d["bereiche"]

    r = client.delete(f"{basis}/alle", headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()["text"] == ""


def test_rest_weist_unbekannten_bereich_ab(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ph, "DB_PATH", Path("data/db/prompt_hinweise_test.sqlite"))
    r = client.get(f"/api/cra/projekte/{PROJ}/prompt-hinweise?bereich=erfunden",
                   headers=auth_headers)
    assert r.status_code == 400


def test_rest_ohne_anmeldung_abgewiesen(client):
    r = client.get(f"/api/cra/projekte/{PROJ}/prompt-hinweise")
    assert r.status_code in (401, 422)


# ── Verdrahtung in allen sieben Modulen ────────────────────────────────────

MODULE = ["cra", "nis2", "aiact", "dsgvo", "wiba", "risikobewertung",
          "compliance-audit"]


@pytest.mark.parametrize("modul", MODULE)
def test_jedes_modul_hat_die_route(app, modul: str):
    """Fehlt sie in einem Modul, merkt dort niemand etwas — es fehlt nur."""
    pfade = {str(r) for r in app.url_map.iter_rules()}
    erwartet = f"/api/{modul}/projekte/<projekt_name>/prompt-hinweise"
    assert erwartet in pfade, f"{modul}: {erwartet} fehlt"


def test_der_pfad_parameter_heisst_projekt_name(app):
    """Die Firmen-ACL löst die Firma über `view_args['projekt_name']` auf.

    Hieße der Parameter anders, griffe das Objekt-RBAC aus #1185 nicht — die
    Lehre aus #1765, dort wörtlich dokumentiert.
    """
    for r in app.url_map.iter_rules():
        if "prompt-hinweise" in str(r):
            assert "<projekt_name>" in str(r), str(r)


# ── Oberfläche ──────────────────────────────────────────────────────────────

def test_das_feld_zeigt_die_herkunft_der_vorbelegung():
    """Ein fremder Text darf nicht wie der eigene aussehen."""
    text = (SRC / "components/shared/PromptZusatzFeld.vue").read_text(encoding="utf-8")
    assert "Vorbelegt aus den Projekt-Hinweisen" in text
    assert "gesetzt von" in text
    assert "überschreibbar" in text


def test_das_feld_kann_merken_und_vergessen():
    text = (SRC / "components/shared/PromptZusatzFeld.vue").read_text(encoding="utf-8")
    assert "Für dieses Projekt merken" in text
    assert "Nicht mehr merken" in text


def test_die_massen_adapter_tragen_das_modul():
    """Aus einer URL zu raten wäre eine zweite Wahrheit (`cra-konformitaet`)."""
    text = (SRC / "utils/massAdapters.ts").read_text(encoding="utf-8")
    assert text.count("modul:") >= 5  # Interface + vier Adapter
