"""Keine Issue-URL verschwindet beim Umbau auf die Fabrik (#1846).

Die ~76 Issue-Routen werden durch `shared/issue_api.register_routes` ersetzt.
Das Bruchrisiko ist nicht die Fabrik, sondern das **Vergessen**: Eine URL, die
nachher anders heißt, bricht das Frontend lautlos — der Aufruf geht ins 404,
und die Maske zeigt „Sync fehlgeschlagen" ohne zu sagen, dass es die Route
nicht mehr gibt.

Deshalb ist die Liste **vor** dem Umbau aus der laufenden App aufgenommen
worden (`tests/data/issue_routen_vor_1846.json`) und wird hier gegen die
aktuelle App gehalten. Das ist der Schutz — nicht die Sorgfalt beim Umbauen.

**Neue Routen sind erlaubt** (die Fabrik schließt acht Fähigkeitslücken und
ergänzt `import-issue`), **verschwundene nicht.** Soll eine Altform bewusst
entfallen, gehört sie in :data:`ABGELOEST` — mit Grund.
"""
from __future__ import annotations

import json
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
INVENTAR = WURZEL / "tests" / "data" / "issue_routen_vor_1846.json"

#: Altformen, die bewusst entfallen — je mit Grund und Nachfolger.
#: Leer: Beim Umbau bleiben alle Altformen erhalten, unregelmäßige als Alias.
ABGELOEST: dict[str, str] = {}


def _aktuelle_routen(app) -> set[str]:
    return {
        f"{sorted(r.methods - {'HEAD', 'OPTIONS'})[0]} {r.rule}"
        for r in app.url_map.iter_rules()
        if "issues" in r.rule or "import-issue" in r.rule or r.rule.endswith("/audit")
    }


def test_inventar_ist_vorhanden():
    """Ohne die Aufnahme von vorher prüft dieser Test nichts."""
    assert INVENTAR.exists(), (
        "Das Routen-Inventar fehlt. Es wird VOR dem Umbau aus der laufenden "
        "App aufgenommen — nachträglich erzeugt wäre es eine Abschrift des "
        "Ist-Zustands und damit wertlos.")
    assert len(json.loads(INVENTAR.read_text())) >= 70


def test_keine_issue_route_ist_verschwunden(app):
    vorher = set(json.loads(INVENTAR.read_text(encoding="utf-8")))
    jetzt = _aktuelle_routen(app)
    fehlend = sorted(r for r in vorher - jetzt if r not in ABGELOEST)
    assert not fehlend, (
        "Diese Issue-URLs gibt es nicht mehr — das Frontend läuft dort ins "
        "404:\n  " + "\n  ".join(fehlend)
        + "\n\nEntweder wiederherstellen (ggf. als Alias) oder in ABGELOEST "
          "mit Grund und Nachfolger aufnehmen.")


def test_abgeloeste_routen_tragen_einen_grund():
    for route, grund in ABGELOEST.items():
        assert len(grund) >= 25, f"{route}: Grund zu knapp — „{grund}“"


def test_doppelte_endpunkte_gibt_es_nicht(app):
    """Zwei Regeln auf dieselbe URL sind ein Umbaufehler.

    Beim Einziehen einer Fabrik ist der naheliegende Fehler, die Altroute
    stehen zu lassen und die neue danebenzulegen: Flask nimmt dann die erste
    und die zweite wirkt nie — stumm.
    """
    gesehen: dict[str, str] = {}
    doppelt = []
    for r in app.url_map.iter_rules():
        if "issues" not in r.rule and "import-issue" not in r.rule:
            continue
        for m in r.methods - {"HEAD", "OPTIONS"}:
            schluessel = f"{m} {r.rule}"
            if schluessel in gesehen and gesehen[schluessel] != r.endpoint:
                doppelt.append(f"{schluessel}: {gesehen[schluessel]} ↔ {r.endpoint}")
            gesehen[schluessel] = r.endpoint
    assert not doppelt, "Doppelt belegte Issue-URLs: " + ", ".join(doppelt)


# ── Jede Objektart ist vollständig verdrahtet ───────────────────────────────

#: Was die Fabrik je Modul führen muss. Diese Liste ist die Zusage „alle
#: Knöpfe in allen Modulen, gleich benannt und gleich wirkend" — fällt eine
#: Objektart heraus, fehlt dort die halbe Oberfläche, ohne dass etwas bricht.
ERWARTET = {
    "cra": {"requirement", "owasp", "risk", "vuln"},
    "nis2": {"requirement"},
    "aiact": {"requirement", "owasp_llm"},
    "dsgvo": {"requirement"},
    "wiba": {"wiba_control"},
    "risikobewertung": {"risk"},
}


def test_jedes_modul_fuehrt_seine_objektarten(app):
    """Die Fabrik ist registriert — und zwar für jede Objektart des Moduls.

    Der Import der API-Module geschieht beim App-Bau; ohne `app` ist die
    Registry leer und der Test prüfte nichts.
    """
    from shared.issue_api import arten_fuer
    for modul, arten in ERWARTET.items():
        ist = {a.art for a in arten_fuer(modul)}
        assert ist == arten, f"{modul}: erwartet {sorted(arten)}, registriert {sorted(ist)}"


def test_keine_objektart_ist_halb_verdrahtet(app):
    """Die Falle aus #1731: registriert, aber ohne Lese-/Schreibweg.

    Ein fehlendes `lies_text` fällt erst auf, wenn ein Anwender den Abgleich
    drückt — und dann als 500, nicht als Hinweis.
    """
    from shared.issue_api import arten_fuer
    for modul in ERWARTET:
        for a in arten_fuer(modul):
            for feld in ("lade", "inhalt", "lies_text", "schreib_text", "stand"):
                assert callable(getattr(a, feld, None)), \
                    f"{modul}/{a.art}: {feld} fehlt"
            assert a.db_path is not None, f"{modul}/{a.art}: db_path fehlt"
            assert a.bezeichnung, f"{modul}/{a.art}: bezeichnung fehlt"


def test_jedes_modul_hat_die_projektweiten_knoepfe(app):
    """Abgleich und Übernahme für das ganze Projekt — in allen sechs Modulen.

    WiBA und DSGVO hatten keine projektweite Übernahme, DSGVO glich zwar ab,
    markierte aber nicht. Beides war nicht entschieden, sondern vergessen.
    """
    regeln = {f"{sorted(r.methods - {'HEAD', 'OPTIONS'})[0]} {r.rule}"
              for r in app.url_map.iter_rules()}
    prefix = {"cra": "/api/cra", "nis2": "/api/nis2", "aiact": "/api/aiact",
              "dsgvo": "/api/dsgvo", "wiba": "/api/wiba",
              "risikobewertung": "/api/risikobewertung"}
    for modul, p in prefix.items():
        for weg in ("issues/sync", "issues/import"):
            assert f"POST {p}/projekte/<projekt_name>/{weg}" in regeln, \
                f"{modul}: {weg} fehlt"


def test_der_abgleich_erledigt_nichts_von_selbst():
    """#1526 gilt für alle Module — Stolperdraht gegen das Auto-Erledigen.

    Vor dem Umbau setzte CRA bei geschlossenem Issue `set_risiko_resolved`
    und `status='fixed'`. Beides ist eine Bewertung; sie trifft ein Mensch.

    Die eigentliche Zusicherung geben die Verhaltenstests
    (`test_cra_risk_issue_sync`, `test_cra_vuln_issue_1041`) — dieser Test ist
    nur der billige Draht an der **einen** Stelle, an der es wieder einziehen
    könnte, und findet die naheliegende Schreibweise.
    """
    from pathlib import Path as _P
    for datei in ("shared/issue_abgleich.py", "shared/issue_api.py"):
        quelle = _P(datei).read_text(encoding="utf-8")
        for verboten in ("set_risiko_resolved", "resolved=True",
                         "'fixed'", '"fixed"'):
            assert verboten not in quelle, (
                f"{datei} enthaelt {verboten!r} — der Abgleich markiert, "
                "er erledigt nicht (#1526).")
