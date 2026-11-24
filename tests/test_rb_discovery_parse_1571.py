"""#1571: Risiken-Assistent — Parser akzeptiert auch Direkt-KI-Antworten mit eingebettetem Array."""
import pytest

from risikobewertung.prompts import parse_discovery_antwort


def test_array_unveraendert():
    r = parse_discovery_antwort('[{"risk_name": "A", "beschreibung": "x"}]')
    assert r == [{"risk_name": "A", "beschreibung": "x"}]


def test_objekt_mit_eingebettetem_array():
    raw = '```json\n{"risiken": [{"risk_name": "Bias", "beschreibung": "b"}, {"risk_name": "Drift"}]}\n```'
    r = parse_discovery_antwort(raw)
    assert [x["risk_name"] for x in r] == ["Bias", "Drift"]


def test_objekt_ohne_liste_bleibt_fehler():
    with pytest.raises(ValueError):
        parse_discovery_antwort('{"risk_name": "A"}')


def test_eu_ai_act_prompt_rolle():
    from risikobewertung.prompts import build_discovery_prompt
    kw = dict(anwendung="Chatbot", risikobereich="", schutzziele=[], beschreibung="",
              anhang_texte=[], n_risiken=5)
    ai = build_discovery_prompt(framework="EU-AI-Act", **kw)
    assert "KI-Risikomanagement nach EU AI Act" in ai and "CRA-Experte" not in ai
    assert "KI-Risiken" in ai
    stride = build_discovery_prompt(framework="STRIDE", **kw)
    assert "CRA-Experte" in stride and "Sicherheitsrisiken" in stride
