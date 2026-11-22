"""AI-Act Art. 73 — Serious-Incident-Register mit Fristenuhr (2/10/15 Tage, #1197).

Self-contained DB-Layer auf der gemeinsamen ``data/db/ai_act.sqlite`` (via
:func:`ai_act.db._connect`). Bildet schwerwiegende Vorfälle nach Art. 73 ab:
Eintritts-/Kenntnis-Zeitpunkt, Schweregrad-Klasse mit gesetzlich abgeleiteter
Meldefrist, Status-Lifecycle (offen → erstbericht → vollbericht → abgeschlossen)
und einen Behörden-/Einreichungsnachweis.

Die Fristenuhr (Ampel/Countdown/Überfälligkeit) wird NICHT hier dupliziert,
sondern über die kanonische Engine :mod:`shared.deadlines` (Stage-Set
``aiact_art73``) berechnet — Single Source of Truth.

Tabelle: ``aiact_incidents`` (eine Zeile je Vorfall, projekt-scoped).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_act.db import _connect

import shared.deadlines as dl

DB_PATH = Path("data/db/ai_act.sqlite")

# Schweregrad-Klassen → relevante Pflicht-Meldestufe (shared.deadlines aiact_art73).
# ``frist_tage`` ist die maßgebliche gesetzliche Frist in Tagen.
SCHWEREGRAD: dict[str, dict[str, Any]] = {
    "weit_verbreitet": {
        "label": "Weit verbreiteter Verstoß / KRITIS-Störung",
        "frist_tage": 2,
        "stage_key": "sofort",
    },
    "tod": {
        "label": "Tod einer Person",
        "frist_tage": 10,
        "stage_key": "todesfall",
    },
    "schwere_schaedigung": {
        "label": "Schwere Gesundheits-/Sachschädigung",
        "frist_tage": 15,
        "stage_key": "regelfrist",
    },
    "standard": {
        "label": "Sonstiger schwerwiegender Vorfall (Regelfrist)",
        "frist_tage": 15,
        "stage_key": "regelfrist",
    },
}

STATUS = ("offen", "erstbericht", "vollbericht", "abgeschlossen")

SCHEMA = """
CREATE TABLE IF NOT EXISTS aiact_incidents (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name      TEXT NOT NULL,
    titel             TEXT NOT NULL DEFAULT '',
    beschreibung      TEXT NOT NULL DEFAULT '',
    eintritts_datum   TEXT NOT NULL DEFAULT '',
    kenntnis_datum    TEXT NOT NULL DEFAULT '',
    schweregrad       TEXT NOT NULL DEFAULT 'standard',
    status            TEXT NOT NULL DEFAULT 'offen',
    behoerde          TEXT NOT NULL DEFAULT '',
    erstbericht_am    TEXT NOT NULL DEFAULT '',
    vollbericht_am    TEXT NOT NULL DEFAULT '',
    abgeschlossen_am  TEXT NOT NULL DEFAULT '',
    einreichungsnachweis TEXT NOT NULL DEFAULT '',
    capa_ref          TEXT NOT NULL DEFAULT '',
    report_text       TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL DEFAULT (aics_now()),
    updated_at        TEXT NOT NULL DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_incidents_projekt ON aiact_incidents(projekt_name);
"""

_FIELDS = (
    "titel", "beschreibung", "eintritts_datum", "kenntnis_datum", "schweregrad",
    "status", "behoerde", "erstbericht_am", "vollbericht_am", "abgeschlossen_am",
    "einreichungsnachweis", "capa_ref", "report_text",
)


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def schweregrade() -> list[dict[str, Any]]:
    """Statischer Katalog der Schweregrad-Klassen + abgeleiteter Frist."""
    return [{"code": k, **v} for k, v in SCHWEREGRAD.items()]


def _base_date(row: dict[str, Any]) -> str:
    """Basis-Zeitpunkt für die Fristenuhr: Kenntnis vor Eintritt (Art. 73)."""
    return row.get("kenntnis_datum") or row.get("eintritts_datum") or ""


def _fulfilled_map(row: dict[str, Any]) -> dict[str, str]:
    """Erfülltzeitpunkte je Stage-Key aus dem Status-Lifecycle ableiten.

    Eine erfolgte (Erst-/Voll-)Meldung erfüllt die maßgebliche Meldestufe der
    Schweregrad-Klasse — die Fristenuhr stoppt dann (met)."""
    sg = SCHWEREGRAD.get(row.get("schweregrad", "standard"), SCHWEREGRAD["standard"])
    stage_key = sg["stage_key"]
    meldung_am = row.get("vollbericht_am") or row.get("erstbericht_am") or ""
    return {stage_key: meldung_am} if meldung_am else {}


def _applicable_stages(row: dict[str, Any]) -> list[dl.DeadlineStage]:
    """Nur die für die Schweregrad-Klasse maßgebliche Meldestufe bewerten.

    Die Stufen ``sofort``/``todesfall``/``regelfrist`` schließen sich gegenseitig
    aus — ein 'standard'-Vorfall ist nicht an die 2-Tage-Frist gebunden. Wir
    filtern das kanonische Stage-Set auf die zutreffende Stufe."""
    sg = SCHWEREGRAD.get(row.get("schweregrad", "standard"), SCHWEREGRAD["standard"])
    stage_key = sg["stage_key"]
    return [s for s in dl.stages_for("aiact_art73") if s.key == stage_key]


def deadlines(row: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Fristenuhr über die kanonische Engine (Stage-Set ``aiact_art73``).

    Bewertet nur die für die Schweregrad-Klasse maßgebliche Meldestufe."""
    return dl.evaluate(
        _base_date(row), _applicable_stages(row),
        fulfilled=_fulfilled_map(row), now=now,
    )


def _enrich(row: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    sg = SCHWEREGRAD.get(row.get("schweregrad", "standard"), SCHWEREGRAD["standard"])
    d = dict(row)
    d["schweregrad_label"] = sg["label"]
    d["frist_tage"] = sg["frist_tage"]
    d["deadlines"] = deadlines(row, now=now)
    nd = d["deadlines"].get("next_due") or {}
    d["due_date"] = nd.get("due_at", "")
    d["ampel"] = d["deadlines"].get("overall_ampel", "grey")
    d["overdue"] = bool(d["deadlines"].get("any_overdue"))
    return d


def list_incidents(db_path: Path, projekt_name: str, *,
                   now: datetime | None = None) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM aiact_incidents WHERE projekt_name=? "
            "ORDER BY COALESCE(NULLIF(kenntnis_datum,''), eintritts_datum) DESC, id DESC",
            (projekt_name,),
        ).fetchall()
    finally:
        con.close()
    return [_enrich(dict(r), now=now) for r in rows]


def get_incident(db_path: Path, projekt_name: str, incident_id: int, *,
                 now: datetime | None = None) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        r = con.execute(
            "SELECT * FROM aiact_incidents WHERE id=? AND projekt_name=?",
            (incident_id, projekt_name),
        ).fetchone()
    finally:
        con.close()
    return _enrich(dict(r), now=now) if r else None


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    sg = str(data.get("schweregrad", "standard") or "standard")
    if sg not in SCHWEREGRAD:
        raise ValueError(f"Unbekannter Schweregrad: {sg!r}")
    status = str(data.get("status", "offen") or "offen")
    if status not in STATUS:
        raise ValueError(f"Ungültiger Status: {status!r}")
    out = {f: str(data.get(f, "") or "") for f in _FIELDS}
    out["schweregrad"] = sg
    out["status"] = status
    return out


def create_incident(db_path: Path, projekt_name: str, data: dict[str, Any]) -> int:
    ensure_table(db_path)
    vals = _validate(data)
    con = _connect(Path(db_path))
    try:
        cols = ", ".join(_FIELDS)
        ph = ", ".join("?" for _ in _FIELDS)
        cur = con.execute(
            f"INSERT INTO aiact_incidents (projekt_name, {cols}) VALUES (?, {ph})",
            (projekt_name, *[vals[f] for f in _FIELDS]),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def update_incident(db_path: Path, projekt_name: str, incident_id: int,
                    data: dict[str, Any]) -> bool:
    ensure_table(db_path)
    vals = _validate(data)
    con = _connect(Path(db_path))
    try:
        sets = ", ".join(f"{f}=?" for f in _FIELDS)
        cur = con.execute(
            f"UPDATE aiact_incidents SET {sets}, updated_at=aics_now() "
            "WHERE id=? AND projekt_name=?",
            (*[vals[f] for f in _FIELDS], incident_id, projekt_name),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def attach_report(db_path: Path, projekt_name: str, incident_id: int,
                  report_text: str) -> bool:
    """A23-Wizard-Reporttext an den Incident-Eintrag binden (statt nur Notiz)."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "UPDATE aiact_incidents SET report_text=?, updated_at=aics_now() "
            "WHERE id=? AND projekt_name=?",
            (str(report_text or ""), incident_id, projekt_name),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def delete_incident(db_path: Path, projekt_name: str, incident_id: int) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "DELETE FROM aiact_incidents WHERE id=? AND projekt_name=?",
            (incident_id, projekt_name),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def summary(db_path: Path, projekt_name: str, *,
            now: datetime | None = None) -> dict[str, Any]:
    items = list_incidents(db_path, projekt_name, now=now)
    offen = [i for i in items if i["status"] != "abgeschlossen"]
    overdue = [i for i in items if i["overdue"] and i["status"] != "abgeschlossen"]
    return {
        "gesamt": len(items),
        "offen": len(offen),
        "ueberfaellig": len(overdue),
        "abgeschlossen": len(items) - len(offen),
    }


def _row(r: Any) -> dict[str, Any]:  # pragma: no cover - convenience
    return dict(r)
