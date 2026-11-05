"""#1391 — generalisierter Berichts-Scheduler: Parse-/Validierungslogik (ohne DB/APScheduler)."""
import shared.reports.scheduler as sched


def _patch(monkeypatch, cfgs):
    monkeypatch.setattr(sched, "_load_cfg", lambda f: cfgs.get(f, {}))


def test_disabled_when_no_module_enabled(monkeypatch):
    _patch(monkeypatch, {})
    assert sched.report_scheduler_enabled() is False
    assert sched.parse_report_schedule() == []


def test_valid_spec_parsed_and_defaults(monkeypatch):
    _patch(monkeypatch, {"cra.config.json": {"berichte": {
        "scheduler_enabled": True,
        "schedule": [{"typ": "gesamt", "projekt": "P"}],  # periode/cron/format default
    }}})
    assert sched.report_scheduler_enabled() is True
    specs = sched.parse_report_schedule()
    assert len(specs) == 1
    s = specs[0]
    assert s["modul"] == "cra" and s["typ"] == "gesamt" and s["projekt"] == "P"
    assert s["periode"] == "quartal"
    assert s["format"] == "docx"
    assert len(s["cron"].split()) == 5
    assert s["job_id"] == "report:cra:gesamt:P:quartal"


def test_invalid_entries_skipped(monkeypatch):
    _patch(monkeypatch, {"nis2.config.json": {"berichte": {
        "scheduler_enabled": True,
        "schedule": [
            {"typ": "bogus-typ-xyz"},            # unbekannter typ
            {"typ": "gesamt", "cron": "0 6 1"},  # kaputter Cron (3 Felder)
            "nope",                               # kein Objekt
        ],
    }}})
    assert sched.parse_report_schedule() == []


def test_jahr_period_cron_default(monkeypatch):
    _patch(monkeypatch, {"dsgvo.config.json": {"berichte": {
        "scheduler_enabled": True,
        "schedule": [{"typ": "gesamt", "periode": "jahr", "format": "pdf"}],
    }}})
    specs = sched.parse_report_schedule()
    assert len(specs) == 1
    assert specs[0]["periode"] == "jahr"
    assert specs[0]["format"] == "pdf"
    # Jahres-Default-Cron: 1x im Jahr (Januar)
    assert specs[0]["cron"] == "0 7 1 1 *"
