"""S8 (#1078) — Zentrales Risiko-Cockpit: Aggregation + Normalisierung + Dedup.

Tests bauen separate temporäre rb-/cra-SQLite-Dateien (wie produktiv: getrennte
DB-Dateien) und prüfen ``shared.risk_cockpit.build_cockpit`` read-only.
"""
import sqlite3
from pathlib import Path

import pytest

from shared.risk_cockpit import (
    build_cockpit,
    collect_rb_risks,
    collect_cra_vulns,
    normalize_cra_severity,
    normalize_rb_severity,
)

_DIR = Path("data/db")


def _unlink(p: Path) -> None:
    for sfx in ("", "-wal", "-shm"):
        Path(str(p) + sfx).unlink(missing_ok=True)


def _make_rb(path: Path, *, with_provenance: bool) -> None:
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE rb_projekte (id INTEGER PRIMARY KEY, name TEXT UNIQUE, "
        "unternehmen TEXT DEFAULT '', firmen_id INTEGER)"
    )
    risk_cols = (
        "id INTEGER PRIMARY KEY, projekt_name TEXT, nr INTEGER DEFAULT 0, "
        "risk_name TEXT, beschreibung TEXT DEFAULT '', risikowert INTEGER, "
        "risiko_label TEXT DEFAULT '', is_resolved INTEGER NOT NULL DEFAULT 0"
    )
    if with_provenance:
        risk_cols += ", provenance_key TEXT DEFAULT ''"
    con.execute(f"CREATE TABLE rb_risiken ({risk_cols})")
    con.executemany(
        "INSERT INTO rb_projekte(id,name,unternehmen,firmen_id) VALUES(?,?,?,?)",
        [(1, "RBProj", "Cyberwoks", 7), (2, "OtherFirmProj", "Andere", 99)],
    )
    base = (
        "INSERT INTO rb_risiken(projekt_name,nr,risk_name,beschreibung,"
        "risikowert,risiko_label,is_resolved"
    )
    if with_provenance:
        con.execute(
            base + ",provenance_key) VALUES(?,?,?,?,?,?,?,?)",
            ("RBProj", 1, "Promoted CVE", "x", 12, "Sehr hoch", 0, "cve:cve-2024-0001"),
        )
    else:
        # Same logical risk, but no provenance_key column → no dedup possible
        con.execute(
            base + ") VALUES(?,?,?,?,?,?,?)",
            ("RBProj", 1, "Promoted CVE", "x", 12, "Sehr hoch", 0),
        )
    con.execute(
        base + ") VALUES(?,?,?,?,?,?,?)",
        ("RBProj", 2, "Offenes Risiko", "y", 8, "Hoch", 0),
    )
    con.execute(
        base + ") VALUES(?,?,?,?,?,?,?)",
        ("RBProj", 3, "Erledigtes Risiko", "z", 4, "Mittel", 1),  # resolved → skip
    )
    con.execute(
        base + ") VALUES(?,?,?,?,?,?,?)",
        ("OtherFirmProj", 1, "Fremd", "", 12, "Sehr hoch", 0),  # andere Firma → skip
    )
    con.commit()
    con.close()


def _make_cra(path: Path) -> None:
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE cra_projekte (id INTEGER PRIMARY KEY, name TEXT UNIQUE, "
        "unternehmen TEXT DEFAULT '', firmen_id INTEGER)"
    )
    con.execute(
        "CREATE TABLE cra_vuln (id INTEGER PRIMARY KEY, projekt_name TEXT, "
        "cve_id TEXT, titel TEXT DEFAULT '', schwere TEXT DEFAULT 'unknown', "
        "cvss_score REAL DEFAULT 0.0, status TEXT DEFAULT 'open', "
        "triage_kommentar TEXT DEFAULT '')"
    )
    con.executemany(
        "INSERT INTO cra_projekte(id,name,unternehmen,firmen_id) VALUES(?,?,?,?)",
        [(1, "CRAProj", "Cyberwoks", 7)],
    )
    con.executemany(
        "INSERT INTO cra_vuln(projekt_name,cve_id,titel,schwere,cvss_score,status) "
        "VALUES(?,?,?,?,?,?)",
        [
            ("CRAProj", "CVE-2024-0001", "Critical RCE", "critical", 9.8, "open"),
            ("CRAProj", "CVE-2024-0002", "Medium XSS", "medium", 5.4, "triaging"),
            ("CRAProj", "CVE-2024-0003", "Fixed bug", "high", 7.1, "fixed"),  # closed
        ],
    )
    con.commit()
    con.close()


@pytest.fixture
def dbs(request):
    with_prov = getattr(request, "param", True)
    _DIR.mkdir(parents=True, exist_ok=True)
    rb = _DIR / "_pytest_cockpit_rb.sqlite"
    cra = _DIR / "_pytest_cockpit_cra.sqlite"
    _unlink(rb)
    _unlink(cra)
    _make_rb(rb, with_provenance=with_prov)
    _make_cra(cra)
    yield rb, cra
    _unlink(rb)
    _unlink(cra)


# ── Normalisierung ──────────────────────────────────────────────────────────

def test_normalize_cra_severity():
    assert normalize_cra_severity("critical") == "critical"
    assert normalize_cra_severity("HIGH") == "high"
    assert normalize_cra_severity("mittel") == "medium"
    assert normalize_cra_severity("low") == "low"
    assert normalize_cra_severity("") == "unknown"


def test_normalize_rb_severity_label_and_numeric():
    assert normalize_rb_severity("Sehr hoch") == "critical"
    assert normalize_rb_severity("Hoch") == "high"
    assert normalize_rb_severity("Mittel") == "medium"
    assert normalize_rb_severity("gering") == "low"
    # Numeric fallback (TARA 1..4 scale)
    assert normalize_rb_severity("", 4) == "critical"
    assert normalize_rb_severity("", 3) == "high"
    assert normalize_rb_severity(None, None) == "unknown"


# ── Read-only-Collectors ────────────────────────────────────────────────────

@pytest.mark.parametrize("dbs", [True], indirect=True)
def test_collect_rb_only_open_and_firm(dbs):
    rb, _cra = dbs
    rows = collect_rb_risks(rb, 7)
    titles = {r["titel"] for r in rows}
    # resolved + andere Firma rausgefiltert
    assert "Erledigtes Risiko" not in titles
    assert "Fremd" not in titles
    assert all(r["source"] == "rb" and r["status"] == "open" for r in rows)


@pytest.mark.parametrize("dbs", [True], indirect=True)
def test_collect_cra_excludes_closed(dbs):
    _rb, cra = dbs
    rows = collect_cra_vulns(cra, 7)
    cves = {r["cve_id"] for r in rows}
    assert "CVE-2024-0001" in cves
    assert "CVE-2024-0002" in cves
    assert "CVE-2024-0003" not in cves  # fixed
    assert all(r["source"] == "cra" for r in rows)


# ── Dedup (provenance_key present) ──────────────────────────────────────────

@pytest.mark.parametrize("dbs", [True], indirect=True)
def test_build_cockpit_dedup_cra_wins(dbs):
    rb, cra = dbs
    out = build_cockpit(7, rb_db=rb, cra_db=cra)
    refs = [it["ref"] for it in out["items"]]
    # RB-Duplikat (provenance cve-2024-0001) unterdrückt; CRA-CVE bleibt
    assert "rb:1" not in refs
    assert "cra:CVE-2024-0001" in refs
    # Offenes RB-Risiko ohne provenance bleibt
    assert any(it["titel"] == "Offenes Risiko" for it in out["items"])


@pytest.mark.parametrize("dbs", [True], indirect=True)
def test_build_cockpit_summary_and_sort(dbs):
    rb, cra = dbs
    out = build_cockpit(7, rb_db=rb, cra_db=cra)
    # 2 cra (open/triaging) + 1 rb (Offenes Risiko); dup removed
    assert out["summary"]["total"] == 3
    assert out["summary"]["by_source"]["cra"] == 2
    # Highest severity first
    assert out["items"][0]["severity"] == "critical"
    assert "CRAProj" in out["summary"]["projekte"]


# ── Dedup graceful when provenance_key column absent ─────────────────────────

@pytest.mark.parametrize("dbs", [False], indirect=True)
def test_build_cockpit_without_provenance_column(dbs):
    rb, cra = dbs
    out = build_cockpit(7, rb_db=rb, cra_db=cra)
    # No provenance → no dedup → the promoted RB risk stays in addition
    titles = {it["titel"] for it in out["items"]}
    assert "Promoted CVE" in titles
    assert "CVE-2024-0001" in {it.get("cve_id") for it in out["items"]}


def test_missing_dbs_returns_empty():
    out = build_cockpit(
        7, rb_db=Path("/nonexistent/rb.sqlite"), cra_db=Path("/nonexistent/cra.sqlite")
    )
    assert out["items"] == []
    assert out["summary"]["total"] == 0
