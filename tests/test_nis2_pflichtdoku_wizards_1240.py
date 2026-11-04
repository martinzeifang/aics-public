"""Sprint #28 (#1240) — NIS2 Pflichtdokument-Generatoren (Art. 21(2)).

Je Pflichtdokument ein Copy/Paste-Doc-only-Wizard: Prompt (kontext-bewusst aus
N1/N3/N4/N5) + Parse (Vorschau + Plausibilität). Persistenz erfolgt im Frontend
über „Als Dokument speichern" (#1235) → managed_doc. Hier: reine
Builder/Parser-Tests (DB-frei, voll isoliert) + API-Prompt-Smoke + Katalog-Wiring.
"""
from __future__ import annotations

import pytest

from nis2 import ai_wizards as w
from shared.documents import catalog as dcat


PROJEKT = {
    "name": "ACME-NIS2",
    "unternehmen": "ACME GmbH",
    "beschreibung": "Energieversorger",
}


# ── Builder: Kontext + Pflichtinhalte im Prompt ─────────────────────────────

def test_is_leitlinie_prompt_uses_asset_context():
    assets = [{"asset_name": "ERP", "kritikalitaet": "kritisch"},
              {"asset_name": "DMS", "kritikalitaet": "mittel"}]
    p = w.build_is_leitlinie_prompt(PROJEKT, assets)
    assert "ACME GmbH" in p
    assert "Art. 21 Abs. 2 lit. a" in p
    assert "ERP" in p                # Asset-Kontext eingebaut
    assert "1 hoch/kritisch" in p
    assert "doc_text" in p           # JSON-Schema vorhanden


def test_is_leitlinie_prompt_without_assets():
    p = w.build_is_leitlinie_prompt(PROJEKT, [])
    assert "Noch kein Asset-Inventar" in p


def test_incident_handling_konzept_prompt_uses_ir():
    ir = {"csirt_kontakt": "CERT-Bund", "early_warning_sla": "24h"}
    p = w.build_incident_handling_konzept_prompt(PROJEKT, ir)
    assert "Art. 21 Abs. 2 lit. b" in p
    assert "Art. 23" in p
    assert "CERT-Bund" in p


def test_bcm_dr_prompt_uses_rpo_rto():
    bcp = {"rpo_minuten": 5, "rto_minuten": 30, "backup_strategie": "3-2-1"}
    p = w.build_bcm_dr_plan_prompt(PROJEKT, bcp)
    assert "Art. 21 Abs. 2 lit. c" in p
    assert "5 Minuten" in p and "30 Minuten" in p
    assert "3-2-1" in p


def test_lieferketten_prompt_uses_vendors():
    vendors = [{"vendor_name": "CloudCo", "leistung": "IaaS", "kritikalitaet": "hoch"}]
    p = w.build_lieferketten_richtlinie_prompt(PROJEKT, vendors)
    assert "Art. 21 Abs. 2 lit. d" in p
    assert "CloudCo" in p
    assert "1 hoch/kritisch" in p


def test_krypto_prompt_mentions_tr02102():
    p = w.build_krypto_richtlinie_prompt(PROJEKT)
    assert "Art. 21 Abs. 2 lit. h" in p
    assert "TR-02102" in p
    assert "AES-256" in p


def test_zugriffskontroll_prompt_uses_assets_and_mfa():
    p = w.build_zugriffskontroll_policy_prompt(PROJEKT, [{"asset_name": "AD"}])
    assert "lit. i und j" in p
    assert "MFA" in p
    assert "AD" in p


# ── Parser: doc_text-Extraktion + Plausibilität ─────────────────────────────

def test_parse_doc_response_extracts_text():
    raw = """```json
    {"titel": "IS-Leitlinie — ACME", "doc_text": "# Geltungsbereich\\nDieser Geltungsbereich umfasst Rollen und Risikoanalyse.",
     "abgedeckte_punkte": ["Geltungsbereich"], "offene_punkte": ["Übersicht"]}
    ```"""
    out = w.parse_is_leitlinie_response(raw)
    assert out["titel"].startswith("IS-Leitlinie")
    assert "Geltungsbereich" in out["doc_text"]
    assert out["abgedeckte_punkte"] == ["Geltungsbereich"]
    assert out["offene_punkte"] == ["Übersicht"]
    assert "plausibilitaet_hinweise" in out


def test_parse_doc_response_flags_missing_text():
    out = w.parse_bcm_dr_plan_response("kein json")
    assert out["doc_text"] == ""
    assert any("Kein Dokumenttext" in h for h in out["plausibilitaet_hinweise"])


def test_parse_doc_response_flags_missing_pflichtpunkt():
    raw = '{"doc_text": "Nur ein kurzer Satz ohne Pflichtinhalte."}'
    out = w.parse_krypto_richtlinie_response(raw)
    # 'Algorithmen' u.a. fehlen im Text → Hinweise
    assert any("Pflichtpunkt" in h for h in out["plausibilitaet_hinweise"])


def test_all_six_builders_and_parsers_callable():
    for fn in (
        w.build_is_leitlinie_prompt, w.build_incident_handling_konzept_prompt,
        w.build_bcm_dr_plan_prompt, w.build_lieferketten_richtlinie_prompt,
        w.build_krypto_richtlinie_prompt, w.build_zugriffskontroll_policy_prompt,
        w.parse_is_leitlinie_response, w.parse_incident_handling_konzept_response,
        w.parse_bcm_dr_plan_response, w.parse_lieferketten_richtlinie_response,
        w.parse_krypto_richtlinie_response, w.parse_zugriffskontroll_policy_response,
    ):
        assert callable(fn)


# ── Katalog-Wiring: suggested_assistant je DocSpec (#1240) ──────────────────

EXPECTED_ASSISTANT = {
    "is_leitlinie": "nis2-is-leitlinie",
    "incident_handling_konzept": "nis2-incident-handling-konzept",
    "bcm_dr_plan": "nis2-bcm-dr-plan",
    "lieferketten_richtlinie": "nis2-lieferketten-richtlinie",
    "krypto_richtlinie": "nis2-krypto-richtlinie",
    "zugriffskontroll_policy": "nis2-zugriffskontroll-policy",
    "incident_meldung": "n8",
}


def test_catalog_assistant_wiring():
    specs = {s["doc_type"]: s for s in dcat.get_catalog("nis2")}
    # Alle 7 Pflichtdokumente haben einen Assistenten.
    for doc_type, assistant in EXPECTED_ASSISTANT.items():
        assert doc_type in specs, f"DocSpec {doc_type} fehlt"
        assert specs[doc_type]["suggested_assistant"] == assistant


# ── API-Smoke: Prompt-Endpunkte liefern Text, doc-only (kein Apply) ─────────

BASE = "/api/nis2"
PROJ = "pytest-nis2-pflichtdoku-1240"

DOC_WIZARDS = [
    "is-leitlinie", "incident-handling-konzept", "bcm-dr-plan",
    "lieferketten-richtlinie", "krypto-richtlinie", "zugriffskontroll-policy",
]


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = "ok", ["*"]
    yield
    cur.state, cur.modules = prev[0], prev[1]


@pytest.fixture
def projekt(client, auth_headers):
    client.delete(f"{BASE}/projekte/{PROJ}", headers=auth_headers)
    client.post(f"{BASE}/projekte", headers=auth_headers,
                json={"name": PROJ, "unternehmen": "TestOrg"})
    yield PROJ
    client.delete(f"{BASE}/projekte/{PROJ}", headers=auth_headers)


@pytest.mark.parametrize("kind", DOC_WIZARDS)
def test_prompt_endpoint_returns_text(client, auth_headers, projekt, kind):
    r = client.get(f"{BASE}/projekte/{projekt}/wizards/{kind}/prompt",
                   headers=auth_headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["prompt"].strip()


@pytest.mark.parametrize("kind", DOC_WIZARDS)
def test_parse_endpoint_is_doc_only(client, auth_headers, projekt, kind):
    raw = '{"doc_text": "Beispieltext", "titel": "X"}'
    r = client.post(f"{BASE}/projekte/{projekt}/wizards/{kind}/parse",
                    headers=auth_headers, json={"response": raw})
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data["applied"] is False          # doc-only: keine Persistenz
    assert data["doc_text"] == "Beispieltext"


def test_prompt_requires_project(client, auth_headers):
    r = client.get(f"{BASE}/projekte/__missing__/wizards/is-leitlinie/prompt",
                   headers=auth_headers)
    assert r.status_code in (403, 404)


def test_assistant_doc_round_trip(client, auth_headers, projekt):
    """#1240↔#1235: Generator-Ergebnis als managed_doc speicher-/exportierbar."""
    base = "/api/nis2-dokumente"
    r = client.post(f"{base}/{projekt}", json={
        "doc_type": "is_leitlinie",
        "source": "assistant",
        "assistant_key": "nis2-is-leitlinie",
        "content_html": "<h1>IS-Leitlinie</h1><p>Geltungsbereich.</p>"},
        headers=auth_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    did = r.get_json()["id"]
    doc = client.get(f"{base}/{projekt}/{did}", headers=auth_headers).get_json()
    assert doc["source"] == "assistent" and doc["assistant_key"] == "nis2-is-leitlinie"
    # freigeben + DOCX-Export
    st = client.post(f"{base}/{projekt}/{did}/status",
                     json={"status": "freigegeben"}, headers=auth_headers)
    assert st.status_code == 200
    dx = client.post(f"{base}/{projekt}/{did}/export?format=docx", headers=auth_headers)
    assert dx.status_code == 200 and dx.data[:2] == b"PK"
    client.delete(f"{base}/{projekt}/{did}", headers=auth_headers)
