"""Postgres-gestützte Audit-Trail-Persistenz mit Integritätskette (#1338).

Die sicherheitsrelevanten Audit-Events (``shared.audit.audit_event``) werden — zusätzlich
zum rotierenden Logfile (``logs/audit.log``) — in einer **append-only** Tabelle
``audit_events`` im Postgres-Schema ``audit`` persistiert. Jede Zeile trägt eine
**SHA-256-Integritätskette**: ``row_hash = sha256(prev_hash | ts | event_type | actor |
action | module | outcome | details)``. ``prev_hash`` ist der ``row_hash`` der unmittelbar
vorigen Zeile (Genesis = ``""``). Eine nachträglich gelöschte oder geänderte Zeile bricht
die Kette → ``verify_chain()`` findet die erste Bruchstelle.

Bewusste Abgrenzung: Das **HTTP-Request-Logging** (``log_http_request``, ein Event je
Request) bleibt dateibasiert. Es pro Request in eine kettenpflichtige Tabelle zu schreiben
würde alle Requests hinter einem Advisory-Lock serialisieren (Lock-Kontention wie bei der
DDL-Deadlock-Klasse #1355) und die Tabelle unkontrolliert aufblähen. Persistiert wird die
sicherheits­relevante Spur (Logins, Resets, Rechte-/Config-Änderungen, Löschungen, Exporte).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from shared import db as _sdb

# Logischer Pfad → Schema ``audit`` (konsistent mit ``server/api/admin.py`` AUDIT_DB und
# ``server/config/database.py``). Der Kompat-Layer leitet aus dem Dateinamen das Schema ab.
AUDIT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "db" / "audit.sqlite"

# Eigener Advisory-Lock-Key (≠ ``shared.db._DDL_LOCK_KEY``). Serialisiert AUSSCHLIESSLICH
# die Audit-Inserts untereinander, damit die Hash-Kette konsistent bleibt (prev_hash liest
# den row_hash der zuletzt eingefügten Zeile). Keine Wechselwirkung mit der DDL-Serialisierung.
_AUDIT_LOCK_KEY = 770155330111

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_events (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts          TEXT NOT NULL,
    event_type  TEXT NOT NULL DEFAULT 'audit',
    actor       TEXT,
    action      TEXT NOT NULL,
    module      TEXT NOT NULL,
    outcome     TEXT NOT NULL DEFAULT 'success',
    details     TEXT,
    prev_hash   TEXT NOT NULL,
    row_hash    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_events_ts ON audit_events(ts);
CREATE INDEX IF NOT EXISTS ix_audit_events_module ON audit_events(module);
"""

# Spalten der Kette in fester Reihenfolge — die Berechnung MUSS deterministisch sein.
_CHAIN_FIELDS = ("ts", "event_type", "actor", "action", "module", "outcome", "details")


def _row_hash(prev_hash: str, rec: dict[str, Any]) -> str:
    """SHA-256 über prev_hash + die kanonischen Feldwerte (None → leerer String)."""
    h = hashlib.sha256()
    h.update(prev_hash.encode("utf-8"))
    for f in _CHAIN_FIELDS:
        h.update(b"\x1f")  # Feldtrenner (Unit Separator), kollisionssicher
        h.update(str(rec.get(f) if rec.get(f) is not None else "").encode("utf-8"))
    return h.hexdigest()


def ensure_audit_db(conn: Any = None) -> None:
    """Tabelle ``audit_events`` (Schema ``audit``) anlegen. Idempotent, prozess-gecacht."""
    if conn is not None:
        conn.executescript(_SCHEMA_SQL)
        return
    with _sdb.connect(str(AUDIT_DB_PATH)) as c:
        c.executescript(_SCHEMA_SQL)


def record_audit_event(
    *,
    ts: str,
    action: str,
    module: str,
    outcome: str = "success",
    actor: str | None = None,
    details: Any = None,
    event_type: str = "audit",
) -> int | None:
    """Schreibt EIN Audit-Event append-only mit Hash-Kette nach Postgres.

    Liefert die vergebene ``id`` oder ``None`` bei Fehler. Best-effort: wirft nicht — der
    aufrufende ``audit_event`` darf durch einen DB-Ausfall niemals die fachliche Aktion
    abbrechen (das Logfile bleibt die zweite, unabhängige Spur).
    """
    details_json = (
        details if isinstance(details, str)
        else json.dumps(details, ensure_ascii=False, sort_keys=True) if details is not None
        else None
    )
    rec = {
        "ts": ts,
        "event_type": event_type,
        "actor": actor,
        "action": action,
        "module": module,
        "outcome": outcome,
        "details": details_json,
    }
    try:
        conn = _sdb.connect(str(AUDIT_DB_PATH))
    except Exception:
        return None
    try:
        ensure_audit_db(conn)
        cur = conn.cursor()
        # Advisory-Lock + prev-Hash-Read + Insert in EINER Transaktion → die Kette kann
        # auch bei parallelen Workern nicht zerreißen oder eine Lücke bekommen.
        cur.execute("SELECT pg_advisory_xact_lock(?)", (_AUDIT_LOCK_KEY,))
        cur.execute("SELECT row_hash FROM audit_events ORDER BY id DESC LIMIT 1")
        last = cur.fetchone()
        prev_hash = last[0] if last else ""
        rh = _row_hash(prev_hash, rec)
        cur.execute(
            "INSERT INTO audit_events "
            "(ts, event_type, actor, action, module, outcome, details, prev_hash, row_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rec["ts"], rec["event_type"], rec["actor"], rec["action"], rec["module"],
             rec["outcome"], rec["details"], prev_hash, rh),
        )
        new_id = cur.lastrowid
        conn.commit()
        return new_id
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def verify_chain() -> dict[str, Any]:
    """Prüft die Integritätskette über ALLE Zeilen (id-Reihenfolge).

    Returns ``{ok, count, broken_at}`` — ``broken_at`` ist die ``id`` der ersten Zeile,
    deren ``prev_hash``/``row_hash`` nicht zur neu berechneten Kette passt (sonst ``None``).
    """
    with _sdb.connect(str(AUDIT_DB_PATH)) as conn:
        ensure_audit_db(conn)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, ts, event_type, actor, action, module, outcome, details, "
            "prev_hash, row_hash FROM audit_events ORDER BY id ASC"
        )
        rows = cur.fetchall()

    prev_hash = ""
    count = 0
    for r in rows:
        count += 1
        rec = {f: r[f] for f in _CHAIN_FIELDS}
        expected = _row_hash(prev_hash, rec)
        if r["prev_hash"] != prev_hash or r["row_hash"] != expected:
            return {"ok": False, "count": count, "broken_at": r["id"]}
        prev_hash = r["row_hash"]
    return {"ok": True, "count": count, "broken_at": None}
