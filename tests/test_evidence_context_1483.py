"""Evidenzbewusste KI-Bewertung (Sprint #40, #1483–#1498).

Reine Logik-Tests (ohne DB) für Aggregator, Prompt-Injektion und Provenienz +
ein Postgres-gestützter Integrationstest für den CRA-Provider.
"""
from __future__ import annotations

import pytest

from shared.evidence_context import (
    EvidenceItem, dedup_items, redact_for_cloud, rank_and_truncate, render_block,
    get_evidence_provider, build_context,
)
from server.services.anforderung_prompt import (
    evidence_section, build_anforderung_prompt, normalize_eval_parsed,
)


# ── Reine Aggregator-Helfer ──────────────────────────────────────────────────

def test_dedup_keeps_order_removes_duplicates():
    a = EvidenceItem("Q", "vuln", "r1", "t")
    b = EvidenceItem("Q", "risk", "r2", "t2")
    dup = EvidenceItem("Q", "vuln", "r1", "t")
    out = dedup_items([a, b, dup])
    assert [i.ref for i in out] == ["r1", "r2"]


def test_rank_orders_by_relevance_and_respects_budget():
    items = [EvidenceItem("Q", "k", "low", "x", relevance=0.5),
             EvidenceItem("Q", "k", "high", "y", relevance=2.0)]
    assert rank_and_truncate(items, 10000)[0].ref == "high"
    # winziges Budget → mind. das erste (höchstrelevante) Item, aber nicht beide
    assert len(rank_and_truncate(items, 5)) == 1


def test_redact_for_cloud_only_sensitive():
    items = [EvidenceItem("Q", "k", "ok", "Klartext", sensitive=False),
             EvidenceItem("Q", "k", "pii", "Datenpanne Müller", sensitive=True)]
    red = {i.ref: i.text for i in redact_for_cloud(items)}
    assert red["ok"] == "Klartext"
    assert "Müller" not in red["pii"] and "redigiert" in red["pii"]


def test_render_block_empty():
    assert render_block([]) == ""


# ── Prompt-Injektion + Rückwärtskompatibilität (#1485) ──────────────────────

def test_evidence_section_empty_is_noop():
    assert evidence_section("") == ""
    assert evidence_section("   ") == ""


def test_no_evidence_prompt_is_byte_identical():
    """Ohne Evidenz MUSS der Prompt identisch zum bisherigen Verhalten sein (#1496)."""
    req = {"id": "A1", "titel": "T", "kapitel": "K", "ref": "R",
           "beschreibung": "B", "hinweise": "H", "gewichtung": 2}
    proj = {"name": "P", "unternehmen": "Acme"}
    cur = {"bewertung": 2, "kommentar": "k", "massnahme": "m"}
    default = build_anforderung_prompt("CRA", "Cyber Resilience Act", req, proj, cur)
    empty = build_anforderung_prompt("CRA", "Cyber Resilience Act", req, proj, cur, evidence_block="")
    assert default == empty
    assert "Vorhandene Nachweise" not in default


def test_evidence_block_appears_when_present():
    req = {"id": "A1", "titel": "T", "kapitel": "K"}
    proj = {"name": "P"}
    cur = {}
    p = build_anforderung_prompt("CRA", "CRA", req, proj, cur,
                                 evidence_block="- **CRA Schwachstellen-Sync** (cra_vuln:1): 3 offene CVEs")
    assert "Vorhandene Nachweise" in p
    assert "genutzte_nachweise" in p
    assert "cra_vuln:1" in p


def test_normalize_parses_genutzte_nachweise_backward_compatible():
    n = normalize_eval_parsed({"score": 4, "kommentar": "ok", "massnahmen": ["x"],
                               "genutzte_nachweise": ["cra_vuln:CVE-1", "doc:7"]})
    assert n["score"] == 4
    assert n["genutzte_nachweise"] == ["cra_vuln:CVE-1", "doc:7"]
    # Altes Format ohne das Feld → leere Liste, kein Fehler
    assert normalize_eval_parsed({"score": 3, "kommentar": "ok"})["genutzte_nachweise"] == []


# ── Provider-Registry (#1484) ────────────────────────────────────────────────

@pytest.mark.parametrize("modul", ["cra", "nis2", "ai_act", "dsgvo", "wiba", "risikobewertung"])
def test_provider_registry_resolves(modul):
    prov = get_evidence_provider(modul)
    assert prov is not None
    assert hasattr(prov, "relevant_for")


def test_unknown_module_provider_is_none():
    assert get_evidence_provider("does-not-exist") is None


# ── Postgres-Integration: CRA-Provider liest echte Schwachstellen (#1488) ────

def test_cra_provider_surfaces_open_vuln(pg):
    """Eine offene cra_vuln muss als Evidenz für ART14-01 erscheinen (gegen echtes PG)."""
    from pathlib import Path
    from cra import db as cdb
    from cra.evidence_provider import relevant_for

    dbp = Path("data/db/cra.sqlite")
    cdb.ensure_db(dbp)
    projekt = "EvidenzTest"
    cdb.save_vuln(dbp, projekt, {
        "cve_id": "CVE-2026-9999", "titel": "Testlücke", "schwere": "high",
        "cvss_score": 8.1, "status": "open",
    })
    items = relevant_for({"name": projekt, "meta": {}}, {"id": "ART14-01", "kapitel": "ART14"})
    refs = " ".join(i.ref for i in items)
    texts = " ".join(i.text for i in items)
    assert any(i.kind == "vuln" for i in items), f"keine vuln-Evidenz: {refs}"
    assert "offene" in texts.lower() or "CVE-2026-9999" in texts


def test_build_context_best_effort_without_data(pg):
    """build_context wirft nie und liefert eine wohlgeformte Struktur."""
    ctx = build_context("cra", {"name": "LeeresProjekt"}, {"id": "ART13-05", "kapitel": "ART13"})
    assert set(ctx.keys()) == {"items", "rendered_block", "sources"}
    assert isinstance(ctx["items"], list)
