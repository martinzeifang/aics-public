"""Die Bewertung eines Risikos nimmt ihm nicht seine Herkunft (#1976).

**Der gemeldete Fall, auf Produktiv nachgemessen.** Zwei Anforderungen
(``IMPL-06``, ``AI2-06``) waren als Abweichung begründet akzeptiert — Kategorie
``restrisiko``, Begründung gesetzt, Risiko bewertet, Verknüpfung in
``risk_requirement_links`` vorhanden. Die Feststellung „CRA-ready" blieb
trotzdem verweigert, weil das Gate beide als *offen* zählte.

Das Änderungsprotokoll der Installation hielt die Ursache minutengenau:

    05.11. 22:24  create  felder._source_id = cra:requirement:IMPL-06   ✓
    06.11. 06:40  update  felder._source_id = (ohne)                    ✗

``save_risiko`` ersetzte ``felder_json`` vollständig, und jeder Bewertungsweg
schickt nur die Felder des Frameworks. **Der erste Speichervorgang nach dem
Anlegen löschte die Herkunft** — die Handlung „Risiko bewerten" nahm der
Akzeptanz ihre Lesbarkeit.

Nichts schlug dabei fehl: Die Maske zeigte „akzeptiert · Restrisiko", das Gate
rechnete „nicht erfüllt und nicht begründet akzeptiert". Dieselbe Klasse wie
#1805, #1820 und #1870 — es wird das Falsche gelesen.

**Dieser Prüfer hat zwei Hälften**, und die zweite ist die wichtigere: Der
Verhaltenstest hält fest, dass die Herkunft ein Teil-Update übersteht. Der
Wächter darunter hält die **Zeichenkette** zusammen, die in einer Datei
geschrieben und in einer anderen gelesen wird (``_source_id``) — die
Spiegel-Liste aus #1731/#1735 in ihrer leisesten Form, wie in #1870.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from risikobewertung.db import _felder_mit_herkunft

WURZEL = Path(__file__).resolve().parents[1]


# ── Verhalten: die Herkunft übersteht ein Teil-Update ───────────────────────

def test_bewertung_ohne_herkunft_laesst_die_herkunft_stehen():
    """Der gemeldete Fall: Bewertungsfelder rein, Herkunft bleibt."""
    bestand = {"_source": "req-gap", "_source_id": "cra:requirement:IMPL-06"}
    bewertung = {"octave_actor": "Intern", "impact_fines": "Hoch"}
    zusammen = _felder_mit_herkunft(bewertung, bestand)
    assert zusammen["_source_id"] == "cra:requirement:IMPL-06"
    assert zusammen["_source"] == "req-gap"
    assert zusammen["octave_actor"] == "Intern"


def test_ausdruecklich_mitgeschickt_gewinnt():
    """Linie aus #1805: Ein genannter Wert wird nicht vom Bestand überstimmt.

    Der Framework-Wechsel (#1577) setzt ``_vorher`` absichtlich, und ein
    Umhängen der Herkunft muss möglich bleiben.
    """
    zusammen = _felder_mit_herkunft(
        {"_source_id": "cra:requirement:AI2-06", "_vorher": {"x": 1}},
        {"_source_id": "cra:requirement:IMPL-06", "_vorher": {"alt": True}})
    assert zusammen["_source_id"] == "cra:requirement:AI2-06"
    assert zusammen["_vorher"] == {"x": 1}


def test_nur_herkunftsschluessel_werden_uebernommen():
    """Ein Bewertungsfeld des alten Frameworks darf **nicht** überleben.

    Nach einem Framework-Wechsel sind die alten Felder gegenstandslos
    (#1577 setzt sie bewusst zurück); sie zurückzuholen wäre eine Bewertung,
    die niemand abgegeben hat.
    """
    zusammen = _felder_mit_herkunft({"stride_x": "neu"},
                                    {"octave_actor": "Intern", "_source": "req-gap"})
    assert "octave_actor" not in zusammen
    assert zusammen["_source"] == "req-gap"


def test_leeres_update_loescht_die_herkunft_nicht():
    """Die Massenübernahme schickt für ein Objekt auch mal ``{}``."""
    assert _felder_mit_herkunft({}, {"_source_id": "cra:requirement:IMPL-06"}) \
        == {"_source_id": "cra:requirement:IMPL-06"}


def test_unbrauchbare_eingaben_brechen_nicht():
    """``felder`` kommt aus einer KI-Antwort — es ist nicht immer ein Objekt."""
    assert _felder_mit_herkunft(None, None) == {}
    assert _felder_mit_herkunft("kein Objekt", {"_source": "req-gap"}) \
        == {"_source": "req-gap"}


def test_save_risiko_ersetzt_felder_nicht_mehr_blind():
    """Der Schutz steckt in der Speicherfunktion, nicht im Aufrufer.

    Geprüft am Programm, nicht an der Erzählung: Der Docstring nennt
    ``_felder_mit_herkunft`` ohnehin.
    """
    programm = _programm(WURZEL / "risikobewertung" / "db.py")
    stelle = programm[programm.index("def save_risiko"):]
    stelle = stelle[:stelle.index("\ndef ", 1)]
    assert "_felder_mit_herkunft(" in stelle, (
        "save_risiko führt die Herkunft nicht mehr nach — der Defekt aus #1976 "
        "ist zurück.")
    assert not re.search(r"json\.dumps\(\s*risk\.get\(\s*[\"']felder[\"']\s*,\s*\{\}\s*\)",
                         stelle), (
        "save_risiko schreibt `felder` wieder vollständig aus der Eingabe.")


# ── Wächter: eine Zeichenkette, zwei Dateien ────────────────────────────────

def _programm(pfad: Path) -> str:
    """Quelltext ohne Docstrings und Kommentare (AST, nicht Regex — #1966)."""
    quelle = pfad.read_text(encoding="utf-8")
    zeilen = quelle.splitlines()
    for knoten in ast.walk(ast.parse(quelle)):
        if not isinstance(knoten, (ast.Module, ast.FunctionDef,
                                   ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        koerper = getattr(knoten, "body", None) or []
        if (koerper and isinstance(koerper[0], ast.Expr)
                and isinstance(koerper[0].value, ast.Constant)
                and isinstance(koerper[0].value.value, str)):
            doc = koerper[0]
            for nr in range(doc.lineno - 1, (doc.end_lineno or doc.lineno)):
                zeilen[nr] = ""
    return re.sub(r"(?m)#.*$", "", "\n".join(zeilen))


def test_schreiber_und_leser_nennen_denselben_schluessel():
    """``_source_id`` entsteht in `shared/req_risks` und wird im CRA-Gate gelesen.

    Benennt eine Seite ihn um, rechnet die Anwendung weiter und meldet jede
    begründete Abweichung als offen — ohne Fehler. Genau diese Lücke hat
    #1870 gekostet.
    """
    schreiber = _programm(WURZEL / "shared" / "req_risks.py")
    leser = _programm(WURZEL / "cra" / "konformitaet_gate.py")
    assert '"_source_id"' in schreiber or "'_source_id'" in schreiber
    assert '"_source_id"' in leser or "'_source_id'" in leser
    # Das Format des Werts: Modul:Art:Objekt — das Gate baut es selbst zusammen.
    assert "cra:requirement:" in leser, (
        "Das Gate baut den Quell-Schlüssel nicht mehr als "
        "`cra:requirement:<ID>` — der Schreiber in shared/req_risks tut es.")
    assert '{modul}:{kind}:{obj_id}' in schreiber, (
        "shared/req_risks setzt `_source_id` nicht mehr als `<modul>:<art>:<id>` "
        "zusammen — das Gate erwartet genau diese Form.")


def test_das_nachtrag_werkzeug_liegt_bereit():
    """Der Code-Fix wirkt nur nach vorn.

    Wer den Defekt hatte, hat Risiken **ohne** Herkunft im Bestand; ohne
    Werkzeug bliebe die Akzeptanz dort unlesbar. Dieselbe Lehre wie B6/#1966:
    Ein Schalter ohne Weg, den Bestand nachzuziehen, ist eine Sackgasse.
    """
    skript = WURZEL / "scripts" / "ops" / "risiko_herkunft_nachtragen.py"
    assert skript.is_file(), "Das Nachtrag-Werkzeug fehlt."
    programm = _programm(skript)
    assert "risk_requirement_links" in programm, (
        "Das Werkzeug liest die Herkunft nicht aus der Verknüpfungstabelle.")
    assert "--nachtragen" in programm, "Kein Trockenlauf als Vorgabe."
    assert "commit()" in programm, (
        "Ohne commit() wäre der ganze Lauf wirkungslos (die Lehre aus #1966).")
