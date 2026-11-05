"""Sprint #28 (Milestone #30) — AI-Act-Dokument-/Register-Assistenten.

Deckt ab:
- #1242 AI-Literacy-Ausfüll-Assistent (Prompt + Parse + Apply ins Register).
- #1243 Konformität: optionale, manuell überstimmbare CRA-Verknüpfung (read-only).
- #1244 GPAI-Dokument-Assistenten (Copyright-Policy / Trainingsdaten-Summary-Prompts)
        + DocSpecs gpai_copyright_policy / gpai_training_summary.
- #1245 Pflichtdokument-Wizards (Betriebsanleitung Art. 13, FRIA Art. 27) +
        suggested_assistant-Verdrahtung der drei assistenzlosen Docs.

Test-Isolation: alle DB_PATH-Globals werden auf eine Temp-SQLite im Workspace
umgebogen (connect_sqlite-Constraint); CRA-DB als separate Temp-Datei.
"""
import sqlite3
import uuid
from pathlib import Path

import pytest

BASE = '/api/aiact'
LIT = '/api/aiact-literacy'
GPAI = '/api/aiact-gpai'
CONF = '/api/aiact-conformity'
PROJ = 'pytest-sprint28-1242'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch):
    db = Path('data/db') / f'test_aiact_s28_{uuid.uuid4().hex}.sqlite'
    cra_db = Path('data/db') / f'test_cra_s28_{uuid.uuid4().hex}.sqlite'
    import server.api.aiact as aiact_main
    import server.api.aiact_literacy as lit_bp
    import server.api.aiact_gpai as gpai_bp
    import server.api.aiact_conformity as conf_bp
    import ai_act.ai_literacy as lit
    import ai_act.gpai as gpai
    import ai_act.conformity as conf
    import ai_act.db as db_mod
    db_mod.ensure_db(db)
    for m in (aiact_main, lit_bp, gpai_bp, conf_bp, lit, gpai, conf):
        monkeypatch.setattr(m, 'DB_PATH', db, raising=False)
    # CRA-DB für die optionale Verknüpfung (#1243) read-only.
    monkeypatch.setattr(conf, 'CRA_DB_PATH', cra_db, raising=False)
    yield db, cra_db
    for base in (db, cra_db):
        for sfx in ('', '-wal', '-shm'):
            p = Path(str(base) + sfx)
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass


@pytest.fixture
def projekt(client, auth_headers):
    r = client.post(f'{BASE}/projekte', headers=auth_headers,
                    json={'name': PROJ, 'produkt': 'Foundation-Model',
                          'beschreibung': 'LLM-Assistent'})
    assert r.status_code in (200, 201), r.get_json()
    return PROJ


# ── #1242 AI-Literacy-Ausfüll-Assistent ─────────────────────────────────────────

def test_literacy_wizard_prompt(client, auth_headers, projekt):
    r = client.get(f'{LIT}/projekte/{PROJ}/wizard/prompt', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    p = r.get_json()['prompt']
    assert 'AI-Literacy' in p and 'Art. 4' in p
    # rollenbasierte Zielgruppen müssen im Prompt vorkommen
    assert 'Entwickler' in p and 'Management' in p


def test_literacy_wizard_parse_and_apply(client, auth_headers, projekt):
    raw = ('{"konzept": "Risikoangemessene Schulung.", '
           '"plan_markdown": "# AI-Literacy-Plan\\n\\nInhalt", '
           '"massnahmen": [{"rolle": "Entwickler/Data-Science", '
           '"schulungsmodul": "AI-Act-Grundlagen", "kompetenzlevel": "fortgeschritten", '
           '"turnus": "jährlich", "inhalte": "Risiken, Bias"}]}')
    r = client.post(f'{LIT}/projekte/{PROJ}/wizard/parse', headers=auth_headers,
                    json={'response': raw, 'apply': True})
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    assert data['applied']['created'] == 1
    assert data['plan_markdown'].startswith('# AI-Literacy-Plan')
    assert data['konzept']['konzept'] == 'Risikoangemessene Schulung.'
    # Maßnahme ist als Register-Eintrag angelegt
    assert any(n['schulungsmodul'] == 'AI-Act-Grundlagen' for n in data['nachweise'])


def test_literacy_wizard_parse_invalid_json(client, auth_headers, projekt):
    r = client.post(f'{LIT}/projekte/{PROJ}/wizard/parse', headers=auth_headers,
                    json={'response': 'kein json'})
    assert r.status_code == 400


def test_literacy_wizard_404(client, auth_headers):
    r = client.get(f'{LIT}/projekte/nope-xyz/wizard/prompt', headers=auth_headers)
    assert r.status_code == 404


# ── #1244 GPAI-Dokument-Assistenten ─────────────────────────────────────────────

def test_gpai_copyright_policy_prompt(client, auth_headers, projekt):
    r = client.get(f'{GPAI}/projekte/{PROJ}/wizard/copyright-policy/prompt',
                   headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    p = r.get_json()['prompt']
    assert 'Urheberrecht' in p and '53(1)c' in p
    assert 'Markdown' in p


def test_gpai_training_summary_prompt(client, auth_headers, projekt):
    r = client.get(f'{GPAI}/projekte/{PROJ}/wizard/training-summary/prompt',
                   headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    p = r.get_json()['prompt']
    assert '53(1)d' in p and 'Trainings' in p


def test_gpai_doc_prompt_404(client, auth_headers):
    r = client.get(f'{GPAI}/projekte/nope/wizard/copyright-policy/prompt',
                   headers=auth_headers)
    assert r.status_code == 404


def test_gpai_docspecs_in_catalog():
    from shared.documents.catalog import get_doc_spec
    cp = get_doc_spec('ai_act', 'gpai_copyright_policy')
    ts = get_doc_spec('ai_act', 'gpai_training_summary')
    assert cp and cp['suggested_assistant'] == 'gpai-copyright'
    assert ts and ts['suggested_assistant'] == 'gpai-training-summary'


# ── #1245 Pflichtdokument-Wizards + DocSpec-Verdrahtung ──────────────────────────

def test_betriebsanleitung_wizard_prompt(client, auth_headers, projekt):
    r = client.get(f'{BASE}/projekte/{PROJ}/wizards/betriebsanleitung/prompt',
                   headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    p = r.get_json()['prompt']
    assert 'Betriebsanleitung' in p and 'Art. 13' in p


def test_fria_doc_wizard_prompt(client, auth_headers, projekt):
    r = client.get(f'{BASE}/projekte/{PROJ}/wizards/fria-doc/prompt',
                   headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    p = r.get_json()['prompt']
    assert 'FRIA' in p and 'Art. 27' in p


def test_doc_wizards_404(client, auth_headers):
    r = client.get(f'{BASE}/projekte/nope/wizards/fria-doc/prompt', headers=auth_headers)
    assert r.status_code == 404


def test_assistenzlose_docs_now_have_assistant():
    from shared.documents.catalog import get_doc_spec
    assert get_doc_spec('ai_act', 'technische_doku_annex_iv')['suggested_assistant'] == 'high-risk-doc'
    assert get_doc_spec('ai_act', 'betriebsanleitung')['suggested_assistant'] == 'betriebsanleitung'
    assert get_doc_spec('ai_act', 'fria')['suggested_assistant'] == 'fria-doc'
    # AI-Literacy-Plan-DocSpec (#1242)
    assert get_doc_spec('ai_act', 'ai_literacy_plan')['suggested_assistant'] == 'literacy'


# ── #1243 Optionale CRA-Verknüpfung ─────────────────────────────────────────────

def _seed_cra(cra_db: Path):
    """Legt einen CRA-Konformitäts-Record im CRA-Schema an (read-only Quelle)."""
    from cra.konformitaet_db import save_konformitaet, ensure_table
    ensure_table(cra_db)
    save_konformitaet(cra_db, 'CRA-Prod', {
        'release_version': '1.0', 'bewertungsweg': 'A', 'ce_status': 'ce_angebracht',
        'nb_kennnummer': '1234', 'bewertung_abgeschlossen': True})


def test_cra_link_default_empty(client, auth_headers, projekt):
    r = client.get(f'{CONF}/projekte/{PROJ}/cra-link', headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d['linked'] is False and d['linked_cra_projekt'] == ''
    assert d['cra_record'] is None


def test_cra_link_set_and_readonly_reference(client, auth_headers, projekt, _tmp_db):
    _db, cra_db = _tmp_db
    _seed_cra(cra_db)
    r = client.put(f'{CONF}/projekte/{PROJ}/cra-link', headers=auth_headers,
                   json={'linked_cra_projekt': 'CRA-Prod'})
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d['linked'] is True
    assert d['cra_record']['ce_status'] == 'ce_angebracht'
    assert d['cra_record']['nb_kennnummer'] == '1234'


def test_cra_link_manual_override_ignores_cra(client, auth_headers, projekt, _tmp_db):
    _db, cra_db = _tmp_db
    _seed_cra(cra_db)
    client.put(f'{CONF}/projekte/{PROJ}/cra-link', headers=auth_headers,
               json={'linked_cra_projekt': 'CRA-Prod'})
    # Manuell überstimmen → keine Automatik-Übernahme.
    r = client.put(f'{CONF}/projekte/{PROJ}/cra-link', headers=auth_headers,
                   json={'manual_override': True})
    d = r.get_json()
    assert d['manual_override'] is True
    assert d['linked'] is False
    assert d['cra_record'] is None


def test_cra_link_clear(client, auth_headers, projekt, _tmp_db):
    _db, cra_db = _tmp_db
    _seed_cra(cra_db)
    client.put(f'{CONF}/projekte/{PROJ}/cra-link', headers=auth_headers,
               json={'linked_cra_projekt': 'CRA-Prod'})
    r = client.put(f'{CONF}/projekte/{PROJ}/cra-link', headers=auth_headers,
                   json={'linked_cra_projekt': '', 'manual_override': False})
    d = r.get_json()
    assert d['linked'] is False and d['linked_cra_projekt'] == ''


def test_conformity_manual_without_cra_link(client, auth_headers, projekt):
    """Grundfall: Bewertung vollständig manuell, OHNE jede CRA-Verknüpfung."""
    r = client.put(f'{CONF}/projekte/{PROJ}/conformity', headers=auth_headers,
                   json={'verfahren': 'annex_vi_intern', 'ergebnis': 'konform',
                         'qms_geprueft': True, 'techdoc_geprueft': True})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['doc_gate']['assessment_complete'] is True
    # CRA-Link bleibt leer
    link = client.get(f'{CONF}/projekte/{PROJ}/cra-link', headers=auth_headers).get_json()
    assert link['linked'] is False
