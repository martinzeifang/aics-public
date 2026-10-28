"""Das Feld für eigene Hinweise in jeder KI-Maske (#1834).

Die Verdrahtung steht in einer *anderen* Datei als der Knopf — deshalb ist das
eine Testaufgabe und keine Frage der Sorgfalt (die Lehre aus #1731 und #1805).
Fehlt das Feld, schlägt nichts fehl: Es fehlt bloß die Möglichkeit, und niemand
sucht nach etwas, das er nicht kennt.

Die Regel: Jede Komponente, die eine ``KiStreamView`` **selbst** einbindet,
führt entweder ``PromptZusatzFeld`` oder steht in :data:`WARTET` — mit Grund.
Wer nur ``WizardPromptModal``, ``AutoBewertungDialog``,
``AutoMassBewertungModal`` oder ``MassAssessmentModal`` benutzt, erbt das Feld
und braucht nichts zu tun.

:data:`WARTET` ist bewusst **keine** Ausnahmeliste, sondern eine Warteliste:
Die Bestandsaufnahme #1836 hat 30 Eigenbau-Masken gefunden, die eigenen
Transport, eigene Zustandsmaschinen und eigene Fehlerbehandlung mitbringen. Sie
jetzt einzeln zu verdrahten hieße, sie mit der gemeinsamen Engine (#1836/E4)
ein zweites Mal anzufassen. Die Liste schrumpft mit dieser Arbeit — ihre Länge
ist die Schuld, nicht die Erlaubnis.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "frontend" / "src"

#: Trägt das Feld und gibt es an seine Aufrufer weiter.
GETEILT = {
    "components/shared/WizardPromptModal.vue",
    "components/shared/AutoBewertungDialog.vue",
    "components/shared/AutoMassBewertungModal.vue",
    "components/shared/MassAssessmentModal.vue",
    "components/shared/ReportCenterPanel.vue",
    "components/shared/DocumentChecklistPanel.vue",
}

#: Eigenbau-Masken, die noch kein Feld haben — mit Grund.
#:
#: **Leer seit #1836/E6.** Die elf Einträge von #1834 sind verdrahtet, nachdem
#: die Engine stand: Sie vorher einzeln anzufassen hätte bedeutet, sie mit der
#: Engine ein zweites Mal anzufassen. Die Liste bleibt als Mechanismus
#: bestehen — ein Eintrag braucht einen Grund, sonst wird sie zum Teppich
#: (die Lehre aus #1805).
WARTET: dict[str, str] = {}


def _vue_dateien() -> list[Path]:
    return sorted(SRC.rglob("*.vue"))


def _rel(p: Path) -> str:
    return p.relative_to(SRC).as_posix()


def _bindet_ein(text: str, komponente: str) -> bool:
    """Bindet der Quelltext die Komponente ein (Import **und** Template)?"""
    if not re.search(rf"\bimport\s+{komponente}\b", text):
        return False
    return bool(re.search(rf"<{komponente}\b", text))


def test_die_geteilten_bausteine_tragen_das_feld():
    """Hier liegt die Hebelwirkung — sie darf nicht still verloren gehen."""
    fehlend = []
    for rel in sorted(GETEILT):
        pfad = SRC / rel
        assert pfad.exists(), f"{rel} gibt es nicht mehr — Liste anpassen"
        if not _bindet_ein(pfad.read_text(encoding="utf-8"), "PromptZusatzFeld"):
            fehlend.append(rel)
    assert not fehlend, ("Diese geteilten Masken haben das Feld verloren: "
                         + ", ".join(fehlend))


def test_jede_ki_maske_hat_das_feld_oder_steht_auf_der_warteliste():
    """Eine neue KI-Maske fällt auf, statt lautlos ohne Feld zu bleiben."""
    offen = []
    for pfad in _vue_dateien():
        rel = _rel(pfad)
        if rel == "components/shared/KiStreamView.vue":
            continue  # die Ansicht selbst, keine Maske
        text = pfad.read_text(encoding="utf-8")
        if not _bindet_ein(text, "KiStreamView"):
            continue
        if _bindet_ein(text, "PromptZusatzFeld") or rel in WARTET:
            continue
        offen.append(rel)
    assert not offen, (
        "Diese Masken binden KiStreamView ein, bieten aber kein Feld für eigene "
        "Hinweise und stehen auch nicht auf der Warteliste: " + ", ".join(offen)
        + " — entweder PromptZusatzFeld einbinden oder in WARTET mit Grund "
          "aufnehmen.")


def test_die_warteliste_nennt_nur_echte_dateien_mit_grund():
    """Eine Warteliste mit Leichen darin verschleiert den Stand."""
    for rel, grund in WARTET.items():
        assert (SRC / rel).exists(), f"{rel} gibt es nicht mehr — aus WARTET entfernen"
        assert len(grund) >= 20, f"{rel}: Grund zu knapp — „{grund}“"


def test_die_warteliste_bleibt_leer():
    """Sie war elf Einträge lang und ist seit #1836/E6 leer.

    Ein neuer Eintrag ist keine Ausnahme, sondern Schuld — und braucht einen
    Grund, sonst wird die Liste zum Teppich (#1805).
    """
    assert len(WARTET) == 0, (
        f"Die Warteliste ist auf {len(WARTET)} gewachsen: "
        + ", ".join(WARTET) + " — das Feld gehört in die Maske, nicht auf die Liste.")


# ── Der Fehler, der mir hier dreimal passiert ist ──────────────────────────

_BINDUNG = re.compile(r':(?:projekt|hinweis-projekt)="([A-Za-z_$][\w.$]*)"')


def test_die_projekt_bezeichner_gibt_es_wirklich():
    """Ein unbekannter Bezeichner im Template ist zur Laufzeit `undefined`.

    Vue meldet das nicht, `vue-tsc` beanstandet es nicht und der Build läuft
    durch — genau #1830. Beim Verdrahten von `PromptZusatzFeld` habe ich
    dreimal `projektName` geschrieben, wo die Maske `store.selectedProjekt`
    führt: Das Feld hätte still keine Projekt-Hinweise geladen, und niemand
    hätte es gemerkt, weil ein fehlender Hinweis kein Fehler ist.
    """
    fehler = []
    for pfad in _vue_dateien():
        text = pfad.read_text(encoding="utf-8")
        if "PromptZusatzFeld" not in text and "WizardPromptModal" not in text:
            continue
        teile = text.split("<script")
        if len(teile) < 2:
            continue
        template, script = teile[0], "<script".join(teile[1:])
        for bezeichner in set(_BINDUNG.findall(template)):
            wurzel = bezeichner.split(".")[0]
            if wurzel in ("$props", "props"):
                continue
            if not re.search(rf"\b{re.escape(wurzel)}\b", script):
                fehler.append(f"{_rel(pfad)}: {bezeichner}")
    assert not fehler, (
        "Diese Projekt-Bindungen verweisen auf Bezeichner, die im Script "
        "nicht vorkommen — sie wären zur Laufzeit `undefined`: "
        + ", ".join(sorted(fehler)))


def test_das_feld_setzt_nicht_selbst_zusammen():
    """Zusammengesetzt wird serverseitig — sonst zwei Wahrheiten (#1727/#1735).

    Geprüft wird der **Code**, nicht der Text: Der erste Anlauf suchte das Wort
    „komponiere" und fand es im eigenen Kommentar. Dieselbe Falle wie beim
    Quelltext-Wächter in #1833 — ein Prüfer, der auf Kommentare anspringt,
    prüft die Erzählung und nicht das Programm.
    """
    text = (SRC / "components/shared/PromptZusatzFeld.vue").read_text(encoding="utf-8")
    # Das Feld lädt seit #1835 seinen eigenen Vorbelegungstext — aber es baut
    # keinen Prompt. Geprüft wird genau das: keine Zusammenbau-Stelle im
    # Frontend, kein Aufruf des Komponier-Endpunkts.
    assert "/ai/prompt" not in text
    assert "prompt-hinweise" in text, "Vorbelegung aus #1835 fehlt"

    from shared.prompt_zusatz import MARKER, MARKER_VORRANG
    assert MARKER.lstrip("# ") not in text
    assert MARKER_VORRANG.lstrip("# ") not in text
    # Der Hinweis auf die Grenze steht AM Feld, nicht in einer Hilfeseite.
    assert "unverändert" in text


def test_die_grenze_im_feld_passt_zum_server():
    """Zwei Zahlen für dieselbe Grenze wären die nächste Spiegel-Liste."""
    from shared.prompt_zusatz import GRENZE
    text = (SRC / "components/shared/PromptZusatzFeld.vue").read_text(encoding="utf-8")
    m = re.search(r"grenze\?: number.*?grenze: (\d+)", text, re.S)
    assert m, "Vorgabewert der Grenze nicht gefunden"
    assert int(m.group(1)) == GRENZE


@pytest.mark.parametrize("rel", sorted(GETEILT))
def test_der_hinweis_reist_mit(rel: str):
    """Ein Feld, dessen Inhalt nirgends mitgeschickt wird, ist Dekoration."""
    text = (SRC / rel).read_text(encoding="utf-8")
    assert "prompt_zusatz" in text, (
        f"{rel} zeigt das Feld, schickt den Hinweis aber nicht mit "
        "(Body des Streams oder /ai/prompt/komponieren).")
