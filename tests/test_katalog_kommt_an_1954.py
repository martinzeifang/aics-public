"""Die Katalog-Übersetzung muss im Dokument ankommen (#1954, Klasse #1735).

DER BEFUND, DER DAS NÖTIG MACHT
Mit #1954 tragen die Anforderungskataloge `titel_en`, `beschreibung_en`,
`label_en` und `referenz_en`. Mehrere Berichts-Renderer lesen die Kataloge
aber als **Modul-Literale** und greifen direkt auf `req["titel"]` oder
`binfo["label"]` zu — dort kommt die englische Fassung nie an. Die
Übersetzung war vorhanden und wirkungslos, in vier Dateien:

* `dsgvo/report_export.py` — im englischen Gesamtbericht blieben 64 Zeilen
  deutsch,
* `cra/report_export.py` — nur 79 von 467 Textstellen wechselten die Sprache,
* `ai_act/berichte_provider.py`, `nis2/report_export.py`,
  `cra/konformitaet_report.py` — dasselbe.

Das ist **genau** der Defekt aus #1735: Dort wirkte die hochgeladene
Word-Vorlage nur im Test-Export des Admin-UI, weil das Berichts-Center
`render()` ohne Vorlagen-Parameter rief. Nichts schlug fehl, es passierte
nur nicht.

WARUM EIN PRÜFER UND NICHT SORGFALT
Die Verbindung zwischen „Katalog trägt eine Übersetzung" und „Renderer
benutzt sie" steht nirgends im Code. Sie ist eine Absprache zwischen zwei
Dateien, die niemand gemeinsam liest — und der nächste Renderer, der ein
Katalog-Literal liest, wird sie wieder nicht kennen.

WAS HIER **NICHT** GEPRÜFT WIRD
Nicht, ob die Übersetzung gut ist, und nicht, ob jeder Satz umgestellt
wurde. Geprüft wird genau der Zusammenhang, der hier gefehlt hat: Liest eine
Datei ein Katalog-Literal **und** erzeugt sie ein Dokument, dann muss sie
`shared.katalog_sprache` benutzen.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Die Katalog-Literale, deren Einträge eine Sprachfassung tragen können.
LITERALE = (
    "CRA_ANFORDERUNGEN", "NIS2_ANFORDERUNGEN", "DSGVO_ANFORDERUNGEN",
    "AI_ACT_REQUIREMENTS", "KAPITEL", "BEWERTUNG_SKALA", "PRODUKTKLASSEN",
    "EINRICHTUNGSKLASSEN", "ORGANISATIONSTYPEN", "OWASP_PC_V3",
    "OWASP_LLM_TOP10",
)

#: Woran eine Datei als Renderer oder Auslieferer erkannt wird.
ERZEUGT = re.compile(r"add_heading|add_paragraph|ReportSpec|build_docx|"
                     r"export_report|export_docx|export_markdown")

#: Verzeichnisse, die außen vor bleiben — je mit Grund.
AUSSEN: dict[str, str] = {
    "tests/": "Tests prüfen Dokumente, sie liefern keine aus.",
    "frontend/": "Kein Python-Renderer; die Oberfläche hat ihren eigenen Sprachkatalog.",
    ".claude/": "Arbeitskopien der Agenten (worktrees), nicht das Produkt.",
    "vcs/": "Issue-Anbindung an GitHub/GitLab, erzeugt kein Dokument.",
    "tools/": "Werkzeuge außerhalb des Images (E2E, Wiki-Generator).",
    "scripts/": "Betriebsskripte; sie werden nicht ins Image kopiert.",
}

#: Begründete Ausnahmen. Ohne Grund wäre die Liste ein Teppich (#1851).
ERLAUBT: dict[str, str] = {
    "gutachten/gerichtsgutachten_gen.py":
        "Ein Gerichtsgutachten wird bei einem deutschen Gericht nach "
        "§ 406/§ 407a ZPO eingereicht; eine englische Fassung wäre dort nicht "
        "verwendbar. Siehe NICHT_UMSCHALTBAR in test_berichtstexte_1954.",
    "gutachten/gutachten_gen.py":
        "Derselbe Grund — der Renderer teilt Aufbau und Formeln mit dem "
        "Gerichtsgutachten.",
    "server/services/reports.py":
        "Führt eine **eigene** Skala (lokale Liste mit wert/label/farbe_hex), "
        "nicht den Modul-Katalog. `score_label` und `score_color_hex` haben "
        "im ganzen Baum keinen Aufrufer — toter Code, und eine Übersetzung "
        "dort wäre toter Inhalt.",
}


def _dateien() -> list[Path]:
    out: list[Path] = []
    for p in sorted(WURZEL.rglob("*.py")):
        rel = str(p.relative_to(WURZEL))
        if any(rel.startswith(a) for a in AUSSEN):
            continue
        # Tkinter-Oberflächen und -Panels liefern keine Dokumente aus.
        if "gui_module" in rel or "/_panel" in rel or rel.startswith("_panel"):
            continue
        out.append(p)
    return out


def test_jeder_renderer_mit_katalog_uebersetzt_ihn():
    verstoesse: list[str] = []
    for p in _dateien():
        rel = str(p.relative_to(WURZEL))
        if rel in ERLAUBT:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if not ERZEUGT.search(txt):
            continue
        # Nur echte Zugriffe, nicht der Import und nicht eine Erwähnung im
        # Kommentar: `KAPITEL[...]`, `KAPITEL.items()`, `in KAPITEL`.
        ohne_kommentar = "\n".join(
            z for z in txt.split("\n") if not z.lstrip().startswith("#"))
        nutzt = [L for L in LITERALE
                 if re.search(rf"\b{L}\b\s*[\[.(]|\bin\s+{L}\b",
                              ohne_kommentar)]
        if not nutzt:
            continue
        if "katalog_sprache" in txt:
            continue
        verstoesse.append(f"{rel}: liest {nutzt} ohne shared.katalog_sprache")
    assert not verstoesse, (
        "Die Katalog-Übersetzung kommt dort nicht an — sie ist vorhanden und "
        "wirkungslos (Klasse #1735):\n  " + "\n  ".join(verstoesse))


def test_die_ausnahmen_tragen_eine_begruendung():
    """Eine Ausnahme ohne Grund ist ein Teppich, kein Befund (#1851)."""
    for liste, name in ((ERLAUBT, "ERLAUBT"), (AUSSEN, "AUSSEN")):
        for stelle, grund in liste.items():
            assert len(grund) >= 30, \
                f"{name}[{stelle}]: Grund zu knapp — {grund!r}"


def test_die_ausnahmen_gibt_es_noch():
    """Eine Ausnahme für eine gelöschte Datei verdeckt die nächste."""
    fehlt = [s for s in ERLAUBT if not (WURZEL / s).exists()]
    assert not fehlt, f"Ausnahme für nicht vorhandene Dateien: {fehlt}"


def test_uebersetze_laesst_das_literal_unberuehrt():
    """Die Kopie ist der Grund, warum der Helfer so aussieht.

    Die Kataloge sind Modul-Literale und werden von mehreren Anfragen
    gleichzeitig gelesen. Sie an Ort und Stelle zu ändern wäre ein
    Datenrennen, das sich als sprunghaft falsche Sprache zeigt — und das
    fällt im Betrieb erst auf, wenn ein Anwender es meldet.
    """
    from shared import katalog_sprache as ks

    eintrag = {"id": "X", "titel": "deutsch", "titel_en": "english"}
    kopie = ks.uebersetze(eintrag, "en")
    assert kopie["titel"] == "english"
    assert eintrag["titel"] == "deutsch", "das Literal wurde verändert"
    assert kopie is not eintrag
