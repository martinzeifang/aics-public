"""#1087 — OWASP-LLM-Top-10-Register: DB-Status, Auto-Detect (token-aware),
KI-Wizard-Parse. Compliance: maps_to-Mapping bleibt unverändert."""
from pathlib import Path

import pytest

import ai_act.db as db
import ai_act.owasp_llm_register as reg
from ai_act.owasp_llm_top10 import OWASP_LLM_TOP10


@pytest.fixture()
def db_path() -> Path:
    # connect_sqlite erzwingt Pfad-Containment im Workspace-Root → DB in data/db/.
    import uuid
    root = Path(__file__).resolve().parent.parent
    p = root / "data" / "db" / f"_test_owasp_llm_{uuid.uuid4().hex}.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    db.ensure_db(p)
    try:
        yield p
    finally:
        for suffix in ("", "-wal", "-shm"):
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()


# ── DB: Status-Verwaltung (Skala 0-5) ───────────────────────────────────────

def test_upsert_and_load_status(db_path: Path):
    db.upsert_owasp_llm_check(db_path, projekt_name="P", llm_id="LLM01",
                              status=4, kommentar="ok",
                              evidence=[{"url": "u", "path": "p"}])
    saved = db.load_owasp_llm_checks(db_path, "P")
    assert saved["LLM01"]["status"] == 4
    assert saved["LLM01"]["kommentar"] == "ok"
    assert saved["LLM01"]["evidence"] == [{"url": "u", "path": "p"}]


def test_status_is_clamped(db_path: Path):
    db.upsert_owasp_llm_check(db_path, projekt_name="P", llm_id="LLM02", status=99)
    db.upsert_owasp_llm_check(db_path, projekt_name="P", llm_id="LLM03", status=-5)
    saved = db.load_owasp_llm_checks(db_path, "P")
    assert saved["LLM02"]["status"] == 0
    assert saved["LLM03"]["status"] == 0


def test_upsert_is_idempotent(db_path: Path):
    db.upsert_owasp_llm_check(db_path, projekt_name="P", llm_id="LLM01", status=2)
    db.upsert_owasp_llm_check(db_path, projekt_name="P", llm_id="LLM01", status=5,
                              kommentar="upd")
    saved = db.load_owasp_llm_checks(db_path, "P")
    assert len(saved) == 1
    assert saved["LLM01"]["status"] == 5
    assert saved["LLM01"]["kommentar"] == "upd"


def test_does_not_touch_a1a5_tables(db_path: Path):
    # Writing an OWASP-LLM check must not create rows in A1-A5 tables.
    db.upsert_owasp_llm_check(db_path, projekt_name="P", llm_id="LLM01", status=3)
    assert db.load_system_doku(db_path, "P") is None
    assert db.load_human_oversight(db_path, "P") is None
    assert db.load_pmm(db_path, "P") is None


# ── Compliance: Mapping bleibt unverändert ──────────────────────────────────

def test_maps_to_preserved_in_register_items():
    items = {it["id"]: it for it in reg.register_items()}
    for src in OWASP_LLM_TOP10:
        assert items[src["id"]]["maps_to"] == src["maps_to"]
    # LLM01 muss weiterhin auf Art.15-nahe AIA-HR-07/05 mappen.
    assert "AIA-HR-07" in items["LLM01"]["maps_to"]


def test_register_has_all_ten_items():
    ids = [it["id"] for it in reg.register_items()]
    assert ids == [f"LLM{n:02d}" for n in range(1, 11)]
    for it in reg.register_items():
        assert it["hint"]  # jede Heuristik hat einen Hint


# ── Auto-Detect: 10 Heuristiken + token-aware Threading (#1064) ──────────────

def test_autodetect_invalid_repo_raises():
    with pytest.raises(ValueError):
        reg.autodetect_owasp_llm(repo="", token=None)


def test_autodetect_threads_token(monkeypatch):
    """Der token muss in github_path_exists/github_fetch_text durchgereicht werden."""
    seen_tokens = []

    def fake_exists(o, n, p, b="", token=None):
        seen_tokens.append(token)
        return (False, None)

    def fake_fetch(o, n, p, b="", token=None):
        seen_tokens.append(token)
        return None

    monkeypatch.setattr(reg, "github_path_exists", fake_exists)
    monkeypatch.setattr(reg, "github_fetch_text", fake_fetch)

    results = reg.autodetect_owasp_llm(repo="owner/repo", token="TOK-LLM")
    assert len(results) == 10
    assert all(not r.matched for r in results)
    # Mindestens ein Aufruf, und alle Aufrufe trugen den Token.
    assert seen_tokens
    assert all(t == "TOK-LLM" for t in seen_tokens)


def test_autodetect_positive_hit_for_dependency_pinning(monkeypatch):
    """LLM08 (Dependency-Pinning) greift, wenn requirements.txt existiert."""
    def fake_exists(o, n, p, b="", token=None):
        if p in ("requirements.txt", "shared/redaction.py", "shared/audit.py",
                 "shared/encoding.py"):
            return (True, {"url": f"https://github.com/{o}/{n}/blob/main/{p}", "path": p})
        return (False, None)

    monkeypatch.setattr(reg, "github_path_exists", fake_exists)
    monkeypatch.setattr(reg, "github_fetch_text", lambda *a, **k: None)

    results = {r.llm_id: r for r in reg.autodetect_owasp_llm(repo="o/r", token=None)}
    assert results["LLM08"].matched is True
    assert results["LLM08"].status >= 4
    assert results["LLM08"].evidence


def test_autodetect_scan_match_in_file(monkeypatch):
    """LLM01 greift bei add_untrusted_block in security_utils.py."""
    def fake_exists(o, n, p, b="", token=None):
        return (True, {"url": f"https://github.com/{o}/{n}/blob/main/{p}", "path": p})

    def fake_fetch(o, n, p, b="", token=None):
        if p == "security_utils.py":
            return "def add_untrusted_block(): ..."
        return None

    monkeypatch.setattr(reg, "github_path_exists", fake_exists)
    monkeypatch.setattr(reg, "github_fetch_text", fake_fetch)

    results = {r.llm_id: r for r in reg.autodetect_owasp_llm(repo="o/r", token=None)}
    assert results["LLM01"].matched is True
    assert results["LLM01"].status >= 4


# ── KI-Wizard: Prompt + Parse ───────────────────────────────────────────────

def test_build_prompt_lists_all_items():
    prompt = reg.build_owasp_llm_prompt({"name": "Sys", "organisation": "Org"})
    for n in range(1, 11):
        assert f"LLM{n:02d}" in prompt
    assert "Art. 9" in prompt and "Art. 15" in prompt


def test_parse_response_object_form():
    raw = """Hier:
```json
{"items": [
  {"id": "LLM01", "status": 4, "kommentar": "guards vorhanden"},
  {"id": "LLM02", "status": 2, "kommentar": "teilweise"}
]}
```"""
    items = reg.parse_owasp_llm_response(raw)
    assert {i["id"] for i in items} == {"LLM01", "LLM02"}
    assert items[0]["status"] == 4


def test_parse_response_array_form_and_clamping():
    raw = '[{"id": "llm03", "status": 9}, {"id": "BOGUS", "status": 1}]'
    items = reg.parse_owasp_llm_response(raw)
    assert len(items) == 1
    assert items[0]["id"] == "LLM03"
    assert items[0]["status"] == 5  # 9 → geklemmt


def test_parse_response_empty_on_garbage():
    assert reg.parse_owasp_llm_response("kein json") == []
    assert reg.parse_owasp_llm_response("") == []
