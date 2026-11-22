"""Berichtstexte: vollständig, in beiden Sprachen, ohne gedruckte Schlüssel (#1954).

WARUM ES DIESEN WÄCHTER BRAUCHT
``shared/reports/texte.macher`` liefert bei unbekanntem Schlüssel den
**Schlüssel selbst** zurück. Das ist Absicht — eine leere Überschrift sieht
aus wie Absicht, ein sichtbarer Schlüssel nicht. Es heißt aber auch: Ein
vergessener Eintrag erscheint als ``g_sbom_vorhanden_ok`` in der
Ergebnisspalte des Vorgangsberichts, still und plausibel aussehend.

DIE VIERTE STELLE
Der Vorgangsbericht führt je **gerechnetem** Prüfpunkt zwei Texte
(``g_<quelle>_ok`` und ``g_<quelle>_fehl``). Damit steht ein solcher Punkt
jetzt an **vier** Orten: ``cra/release_checkliste.KATALOG``, dem flachen
Schlüssel in ``konformitaet_gate.evaluate()``, der Auswertung in
``release_bericht`` und dem Fall im ``ReleasesPanel``. Fehlt eine, rechnet
die Anwendung richtig und der Bericht meldet etwas anderes — genau die Falle,
die in #1762, #1773, #1799 und #1824 je einmal zugeschlagen hat.
"""
from __future__ import annotations

import importlib

import pytest

#: (Modul, Name des TEXTE-Katalogs). Jeder Renderer führt seinen eigenen —
#: ein zentraler Katalog wäre die Spiegel-Liste mit Prosa
#: (Begründung im Docstring von ``shared/reports/texte``).
RENDERER = [
    "cra.release_bericht", "cra.kundenfassung", "cra.doc_export",
    "cra.konformitaet_report", "cra.report_export",
    "ai_act.doc_export", "ai_act.report_export",
    "ai_act.berichte_provider", "nis2.report_export",
    "dsgvo.report_export", "dsgvo.tom", "dsgvo.privacy", "dsgvo.training",
    "dsgvo.einzelberichte", "dsgvo.jahresbericht_export",
    "dsgvo.datenpannen_frist",
]


def _texte(modulpfad: str) -> dict[str, dict[str, str]]:
    try:
        mod = importlib.import_module(modulpfad)
    except ImportError as e:  # pragma: no cover
        pytest.skip(f"{modulpfad} nicht importierbar: {e}")
    texte = getattr(mod, "TEXTE", None)
    if not isinstance(texte, dict) or "de" not in texte:
        pytest.skip(f"{modulpfad} führt (noch) keinen TEXTE-Katalog")
    return texte


@pytest.mark.parametrize("modulpfad", RENDERER)
def test_beide_sprachen_haben_dieselben_schluessel(modulpfad):
    """Eine halbe Übersetzung ist ein unvollständiges Dokument.

    Der Rückfall auf den deutschen Text ist richtig (siehe
    ``texte.macher``) — aber er macht die Lücke unsichtbar. Deshalb wird sie
    hier benannt.
    """
    texte = _texte(modulpfad)
    de, en = set(texte.get("de", {})), set(texte.get("en", {}))
    fehlt, zuviel = sorted(de - en), sorted(en - de)
    assert not fehlt and not zuviel, (
        f"{modulpfad}.TEXTE: {len(fehlt)} Schlüssel ohne englische Fassung, "
        f"{len(zuviel)} überzählig\n  fehlt: {fehlt[:20]}\n  "
        f"zuviel: {zuviel[:20]}")


@pytest.mark.parametrize("modulpfad", RENDERER)
def test_kein_wert_ist_leer(modulpfad):
    """Ein leerer Wert druckt eine Überschrift ohne Text."""
    texte = _texte(modulpfad)
    leer = [f"{code}:{k}" for code, kat in texte.items()
            for k, v in kat.items() if not (isinstance(v, str) and v.strip())]
    assert not leer, f"{modulpfad}.TEXTE: leere Werte — {leer[:20]}"


@pytest.mark.parametrize("modulpfad", RENDERER)
def test_platzhalter_sind_in_jeder_sprache_dieselben(modulpfad):
    """``{produkt}`` muss in beiden Fassungen vorkommen.

    Ein fehlender Platzhalter lässt den Wert **ohne** den Wert erscheinen
    (``str.format`` schluckt ihn nicht, er fehlt einfach im Satz); ein
    zusätzlicher wirft ``KeyError`` beim Erzeugen des Dokuments.
    """
    import re

    texte = _texte(modulpfad)
    de, en = texte.get("de", {}), texte.get("en", {})
    muster = re.compile(r"\{(\w+)\}")
    abweichung = []
    for k, v in de.items():
        if k not in en:
            continue
        a, b = set(muster.findall(v)), set(muster.findall(en[k]))
        if a != b:
            abweichung.append(f"{k}: de={sorted(a)} en={sorted(b)}")
    assert not abweichung, (
        f"{modulpfad}.TEXTE: Platzhalter weichen ab —\n  "
        + "\n  ".join(abweichung[:15]))


def test_jeder_gerechnete_pruefpunkt_hat_seine_beiden_ergebnistexte():
    """Die vierte Stelle: ``g_<quelle>_ok`` und ``g_<quelle>_fehl``.

    Der Vorgangsbericht druckt je gerechnetem Prüfpunkt einen Ergebnistext.
    Fehlt er, erscheint der **Schlüsselname** in der Ergebnisspalte — still,
    und er sieht wie ein Wert aus. Empfohlen vom Übersetzer des
    Vorgangsberichts, nachdem er alle 36 von Hand geprüft hatte.
    """
    rb = importlib.import_module("cra.release_bericht")
    kl = importlib.import_module("cra.release_checkliste")
    texte = getattr(rb, "TEXTE", None)
    if not isinstance(texte, dict):
        pytest.skip("cra.release_bericht führt (noch) keinen TEXTE-Katalog")

    quellen = {getattr(p, "quelle", "") for p in kl.KATALOG
               if getattr(p, "art", "") == "gerechnet"}
    quellen.discard("")
    assert quellen, "keine gerechneten Prüfpunkte gefunden — Katalog geändert?"

    fehlt = []
    for code, kat in texte.items():
        for q in sorted(quellen):
            for suffix in ("ok", "fehl"):
                if f"g_{q}_{suffix}" not in kat:
                    fehlt.append(f"{code}:g_{q}_{suffix}")
    assert not fehlt, (
        "Gerechnete Prüfpunkte ohne Ergebnistext — der Vorgangsbericht "
        "druckt dort den Schlüsselnamen:\n  " + "\n  ".join(fehlt[:30]))


# ── Bewusst nicht umschaltbar ────────────────────────────────────────────────

#: Renderer, die **absichtlich** keinen `TEXTE`-Katalog bekommen — je mit
#: Grund. Ohne diese Liste sähe ihre deutsche Fassung aus wie eine
#: vergessene Datei; mit ihr ist sie eine Entscheidung.
NICHT_UMSCHALTBAR: dict[str, str] = {
    "gutachten.gerichtsgutachten_gen":
        "Ein Gerichtsgutachten wird bei einem **deutschen** Gericht "
        "eingereicht und steht unter deutschem Verfahrensrecht — die "
        "Befangenheitserklärung nach § 406 ZPO und die Hilfspersonen nach "
        "§ 407a Abs. 2 ZPO sind Pflichtinhalte in der Sprache des Gerichts. "
        "Eine englische Fassung wäre bei keinem Gericht verwendbar und "
        "würde über die Verfahrensgrundlage täuschen. Die **Oberfläche** des "
        "Moduls ist umschaltbar, das Dokument nicht.",
    "gutachten.gutachten_gen":
        "Derselbe Grund: Der Renderer teilt Aufbau und Formeln mit dem "
        "Gerichtsgutachten. Soll ein Privatgutachten für einen "
        "international tätigen Auftraggeber englisch erscheinen, ist das ein "
        "eigener Vorgang mit eigener Abwägung — und keine Übersetzung "
        "dieses Renderers.",
    "wiba.report_export":
        "Die BSI-Prüffragen haben keine amtliche englische Fassung, und der "
        "Katalogtext ist urheberrechtlich geschützt (BSI). Übersetzt wäre er "
        "eine eigene Fassung, die sich als BSI-Inhalt ausgibt. Die "
        "**Rahmen**texte des Berichts folgen der Sprache des Mandanten, die "
        "Prüffragen bleiben deutsch.",
}


def test_die_ausnahmen_tragen_eine_begruendung():
    """Eine Ausnahme ohne Grund ist ein Teppich, kein Befund (#1851)."""
    for modulpfad, grund in NICHT_UMSCHALTBAR.items():
        assert len(grund) >= 120, \
            f"{modulpfad}: Grund zu knapp — {grund!r}"


@pytest.mark.parametrize("modulpfad", sorted(NICHT_UMSCHALTBAR))
def test_die_ausnahmen_stehen_nicht_zugleich_in_der_pflichtliste(modulpfad):
    """Keine Datei kann beides sein — sonst widerspricht sich der Wächter."""
    assert modulpfad not in RENDERER, (
        f"{modulpfad} steht in NICHT_UMSCHALTBAR **und** in RENDERER")
