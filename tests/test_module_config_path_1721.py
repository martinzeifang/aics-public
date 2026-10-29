"""Modul-Configs müssen an einem schreibbaren Ort liegen (#1721).

Im Container läuft der Dienst als ``aics`` mit Arbeitsverzeichnis ``/app``, das
**nicht** schreibbar ist; keine ``*.config.json`` liegt im Image. Weil
``load_config`` die Datei beim **Lesen** anlegt, wenn sie fehlt, endete jeder
Endpunkt, der eine Modul-Config anfasst, in:

    PermissionError: [Errno 13] Permission denied: 'gutachten.config.json.lock'

Konkret traf es die Fragen-Generierung des Compliance-Audits (HTTP 500).
"""
from __future__ import annotations

import importlib
import os
import stat
from pathlib import Path

import pytest

from shared.config_io import module_config_path

#: Alle Module mit eigener Konfiguration.
MODULE = ('ai_act', 'baso', 'compliance', 'compliance_db', 'cra', 'dsgvo',
          'gutachten', 'ict', 'nis2', 'risikobewertung')

#: Module, deren ``load_config`` die Datei beim Lesen anlegt.
SCHREIBT_BEIM_LESEN = ('ai_act', 'baso', 'compliance', 'cra', 'dsgvo',
                       'gutachten', 'ict')


# ── Pfadwahl ─────────────────────────────────────────────────────────────────

def test_ohne_env_bleibt_es_bei_cwd(monkeypatch):
    """In der Entwicklung darf sich nichts ändern."""
    monkeypatch.delenv('AICS_CONFIG_PATH', raising=False)
    assert module_config_path('gutachten.config.json') == Path('gutachten.config.json')


def test_mit_env_neben_der_suite_config(monkeypatch):
    """Im Container landet die Modul-Config im beschreibbaren data-Volume."""
    monkeypatch.setenv('AICS_CONFIG_PATH', '/app/data/ai_compliance_suite.config.json')
    assert module_config_path('cra.config.json') == Path('/app/data/cra.config.json')


def test_env_mit_tilde_wird_aufgeloest(monkeypatch):
    monkeypatch.setenv('AICS_CONFIG_PATH', '~/aics/suite.config.json')
    p = module_config_path('nis2.config.json')
    assert '~' not in str(p) and p.name == 'nis2.config.json'


@pytest.mark.parametrize('modul', MODULE)
def test_kein_modul_haengt_mehr_an_cwd(modul):
    """Der CWD-relative Literal-Pfad war die Ursache — er darf nicht zurückkommen."""
    quelle = (Path(__file__).resolve().parent.parent / modul / 'config.py').read_text()
    assert 'module_config_path(' in quelle, \
        f'{modul}/config.py nutzt den gemeinsamen Helfer nicht'
    assert 'DEFAULT_CONFIG_PATH = Path("' not in quelle, \
        (f'{modul}/config.py setzt den Pfad wieder CWD-relativ — im Container ist '
         'das Arbeitsverzeichnis nicht schreibbar')


@pytest.mark.parametrize('modul', MODULE)
def test_pfad_folgt_der_env(modul, monkeypatch, tmp_path):
    """Jedes Modul muss die Umgebung tatsächlich auswerten (Import-Zeitpunkt)."""
    monkeypatch.setenv('AICS_CONFIG_PATH', str(tmp_path / 'suite.config.json'))
    cfgmod = importlib.reload(importlib.import_module(f'{modul}.config'))
    assert cfgmod.DEFAULT_CONFIG_PATH.parent == tmp_path, \
        f'{modul}: Pfad {cfgmod.DEFAULT_CONFIG_PATH} ignoriert AICS_CONFIG_PATH'


# ── Lesen darf nicht scheitern ───────────────────────────────────────────────

@pytest.mark.parametrize('modul', SCHREIBT_BEIM_LESEN)
def test_load_config_ueberlebt_nicht_schreibbaren_ort(modul, tmp_path):
    """Der eigentliche 500er: ``load_config`` auf einem read-only Verzeichnis.

    Statt zu werfen, müssen die Vorgaben zurückkommen — ein Lesevorgang darf die
    Anwendung nicht lahmlegen, bloß weil er nicht persistieren kann.
    """
    nur_lesen = tmp_path / 'ro'
    nur_lesen.mkdir()
    cfgmod = importlib.import_module(f'{modul}.config')
    ziel = nur_lesen / f'{modul}.config.json'
    nur_lesen.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x, kein Schreiben
    try:
        cfg = cfgmod.load_config(ziel)
        assert isinstance(cfg, dict) and cfg, f'{modul}: keine Vorgaben zurueckgegeben'
        assert not ziel.exists(), 'nichts geschrieben — wie erwartet'
    finally:
        nur_lesen.chmod(stat.S_IRWXU)


@pytest.mark.parametrize('modul', SCHREIBT_BEIM_LESEN)
def test_load_config_schreibt_wenn_es_darf(modul, tmp_path):
    """Gegenprobe: Auf einem beschreibbaren Ort wird weiterhin angelegt."""
    cfgmod = importlib.import_module(f'{modul}.config')
    ziel = tmp_path / f'{modul}.config.json'
    cfg = cfgmod.load_config(ziel)
    assert isinstance(cfg, dict) and cfg
    assert ziel.exists(), f'{modul}: Konfiguration wurde nicht angelegt'


def test_echter_endpunkt_funktioniert_ohne_schreibrechte(client, auth_headers,
                                                         tmp_path, monkeypatch):
    """Der Fall aus dem Log: Fragen-Prompt im Compliance-Audit.

    Vorher: PermissionError auf der Lock-Datei → HTTP 500.
    """
    from pathlib import Path as _P

    import gutachten.config as gcfg
    nur_lesen = tmp_path / 'ro'
    nur_lesen.mkdir()
    monkeypatch.setattr(gcfg, 'DEFAULT_CONFIG_PATH',
                        _P(nur_lesen / 'gutachten.config.json'))
    nur_lesen.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        import server.api.compliance_audit as bp
        from gutachten.db import save_project

        save_project(bp.DB_PATH, 'ConfigRoTest', frameworks=['NIS2'],
                     pruefungsfokus='x', unternehmen='')
        r = client.post('/api/compliance-audit/ConfigRoTest/fragen/prompt',
                        json={}, headers=auth_headers)
        assert r.status_code == 200, f'HTTP {r.status_code}: {r.data[:300]}'
        assert 'prompts' in r.json
    finally:
        nur_lesen.chmod(stat.S_IRWXU)
