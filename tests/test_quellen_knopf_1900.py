"""#1900 — der „⚙“-Knopf am Feld: eine Stelle, feste Größe.

Meldung aus dem Betrieb: „Der Knopf ist viel zu groß und passt nicht so richtig
in das Design."

Zwei Dinge steckten dahinter:

1. Er trug seinen Text mit (``⚙ füllen`` / ``⚙ ersetzen``) — bei 18 Feldern 18
   Textknöpfe in den Beschriftungszeilen, **und die Breite wechselte beim
   Tippen**, sobald aus „füllen“ ein „ersetzen“ wurde. Das Layout sprang also
   während der Eingabe.
2. Es gab ihn **zweimal** — in ``cra/`` und ``aiact/KonformitaetserklaerungForm.vue``,
   mit identischem CSS und identischem Verhalten. Die Spiegel-Liste aus
   #1731/#1735 in ihrer harmlosesten und zugleich sichtbarsten Form: Eine
   Korrektur an einer Fassung lässt die andere unschön.

Geprüft wird das **Programm**, nicht die Erzählung — die Dateikopf-Kommentare
zitieren den alten Zustand als Begründung und dürfen den Test nicht bewegen
(die Lehre aus #1834/#1867/#1878, und aus #1903, wo mir genau das passiert ist).
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
KOMPONENTE = WURZEL / "frontend/src/components/shared/QuellenKnopf.vue"
FORMULARE = [
    WURZEL / "frontend/src/components/cra/KonformitaetserklaerungForm.vue",
    WURZEL / "frontend/src/components/aiact/KonformitaetserklaerungForm.vue",
]


def _ohne_kommentare(text: str) -> str:
    """HTML-Kommentare, Blockkommentare und ``//``-Zeilen entfernen."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(z for z in text.splitlines()
                     if not z.lstrip().startswith("//"))


def test_die_komponente_gibt_es():
    assert KOMPONENTE.exists(), (
        "Der Knopf gehört in eine geteilte Komponente — sonst steht er wieder "
        "zweimal da und eine Korrektur trifft nur eine Fassung")


def test_beide_formulare_benutzen_sie():
    for datei in FORMULARE:
        programm = _ohne_kommentare(datei.read_text(encoding="utf-8"))
        assert re.search(r"^import QuellenKnopf from ", programm, re.M), (
            f"{datei.name} muss den geteilten Knopf einbinden")
        assert "h(QuellenKnopf" in programm, (
            f"{datei.name} bindet ihn ein, benutzt ihn aber nicht — "
            "genau die Klasse aus #1830 (da, aber ohne Wirkung)")


def test_kein_formular_baut_den_knopf_selbst():
    """Kein eigenes ``<button>`` mit dem Zahnrad, kein eigenes Styling."""
    for datei in FORMULARE:
        programm = _ohne_kommentare(datei.read_text(encoding="utf-8"))
        assert ".feld-knopf" not in programm, (
            f"{datei.name} trägt wieder eigenes Styling für den Knopf")
        # Ein `⚙` darf als Beschriftung größerer Knöpfe vorkommen
        # („⚙ Aus den Quellen füllen“ für alle Felder) — aber nicht in einem
        # selbstgebauten Feld-Knopf mit `onClick: () => …fuellen(`.
        assert not re.search(r"h\('button',[^)]*fuellen\(", programm), (
            f"{datei.name} baut den Feld-Knopf wieder selbst")


def test_der_knopf_hat_eine_feste_groesse():
    """Die wechselnde Breite war der eigentliche Mangel, nicht die Größe."""
    programm = _ohne_kommentare(KOMPONENTE.read_text(encoding="utf-8"))
    assert re.search(r"\.knopf\s*\{[^}]*width:\s*\d+px", programm, re.S), (
        "Ohne feste Breite springt die Zeile beim Tippen, sobald aus „füllen“ "
        "ein „ersetzen“ wird")
    assert re.search(r"\.knopf\s*\{[^}]*height:\s*\d+px", programm, re.S)


def test_der_knopf_traegt_seinen_text_nicht_mehr():
    """Die Handlung steht im Tooltip, nicht in der Breite."""
    programm = _ohne_kommentare(KOMPONENTE.read_text(encoding="utf-8"))
    # Im Template steht nur das Symbol.
    template = programm.split("</template>")[0]
    assert "füllen<" not in template and "ersetzen<" not in template, (
        "Der sichtbare Knopftext ist zurück — damit wechselt die Breite wieder")
    assert ">⚙<" in template


def test_die_handlung_bleibt_lesbar():
    """Ohne sichtbaren Text müssen Tooltip UND aria-label sie nennen.

    Der alte Knopf hatte kein eigenes ``aria-label``; für einen Screenreader
    war er nur „⚙“. Ein Symbolknopf ohne Beschriftung wäre hier also eine
    Verschlechterung — deshalb gehört beides dazu.
    """
    programm = _ohne_kommentare(KOMPONENTE.read_text(encoding="utf-8"))
    assert ":title=" in programm and ":aria-label=" in programm
    assert "ersetzen" in programm and "füllen" in programm, (
        "Der Unterschied zwischen Füllen und Ersetzen muss benannt bleiben — "
        "ein gefülltes Feld wird überschrieben (#1769/#1773)")


def test_ersetzen_ist_sichtbar_unterschieden():
    """Nicht durch mehr Text, sondern durch die Farbe."""
    programm = _ohne_kommentare(KOMPONENTE.read_text(encoding="utf-8"))
    assert re.search(r"\.knopf\.ersetzt\s*\{", programm), (
        "Ein Klick, der eine Eingabe überschreibt, muss sich vom Füllen "
        "unterscheiden")


def test_der_knopf_hat_einen_hover_zustand():
    """Fehlte ganz — ein Knopf ohne Rückmeldung sieht aus wie ein Symbol."""
    programm = _ohne_kommentare(KOMPONENTE.read_text(encoding="utf-8"))
    assert ".knopf:hover" in programm
    assert ".knopf:focus-visible" in programm, (
        "Tastaturbedienung braucht einen sichtbaren Fokus")
