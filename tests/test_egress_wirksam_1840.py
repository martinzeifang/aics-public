"""Die Zustimmung zur Datenübermittlung wirkt (#1840, #1836/E1+E2).

Der Befund aus dem Firefox-Durchlauf: Die Daten-Vorschau (#868) zeigt dem
Anwender, welche Daten an die KI gehen, und verlangt eine Bestätigung. In drei
von vier Dialogen setzte ihr ``@confirm`` ein Feld, **das niemand las** — der
Haken gab nichts frei und sperrte nichts. Daneben lag ein zweites, wirksames
Tor mit anderem Wortlaut.

Dazu die Zählung aus #1836: Von 47 serverseitig sendenden Wegen verlangten
**zwei** eine Bestätigung. Die Masken zeigten die Vorschau und schickten die
Zustimmung nicht mit.

Das ist die dritte Richtung derselben Fehlerklasse: #1805 ein Ereignis ohne
Zuhörer, #1830 ein Zuhörer ohne Funktion, hier ein **Zustand, den niemand
liest**. Alle drei schlagen nicht fehl.

Geprüft wird deshalb beides: dass der Server ohne Bestätigung nicht sendet,
und dass **jede** sendende Maske eine mitschickt. Das Zweite ist das
Wichtigere — die Pflicht im Server ist nur so gut wie die Masken, die sie
bedienen; sonst bekommt der Anwender ein 428 und die Funktion ist kaputt.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import Flask

WURZEL = Path(__file__).resolve().parents[1]
SRC = WURZEL / "frontend" / "src"


# ── Server: ohne Bestätigung geht nichts hinaus ─────────────────────────────

@pytest.fixture()
def ki_da(monkeypatch):
    import server.services.prefill as prefill
    monkeypatch.setattr(prefill, "is_ai_available", lambda: (True, ""))


def test_stream_ai_sse_verlangt_die_bestaetigung(ki_da, monkeypatch):
    """Die Hülle, durch die alle acht Altaufrufer laufen."""
    from ai_compliance_suite.ai import streaming
    from shared.sse import stream_ai_sse

    gesendet = []
    monkeypatch.setattr(streaming, "stream_generate",
                        lambda *a, **k: (gesendet.append(1), iter([{"kind": "done"}]))[1])

    app = Flask(__name__)
    with app.test_request_context("/api/cra/x/stream", method="POST", json={}):
        roh = "".join(stream_ai_sse("sys", "Prompt").response)
    assert not gesendet, "Ohne Bestätigung darf nichts an die KI gehen"
    assert '"ok": false' in roh
    assert "Bestätigung" in roh


def test_mit_bestaetigung_laeuft_es(ki_da, monkeypatch):
    from ai_compliance_suite.ai import streaming
    from shared.sse import stream_ai_sse

    gesendet = []
    monkeypatch.setattr(streaming, "stream_generate",
                        lambda *a, **k: (gesendet.append(1),
                                         iter([{"kind": "done", "provider": "t"}]))[1])
    app = Flask(__name__)
    with app.test_request_context("/api/cra/x/stream", method="POST",
                                  json={"confirmed": True}):
        "".join(stream_ai_sse("sys", "Prompt").response)
    assert gesendet


def test_die_bestaetigung_wird_protokolliert(ki_da, monkeypatch):
    """Eine Zustimmung ohne Spur im Revisionspfad ist keine."""
    from ai_compliance_suite.ai import streaming
    import shared.audit as audit
    from shared.sse import stream_ai_sse

    monkeypatch.setattr(streaming, "stream_generate",
                        lambda *a, **k: iter([{"kind": "done", "provider": "t"}]))
    ereignisse = []
    monkeypatch.setattr(audit, "audit_event",
                        lambda action, *, module, outcome="success", details=None:
                        ereignisse.append((action, details or {})))
    app = Flask(__name__)
    with app.test_request_context("/api/cra/x/stream", method="POST",
                                  json={"confirmed": True}):
        "".join(stream_ai_sse("sys", "Prompt").response)

    egress = [d for name, d in ereignisse if name == "ai.egress.confirmed"]
    assert len(egress) == 1
    # #1784: ohne `user_id` steht dort „irgendwer hat gehandelt".
    assert "user_id" in egress[0]
    assert "lauf_id" in egress[0]


def test_interne_laeufe_bleiben_ohne_pflicht(ki_da, monkeypatch):
    """Die Issue-Verdichtung läuft serverseitig, ohne Maske und ohne Anwender.

    Für sie eine Bestätigung zu verlangen hieße, eine Zustimmung zu erfinden,
    die niemand geben kann — und die Verdichtung fiele still auf den
    Originaltext zurück.
    """
    import ai_compliance_suite.ai.dispatch as d
    import shared.issue_feedback as fb

    class _Resp:
        text = "- kurz"
        provider = "on_prem"

    monkeypatch.setattr(d, "generate_text", lambda **_k: _Resp())
    monkeypatch.setattr(d, "current_provider_name", lambda: "on_prem")
    app = Flask(__name__)
    with app.test_request_context("/api/cra/x", method="POST", json={}):
        out = fb.condense_feedback("y" * 20000)
    assert "KI-verdichtet" in out


# ── Oberfläche: jede sendende Maske schickt eine Zustimmung mit ─────────────

#: Masken, die bewusst keine Zustimmung mitschicken — mit Grund.
OHNE_ZUSTIMMUNG: dict[str, str] = {}

_SENDET = re.compile(r"confirm-egress|confirmEgress|egress-vorbestaetigt"
                     r"|egressVorbestaetigt|confirmed")


def _vue_mit_stream() -> list[tuple[str, str]]:
    """Alle .vue-Dateien, die selbst einen KI-Stream starten."""
    treffer = []
    for p in sorted(SRC.rglob("*.vue")):
        rel = p.relative_to(SRC).as_posix()
        text = p.read_text(encoding="utf-8")
        if rel == "components/shared/KiStreamView.vue":
            continue  # die Ansicht selbst
        startet = ("<KiStreamView" in text) or re.search(r"\brunSse\s*\(", text)
        if startet:
            treffer.append((rel, text))
    return treffer


def test_jede_sendende_maske_schickt_eine_zustimmung():
    """Sonst bekommt der Anwender ein 428 und die Funktion ist kaputt.

    Das ist die Gegenprobe zur Egress-Pflicht im Server: Sie ist nur so gut
    wie die Masken, die sie bedienen.
    """
    offen = [rel for rel, text in _vue_mit_stream()
             if rel not in OHNE_ZUSTIMMUNG and not _SENDET.search(text)]
    assert not offen, (
        "Diese Masken starten einen KI-Stream, schicken aber keine Zustimmung "
        "mit: " + ", ".join(offen)
        + " — `confirm-egress` setzen (eigenes Tor), `egress-vorbestaetigt` "
          "(Aufrufer hat bestätigt) oder `confirmed: true` in den Body.")


def test_mindestens_zwoelf_masken_sind_erfasst():
    """Ein Wächter, der nichts findet, prüft nichts.

    Fiele die Erkennung aus (etwa weil die Komponente umbenannt wird), wäre
    der Test oben leer und grün.
    """
    assert len(_vue_mit_stream()) >= 12


def test_die_warteliste_traegt_gruende():
    for rel, grund in OHNE_ZUSTIMMUNG.items():
        assert (SRC / rel).exists(), f"{rel} gibt es nicht mehr"
        assert len(grund) >= 25, f"{rel}: Grund zu knapp"


# ── Das totgelegte Feld wird wieder gelesen ────────────────────────────────

# Seit #1848 liegt das Tor im geteilten KI-Baustein: Die Masken binden
# `KiBewertungsBlock` ein, und **dort** sperrt `wizard.bestaetigt` den Knopf
# „⚡ Direkt mit KI". Das ist nicht weniger Prüfung, sondern mehr — vorher
# hatten OWASP-LLM und WiBA überhaupt kein Tor, und jetzt erben sie es. Der
# Wächter prüft deshalb den Baustein; die Masken führt
# `test_jede_ki_maske_nutzt_den_geteilten_baustein` in
# `test_geteilte_bausteine_1847_1848.py`.
GEGATET = {
    "components/shared/KiBewertungsBlock.vue": "wizard.bestaetigt",
    "views/gutachten/GerichtsgutachtenView.vue": "wizardModal.confirmed",
}


@pytest.mark.parametrize("rel,feld", sorted(GEGATET.items()))
def test_das_bestaetigungsfeld_wirkt(rel: str, feld: str):
    """`confirmed` wurde gesetzt und nirgends gelesen — jetzt gatet es."""
    text = (SRC / rel).read_text(encoding="utf-8")
    assert f':egress-vorbestaetigt="{feld}"' in text, (
        f"{rel}: {feld} wird gesetzt, aber nicht als Tor benutzt — genau der "
        "Zustand aus #1840.")


def test_das_wizard_modal_sperrt_bis_zur_bestaetigung():
    """Der Knopf „⚡ Direkt mit KI" darf nicht vor der Zustimmung laufen."""
    text = (SRC / "components/shared/WizardPromptModal.vue").read_text(encoding="utf-8")
    # Ohne Kommentare prüfen (Lehre aus #1833/#1834: Wächter springen sonst
    # auf die Erzählung an statt auf das Programm).
    code = "\n".join(z for z in text.split("\n") if not z.lstrip().startswith("//"))
    code = re.sub(r"<!--.*?-->", "", code, flags=re.S)
    assert "egressVorbestaetigt === false" in code


# ── Abbruch (#1836/E1) ─────────────────────────────────────────────────────

def test_die_stream_ansicht_hat_einen_stopp_knopf():
    """Der AbortController lag da; es fehlte der Knopf.

    Betrifft alle Einbindungen gleichzeitig — auch die längsten Läufe
    (Pentest-Extraktion in 16k-Scheiben).
    """
    text = (SRC / "components/shared/KiStreamView.vue").read_text(encoding="utf-8")
    code = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    assert "ks-stop" in code
    assert "function stop()" in code
    assert "abort?.abort()" in code.split("function stop()")[1][:200]
