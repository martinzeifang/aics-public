"""Betrieb: lange Läufe, lesbare Zeiten, ehrliche Startzeile — #2022/#2024/#2093/#2095.

Vier Funde aus der Störung vom 09.11.2026 und ihrer Untersuchung. Keiner ist
ein Defekt im Fachcode; alle vier betreffen die Schicht, in der man im
Störungsfall nachsieht — und genau dort war etwas falsch oder nicht da.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.i18n_text import python_programm


# ══════════════════════════════════════════════════════════════════════════════
# #2022 — ein Lauf von einer Stunde gehört nicht in einen Request
# ══════════════════════════════════════════════════════════════════════════════

def test_das_einlesen_laeuft_im_hintergrund():
    """Gemessen braucht das BSI-Verzeichnis **3 668 s**; das Frontend gab nach
    300 s auf, der Server arbeitete weiter, und der Anwender sah einen Fehler
    für einen Lauf, der gelang."""
    programm = python_programm("server/api/compliance_audit.py")
    assert "threading.Thread" in programm, "das Einlesen läuft weiter synchron"
    assert "202" in programm


def test_ein_zweiter_lauf_wird_abgewiesen():
    """Zwei gleichzeitige Läufe über dasselbe Verzeichnis schreiben dieselben
    Abschnitte doppelt (dieselbe Regel wie beim CRA-Sync, #937)."""
    programm = python_programm("server/api/compliance_audit.py")
    assert "ingest-laeuft-bereits" in programm
    assert "409" in programm


def test_der_zustand_steht_in_der_datenbank(tmp_path):
    """Nicht im Prozess: Ein Lauf, der in Worker A startet, wäre in einem Dict
    von Worker B unsichtbar, und die Abfrage landete per Zufall beim richtigen
    oder beim falschen."""
    from compliance_audit import ingest_runs as runs

    db = Path("data/db/gutachten.sqlite")
    runs.ensure_table(db)

    lauf = runs.starten(db, "pytest-fw-2022", von="pytest", dateien=3)
    assert lauf > 0
    offen = runs.laeuft(db, "pytest-fw-2022")
    assert offen and offen["zustand"] == "laeuft" and offen["dateien"] == 3

    runs.fortschritt(db, lauf, "2 von 3 gelesen", abschnitte=120)
    offen = runs.laeuft(db, "pytest-fw-2022")
    assert offen["fortschritt"] == "2 von 3 gelesen" and offen["abschnitte"] == 120

    runs.beenden(db, lauf, zustand="fertig", abschnitte=976, log=["eine Warnung"])
    assert runs.laeuft(db, "pytest-fw-2022") is None
    letzter = runs.letzter(db, "pytest-fw-2022")
    assert letzter["zustand"] == "fertig" and letzter["abschnitte"] == 976
    assert letzter["log"] == ["eine Warnung"]


def test_ein_unbekannter_zustand_wird_abgewiesen():
    """Ein Tippfehler im Zustand wäre ein Lauf, den niemand mehr findet."""
    from compliance_audit import ingest_runs as runs

    with pytest.raises(ValueError):
        runs.beenden(Path("data/db/gutachten.sqlite"), 1, zustand="irgendwas")


def test_das_frontend_wartet_nicht_mehr():
    quelle = Path("frontend/src/views/admin/FrameworksView.vue").read_text(encoding="utf-8")
    from tests.i18n_text import ohne_kommentare

    programm = ohne_kommentare(quelle)
    assert "timeout: 300000" not in programm, (
        "der Browser wartet weiter auf einen Lauf von einer Stunde")
    assert "ingest/status" in programm, "kein Weg, den Stand zu erfahren"
    assert "onUnmounted" in programm, (
        "die Abfrage läuft weiter, nachdem die Maske zu ist (#2087)")


# ══════════════════════════════════════════════════════════════════════════════
# #2024 — die Antwortzeiten sind lesbar
# ══════════════════════════════════════════════════════════════════════════════

def test_das_profil_liest_echte_einträge(tmp_path):
    from shared import antwortzeiten as az

    log = tmp_path / "audit.log"
    zeilen = [
        {"ts": "2026-11-09T10:00:01+00:00", "path": "/api/a", "status_code": 200,
         "duration_ms": 50},
        {"ts": "2026-11-09T10:00:02+00:00", "path": "/api/a", "status_code": 200,
         "duration_ms": 70},
        # Drei Antworten, die in **derselben Sekunde** enden — der Fingerabdruck
        # eines Staus, der sich auf einen Schlag löst.
        {"ts": "2026-11-09T10:05:11+00:00", "path": "/api/b", "status_code": 200,
         "duration_ms": 20100},
        {"ts": "2026-11-09T10:05:11+00:00", "path": "/api/c", "status_code": 200,
         "duration_ms": 8400},
        {"ts": "2026-11-09T10:05:11+00:00", "path": "/api/d", "status_code": 200,
         "duration_ms": 6700},
        # Ein anderer Tag darf nicht mitgezählt werden.
        {"ts": "2026-11-08T10:00:00+00:00", "path": "/api/a", "status_code": 200,
         "duration_ms": 999999},
        # Ein Eintrag ohne duration_ms (Altbestand) wird übersprungen.
        {"ts": "2026-11-09T10:00:03+00:00", "path": "/api/a", "status_code": 200},
    ]
    log.write_text("\n".join(json.dumps(z) for z in zeilen) + "\n", encoding="utf-8")

    p = az.profil("2026-11-09", pfad=log)
    assert p["anfragen"] == 5, p
    assert p["langsam_gesamt"] == 3
    assert p["langsamste"][0]["dauer_s"] == 20.1
    assert p["gleichzeitige_enden"][0]["anzahl"] == 3, (
        "die gleichzeitig endenden Antworten werden nicht erkannt — das ist "
        "der Unterschied zwischen einem Stau und gleichmäßiger Langsamkeit")
    stunde = next(h for h in p["stunden"] if h["stunde"] == "10")
    assert stunde["anzahl"] == 5 and stunde["langsam"] == 3


def test_eine_kaputte_zeile_bricht_nichts_ab(tmp_path):
    from shared import antwortzeiten as az

    log = tmp_path / "audit.log"
    log.write_text(
        '{"ts": "2026-11-09T10:00:00+00:00", "path": "/a", "duration_ms": 10}\n'
        'das ist kein JSON 2026-11-09\n'
        '{"ts": "2026-11-09T10:00:01+00:00", "path": "/a", "duration_ms": 20}\n',
        encoding="utf-8")
    assert az.profil("2026-11-09", pfad=log)["anfragen"] == 2


def test_ohne_log_gibt_es_kein_raten(tmp_path):
    from shared import antwortzeiten as az

    p = az.profil("2026-11-09", pfad=tmp_path / "gibt-es-nicht.log")
    assert p["log_vorhanden"] is False and p["anfragen"] == 0
    assert az.tage(tmp_path / "gibt-es-nicht.log") == []


def test_die_tagesliste_liest_vom_ende(tmp_path):
    """Ein Log mit 432 019 Zeilen von vorn zu durchlaufen wäre die Last, die
    dieses Modul vermeiden soll."""
    from shared import antwortzeiten as az

    log = tmp_path / "audit.log"
    log.write_text("\n".join(
        json.dumps({"ts": f"2026-11-{t:02d}T10:00:00+00:00", "path": "/a",
                    "duration_ms": 10})
        for t in range(1, 10)) + "\n", encoding="utf-8")
    assert az.tage(log, grenze=3) == ["2026-11-09", "2026-11-08", "2026-11-07"]


def test_die_schwelle_ist_dieselbe_wie_in_der_datenbank():
    """Zwei verschiedene Schwellen wären zwei Bilder desselben Staus."""
    from shared.antwortzeiten import LANGSAM_MS

    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert f"log_min_duration_statement={int(LANGSAM_MS)}" in compose


def test_der_endpunkt_ist_registriert_und_admin_only():
    programm = python_programm("server/api/admin.py")
    assert "/antwortzeiten" in programm
    assert "admin:config" in programm


# ══════════════════════════════════════════════════════════════════════════════
# #2093 — die Startzeile sagt die Wahrheit
# ══════════════════════════════════════════════════════════════════════════════

def test_die_startzeile_steht_nach_der_entscheidung():
    """Vier Angaben, zwei Wahrheiten: ``printenv`` → 4, Startzeile → „Workers:
    4", ``/proc/1/cmdline`` → ``-w 2``. Das hat eine Fehlersuche in die falsche
    Richtung geschickt (#2023 erste Fassung)."""
    zeilen = Path("docker/entrypoint.sh").read_text(encoding="utf-8").splitlines()
    i_entscheidung = next(i for i, z in enumerate(zeilen)
                          if 'if [ "$#" -gt 0 ]' in z)
    i_workerzeile = next(i for i, z in enumerate(zeilen)
                         if "Workers: ${GUNICORN_WORKERS}" in z)
    assert i_workerzeile > i_entscheidung, (
        "die Workerzahl wird gedruckt, bevor der Override greift — sie "
        "behauptet dann eine Zahl, die nicht läuft")


def test_ein_override_wird_benannt():
    quelle = Path("docker/entrypoint.sh").read_text(encoding="utf-8")
    assert "wirken NICHT" in quelle, (
        "ein Stack-command:-Override macht die drei Env-Werte tot, und das "
        "muss im Log stehen — sonst ist ein `--env GUNICORN_WORKERS=…` ein "
        "Knopf ohne Wirkung")


# ══════════════════════════════════════════════════════════════════════════════
# #2095 — die Postgres-Konfiguration steht im Repo
# ══════════════════════════════════════════════════════════════════════════════

def test_die_protokollierung_ist_im_repo_verankert():
    """`ALTER SYSTEM` schreibt ins Datenvolumen: Das überlebt einen
    Container-Neustart, aber kein neues Volume und keine neue Installation."""
    import yaml

    pg = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8")) \
        ["services"]["postgres"]
    kommando = " ".join(str(pg.get("command") or "").split())
    assert "log_lock_waits=on" in kommando
    assert "log_min_duration_statement=2000" in kommando


def test_die_logrotation_gilt_fuer_alle():
    """Dev und Test hatten sie nur, weil jemand die **Live**-Stack-Datei
    angefasst hat — eine neue Installation stand schlechter da."""
    import yaml

    pg = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8")) \
        ["services"]["postgres"]
    log = pg.get("logging") or {}
    assert log.get("driver") == "json-file"
    assert log.get("options", {}).get("max-size")
    assert log.get("options", {}).get("max-file")


def test_der_vorrang_von_c_ist_benannt():
    """`-c` sticht `postgresql.auto.conf` — wer das nicht weiß, sucht den
    Fehler dort, wo er bei gunicorn gesucht wurde (#2093)."""
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "Vorrang" in compose and "postgresql.auto.conf" in compose
