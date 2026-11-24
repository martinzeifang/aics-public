"""Das Frontend hat einen Typprüfer — und er ist verbindlich (#1858).

DER BEFUND
Es gab im Repo keine ``tsconfig.json``. ``vue-tsc --noEmit`` fand damit kein
Projekt, druckte die ``tsc``-Hilfe und endete mit Exit 1; in der CI lief für
das Frontend **gar keine** Typprüfung (der Job ``typecheck`` dort ist mypy für
Python). Gebaut wird mit Vite/Rolldown, und das **transpiliert** TypeScript
nur, statt es zu prüfen.

Durch genau diese Lücke ging **#1854**: ``export { X as Y } from '…'`` reicht
einen Namen durch und legt in der Datei keine Bindung an; die Benutzung
desselben Namens ergab zur Laufzeit einen ``ReferenceError``, der im ``catch``
des Ladevorgangs als „Fehler beim Laden" erschien. Der Fehler stand auf allen
vier Instanzen, und kein Prüfer hat ihn gesehen.

WAS DIESER TEST HÄLT
Nicht die Abwesenheit von Typfehlern — das tut ``vue-tsc`` selbst, und zwar in
der CI. Dieser Test hält die **Einrichtung**: dass es die Projektdatei gibt,
dass streng geprüft wird, und dass der Lauf in der CI **folgen hat**. Ein
``continue-on-error`` an der falschen Stelle macht aus dem Prüfer wieder eine
Verzierung — das ist die Lehre aus #1805 (ein Prüfer, dessen Ausgabe man nicht
mehr liest, prüft nichts), hier auf die CI angewandt.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend"
TSCONFIG = FRONTEND / "tsconfig.json"
CI = WURZEL / ".github" / "workflows" / "ci.yml"


def _tsconfig() -> dict:
    """Liest die tsconfig — Kommentare sind dort erlaubt und müssen weg."""
    rohtext = TSCONFIG.read_text(encoding="utf-8")
    ohne = re.sub(r"^\s*//.*$", "", rohtext, flags=re.MULTILINE)
    return json.loads(ohne)


def test_die_projektdatei_existiert():
    assert TSCONFIG.is_file(), (
        "frontend/tsconfig.json fehlt — ohne sie findet `vue-tsc` kein "
        "Projekt, druckt die `tsc`-Hilfe und prüft nichts (#1858).")


def test_streng_wird_geprueft():
    opts = _tsconfig()["compilerOptions"]
    assert opts.get("strict") is True, (
        "`strict` muss an bleiben. Der Unterschied zur lockeren Prüfung waren "
        "beim Einschalten zwölf Meldungen — dafür lohnt kein zweiter Schritt, "
        "und ein locker eingestellter Prüfer wird nicht nachträglich strenger.")
    assert opts.get("noEmit") is True, "Der Prüfer darf nichts schreiben."


def test_der_quellbaum_ist_erfasst():
    """Eine `include`-Liste, die `.vue` auslässt, prüft am Kern vorbei."""
    include = _tsconfig().get("include") or []
    assert any(e.endswith(".vue") for e in include), (
        "Die `.vue`-Dateien müssen erfasst sein — dort steht der Code, der "
        "in #1830 und #1854 gebrochen war.")
    assert any("src/" in e for e in include), "Der Quellbaum `src/` fehlt."


def test_der_alias_ist_hier_auch_bekannt():
    """`@` steht in `vite.config.ts`; ohne `paths` scheitert die Auflösung.

    Zwei Stellen für dieselbe Zuordnung sind die Spiegel-Liste aus
    #1731/#1735 — hier unvermeidlich, weil Vite und tsc je eigene Auflösung
    mitbringen. Der Test hält wenigstens fest, dass beide sie kennen.
    """
    paths = (_tsconfig()["compilerOptions"].get("paths") or {})
    assert "@/*" in paths, "Der `@`-Alias aus vite.config.ts fehlt in `paths`."
    vite = (FRONTEND / "vite.config.ts").read_text(encoding="utf-8")
    assert "'@'" in vite, "Der Alias ist in vite.config.ts verschwunden — dann " \
                          "gehört er auch hier weg."


def test_das_skript_ruft_vue_tsc():
    pkg = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    skript = (pkg.get("scripts") or {}).get("type-check", "")
    assert "vue-tsc" in skript, (
        "`npm run type-check` muss `vue-tsc` rufen — `tsc` allein sieht in "
        "`.vue`-Dateien nicht hinein.")


def test_die_ci_prueft_und_es_hat_folgen():
    """Der Lauf muss in einem Job stehen, der rot werden **kann**.

    Bewusst als Schritt in `frontend-build`: Ein eigener Job wäre ein neuer
    Check-Name, der erst in der Branch-Protection als Pflicht eingetragen
    werden müsste und bis dahin folgenlos bliebe.
    """
    text = CI.read_text(encoding="utf-8")
    assert "npm run type-check" in text, (
        "Die CI ruft `npm run type-check` nicht — damit prüft im Frontend "
        "wieder niemand (#1858).")

    # Den Job herausschneiden, in dem der Aufruf steht, und sehen, ob er
    # non-blocking ist. `continue-on-error` an dieser Stelle wäre genau die
    # Verzierung, die #1858 beseitigt hat.
    jobs = re.split(r"\n(?=  [a-z][a-z0-9-]*:\n)", text)
    treffer = [j for j in jobs if "npm run type-check" in j]
    assert treffer, "Kein Job gefunden, der den Typprüfer ruft."
    for job in treffer:
        kopf = job.split("steps:")[0]
        assert "continue-on-error: true" not in kopf, (
            "Der Job mit dem Typprüfer trägt `continue-on-error: true` — er "
            "kann dann nicht rot werden, und die Prüfung ist folgenlos. Das "
            "war der Zustand, den #1858 beendet hat.")


# ── Der Defekt, den der Prüfer gefunden hat ──────────────────────────────────

def test_aiact_panel_liest_den_schluessel_den_der_server_liefert():
    """#1858: `AIActPflichtDokuPanel` las `meta_json` — das gibt es dort nicht.

    `_serialize_projekt` in `server/api/aiact.py` ist eine **Positivliste** und
    gibt die Rohspalte nicht heraus; sie heißt in der Antwort `meta`. CRA,
    DSGVO und WiBA liefern dagegen `meta_json`, und nach deren Muster war die
    Zeile geschrieben. Folge: Der Entwurf war immer `{}`, `riskTierInfo` immer
    `null` — die Karte mit der Einstufung des KI-Systems (prohibited /
    high-risk / limited / minimal) konnte nie erscheinen, obwohl der Assistent
    A1 sie schreibt und Bericht und FRIA sie lesen.

    Der Typprüfer sieht das nur, solange `AIActProjekt` die Felder **nicht**
    großzügig deklariert. Dieser Test hält die Richtung unabhängig davon.
    """
    serializer = (WURZEL / "server" / "api" / "aiact.py").read_text(encoding="utf-8")
    block = serializer.split("def _serialize_projekt", 1)[1].split("\ndef ", 1)[0]
    geliefert = set(re.findall(r"^\s*'([a-z_]+)':", block, flags=re.MULTILINE))
    assert "meta" in geliefert, (
        "Der AI-Act-Serializer liefert `meta` nicht mehr — dann müssen die "
        "Leser im Frontend mitgezogen werden.")

    panel = (WURZEL / "frontend" / "src" / "views" / "aiact"
             / "AIActPflichtDokuPanel.vue").read_text(encoding="utf-8")
    gelesen = set(re.findall(r"selectedProjektObj\?\.([a-z_]+)", panel))
    unbekannt = gelesen - geliefert
    assert not unbekannt, (
        "AIActPflichtDokuPanel liest Felder, die `_serialize_projekt` nicht "
        f"ausgibt: {sorted(unbekannt)}. Zur Laufzeit ist das `undefined` — es "
        "schlägt nichts fehl, die Anzeige bleibt nur leer.")


def test_wiba_bausteine_ist_text():
    """Der Typ sagte `string[]`, die Spalte ist TEXT (#1858).

    Alle drei Leser behandeln den Wert als Text (`bausteinChips` trennt an
    `;`, `bausteinKuerzel` sucht per Regex). Hier war der **Typ** falsch, nicht
    der Code — und ein falscher Typ lässt den Prüfer gegen die falsche Wahrheit
    prüfen.
    """
    db = (WURZEL / "wiba" / "db.py").read_text(encoding="utf-8")
    assert re.search(r"bausteine\s+TEXT", db), (
        "`wiba_themen.bausteine` ist nicht mehr TEXT — dann gehört der "
        "Frontend-Typ nachgezogen.")
    store = (WURZEL / "frontend" / "src" / "stores" / "wiba.ts").read_text(encoding="utf-8")
    assert "bausteine: string\n" in store, (
        "`WiBAThema.bausteine` muss `string` sein, nicht `string[]`.")


@pytest.mark.parametrize("modul", [
    "cra", "nis2", "aiact", "dsgvo", "wiba", "risikobewertung", "gutachten",
    "compliance_audit",
])
def test_firmen_modulschalter_vollstaendig(modul: str):
    """Jede Spalte `module_*` braucht ihren Schalter im Formular (#1858).

    `compliance_audit` fehlte seit dem Modul-Split (#1713): Die Spalte steht
    auf `DEFAULT 1`, und `_fields_from_payload` schreibt nur, was der Aufrufer
    **nennt** — eine neue Firma hatte das Modul also an, während die Kachel im
    Formular leer aussah.
    """
    from shared.licensing.modules import FIRMEN_MODULE_COLUMNS
    assert modul in FIRMEN_MODULE_COLUMNS, f"Unbekanntes Modul: {modul}"
    # Im Frontend heißt der AI-Act-Schlüssel `ai_act` (wie die Spalte).
    schluessel = "ai_act" if modul == "aiact" else modul
    store = (WURZEL / "frontend" / "src" / "stores" / "firmen.ts").read_text(encoding="utf-8")
    assert f"{schluessel}: boolean" in store, (
        f"`Firma.modules.{schluessel}` fehlt im Store-Typ.")
    view = (WURZEL / "frontend" / "src" / "views" / "firmen"
            / "FirmenView.vue").read_text(encoding="utf-8")
    assert f"{schluessel}: true" in view, (
        f"`{schluessel}` fehlt in der Vorbelegung für eine neue Firma — die "
        f"Kachel sieht dann leer aus, obwohl die Spalte auf 1 steht.")
