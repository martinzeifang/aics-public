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


# ── Entkopplung vom Master-Schalter (03.11.2026) ─────────────────────────────
#
# Der Grund für diesen Abschnitt steht im Docstring von
# `paket._verschluesselung_gewollt`: Bis 8.3.2 war `enabled` der einzige Weg,
# und er verlangt `AICS_AT_REST_KEY` (#1189) — womit die Feldverschlüsselung
# ihre Schlüsselquelle wechselt und bereits verschlüsselte Token und
# TOTP-Geheimnisse unlesbar werden. Auf Produktiv waren das drei Werte, einer
# davon ein aktiver zweiter Faktor. Deshalb war die Verschlüsselung der
# Sicherungen nirgends eingeschaltet.

def _mit_config(monkeypatch, at_rest: dict) -> None:
    """Die Konfiguration unterschieben, die `_at_rest_config` liest."""
    import ai_compliance_suite.config as c
    monkeypatch.setattr(c, "load_config",
                        lambda *a, **k: {"security": {"at_rest_encryption": at_rest}},
                        raising=True)


def test_der_schluessel_allein_schaltet_ein(monkeypatch) -> None:
    """Der Weg, der auf Produktiv gebraucht wird: nur AICS_BACKUP_KEY."""
    from shared.backup import paket
    _mit_config(monkeypatch, {"enabled": False, "encrypt_backups": True})
    monkeypatch.setenv("AICS_BACKUP_KEY", _SCHLUESSEL)
    assert paket._verschluesselung_gewollt() is True
    assert paket._verschluesselung_erklaert() is False, (
        "Ohne `enabled` darf nichts als *erklärt* gelten — sonst bricht "
        "`erstelle_backup` ab, statt zu verschlüsseln."
    )


def test_ohne_schluessel_bleibt_alles_wie_es_war(monkeypatch) -> None:
    """Die tragende Zusage: Eine Installation ohne Schlüssel schreibt weiter
    klare Sicherungen — ein Update ändert ihr Verhalten nicht."""
    from shared.backup import paket
    _mit_config(monkeypatch, {"enabled": False, "encrypt_backups": True})
    monkeypatch.delenv("AICS_BACKUP_KEY", raising=False)
    assert paket._verschluesselung_gewollt() is False


def test_encrypt_backups_false_sticht_den_schluessel(monkeypatch) -> None:
    """Wer den Schlüssel in der Umgebung haben will, ohne zu verschlüsseln,
    hat genau diesen einen Schalter."""
    from shared.backup import paket
    _mit_config(monkeypatch, {"enabled": False, "encrypt_backups": False})
    monkeypatch.setenv("AICS_BACKUP_KEY", _SCHLUESSEL)
    assert paket._verschluesselung_gewollt() is False


def test_erklaert_ohne_schluessel_bricht_weiter_ab(monkeypatch) -> None:
    """Der Fail-Closed-Fall aus #1916 bleibt: Liegt die Zusage vor und fehlt
    der Schlüssel, entsteht keine klare Sicherung."""
    from shared.backup import paket
    _mit_config(monkeypatch, {"enabled": True, "encrypt_backups": True})
    monkeypatch.delenv("AICS_BACKUP_KEY", raising=False)
    assert paket._verschluesselung_erklaert() is True
    assert paket._verschluesselung_gewollt() is True, (
        "Damit `erstelle_backup` den Abbruch auslöst, muss der erklärte Weg "
        "weiter als *gewollt* gelten."
    )


def test_sicherungen_brauchen_den_at_rest_schluessel_nicht() -> None:
    """Der Kern der Entkopplung, als Wächter.

    `AICS_BACKUP_KEY` hat keinen Rückfall — die Begründung von #1189
    (Signatur- und Verschlüsselungsschlüssel nicht koppeln) trifft auf die
    Sicherungen gar nicht zu. Wer `AICS_AT_REST_KEY` wieder zur Bedingung
    macht, macht die Umsetzung auf einer Bestandsinstallation unmöglich.
    """
    import inspect

    from shared.backup import paket
    quelle = inspect.getsource(paket._verschluesselung_gewollt)
    programm = re.sub(r'""".*?"""', "", quelle, flags=re.S)
    programm = re.sub(r"#.*", "", programm)
    assert "AICS_AT_REST_KEY" not in programm, (
        "Die Verschlüsselung der Sicherungen darf nicht vom At-Rest-Schlüssel "
        "abhängen; sie hat ihren eigenen (shared/backup/verschluesselung."
        "SCHLUESSEL_ENV)."
    )


# ── Der Rückweg von außen, als Rundlauf (05.11.2026, Nachweis zu #1917) ──────
#
# Oben steht der Rundlauf durch die *Anwendung*. Das eigenständige Skript hatte
# dafür nur Textprüfungen — und genau dort saß ein Riegel, den kein Blick in
# den Quelltext zeigt: Die Zieldatei entsteht, bevor der erste Block
# entschlüsselt ist, und das Skript überschreibt nichts Vorhandenes. Ein
# Tippfehler in der Passphrase ließ also eine 0-Byte-Datei zurück und sperrte
# damit den **nächsten** Versuch aus — in einem Werkzeug für die Zehnjahresfrist
# aus Art. 13 Abs. 13 die falsche Richtung. Aufgefallen bei der Gegenprobe zum
# Entschlüsselungs-Nachweis (#1917, Schritt 6).

_SKRIPT = _WURZEL / "scripts" / "ops" / "backup_entschluesseln.py"


def _lauf(tmp_path: Path, quelle: Path, ziel: Path, schluessel: str):
    import subprocess
    import sys as _sys
    return subprocess.run(
        [_sys.executable, str(_SKRIPT), str(quelle), str(ziel)],
        env={"PATH": os.environ.get("PATH", ""), "AICS_BACKUP_KEY": schluessel},
        capture_output=True, text=True, timeout=120, cwd=str(tmp_path),
    )


@pytest.fixture()
def verschluesseltes_archiv(tmp_path, key) -> Path:
    from shared.backup.verschluesselung import verschluessele
    (tmp_path / "klar").write_bytes(b"PK\x03\x04" + secrets.token_bytes(5000))
    verschluessele(tmp_path / "klar", tmp_path / "enc")
    return tmp_path / "enc"


def test_das_skript_entschluesselt_byte_gleich(tmp_path, verschluesseltes_archiv):
    """Der Erfolgsweg — sonst prüfen die Fehlerfälle unten ein kaputtes Skript."""
    erg = _lauf(tmp_path, verschluesseltes_archiv, tmp_path / "aus", _SCHLUESSEL)
    assert erg.returncode == 0, erg.stderr
    assert (tmp_path / "aus").read_bytes() == (tmp_path / "klar").read_bytes()


@pytest.mark.parametrize("fall", ["falscher_schluessel", "gekuerzt"])
def test_ein_fehlversuch_laesst_keine_datei_zurueck(
    tmp_path, verschluesseltes_archiv, fall
):
    """Eine 0-Byte-Datei neben dem verschlüsselten Archiv sieht aus wie ein
    Ergebnis — und versperrt den zweiten Versuch."""
    quelle, schluessel = verschluesseltes_archiv, _SCHLUESSEL
    if fall == "falscher_schluessel":
        schluessel = "ein anderer"
    else:
        quelle = tmp_path / "kurz"
        quelle.write_bytes(verschluesseltes_archiv.read_bytes()[:200])

    ziel = tmp_path / "aus"
    erg = _lauf(tmp_path, quelle, ziel, schluessel)
    assert erg.returncode == 1, erg.stdout + erg.stderr
    assert not ziel.exists(), (
        f"{ziel.name} blieb nach dem Fehlversuch liegen — der nächste Aufruf "
        "mit dem richtigen Schlüssel wird dann abgewiesen."
    )


def test_nach_einem_fehlversuch_gelingt_der_zweite(tmp_path, verschluesseltes_archiv):
    """Der eigentliche Befund: vertippt, nachgetippt, muss gehen."""
    ziel = tmp_path / "aus"
    assert _lauf(tmp_path, verschluesseltes_archiv, ziel, "vertippt").returncode == 1
    erg = _lauf(tmp_path, verschluesseltes_archiv, ziel, _SCHLUESSEL)
    assert erg.returncode == 0, erg.stderr
    assert ziel.read_bytes() == (tmp_path / "klar").read_bytes()


def test_eine_vorhandene_datei_wird_nie_ueberschrieben(tmp_path, verschluesseltes_archiv):
    """Die andere Richtung: Der Riegel selbst muss bleiben. Ein Rückweg, der
    eine fremde Datei überschreibt, ist im Ernstfall ein zweiter Verlust."""
    ziel = tmp_path / "aus"
    ziel.write_bytes(b"fremder Inhalt")
    erg = _lauf(tmp_path, verschluesseltes_archiv, ziel, _SCHLUESSEL)
    assert erg.returncode == 1
    assert ziel.read_bytes() == b"fremder Inhalt"


def test_eine_fehlende_quelle_ist_eine_meldung_kein_traceback(tmp_path):
    erg = _lauf(tmp_path, tmp_path / "gibtesnicht.zip", tmp_path / "aus", "x")
    assert erg.returncode == 1
    assert "Traceback" not in erg.stderr, erg.stderr
