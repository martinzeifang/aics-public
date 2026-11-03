"""#1945 — handgebaute Dialoge dürfen nicht mehr werden.

Meldung aus dem Betrieb: *„der Button custom ist komisch formatiert. die
felder gehen über die Grenzen hinaus."* Der Dialog „Neue Custom-Anforderung"
in ``CRAView.vue`` legte Überschrift, Felder und Knöpfe **direkt** in
``.modal-content`` — und dort steckt kein Innenabstand, der liegt in
``.modal-header``/``.modal-body``/``.modal-footer``. Dazu fehlte
``box-sizing: border-box``: Ohne globalen Reset rechnet der Browser
``100 % + 2×10px + 2×1px`` und das Feld steht über den Rand.

Der dritte, nicht gemeldete Defekt war der schlimmere: Ohne ``.modal-body``
gibt es kein ``overflow-y: auto``, während ``.modal-content`` auf
``max-height: 90vh`` begrenzt ist — auf einem flachen Fenster war „Anlegen"
nicht erreichbar.

**Warum dieser Wächter den Bestand nur einfriert.** ``ModalRahmen`` (#1849)
ist für neue Dialoge verbindlich, aber im Baum stehen 38 Dateien mit 54
handgebauten Dialogen. Eine Ausnahmeliste mit 38 Einzelbegründungen wird zum
Teppich, und ein Prüfer, dessen Ausgabe man nicht mehr liest, prüft nichts
(die Lehre aus #1805 und #1834). Deshalb: Die Zahl je Datei darf **sinken**,
nicht steigen, und eine neue Datei mit eigenem Overlay fällt durch. Muster ist
das eingefrorene Routen-Inventar aus #1846.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_WURZEL = Path(__file__).resolve().parents[1]
_FRONTEND = _WURZEL / "frontend" / "src"
_BESTAND = Path(__file__).parent / "data" / "handgebaute_modale_vor_1945.json"

_OVERLAY = re.compile(r'class="modal-overlay"')


def _ohne_kommentare(text: str) -> str:
    """HTML- und Blockkommentare weg.

    Zweimal in diesem Haus hat ein Wächter auf einen **Kommentar** angeschlagen,
    der den alten Zustand zitierte (#1834, #1867, #1903). Geprüft wird das
    Programm, nicht die Erzählung.
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _erhebung() -> dict[str, int]:
    gefunden: dict[str, int] = {}
    for datei in sorted(_FRONTEND.rglob("*.vue")):
        treffer = len(_OVERLAY.findall(_ohne_kommentare(datei.read_text(encoding="utf-8"))))
        if treffer:
            gefunden[str(datei.relative_to(_FRONTEND))] = treffer
    return gefunden


def _eingefroren() -> dict[str, int]:
    return json.loads(_BESTAND.read_text(encoding="utf-8"))["dateien"]


@pytest.mark.skipif(not _FRONTEND.is_dir(), reason="Frontend-Baum nicht vorhanden")
def test_kein_neuer_handgebauter_dialog() -> None:
    jetzt, vorher = _erhebung(), _eingefroren()

    neu = sorted(set(jetzt) - set(vorher))
    assert not neu, (
        "Neue Datei mit handgebautem `class=\"modal-overlay\"`: "
        + ", ".join(neu)
        + ". Für neue Dialoge gilt `components/shared/ModalRahmen.vue` (#1849) — "
        "dort steht `position: fixed` an genau einer Stelle, dazu Innenabstand, "
        "Rollbereich, Escape, Fokusfalle und die z-index-Stufe je Ebene. "
        "Jede eigene Kopie ist eine Gelegenheit, einen Baustein zu vergessen; "
        "#1535 und #1945 sind die Belege."
    )

    gewachsen = {d: (vorher[d], jetzt[d]) for d in jetzt if jetzt[d] > vorher.get(d, 0)}
    assert not gewachsen, (
        "Zusätzliche handgebaute Dialoge in bestehenden Dateien: "
        + "; ".join(f"{d}: {alt} → {neu_}" for d, (alt, neu_) in sorted(gewachsen.items()))
        + ". Der Bestand darf schrumpfen, nicht wachsen."
    )


@pytest.mark.skipif(not _FRONTEND.is_dir(), reason="Frontend-Baum nicht vorhanden")
def test_bestandsliste_ist_nicht_veraltet() -> None:
    """Verschwundene Dateien gehören aus der Liste — sonst verdeckt sie Fortschritt.

    Anders als bei #1846 ist Schrumpfen hier ausdrücklich erwünscht. Eine
    Bestandsliste, die längst umgestellte Dateien weiter aufführt, erlaubt
    stillschweigend einen neuen Dialog an deren Stelle.
    """
    jetzt, vorher = _erhebung(), _eingefroren()
    veraltet = sorted(d for d in vorher if d not in jetzt)
    assert not veraltet, (
        "Diese Dateien haben keinen handgebauten Dialog mehr und gehören aus "
        f"{_BESTAND.name}: " + ", ".join(veraltet)
    )
    gesunken = {d: (vorher[d], jetzt[d]) for d in jetzt if jetzt[d] < vorher[d]}
    assert not gesunken, (
        "Erfreulich, aber die Bestandsliste ist nachzuziehen: "
        + "; ".join(f"{d}: {alt} → {neu_}" for d, (alt, neu_) in sorted(gesunken.items()))
    )


@pytest.mark.skipif(not _FRONTEND.is_dir(), reason="Frontend-Baum nicht vorhanden")
def test_custom_dialog_hat_kopf_koerper_fuss() -> None:
    """Der gemeldete Dialog selbst — Innenabstand und Rollbereich.

    Geprüft wird der Abschnitt zwischen `customDialogOpen` und dem Ende des
    Dialogs, nicht die ganze Datei: Die beiden Nachbardialoge waren von Anfang
    an richtig und würden die Prüfung sonst bestehen lassen.
    """
    quelle = _ohne_kommentare((_FRONTEND / "views" / "cra" / "CRAView.vue")
                              .read_text(encoding="utf-8"))
    start = quelle.index('v-if="customDialogOpen"')
    abschnitt = quelle[start:start + 2600]
    for baustein in ("modal-header", "modal-body", "modal-footer"):
        assert f'class="{baustein}"' in abschnitt, (
            f"Dem Custom-Dialog fehlt `{baustein}`. Der Innenabstand steckt in "
            "diesen Bausteinen (`.modal-content` hat keinen), und `.modal-body` "
            "bringt den Rollbereich — ohne ihn wird der Inhalt an "
            "`max-height: 90vh` abgeschnitten und „Anlegen\" ist nicht erreichbar."
        )


@pytest.mark.skipif(not _FRONTEND.is_dir(), reason="Frontend-Baum nicht vorhanden")
def test_formularfelder_rechnen_mit_border_box() -> None:
    """Es gibt keinen globalen Reset — also muss die Regel dort stehen."""
    quelle = (_FRONTEND / "views" / "cra" / "CRAView.vue").read_text(encoding="utf-8")
    regel = re.search(r"\.form-row input,.*?\}", quelle, flags=re.S)
    assert regel, ".form-row-Feldregel in CRAView.vue nicht gefunden"
    assert "box-sizing: border-box" in regel.group(0), (
        "Den Feldern in `.form-row` fehlt `box-sizing: border-box`. Ohne "
        "globalen Reset ergibt `width: 100%` plus Innenabstand plus Rahmen "
        "100 % + 22 px — das Feld steht über den Rand hinaus (#1945)."
    )
