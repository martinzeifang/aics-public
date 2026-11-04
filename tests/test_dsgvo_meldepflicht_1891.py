"""Die Meldepflicht nach Art. 33/34 rechnen statt ankreuzen (#1891).

**Der Befund:** ``meldung_aufsicht_pflicht`` und ``meldung_betroffene_pflicht``
sind ``INTEGER NOT NULL DEFAULT 0`` und kamen **aus dem Browser** —
nachgeprüft: Keine Stelle im Produktionscode leitete sie ab. Daneben steht
``risikoeinschaetzung``, und die Verordnung nennt die Bedingung ausdrücklich.

Die Tests halten vor allem die **Richtung** fest: fail-safe, nicht
fail-closed. Eine Anwendung, die eine Meldepflicht wegrechnet, nimmt dem
Verantwortlichen eine Entscheidung, deren Folgen er trägt.
"""
from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

from dsgvo import meldepflicht as mp
from shared import formular_pruefung as fp

FRONTEND = Path(__file__).resolve().parents[1] / "frontend/src"


def _ohne_kommentare(text: str) -> str:
    raus: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        raus.append(tok.string)
    return " ".join(raus)


# ── Art. 33 Abs. 1 ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("stufe,erwartet", [
    ("hoch", True), ("mittel", True), ("gering", False),
])
def test_die_aufsichtsmeldung_folgt_der_einschaetzung(stufe, erwartet):
    b = mp.befund({"risikoeinschaetzung": stufe})
    assert b["aufsicht"]["pflicht"] is erwartet


def test_der_grund_nennt_die_fundstelle():
    """Er steht in der Oberfläche — eine Pflicht ohne Fundstelle ist eine
    Behauptung."""
    b = mp.befund({"risikoeinschaetzung": "hoch"})
    assert "Art. 33 Abs. 1" in b["aufsicht"]["rechtsgrundlage"]
    assert "Art. 34 Abs. 1" in b["betroffene"]["rechtsgrundlage"]
    assert b["aufsicht"]["grund"]


# ── Art. 34 Abs. 1 ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("stufe,erwartet", [
    ("hoch", True), ("mittel", False), ("gering", False),
])
def test_die_betroffenenbenachrichtigung_verlangt_hohes_risiko(stufe, erwartet):
    assert mp.befund({"risikoeinschaetzung": stufe})["betroffene"]["pflicht"] is erwartet


# ── Besondere Kategorien heben an, nie ab ───────────────────────────────────

def test_art9_hinweise_heben_die_einschaetzung_an():
    b = mp.befund({"risikoeinschaetzung": "gering",
                   "datenkategorien": "Gesundheitsdaten der Patienten"})
    assert b["stufe"] == "mittel"
    assert b["aufsicht"]["pflicht"] is True
    assert b["art9_treffer"]
    assert b["angehoben"]


def test_art9_hinweise_senken_nie():
    """Aus einer Wortliste auf „hohes Risiko" zu schließen wäre eine
    Rechtsanwendung, die diese Anwendung nicht leisten kann."""
    b = mp.befund({"risikoeinschaetzung": "hoch", "datenkategorien": "Namen"})
    assert b["stufe"] == "hoch"
    assert b["betroffene"]["pflicht"] is True


def test_ohne_einschaetzung_gilt_gering():
    """Der Spaltendefault. Er bleibt eine **Einschätzung** und wird als solche
    begründet — nicht als Rechenergebnis ausgegeben."""
    b = mp.befund({})
    assert b["stufe"] == "gering"
    assert "Einschätzung des Verantwortlichen" in b["aufsicht"]["grund"]


# ── Widersprüche: ausweisen, nicht überschreiben ────────────────────────────

def test_die_abweichung_wird_ausgewiesen():
    b = mp.befund({"risikoeinschaetzung": "hoch",
                   "meldung_aufsicht_pflicht": 0,
                   "meldung_betroffene_pflicht": 0})
    ids = {w["id"] for w in b["widersprueche"]}
    assert ids == {"aufsicht_nicht_vermerkt", "betroffene_nicht_vermerkt"}
    assert all(w["wirkung"] == fp.WIRKUNG_HINWEIS for w in b["widersprueche"])


def test_die_gegenrichtung_ist_kein_widerspruch():
    """Wer meldet, obwohl er nicht müsste, tut nichts Falsches. Das zu
    beanstanden hieße, von einer Meldung abzuraten."""
    b = mp.befund({"risikoeinschaetzung": "gering",
                   "meldung_aufsicht_pflicht": 1,
                   "meldung_aufsicht_datum": "2026-10-30"})
    assert b["widersprueche"] == []


def test_eine_pflicht_ohne_datum_ist_eine_luecke():
    b = mp.befund({"risikoeinschaetzung": "hoch",
                   "meldung_aufsicht_pflicht": 1,
                   "meldung_betroffene_pflicht": 1})
    ids = {w["id"] for w in b["widersprueche"]}
    assert ids == {"aufsicht_ohne_datum", "betroffene_ohne_datum"}


def test_der_vorschlag_setzt_nur_und_nimmt_nie_zurueck():
    """Nur leere Felder füllen (#1769/#1773) — und ein Häkchen wegzunehmen
    wäre ein Rat, nicht zu melden."""
    assert mp.befund({"risikoeinschaetzung": "hoch"})["vorschlag"] == {
        "meldung_aufsicht_pflicht": True, "meldung_betroffene_pflicht": True}
    assert mp.befund({"risikoeinschaetzung": "gering"})["vorschlag"] == {
        "meldung_aufsicht_pflicht": False, "meldung_betroffene_pflicht": False}


def test_das_haekchen_wird_nicht_geschrieben():
    """Wächter: Dieses Modul **rechnet**. Würde es schreiben, wäre die
    Entscheidung des Verantwortlichen weg."""
    programm = _ohne_kommentare(
        Path("dsgvo/meldepflicht.py").read_text(encoding="utf-8"))
    for verboten in ("UPDATE", "INSERT", "save_panne", "con.execute"):
        assert verboten not in programm


# ── Die Frist bleibt, wo sie ist ────────────────────────────────────────────

def test_die_72h_frist_wird_nicht_nachgebaut():
    """Sie läuft über ``shared/deadlines`` (STAGE_SET ``dsgvo_art33``, #1193).
    Zwei Rechenwege wären zwei Wahrheiten (#1726/#1727)."""
    programm = _ohne_kommentare(
        Path("dsgvo/meldepflicht.py").read_text(encoding="utf-8"))
    assert "72" not in programm
    assert "deadlines" not in programm


def test_beide_anreicherungen_laufen_nebeneinander():
    """Dieselbe Bauform wie ``datenpannen_frist.enrich_panne`` — damit sie
    sich nicht kennen müssen."""
    from dsgvo import datenpannen_frist as pf

    panne = {"festgestellt_am": "2026-10-28T08:00:00", "status": "offen",
             "risikoeinschaetzung": "hoch"}
    d = mp.enrich_panne(pf.enrich_panne(panne))
    assert "frist" in d and "meldepflicht" in d


# ── Nur offene Vorgänge in der Übersicht ────────────────────────────────────

def test_abgeschlossene_pannen_erscheinen_nicht():
    """Eine Liste, die bei jeder Panne anschlägt, wird abgeschaltet
    (#1774/#1877)."""
    pannen = [
        {"panne_id": "P-1", "risikoeinschaetzung": "hoch", "status": "offen"},
        {"panne_id": "P-2", "risikoeinschaetzung": "hoch", "status": "gemeldet"},
        {"panne_id": "P-3", "risikoeinschaetzung": "hoch",
         "status": "abgeschlossen"},
    ]
    ids = {w["panne_id"] for w in mp.offene_widersprueche(pannen)}
    assert ids == {"P-1"}


# ── Oberfläche ──────────────────────────────────────────────────────────────

def test_die_maske_zeigt_den_gerechneten_stand():
    panel = (FRONTEND / "views/dsgvo/DatenpannenPanel.vue").read_text(
        encoding="utf-8")
    assert "gerechnet" in panel
    assert "pflichtUebernehmen" in panel


def test_die_maske_rechnet_nicht_selbst():
    """Die Regeln im Frontend nachzubauen ist die Lehre aus #1703/S9 — und an
    ihnen hängt eine Rechtspflicht.

    Geprüft wird der **Skriptteil**: ``value="hoch"`` im Template ist die
    Auswahl der Einschätzung und keine Entscheidung über die Meldepflicht. Ein
    Wächter, der darauf anschlägt, prüft die Maske statt das Programm (die
    Lehre aus #1834/#1867).
    """
    panel = (FRONTEND / "views/dsgvo/DatenpannenPanel.vue").read_text(
        encoding="utf-8")
    skript = panel.split("<script setup", 1)[1].split("</script>", 1)[0]
    for verboten in ("=== 'hoch'", '=== "hoch"', "includes('hoch')",
                     "risikoeinschaetzung ==="):
        assert verboten not in skript, (
            "die Maske entscheidet die Meldepflicht selbst")


def test_die_uebernahme_nimmt_kein_haekchen_zurueck():
    panel = (FRONTEND / "views/dsgvo/DatenpannenPanel.vue").read_text(
        encoding="utf-8")
    block = panel.split("function pflichtUebernehmen", 1)[1][:600]
    assert "= false" not in block


def test_der_endpunkt_liefert_den_stand_mit():
    api = (Path(__file__).resolve().parents[1]
           / "server/api/dsgvo_datenpannen.py").read_text(encoding="utf-8")
    assert "mp.enrich_panne" in api
    assert "meldepflicht" in api
