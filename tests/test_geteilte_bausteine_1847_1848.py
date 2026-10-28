"""Issue-Verknüpfung und KI-Bewertung kommen aus **einem** Baustein (#1847/#1848).

~350 Zeilen Issue-Bedienung lagen in fünf Masken, der KI-Baustein war für vier
Module geteilt und dreimal nachgebaut. Was dabei auseinanderlief, war nicht nur
die Beschriftung, sondern die **Funktion**:

- OWASP-LLM und WiBA hatten kein ``DataPreviewWarning``. Damit lief der
  eingebaute Knopf „⚡ Direkt mit KI ausführen" dort **ohne**
  Egress-Bestätigung — die Lücke, die #1840 im Server geschlossen hat, auf der
  Seite der Maske wieder offen.
- Beide setzten ``hinweis-modul``/``hinweis-projekt`` am ``WizardPromptModal``
  nicht. Das eingebaute Hinweis-Feld (#1834) lief mit leerem Modul, also wurden
  die **gespeicherten** Projekt-Hinweise (#1835) nie geladen. Das Feld war da
  und tat nichts — die Fehlerklasse aus #1830.
- Der RisikoEditor zeigte die Markierung „⚠️ Neubewertung erforderlich" nicht
  an und verlinkte Issue-URLs **ohne** ``safeUrl``.

Dieser Test hält fest, dass es dabei bleibt. Er prüft das Programm, nicht die
Erzählung (die Lehre aus #1833): Kommentare werden vor dem Prüfen entfernt.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
SRC = WURZEL / "frontend" / "src"

ISSUE_BAUSTEIN = "components/shared/IssueVerknuepfung.vue"
KI_BAUSTEIN = "components/shared/KiBewertungsBlock.vue"

#: Die fünf Masken mit Issue-Bedienung am Objekt — und was sie dort pflegen.
ISSUE_MASKEN = {
    "components/shared/RequirementActions.vue": "anforderungen",
    "views/aiact/OwaspLlmPanel.vue": "owasp-llm",
    "views/wiba/PrueffragenPanel.vue": "controls",
    "views/risikobewertung/RisikoEditor.vue": "risiken",
    "views/cra/PflichtDokuPanel.vue": "vulns",
}

#: Die Masken mit KI-Bewertung am Objekt. ``PflichtDokuPanel`` fehlt hier
#: bewusst: Diese Maske hat **keinen** KI-Pfad — die Wizards liegen seit
#: #1081 im Assistenten-Tab, und sie zeigt nur Issues an Risiko- und
#: Schwachstellenzeilen.
KI_MASKEN = {
    "components/shared/RequirementActions.vue",
    "views/aiact/OwaspLlmPanel.vue",
    "views/wiba/PrueffragenPanel.vue",
    "views/risikobewertung/RisikoEditor.vue",
}

#: Wer Issue-Endpunkte selbst aufrufen darf — je mit Grund.
EIGENE_AUFRUFE_ERLAUBT = {
    ISSUE_BAUSTEIN:
        "Der Baustein selbst. Hier stehen die Aufrufe, genau darum geht es.",
    "components/shared/ProjektWerkzeugleiste.vue":
        "Die projektweiten Handlungen (`issues/bulk|sync|import`) sind eine "
        "andere Ebene — sie gelten dem Projekt, nicht einem Objekt (#1851).",
    "components/shared/IssueNeubewertungModal.vue":
        "Lesende Übersicht über `issues/neubewertung`; schreibt nichts und "
        "gehört zur Werkzeugleiste.",
    "views/admin/IssueOverviewView.vue":
        "Administrationsansicht über alle Module; ein Wartungslauf, keine "
        "Bedienung am einzelnen Objekt.",
}


def _code(rel: str) -> str:
    """Datei ohne Kommentare — Wächter prüfen das Programm (#1833)."""
    text = (SRC / rel).read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return "\n".join(z for z in text.split("\n")
                     if not z.lstrip().startswith(("//", "*", "/*")))


# ── #1847: ein Issue-Baustein ───────────────────────────────────────────────

@pytest.mark.parametrize("rel,pfad", sorted(ISSUE_MASKEN.items()))
def test_jede_maske_nutzt_den_issue_baustein(rel: str, pfad: str):
    code = _code(rel)
    assert "IssueVerknuepfung" in code, (
        f"{rel}: baut die Issue-Bedienung wieder selbst — der Baustein steht "
        f"in {ISSUE_BAUSTEIN}.")
    # `RequirementActions` bedient zwei Objektarten (Anforderung und
    # OWASP-Kontrolle) und bindet den Pfad deshalb berechnet. Geprüft wird
    # dort, dass die Berechnung beide Werte der Fabrik kennt.
    if ":objekt-pfad=" in code:
        assert f"'{pfad}'" in code, (
            f"{rel}: der berechnete Objekt-Pfad kennt „{pfad}“ nicht (#1846).")
    else:
        assert f'objekt-pfad="{pfad}"' in code, (
            f"{rel}: erwartet die Objektart „{pfad}“ aus der Fabrik (#1846).")


def test_niemand_ruft_die_issue_endpunkte_selbst():
    """Eine Maske mit eigenem Aufruf ist die nächste abweichende Fassung."""
    muster = re.compile(r"/(issues|import-issue)(/|'|`|\")")
    verstoesse: list[str] = []
    for pfad in sorted(SRC.rglob("*.vue")):
        rel = str(pfad.relative_to(SRC))
        if rel in EIGENE_AUFRUFE_ERLAUBT:
            continue
        code = _code(rel)
        for zeile in code.splitlines():
            if ("apiClient" in zeile or "api.post" in zeile or "api.get" in zeile
                    or "api.delete" in zeile) and muster.search(zeile):
                verstoesse.append(f"{rel}: {zeile.strip()[:90]}")
    assert not verstoesse, (
        "Issue-Endpunkte außerhalb der geteilten Bausteine:\n  "
        + "\n  ".join(verstoesse))


def test_die_warteliste_traegt_gruende():
    for rel, grund in EIGENE_AUFRUFE_ERLAUBT.items():
        assert (SRC / rel).exists(), f"{rel} gibt es nicht (mehr)"
        assert len(grund) >= 40, f"{rel}: Grund zu knapp — „{grund}“"


def test_der_issue_baustein_kann_die_sechserform():
    """Alle sechs Handlungen der Fabrik sind bedienbar (#1846)."""
    code = _code(ISSUE_BAUSTEIN)
    for teil in ("/issues`", "/issues/link`", "/issues/sync`", "/import-issue`"):
        assert teil in code, f"{teil} wird nicht aufgerufen"
    assert "apiClient.delete" in code, "Entknüpfen fehlt"
    assert "safeUrl" in code, "Issue-Links ohne safeUrl (#1175)"


def test_das_anlegen_erzwingt_kein_repository():
    """Repo und Provider sind Überschreibungen, keine Pflichtfelder.

    Vier der fünf Masken legten ohne Repo an — der Server löst es aus der
    Projekt-Konfiguration auf (``shared.issue_api.loese_repo``). Ein
    Pflichtfeld hier nähme dieses Verhalten, und ein fest mitgesendetes
    ``provider: 'github'`` würde ein auf GitLab konfiguriertes Projekt
    überstimmen.
    """
    code = _code(ISSUE_BAUSTEIN)
    assert "anlegen.value.repo.trim() || undefined" in code, (
        "Leeres Repo muss **weggelassen** werden, nicht als leere "
        "Zeichenkette gesendet — sonst ist es ein Override auf „nichts“.")
    assert "anlegen.value.provider || undefined" in code
    assert "!anlegen.repo.trim() ||" not in code, (
        "Das Repository darf das Anlegen nicht sperren.")


# ── #1848: ein KI-Baustein ──────────────────────────────────────────────────

@pytest.mark.parametrize("rel", sorted(KI_MASKEN))
def test_jede_ki_maske_nutzt_den_geteilten_baustein(rel: str):
    code = _code(rel)
    assert "KiBewertungsBlock" in code, (
        f"{rel}: baut die KI-Bewertung wieder selbst. Damit fehlen ihr "
        f"Daten-Vorschau (#868), Egress-Tor (#1840) und die gespeicherten "
        f"Projekt-Hinweise (#1835) — alle drei fehlten in den Eigenbauten.")


def test_der_ki_baustein_traegt_vorschau_hinweis_und_tor():
    """Die drei Dinge, die in den Eigenbauten fehlten."""
    code = _code(KI_BAUSTEIN)
    assert "DataPreviewWarning" in code, "Daten-Vorschau fehlt (#868)"
    assert ':egress-vorbestaetigt="wizard.bestaetigt"' in code, (
        "Das Tor ist nicht verdrahtet — genau der Zustand aus #1840.")
    assert ':hinweis-modul="adapter.modul"' in code, (
        "Ohne Modul lädt das Hinweis-Feld die gespeicherten Hinweise nicht "
        "(#1835) — es wäre da und täte nichts (#1830).")
    assert ':hinweis-projekt="projektName"' in code
    assert "NeubewertungBadge" in code, "Markierung fehlt (#1850)"
    assert "KiHerkunftBadge" in code, "Herkunftsnachweis fehlt (#1765)"


def test_abgeschaltete_einstiege_sind_aus_und_nicht_kaputt():
    """Was es nicht gibt, wird nicht angezeigt — über einen **Schalter**.

    Zwei Fälle, beide nachgeprüft:

    * **OWASP-LLM** hat keinen Prompt je Kontrolle; der Wizard ist dort
      registerweit (``…/owasp-llm/wizard/prompt``).
    * Die **Risikobewertung** hat einen eigenen, reicheren Neubewertungs-Weg.
      Der gemeinsame schickte ``use_issue_feedback`` an ``ollama/stream``, und
      **dieser Endpunkt liest das Feld nicht** — der Knopf hätte gestartet,
      sauber durchgelaufen und das Feedback stillschweigend weggelassen.
    """
    quelle = (SRC / "utils" / "kiBewertung.ts").read_text(encoding="utf-8")
    owasp = quelle.split("export function owaspLlmKiAdapter")[1].split("export ")[0]
    assert "prompt: false" in owasp, (
        "OWASP-LLM hat keinen Prompt je Kontrolle — der Einstieg muss "
        "abgeschaltet sein, nicht ins 404 laufen (#1846).")
    risiko = quelle.split("export function risikoKiAdapter")[1]
    assert "neubewertung: false" in risiko, (
        "Die Risikobewertung bedient die Neubewertung selbst; der gemeinsame "
        "Weg wäre dort wirkungslos.")


def test_der_wertetyp_kommt_aus_dem_adapter():
    """WiBA zeigt ja/nein, die Risikobewertung den Risikowert."""
    quelle = (SRC / "utils" / "kiBewertung.ts").read_text(encoding="utf-8")
    assert "wertLabel: 'Antwort'" in quelle, "WiBA braucht „Antwort“"
    assert "wertLabel: 'Risiko'" in quelle, "Die RB braucht „Risiko“"
    assert "wertLabel: 'Bewertung'" in quelle, "Score-Module brauchen „Bewertung“"
    # Die Vorschau der Prüffrage nennt die **Antwort in Worten**, nicht den
    # Rohwert der Spalte — in der Vorschau steht, was der Anwender sieht.
    assert "WIBA_ANTWORT" in quelle
