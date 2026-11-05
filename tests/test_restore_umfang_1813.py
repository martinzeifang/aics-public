"""Beim Einspielen entscheidet der Betreiber, was ersetzt wird (#1813, #1809).

Aus dem Betrieb: Ein Archiv der Testinstanz wurde auf der Produktivinstallation
eingespielt. Danach waren nicht nur elf von zwölf Mandanten weg — die Konten
waren durch die der Quelle **ersetzt**, samt deren Passkeys. Weil ein Passkey
an die Domain gebunden ist, verlangte das übernommene Konto einen zweiten
Faktor, der unter dem neuen Hostnamen nicht funktioniert: Der Betreiber war
aus seiner eigenen Installation ausgesperrt.

Zwei Lehren, beide hier festgehalten:

* **Konten gehören zur Installation, nicht zu den Daten.** Wer eine Sicherung
  einer anderen Installation übernimmt, will fast nie deren Zugänge — und
  merkt es erst, wenn er sich nicht mehr anmelden kann.
* **Eine Rückfrage ohne Zahlen ist keine Warnung.** Die Anwendung wusste, dass
  das Archiv eine Firma enthält und das Ziel zwölf. Gesagt hat sie es nicht.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from shared.backup import paket


# ── Der Umfang ──────────────────────────────────────────────────────────────

def test_installations_schemata_sind_benannt():
    """Konten, Audit-Trail und Zeitpläne gehören zur Installation."""
    assert paket.INSTALLATIONS_SCHEMATA == frozenset({"users", "audit", "scheduler"})


@pytest.mark.parametrize("schema,fachdaten,alles,nur_benutzer", [
    ("cra", True, True, False),
    ("firmen", True, True, False),
    ("evidence", True, True, False),
    ("risikobewertung", True, True, False),
    ("users", False, True, True),
    ("audit", False, True, False),
    ("scheduler", False, True, False),
])
def test_umfang_entscheidet_je_schema(schema, fachdaten, alles, nur_benutzer):
    assert paket._schema_gewollt(schema, "fachdaten") is fachdaten
    assert paket._schema_gewollt(schema, "alles") is alles
    assert paket._schema_gewollt(schema, "nur_benutzer") is nur_benutzer


def test_unbekannter_umfang_wird_abgelehnt(tmp_path):
    """Ein Tippfehler darf nicht stillschweigend zum Vollumfang führen."""
    leer = tmp_path / "x.zip"
    leer.write_bytes(b"PK\x05\x06" + b"\0" * 18)
    with pytest.raises(ValueError, match="Unbekannter Umfang"):
        paket.stelle_wieder_her(leer, umfang="halb")


def test_vorgabe_bleibt_vollumfang():
    """`alles` als Vorgabe: Vorhandene Aufrufer und gespeicherte Abläufe
    sollen sich nicht stillschweigend anders verhalten. Die *Oberfläche*
    wählt `fachdaten` vor — das ist eine Anzeige-Entscheidung, keine
    Verhaltensänderung in der Bibliothek."""
    sig = inspect.signature(paket.stelle_wieder_her)
    assert sig.parameters["umfang"].default == "alles"


# ── Die Vorschau ────────────────────────────────────────────────────────────

def test_vergleiche_nennt_die_positionen():
    """Die Vorschau muss die Dinge nennen, die ein Betreiber vermisst."""
    quelle = inspect.getsource(paket)
    for erwartet in ("Mandanten", "Benutzerkonten", "Nachweisdokumente"):
        assert erwartet in quelle, f"'{erwartet}' fehlt in der Vorschau"
    assert "verlust" in quelle, "Die Vorschau beziffert den Verlust nicht"


def test_vorschau_respektiert_den_umfang():
    """Bei `fachdaten` dürfen Konten nicht als betroffen gemeldet werden —
    sonst warnt die Anzeige vor etwas, das gar nicht passiert."""
    q = inspect.getsource(paket.vergleiche)
    assert "_schema_gewollt" in q
    assert "installation_unberuehrt" in q


# ── Die REST-Schicht ────────────────────────────────────────────────────────

def test_endpunkte_kennen_umfang_und_vorschau():
    quelle = Path("server/api/admin.py").read_text(encoding="utf-8")
    assert "/backup/<backup_id>/vorschau" in quelle, "Kein Vorschau-Endpunkt"
    assert "umfang=umfang" in quelle, "Der Umfang wird nicht durchgereicht"
    assert "'umfang': umfang" in quelle or '"umfang": umfang' in quelle, \
        "Die Antwort nennt den verwendeten Umfang nicht"


def test_restore_wird_mit_umfang_protokolliert():
    """Wer was ersetzt hat, ist nach einem Vorfall die erste Frage."""
    quelle = Path("server/api/admin.py").read_text(encoding="utf-8")
    stelle = quelle[quelle.index("admin.backup.restored"):][:400]
    assert "umfang" in stelle, "Der Audit-Eintrag hält den Umfang nicht fest"


def test_sicherheitskopie_bleibt_pflicht():
    """Die `pre_restore_*`-Kopie hat den Fall vom 24.10. gerettet — sie bleibt."""
    quelle = Path("server/api/admin.py").read_text(encoding="utf-8")
    assert "pre_restore_" in quelle
    assert "ohne_sicherheitskopie" in quelle, \
        "Der Verzicht muss eine ausdrückliche Entscheidung bleiben"


def test_vorschau_zaehlt_datensaetze_nicht_zeilen(tmp_path):
    """Eine falsche Zahl in einer Warnung ist schlimmer als keine.

    CSV-Felder dürfen Zeilenumbrüche enthalten, und genau die Felder, um die es
    hier geht, tun das — eine Projekt- oder Firmenbeschreibung ist oft
    mehrzeilig. Über ``count("\\n")`` gezählt wäre die Zahl im Archiv überhöht
    und der gemeldete Verlust kleingerechnet: Der Dialog hätte „kein Verlust"
    gezeigt, wo Mandanten verschwinden.
    """
    import zipfile

    archiv = tmp_path / "mehrzeilig.zip"
    with zipfile.ZipFile(archiv, "w") as zf:
        # Drei Datensätze, einer davon mit einem Umbruch im zweiten Feld.
        zf.writestr("db/firmen/firmen.csv",
                    '"1","A","einzeilig"\n'
                    '"2","B","erste Zeile\nzweite Zeile\ndritte Zeile"\n'
                    '"3","C","einzeilig"\n')

    with zipfile.ZipFile(archiv, "r") as zf:
        assert paket._zeilen_im_archiv(zf, "db/firmen/firmen.csv") == 3
