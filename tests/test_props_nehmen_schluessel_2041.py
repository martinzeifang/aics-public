"""Geteilte Bausteine nehmen Schlüssel, keine fertigen Sätze (#2041).

DER BEFUND
----------
``ModuleDashboard`` nahm ``gesamtStats?: string[]`` — **fertige Sätze**. Damit
konnte die Komponente ihre eigene Übersetzung nicht durchsetzen, und alle
sechs Aufrufer hatten deutsche Literale hineingeschrieben. Mit ``en`` als
Anzeigesprache stand auf der **ersten Seite jedes Moduls**:
„Gesamt-Reifegrad", „142 / 180 Punkte", „36 Anforderungen · 10 OWASP",
„erstellt/freigegeben · 7 ausstehend", „3 kritisch · 8 hoch".

Dasselbe bei ``ProjektWerkzeugleiste``: ``objektWort``/``wertWort`` haben
übersetzte Vorgaben, und **alle sechs** Views überschrieben sie mit deutschen
Literalen. WiBA zeigte den Bruch in zwei benachbarten Zeilen
(``:objekt-wort="$t(…)"`` über ``wert-wort="Antworten"``).

Die Rückfrage vor „🐙 Issues anlegen" war in drei Bruchstücke geteilt, von
denen nur zwei im Katalog standen — sie **begann deutsch und endete
englisch**, und zwar bei der Handlung, die Tickets im Repository des Kunden
erzeugt und die „von hier niemand zurücknehmen" kann (#1851).

DER ENTWURFSFEHLER, UND WARUM #1954 IHN NICHT GEFUNDEN HAT
----------------------------------------------------------
Eine Komponente, die **Sätze** entgegennimmt, ist nicht umschaltbar. Der
Wächter aus #1954 prüft die Kataloge gegeneinander und die **benutzten**
Schlüssel — nicht Texte, die nie in einen Katalog gegangen sind. Genau diese
Lücke schließt dieser Test für die geteilten Bausteine.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.i18n_text import ohne_kommentare

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "frontend" / "src"
DASHBOARD = SRC / "components" / "shared" / "ModuleDashboard.vue"
LEISTE = SRC / "components" / "shared" / "ProjektWerkzeugleiste.vue"

#: Die Views, die ``ModuleDashboard`` mit Kennzahlen füllen.
VIEWS = (
    "views/cra/CRAView.vue",
    "views/nis2/NIS2View.vue",
    "views/aiact/AIActView.vue",
    "views/dsgvo/DSGVOView.vue",
    "views/wiba/WiBAView.vue",
    "views/compliance-audit/ComplianceAuditView.vue",
)


def _programm(pfad: Path) -> str:
    return ohne_kommentare(pfad.read_text(encoding="utf-8"))


def test_gesamt_stats_nimmt_schluessel():
    """``string[]`` ist der Entwurfsfehler selbst."""
    programm = _programm(DASHBOARD)
    assert "gesamtStats?: DashboardStat[]" in programm
    assert "gesamtStats?: string[]" not in programm
    assert "interface DashboardStat" in programm


def test_das_dashboard_uebersetzt_selbst():
    programm = _programm(DASHBOARD)
    # Der Kopf nennt keinen fertigen Satz mehr …
    assert 'label="Gesamt-Reifegrad"' not in programm
    # … und die Zeilen laufen durch $t
    assert re.search(r"\$t\(z\.key", programm)


def test_kein_deutscher_satz_mehr_in_den_stat_bauern():
    """Die sechs Aufrufer geben Schlüssel, keine Sätze.

    Geprüft wird auf die **Wörter**, die dort standen — nicht auf das Muster
    „Backtick mit Interpolation". Ein Aufrufer darf einen Backtick für eine
    URL benutzen; verboten ist der deutsche Anzeigetext.
    """
    verdaechtig = ("Punkte`", "Anforderungen`", "bewertet`", "Prüffragen",
                   "DSMS-Bereiche", "Fragen`", "erfüllt`", "teilweise`",
                   "nicht erfüllt`", "Abdeckung ")
    treffer: list[str] = []
    for rel in VIEWS:
        programm = _programm(SRC / rel)
        # nur der Block, der die Kennzahlen baut
        for name in ("dashboardStats", "dashStats"):
            m = re.search(rf"const {name} = computed", programm)
            if not m:
                continue
            block = programm[m.start():m.start() + 1200]
            for wort in verdaechtig:
                if wort in block:
                    treffer.append(f"{rel}: {wort!r}")
    assert not treffer, f"fertige Sätze im Kennzahlen-Bauer: {treffer}"


def test_die_stat_bauern_sind_typisiert():
    """``computed<DashboardStat[]>`` statt eines Casts.

    Ein ``as DashboardStat[]`` hätte den Typprüfer nur stumm gestellt; mit der
    Annotation beanstandet er einen falschen Schlüssel-Eintrag.
    """
    for rel in VIEWS:
        programm = _programm(SRC / rel)
        assert "computed<DashboardStat[]>" in programm, rel
        assert "as DashboardStat[]" not in programm, rel


def test_die_rueckfragen_sind_je_ein_schluessel():
    """Eine aus Bruchstücken zusammengesetzte Rückfrage bricht mitten im Satz.

    Sie stand vor der Handlung, die Issues im **Repository des Kunden**
    anlegt — der Ort, an dem ein halb verstandener Hinweis am teuersten ist.
    """
    programm = _programm(LEISTE)
    for schluessel in ("rueckfrageIssuesAnlegen", "rueckfrageAbgleichen",
                       "rueckfrageUebernehmen"):
        assert schluessel in programm, schluessel
    # Kein zusammengesetzter Rückfragetext mehr: kein `t(...)` + Literal
    assert "+ t('geteilt.projektWerkzeugleiste." not in programm


def test_die_wort_props_werden_nicht_mit_literalen_ueberschrieben():
    """Eine übersetzte Vorgabe, die jeder Aufrufer überschreibt, ist keine."""
    treffer: list[str] = []
    for pfad in sorted(SRC.rglob("*.vue")):
        programm = _programm(pfad)
        for m in re.finditer(r'(objekt-wort|wert-wort)="([^"$][^"]*)"', programm):
            treffer.append(f"{pfad.relative_to(SRC)}: {m.group(0)}")
    assert not treffer, f"deutsches Literal statt Schlüssel: {treffer}"


def test_leere_platzhalter_erscheinen_nicht_in_der_oberflaeche():
    """Der gelockerte Typ (``| undefined``) darf nichts aufreißen.

    TypeScript weist dem kürzeren Element eines Array-Literals ``v1?:
    undefined`` zu — „abwesend", nicht „Wert undefined". Der Typ lässt das
    deshalb zu, und ``saubereWerte`` wirft es vor dem Rendern weg; sonst
    stünde „undefined" in der Oberfläche.
    """
    programm = _programm(DASHBOARD)
    assert "saubereWerte" in programm
    assert "v !== undefined" in programm
