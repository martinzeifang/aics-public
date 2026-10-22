"""Lange Issue-Inhalte dürfen bei der Übernahme/Bewertung nicht verloren gehen —
verlustfreie KI-Verdichtung mit vollständigem Fallback (kein stilles Abschneiden)."""
import shared.issue_feedback as fb
from server.services.anforderung_prompt import _cap


def test_short_feedback_unchanged():
    assert fb.condense_feedback("kurzer text") == "kurzer text"


def test_long_feedback_without_ai_keeps_full_content(monkeypatch):
    # Kein KI-Provider → generate_text wirft → vollständiger Originaltext zurück.
    import ai_compliance_suite.ai.dispatch as d
    def _boom(**_k):
        raise RuntimeError("kein Provider")
    monkeypatch.setattr(d, "generate_text", _boom)
    long = "Befund A. Anforderung B. Entscheidung C. " * 400  # > Schwelle
    out = fb.condense_feedback(long)
    assert out == long.strip()  # kein Inhaltsverlust


def test_long_feedback_with_ai_is_condensed_and_labeled(monkeypatch):
    import ai_compliance_suite.ai.dispatch as d
    class _Resp:
        text = "- Befund A\n- Anforderung B\n- Entscheidung C"
        provider = "on_prem"
    monkeypatch.setattr(d, "generate_text", lambda **_k: _Resp())
    long = "x" * 20000
    out = fb.condense_feedback(long)
    assert "KI-verdichtet" in out
    assert "Befund A" in out


def test_collect_issue_feedback_condense_flag(monkeypatch):
    # condense=False lässt den Rohtext unangetastet.
    monkeypatch.setattr(fb, "fetch_issue_content_by_url",
                        lambda url, **_k: {"combined": "Z" * 20000})
    text, src = fb.collect_issue_feedback([{"url": "https://github.com/o/r/issues/1"}], condense=False)
    assert len(text) >= 20000 and src[0]["ok"] is True


def test_cap_adds_visible_marker():
    assert _cap("abc", 10) == "abc"
    capped = _cap("y" * 100, 20)
    assert capped.startswith("y" * 20)
    assert "gekürzt" in capped  # sichtbar, nicht still
