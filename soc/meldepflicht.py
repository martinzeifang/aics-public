"""Meldepflicht-Router (#1281).

Ein bestätigter Incident löst — je nach betroffenem Asset — automatisch die
einschlägigen Meldetracks aus: DSGVO Art. 33/34, NIS2 Art. 23, CRA Art. 14,
AI-Act Art. 73, DORA Art. 19 (Stub). Statt manuell zu raten, was wo zu melden
ist, leitet der Router die Pflichten aus den Asset-Compliance-Tags ab und
berechnet die Fristen ab dem Awareness-Zeitpunkt.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from soc import db as sdb
from soc.constants import REGIMES


def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    txt = str(s).strip().replace("Z", "+00:00")
    for fmt in (None,):  # try fromisoformat first
        try:
            dt = datetime.fromisoformat(txt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            break
    # Fallback: 'YYYY-MM-DD HH:MM:SS'
    try:
        return datetime.strptime(txt[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _deadlines_for(regime_key: str, awareness: datetime) -> list[dict[str, Any]]:
    spec = REGIMES[regime_key]
    out = []
    for dl in spec["deadlines"]:
        hours = dl.get("hours")
        due = (awareness + timedelta(hours=hours)).isoformat() if hours is not None else None
        out.append({"key": dl["key"], "label": dl["label"], "hours": hours,
                    "due_at": due, "done": False})
    return out


def triggered_regimes(asset: dict[str, Any] | None, *, personal_data_involved: bool = False) -> list[str]:
    """Welche Regime sind für dieses Asset/diesen Incident einschlägig?"""
    flags = dict(asset or {})
    if personal_data_involved:
        flags["personenbezogen"] = True
    out = []
    for key, spec in REGIMES.items():
        if flags.get(spec["trigger_flag"]):
            out.append(key)
    return out


def evaluate_incident(db_path: Path, incident_id: int, *, actor: str = "") -> dict[str, Any]:
    """Wertet einen Incident aus und legt/aktualisiert die fälligen Meldetracks an."""
    inc = sdb.get_incident(db_path, incident_id)
    if not inc:
        return {"ok": False, "error": "Incident nicht gefunden"}
    # Flags aus (a) verknüpftem Asset + (b) am Incident direkt gewählten Regelwerken
    asset = sdb.get_asset(db_path, inc["asset_id"]) if inc.get("asset_id") else None
    flags: dict = dict(asset or {})
    flags.update((inc.get("meta_json") or {}).get("regime_flags") or {})
    awareness = _parse_dt(inc.get("awareness_at") or inc.get("created_at"))
    regimes = triggered_regimes(flags, personal_data_involved=inc.get("personal_data_involved", False))

    created = []
    for key in regimes:
        spec = REGIMES[key]
        deadlines = _deadlines_for(key, awareness)
        tid = sdb.upsert_meldetrack(db_path, incident_id, regime=key, legal=spec["legal"],
                                    deadlines=deadlines)
        created.append({"regime": key, "label": spec["label"], "legal": spec["legal"],
                        "track_id": tid, "stub": spec.get("stub", False)})
    if created:
        sdb.add_timeline_note(db_path, incident_id, actor=actor or "router",
                              detail=f"Meldepflicht-Router: Tracks {', '.join(c['regime'] for c in created)} ausgelöst")
    return {"ok": True, "regimes": regimes, "tracks": created,
            "asset": asset.get("agent_name") if asset else None,
            "awareness_at": awareness.isoformat()}
