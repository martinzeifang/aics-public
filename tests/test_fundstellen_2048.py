"""Rechtsfundstellen gegen das Amtsblatt — #2048–#2060.

Dreizehn Fundstellen aus dem Prüflauf 09.11.2026, in CRA, NIS2 und AI Act.
Keine davon lässt etwas fehlschlagen; jede ist eine **Rechtsaussage**, nach der
jemand entscheidet, und mehrere werden in Nachweisdokumente gedruckt.

Es ist die vierte Runde derselben Fehlerklasse (#1763, #1792, #1884, #1953), und
sie entsteht immer gleich: Die Nachbarnummer existiert und klingt plausibel.

ZWEI ARTEN VON PRÜFUNG
* **Strukturell** — läuft immer: Begriffe, die im amtlichen Text 0× vorkommen,
  dürfen nicht im Produktionscode stehen; eine Fundstelle darf keine URL sein;
  eine Monatsfrist darf nicht in Stunden gerechnet werden.
* **Gegen den Text** — läuft nur, wenn die amtlichen Fassungen vorliegen
  (``data/*_resources/``, gitignored, also in der Installation und lokal, nicht
  in der CI). Ein ``skip`` sagt das ausdrücklich; ein stiller Durchlauf wäre
  schlimmer als keine Prüfung.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

CRA_PDF = Path("data/cra_resources/32024R2847_DEU.pdf")
NIS2_PDF = Path("data/nis2_resources/32022L2555_DEU.pdf")
AIACT_PDF = Path("data/ai_act_resources/32024R1689_DEU.pdf")

_CACHE: dict[str, str] = {}


def _amtlich(pdf: Path) -> str:
    """Den amtlichen Text lesen — oder den Test überspringen."""
    if not pdf.is_file():
        pytest.skip(f"{pdf} liegt nicht vor (data/ ist gitignored) — "
                    "die Prüfung gegen den Text läuft lokal und in der "
                    "Installation, nicht in der CI")
    if str(pdf) not in _CACHE:
        try:
            import pdfplumber
        except ImportError:                       # pragma: no cover
            pytest.skip("pdfplumber fehlt")
        with pdfplumber.open(pdf) as doc:
            roh = "\n".join((s.extract_text() or "") for s in doc.pages)
        # Leerraum normalisieren: Im PDF-Layout bricht jeder Satz mehrfach um,
        # und ein gesuchter Wortlaut wäre dann nie zu finden. Ein Wächter, der
        # daran scheitert, prüft nichts.
        _CACHE[str(pdf)] = " ".join(roh.split())
    return _CACHE[str(pdf)]


def _programm(pfad: str) -> str:
    """Quelltext ohne Kommentare und Docstrings (#1834 ff.)."""
    baum = ast.parse(Path(pfad).read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef)):
            if (knoten.body and isinstance(knoten.body[0], ast.Expr)
                    and isinstance(knoten.body[0].value, ast.Constant)
                    and isinstance(knoten.body[0].value.value, str)):
                knoten.body = knoten.body[1:] or [ast.Pass()]
    return ast.unparse(baum)


# ══════════════════════════════════════════════════════════════════════════════
# #2048 — der Zertifikatsgrad heißt anders
# ══════════════════════════════════════════════════════════════════════════════

def test_der_amtliche_begriff_steht_im_text():
    cra = _amtlich(CRA_PDF)
    assert cra.count("Vertrauenswürdigkeitsstufe") > 0
    assert cra.count("substanziell") == 0, (
        "„substanziell“ ist die Terminologie der Vorgänger-Entwürfe")
    assert cra.count("Vertrauensniveau") == 0
    assert "mindestens der Vertrauenswürdigkeitsstufe „mittel“" in cra


def test_kein_vorgaenger_begriff_im_produktionscode():
    """Der Begriff wird in den Konformitätsbericht gedruckt."""
    quelle = _programm("cra/requirements.py")
    for wort in ("substanziell", "Vertrauensniveau"):
        assert wort not in quelle, f"„{wort}“ steht weiter im Programm"
    assert "Vertrauenswürdigkeitsstufe" in quelle


# ══════════════════════════════════════════════════════════════════════════════
# #2049 — eine erfundene gesetzliche Frist
# ══════════════════════════════════════════════════════════════════════════════

def test_die_verordnung_nennt_keine_zehn_tage():
    cra = _amtlich(CRA_PDF)
    for begriff in ("zehn Tage", "10 Tage", "zehn Arbeitstage"):
        assert cra.count(begriff) == 0, f"„{begriff}“ kommt vor — Befund prüfen"
    assert "auf deren begründetes Verlangen" in cra


def test_keine_erfundene_frist_in_den_anforderungen():
    """Eine erfundene gesetzliche Frist ist schlimmer als keine: Danach richtet
    jemand seinen Prozess aus."""
    quelle = _programm("cra/requirements.py")
    assert "binnen 10 Tagen" not in quelle
    assert "begründetes Verlangen" in quelle


# ══════════════════════════════════════════════════════════════════════════════
# #2057 — die Marktüberwachungsartikel
# ══════════════════════════════════════════════════════════════════════════════

AMTLICHE_UEBERSCHRIFTEN = {
    53: "Zugang zu Daten und zur Dokumentation",
    58: "Formale Nichtkonformität",
}


@pytest.mark.parametrize("nummer,ueberschrift", AMTLICHE_UEBERSCHRIFTEN.items())
def test_artikelueberschrift_stimmt(nummer, ueberschrift):
    cra = _amtlich(CRA_PDF)
    assert f"Artikel {nummer}" in cra
    assert ueberschrift in cra, f"Art. {nummer} heißt nicht {ueberschrift!r}"


def test_art57_ist_risiko_trotz_konformitaet():
    cra = _amtlich(CRA_PDF)
    assert ("Konforme Produkte mit digitalen Elementen, die ein erhebliches "
            "Cybersicherheitsrisiko bergen") in cra


def test_marktueberwachung_nennt_die_richtigen_artikel():
    quelle = Path("cra/marktueberwachung_db.py").read_text(encoding="utf-8")
    assert "Art. 52-58" in quelle, "die Modulüberschrift nennt die falsche Spanne"
    assert "Art. 57" in quelle and "Art. 58" in quelle, (
        "die Fallgruppen „Risiko trotz Konformität“ (Art. 57) und „formale "
        "Nichtkonformität“ (Art. 58) fehlen — und genau diese Zuordnung "
        "schreibt ein Bearbeiter in den Vorgang")


# ══════════════════════════════════════════════════════════════════════════════
# #2058 — vier kleinere Fundstellen
# ══════════════════════════════════════════════════════════════════════════════

def test_ce_hoehe_die_cra_weicht_ab():
    cra = _amtlich(CRA_PDF)
    assert ("kann die Höhe des daran angebrachten CE-Kennzeichens kleiner als "
            "5 mm sein") in cra


def test_ce_modul_behauptet_keine_untergrenze_mehr():
    """Kommentarfrei geprüft: Mein eigener Kommentar **zitiert** den falschen
    Satz, um die Reparatur zu erklären — und hat diesen Wächter beim ersten
    Anlauf rot gemacht. Siebtes Mal dieselbe Lehre in diesem Repo
    (#1834/#1867/#1878/#1903/#1974/#2069/#2026)."""
    programm = _programm("cra/ce_mark.py")
    assert "Kleiner darf das Zeichen nicht gedruckt werden" not in programm, (
        "der Satz ist für die CRA falsch (Art. 30 Abs. 2)")
    # Die Fundstelle steht als Begründung im Dateikopf, also im Rohtext.
    assert "Art. 30 Abs. 2" in Path("cra/ce_mark.py").read_text(encoding="utf-8")


def test_akteurs_artikel_sind_nicht_verschoben():
    """Drei von vier waren um eine Position verschoben — dieselbe Klasse wie
    der Anhang-IV-Versatz aus #1953."""
    for sprache in ("de", "en"):
        text = Path(f"frontend/src/help/{sprache}/cra.json").read_text(encoding="utf-8")
        assert "Art. 19 (Bevollmächtigter)" not in text
        assert "Art. 19 (authorised representative)" not in text
        assert "Art. 22 (Händler)" not in text
        assert "Art. 22 (distributors)" not in text


def test_kein_aufgehobenes_bsig():
    """§ 8a BSIG ist eine Vorschrift des **aufgehobenen** BSIG 2009 und betraf
    Betreiber Kritischer Infrastrukturen, nicht MSP/Cloud."""
    quelle = _programm("nis2/ai_wizards.py")
    assert "§ 8a BSIG" not in quelle
    assert "§ 30 BSIG" in quelle or "§ 34 BSIG" in quelle


# ══════════════════════════════════════════════════════════════════════════════
# #2060 — eine Fundstelle ist keine Internetadresse
# ══════════════════════════════════════════════════════════════════════════════

def test_jede_ai_act_anforderung_nennt_artikel_und_absatz():
    """Für einen Prüfer ist „CELEX:32024R1689“ keine Fundstelle, sondern der
    Hinweis, dass er selbst suchen soll."""
    import ai_act.requirements as ar

    liste = next(v for v in vars(ar).values()
                 if isinstance(v, list) and v and isinstance(v[0], dict)
                 and "id" in v[0])
    assert len(liste) == 13
    for r in liste:
        ref = str(r.get("ref") or "")
        assert ref, f"{r['id']} hat keine Fundstelle"
        assert not ref.startswith("http"), (
            f"{r['id']} nennt eine URL statt einer Vorschrift: {ref}")
        assert re.search(r"Art\.\s*\d+", ref), f"{r['id']}: {ref!r}"


AI_ACT_UEBERSCHRIFTEN = {
    9: "Risikomanagementsystem",
    10: "Daten und Daten-Governance",
    11: "Technische Dokumentation",
    12: "Aufzeichnungspflichten",
    14: "Menschliche Aufsicht",
    17: "Qualitätsmanagementsystem",
    73: "Meldung schwerwiegender Vorfälle",
}


@pytest.mark.parametrize("nummer,ueberschrift", AI_ACT_UEBERSCHRIFTEN.items())
def test_ai_act_artikelueberschrift_stimmt(nummer, ueberschrift):
    t = _amtlich(AIACT_PDF)
    assert ueberschrift in t, f"Art. {nummer} heißt nicht {ueberschrift!r}"


def test_change_management_steht_in_art_17_abs_1_buchst_a():
    """Die Zuordnung, die ich selbst am Text nachgelesen habe."""
    t = _amtlich(AIACT_PDF)
    assert "Verfahren für das Management von Änderungen" in t


# ══════════════════════════════════════════════════════════════════════════════
# #2050 — der 3-Jahres-Zyklus ist nationales Recht
# ══════════════════════════════════════════════════════════════════════════════

def test_nis2_nennt_keinen_turnus():
    nis = _amtlich(NIS2_PDF)
    for begriff in ("drei Jahre", "Dreijahres", "3-Jahres"):
        assert nis.count(begriff) == 0, f"„{begriff}“ kommt in NIS2 vor"
    assert ("regelmäßige und gezielte Sicherheitsprüfungen" in nis), (
        "Art. 32 Abs. 2 Buchst. b nicht gefunden")


def test_der_turnus_ist_als_hausregel_benannt():
    """Unionsrecht und nationales Recht als dasselbe auszugeben ist die Klasse,
    auf die dieser Prüflauf wiederholt gestoßen ist."""
    quelle = Path("nis2/audit_db.py").read_text(encoding="utf-8")
    assert "§ 39 BSIG" in quelle, "die wirkliche Fundstelle fehlt"
    programm = _programm("nis2/audit_db.py")
    assert "3-Jahres-Zyklus Art. 32" not in programm


# ══════════════════════════════════════════════════════════════════════════════
# #2051 — ein Monat ist ein Kalendermonat
# ══════════════════════════════════════════════════════════════════════════════

def test_abschlussbericht_rechnet_in_kalendermonaten():
    """Bei einer Meldung am 1. Februar ist die Frist der 1. März; mit ``30 * D``
    kam der 3. März heraus — zwei Tage **nach** Fristablauf noch „on track“."""
    from shared import deadlines as dl

    r = dl.evaluate("2026-02-01T10:00:00+00:00", "nis2_art23",
                    now="2026-02-02T10:00:00+00:00")
    ab = next(s for s in r["stages"] if s["key"] == "abschlussbericht")
    assert ab["due_at"].startswith("2026-03-01"), ab["due_at"]


def test_der_monatsendfall_wandert_nicht_in_den_naechsten_monat():
    from shared import deadlines as dl

    r = dl.evaluate("2026-01-31T10:00:00+00:00", "nis2_art23",
                    now="2026-02-01T10:00:00+00:00")
    ab = next(s for s in r["stages"] if s["key"] == "abschlussbericht")
    assert ab["due_at"].startswith("2026-02-28"), ab["due_at"]


def test_beide_monatsstufen_sind_umgestellt():
    """NIS2 **und** CRA — zwei Sets mit derselben Rechnung."""
    from shared.deadlines import STAGE_SETS

    for schluessel in ("nis2_art23", "cra_art14"):
        stufe = next(s for s in STAGE_SETS[schluessel]
                     if s.key == "abschlussbericht")
        assert stufe.offset_months == 1, (
            f"{schluessel}: Abschlussbericht rechnet weiter in Stunden")


def test_die_stundenfristen_bleiben_unberuehrt():
    """24 h und 72 h sind Stundenfristen und bleiben es."""
    from shared.deadlines import STAGE_SETS

    for schluessel, erwartet in (("nis2_art23", {"fruehwarnung": 24.0,
                                                 "meldung": 72.0}),
                                 ("dsgvo_art33", {"aufsichtsmeldung": 72.0})):
        for stufe in STAGE_SETS[schluessel]:
            if stufe.key in erwartet:
                assert stufe.offset_hours == erwartet[stufe.key]
                assert stufe.offset_months == 0


# ══════════════════════════════════════════════════════════════════════════════
# #2052 / #2054 / #2055 / #2059 — NIS2-Zuordnungen
# ══════════════════════════════════════════════════════════════════════════════

def test_art21_abs2_buchstaben_stehen_so_im_text():
    nis = _amtlich(NIS2_PDF)
    assert "Konzepte in Bezug auf die Risikoanalyse und Sicherheit für Informationssysteme" in nis
    assert "Bewältigung von Sicherheitsvorfällen" in nis
    assert "Sicherheit des Personals, Konzepte für die Zugriffskontrolle und Management von Anlagen" in nis


@pytest.mark.parametrize("sprache,falsch", [
    ("de", "Art. 21 (2) lit. a verlangt eine vollständige Bestandsaufnahme"),
    ("de", "Art. 21 (2) lit. b verlangt ein dokumentiertes Risiko-Management"),
    ("en", "Art. 21(2) point (a) requires a complete inventory"),
    ("en", "Art. 21(2) point (b) requires documented risk management"),
])
def test_lit_a_und_b_sind_nicht_mehr_vertauscht(sprache, falsch):
    """Beide Angaben zeigten auf den jeweils anderen Gegenstand."""
    text = Path(f"frontend/src/i18n/{sprache}/nis2.json").read_text(encoding="utf-8")
    assert falsch not in text


def test_art27_abs4_richtet_sich_nicht_an_die_einrichtung():
    """#2059: #2004 hatte das im Datenpfad korrigiert — die Oberfläche nicht."""
    for sprache in ("de", "en"):
        text = Path(f"frontend/src/i18n/{sprache}/nis2.json").read_text(encoding="utf-8")
        assert "27(4)" not in text, "Abs. 4 adressiert die zentrale Anlaufstelle"
    assert "27(4)" not in _programm("nis2/fristen.py")


def test_die_nicht_erbringbare_pflicht_ist_weg():
    """#2054: Art. 22 richtet sich an die Kooperationsgruppe und die Kommission;
    eine Einrichtung kann sich daran nicht beteiligen. Eine Anforderung, die
    niemand erfüllen kann, wird nicht bearbeitet, sondern umgangen."""
    import nis2.requirements as nr

    liste = next(v for v in vars(nr).values()
                 if isinstance(v, list) and v and isinstance(v[0], dict)
                 and "id" in v[0])
    nis4 = next(r for r in liste if r["id"] == "NIS4-03")
    assert nis4["ref"].startswith("Art. 21 Abs. 3")
    assert "Beteiligung an koordinierten" not in nis4["beschreibung"]

    nis1 = next(r for r in liste if r["id"] == "NIS1-04")
    assert "Art. 21 Abs. 1" in nis1["ref"], (
        "NIS1-04 hing an Art. 20, der keine Strategiepflicht trägt")


def test_art22_adressiert_unionsorgane():
    nis = _amtlich(NIS2_PDF)
    assert "Die Kooperationsgruppe kann" in nis


# ══════════════════════════════════════════════════════════════════════════════
# #2056 — der Ringtausch der Erwägungsgründe
# ══════════════════════════════════════════════════════════════════════════════

def test_eg34_ist_der_lieferketten_erwaegungsgrund():
    cra = _amtlich(CRA_PDF)
    assert "von Dritten bezogene Komponenten" in cra
    assert cra.count("Governance") == 0, (
        "die CRA kennt keine Governance-Vorschrift — deshalb ist EG 34 bei "
        "IMPL-01 zu streichen und nicht zu ersetzen")


def test_impl01_nennt_keinen_erwaegungsgrund_mehr():
    import cra.requirements as cr

    liste = next(v for v in vars(cr).values()
                 if isinstance(v, list) and v and isinstance(v[0], dict)
                 and "id" in v[0])
    impl01 = next(r for r in liste if r["id"] == "IMPL-01")
    impl03 = next(r for r in liste if r["id"] == "IMPL-03")
    assert "Erwägungsgrund" not in impl01["ref"], impl01["ref"]
    assert "Erwägungsgrund 34" in impl03["ref"], impl03["ref"]
