"""Datenhaltung des Compliance-Audits.

Liegt bewusst in **derselben** Datenbank wie das frühere Gutachten-Audit
(``data/db/gutachten.sqlite``) und nutzt dessen Tabellen weiter
(:mod:`gutachten.db`). Nur die Neuerungen von v7.4.0 stehen hier:

* Spalte ``gutachten_questions.erfuellung`` — die **kanonische** Erfüllung je
  Frage (``erfuellt``/``teilweise``/``nicht_erfuellt``/``nicht_anwendbar``/
  ``offen``). Vorher gab es nur das Freitextfeld ``bewertung`` mit einer je
  Projekt konfigurierbaren Skala; daraus lässt sich keine belastbare
  Compliance-Aussage rechnen. ``bewertung`` bleibt als Notiz des Auditors.
* Tabelle ``audit_wasserstand`` — erzeugte Wasserstandsmeldungen mit dem
  **berechneten** Stand und dem KI-Text, getrennt gespeichert. So bleibt
  nachvollziehbar, was gerechnet und was formuliert wurde.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared import db as _sdb

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_wasserstand (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_name  TEXT NOT NULL,
    stufe         TEXT NOT NULL DEFAULT 'unbewertet',
    quote_prozent REAL,
    status_json   TEXT NOT NULL DEFAULT '{}',
    ki_json       TEXT NOT NULL DEFAULT '{}',
    provider      TEXT NOT NULL DEFAULT '',
    erstellt_von  TEXT NOT NULL DEFAULT '',
    created_at    TEXT DEFAULT (aics_now())
);

CREATE INDEX IF NOT EXISTS idx_aw_project ON audit_wasserstand(project_name);
"""


def _connect(db_path: Path) -> Any:
    return _sdb.connect(db_path)


def ensure_db(db_path: Path) -> None:
    """Tabellen des Compliance-Audits anlegen/migrieren (idempotent)."""
    from gutachten.db import ensure_db as ensure_basis

    ensure_basis(db_path)  # Projekte/Fragen/Assessments (historische Namen)
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        # Kanonische Erfüllung je Frage (v7.4.0). Leer = noch nicht gesetzt →
        # status.erfuellung_of fällt dann auf das alte `bewertung` zurück.
        con.execute("ALTER TABLE gutachten_questions "
                    "ADD COLUMN IF NOT EXISTS erfuellung TEXT NOT NULL DEFAULT ''")
        con.commit()
    finally:
        con.close()


# ── Erfüllung je Frage ───────────────────────────────────────────────────────

def set_erfuellung(db_path: Path, question_id: int, erfuellung: str) -> bool:
    """Erfüllung einer Frage setzen. ``False`` wenn der Wert unbekannt ist."""
    from compliance_audit.status import ERFUELLUNG

    if erfuellung not in ERFUELLUNG:
        return False
    con = _connect(db_path)
    try:
        con.execute("UPDATE gutachten_questions SET erfuellung = ? WHERE id = ?",
                    (erfuellung, int(question_id)))
        con.commit()
        return True
    finally:
        con.close()


def backfill_erfuellung(db_path: Path, project_name: str) -> int:
    """Leere ``erfuellung`` aus dem alten Freitext ``bewertung`` ableiten.

    Einmalige Hilfe für Projekte von vor v7.4.0. Vorhandene Werte werden **nicht**
    überschrieben — eine bewusste Auditor-Entscheidung gewinnt immer.

    Returns:
        Anzahl geänderter Fragen.
    """
    from compliance_audit.status import normalize_erfuellung

    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT id, bewertung FROM gutachten_questions "
            "WHERE project_name = ? AND (erfuellung IS NULL OR erfuellung = '')",
            (project_name,)).fetchall()
        n = 0
        for r in rows:
            d = dict(r)
            # Ohne Freitext bleibt es `offen` — das ist der Default, also kein Update.
            if not (d.get('bewertung') or '').strip():
                continue
            con.execute("UPDATE gutachten_questions SET erfuellung = ? WHERE id = ?",
                        (normalize_erfuellung(d.get('bewertung')), int(d['id'])))
            n += 1
        con.commit()
        return n
    finally:
        con.close()


# ── Wasserstandsmeldungen ────────────────────────────────────────────────────

def save_wasserstand(db_path: Path, project_name: str, *, status: dict[str, Any],
                     ki: dict[str, Any] | None = None, provider: str = '',
                     erstellt_von: str = '') -> int:
    """Eine Wasserstandsmeldung ablegen und ihre ID zurückgeben."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO audit_wasserstand "
            "(project_name, stufe, quote_prozent, status_json, ki_json, provider, erstellt_von) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project_name, str(status.get('stufe') or 'unbewertet'),
             status.get('quote_prozent'),
             json.dumps(status, ensure_ascii=False),
             json.dumps(ki or {}, ensure_ascii=False),
             provider, erstellt_von))
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def list_wasserstand(db_path: Path, project_name: str,
                     *, limit: int = 20) -> list[dict[str, Any]]:
    """Verlauf der Wasserstandsmeldungen (neueste zuerst), ohne die JSON-Blobs."""
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT id, project_name, stufe, quote_prozent, provider, erstellt_von, "
            "created_at FROM audit_wasserstand WHERE project_name = ? "
            "ORDER BY id DESC LIMIT ?", (project_name, int(limit))).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def load_wasserstand(db_path: Path, report_id: int) -> dict[str, Any] | None:
    """Eine Wasserstandsmeldung samt gerechnetem Stand und KI-Text."""
    con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM audit_wasserstand WHERE id = ?",
                          (int(report_id),)).fetchone()
        if row is None:
            return None
        d = dict(row)
        for feld in ('status_json', 'ki_json'):
            try:
                d[feld[:-5]] = json.loads(d.pop(feld) or '{}')
            except (ValueError, TypeError):
                d[feld[:-5]] = {}
        return d
    finally:
        con.close()
