"""Die Meldestelle: eintragbar, verlustfrei, lesbar gedruckt (#1796).

Der Prüfpunkt ``vuln_handling`` verlangte einen PSIRT-Kontakt und las dafür
ein Feld, das die Oberfläche nicht anbot. Drei Fehler an einer Angabe:

1. **Nicht eintragbar** — die C2-Maske kannte ``psirt_contacts`` nicht, das
   Autodetect schrieb die Adresse nur in den Intake-Kanal. Der Punkt war durch
   Bedienung nicht erfüllbar.
2. **Beim Speichern verloren** — ``save_psirt`` setzte jedes Feld auf
   ``data.get(k, '')``; ein Teil-Update löschte, was es nicht mitbrachte.
3. **Als Python-Text gedruckt** — ``_s(<list>)`` ergab ``['security@…']`` in
   der Kundenfassung, also im Dokument, das das Haus verlässt.

Die Tests hier prüfen jeden der drei Fehler an seiner Ursache, nicht am
Gesamtbild: Ein Test, der nur „der Punkt ist grün" sagt, bliebe grün, wenn der
Kontakt beim nächsten Speichern wieder verschwindet.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cra import db as cdb
from cra import psirt as cpsirt

CRA_DB = Path("data/db/cra.sqlite")
PROJ = "pytest-psirt-1796"


@pytest.fixture
def projekt():
    cdb.ensure_db(CRA_DB)
    cdb.delete_projekt(CRA_DB, PROJ)
    cdb.save_projekt(CRA_DB, PROJ, unternehmen="pytest-firma-1796", produkt="Testprodukt")
    yield PROJ
    cdb.delete_projekt(CRA_DB, PROJ)


# ── Eine Lesart für ein Feld, das beides trägt ───────────────────────────────

@pytest.mark.parametrize(("eingabe", "erwartet"), [
    (None, []),
    ("", []),
    ("security@example.test", ["security@example.test"]),
    (["a@example.test", "b@example.test"], ["a@example.test", "b@example.test"]),
    ("a@example.test, b@example.test", ["a@example.test", "b@example.test"]),
    ("a@example.test; b@example.test", ["a@example.test", "b@example.test"]),
    ("a@example.test\nb@example.test", ["a@example.test", "b@example.test"]),
    # Dubletten sind dieselbe Stelle, auch in anderer Schreibweise
    (["A@example.test", "a@example.test"], ["A@example.test"]),
    # Reihenfolge ist die Entscheidung des Pflegenden, nicht alphabetisch
    (["z@example.test", "a@example.test"], ["z@example.test", "a@example.test"]),
])
def test_normalisiere_liest_jede_altform(eingabe, erwartet):
    assert cpsirt.normalisiere(eingabe) == erwartet


def test_intake_kanal_zaehlt_als_kontakt():
    """Fachlich dieselbe Angabe — wohin melden Dritte eine Schwachstelle?"""
    assert cpsirt.kontakte({"intake_kanal": "security@example.test"}) == \
        ["security@example.test"]


def test_expliziter_kontakt_steht_vor_dem_intake_kanal():
    k = cpsirt.kontakte({"psirt_contacts": ["psirt@example.test"],
                         "intake_kanal": "security@example.test"})
    assert k == ["psirt@example.test", "security@example.test"]


def test_dieselbe_adresse_wird_nicht_doppelt_gezaehlt():
    """Sonst meldete die Akte zwei Meldestellen, wo eine ist."""
    k = cpsirt.kontakte({"psirt_contacts": ["security@example.test"],
                         "intake_kanal": "Security@example.test"})
    assert k == ["security@example.test"]


# ── Speichern darf nichts verlieren ──────────────────────────────────────────

def test_teil_update_erhaelt_den_kontakt(projekt):
    """Der eigentliche Defekt: Das C2-Formular kennt das Feld nicht, und sein
    Speichern löschte den Kontakt — ohne Meldung."""
    cdb.save_psirt(CRA_DB, projekt, {"psirt_contacts": ["psirt@example.test"],
                                     "intake_kanal": "security@example.test"})
    # So schickt die Maske: alle sichtbaren Felder, ohne `psirt_contacts`.
    cdb.save_psirt(CRA_DB, projekt, {"intake_kanal": "security@example.test",
                                     "triage_sla": "24h", "fix_sla_critical": "7 Tage",
                                     "fix_sla_high": "", "fix_sla_medium": "",
                                     "disclosure_policy_url": "",
                                     "security_md_url": "", "notizen": ""})
    p = cdb.load_psirt(CRA_DB, projekt) or {}
    assert p["psirt_contacts"] == ["psirt@example.test"]
    assert p["triage_sla"] == "24h"


def test_leeren_bleibt_moeglich(projekt):
    """Erhalten heißt nicht festschreiben: Wer das Feld ausdrücklich leer
    schickt, löscht es — sonst wäre ein Fehleintrag nicht korrigierbar."""
    cdb.save_psirt(CRA_DB, projekt, {"psirt_contacts": ["psirt@example.test"]})
    cdb.save_psirt(CRA_DB, projekt, {"psirt_contacts": []})
    assert (cdb.load_psirt(CRA_DB, projekt) or {})["psirt_contacts"] == []


def test_load_liefert_immer_eine_liste(projekt):
    """Bestandszeilen tragen einen einzelnen String (so steht es seit #1758 im
    Kundenfassungs-Test). Aufrufer dürfen sich auf eine Liste verlassen."""
    cdb.save_psirt(CRA_DB, projekt, {"psirt_contacts": "security@example.test"})
    p = cdb.load_psirt(CRA_DB, projekt) or {}
    assert p["psirt_contacts"] == ["security@example.test"]


# ── Der Prüfpunkt liest nicht an der Akte vorbei ─────────────────────────────

def _gate(projekt: str, version: str = "1.0.0"):
    from cra.konformitaet_gate import evaluate
    return evaluate(projekt, version=version)


def test_prueffpunkt_ist_mit_dem_intake_kanal_erfuellbar(projekt):
    """Vorher unerfüllbar: Das verlangte Feld hatte keine Eingabestelle."""
    cdb.save_psirt(CRA_DB, projekt, {"intake_kanal": "security@example.test",
                                     "disclosure_policy_url": "https://example.test/sec"})
    gate = _gate(projekt)
    offen = [p for p in gate["release_punkte"] if p["typ"] == "vuln_handling"]
    assert offen == [], f"Punkt trotz hinterlegter Meldestelle offen: {offen}"
    assert gate["release_befunde"]["vuln_handling"]["psirt_kontakte"] == 1


def test_ohne_jede_meldestelle_bleibt_der_punkt_offen(projekt):
    """Die Gegenprobe — sonst wäre der Punkt jetzt immer grün."""
    cdb.save_psirt(CRA_DB, projekt, {"disclosure_policy_url": "https://example.test/sec"})
    offen = [p for p in _gate(projekt)["release_punkte"] if p["typ"] == "vuln_handling"]
    assert len(offen) == 1
    assert "PSIRT-Kontakt" in offen[0]["hinweis"]


# ── Gedruckt wird eine Zeile, keine Python-Liste ─────────────────────────────

def test_kundenfassung_druckt_mehrere_kontakte_lesbar(projekt):
    """Das Dokument verlässt das Haus — hier stand `['security@…']`."""
    from cra import kundenfassung

    cdb.save_support_period(CRA_DB, projekt, {"markteintritt_datum": date.today().isoformat(),
                                              "support_jahre": 5,
                                              "update_kanal": "https://example.test/updates"})
    cdb.save_psirt(CRA_DB, projekt, {"psirt_contacts": ["a@example.test", "b@example.test"],
                                     "disclosure_policy_url": "https://example.test/sec"})
    d = kundenfassung.sammle(projekt, db_path=CRA_DB)
    assert d["meldestelle"]["kontakt"] == "a@example.test, b@example.test"
    assert "[" not in d["meldestelle"]["kontakt"]


# ── Autodetect trägt die gefundene Adresse auch als Kontakt ein ──────────────

def test_autodetect_fuehrt_die_adresse_als_kontakt(monkeypatch):
    """Sie stand nur im Intake-Kanal — die Akte wies den Kontakt damit nicht
    aus, obwohl er bekannt war."""
    from cra import pflicht_doku_autodetect as auto

    monkeypatch.setattr(auto, "_fetch_file_content",
                        lambda o, r, p: ("# Security\nMelden an security@example.test"
                                         if p == "SECURITY.md" else None))
    found = auto.detect_psirt("owner", "repo")
    assert found["intake_kanal"] == "security@example.test"
    assert found["psirt_contacts"] == ["security@example.test"]
