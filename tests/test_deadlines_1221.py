"""Phase 0 Deadline-Engine (Sprint #26, #1221)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shared import deadlines as dl


def _t(h: float) -> datetime:
    """Basis-Zeitpunkt h Stunden in der Vergangenheit (UTC)."""
    return datetime.now(timezone.utc) - timedelta(hours=h)


def test_parse_dt_variants():
    assert dl.parse_dt("2026-06-09").tzinfo is not None
    assert dl.parse_dt("2026-06-09T12:00:00Z").hour == 12
    assert dl.parse_dt("2026-06-09T12:00:00+02:00").hour == 10  # → UTC
    assert dl.parse_dt("") is None
    assert dl.parse_dt(None) is None
    assert dl.parse_dt("quatsch") is None


def test_add_months_leap_clamp():
    from datetime import date
    assert dl.add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)  # leap
    assert dl.add_months(date(2025, 1, 31), 1) == date(2025, 2, 28)
    assert dl.add_months(date(2025, 12, 15), 1) == date(2026, 1, 15)


def test_stage_status_on_track_amber_overdue():
    st = dl.DeadlineStage("meldung", "Meldung (72h)", 72.0)
    # Basis vor 1h → 71h übrig → grün/on_track
    r = dl.stage_status(_t(1), st)
    assert r["status"] == "on_track" and r["ampel"] == "green"
    # Basis vor 60h → 12h übrig (<25% von 72) → amber/due_soon
    r = dl.stage_status(_t(60), st)
    assert r["ampel"] == "amber" and r["status"] == "due_soon"
    # Basis vor 80h → überfällig
    r = dl.stage_status(_t(80), st)
    assert r["status"] == "overdue" and r["ampel"] == "red"
    assert r["hours_overdue"] >= 7


def test_stage_status_fulfilled_on_time_vs_late():
    st = dl.DeadlineStage("meldung", "Meldung (72h)", 72.0)
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    on_time = dl.stage_status(base, st, fulfilled_at="2026-01-03T00:00:00Z")
    assert on_time["status"] == "met" and on_time["ampel"] == "green"
    late = dl.stage_status(base, st, fulfilled_at="2026-01-05T00:00:00Z")
    assert late["status"] == "met" and late["ampel"] == "red"


def test_evaluate_nis2_set():
    res = dl.evaluate(_t(2), "nis2_art23")
    assert len(res["stages"]) == 3
    assert res["next_due"] is not None
    # frühwarnung (24h) zuerst fällig
    assert res["next_due"]["key"] == "fruehwarnung"


def test_evaluate_no_base_is_grey():
    res = dl.evaluate(None, "dsgvo_art33")
    assert res["overall_ampel"] == "grey"


def test_stage_sets_present():
    for key in ("dsgvo_art33", "nis2_art23", "cra_art14", "aiact_art73"):
        assert dl.stages_for(key), key
