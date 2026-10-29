"""Kein sichtbarer Knopf ohne Wirkung (#1805).

**Der Befund aus dem Betrieb:** „Im Release-Vorgang Erfassen-Button bei
Konformität geht nicht." Er ging wirklich nicht. ``KonformitaetPanel`` bietet
„→ Im Release-Vorgang erfassen" an und feuert dafür ``goto``; die Einbindung in
``CRAView.vue`` hatte keinen ``@goto``-Zuhörer. Vue meldet das nicht — ein
Event ohne Zuhörer ist kein Fehler, sondern ein Ereignis, das niemanden
interessiert. Für den Anwender ist es ein Knopf, der nichts tut.

Diese Klasse lässt sich nicht durch Sorgfalt ausschließen, nur durch eine
Prüfung: Die Verdrahtung steht in einer **anderen Datei** als der Knopf, und
beim Einbauen einer Komponente sieht man ihre Events nicht. Derselbe Grund, aus
dem ``test_vorlagen_verdrahtung_1731.py`` existiert.

Geprüft wird: Jedes von einer Komponente emittierte Event hat an **jeder**
Einbindung einen Zuhörer — oder steht hier mit Begründung als Ausnahme.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path("frontend/src")

#: Events, die ohne Zuhörer richtig sind — je mit dem Grund.
#:
#: Die Liste ist kurz und bleibt es: Jeder Eintrag ist die Aussage „dieser Knopf
#: tut auch ohne Empfänger etwas Sinnvolles". Wer sie verlängert, um einen Test
#: grün zu bekommen, baut genau den Defekt wieder ein, den sie verhindern soll.
AUSNAHMEN: dict[tuple[str, str], str] = {
    # #1781: FehlerHinweis schließt sich selbst, damit nicht jede der 46
    # Fundstellen eine eigene Zuweisung braucht. `@close` ist die Kür.
    ("FehlerHinweis", "close"): "schließt sich selbst (#1781)",
    # Rückmeldungen über einen Download, der auch ohne Empfänger stattfindet.
    ("DownloadButton", "success"): "Benachrichtigung, der Download läuft ohnehin",
    ("DownloadButton", "error"): "Benachrichtigung; der Knopf zeigt den Fehler selbst",
    # Das Grid speichert selbst und zeigt das Ergebnis an; der Host darf, muss
    # aber nicht nachladen.
    ("AssistentenKachelGrid", "document-saved"): "Grid zeigt den Erfolg selbst an",
    # Das Badge lädt seinen Stand nach dem Setzen selbst neu.
    ("KiHerkunftBadge", "geprueft"): "Badge aktualisiert sich selbst",
    # Kacheln, die ein Modul nicht hat, werden nicht gerendert (`mitDokumente`
    # / `mitRisiken` / `fristenTab` / leere `extraKpis`) — dann gibt es keinen
    # Knopf, der nichts tut. Siehe `test_dashboard_kacheln_nur_mit_bereich`.
    ("ModuleDashboard", "open-dokumente"): "Kachel nur mit mitDokumente",
    ("ModuleDashboard", "open-risiken"): "Kachel nur mit mitRisiken",
    ("ModuleDashboard", "open-fristen"): "Kachel nur klickbar mit fristenTab",
    ("ModuleDashboard", "open-kpi"): "Kachel nur bei übergebenen extraKpis",
    # #1856: Die Werkzeuge der Seitenleiste rendern nur, was ihnen übergeben
    # wird — ohne `schalter` keine Chips, ohne `zeige-aufklappen` kein
    # „alle aufklappen", ohne `auswahlen`/`filterFelder` kein Auswahlfeld.
    # Fehlt der Zuhörer, fehlt also auch der Knopf. Dieselbe Begründung wie
    # bei `ModuleDashboard` darüber.
    ("SidebarWerkzeuge", "schalter"): "Chips nur mit übergebenen `schalter`",
    ("SidebarWerkzeuge", "expand-all"): "Link nur mit `zeige-aufklappen`",
    ("SidebarWerkzeuge", "auswahl"): "Auswahlfeld nur mit Filterwerten",
    # Modale: `close` ist am Overlay/✕ gebunden, `apply` schreibt selbst.
    ("WizardPromptModal", "close"): "Modal schließt über sein eigenes v-model/Overlay",
    ("WizardPromptModal", "apply"): "Übernahme erfolgt im Modal",
    # Der Stream zeigt Fehler (`.ks-error`) und Ergebnis selbst an; die Events
    # sind für Hosts, die darauf weiterarbeiten wollen.
    ("KiStreamView", "error"): "Fehler steht im Stream-Fenster",
    ("KiStreamView", "done"): "Ergebnis steht im Stream-Fenster",
    # Suchfeld-Link und Filter-Chips werden nur gerendert, wenn die Sidebar
    # `zeigeAufklappen` bzw. `schalter` übergibt — ohne Prop kein Knopf.
    ("SidebarSearch", "expand-all"): "Link nur mit zeigeAufklappen",
    ("SidebarSortFilter", "schalter"): "Chips nur mit schalter-Prop",
    # Diese zwei sind **keine** toten Knöpfe, aber auch nicht ganz sauber: Die
    # Komponente meldet den Erfolg selbst und lädt ihre eigene Anzeige neu; der
    # umgebende Score in der Liste zieht erst beim nächsten Laden nach. Hier
    # bewusst nicht mitgefixt — das sind geteilte Panels in vier Modulen, und
    # ein Nachladen dort gehört nicht in einen Fix für den Release-Vorgang.
    ("RequirementRiskLinks", "changed"): "lädt sich selbst neu; Host-Score zieht "
                                         "erst beim nächsten Laden nach",
    ("Hr01RiskLinkBox", "saved"): "Box meldet den übernommenen Score selbst",
}


def _vue_dateien() -> list[Path]:
    return sorted(SRC.rglob("*.vue"))


def _kebab(name: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name).lower()


def _emittierte_events() -> dict[str, set[str]]:
    """Welche Events emittiert welche Komponente (nach Dateiname)?"""
    ergebnis: dict[str, set[str]] = {}
    for f in _vue_dateien():
        text = f.read_text(encoding="utf-8")
        ev = set(re.findall(r"\$?emit\(\s*['\"]([a-zA-Z][\w-]*)['\"]", text))
        for m in re.finditer(r"defineEmits<(.*?)>\s*\(", text, re.S):
            ev |= set(re.findall(r"e:\s*['\"]([a-zA-Z][\w-]*)['\"]", m.group(1)))
        for m in re.finditer(r"defineEmits\(\s*\[(.*?)\]", text, re.S):
            ev |= set(re.findall(r"['\"]([a-zA-Z][\w-]*)['\"]", m.group(1)))
        if ev:
            ergebnis[f.stem] = ev
    return ergebnis


def _tag_ende(text: str, start: int) -> int:
    """Index des ``>``, das das Tag schließt — Anführungszeichen übersprungen.

    Der erste Anlauf dieser Prüfung scheiterte hier: ``@open-punkt="(id) => {…}"``
    enthält ein ``>``, und ein Regex auf ``[^>]*`` schnitt das Tag mitten im
    Handler ab. Die Folge waren 25 Fehlalarme — und ein Prüfskript, dessen
    Ausgabe man nicht mehr liest, prüft nichts.
    """
    i, quote = start, ""
    while i < len(text):
        c = text[i]
        if quote:
            if c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif c == ">":
            return i
        i += 1
    return len(text)


def _befunde() -> list[tuple[str, int, str, str]]:
    emits = _emittierte_events()
    befunde: list[tuple[str, int, str, str]] = []
    for f in _vue_dateien():
        text = f.read_text(encoding="utf-8")
        for komp, events in sorted(emits.items()):
            if komp == f.stem:
                continue
            muster = r"<(?:" + re.escape(komp) + r"|" + re.escape(_kebab(komp)) + r")(?=[\s/>])"
            for m in re.finditer(muster, text):
                attrs = text[m.end():_tag_ende(text, m.end())]
                # v-on="obj" / v-bind="obj" können alles weiterreichen.
                if "v-on=" in attrs or "v-bind=" in attrs:
                    continue
                for e in sorted(events):
                    if (komp, e) in AUSNAHMEN:
                        continue
                    if re.search(r"(?:@|v-on:)" + re.escape(e) + r"\b", attrs) \
                       or re.search(r"(?:@|v-on:)" + re.escape(_kebab(e)) + r"\b", attrs):
                        continue
                    zeile = text[:m.start()].count("\n") + 1
                    befunde.append((str(f.relative_to(SRC)), zeile, komp, e))
    return befunde


def test_jedes_event_hat_einen_zuhoerer():
    befunde = _befunde()
    if befunde:
        zeilen = "\n".join(f"  {d}:{z}  <{k}> emittiert '{e}' — kein Handler"
                           for d, z, k, e in befunde)
        pytest.fail(
            "Komponenten-Events ohne Zuhörer — für den Anwender ein Knopf, der "
            "nichts tut:\n" + zeilen
            + "\n\nEntweder einen Handler ergänzen oder, wenn der Knopf ohne "
              "Empfänger richtig ist, in AUSNAHMEN mit Begründung aufnehmen.")


def test_die_fundstelle_aus_dem_betrieb_ist_verdrahtet():
    """Der konkrete Befund: „Im Release-Vorgang erfassen" im Konformitäts-Tab."""
    view = (SRC / "views/cra/CRAView.vue").read_text(encoding="utf-8")
    m = re.search(r"<KonformitaetPanel(?=[\s/>])", view)
    assert m, "KonformitaetPanel ist nicht mehr eingebunden"
    attrs = view[m.end():_tag_ende(view, m.end())]
    assert "@goto" in attrs, "Der goto-Zuhörer fehlt wieder — der Knopf tut nichts"

    panel = (SRC / "views/cra/KonformitaetPanel.vue").read_text(encoding="utf-8")
    assert "$emit('goto', 'releases')" in panel, \
        "Der Knopf springt nicht mehr in den Releases-Tab"


def test_dashboard_kacheln_nur_mit_bereich():
    """Eine Kachel für einen Bereich, den das Modul nicht hat, gehört weg.

    Im Compliance-Audit standen „📄 Dokumente 0/0" und „⚠️ Offene Risiken 0"
    mit Zeigefinger-Cursor und sprangen nirgendwohin — das Modul hat beide
    Register nicht. Dieselbe Haltung wie bei ``extraKpis``: nichts übergeben
    heißt keine Kachel, nicht eine leere.
    """
    dash = (SRC / "components/shared/ModuleDashboard.vue").read_text(encoding="utf-8")
    assert re.search(r'v-if="mitDokumente"[^>]*open-dokumente', dash, re.S), \
        "Die Dokumente-Kachel ist wieder bedingungslos"
    assert re.search(r'v-if="mitRisiken"[^>]*open-risiken', dash, re.S), \
        "Die Risiko-Kachel ist wieder bedingungslos"

    audit = (SRC / "views/compliance-audit/ComplianceAuditView.vue").read_text(encoding="utf-8")
    assert ':mit-dokumente="false"' in audit and ':mit-risiken="false"' in audit, \
        "Das Compliance-Audit zeigt wieder Kacheln für Bereiche, die es nicht hat"


def test_sprungziele_sind_echte_tabs():
    """Ein Sprung auf einen Tab, den es nicht gibt, ist derselbe Defekt.

    Der Handler wäre da, der Klick täte nur nichts — noch schwerer zu finden,
    weil die Verdrahtung vorhanden aussieht.
    """
    faelle = [
        ("views/wiba/WiBAView.vue", "dokumente"),
        ("views/dsgvo/DSGVOView.vue", "dokumente"),
        ("views/cra/CRAView.vue", "releases"),
        ("views/cra/CRAView.vue", "konformitaet"),
    ]
    for datei, tab in faelle:
        text = (SRC / datei).read_text(encoding="utf-8")
        assert f"activeTab === '{tab}'" in text, \
            f"{datei}: Es gibt keinen Tab '{tab}', auf den gesprungen werden kann"


# ── Die andere Richtung: ein Zuhörer ohne Funktion (#1830) ──────────────────
#
# Der Wächter oben prüft Events, die niemanden interessieren. Der Befund aus dem
# Betrieb zum Compliance-Audit war das Spiegelbild: `@click="onBuildGutachtenPrompt"`
# — und die Funktion gab es nicht. Vue löst einen unbekannten Bezeichner in
# `<script setup>` zur Laufzeit zu `undefined` auf; `@click` bindet dann nichts,
# und der Klick wird still geschluckt. Keine Meldung, keine Anfrage, grüner Build:
# `vue-tsc` beanstandet unbekannte Template-Bezeichner hier nicht.

#: Bezeichner, die Vue selbst im Template bereitstellt.
TEMPLATE_GLOBALS: frozenset[str] = frozenset({
    "$emit", "$event", "$refs", "$attrs", "$slots", "$props", "$el", "$nextTick",
    "true", "false", "null", "undefined",
    "Math", "JSON", "Object", "Array", "String", "Number", "Boolean", "Date",
    "console", "parseInt", "parseFloat", "isNaN",
    "encodeURIComponent", "decodeURIComponent",
})

#: ``@event="name"`` bzw. ``v-on:event="name"`` mit einem **einfachen**
#: Bezeichner. Alles andere (``store.foo``, Inline-Pfeilfunktionen, Zuweisungen)
#: prüft diese Regel bewusst nicht — dort steht der Code im Template selbst und
#: kann nicht spurlos verschwinden.
_HANDLER = re.compile(
    r'(?:@|v-on:)([a-zA-Z][\w.:-]*)\s*=\s*"([A-Za-z_$][\w$]*)\s*(?:\([^"]*\))?"')


def _script_und_template(text: str) -> tuple[str, str]:
    teile = list(re.finditer(r"<script[^>]*>(.*?)</script>", text, re.S))
    script = "".join(m.group(1) for m in teile)
    template = text
    for m in reversed(teile):
        template = template[:m.start()] + template[m.end():]
    return script, template


def _ist_definiert(name: str, script: str) -> bool:
    n = re.escape(name)
    muster = (
        rf"\b(?:const|let|var|function|async\s+function)\s+{n}\b",  # Deklaration
        rf"\bimport\b[^\n]*\b{n}\b",                                # Import
        rf"[{{,]\s*{n}\s*[,}}:=]",                                  # Destrukturierung
        rf"\b{n}\s*\??\s*:",            # Funktions-Prop in defineProps
        rf"\b{n}\s*=",                  # Zuweisung
    )
    return any(re.search(p, script) for p in muster)


def _handler_ohne_funktion() -> list[tuple[str, int, str, str]]:
    befunde: list[tuple[str, int, str, str]] = []
    for f in _vue_dateien():
        text = f.read_text(encoding="utf-8")
        script, template = _script_und_template(text)
        if not script:
            continue
        for m in _HANDLER.finditer(template):
            ereignis, name = m.group(1), m.group(2)
            if name in TEMPLATE_GLOBALS or _ist_definiert(name, script):
                continue
            zeile = text.count("\n", 0, text.find(m.group(0))) + 1
            befunde.append((str(f.relative_to(SRC)), zeile, ereignis, name))
    return befunde


def test_jeder_handler_ist_definiert():
    befunde = _handler_ohne_funktion()
    if befunde:
        zeilen = "\n".join(f"  {d}:{z}  @{e}=\"{n}\" — {n} ist im Script nicht definiert"
                           for d, z, e, n in befunde)
        pytest.fail(
            "Template-Handler ohne Funktion. Vue bindet dann nichts, und der "
            "Klick wird still geschluckt:\n" + zeilen
            + "\n\nFunktion ergänzen, importieren oder als Funktions-Prop "
              "deklarieren.")


def test_die_fundstelle_aus_dem_betrieb_ist_wieder_verdrahtet():
    """Der konkrete Befund: „Entwurf erzeugen" im Compliance-Bericht (#1830).

    Beide Enden werden geprüft. Der Knopf allein genügt nicht: Selbst wenn er
    das Modal öffnete, liefe „Antwort übernehmen" ins Leere, solange der
    ``@apply``-Handler fehlt — der Weg war an beiden Enden durchtrennt.
    """
    view = (SRC / "views/compliance-audit/ComplianceAuditView.vue").read_text(
        encoding="utf-8")
    script, _ = _script_und_template(view)
    for name in ("onBuildGutachtenPrompt", "onBerichtAusKi"):
        assert _ist_definiert(name, script), f"{name} fehlt wieder"
    assert "store.buildGutachtenPrompt(" in script, \
        "Der Knopf holt den Prompt nicht mehr"
    assert "store.importGutachten(" in script, \
        "Die KI-Antwort wird nicht mehr übernommen"
