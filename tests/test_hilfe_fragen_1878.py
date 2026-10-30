"""#1878: Die Hilfe ist fragbar — geerdet auf das Handbuch.

Wunsch aus dem Betrieb: „Ich will überall, wo Hilfe steht, die Möglichkeit, wie
in einem LLM-Chat die KI fragen zu können, was mein Problem ist. Bei der Lösung
soll immer die API verwendet werden und das Handbuch und die Infos herangezogen
werden, sodass die Lösung möglichst gut ist."

Geprüft wird das **Verhalten**, nicht die Erzählung: dass das Handbuch wirklich
gelesen wird, dass die Auswahl zur Frage passt, dass der Prompt die Grenzen
einhält und dass dieses Modul die KI **nicht selbst** ruft. Ein Wächter, der nur
nach Wörtern im Quelltext sucht, bleibt grün, wenn man die Zeile durch `pass`
ersetzt — das Wort steht noch im Kommentar darüber (die Lehre aus #1834).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared import hilfe

WURZEL = Path(__file__).resolve().parent.parent


# ── Das Handbuch wird wirklich gelesen ──────────────────────────────────────

def test_handbuch_liegt_im_repo_und_wird_zerlegt():
    """Gegen die echten Dateien, nicht gegen erfundene Abschnitte.

    Ein Test, der sich seine Quelle selbst mitbringt, prüft nur sich selbst —
    das war der Befund in #1870.
    """
    teile = hilfe.handbuch("cra")
    assert teile, "docs/modules/cra.md muss lesbar sein"
    assert all(inhalt.strip() for _t, inhalt in teile)
    assert any(t for t, _i in teile), "mindestens eine Überschrift"


@pytest.mark.parametrize("modul,datei", sorted(hilfe.MODUL_DATEI.items()))
def test_jede_zuordnung_zeigt_auf_eine_vorhandene_datei(modul, datei):
    """Die Spiegel-Liste aus #1731/#1735 in ihrer leisesten Form.

    Ein falscher Dateiname ergibt keinen Fehler — die Hilfe antwortet dann ohne
    Handbuch und sieht dabei aus wie eine, die eines gelesen hat.
    """
    assert (hilfe.DOKU_VERZEICHNIS / datei).is_file(), (
        f"MODUL_DATEI['{modul}'] = '{datei}' gibt es nicht")


def test_jede_moduldoku_ist_zugeordnet():
    """Die Gegenrichtung: eine neue Modul-Doku darf nicht unerreichbar bleiben."""
    vorhanden = {p.name for p in hilfe.DOKU_VERZEICHNIS.glob("*.md")}
    zugeordnet = set(hilfe.MODUL_DATEI.values())
    # `index.md` ist Beiwerk; `bedienung.md` wird IMMER gelesen (ALLGEMEIN_DATEI)
    # und braucht deshalb keinen Modulschlüssel.
    offen = {n for n in vorhanden - zugeordnet
             if n not in {"index.md", hilfe.ALLGEMEIN_DATEI}}
    assert not offen, f"Modul-Doku ohne Zuordnung in MODUL_DATEI: {sorted(offen)}"


def test_fehlendes_verzeichnis_stuerzt_nicht_ab(monkeypatch):
    """Fehlende Doku → leer, nicht Ausnahme.

    Ein unbekanntes Modul liefert dagegen bewusst NICHT leer: Die allgemeine
    Bedienanleitung bleibt, siehe `test_bedienanleitung_ist_immer_dabei`.
    """
    monkeypatch.setattr(hilfe, "DOKU_VERZEICHNIS", WURZEL / "gibt-es-nicht")
    assert hilfe.handbuch("cra") == []
    assert hilfe.handbuch("") == []
    prompt, fundstellen = hilfe.baue_prompt("x", modul="cra")
    assert "(keine Handbuch-Abschnitte gefunden)" in prompt
    assert fundstellen == []


# ── Die Auswahl passt zur Frage ─────────────────────────────────────────────

def test_passende_abschnitte_bevorzugen_die_frage():
    ab = [("Release-Vorgänge", "Ampel gruen bedingt rot je Release"),
          ("Schwachstellen", "Dependabot und CVE-Register"),
          ("Vorlagen", "Word-Vorlagen und Platzhalter")]
    treffer = hilfe.passende_abschnitte("Warum ist mein Release rot?", ab)
    assert treffer[0][0] == "Release-Vorgänge"


def test_ohne_treffer_kommt_der_anfang_und_nicht_nichts():
    """„Dazu finde ich nichts" ist auch eine Antwort — aber sie braucht
    Material, um gegeben werden zu können."""
    ab = [("A", "aaa"), ("B", "bbb"), ("C", "ccc")]
    treffer = hilfe.passende_abschnitte("zzzzzzzz qqqqqqqq", ab)
    assert treffer and len(treffer) <= 2


def test_auswahl_haelt_die_obergrenze():
    ab = [(f"T{i}", f"release ampel rot {i}") for i in range(40)]
    assert len(hilfe.passende_abschnitte("release rot", ab)) <= hilfe.MAX_ABSCHNITTE


# ── Der Prompt ──────────────────────────────────────────────────────────────

def test_prompt_traegt_frage_stand_hilfe_und_handbuch():
    prompt, fundstellen = hilfe.baue_prompt(
        "Warum ist mein Release rot?", modul="cra", bereich="releases",
        hilfe_text="Der Release-Check zeigt eine Ampel.",
        stand={"Projekt": "Testprodukt", "Version": "8.2.2"})
    assert "Warum ist mein Release rot?" in prompt
    assert "cra" in prompt and "releases" in prompt
    assert "Testprodukt" in prompt and "8.2.2" in prompt
    assert "Der Release-Check zeigt eine Ampel." in prompt
    assert "## Handbuch" in prompt
    assert fundstellen, "die Grundlage muss nachsehbar sein"


def test_prompt_verbietet_erfundene_wege():
    """Eine erfundene Wegbeschreibung ist schlechter als keine (#1805)."""
    prompt, _ = hilfe.baue_prompt("Wo stelle ich das ein?", modul="cra")
    assert "Erfinde keine" in prompt
    assert "Dazu steht nichts in der" in prompt
    assert "keine rechtsberatung" in prompt.lower()


def test_leere_frage_und_leerer_stand_laufen_durch():
    prompt, _ = hilfe.baue_prompt("", modul="")
    assert "(nicht angegeben)" in prompt
    assert "(kein Hilfe-Abschnitt übergeben)" in prompt
    # Nichts darf als Wert „None" im Prompt landen (die Falle aus #1730).
    assert "None" not in prompt


def test_leere_standwerte_fallen_weg():
    prompt, _ = hilfe.baue_prompt("x", modul="cra",
                                  stand={"Projekt": "P", "Tab": "", "Leer": None})
    assert "- Projekt: P" in prompt
    assert "Tab" not in prompt.split("## Hilfe-Abschnitt")[0].split("Bereich:")[1]


def test_prompt_bleibt_in_seinen_grenzen():
    """Ein Modell, dem man das halbe Handbuch vorlegt, antwortet schlechter —
    und das Budget aus #1841 schnitte mitten im Material ab."""
    lang = "x" * 50000
    prompt, _ = hilfe.baue_prompt(lang, modul="cra", hilfe_text=lang)
    grenze = (hilfe.MAX_FRAGE + hilfe.MAX_ZEICHEN_HILFE
              + hilfe.MAX_ZEICHEN_HANDBUCH + 4000)
    assert len(prompt) <= grenze, f"Prompt ist {len(prompt)} Zeichen lang"


# ── Dieses Modul ruft die KI nicht selbst ───────────────────────────────────

def test_kein_eigener_ki_transport():
    """`/api/ai/run-stream` leistet Verfügbarkeit, Egress-Tor samt
    Revisionseintrag, eigene Hinweise und Budget (#1841). Ein eigener Transport
    wäre der sechste — und hätte keines davon.
    """
    for datei in ("shared/hilfe.py", "server/api/hilfe.py"):
        quelle = (WURZEL / datei).read_text(encoding="utf-8")
        ohne_kommentare = "\n".join(
            z for z in quelle.splitlines() if not z.lstrip().startswith("#"))
        for verboten in ("requests.post", "ki_lauf", "generate_text", "ollama"):
            assert verboten not in ohne_kommentare, (
                f"{datei} spricht selbst mit der KI: {verboten}")


def test_endpunkt_haengt_unter_api_hilfe_und_verlangt_anmeldung():
    """Gegen eine echte Flask-App, nicht gegen den Quelltext.

    Geprüft wird, was eine Anfrage erlebt: Die Route existiert, und ohne Token
    kommt 401 — nicht 404 und nicht 200.
    """
    from flask import Flask
    from flask_jwt_extended import JWTManager

    from server.api.hilfe import hilfe_bp

    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = "x" * 32
    JWTManager(app)
    app.register_blueprint(hilfe_bp, url_prefix="/api/hilfe")

    pfade = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/hilfe/prompt" in pfade
    assert "/api/hilfe/handbuch/<modul>" in pfade

    c = app.test_client()
    assert c.post("/api/hilfe/prompt", json={"frage": "x"}).status_code == 401

    # Mit Token: eine leere Frage wird abgewiesen, eine echte beantwortet.
    with app.app_context():
        from flask_jwt_extended import create_access_token
        kopf = {"Authorization": f"Bearer {create_access_token(identity='1')}"}
    assert c.post("/api/hilfe/prompt", json={}, headers=kopf).status_code == 400
    r = c.post("/api/hilfe/prompt",
               json={"frage": "Warum ist mein Release rot?", "modul": "cra"},
               headers=kopf)
    assert r.status_code == 200
    assert r.get_json()["prompt"].strip()
    assert r.get_json()["fundstellen"]

    h = c.get("/api/hilfe/handbuch/cra", headers=kopf).get_json()
    assert h["vorhanden"] is True and h["modul_doku"] is True and h["abschnitte"]
    # Unbekanntes Modul: keine Modul-Doku, aber die Bedienanleitung bleibt —
    # die Oberfläche kann beides auseinanderhalten.
    u = c.get("/api/hilfe/handbuch/gibtsnicht", headers=kopf).get_json()
    assert u["modul_doku"] is False and u["allgemein"] is True


def test_das_handbuch_liegt_im_image():
    """Ohne diese Zeile im Dockerfile liest der Server im Betrieb nichts —
    und die Hilfe antwortete ohne Handbuch, ohne dass es auffällt."""
    docker = (WURZEL / "Dockerfile").read_text(encoding="utf-8")
    assert "docs/modules/" in docker, (
        "Dockerfile kopiert docs/modules/ nicht ins Image — #1878")


def test_bedienanleitung_ist_immer_dabei():
    """Die häufigsten Bedienfragen sind nicht modulspezifisch.

    `bedienung.md` muss auch dann gelesen werden, wenn kein oder ein
    unbekanntes Modul übergeben wurde — sonst antwortet die Hilfe genau dort
    ohne Material, wo sie am ehesten gebraucht wird.
    """
    assert (hilfe.DOKU_VERZEICHNIS / hilfe.ALLGEMEIN_DATEI).is_file()
    ohne = hilfe.handbuch("")
    assert ohne, "ohne Modul muss die Bedienanleitung bleiben"
    # Mit Modul kommt sie zusätzlich, und die Modul-Doku steht VORN.
    nur_allgemein = hilfe._lies(hilfe.ALLGEMEIN_DATEI)
    mit = hilfe.handbuch("cra")
    assert len(mit) > len(nur_allgemein)
    assert mit[:1] != nur_allgemein[:1], "die genauere Quelle gehört nach vorn"


# ── Hilfe, die niemand öffnen kann, ist keine Hilfe ─────────────────────────

def test_jeder_hilfe_inhalt_ist_erreichbar():
    """Jeder im Hilfe-Index registrierte Modulschlüssel braucht einen Knopf.

    `complianceAuditHelp` (seit #1713) und `socHelp` waren gepflegt und
    **nirgends** erreichbar: Die übrigen Modul-Ansichten bekommen den Knopf
    über `ModuleShell`, diese zwei nutzen sie nicht. Hilfe-Inhalt ohne Weg
    dorthin ist dieselbe Klasse wie ein Knopf ohne Wirkung (#1805/#1830) —
    nichts schlägt fehl, es ist nur nicht da.
    """
    import re

    idx = (WURZEL / "frontend" / "src" / "help" / "index.ts").read_text(encoding="utf-8")
    # Der Katalog: `'compliance-audit': complianceAuditHelp,` bzw. `cra: craHelp,`
    block = idx.split("{", 1)[1] if "{" in idx else idx
    registriert = set(re.findall(r"^\s*'?([a-zA-Z][\w-]*)'?\s*:\s*\w+Help\s*,",
                                 block, re.M))
    assert registriert, "Hilfe-Index konnte nicht gelesen werden"

    verwendet: set[str] = set()
    for pfad in (WURZEL / "frontend" / "src").rglob("*.vue"):
        text = pfad.read_text(encoding="utf-8")
        verwendet |= set(re.findall(r'<ModuleHelpButton[^>]*?module="([\w-]+)"', text))
        # `ModuleShell` reicht `moduleName` durch — der Wert steht am Aufrufer.
        verwendet |= set(re.findall(r'module-name="([\w-]+)"', text))
        verwendet |= set(re.findall(r':module-name="\'([\w-]+)\'"', text))

    fehlt = registriert - verwendet
    assert not fehlt, (
        f"Hilfe-Inhalt ohne Hilfe-Knopf: {sorted(fehlt)} — "
        "entweder einbinden oder aus help/index.ts entfernen")
