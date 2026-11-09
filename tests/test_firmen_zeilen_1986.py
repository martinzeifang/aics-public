"""Wer die Firmenzeilen will, bekommt die Zeilen (#1986).

DER BEFUND
``firmen.db.list_firmen_rows`` liefert ein **Tupel** ``(zeilen, gesamtzahl)`` —
die Projektliste braucht beides für ihre Paginierung (#1709). Vier Stellen im
Haus haben das Tupel **iteriert**:

    for zeile in _fdb.list_firmen_rows(pfad):
        if int(zeile.get("id") or 0) == fid:      # `zeile` ist eine LISTE

Herausgekommen sind zwei Durchläufe — erst die Liste, dann die Zahl —, in
beiden ein ``AttributeError``, und alle vier Stellen fingen ihn weg. Die Folge
war jedes Mal „nicht gefunden", und zwar lautlos:

- ``shared/sprache.firma_sprache`` und ``firma_sprache_nach_name`` lieferten
  **immer** ``""``. Damit war die **Inhaltssprache eines Mandanten** (#1954)
  dauerhaft unwirksam: Berichte, Dokumente und KI-Antworten blieben in der
  Standardsprache, auch wenn an der Firma Englisch gesetzt war. Gemessen: eine
  Firma mit ``sprache='en'`` ergab ``''``.
- ``shared/sprache.sprachen_fuer_projekt`` fiel in seinen ``except``-Zweig.
- ``shared/nachziehen._firma_von`` lieferte ``""`` → die firmenweiten Anlässe
  in „Was ist überholt?" wurden nie zugeordnet. Genau die Brücke, die #1870
  gebaut hat.
- Dazu meine eigene, neue Stelle in ``shared/evidence_context`` (#1985) — ich
  bin in dieselbe Falle gelaufen, einen Tag nach dem Befund, der sie
  beschreibt.

DIE ENTSCHEIDUNG
Eine Regel „bitte richtig entpacken" hat vier Mal nicht getragen. Deshalb gibt
es ``firmen_zeilen()``: Eine Funktion, die das Richtige zurückgibt, muss man
nicht befolgen. ``list_firmen_rows`` bleibt für den einen Aufrufer, der die
Gesamtzahl wirklich braucht.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Nur diese Dateien dürfen das Tupel-API benutzen, je mit Grund.
TUPEL_ERLAUBT = {
    "firmen/db.py": "Definition + firmen_zeilen() selbst",
    "server/api/firmen.py": "braucht die Gesamtzahl für die Paginierung (#1709)",
}

NICHT_PRODUKTIONSCODE = {"tests", "node_modules", ".git", "frontend", ".claude",
                         ".github", "tools"}


def _programm(pfad: Path) -> str:
    """Quelltext ohne Kommentare und Docstrings.

    Nötig, weil der Docstring von ``firmen_zeilen`` den falschen Aufruf
    **zitiert** — ein Wächter auf dem Rohtext würde darauf anspringen. Die
    Falle steht hier viermal (#1834/#1867/#1878/#1903).
    """
    return ast.unparse(ast.parse(pfad.read_text(encoding="utf-8")))


def test_nur_benannte_stellen_benutzen_das_tupel_api():
    treffer: set[str] = set()
    for p in WURZEL.rglob("*.py"):
        if set(p.relative_to(WURZEL).parts) & NICHT_PRODUKTIONSCODE:
            continue
        try:
            quelle = _programm(p)
        except SyntaxError:
            continue
        if re.search(r"(?<![_\w])list_firmen_rows\s*\(", quelle):
            treffer.add(p.relative_to(WURZEL).as_posix())

    neu = treffer - set(TUPEL_ERLAUBT)
    assert not neu, (
        "Diese Stellen rufen list_firmen_rows und bekommen ein Tupel "
        "(zeilen, gesamtzahl): " + ", ".join(sorted(neu))
        + ". Wer nur die Zeilen braucht, nimmt `firmen.db.firmen_zeilen()` — "
          "ein iteriertes Tupel liefert erst eine Liste und dann eine Zahl, "
          "und beide haben kein .get() (#1986).")


def test_firmen_zeilen_liefert_zeilen_und_kein_tupel(tmp_path):
    from firmen import db as fdb

    p = tmp_path / "firmen.sqlite"
    fdb.ensure_db(p)
    fdb.save_firma(p, "Englische GmbH", unternehmen="Englische GmbH",
                   sprache="en")

    zeilen = fdb.firmen_zeilen(p)
    assert isinstance(zeilen, list)
    assert zeilen and isinstance(zeilen[0], dict), (
        "firmen_zeilen darf nicht wieder ein Tupel durchreichen.")
    assert zeilen[0]["name"] == "Englische GmbH"
    # Das Tupel-API bleibt, wie es ist — es hat einen Aufrufer mit Grund.
    roh = fdb.list_firmen_rows(p)
    assert isinstance(roh, tuple) and len(roh) == 2


def test_die_inhaltssprache_des_mandanten_kommt_an(tmp_path):
    """Der Rundlauf, der gefehlt hat.

    Nicht die Teilfunktion, sondern die Aussage: *an der Firma steht Englisch,
    also ist die Inhaltssprache Englisch.* Sie stand nirgends unter Prüfung,
    und deshalb ist sie ein halbes Jahr lang nicht eingetreten.
    """
    from firmen import db as fdb
    from shared import sprache as sp

    p = tmp_path / "firmen.sqlite"
    fdb.ensure_db(p)
    fdb.save_firma(p, "Englische GmbH", unternehmen="Englische GmbH",
                   sprache="en")
    fid = fdb.firmen_zeilen(p)[0]["id"]

    assert sp.firma_sprache(p, fid) == "en", (
        "Die Inhaltssprache des Mandanten kommt nicht an (#1954/#1986).")
    assert sp.firma_sprache_nach_name(p, "Englische GmbH") == "en"


def test_eine_firma_ohne_sprache_bleibt_leer(tmp_path):
    """Die Gegenrichtung: nicht gesetzt heißt nicht gesetzt.

    Ohne diesen Test wäre ein `return "en"` genauso grün wie der Fix.
    """
    from firmen import db as fdb
    from shared import sprache as sp

    p = tmp_path / "firmen.sqlite"
    fdb.ensure_db(p)
    fdb.save_firma(p, "Deutsche GmbH", unternehmen="Deutsche GmbH")
    fid = fdb.firmen_zeilen(p)[0]["id"]

    assert sp.firma_sprache(p, fid) == ""
    assert sp.firma_sprache(p, 999999) == ""
    assert sp.firma_sprache_nach_name(p, "Gibt Es Nicht") == ""
