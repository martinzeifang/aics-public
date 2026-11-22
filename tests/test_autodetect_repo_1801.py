"""Der Autodetect muss das verknüpfte Repo finden (#1801).

Der Endpunkt las ausschließlich ``meta.linked_app.repo`` — ein Feld aus dem
Tkinter-GUI. Die Weboberfläche speichert die Verknüpfung seit #862 unter
``meta.vcs_publish`` und zeigt sie im selben Panel an. Der Autodetect
antwortete daneben „Kein GitHub-Repo bekannt … oder Projekt mit Repo
verknüpfen" — für ein Repo, das zwei Zeilen höher stand.

Die Folge war kein Fehler, sondern ein **Nichtgeschehen**: Der Knopf lief nicht
los, und der Anwender schloss daraus, die Suite finde seine SBOM nicht. Diese
Tests halten beide Quellen fest, damit die Auflösung nicht wieder an einer
Stelle hängt, die niemand mehr befüllt.
"""
from __future__ import annotations

import json

import pytest

CRA = '/api/cra'
PROJ = 'pytest-autodetect-1801'
FIRMA = 'pytest-firma-1801'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': PROJ, 'unternehmen': FIRMA})
    yield PROJ
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)


@pytest.fixture
def kein_netz(monkeypatch):
    """Was das Repo hergibt, ist hier nicht die Frage — nur ob gesucht wird."""
    gerufen: list[tuple[str, str]] = []

    def _autodetect_all(owner, name):
        gerufen.append((owner, name))
        return {'sbom': [], 'psirt': {}, 'vuln': [], 'support_period': {},
                'threatmodel': {}, 'access': {}, 'warnings': []}

    monkeypatch.setattr('cra.pflicht_doku_autodetect.autodetect_all', _autodetect_all)
    return gerufen


def test_verknuepftes_repo_aus_der_weboberflaeche_wird_genutzt(client, auth_headers,
                                                               projekt, kein_netz):
    """Der eigentliche Defekt: 400 trotz gepflegter Verknüpfung."""
    r = client.put(f'{CRA}/projekte/{PROJ}/repo-config', headers=auth_headers,
                   json={'vcs_publish': {'provider': 'github',
                                         'repo': 'martinzeifang/AI_Compliance_Suite'}})
    assert r.status_code == 200, r.json

    r = client.post(f'{CRA}/projekte/{PROJ}/pflicht-doku/autodetect?dry_run=true',
                    headers=auth_headers, json={})
    assert r.status_code == 200, r.json
    assert kein_netz == [('martinzeifang', 'AI_Compliance_Suite')]


def test_altbestand_aus_dem_tkinter_gui_bleibt_lesbar(client, auth_headers,
                                                      projekt, kein_netz):
    """`linked_app` ist der Weg, über den Bestandsprojekte verknüpft sind."""
    from pathlib import Path

    from cra.db import load_projekt, save_projekt

    db = Path('data/db/cra.sqlite')
    p = load_projekt(db, PROJ) or {}
    meta = json.loads(p.get('meta_json') or '{}')
    meta['linked_app'] = {'repo': 'https://github.com/alt/bestand'}
    save_projekt(db, PROJ, unternehmen=FIRMA, meta=meta)

    r = client.post(f'{CRA}/projekte/{PROJ}/pflicht-doku/autodetect?dry_run=true',
                    headers=auth_headers, json={})
    assert r.status_code == 200, r.json
    assert kein_netz == [('alt', 'bestand')]


def test_angegebenes_repo_sticht_die_verknuepfung(client, auth_headers,
                                                  projekt, kein_netz):
    """Das Eingabefeld bleibt ein ausdrücklicher Übersteuerungsweg."""
    client.put(f'{CRA}/projekte/{PROJ}/repo-config', headers=auth_headers,
               json={'vcs_publish': {'provider': 'github', 'repo': 'haus/standard'}})
    r = client.post(f'{CRA}/projekte/{PROJ}/pflicht-doku/autodetect?dry_run=true',
                    headers=auth_headers, json={'repo': 'anderer/ort'})
    assert r.status_code == 200, r.json
    assert kein_netz == [('anderer', 'ort')]


def test_ohne_jede_verknuepfung_bleibt_es_bei_der_klaren_ansage(client, auth_headers,
                                                                projekt, kein_netz):
    """Die Fehlermeldung war nie falsch — sie stand nur am falschen Projekt."""
    r = client.post(f'{CRA}/projekte/{PROJ}/pflicht-doku/autodetect?dry_run=true',
                    headers=auth_headers, json={})
    assert r.status_code == 400
    assert 'Repo' in (r.json or {}).get('error', '')
    assert kein_netz == []
