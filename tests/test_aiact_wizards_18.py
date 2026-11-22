"""Unit-Tests für die AI-Act Copy-Paste-Wizards (#1022/#1023/#1024).

Reine Prompt-/Parse-Lib + statische PMM-Hilfe — keine Netz-/LLM-Zugriffe.
"""
from __future__ import annotations

from ai_act import ai_wizards as w
from ai_act.pmm_help import get_pmm_help


PROJEKT = {'name': 'KreditScore', 'organisation': 'ACME GmbH', 'produkt': 'LoanBot'}
SYSTEM_DOKU = {
    'system_name': 'KreditScore-v2',
    'architecture': 'XGBoost + Feature-Store',
    'intended_purpose': 'Bonitätsbewertung von Kreditanträgen',
}


# A3 (Art. 9): Risk-Register-Wizard entfernt (#1047) — A3-Risiken werden im
# Risikobewertungs-Modul gepflegt. Siehe test_aiact_risk_link_1044.py.


# ─────────────────────────────────────────────────────────────────────────
# Story 5 — Human-Oversight (Art. 14)
# ─────────────────────────────────────────────────────────────────────────

def test_build_human_oversight_prompt_core_terms():
    p = w.build_human_oversight_prompt(PROJEKT, SYSTEM_DOKU)
    assert 'Art. 14' in p
    for kw in ('oversight_mode', 'oversight_persons', 'intervention_mechanisms',
               'monitoring_interface', 'output_interpretation_aids',
               'abnormal_behavior_detection', 'training_program'):
        assert kw in p


def test_parse_human_oversight_object_with_fence():
    raw = """```json
{"oversight_mode": "human-on-the-loop",
 "oversight_persons": [{"rolle": "Operator"}],
 "intervention_mechanisms": "Stop-Button",
 "monitoring_interface": "Dashboard",
 "output_interpretation_aids": "Confidence",
 "abnormal_behavior_detection": "Drift-Alarm",
 "training_program": "jährlich"}
```"""
    d = w.parse_human_oversight_response(raw)
    assert d['oversight_mode'] == 'human-on-the-loop'
    assert d['oversight_persons'] == [{'rolle': 'Operator'}]
    assert d['intervention_mechanisms'] == 'Stop-Button'


def test_parse_human_oversight_garbage_returns_empty_dict():
    # #1043: ohne erkennbares JSON → leeres Dict (kein Default-Apply, sonst
    # würde der Wizard leere Defaults über bestehende Werte schreiben)
    assert w.parse_human_oversight_response('blubb') == {}


# ─────────────────────────────────────────────────────────────────────────
# Story 6 — Post-Market-Monitoring (Art. 72/73)
# ─────────────────────────────────────────────────────────────────────────

def test_build_pmm_plan_prompt_core_terms_and_risk_ref():
    risks = [
        {'risk_id': 'AIA-R-001', 'titel': 'Bias', 'risk_category': 'bias', 'severity': 'hoch'},
    ]
    p = w.build_pmm_plan_prompt(PROJEKT, SYSTEM_DOKU, risk_items=risks)
    assert 'Art. 72' in p
    assert 'Art. 73' in p
    for kw in ('monitoring_plan', 'performance_metrics', 'drift_detection',
               'user_feedback_channel', 'incident_threshold',
               'market_surveillance_contact', 'serious_incident_reporting_sla'):
        assert kw in p
    # referenziert übergebene A3-Risiken
    assert 'AIA-R-001' in p


def test_build_pmm_plan_prompt_without_risks():
    p = w.build_pmm_plan_prompt(PROJEKT, SYSTEM_DOKU)
    assert 'Art. 72' in p


def test_parse_pmm_object_with_fence():
    raw = """```json
{"monitoring_plan": "kontinuierlich",
 "performance_metrics": "Accuracy",
 "drift_detection": "PSI",
 "user_feedback_channel": "In-App",
 "incident_threshold": "Abfall > 5%",
 "market_surveillance_contact": "BNetzA",
 "serious_incident_reporting_sla": "15 Tage"}
```"""
    d = w.parse_pmm_response(raw)
    assert d['monitoring_plan'] == 'kontinuierlich'
    assert d['incident_threshold'] == 'Abfall > 5%'
    assert d['serious_incident_reporting_sla'] == '15 Tage'


def test_parse_pmm_garbage_returns_empty_dict():
    # #1043: kein JSON → {} (nicht nur Default-SLA, sonst „erfolgreiches" Leer-Apply)
    assert w.parse_pmm_response('nichts hier') == {}


# ─────────────────────────────────────────────────────────────────────────
# PMM-Hilfe (statisch)
# ─────────────────────────────────────────────────────────────────────────

def test_get_pmm_help_keys():
    h = get_pmm_help()
    for key in ('behoerde', 'monitoring_plan_snippets', 'incident_threshold_examples',
                'eu_articles', 'serious_incident_reporting_sla_default'):
        assert key in h
    assert h['serious_incident_reporting_sla_default'] == '15 Tage'
    assert isinstance(h['monitoring_plan_snippets'], list)
    assert h['monitoring_plan_snippets']
    assert isinstance(h['incident_threshold_examples'], list)
    # Artikel-Hinweise vorhanden
    joined = ' '.join(h['eu_articles'])
    assert 'Art. 72' in joined and 'Art. 73' in joined
    # BNetzA als Behörde genannt
    assert 'Bundesnetzagentur' in h['behoerde'] or 'BNetzA' in h['behoerde']
