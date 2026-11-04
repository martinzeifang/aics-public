"""Der Mechanismus „aus den Quellen füllen" liegt in ``shared`` (#1893).

#1884–#1887 haben ihn für die CRA-Konformitätserklärung gebaut. Dasselbe
braucht die AI-Act-Erklärung (#1889), das DSGVO-VVT (#1890) und die
Datenpanne (#1891). Je Modul nachgebaut wären das vier Kopien — und beim
fünften fehlt eine, ohne dass etwas fehlschlägt (#1731/#1735).

Besonders teuer wäre das bei **einer** Regel: „Die KI darf gerechnete Felder
nicht setzen." In vier Fassungen existiert sie irgendwann in dreien.

Die Wächter unten lassen rot werden, wer ein eigenes Platzhaltermuster, einen
eigenen Versions-Regex oder eine eigene Füll-Mechanik mitbringt. Die
**Feldlisten** bleiben modul-eigen — Anhang V der CRA und Anhang V der KI-VO
sind verschiedene Kataloge, und sie zusammenzuführen wäre der umgekehrte
Fehler.
"""
from __future__ import annotations

import inspect
import io
import tokenize
from pathlib import Path

import pytest

from shared import formular_pruefung as fp
from shared import formular_vorschlag as fv

REPO = Path(__file__).resolve().parents[1]

#: Module, die Formulare dieser Art führen.
FACHMODULE: tuple[str, ...] = (
    "cra/doc_vorschlag.py",
    "cra/doc_pruefung.py",
    # #1889 — AI-Act-Konformitätserklärung (Art. 47/Anhang V der KI-VO)
    "ai_act/doc_vorschlag.py",
    "ai_act/doc_pruefung.py",
    # #1890/#1891 — DSGVO
    "dsgvo/vvt_katalog.py",
    "dsgvo/meldepflicht.py",
)


def _ohne_kommentare(text: str) -> str:
    """Kommentare und Zeichenketten weg — das Programm prüfen, nicht die
    Erzählung (#1834/#1867/#1878).

    Ohne das würde dieser Wächter auf die Docstrings anschlagen, die die
    entfernten Muster zitieren.
    """
    raus: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        raus.append(tok.string)
    return " ".join(raus)


# ── Die gemeinsamen Bausteine wirken ────────────────────────────────────────

def test_cra_nutzt_die_gemeinsame_pruefung():
    from cra import doc_pruefung as dp

    assert issubclass(dp.ErklaerungUnstimmig, fp.FormularUnstimmig)
    assert issubclass(dp.BestaetigungErforderlich, fp.BestaetigungErforderlich)
    assert dp.WIRKUNG_BLOCKIERT is fp.WIRKUNG_BLOCKIERT


def test_cra_nutzt_die_gemeinsamen_feldklassen():
    from cra import doc_vorschlag as dv

    assert set(dv.FELD_KLASSE.values()) <= set(fv.KLASSEN)


def test_cra_filtert_die_ki_ueber_shared():
    """Die Grenze gegen die KI darf nicht je Modul nachgebaut werden."""
    from cra import doc_vorschlag as dv

    programm = _ohne_kommentare(inspect.getsource(dv.uebernahme_filter))
    assert "filter_ki" in programm


@pytest.mark.parametrize("datei", FACHMODULE)
def test_kein_modul_baut_die_muster_nach(datei):
    """Platzhalter- und Versions-Muster gehören in ``shared``.

    Die beiden Fallen aus #1885 sind nicht naheliegend: Ein Regex auf jede
    Zahlenfolge liest „TLS 1.3" als Produktversion (blockierender Fehlalarm),
    und ein Prüfer über *alle* Dict-Schlüssel schlägt auf seinen eigenen
    Hinweistext an. Wer sie nachbaut, baut die Fallen mit nach.
    """
    programm = _ohne_kommentare((REPO / datei).read_text(encoding="utf-8"))
    for verboten in ("zu ergänzen", "[FEHLT]", "TBD", "sha256:[0-9a-f]",
                     r"\d+(?:\.\d+)"):
        assert verboten not in programm, (
            f"{datei} bringt ein eigenes Muster mit — gehört nach "
            "shared/formular_pruefung.py")


def test_jedes_fachmodul_benutzt_die_gemeinsamen_bausteine():
    """Nicht nur „kein eigenes Muster", sondern auch „benutzt das gemeinsame":
    Ein Modul, das die Prüfung ganz weglässt, fiele dem Negativ-Wächter nicht
    auf."""
    import importlib

    for datei in FACHMODULE:
        modul = importlib.import_module(datei[:-3].replace("/", "."))
        quelle = _ohne_kommentare(inspect.getsource(modul))
        assert ("formular_pruefung" in quelle
                or "formular_vorschlag" in quelle), datei


def test_jede_erklaerung_hat_ihre_eigene_ausnahmeklasse():
    """Gemeinsame Basis, eigene Meldung: ``FormularUnstimmig`` kennt den
    Gegenstand nicht, und „Das Formular kann nicht abgeschlossen werden" ist
    in einer Konformitätserklärung die falsche Auskunft."""
    from ai_act import doc_pruefung as aiact_dp
    from cra import doc_pruefung as cra_dp

    for klasse in (cra_dp.ErklaerungUnstimmig, aiact_dp.ErklaerungUnstimmig):
        assert issubclass(klasse, fp.FormularUnstimmig)
        meldung = str(klasse([{"text": "x"}]))
        assert "EU-Konformitätserklärung" in meldung


def test_die_wirkungsstufen_stehen_an_einer_stelle():
    """Drei Stufen, drei Bedeutungen. Ein Modul, das eine vierte erfindet,
    macht die Ampel unlesbar."""
    assert {fp.WIRKUNG_BLOCKIERT, fp.WIRKUNG_BESTAETIGUNG,
            fp.WIRKUNG_HINWEIS} == {"blockiert", "bestaetigung", "hinweis"}


# ── Die Regeln selbst ───────────────────────────────────────────────────────

def test_nur_leere_felder():
    """Ein gefülltes Feld ist die Aussage eines Menschen (#1769/#1773)."""
    vorschlaege = {"a": {}, "b": {}, "c": {}}
    werte = {"a": "steht", "b": "", "c": []}
    assert fv.nur_leere(vorschlaege, werte) == ["b", "c"]


def test_ein_schalter_gilt_als_nicht_gefuellt_wenn_er_falsch_ist():
    """``INTEGER NOT NULL DEFAULT 0`` kennt „nein" und „nicht gesetzt" nicht
    auseinander (#1805) — ein falscher Schalter darf einen Vorschlag nicht
    blockieren."""
    assert not fv.ist_gefuellt(False)
    assert fv.ist_gefuellt(True)


def test_der_sammler_verlangt_wert_und_quelle():
    s = fv.Sammler({"a": fv.KLASSE_GERECHNET})
    s.setze("a", "Wert", "Quelle")
    s.setze("b", "", "Quelle")          # ohne Wert
    s.setze("c", "Wert", "")            # ohne Quelle
    erg = s.ergebnis()
    assert set(erg) == {"a"}
    assert erg["a"]["klasse"] == fv.KLASSE_GERECHNET


def test_ein_feld_ohne_klasse_gilt_als_uebernommen():
    """Die mildere Annahme: Füll-Knopf ja, KI nein — dafür muss es
    ausdrücklich in der KI-Liste stehen."""
    erg = fv.Sammler({}).setze("x", "W", "Q").ergebnis()
    assert erg["x"]["klasse"] == fv.KLASSE_UEBERNOMMEN


def test_die_ki_grenze_benennt_das_verworfene():
    uebernommen, verworfen = fv.filter_ki(
        {"prosa": "Text", "version": "9.9.9"}, {"prosa"})
    assert uebernommen == {"prosa": "Text"}
    assert verworfen == ["version"]
    assert "version" in fv.verworfen_satz(verworfen)


def test_ohne_verworfenes_kein_satz():
    assert fv.verworfen_satz([]) == ""


# ── Die beiden Fallen aus #1885, jetzt zentral ──────────────────────────────

@pytest.mark.parametrize("text", [
    "Verschlüsselung nach TLS 1.3",
    "Stückliste im Format SPDX 2.3",
    "Managementsystem nach ISO/IEC 27001:2022",
])
def test_zahlen_in_prosa_sind_keine_versionen(text):
    assert fp.versionen_im_kontext(text) == []


@pytest.mark.parametrize("text,erwartet", [
    ("Produkt, Release 8.2.3", ["8.2.3"]),
    ("Fassung v1.0 des Systems", ["1.0"]),
    ("Version 2.0 und Release 3.1", ["2.0", "3.1"]),
])
def test_versionen_im_kontext_werden_erkannt(text, erwartet):
    assert fp.versionen_im_kontext(text) == erwartet


def test_ohne_vergleichsmassstab_kein_abgleich():
    """Ein Prüfer, der immer anschlägt, wird abgeschaltet (#1805)."""
    assert fp.version_befunde({"a": "Release 9.9.9"}, ("a",), (),
                              lambda f: f, lambda f: 0) == []


def test_geprueft_wird_eine_positivliste():
    """Abgeleitete Felder tragen absichtlich Texte wie ``[fehlt — …]``."""
    werte = {"eingabe": "ok", "abgeleitet": "[fehlt — Nr. 6]"}
    assert fp.texte(werte, ("eingabe",)) == [("eingabe", "ok")]


def test_ein_blockierender_befund_hat_keine_bestaetigung():
    befunde = fp.platzhalter_befunde({"a": "TBD"}, ("a",),
                                     lambda f: "Feld A", lambda f: 1)
    harte = fp.blockierend(befunde)
    assert harte and all("confirm" not in b for b in harte)


def test_offene_bestaetigungen_beruecksichtigen_das_gegebene():
    befunde = fp.datum_vor_befund("2026-01-01", "2026-02-01", feld="datum",
                                  nr=8, confirm="confirm_x", was="Das Dokument",
                                  bezug_label="die Freigabe")
    assert fp.offene_bestaetigungen(befunde, []) == befunde
    assert fp.offene_bestaetigungen(befunde, ["confirm_x"]) == []


def test_katalog_zuordnung_liest_den_anhang_katalog():
    from cra.doc_export import ANHANG_V

    nummern, labels = fp.katalog_zuordnung(ANHANG_V)
    assert nummern["gegenstand"] == 4
    assert labels["gegenstand"] == "Gegenstand der Erklärung"


# ── Frontend ────────────────────────────────────────────────────────────────

FRONTEND = REPO / "frontend/src"


def test_die_frontend_mechanik_liegt_im_composable():
    """Dieselbe Regel im Frontend nachzubauen ist die Lehre aus #1703/S9."""
    form = (FRONTEND / "components/cra/KonformitaetserklaerungForm.vue").read_text(
        encoding="utf-8")
    assert "useFormularVorschlag" in form
    assert "QuellenLeiste" in form and "BefundListe" in form


#: Geteilte Bausteine dieser Familie — sie **sind** die Mechanik und benutzen
#: sie nicht. Jede Ausnahme trägt ihren Grund, sonst wird die Liste zum Teppich
#: (#1805/#1834).
_BAUSTEINE = {
    # Die Leiste für alle Felder auf einmal.
    "QuellenLeiste.vue",
    # #1900: der Knopf je einzelnem Feld. Er nennt „Aus den Quellen füllen" im
    # Tooltip, ist aber selbst der geteilte Baustein — vorher stand er doppelt
    # in cra/ und aiact/KonformitaetserklaerungForm.vue.
    "QuellenKnopf.vue",
}


def test_keine_maske_baut_die_fuell_mechanik_nach():
    """Wer „nur leere Felder" selbst schreibt, schreibt irgendwann „alle"."""
    verdaechtig: list[str] = []
    for datei in FRONTEND.rglob("*.vue"):
        text = datei.read_text(encoding="utf-8")
        if "Aus den Quellen füllen" not in text:
            continue
        if datei.name in _BAUSTEINE:
            continue
        if "QuellenLeiste" not in text:
            verdaechtig.append(str(datei.relative_to(FRONTEND)))
    assert verdaechtig == [], (
        "diese Masken zeigen den Knopf, ohne die geteilte Leiste zu "
        f"benutzen: {verdaechtig}")
