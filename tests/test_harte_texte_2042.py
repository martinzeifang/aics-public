"""Harte Anzeigetexte in der Oberfläche — #2042.

DIE LÜCKE IN DER PRÜFKETTE
Für #1954 („die Suite ist auf Englisch umschaltbar") gibt es zwei Wächter:
``test_i18n_katalog_1954`` hält die Kataloge gegeneinander,
``test_i18n_schluessel_1964`` prüft, dass jeder **benutzte** Schlüssel eine
Nachricht hat. Beide sind grün — und keiner prüft Texte, die **nie in den
Katalog gegangen sind**.

WARUM DIESER WÄCHTER ZWEI TEILE HAT
Der erste Anlauf war ein breiter Erkenner auf deutsche Wörter: **247
Fundstellen**, darunter Schlüsselnamen, CSS-Klassen und Variablen. Ein Prüfer,
dessen Ausgabe man nicht mehr liest, prüft nichts (#1805/#1834/#2090) — also
verengt:

1. **Mischformen** (``fehler``): ein Literal **gegenüber** einem
   Übersetzungsaufruf im selben Ternär. Das ist der sichtbare Defekt — in der
   englischen Oberfläche stand „✓ fulfilled" neben „offen". Davon gibt es
   **keine** mehr; rein symbolische Werte (``⏳ …``) sind sprachneutral und
   ausgenommen.
2. **Anzeigende Attribute** mit Literaltext (``rueckstand``): 93 Fundstellen in
   39 Dateien, überwiegend ``placeholder="z. B. …"``. Die sind unübersetzt, aber
   nicht defekt. Sie stehen hier als **Deckel je Datei**: Der Rückstand bleibt
   sichtbar, und die 94. Fundstelle fällt auf — auch in einer Datei, die schon
   welche hat.

Den Rückstand in einem Zug zu übersetzen wäre ein eigener Vorgang; ihn
unbeaufsichtigt zu lassen heißt, dass er wächst.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from tests.i18n_text import ohne_kommentare

WURZEL = pathlib.Path("frontend/src")

#: Ein Literal **hinter** einem Übersetzungsaufruf im selben Ternär — also der
#: ``else``-Zweig, der unübersetzt blieb.
#:
#: Die erste Fassung hatte einen zweiten Zweig (``'wert' : t(…)``) und meldete
#: damit 24 **Objektschlüssel** und Vergleichswerte (``'self-signed'``,
#: ``'risk-tier'``, ``'konfiguriert'``) — Bezeichner, keine Anzeigetexte. Ein
#: Wächter, dessen Ausgabe man nicht mehr liest, prüft nichts
#: (#1805/#1834/#2090), also ist der Zweig weg. Die Gegenrichtung
#: (``{ offen: 'offen' }``) fängt kein Regex sinnvoll; sie ist beim Lesen
#: aufgefallen und einzeln behoben.
MISCHFORM = re.compile(
    r"(?:\$?t|uebersetze)\(\s*['\"][\w.]+['\"][^)]*\)\s*:\s*'([^'\n]{2,60})'")

#: Attribute, deren Wert der Anwender liest.
ATTRIBUT = re.compile(r'(?<![:\w-])(title|placeholder|aria-label|alt)="([^"{}:]{3,})"')

#: Werte, die keine Anzeigetexte sind (Schlüssel, Codes, Zahlen, URLs).
HARMLOS = re.compile(r"^(?:[\w.-]+|[A-Z_]+|\d+|#[0-9a-f]+|https?://\S+)$")

#: Rein symbolische Werte — sprachneutral, also kein Fund.
SYMBOLISCH = re.compile(r"^[\s…⏳✓✔✘⚠️—.·…]+$")

#: Fachcodes, die in jeder Sprache so heißen.
FACHCODES = frozenset({"B+C", "A", "H", "B", "C"})

#: Dateien mit noch unübersetzten Attributtexten → **Höchstzahl**.
#: Gemessen am 09.11.2026. Wer eine Datei übersetzt, senkt die Zahl (oder nimmt
#: die Zeile heraus); wer eine neue Fundstelle einbaut, wird rot.
RUECKSTAND: dict[str, int] = {
    "components/SettingsDialog.vue": 1,
    "components/cra/KonformitaetserklaerungForm.vue": 2,
    "views/account/SecurityView.vue": 1,
    "views/admin/AdminGroupsView.vue": 1,
    "views/admin/AdminSettingsView.vue": 1,
    "views/admin/AdminTemplatesView.vue": 2,
    "views/admin/LicenseView.vue": 1,
    "views/admin/dialogs/CertCsrWizard.vue": 1,
    "views/aiact/AIActAssistentenTab.vue": 1,
    "views/aiact/AIActPflichtDokuPanel.vue": 6,
    "views/aiact/AIActView.vue": 1,
    "views/aiact/GpaiPanel.vue": 1,
    "views/compliance-audit/ComplianceAuditView.vue": 3,
    "views/cra/CRAView.vue": 1,
    "views/cra/KonformitaetPanel.vue": 3,
    "views/cra/KorrekturPanel.vue": 2,
    "views/cra/MarktueberwachungPanel.vue": 5,
    "views/cra/MeldungPanel.vue": 4,
    "views/cra/PflichtDokuPanel.vue": 1,
    "views/cra/ReleasesPanel.vue": 1,
    "views/cra/TraceabilityPanel.vue": 2,
    "views/dsgvo/BetroffenenrechtePanel.vue": 2,
    "views/dsgvo/DSGVOPflichtDokuPanel.vue": 4,
    "views/dsgvo/DSGVOView.vue": 1,
    "views/dsgvo/EinwilligungPanel.vue": 4,
    "views/dsgvo/KontrollenPanel.vue": 2,
    "views/dsgvo/LoeschkonzeptPanel.vue": 6,
    "views/dsgvo/TomKatalogPanel.vue": 2,
    "views/dsgvo/TransferPanel.vue": 4,
    "views/firmen/FirmenView.vue": 4,
    "views/firmen/PentestPanel.vue": 1,
    "views/firmen/dialogs/EvidenceURLDialog.vue": 2,
    "views/gutachten/GerichtsgutachtenView.vue": 6,
    "views/nis2/AssistentenPanel.vue": 1,
    "views/nis2/NIS2PflichtDokuPanel.vue": 7,
    "views/nis2/NIS2View.vue": 2,
    "views/risikobewertung/RisikoAssistent.vue": 2,
    "views/shared/DokumenteRegister.vue": 1,
    "views/wiba/WiBAView.vue": 1,
}


def _dateien() -> list[pathlib.Path]:
    return sorted(WURZEL.rglob("*.vue"))


#: Werte, die bei einer **Mischform** nicht zählen. Hier gilt ``HARMLOS``
#: ausdrücklich **nicht**: Ein einzelnes deutsches Wort ohne Leerzeichen —
#: ``'offen'`` — ist dort genau der Defekt, und ``[\w.-]+`` hätte es
#: weggefiltert. Das hat mein eigener Gegenbeweis-Test gefangen, bevor die
#: Zusage „keine Mischform" eine leere Behauptung wurde.
KEIN_ANZEIGETEXT = re.compile(r"^(?:[\w-]+(?:\.[\w-]+)+|\d+|#[0-9a-f]+|https?://\S+)$")


def _mischformen(pfad: pathlib.Path) -> list[str]:
    text = ohne_kommentare(pfad.read_text(encoding="utf-8"))
    aus: list[str] = []
    for m in MISCHFORM.finditer(text):
        wert = m.group(1) or ""
        if not wert or KEIN_ANZEIGETEXT.match(wert) or SYMBOLISCH.match(wert):
            continue
        if wert.strip() in FACHCODES:
            continue
        aus.append(wert)
    return aus


def _attribute(pfad: pathlib.Path) -> list[str]:
    kopf = ohne_kommentare(pfad.read_text(encoding="utf-8")).split("<script", 1)[0]
    return [f"{m.group(1)}={m.group(2)!r}" for m in ATTRIBUT.finditer(kopf)
            if not HARMLOS.match(m.group(2)) and " " in m.group(2)]


# ══════════════════════════════════════════════════════════════════════════════
# Teil 1 — Mischformen: der sichtbare Defekt
# ══════════════════════════════════════════════════════════════════════════════

def test_keine_mischform_mehr():
    """Ein deutsches Wort neben einem übersetzten ist in der englischen
    Oberfläche sichtbar falsch — und zwar in derselben Zeile."""
    funde = {str(p): w for p in _dateien() if (w := _mischformen(p))}
    assert not funde, (
        "Literal gegenüber einem Übersetzungsaufruf:\n"
        + "\n".join(f"  {d}: {w}" for d, w in funde.items()))


def test_symbolische_werte_gelten_nicht_als_fund():
    """``⏳ …`` ist sprachneutral. Ohne diese Ausnahme meldete der Wächter 21
    Sanduhren und wäre damit unlesbar."""
    assert SYMBOLISCH.match("⏳ …")
    assert SYMBOLISCH.match("✓")
    assert not SYMBOLISCH.match("✓ Fertig")


def test_der_erkenner_findet_eine_echte_mischform(tmp_path):
    """Gegenprobe: Ohne sie wäre „keine Mischform" auch bei einem blinden
    Erkenner wahr."""
    datei = tmp_path / "Probe.vue"
    datei.write_text(
        "<template><span>{{ x ? $t('a.b.c') : 'offen' }}</span></template>",
        encoding="utf-8")
    assert _mischformen(datei) == ["offen"]


# ══════════════════════════════════════════════════════════════════════════════
# Teil 2 — der Rückstand bleibt sichtbar und wächst nicht
# ══════════════════════════════════════════════════════════════════════════════

def test_keine_neue_datei_mit_harten_attributtexten():
    neu = {str(p.relative_to(WURZEL)): _attribute(p)
           for p in _dateien()
           if _attribute(p) and str(p.relative_to(WURZEL)) not in RUECKSTAND}
    assert not neu, (
        "Diese Dateien haben anzeigende Attribute mit Literaltext und stehen "
        "nicht im Rückstand:\n"
        + "\n".join(f"  {d}: {w}" for d, w in neu.items())
        + "\n\nÜbersetzen — oder, wenn es wirklich sprachneutral ist, mit "
          "Begründung in RUECKSTAND aufnehmen.")


@pytest.mark.parametrize("datei,deckel", sorted(RUECKSTAND.items()))
def test_der_rueckstand_wird_nicht_groesser(datei, deckel):
    p = WURZEL / datei
    if not p.is_file():
        pytest.skip(f"{datei} gibt es nicht mehr — Zeile aus RUECKSTAND nehmen")
    gefunden = _attribute(p)
    assert len(gefunden) <= deckel, (
        f"{datei}: {len(gefunden)} harte Attributtexte, erlaubt sind {deckel}.\n"
        + "\n".join(f"    {w}" for w in gefunden))


def test_der_rueckstand_nennt_nur_vorhandene_dateien():
    """Eine Zeile für eine gelöschte Datei ist ein Deckel ohne Gegenstand — und
    verdeckt, dass die Arbeit erledigt ist."""
    fehlen = [d for d in RUECKSTAND if not (WURZEL / d).is_file()]
    assert not fehlen, f"RUECKSTAND nennt gelöschte Dateien: {fehlen}"


def test_der_rueckstand_schrumpft_wenn_man_arbeitet():
    """Die Summe ist eine Zahl, die kleiner werden soll. Sie steht hier, damit
    sie jemand sieht — ein Rückstand ohne Zahl ist kein Rückstand."""
    summe = sum(RUECKSTAND.values())
    assert summe <= 93, (
        f"Der Rückstand ist auf {summe} gewachsen (gemessen am 09.11.2026: 93)")
