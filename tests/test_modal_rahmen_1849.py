"""Ein Modal-Gerüst — die Wiederholungssperre für #1535 (#1849).

DER BEFUND, DER DAS AUSGELÖST HAT
``MassAssessmentModal`` stylte nur ``.mass-modal``, nicht ``.modal-overlay``.
Vue-Styles sind ``scoped``, ein globales Overlay-CSS gibt es in diesem Repo
nicht — das ``<Teleport to="body">``-Overlay hatte also kein
``position: fixed`` und landete unsichtbar am Seitenende. Das Modal war da,
nur nicht zu sehen; für den Anwender ein Knopf ohne Wirkung, der keiner war.

**Dieser Defekt ist nicht durch Sorgfalt vermeidbar.** Die Ursache (fehlendes
Overlay-CSS) liegt in einer anderen Datei als der Fehler (der Knopf, der
scheinbar nichts tut) — dieselbe Klasse wie #1731 und #1805. Solange jedes
Modal sein Overlay selbst stylt, ist er reproduzierbar. Deshalb ist die
Wiederholungssperre der eigentliche Zweck dieses Schritts, nicht die Optik.

Der Bestand kannte **zwölf** Klassennamen für dasselbe Gerüst, und ``Teleport``
nutzten 5 von 17 KI-Overlays. Umgebaut werden nur die KI- und Issue-Masken aus
#1847/#1848 — ein repoweiter Austausch über 58 Vorkommen wäre ein eigenes
Vorhaben mit eigenem Risiko; ``sidebar-overlay``, ``help-overlay`` und
``reauth-overlay`` haben andere Anforderungen und bleiben.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
SRC = WURZEL / "frontend" / "src"
RAHMEN = SRC / "components" / "shared" / "ModalRahmen.vue"

#: Die Bausteine aus #1847/#1848/#1851 — sie müssen den Rahmen benutzen.
MIT_RAHMEN = [
    "components/shared/IssueVerknuepfung.vue",
    "components/shared/KiBewertungsBlock.vue",
    "components/shared/AuditLogModal.vue",
    "components/shared/IssueNeubewertungModal.vue",
]


def _text(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def _ohne_kommentare(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return "\n".join(z for z in text.split("\n")
                     if not z.lstrip().startswith(("//", "*", "/*")))


def test_der_rahmen_teleportiert_immer():
    """`Teleport` ist nicht optional — genau das war #1535."""
    code = _ohne_kommentare(RAHMEN.read_text(encoding="utf-8"))
    assert '<Teleport to="body">' in code
    # Kein `v-if` am Teleport: Ein abschaltbarer Teleport ist ein Teleport,
    # den jemand abschaltet.
    assert "<Teleport to=\"body\" v-if" not in code


def test_der_rahmen_bringt_sein_overlay_css_mit():
    """`position: fixed` steht im Rahmen und nirgends sonst."""
    code = RAHMEN.read_text(encoding="utf-8")
    stil = code[code.index("<style"):]
    assert ".mr-overlay" in stil
    overlay = stil.split(".mr-overlay")[1].split("}")[0]
    assert "position: fixed" in overlay, (
        "Ohne `position: fixed` landet das teleportierte Overlay am "
        "Seitenende — das war #1535.")
    assert "inset: 0" in overlay


def test_der_rahmen_schliesst_mit_escape_und_setzt_den_fokus():
    code = _ohne_kommentare(RAHMEN.read_text(encoding="utf-8"))
    assert "'Escape'" in code, "Escape schließt nicht"
    assert "dialog.value?.focus()" in code, "Der Fokus wandert nicht in den Dialog"
    assert "vorherFokussiert?.focus()" in code, "Der Fokus kommt nicht zurück"
    assert 'aria-modal="true"' in code
    assert 'role="dialog"' in code


def test_verschachtelte_dialoge_bekommen_je_eine_stufe():
    """Prompt-Modal über Bewertungs-Modal ist der Normalfall.

    Eine z-index-**Stufe** je Ebene, nicht drei Overlays auf 1000. Und Escape
    schließt nur die oberste — sonst nimmt ein Tastendruck dem Anwender den
    ganzen Stapel samt seiner Eingabe.
    """
    code = _ohne_kommentare(RAHMEN.read_text(encoding="utf-8"))
    assert "1100 + ebene.value * 100" in code, "z-index folgt der Ebene nicht"
    assert "ebene.value === _offen" in code, (
        "Escape muss auf die oberste Ebene beschränkt sein.")


@pytest.mark.parametrize("rel", MIT_RAHMEN)
def test_die_neuen_bausteine_nutzen_den_rahmen(rel: str):
    code = _ohne_kommentare(_text(rel))
    assert "ModalRahmen" in code, f"{rel}: eigenes Modal-Gerüst statt des Rahmens"
    assert "modal-overlay" not in code, (
        f"{rel}: baut wieder ein eigenes Overlay — der Rahmen bringt es mit.")


@pytest.mark.parametrize("rel", MIT_RAHMEN)
def test_kein_eigenes_overlay_css_in_den_bausteinen(rel: str):
    """Ein eigenes `position: fixed` ist der Anfang der zwölf Klassennamen."""
    text = _text(rel)
    if "<style" not in text:
        return
    stil = text[text.index("<style"):]
    assert "position: fixed" not in stil, (
        f"{rel}: eigenes Overlay-CSS. Der Rahmen stellt es; zwei Quellen "
        "dafür sind der Weg zurück zu #1535.")


def test_der_rahmen_wird_wirklich_benutzt():
    """Ein Rahmen ohne Einbindungen ist ein Vorschlag, keine Sperre."""
    nutzer = [p for p in SRC.rglob("*.vue")
              if "ModalRahmen" in p.read_text(encoding="utf-8")
              and p.name != "ModalRahmen.vue"]
    assert len(nutzer) >= 4, (
        f"Nur {len(nutzer)} Einbindungen — der Rahmen soll die Masken aus "
        "#1847/#1848 tragen.")
