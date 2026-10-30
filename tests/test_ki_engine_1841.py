"""Eine Funktion für alle KI-Anfragen (#1841, aus #1836/E4).

Die Behauptung dieser Änderung ist nicht „es gibt jetzt eine Engine", sondern
**„jeder KI-Lauf durchläuft dieselben Schritte"**. Das lässt sich nur an zwei
Dingen prüfen: am Verhalten der Engine und daran, dass niemand an ihr vorbei
sendet. Beides steht hier.

Der Wächter am Ende ist der wichtigere Teil. Fünf eigene Ollama-Clients sind
nicht aus Nachlässigkeit entstanden, sondern weil es nichts gab, das sie
verhindert hätte — und der sechste entstünde genauso.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import Flask

from shared import ki_engine as ke
from shared.ki_engine import (OHNE_OBJEKT, EgressNichtBestaetigt, Herkunft,
                              KiAuftrag, KiNichtVerfuegbar, budget_fuer, ki_lauf)

WURZEL = Path(__file__).resolve().parents[1]


@pytest.fixture()
def ki_da(monkeypatch):
    """KI verfügbar melden, ohne einen Provider zu konfigurieren."""
    import server.services.prefill as prefill
    monkeypatch.setattr(prefill, "is_ai_available", lambda: (True, ""))


@pytest.fixture()
def antwort(monkeypatch):
    """Synchronen Provider-Aufruf abfangen und das Gesendete festhalten."""
    import ai_compliance_suite.ai.dispatch as d
    gesehen: dict = {}

    class _Resp:
        text = '{"score": 4, "kommentar": "ok"}'
        provider = "on_prem"

    def _fake(**kw):
        gesehen.update(kw)
        return _Resp()

    monkeypatch.setattr(d, "generate_text", _fake)
    monkeypatch.setattr(d, "current_provider_name", lambda: "on_prem")
    return gesehen


def _auftrag(**kw) -> KiAuftrag:
    kw.setdefault("prompt", "Bewerte X.")
    kw.setdefault("herkunft", OHNE_OBJEKT)
    return KiAuftrag(**kw)


# ── Der Auftrag zwingt zu einer Entscheidung ────────────────────────────────

def test_herkunft_ist_pflicht():
    """Das Weglassen darf nichts kosten — genau daran scheiterte #1765.

    Zwei der acht Objektarten wurden nie geschrieben, weil die Aufrufstelle
    den Vermerk schlicht nicht aufrief. Hier geht das nicht: Entweder ein
    Objekt oder ausdrücklich OHNE_OBJEKT.
    """
    with pytest.raises(TypeError):
        KiAuftrag(prompt="x")  # type: ignore[call-arg]
    assert KiAuftrag(prompt="x", herkunft=OHNE_OBJEKT).herkunft is OHNE_OBJEKT
    assert KiAuftrag(prompt="x", herkunft=Herkunft("requirement", "CRA-1")).herkunft.art \
        == "requirement"


def test_jeder_lauf_hat_eine_kennung():
    """Ohne sie ist nicht herstellbar, welcher Provider-Aufruf wozu gehörte."""
    a, b = _auftrag(), _auftrag()
    assert a.lauf_id and b.lauf_id and a.lauf_id != b.lauf_id


# ── Budget: aus Aufgabenart und Menge, nicht aus Gewohnheit ─────────────────

def test_budget_folgt_der_aufgabe():
    assert budget_fuer("bewertung") > budget_fuer("diagnose")
    assert budget_fuer("massenbewertung") > budget_fuer("bewertung")


def test_budget_waechst_mit_der_menge_aber_nicht_grenzenlos():
    """Ein Sammel-Prompt über 80 Objekte braucht mehr — aber nicht das 80-fache."""
    eins = budget_fuer("bewertung", 1)
    viele = budget_fuer("bewertung", 80)
    assert viele > eins
    assert viele < eins * 80


def test_unbekannte_aufgabe_faellt_auf_den_grundwert():
    assert budget_fuer("gibtsnicht") == budget_fuer("sonstiges")


# ── Schritt 1: Verfügbarkeit ────────────────────────────────────────────────

def test_ohne_provider_gibt_es_keinen_aufruf(monkeypatch):
    """Kein stiller Rückfall, und kein Stream, der sofort leer endet."""
    import server.services.prefill as prefill
    monkeypatch.setattr(prefill, "is_ai_available", lambda: (False, "Kein Modell"))
    with pytest.raises(KiNichtVerfuegbar) as e:
        ki_lauf(_auftrag())
    assert "Kein Modell" in str(e.value)


# ── Schritt 2: Egress ───────────────────────────────────────────────────────

def test_egress_pflicht_ohne_bestaetigung(ki_da, antwort):
    app = Flask(__name__)
    with app.test_request_context("/api/cra/x", method="POST", json={}):
        with pytest.raises(EgressNichtBestaetigt):
            ki_lauf(_auftrag(egress_pflicht=True))
    assert not antwort, "Es darf nichts gesendet worden sein"


def test_egress_pflicht_mit_bestaetigung(ki_da, antwort):
    app = Flask(__name__)
    with app.test_request_context("/api/cra/x", method="POST",
                                  json={"confirmed": True}):
        erg = ki_lauf(_auftrag(egress_pflicht=True))
    assert erg.ok


def test_ohne_pflicht_laeuft_es_auch_ohne_bestaetigung(ki_da, antwort):
    """Das Umlegen für alle Wege ist eine eigene, angekündigte Entscheidung.

    Würde die Engine `confirmed` sofort überall verlangen, bekämen 45 Wege ein
    428 und die Anwendung wäre für Anwender zunächst kaputt (#1836/E2).
    """
    app = Flask(__name__)
    with app.test_request_context("/api/cra/x", method="POST", json={}):
        assert ki_lauf(_auftrag()).ok


# ── Schritt 3: die eigenen Hinweise (#1833) ─────────────────────────────────

def test_eigene_hinweise_wirken_in_jedem_lauf(ki_da, antwort):
    """Der Kern des Auftrags: Die Editier-Funktion steckt in der Engine.

    Damit erreicht sie auch die Wege, die vorher eigenen Transport hatten.
    """
    import base64
    from shared import prompt_zusatz as pz

    app = Flask(__name__)
    wert = base64.b64encode("Schwerpunkt: Fertigung.".encode()).decode()
    with app.test_request_context("/api/cra/x", method="POST",
                                  headers={pz.HEADER: wert}):
        ki_lauf(_auftrag(prompt="## Format\nNur JSON."))

    gesendet = antwort["prompt"]
    assert "Schwerpunkt: Fertigung." in gesendet
    assert pz.MARKER_VORRANG in gesendet
    assert gesendet.startswith("## Format")


def test_hinweise_lassen_sich_je_auftrag_abschalten(ki_da, antwort):
    import base64
    from shared import prompt_zusatz as pz

    app = Flask(__name__)
    wert = base64.b64encode("Hinweis".encode()).decode()
    with app.test_request_context("/api/cra/x", method="POST",
                                  headers={pz.HEADER: wert}):
        ki_lauf(_auftrag(prompt="Basis", zusatz_erlaubt=False))
    assert antwort["prompt"] == "Basis"


# ── Schritt 4: Parameter, die ankommen ──────────────────────────────────────

def test_budget_und_temperatur_gehen_an_den_provider(ki_da, antwort):
    ki_lauf(_auftrag(aufgabe="bewertung", antwortform="json"))
    assert antwort["max_output_tokens"] == budget_fuer("bewertung")
    assert antwort["temperature"] == 0.2


def test_prosa_bekommt_eine_andere_temperatur(ki_da, antwort):
    """Extraktion will Reproduzierbarkeit, Formulierung will Sprache."""
    ki_lauf(_auftrag(antwortform="prosa"))
    assert antwort["temperature"] == 0.3


def test_json_wird_jetzt_erzwungen_nicht_nur_erbeten(ki_da, antwort):
    """#1841/E3: `force_json` kommt beim Provider an — auch synchron.

    Vorher wirkte es **nur** im Ollama-Streaming-Zweig; die synchrone
    Schnittstelle (`AITextRequest`) kannte das Feld nicht, und elf
    JSON-erwartende Läufe verließen sich darauf, dass das Modell dem Prompt
    folgt. Dass es gutging, lag an `_repair_truncated_json`.
    """
    ki_lauf(_auftrag(antwortform="json"))
    assert antwort["force_json"] is True
    ki_lauf(_auftrag(antwortform="prosa"))
    assert antwort["force_json"] is False


def test_was_der_provider_nicht_kann_wird_gemeldet(ki_da, antwort, monkeypatch):
    """Anthropic hat keinen JSON-Modus — das wird gesagt, nicht verschwiegen.

    Ein Parameter, der still verfällt, ist schlimmer als keiner: Er wurde
    geschrieben, um etwas sicherzustellen, und sieht danach sichergestellt aus
    (#1836).
    """
    import ai_compliance_suite.ai.dispatch as d
    monkeypatch.setattr(d, "is_cloud_provider", lambda: True)
    monkeypatch.setattr(d, "_load_ai_config",
                        lambda: {"ai": {"provider": "cloud", "cloud": {
                            "base_url": "https://api.anthropic.com/v1"}}})
    assert "force_json" in ki_lauf(_auftrag(antwortform="json")).nicht_abbildbar

    # OpenAI-kompatibel: `response_format` gibt es → nichts zu melden.
    monkeypatch.setattr(d, "_load_ai_config",
                        lambda: {"ai": {"provider": "cloud", "cloud": {
                            "base_url": "https://api.openai.com/v1"}}})
    assert ki_lauf(_auftrag(antwortform="json")).nicht_abbildbar == []


def test_ohne_json_gibt_es_nichts_zu_melden(ki_da, antwort):
    assert ki_lauf(_auftrag(antwortform="prosa")).nicht_abbildbar == []


# ── Schritt 5: Ergebnis in einem Stück ──────────────────────────────────────

def test_json_wird_geparst(ki_da, antwort):
    erg = ki_lauf(_auftrag(antwortform="json"))
    assert erg.ok and erg.parsed["score"] == 4


def test_prosa_wird_nicht_geparst(ki_da, antwort):
    erg = ki_lauf(_auftrag(antwortform="prosa"))
    assert erg.parsed == erg.text


def test_unparsebare_antwort_ist_kein_erfolg(ki_da, monkeypatch):
    import ai_compliance_suite.ai.dispatch as d

    class _Resp:
        text = "das ist kein JSON"
        provider = "on_prem"

    monkeypatch.setattr(d, "generate_text", lambda **_k: _Resp())
    monkeypatch.setattr(d, "current_provider_name", lambda: "on_prem")
    erg = ki_lauf(_auftrag(antwortform="json"))
    assert not erg.ok and "nicht verwertbar" in erg.fehler


def test_provider_fehler_wird_zum_ergebnis_nicht_zur_exception(ki_da, monkeypatch):
    import ai_compliance_suite.ai.dispatch as d

    def _boom(**_k):
        raise RuntimeError("Netz weg")

    monkeypatch.setattr(d, "generate_text", _boom)
    monkeypatch.setattr(d, "current_provider_name", lambda: "on_prem")
    erg = ki_lauf(_auftrag())
    assert not erg.ok and "Netz weg" in erg.fehler


def test_herkunft_wird_vermerkt(ki_da, antwort, monkeypatch):
    """Der Vermerk hängt nicht mehr an der Sorgfalt der Aufrufstelle."""
    import shared.ki_herkunft as kh
    vermerkt = {}
    monkeypatch.setattr(kh, "vermerken",
                        lambda modul, projekt, art, oid, **kw:
                        vermerkt.update(modul=modul, art=art, oid=oid))
    ki_lauf(_auftrag(herkunft=Herkunft("requirement", "CRA-7"),
                     modul="cra", projekt="P", antwortform="json"))
    assert vermerkt == {"modul": "cra", "art": "requirement", "oid": "CRA-7"}


def test_ohne_objekt_wird_nichts_vermerkt(ki_da, antwort, monkeypatch):
    import shared.ki_herkunft as kh
    gerufen = []
    monkeypatch.setattr(kh, "vermerken", lambda *a, **k: gerufen.append(1))
    ki_lauf(_auftrag(antwortform="json"))
    assert not gerufen


def test_ein_revisionseintrag_je_lauf_mit_akteur_und_kennung(ki_da, antwort, monkeypatch):
    import shared.audit as audit
    ereignisse = []
    monkeypatch.setattr(audit, "audit_event",
                        lambda action, *, module, outcome="success", details=None:
                        ereignisse.append((action, module, details or {})))
    a = _auftrag(antwortform="json", modul="cra", aufgabe="bewertung")
    ki_lauf(a)

    laeufe = [d for name, _m, d in ereignisse if name == "ai.lauf"]
    assert len(laeufe) == 1
    d = laeufe[0]
    assert d["lauf_id"] == a.lauf_id      # verbindet Vorgang und Provider-Aufruf
    assert "user_id" in d                  # #1784 — sonst „irgendwer hat gehandelt"
    assert d["aufgabe"] == "bewertung"
    assert d["budget"] == budget_fuer("bewertung")


# ── Der Wächter: niemand sendet an der Engine vorbei ────────────────────────

#: Dateien, die **dürfen** — die Engine selbst und die Transportschicht.
TRANSPORT = {
    "shared/ki_engine.py",
    "ai_compliance_suite/ai/dispatch.py",
    "ai_compliance_suite/ai/provider.py",
    "ai_compliance_suite/ai/streaming.py",
    "ai_compliance_suite/ai/providers/cloud.py",
    "ai_compliance_suite/ai/providers/on_prem.py",
}

#: Wege, die noch eigenen Transport haben — mit Grund. Die Liste ist die
#: verbleibende Schuld aus #1836, nicht die Erlaubnis; sie soll schrumpfen.
WARTET = {
    "compliance_db/local_llm.py":
        "eigenes RAG-Modul der Compliance-DB (eigener Prompt-Aufbau, kein Web-Weg)",
    "compliance_db/gui_module.py":
        "Tkinter-Oberfläche der Compliance-DB, nicht Teil der Web-Anwendung",
    "risikobewertung/prompts.py":
        "generate_discovery_llm bedient die Tkinter-Oberfläche (gui_module)",
    "prefill/engine.py":
        "prefill/api.py ist in server/app.py gar nicht registriert (#1836)",
}

_MUSTER = re.compile(
    r"\b(generate_text|stream_text|stream_generate|generate_ollama)\s*\(")


def _python_dateien():
    for p in WURZEL.rglob("*.py"):
        rel = p.relative_to(WURZEL).as_posix()
        if rel.startswith((".claude/", "tests/", "venv/", ".venv/", "build/")):
            continue
        yield rel, p


def test_kein_neuer_transport_an_der_engine_vorbei():
    """Der sechste eigene Ollama-Client entsteht nicht aus Nachlässigkeit.

    Er entsteht, weil nichts ihn bemerkt. #1836 hat fünf gefunden — zwei davon
    reichten denselben Prompt an eine fremde Systemrolle weiter, ohne dass es
    je jemandem auffiel.
    """
    verstoesse = []
    for rel, pfad in _python_dateien():
        if rel in TRANSPORT or rel in WARTET:
            continue
        text = pfad.read_text(encoding="utf-8", errors="replace")
        for nr, zeile in enumerate(text.split("\n"), 1):
            if zeile.lstrip().startswith("#"):
                continue
            if _MUSTER.search(zeile):
                verstoesse.append(f"{rel}:{nr}")
    assert not verstoesse, (
        "Diese Stellen sprechen direkt mit dem Provider statt über "
        "shared.ki_engine: " + ", ".join(verstoesse)
        + " — entweder auf ki_lauf/ki_lauf_sse umstellen oder in WARTET mit "
          "Grund aufnehmen.")


def test_die_warteliste_nennt_nur_echte_dateien_mit_grund():
    for rel, grund in WARTET.items():
        assert (WURZEL / rel).exists(), f"{rel} gibt es nicht mehr — aus WARTET entfernen"
        assert len(grund) >= 25, f"{rel}: Grund zu knapp"


def test_stream_ai_sse_ist_nur_noch_eine_huelle():
    """Die acht Altaufrufer erben die Engine, ohne geändert zu werden."""
    quelle = (WURZEL / "shared/sse.py").read_text(encoding="utf-8")
    assert "ki_lauf_sse" in quelle
    # Kein eigener Transport mehr: weder Generator-Gerüst noch Provider-Aufruf.
    assert "stream_generate" not in quelle
    assert "yield" not in quelle
