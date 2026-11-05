"""#1045 — RB-Risiko-Assistent (EU-AI-Act) nutzt konkreten AI-Act-Projektkontext."""
from pathlib import Path

import pytest

from server.api.risikobewertung import DB_PATH as RB_DB
from risikobewertung.db import save_projekt as rb_save, update_projekt_meta as rb_meta
from risikobewertung.prompts import build_discovery_prompt
from ai_act.db import save_projekt as ai_save, save_system_doku, update_projekt_meta as ai_meta, delete_projekt as ai_del

AI_DB = Path('data/db/ai_act.sqlite')
RBPROJ = 'pytest-rb-1045'
AIPROJ = 'pytest-ai-1045'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


# ── reiner Prompt-Builder ───────────────────────────────────────────

def test_prompt_includes_aiact_context_and_emphasis():
    p = build_discovery_prompt(
        anwendung='X', risikobereich='', schutzziele=[], beschreibung='',
        anhang_texte=[], framework='EU-AI-Act', n_risiken=8,
        aiact_context='Zweck (intended purpose): Bonitäts-Scoring für Kredite')
    assert 'EU-AI-Act-Systemkontext' in p
    assert 'Bonitäts-Scoring für Kredite' in p
    assert 'design, development, deployment, monitoring' in p
    assert 'fundamental-rights' in p


def test_prompt_without_context_no_block():
    p = build_discovery_prompt(
        anwendung='X', risikobereich='', schutzziele=[], beschreibung='',
        anhang_texte=[], framework='STRIDE', n_risiken=5)
    assert 'EU-AI-Act-Systemkontext' not in p
    assert 'Cyber Resilience Act' in p


# ── Endpoint: Kontext aus Verknüpfung + Override ────────────────────

@pytest.fixture
def linked():
    ai_save(AI_DB, name=AIPROJ, organisation='ACME', produkt='Scoring', beschreibung='')
    save_system_doku(AI_DB, AIPROJ, {
        'system_name': 'CreditAI', 'intended_purpose': 'Bonitäts-Scoring für Privatkredite',
        'architecture': 'Gradient-Boosting + Rules', 'training_methodology': 'Supervised',
        'cybersecurity_measures': 'TLS, RBAC'})
    ai_meta(AI_DB, AIPROJ, {'aiact': {'risk_tier': 'high-risk'}})
    rb_save(RB_DB, RBPROJ, framework='EU-AI-Act', beschreibung='', unternehmen='ACME')
    rb_meta(RB_DB, RBPROJ, {'linked_aiact_projekt': AIPROJ})
    yield
    import sqlite3
    ai_del(AI_DB, AIPROJ)
    try:
        con = sqlite3.connect(str(AI_DB)); con.execute("DELETE FROM aiact_system_doku WHERE projekt_name=?", (AIPROJ,)); con.commit(); con.close()
    except Exception:
        pass
    try:
        con = sqlite3.connect(str(RB_DB)); con.execute("DELETE FROM rb_projekte WHERE name=?", (RBPROJ,)); con.commit(); con.close()
    except Exception:
        pass


def _u():
    return f'/api/risikobewertung/projekte/{RBPROJ}/risiken/discovery-prompt'


def test_endpoint_uses_linked_aiact_context(client, auth_headers, linked):
    r = client.post(_u(), json={'n_risiken': 6}, headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['aiact_projekt_used'] == AIPROJ
    assert body['aiact_context_used'] is True
    assert 'Bonitäts-Scoring für Privatkredite' in body['prompt']
    assert 'high-risk' in body['prompt']


def test_endpoint_request_override_wins(client, auth_headers, linked):
    # Override auf ein nicht existierendes AI-Act-Projekt → kein Kontext, kein Crash
    r = client.post(_u(), json={'aiact_projekt': 'gibtsnicht'}, headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()['aiact_projekt_used'] == 'gibtsnicht'
