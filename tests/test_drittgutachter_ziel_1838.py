"""Die Drittgutachter-Antwort gehört nicht in die Beurteilung (#1838).

Gefunden beim Firefox-Durchlauf zu #1836. Zwei Knöpfe öffneten dasselbe
Wizard-Modal, und der gemeinsame Übernahme-Handler kannte den Unterschied
nicht: Die **Reproduktionsanleitung für den Drittgutachter** (DIN EN 16775)
wurde durch ``beurteilungParse`` geschickt und landete als **Beurteilung** im
Editor. Es schlug nichts fehl — ein Text stand an der falschen Stelle und sah
aus wie ein Ergebnis.

Dazu kam, dass der **richtige** Empfänger seit immer ohne Aufrufer war:
``gutachten.ideen.selbst_audit`` bewertet die Anleitung gegen DIN EN 16775,
und die Oberfläche rief ihn nie. Die Funktion war da, der Weg zu ihr nicht.

In einem Modul, dessen Erzeugnis vor Gericht geht (§ 407a ZPO), ist ein Feld
mit fremdem Inhalt schlimmer als ein leeres.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
VIEW = WURZEL / "frontend/src/views/gutachten/GerichtsgutachtenView.vue"

ANLEITUNG = {
    "schritte": ["Schritt 1: Asservat verifizieren", "Schritt 2: Hash bilden"],
    "voraussetzungen": ["sha256sum", "Zugriff auf Asservat"],
    "erwartetes_ergebnis": "Hash stimmt mit der Akte überein",
    "potenzielle_abweichungen": ["anderes Werkzeug"],
    "reproduzierbarkeits_bewertung": "hoch",
}


@pytest.fixture(autouse=True)
def _volle_lizenz():
    from server import license_state
    cur = license_state._current
    vorher = (cur.state, list(cur.modules))
    # `gutachten` gehört zu EXPLICIT_MODULES — auch `*` schließt es nicht ein.
    cur.state, cur.modules = "ok", ["gutachten"]
    yield
    cur.state, cur.modules = vorher[0], vorher[1]


# ── Der Endpunkt nimmt die rohe Antwort an ──────────────────────────────────

def test_rohe_ki_antwort_wird_geprueft(client, auth_headers):
    """Geparst wird serverseitig — der kanonische Parser kennt Codefences."""
    roh = "Hier die Anleitung:\n```json\n" + json.dumps(ANLEITUNG) + "\n```\n"
    r = client.post("/api/gutachten/gerichts/drittgutachter/audit",
                    headers=auth_headers, json={"response": roh})
    assert r.status_code == 200
    d = r.get_json()
    assert d["drittgutachter_tauglich"] is True
    assert d["score"] == d["max_score"] == 4
    # Die Anleitung kommt mit, damit die Oberfläche die Schritte zeigen kann,
    # ohne sie selbst aus der Antwort zu schneiden.
    assert d["anleitung"]["schritte"][0].startswith("Schritt 1")


def test_unvollstaendige_anleitung_ist_nicht_tauglich(client, auth_headers):
    unvollstaendig = {"schritte": ["nur ein Schritt"]}
    r = client.post("/api/gutachten/gerichts/drittgutachter/audit",
                    headers=auth_headers, json={"response": json.dumps(unvollstaendig)})
    d = r.get_json()
    assert d["drittgutachter_tauglich"] is False
    assert d["checks"]["schritte_vorhanden"] is True
    assert d["checks"]["ergebnis_definiert"] is False


def test_unlesbare_antwort_wird_abgewiesen(client, auth_headers):
    """Kein stilles „0 von 4 Kriterien" für eine Antwort, die niemand las."""
    r = client.post("/api/gutachten/gerichts/drittgutachter/audit",
                    headers=auth_headers, json={"response": "völliger Unsinn"})
    assert r.status_code == 400
    assert "nicht lesbar" in r.get_json()["error"]


def test_bestandsweg_mit_fertigem_objekt_bleibt(client, auth_headers):
    """Der Endpunkt nahm bisher das Objekt direkt — das muss weiter gehen."""
    r = client.post("/api/gutachten/gerichts/drittgutachter/audit",
                    headers=auth_headers, json=ANLEITUNG)
    assert r.status_code == 200
    assert r.get_json()["drittgutachter_tauglich"] is True


# ── Die Oberfläche unterscheidet die beiden Zwecke ──────────────────────────

def _script_ohne_kommentare() -> str:
    """Nur der Code, ohne Kommentare.

    Zweimal in dieser Sitzung ist ein Wächter grün geblieben, weil er das
    gesuchte Wort im Kommentar darüber fand (#1833, #1834). Deshalb hier
    ausdrücklich: geprüft wird das Programm, nicht die Erzählung.
    """
    text = VIEW.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)       # Blockkommentare
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)      # HTML-Kommentare
    zeilen = [z for z in text.split("\n") if not z.lstrip().startswith("//")]
    return "\n".join(zeilen)


def test_das_modal_traegt_einen_zweck():
    code = _script_ohne_kommentare()
    assert "zweck: 'drittgutachter'" in code
    assert "zweck: 'beurteilung'" in code


def test_der_uebernahme_handler_verzweigt():
    """Ein Handler für zwei Zwecke muss sie unterscheiden."""
    code = _script_ohne_kommentare()
    handler = code.split("const onApplyWizard")[1].split("\n}")[0]
    assert "zweck" in handler, "onApplyWizard unterscheidet die Zwecke nicht"
    assert "drittgutachterAudit" in handler
    assert "beurteilungParse" in handler
    # Die Reihenfolge zählt: Der Drittgutachter-Fall muss VOR dem
    # Beurteilungs-Fall abgehandelt und verlassen werden, sonst läuft die
    # Anleitung wieder durch beide.
    assert handler.index("drittgutachterAudit") < handler.index("beurteilungParse")


def test_das_ergebnis_hat_eine_anzeige():
    """Vorher gab es für die Antwort keine Stelle in der Oberfläche."""
    code = _script_ohne_kommentare()
    assert "drittResult" in code
    assert "drittgutachter_tauglich" in code


def test_der_zielhinweis_unterscheidet_die_zwecke():
    """„Übernimmt die Felder der Beurteilung" galt vorher für beide Wege."""
    code = _script_ohne_kommentare()
    assert "DIN EN 16775" in code
    hinweise = code.count("OutputDestinationHint")
    assert hinweise >= 2, "Es braucht je Zweck einen eigenen Ziel-Hinweis"
