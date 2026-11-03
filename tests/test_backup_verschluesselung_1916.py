"""#1916 — Sicherungen werden verschlüsselt.

Eine Sicherung ist ein vollständiger Abzug des Datenbestands: alle Mandanten,
alle Nachweisdokumente, die Benutzertabelle, die Live-Konfiguration. Sie lag
unverschlüsselt im Dateisystem und ließ sich seit #1784 herunterladen — bei
einem Werkzeug, das Nachweisakten für Dritte führt, der schwerste denkbare
Vertraulichkeitsverlust (Anhang I Teil I Nr. 2 Buchst. e, im Verzeichnis
**B2**).

Geprüft wird der **Rundlauf**, nicht die Behauptung (die Lehre aus #1785): Es
gibt keine Zeile Quelltext, aus der sich ablesen lässt, dass ein Archiv nach
dem Verschlüsseln und Entschlüsseln byte-gleich ist.
"""

from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

import pytest

_WURZEL = Path(__file__).resolve().parents[1]
_SCHLUESSEL = "probe-schluessel-fuer-den-rundlauf"


@pytest.fixture()
def key(monkeypatch):
    monkeypatch.setenv("AICS_BACKUP_KEY", _SCHLUESSEL)
    return _SCHLUESSEL


# ── Rundlauf ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("groesse", [0, 1, 1024])
def test_rundlauf_kleine_dateien(tmp_path, key, groesse) -> None:
    from shared.backup.verschluesselung import entschluessele, verschluessele
    daten = secrets.token_bytes(groesse)
    (tmp_path / "ein").write_bytes(daten)
    verschluessele(tmp_path / "ein", tmp_path / "enc")
    entschluessele(tmp_path / "enc", tmp_path / "aus")
    assert (tmp_path / "aus").read_bytes() == daten


def test_rundlauf_ueber_mehrere_bloecke(tmp_path, key, monkeypatch) -> None:
    """Die Blockgrenze ist die Stelle, an der ein Formatfehler auffällt."""
    import shared.backup.verschluesselung as v
    monkeypatch.setattr(v, "BLOCKGROESSE", 4096, raising=True)
    daten = secrets.token_bytes(4096 * 3 + 7)
    (tmp_path / "ein").write_bytes(daten)
    info = v.verschluessele(tmp_path / "ein", tmp_path / "enc")
    assert info["bloecke"] == 4
    v.entschluessele(tmp_path / "enc", tmp_path / "aus")
    assert (tmp_path / "aus").read_bytes() == daten


def test_der_mehraufwand_bleibt_klein(tmp_path, key) -> None:
    """Fernet (``AICSENC1``) base64-kodiert und bläht um ein Drittel — das war
    einer der beiden Gründe gegen das vorhandene Format."""
    from shared.backup.verschluesselung import BLOCKGROESSE, verschluessele
    daten = secrets.token_bytes(BLOCKGROESSE + 1000)
    (tmp_path / "ein").write_bytes(daten)
    info = verschluessele(tmp_path / "ein", tmp_path / "enc")
    aufschlag = info["chiffrat_bytes"] - info["klartext_bytes"]
    assert aufschlag < 1024, f"{aufschlag} Byte Mehraufwand ist zu viel"


# ── was schiefgehen muss ─────────────────────────────────────────────────────

def test_falscher_schluessel_wird_abgewiesen(tmp_path, key, monkeypatch) -> None:
    from cryptography.exceptions import InvalidTag
    from shared.backup.verschluesselung import entschluessele, verschluessele
    (tmp_path / "ein").write_bytes(b"geheim")
    verschluessele(tmp_path / "ein", tmp_path / "enc")
    monkeypatch.setenv("AICS_BACKUP_KEY", "ein anderer")
    with pytest.raises(InvalidTag):
        entschluessele(tmp_path / "enc", tmp_path / "aus")


def test_gekuerztes_archiv_faellt_auf(tmp_path, key) -> None:
    """Das Letzter-Block-Kennzeichen in den Zusatzdaten ist der Schutz gegen
    Abschneiden. Ohne es bliebe ein gekürztes Archiv blockweise gültig — und
    ein Archiv, das sich unbemerkt kürzen lässt, ist als Nachweis nichts wert.
    """
    import shared.backup.verschluesselung as v
    (tmp_path / "ein").write_bytes(secrets.token_bytes(v.BLOCKGROESSE * 2))
    v.verschluessele(tmp_path / "ein", tmp_path / "enc")
    roh = (tmp_path / "enc").read_bytes()
    (tmp_path / "kurz").write_bytes(roh[: len(roh) // 2])
    with pytest.raises(ValueError):
        v.entschluessele(tmp_path / "kurz", tmp_path / "aus")


def test_ohne_schluessel_wird_nicht_verschluesselt_sondern_abgebrochen(
        tmp_path, monkeypatch) -> None:
    from shared.backup.verschluesselung import SchluesselFehlt, verschluessele
    monkeypatch.delenv("AICS_BACKUP_KEY", raising=False)
    (tmp_path / "ein").write_bytes(b"x")
    with pytest.raises(SchluesselFehlt):
        verschluessele(tmp_path / "ein", tmp_path / "enc")
    assert not (tmp_path / "enc").exists() or (tmp_path / "enc").stat().st_size == 0


# ── die Entscheidungen, die bleiben müssen ───────────────────────────────────

def test_kein_rueckfall_auf_das_sitzungsgeheimnis() -> None:
    """**B6.** Wer ``JWT_SECRET_KEY`` wechselt, darf nicht nebenbei alle
    Sicherungen unlesbar machen — und ein Schlüssel, der aus der Installation
    abgeleitet wird, liegt mit den Daten im selben Korb.
    """
    quelle = (_WURZEL / "shared" / "backup" / "verschluesselung.py") \
        .read_text(encoding="utf-8")
    ohne_doku = re.sub(r'""".*?"""', "", quelle, flags=re.S)
    ohne_doku = re.sub(r"#.*", "", ohne_doku)
    for verboten in ("JWT_SECRET_KEY", "AICS_AT_REST_KEY"):
        assert verboten not in ohne_doku, (
            f"{verboten} hat im Sicherungsschlüssel nichts zu suchen (B6)."
        )


def test_nur_eine_stelle_oeffnet_archive() -> None:
    """Acht Aufrufer öffneten ``ZipFile(archiv, "r")`` direkt. Hätte jeder die
    Fallunterscheidung selbst bekommen, wäre beim achten die Entschlüsselung
    vergessen worden — und der Fehler hieße „Archiv beschädigt"
    (#1731/#1735)."""
    for name in ("paket.py", "uebernehmen.py"):
        quelle = (_WURZEL / "shared" / "backup" / name).read_text(encoding="utf-8")
        # Docstrings MIT weg, nicht nur `#`-Kommentare: Beim ersten Anlauf
        # schlug dieser Wächter auf den Docstring von `archiv_oeffnen` an, der
        # den alten Zustand zitiert. Vierter Fall derselben Falle in diesem
        # Haus (#1834, #1867, #1903, #1945) — das Programm prüfen, nicht die
        # Erzählung.
        ohne = re.sub(r'"""....*?"""', "", quelle, flags=re.S)
        ohne = re.sub(r"#.*", "", ohne)
        # `archiv_oeffnen` selbst DARF direkt öffnen — es ist die Stelle, die
        # die Fallunterscheidung trifft. Ausgenommen wird der Rumpf
        # ausdrücklich und nicht durch einen anderen Parameternamen: Eine
        # Prüfung, die man durch Umbenennen umgeht, prüft nichts.
        ohne = re.sub(r"def archiv_oeffnen.*?\n(?=\n\ndef )", "", ohne, flags=re.S)
        assert 'zipfile.ZipFile(archiv, "r")' not in ohne, (
            f"{name} öffnet ein Archiv direkt — `archiv_oeffnen` ist die eine Stelle."
        )


def test_liste_entschluesselt_nicht(tmp_path) -> None:
    """Entschlüsseln heißt PBKDF2 mit 200 000 Runden plus das ganze Archiv
    lesen. Für eine Liste über fünf Sicherungen à mehreren Gigabyte wäre das
    Öffnen der Seite ein Minutenvorgang."""
    quelle = (_WURZEL / "server" / "api" / "admin.py").read_text(encoding="utf-8")
    start = quelle.index("def _kurzinfo")
    rumpf = re.sub(r"#.*", "", quelle[start:start + 1800])
    assert "ist_verschluesselt(archiv)" in rumpf
    assert rumpf.index("ist_verschluesselt(archiv)") < rumpf.index("lies_manifest(archiv)"), (
        "Die Prüfung auf Verschlüsselung muss **vor** dem Lesen des Manifests "
        "stehen, sonst wird für jede Zeile der Liste entschlüsselt."
    )


def test_beilege_nennt_das_format_und_kein_geheimnis(key) -> None:
    """Festlegung 4 in ``docs/cra/aufbewahrung.md``: prüfbar ohne die
    Anwendung. Ein Archiv, das nur diese Anwendung lesen kann, ist in zehn
    Jahren wertlos — und zehn Jahre sind die Frist aus Art. 13 Abs. 13."""
    from shared.backup.verschluesselung import beilege_text
    t = beilege_text("archiv_8.3.1_20261102.zip")
    for pflicht in ("AICSBAK1", "PBKDF2", "AES-256-GCM", "Nonce-Präfix",
                    "Art. 13 Abs. 13", "backup_entschluesseln.py"):
        assert pflicht in t, pflicht
    assert _SCHLUESSEL not in t, "die Beilege darf kein Geheimnis enthalten"
    assert os.environ.get("AICS_BACKUP_KEY") not in t.split()


def test_eigenstaendiges_skript_braucht_nur_cryptography() -> None:
    """Der Rückweg von außen darf nicht an der Anwendung hängen."""
    quelle = (_WURZEL / "scripts" / "ops" / "backup_entschluesseln.py") \
        .read_text(encoding="utf-8")
    for verboten in ("from shared", "import shared", "from server", "ai_compliance_suite"):
        assert verboten not in quelle, (
            f"{verboten} macht das Skript von der Anwendung abhängig — "
            "genau das soll es nicht sein."
        )
    assert "os.environ" in quelle and "argv[2]" in quelle, (
        "Der Schlüssel kommt aus der Umgebung, nicht aus der Befehlszeile: "
        "dort stünde er in der Prozessliste und in der Shell-Historie."
    )
