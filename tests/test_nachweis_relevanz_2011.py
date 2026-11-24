"""Nachweise: erreichen, zählen, kennzeichnen — #2011/#2015/#2016/#2021/#2079.

Fünf Fundstellen an einem Gegenstand: dem Nachweis, auf den sich später jemand
beruft. Drei Richtungen, in denen das schiefgehen kann:

* Der Inhalt **erreicht** das Dokument nicht (#2011) — eine Zeile behauptet
  einen Nachweis und sagt nichts.
* Ein Nachweis wird **gezählt**, obwohl seine Datei fehlt (#2015) oder obwohl
  er gar keiner ist (#2079) — eine falsche Anrechnung sieht aus wie ein
  Nachweis, und das ist schlimmer als eine fehlende.
* Der Weg, eine eigene Vorlage zu hinterlegen, **sieht aus, als gäbe es ihn
  nicht** (#2021).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

CRA_DB = Path("data/db/cra.sqlite")
PROJ = "pytest-nachweis-2011"


def _vue(pfad: str) -> str:
    from tests.i18n_text import ohne_kommentare

    return ohne_kommentare(Path(pfad).read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════════════
# #2011 — der KI-Entwurf erreicht das TOM-Dokument
# ══════════════════════════════════════════════════════════════════════════════

def test_entwurfs_eintraege_tragen_den_schluessel_den_der_leser_liest():
    """``entwurf_mappings`` schrieb ``text``, ``build_tom_abschnitt`` liest
    ``claim`` — der Entwurfstext erreichte das Dokument nicht."""
    from dsgvo.tom import entwurf_mappings

    out = entwurf_mappings({"abschnitte": {"TOM-A": {
        "vorhandene_massnahmen": ["Festplattenverschlüsselung aktiv"],
        "luecken": ["Kein Protokoll der Zugriffe"],
        "empfehlungen": ["Protokollierung einschalten"]}}})
    eintraege = out["TOM-A"]
    assert len(eintraege) == 3
    for e in eintraege:
        assert e.get("claim"), "ohne `claim` liest build_tom_abschnitt nichts"
        assert e["claim"] == e["text"], (
            "`text` bleibt für den Vorlagen-Weg (#2005) und muss übereinstimmen")
        assert e.get("citations"), "der Beleg braucht eine Zitatliste"
        assert e["citations"][0]["doc_name"] == "KI-Entwurf"


def test_aus_drei_eintraegen_werden_drei_zeilen():
    """Gemessen war: **eine** Zeile ``['[NACHWEIS]', '', '']`` — eine Zeile,
    die einen Nachweis behauptet und nichts sagt."""
    from dsgvo.tom import TOM_ABSCHNITTE, build_tom_abschnitt, entwurf_mappings

    abschnitt = TOM_ABSCHNITTE[0]
    mappings = entwurf_mappings({"abschnitte": {abschnitt["id"]: {
        "vorhandene_massnahmen": ["Maßnahme Alpha", "Maßnahme Beta"],
        "luecken": ["Lücke Gamma"]}}})
    inhalt = build_tom_abschnitt(abschnitt=abschnitt, bewertungen={},
                                 approved_mappings=mappings, doc_index={})
    texte = [m["text"] for m in inhalt["massnahmen"]]
    for erwartet in ("Maßnahme Alpha", "Maßnahme Beta", "⚠ Lücke: Lücke Gamma"):
        assert any(erwartet in t for t in texte), (
            f"{erwartet!r} erreicht das Dokument nicht — vorhanden: {texte}")
    assert inhalt["has_evidence"] is True


# ══════════════════════════════════════════════════════════════════════════════
# #2079 — „test" trifft nur genau
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("doc_type,erwartet", [
    ("test", True),             # genau
    ("pentest", True),          # langes Stichwort, Teilstring erlaubt
    ("testbericht", True),
    ("attestation", False),     # der gemeldete Fall: SOC-2-Attestation
    ("attest", False),
    ("Testat", False),
    ("latest", False),
])
def test_kurze_stichworte_treffen_nur_genau(doc_type, erwartet):
    """``annex_evidence`` führt dafür seit #2003 ``_NUR_GENAU``, und diese Datei
    wendete die Liste nicht an.

    Ein SOC-2-Attestation-Dokument machte damit ``juengster`` auf sein
    Hochladedatum: ``kein_nachweis`` entfiel, ``zu_alt`` entfiel — die
    18-Monats-Prüfung aus Anhang I Teil II Nr. 3 war erfüllt, obwohl kein Test
    vorliegt.
    """
    from cra.sicherheitstests import _firma_doc_stichworte, _trifft

    stichworte, nur_genau = _firma_doc_stichworte()
    assert _trifft(stichworte, nur_genau, doc_type.lower(), "") is erwartet


def test_die_positivliste_kommt_aus_einer_quelle():
    """Zwei Fassungen von ``_NUR_GENAU`` wären zwei Begriffe von „Testnachweis"."""
    from cra.annex_evidence import _NUR_GENAU
    from cra.sicherheitstests import _firma_doc_stichworte

    _stichworte, nur_genau = _firma_doc_stichworte()
    assert nur_genau == frozenset(_NUR_GENAU)


def test_ein_tag_trifft_als_ganzes_wort():
    """Marken sind einzelne Wörter — ``latest`` als Tag ist kein Testnachweis."""
    from cra.sicherheitstests import _firma_doc_stichworte, _trifft

    stichworte, nur_genau = _firma_doc_stichworte()
    assert _trifft(stichworte, nur_genau, "", "test release") is True
    assert _trifft(stichworte, nur_genau, "", "latest release") is False


# ══════════════════════════════════════════════════════════════════════════════
# #2015 — ein Testnachweis ohne Datei wird benannt
# ══════════════════════════════════════════════════════════════════════════════

def test_sicherheitstests_prueft_den_dateistand():
    """Die Matrix lernte es mit #1974, der **gerechnete** Prüfpunkt nicht.

    Eine Datei, die nicht mehr vorliegt, schob den Bezugszeitpunkt nach vorn
    und konnte die 18-Monats-Prüfung erfüllen, obwohl nichts vorzulegen ist.
    Dieselbe Datei trug in der Anhang-VII-Matrix „Datei fehlt" und hier gar
    nichts — zwei Aussagen über denselben Sachverhalt (#1726/#1727).
    """
    baum = ast.parse(Path("cra/sicherheitstests.py").read_text(encoding="utf-8"))
    namen: set[str] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom) and (knoten.module or "").startswith("evidence"):
            namen |= {a.asname or a.name for a in knoten.names}
    assert {"dateistand", "DATEI_FEHLT"} <= namen, (
        f"der Dateistand wird nicht gelesen — importiert: {sorted(namen)}")


def test_beide_strecken_benennen_die_fehlende_datei_gleich():
    """Matrix und Prüfpunkt lesen dieselbe Quelle und sagen dasselbe."""
    for pfad in ("cra/annex_evidence.py", "cra/sicherheitstests.py"):
        quelle = Path(pfad).read_text(encoding="utf-8")
        assert "Datei fehlt" in quelle, f"{pfad} benennt die fehlende Datei nicht"


# ══════════════════════════════════════════════════════════════════════════════
# #2016 — die freigegebene Zuordnung bleibt vorrangig und wird gekennzeichnet
# ══════════════════════════════════════════════════════════════════════════════

def test_freigegebene_zuordnung_prueft_die_datei():
    baum = ast.parse(Path("shared/evidence_context.py").read_text(encoding="utf-8"))
    fn = next(k for k in ast.walk(baum)
              if isinstance(k, ast.FunctionDef) and "mapping" in k.name.lower())
    quelle = ast.unparse(fn)
    assert "dateistand" in quelle, (
        "der Zweig der freigegebenen Zuordnungen fragt den Dateistand nicht ab "
        "— und er trägt die höchste Relevanz im Block")
    assert "OHNE_DATEI_VERMERK" in quelle


def test_die_freigabe_bleibt_vorrangig():
    """**Die Relevanz bleibt 2.0.** Eine fehlende Datei hebt keine menschliche
    Freigabe auf — sie ist die Aussage eines Menschen, der das Dokument gelesen
    hat, und seit #1991 beantwortet sie die Anforderung. Gekennzeichnet wird
    sie trotzdem (die Linie aus #1974: benennen, nicht ausschließen).
    """
    baum = ast.parse(Path("shared/evidence_context.py").read_text(encoding="utf-8"))
    fn = next(k for k in ast.walk(baum)
              if isinstance(k, ast.FunctionDef) and "mapping" in k.name.lower())
    quelle = ast.unparse(fn)
    assert "relevance=2.0" in quelle.replace(" ", ""), (
        "die Relevanz wurde gesenkt — damit schneidet rank_and_truncate die "
        "menschliche Freigabe vor den schwächeren Belegen weg")
    assert "RELEVANZ_OHNE_DATEI" not in quelle


# ══════════════════════════════════════════════════════════════════════════════
# #2021 — der Vorlagen-Weg ist sichtbar, auch wenn er leer ist
# ══════════════════════════════════════════════════════════════════════════════

VORLAGEN_STELLEN = [
    ("frontend/src/views/dsgvo/DSGVOView.vue", 'v-if="tomVorlagen.length"'),
    ("frontend/src/components/shared/ReportCenterPanel.vue",
     'v-if="vorlagenFuer(r).length"'),
]


@pytest.mark.parametrize("pfad,altes_muster", VORLAGEN_STELLEN)
def test_das_auswahlfeld_versteckt_sich_nicht_mehr(pfad, altes_muster):
    """Die Meldung lautete „kann keine Vorlage hinterlegt werden" — und für
    ``tom_entwurf`` gab es auf keiner Instanz eine. Ein vorhandener Mechanismus
    sah damit aus wie ein fehlender (dieselbe Form wie #1817)."""
    quelle = _vue(pfad)
    assert altes_muster not in quelle, (
        "das Feld hängt weiter daran, dass es etwas zu wählen gibt")
    assert "keineVorlage" in quelle, "der leere Zustand sagt nichts"


def test_der_leere_zustand_steht_in_beiden_sprachen():
    from tests.i18n_text import nachricht

    for sprache in ("de", "en"):
        for schluessel in ("geteilt.reportCenterPanel.keineVorlageFuerDiesenBericht",
                           "geteilt.reportCenterPanel.keineVorlageFuerDenEntwurf"):
            assert nachricht(schluessel, sprache), f"{schluessel} fehlt in {sprache}"


def test_der_berichtstyp_hat_einen_bauplan():
    """#2021, zweite Hälfte: Ohne Bauplan im Generator kann nie eine Vorlage
    entstehen. Der Eintrag kam mit #2005; dass daraus noch keine Datei erzeugt
    wurde, ist ein Betriebsschritt und kein Codefehler."""
    from tools.vorlagen.cyberwoks_plaene import PLAENE

    from dsgvo.tom import ENTWURF_TYP

    assert ("dsgvo", ENTWURF_TYP) in PLAENE, (
        f"für {ENTWURF_TYP} gibt es keinen Bauplan — test_vorlagen_generator_1790 "
        "hält das normalerweise")
