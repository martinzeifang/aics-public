"""Zwei Läufe, und die Abweichung ist das Signal (#1863).

Die drei Eigenschaften, auf die es ankommt:

1. **Kein Mehrheitsentscheid.** Der erste Lauf bleibt maßgeblich, auch wenn
   zwei weitere etwas anderes sagen. Was richtig ist, entscheidet ein Mensch
   (#1773) — die Funktion stellt nur fest, dass die Antwort nicht stabil ist.
2. **Ein Technikfehler ist kein fachlicher Befund.** Scheitert der
   Kontrolllauf am Provider, ist das Ergebnis ``einig=None`` („nicht geprüft"),
   nicht ``False`` („uneinig"). Sonst sammelt die Arbeitsliste Fehlalarme, und
   ein Prüfer, dessen Ausgabe man nicht mehr liest, prüft nichts (#1805).
3. **Der Kontrolllauf erzeugt keinen Inhalt.** Er trägt deshalb keinen
   Herkunftsvermerk (#1765) und eine eigene Lauf-Kennung — sonst wären die
   Einträge im Revisionspfad nicht auseinanderzuhalten.
"""
from __future__ import annotations

import pytest

from shared.ki_engine import OHNE_OBJEKT, Herkunft, KiAuftrag, KiErgebnis
from shared.ki_mehrlauf import kontrolle_gewuenscht, kontrolllauf


def _auftrag() -> KiAuftrag:
    return KiAuftrag(prompt="P", herkunft=Herkunft("requirement", "CRA-1"),
                     antwortform="json", aufgabe="bewertung", modul="cra",
                     projekt="Projekt")


def _erg(score: int, ok: bool = True) -> KiErgebnis:
    return KiErgebnis(ok=ok, text="{}", parsed={"score": score}, provider="on_prem")


def _wert(parsed) -> str:
    return str((parsed or {}).get("score", ""))


# ── Einigkeit ───────────────────────────────────────────────────────────────

def test_zwei_gleiche_laeufe_sind_einig(monkeypatch):
    monkeypatch.setattr("shared.ki_mehrlauf.ki_lauf", lambda a: _erg(4))
    ml = kontrolllauf(_auftrag(), wert=_wert, erster=_erg(4))
    assert ml.einig is True
    assert ml.abweichung == ""
    assert ml.ergebnis.parsed == {"score": 4}


def test_abweichende_laeufe_werden_gemeldet(monkeypatch):
    monkeypatch.setattr("shared.ki_mehrlauf.ki_lauf", lambda a: _erg(2))
    ml = kontrolllauf(_auftrag(), wert=_wert, erster=_erg(4))
    assert ml.einig is False
    assert ml.abweichung == "4 vs. 2"
    # Maßgeblich bleibt der erste Lauf — die Abweichung ist ein Hinweis, kein
    # Ersatz.
    assert ml.ergebnis.parsed == {"score": 4}


def test_ein_einzelner_lauf_ist_kein_befund(monkeypatch):
    """``n=1`` → ``einig=None``. „Nicht geprüft“ ist nicht „einig“."""
    monkeypatch.setattr("shared.ki_mehrlauf.ki_lauf",
                        lambda a: pytest.fail("darf nicht laufen"))
    ml = kontrolllauf(_auftrag(), wert=_wert, erster=_erg(4), n=1)
    assert ml.einig is None
    assert ml.abweichung == ""


# ── Kein Mehrheitsentscheid ─────────────────────────────────────────────────

def test_kein_mehrheitsentscheid(monkeypatch):
    """Zwei Kontrollläufe sagen 2, der erste sagt 4 — maßgeblich bleibt 4.

    Ein Mehrheitsentscheid wäre die Maschine, die entscheidet. Genau das
    schließt die Leitplanke aus #1773 aus.
    """
    monkeypatch.setattr("shared.ki_mehrlauf.ki_lauf", lambda a: _erg(2))
    ml = kontrolllauf(_auftrag(), wert=_wert, erster=_erg(4), n=3)
    assert ml.ergebnis.parsed == {"score": 4}
    assert ml.einig is False
    assert ml.werte == ["4", "2", "2"]


# ── Technikfehler ───────────────────────────────────────────────────────────

def test_fehlgeschlagener_kontrolllauf_meldet_keine_abweichung(monkeypatch):
    monkeypatch.setattr("shared.ki_mehrlauf.ki_lauf",
                        lambda a: KiErgebnis(ok=False, fehler="Provider weg"))
    ml = kontrolllauf(_auftrag(), wert=_wert, erster=_erg(4))
    assert ml.einig is None, "Ein Provider-Fehler macht den ersten Lauf nicht falsch"
    assert ml.abweichung == ""
    # Und die Werteliste bleibt sauber: Ein gescheiterter Lauf hat keinen Wert
    # und darf keinen leeren Platzhalter hinterlassen — sonst stünde in der
    # Oberfläche „4 vs. “. (Die erste Fassung dieses Tests prüfte nur `einig`
    # und blieb grün, als die Schutzzeile entfernt wurde: `_wert_sicher` fängt
    # den Fall ein zweites Mal. Ein Wächter, der die Probe aufs Exempel
    # übersteht, prüft nicht das, was er behauptet.)
    assert ml.werte == ["4"], ml.werte


def test_unparsebare_antwort_meldet_keine_abweichung(monkeypatch):
    """Ein Parserfehler im Wert-Callback ist ebenfalls kein Befund."""
    def kaputt(parsed):
        raise ValueError("kein score")
    monkeypatch.setattr("shared.ki_mehrlauf.ki_lauf", lambda a: _erg(2))
    ml = kontrolllauf(_auftrag(), wert=kaputt, erster=_erg(4))
    assert ml.einig is None


# ── Herkunft und Lauf-Kennung ───────────────────────────────────────────────

def test_kontrolllauf_ohne_herkunft_und_mit_eigener_kennung(monkeypatch):
    gesehen: list[KiAuftrag] = []

    def fake(a: KiAuftrag) -> KiErgebnis:
        gesehen.append(a)
        return _erg(4)

    monkeypatch.setattr("shared.ki_mehrlauf.ki_lauf", fake)
    a = _auftrag()
    kontrolllauf(a, wert=_wert, erster=_erg(4), n=3)

    assert len(gesehen) == 2
    for k in gesehen:
        assert k.herkunft is OHNE_OBJEKT, (
            "Der Kontrolllauf erzeugt keinen Inhalt am Objekt — er darf die "
            "Herkunft nicht vermerken (#1765).")
    kennungen = {k.lauf_id for k in gesehen} | {a.lauf_id}
    assert len(kennungen) == 3, (
        "Jeder Lauf braucht eine eigene Kennung, sonst sind die Einträge im "
        "Revisionspfad nicht auseinanderzuhalten.")
    # Der Auftrag des Aufrufers bleibt unberührt (dataclasses.replace).
    assert a.herkunft != OHNE_OBJEKT


def test_erster_lauf_wird_selbst_gefahren_wenn_keiner_uebergeben_ist(monkeypatch):
    """Ohne ``erster`` macht die Funktion alle Läufe — dann trägt der erste die
    Herkunft, denn sein Ergebnis wird gespeichert."""
    gesehen: list[KiAuftrag] = []
    monkeypatch.setattr("shared.ki_mehrlauf.ki_lauf",
                        lambda a: (gesehen.append(a), _erg(3))[1])
    ml = kontrolllauf(_auftrag(), wert=_wert, n=2)
    assert len(gesehen) == 2
    assert isinstance(gesehen[0].herkunft, Herkunft)
    assert gesehen[1].herkunft is OHNE_OBJEKT
    assert ml.einig is True


# ── Der Schalter kommt aus dem Request ──────────────────────────────────────

def test_kontrolle_gewuenscht_ohne_request():
    assert kontrolle_gewuenscht() is False


def test_kontrolle_gewuenscht_aus_body_und_query():
    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context(json={"kontrolle": True}):
        assert kontrolle_gewuenscht() is True
    with app.test_request_context(json={"kontrolle": False}):
        assert kontrolle_gewuenscht() is False
    with app.test_request_context(json={}):
        assert kontrolle_gewuenscht() is False
    with app.test_request_context("/?kontrolle=1"):
        assert kontrolle_gewuenscht() is True


def test_der_schalter_wird_an_einer_stelle_gelesen():
    """Sechs Bewertungs-Streams, die ihn einzeln durchreichen, wären die
    Spiegel-Liste aus #1731/#1735 — beim siebten fehlte er wieder."""
    from pathlib import Path
    wurzel = Path(__file__).resolve().parents[1]
    for pfad in ("server/api/cra/__init__.py", "server/api/nis2.py",
                 "server/api/aiact.py", "server/api/dsgvo.py"):
        text = (wurzel / pfad).read_text(encoding="utf-8")
        assert "kontrolle=" not in text, (
            f"{pfad}: reicht den Kontrollschalter selbst durch — er wird in "
            "`ki_mehrlauf.kontrolle_gewuenscht` gelesen.")
