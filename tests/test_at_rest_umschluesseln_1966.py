"""Die At-Rest-Umschlüsselung, geprüft als Rundlauf (#1966).

**Warum dieses Werkzeug nötig war.** ``shared/crypto_at_rest._field_passphrase``
leitet die Passphrase in der Reihenfolge ``AICS_AT_REST_KEY`` →
``JWT_SECRET_KEY`` ab. Den eigenen Schlüssel zu **setzen** wechselt die Quelle
und macht jeden bereits verschlüsselten Wert unlesbar — ohne Fehlermeldung.
Damit war die Abweichung **B6** keine Nachlässigkeit, sondern eine Sackgasse:
Ohne Umschlüsselung war der Schlüssel nicht setzbar, und ohne ihn ist die
Verschlüsselung der Nachweisdateien nicht einschaltbar (``evidence/db.py``
verlangt den Hauptschalter, der verlangt den Schlüssel). AI1-04 blieb deshalb
bei 3.

**Geprüft wird der Rundlauf** (die Lehre aus #1785): Es gibt keine Zeile
Quelltext, aus der sich ablesen lässt, dass ein Wert nach dem Umschlüsseln mit
dem **neuen** und nicht mehr mit dem **alten** Schlüssel lesbar ist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
SKRIPT = WURZEL / "scripts" / "ops" / "at_rest_umschluesseln.py"

ALT = "alter-schluessel-nur-fuer-den-test"
NEU = "neuer-schluessel-nur-fuer-den-test"


def _programm() -> str:
    """Der Quelltext **ohne** Docstrings und Kommentare.

    Mit dem AST und nicht mit einem Regex: Ein Regex über dreifach
    angeführte Zeichenketten löscht auch die SQL-Abfragen, und dann prüft der
    Wächter das Falsche. Genau
    daran ist die erste Fassung dieser Datei gescheitert — zusammen mit dem
    Gegenstück, einem Treffer auf das Wort „HMAC" in einem *Kommentar*. Das ist
    die Falle, die hier schon #1834, #1867, #1878 und #1903 gestellt haben:
    das Programm prüfen, nicht die Erzählung.
    """
    import ast
    quelle = SKRIPT.read_text(encoding="utf-8")
    zeilen = quelle.splitlines()
    baum = ast.parse(quelle)
    for knoten in ast.walk(baum):
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
    import re as _re
    return _re.sub(r"(?m)#.*$", "", "\n".join(zeilen))


def _werkzeug():
    """Das Skript als Modul — es liegt nicht auf dem Importpfad."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("at_rest_um", SKRIPT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture()
def schluessel(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", ALT)
    monkeypatch.setenv("AICS_AT_REST_KEY", NEU)


# ── Der Rundlauf ────────────────────────────────────────────────────────────

def test_rundlauf_konfiguration(tmp_path, schluessel):
    """Verschlüsseln mit alt → umschlüsseln → lesbar mit neu, nicht mit alt."""
    from shared.crypto_at_rest import decrypt_field, encrypt_field

    geheim = "ghp_EinTokenDasNiemandSonstKennt"
    daten = {
        "integrations": {
            "github": {"token": encrypt_field(geheim, key_env="JWT_SECRET_KEY")},
            "portainer": {"api_key": encrypt_field("ptr_zweiter", key_env="JWT_SECRET_KEY")},
        },
        "unbeteiligt": "klartext bleibt klartext",
    }
    pfad = tmp_path / "suite.config.json"
    pfad.write_text(json.dumps(daten), encoding="utf-8")

    w = _werkzeug()
    args = w._argumente(["--konfig", str(pfad)])
    anzahl, _ = w._konfiguration(args, umschluesseln=True)
    assert anzahl == 2, anzahl

    neu = json.loads(pfad.read_text(encoding="utf-8"))
    tok = neu["integrations"]["github"]["token"]
    assert decrypt_field(tok, key_env="AICS_AT_REST_KEY") == geheim, (
        "nach dem Umschlüsseln nicht mit dem NEUEN Schlüssel lesbar")
    with pytest.raises(Exception):
        decrypt_field(tok, key_env="JWT_SECRET_KEY")
    assert neu["unbeteiligt"] == "klartext bleibt klartext", (
        "ein unverschlüsselter Wert wurde angefasst")


def test_der_trockenlauf_schreibt_nichts(tmp_path, schluessel):
    """Vorgabe ist Trockenlauf — sonst ist der erste Aufruf der Ernstfall."""
    from shared.crypto_at_rest import encrypt_field

    pfad = tmp_path / "suite.config.json"
    inhalt = json.dumps({"integrations": {"github": {
        "token": encrypt_field("ghp_x", key_env="JWT_SECRET_KEY")}}})
    pfad.write_text(inhalt, encoding="utf-8")

    w = _werkzeug()
    anzahl, _ = w._konfiguration(w._argumente(["--konfig", str(pfad)]),
                                 umschluesseln=False)
    assert anzahl == 1, "der Trockenlauf muss zählen, was er täte"
    assert pfad.read_text(encoding="utf-8") == inhalt, "Datei wurde verändert"


def test_ein_nicht_lesbarer_wert_wird_gemeldet_nicht_uebergangen(tmp_path, schluessel):
    """Ein Wert, der mit der alten Quelle nicht aufgeht, ist entweder schon
    umgeschlüsselt oder mit einem dritten Schlüssel entstanden.

    Beides stillschweigend zu übergehen hieße, einen unlesbaren Wert als
    erledigt zu melden — die Fehlerklasse aus #1870.
    """
    pfad = tmp_path / "suite.config.json"
    pfad.write_text(json.dumps({"integrations": {"github": {
        "token": "AICSFLD1:Zm9vYmFy"}}}), encoding="utf-8")

    w = _werkzeug()
    anzahl, hinweise = w._konfiguration(w._argumente(["--konfig", str(pfad)]),
                                        umschluesseln=True)
    assert anzahl == 0
    assert any("nicht lesbar" in h for h in hinweise), hinweise
    assert json.loads(pfad.read_text(encoding="utf-8"))[
        "integrations"]["github"]["token"] == "AICSFLD1:Zm9vYmFy", "unangetastet?"


# ── Die Riegel ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("umgebung,erwartet", [
    ({}, "nicht gesetzt"),
    ({"JWT_SECRET_KEY": ALT}, "nicht gesetzt"),
    ({"JWT_SECRET_KEY": ALT, "AICS_AT_REST_KEY": ALT}, "identisch"),
])
def test_ohne_beide_schluessel_laeuft_nichts(monkeypatch, capsys, umgebung, erwartet):
    for name in ("JWT_SECRET_KEY", "AICS_AT_REST_KEY"):
        monkeypatch.delenv(name, raising=False)
    for k, v in umgebung.items():
        monkeypatch.setenv(k, v)
    assert _werkzeug().main([]) == 2
    assert erwartet in capsys.readouterr().err


# ── Was der Quelltext zusichern muss ────────────────────────────────────────

def test_gefunden_wird_durch_suchen_nicht_durch_eine_liste():
    """Eine Positivliste der verschlüsselten Felder wäre die Spiegel-Liste aus
    #1731/#1735 — und ein übersehenes Feld ist hier kein Fehlbetrag, sondern
    ein **endgültig unlesbarer** Wert."""
    programm = _programm()
    assert "information_schema.columns" in programm, (
        "Das Werkzeug durchsucht die Spalten nicht selbst — eine feste Liste "
        "lässt ein neues verschlüsseltes Feld unlesbar zurück.")
    for tabelle in ("users", "repo_config", "webauthn"):
        assert f'"{tabelle}"' not in programm and f"'{tabelle}'" not in programm, (
            f"`{tabelle}` steht als Literal im Werkzeug — das ist der Anfang "
            "einer Liste, die nicht mitwächst.")


def test_der_pool_wird_zurueckgegeben_nicht_geschlossen():
    """`pool.close()` auf dem Pool der Anwendung — der Nebenbefund aus #1808."""
    programm = _programm()
    assert "putconn" in programm
    assert "pool.close()" not in programm


def test_das_sidecar_wird_nicht_mitgeschrieben():
    """Ein HMAC-Sidecar, das zu einem Schlüssel passt, den dieser Prozess nicht
    kennt, wäre schlimmer als keins (die Lehre aus #1785)."""
    programm = _programm()
    assert ".sha256" not in programm and "hmac" not in programm.lower(), (
        "Das Werkzeug fasst das Sidecar an — das soll die Anwendung tun.")
