"""Der Nachweis trägt den hochgeladenen Namen (#1982).

DER BEFUND
In der Nachweisliste der Firma standen ``tmpoqguoy01.md`` und
``tmpsx8joof_.md``. Es waren ``02_System-und-Netzdokumentation.md`` und
``05_IT-Administration-Patch-und-Aenderungsmanagement.md`` — die echten Namen
ließen sich nur aus dem **Inhalt** der Dateien zurückgewinnen, in der
Datenbank standen sie nirgends (``source_path`` trug denselben Temp-Pfad).

Beide Upload-Endpunkte berechneten den geprüften Namen und **verwarfen** ihn:
Der Upload ging in eine ``tempfile.NamedTemporaryFile``, übergeben wurde deren
Pfad, und ``add_document`` leitete ``filename = src.name`` ab. Es schlug nichts
fehl — es stand nur das Falsche da. Und der Name ist nicht Beschriftung:
``cra_traceability`` setzt ihn als ``download_name``, ein Anhang-VII-Beleg kam
also als ``tmpoqguoy01.md`` bei der Behörde an.

Der richtige Weg lag im Haus: ``server/api/pentest.py`` legt ein Temp-**Verzeichnis**
an und darin die Datei unter ihrem echten Namen. Zwei Stellen haben ihn nicht
genommen, und das fällt bei einem Upload nicht auf.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]

#: Verzeichnisse, die nicht ausgeliefert werden. ``.claude`` enthält
#: Arbeitskopien früherer Läufe — beim ersten Anlauf meldete dieser Test
#: ``firmen/gui_module.py`` als neuen Aufrufer, eine mit #1955 gelöschte Datei.
NICHT_PRODUKTIONSCODE = {"tests", "node_modules", ".git", "frontend", ".claude",
                         ".github", "tools"}


def _programm(pfad: Path) -> str:
    """Der Quelltext **ohne** Kommentare und Docstrings.

    Beim ersten Anlauf schlug dieser Wächter auf die Kommentarzeile
    „Temporär speichern, dann via add_document() in den Store kopieren" an und
    meldete einen Aufruf ohne ``filename=``. Das ist die Falle, die hier
    viermal steht (#1834/#1867/#1878/#1903): **das Programm prüfen, nicht die
    Erzählung.** ``ast.unparse`` lässt beides weg und schreibt jeden Aufruf in
    eine Zeile — für die Prüfung unten genau richtig.
    """
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    return ast.unparse(baum)

#: Jeder Aufrufer von ``add_document`` mit der Entscheidung dazu. Ein neuer
#: Upload-Endpunkt lässt diesen Test rot werden — die dritte Fundstelle
#: entsteht sonst genauso lautlos wie die zweite.
AUFRUFER = {
    "server/api/firmen.py": "Zwischendatei → `filename=` ist Pflicht",
    "server/api/risikobewertung.py": "Zwischendatei → `filename=` ist Pflicht",
    "server/api/pentest.py": "Temp-Verzeichnis mit echtem Dateinamen darin",
    "cra/ci_evidence_ingest.py": "echte Dateien aus der Fertigungsstrecke",
    "ai_act/ci_evidence_ingest.py": "echte Dateien aus der Fertigungsstrecke",
}

#: Die Stellen, die eine **Zwischendatei** übergeben und den Namen deshalb
#: ausdrücklich mitgeben müssen.
MIT_ZWISCHENDATEI = ("server/api/firmen.py", "server/api/risikobewertung.py")


def test_jeder_aufrufer_steht_mit_seiner_entscheidung_in_der_liste():
    gefunden: set[str] = set()
    for p in WURZEL.rglob("*.py"):
        teile = p.relative_to(WURZEL).parts
        if set(teile) & NICHT_PRODUKTIONSCODE:
            continue
        if p.relative_to(WURZEL).as_posix() == "evidence/db.py":
            continue
        try:
            quelle = _programm(p)
        except SyntaxError:
            continue
        if re.search(r"(?<![_\w])add_document\s*\(", quelle):
            gefunden.add(p.relative_to(WURZEL).as_posix())

    neu = gefunden - set(AUFRUFER)
    assert not neu, (
        "Neue Aufrufer von add_document: " + ", ".join(sorted(neu))
        + ". Übergibt die Stelle eine Zwischendatei, muss sie `filename=` "
          "mitgeben — sonst steht der Temp-Name in der Akte und im "
          "Download (#1982). Eintrag mit Grund in AUFRUFER ergänzen.")
    weg = set(AUFRUFER) - gefunden
    assert not weg, ("Liste nennt Nicht-Aufrufer: " + ", ".join(sorted(weg)))


@pytest.mark.parametrize("datei", MIT_ZWISCHENDATEI)
def test_wer_eine_zwischendatei_uebergibt_nennt_den_namen(datei: str):
    quelle = _programm(WURZEL / datei)
    assert "NamedTemporaryFile" in quelle, (
        f"{datei} nutzt keine Zwischendatei mehr — Liste nachziehen.")
    # Der Aufruf selbst, nicht irgendeine Zeile der Datei: `filename=` muss im
    # `add_document(...)` stehen.
    aufrufe = re.findall(r"add_document\((?:[^()]|\([^()]*\))*\)", quelle)
    assert aufrufe, f"add_document-Aufruf in {datei} nicht gefunden."
    for a in aufrufe:
        assert "filename=" in a, (
            f"{datei}: add_document ohne `filename=` — der Datensatz bekäme "
            f"den Namen der Zwischendatei (#1982).")


def test_der_anzeigename_gewinnt_gegen_den_pfad_der_zwischendatei(tmp_path):
    """Der Rundlauf: ablegen mit Anzeigenamen, auslesen, vergleichen.

    Die Behauptung „der Name kommt an" lässt sich nicht aus dem Quelltext
    ablesen (die Lehre aus #1785) — hier läuft sie durch.
    """
    from evidence.db import add_document, get_document

    quelle = tmp_path / "tmpoqguoy01.md"
    quelle.write_text("# 02 · System- und Netzdokumentation\n", encoding="utf-8")
    db = tmp_path / "evidence.sqlite"

    doc = add_document(db, quelle, store_dir=tmp_path / "store",
                       doc_type="technische_dokumentation",
                       firmen_id="Firma Cyberwoks",
                       filename="02_System-und-Netzdokumentation.md")

    assert doc.filename == "02_System-und-Netzdokumentation.md"
    gelesen = get_document(db, doc.id)
    assert gelesen is not None and gelesen.filename == doc.filename
    assert "tmpoqguoy01" not in doc.stored_path, (
        "Der Ablagepfad trägt noch den Namen der Zwischendatei.")
    assert Path(doc.stored_path).is_file()


def test_ohne_anzeigename_bleibt_es_beim_dateinamen(tmp_path):
    """Die CI-Aufrufer übergeben echte Dateien — für sie ändert sich nichts."""
    from evidence.db import add_document

    quelle = tmp_path / "sbom.cdx.json"
    quelle.write_text("{}", encoding="utf-8")
    doc = add_document(tmp_path / "evidence.sqlite", quelle,
                       store_dir=tmp_path / "store")
    assert doc.filename == "sbom.cdx.json"


@pytest.mark.parametrize("roh,erwartet_anzeige", [
    ("Netzübersicht Büro.pdf", "Netzübersicht Büro.pdf"),   # Umlaute bleiben
    ("unterordner/datei.pdf", "datei.pdf"),                  # Ordner-Upload
    ("../../etc/passwd", "passwd"),                          # Pfadanteile weg
    ("datei\nmit\tumbruch.md", "dateimitumbruch.md"),         # Steuerzeichen weg
])
def test_der_anzeigename_bleibt_lesbar_und_ist_kein_pfad(tmp_path, roh,
                                                         erwartet_anzeige):
    """Anzeigename und Ablagename sind zwei Dinge.

    ``secure_filename`` auf den Anzeigenamen loszulassen wäre die nächste
    Ausprägung derselben Meldung: Aus „Netzübersicht" würde „Netzubersicht".
    Umgekehrt darf der **Ablagename** keine Pfadanteile tragen.
    """
    from evidence.db import _ablagename, add_document

    quelle = tmp_path / "egal.pdf"
    quelle.write_bytes(b"x")
    doc = add_document(tmp_path / "evidence.sqlite", quelle,
                       store_dir=tmp_path / "store", filename=roh)
    assert doc.filename == erwartet_anzeige
    ablage = Path(doc.stored_path).name
    assert "/" not in ablage and ".." not in ablage
    assert Path(doc.stored_path).is_file()
    assert _ablagename("a/../b") == "b"


def test_der_download_nennt_den_anzeigenamen():
    """Der Name ist der ``download_name`` — das ist der Grund, warum er zählt."""
    quelle = (WURZEL / "server" / "api" / "cra_traceability.py").read_text(
        encoding="utf-8")
    assert 'getattr(ev, "filename", None)' in quelle, (
        "Der Belegdownload nimmt den Anzeigenamen nicht mehr aus dem "
        "Nachweis-Datensatz — dann gilt diese Begründung nicht mehr und der "
        "Test gehört angepasst, nicht gelöscht.")
    assert "download_name=name" in quelle.replace(" ", "")
