"""VVT: vollständige Kataloge, Verweise auf die eigenen Register, DSFA rechnen (#1890).

**Korrektur am Issue-Text:** Dort stand, die Rechtsgrundlagen seien Freitext.
Das war zu scharf — ``DSGVOPflichtDokuPanel.vue`` zeigte für Art. 6 Abs. 1 und
Art. 9 Abs. 2 längst Auswahlfelder. Was bleibt, ist in den Tests unten:

1. Die Auswahl für **Art. 9 Abs. 2 war unvollständig** — d, e und f fehlten.
   Eine unvollständige Positivliste ist schlimmer als ein Freitextfeld: Sie
   sieht abschließend aus, und der Anwender wählt eine falsche Grundlage.
2. Die Listen standen **im Frontend** — eine Spiegel-Liste (#1731/#1735).
3. ``tom_ref`` und ``loeschfrist_ref`` sind wirklich Freitext, obwohl die
   Suite beide Register führt.
4. ``dsfa_trigger`` ist ein Häkchen, obwohl Art. 35 Abs. 3 die Fälle nennt.
"""
from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

from dsgvo import vvt_katalog as vk
from shared import formular_pruefung as fp

FRONTEND = Path(__file__).resolve().parents[1] / "frontend/src"


def _ohne_kommentare(text: str) -> str:
    raus: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        raus.append(tok.string)
    return " ".join(raus)


# ── Die Kataloge sind vollständig ───────────────────────────────────────────

def test_art6_hat_sechs_buchstaben():
    assert [e["lit"] for e in vk.ART6] == list("abcdef")


def test_art9_hat_zehn_buchstaben():
    """**Der Fund:** d, e und f fehlten in der Maske. Eine Verarbeitung auf
    Grundlage von Art. 9 Abs. 2 lit. e (vom Betroffenen offensichtlich
    öffentlich gemacht) ließ sich nicht erfassen."""
    assert [e["lit"] for e in vk.ART9] == list("abcdefghij")


@pytest.mark.parametrize("lit", ["d", "e", "f"])
def test_die_fehlenden_buchstaben_sind_benannt(lit):
    eintrag = next(e for e in vk.ART9 if e["lit"] == lit)
    assert eintrag["label"] and eintrag["wert"] == f"Art. 9(2)({lit})"


def test_der_angezeigte_wert_bleibt_die_gewohnte_schreibweise():
    """Bestandsdaten sollen lesbar bleiben — die Linie aus #1713: Bestand
    nicht anfassen, wenn es nicht nötig ist."""
    assert all(e["wert"].startswith("Art. 6(1)(") for e in vk.ART6)
    assert all(e["wert"].startswith("Art. 9(2)(") for e in vk.ART9)


def test_der_katalog_kommt_vom_server():
    """Die Listen standen im Frontend — gepflegt wird eine, und Berichte,
    Prüfungen und Masken lesen verschiedene Stände (#1731/#1735)."""
    panel = (FRONTEND / "views/dsgvo/DSGVOPflichtDokuPanel.vue").read_text(
        encoding="utf-8")
    assert 'v-for="e in art6"' in panel and 'v-for="e in art9"' in panel
    # Die hartcodierten Optionen sind weg.
    assert 'value="Art. 6(1)(a)"' not in panel
    assert 'value="Art. 9(2)(a)"' not in panel


def test_die_maske_holt_den_katalog():
    panel = (FRONTEND / "views/dsgvo/DSGVOPflichtDokuPanel.vue").read_text(
        encoding="utf-8")
    assert "ladeVvtKataloge" in panel
    assert "vvt/kataloge" in panel


# ── Verweise zeigen auf die eigenen Register ────────────────────────────────

def test_ein_verweis_ins_leere_wird_benannt():
    optionen = {"tom": [{"wert": "TOM-001", "label": "Verschlüsselung"}],
                "loeschkonzept": []}
    befunde = vk.verweis_befunde({"tom_ref": "TOM-001, TOM-999"}, optionen)
    assert [b["id"] for b in befunde] == ["verweis_unbekannt"]
    assert "TOM-999" in befunde[0]["text"]
    assert befunde[0]["wirkung"] == fp.WIRKUNG_HINWEIS


def test_bei_leerem_register_wird_nicht_geprueft():
    """Sonst wäre jeder Verweis „verwaist", und ein Prüfer, der immer
    anschlägt, wird abgeschaltet (#1774/#1877)."""
    assert vk.verweis_befunde({"tom_ref": "TOM-001"},
                              {"tom": [], "loeschkonzept": []}) == []


def test_mehrere_verweise_werden_einzeln_geprueft():
    optionen = {"tom": [{"wert": "TOM-001"}, {"wert": "TOM-002"}],
                "loeschkonzept": [{"wert": "LR-07"}]}
    assert vk.verweis_befunde({"tom_ref": "TOM-001; TOM-002",
                               "loeschfrist_ref": "LR-07"}, optionen) == []


def test_die_maske_bietet_die_register_zur_auswahl():
    panel = (FRONTEND / "views/dsgvo/DSGVOPflichtDokuPanel.vue").read_text(
        encoding="utf-8")
    assert 'list="vvt-tom-refs"' in panel
    assert 'list="vvt-loesch-refs"' in panel


def test_freitext_bleibt_moeglich():
    """Bestandsdaten und Verweise auf Dokumentabschnitte („LK-2024 §3.2")
    müssen weiter eingebbar sein — eine Auswahl, die den Bestand ausschließt,
    erzwingt Datenverlust."""
    panel = (FRONTEND / "views/dsgvo/DSGVOPflichtDokuPanel.vue").read_text(
        encoding="utf-8")
    assert 'v-model="vvtWizard.data.tom_ref"' in panel
    assert "<datalist" in panel      # datalist = Vorschlag, kein select


# ── Art. 35 Abs. 3 — gerechnet, aber ein Hinweis ───────────────────────────

def test_profiling_deutet_auf_lit_a():
    b = vk.dsfa_befund({"zweck": "Bonitäts-Scoring der Kunden"})
    assert "a" in b["faelle"] and b["indiz"]


def test_besondere_kategorien_deuten_auf_lit_b():
    b = vk.dsfa_befund({"art9_grundlage": "Art. 9(2)(h)"})
    assert "b" in b["faelle"]


def test_ueberwachung_deutet_auf_lit_c():
    b = vk.dsfa_befund({"zweck": "Videoüberwachung des Eingangsbereichs"})
    assert "c" in b["faelle"]


def test_ohne_anhaltspunkt_kein_indiz():
    assert vk.dsfa_befund({"zweck": "Rechnungsstellung"})["indiz"] is False


def test_der_widerspruch_ist_ein_hinweis():
    """Art. 35 Abs. 3 nennt Regelbeispiele („insbesondere"); beurteilt wird
    von der oder dem Datenschutzbeauftragten."""
    b = vk.dsfa_befund({"zweck": "Scoring", "dsfa_trigger": 0})
    assert b["widerspruch"]
    assert b["widerspruch"][0]["wirkung"] == fp.WIRKUNG_HINWEIS


def test_gesetzter_haken_ohne_indiz_ist_kein_widerspruch():
    """Wer eine DSFA durchführt, obwohl kein Regelbeispiel greift, tut nichts
    Falsches. Das zu beanstanden hieße, von einer DSFA abzuraten."""
    b = vk.dsfa_befund({"zweck": "Rechnungsstellung", "dsfa_trigger": 1})
    assert b["widerspruch"] == []


def test_der_vorschlag_setzt_nur():
    assert vk.dsfa_befund({"zweck": "Scoring"})["vorschlag"] == {"dsfa_trigger": 1}
    assert vk.dsfa_befund({"zweck": "Rechnungsstellung"})["vorschlag"] == {}


def test_jeder_grund_nennt_die_fundstelle():
    b = vk.dsfa_befund({"zweck": "Scoring von Profilen",
                        "art9_grundlage": "Art. 9(2)(h)"})
    assert all("Art. 35 Abs. 3 lit." in g for g in b["gruende"])


def test_die_schwelle_ist_unsere_und_steht_an_einer_stelle():
    """Die Verordnung nennt keine Zahl. Eine Zahl braucht es trotzdem, sonst
    ist der Punkt nicht rechenbar — und weil sie von uns stammt, wirkt sie nur
    als Hinweis (wie die 18 Monate in #1824)."""
    assert vk.UMFANGREICH_AB > 0
    assert vk.katalog()["umfangreich_ab"] == vk.UMFANGREICH_AB
    # Geprüft wird der **Skriptteil**: Im Stylesheet steht `font-weight: 500`,
    # und ein Wächter, der darauf anschlägt, prüft die Darstellung statt das
    # Programm (die Lehre aus #1834/#1867, hier zum dritten Mal).
    panel = (FRONTEND / "views/dsgvo/DSGVOPflichtDokuPanel.vue").read_text(
        encoding="utf-8")
    skript = panel.split("<script setup", 1)[1].split("</script>", 1)[0]
    assert str(vk.UMFANGREICH_AB) not in skript


# ── Dieses Modul rechnet, es schreibt nicht ─────────────────────────────────

def test_der_katalog_schreibt_nichts():
    programm = _ohne_kommentare(
        Path("dsgvo/vvt_katalog.py").read_text(encoding="utf-8"))
    for verboten in ("UPDATE", "INSERT", "save_vvt", "upsert"):
        assert verboten not in programm


def test_die_anreicherung_laeuft_neben_den_anderen():
    """Dieselbe Bauform wie ``datenpannen_frist.enrich_panne`` und
    ``meldepflicht.enrich_panne``."""
    d = vk.enrich_vvt({"zweck": "Scoring"},
                      {"tom": [{"wert": "TOM-001"}], "loeschkonzept": []})
    assert "dsfa" in d and "befunde" in d


def test_der_endpunkt_reicht_die_hinweise_durch():
    api = (Path(__file__).resolve().parents[1]
           / "server/api/dsgvo.py").read_text(encoding="utf-8")
    assert "vk.enrich_vvt" in api
    assert "vvt/kataloge" in api


def test_referenz_optionen_laufen_ohne_register():
    """Ein leeres oder nicht angelegtes Register darf die VVT-Maske nicht
    lahmlegen — dann bleibt das Feld Freitext wie bisher."""
    o = vk.referenz_optionen(Path("data/db/dsgvo.sqlite"),
                             "pytest-gibt-es-nicht-1890")
    assert isinstance(o.get("tom"), list)
    assert isinstance(o.get("loeschkonzept"), list)
