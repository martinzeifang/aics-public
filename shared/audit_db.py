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


# Wie viele der neuesten Modul-Einträge für die Projektsicht durchgesehen werden
# (#1851). Jenseits davon sagt die Antwort „nicht geprüft" statt stillschweigend
# „nichts gefunden" — ein Revisionspfad, der Einträge verschweigt, ist schlimmer
# als einer, der seine Grenze nennt.
_PROJEKT_FENSTER = 5000


def ereignisse_nach_detail(
    modul: str,
    schluessel: str,
    wert: str,
    *,
    limit: int = 200,
    offset: int = 0,
    fenster: int = _PROJEKT_FENSTER,
) -> dict[str, Any]:
    """Einträge eines Moduls, gefiltert auf **ein** Feld in ``details`` (#1870).

    Herausgezogen aus :func:`projekt_ereignisse`, weil nicht jedes Ereignis
    einem Projekt gehört: Ein Nachweis und ein Pentest-Bericht gelten der
    **Firma** (``module='firmen'``/``'pentest'``, ``details={firma, …}``).
    `shared/nachziehen` braucht beide Sichten, und zwei Fassungen derselben
    Abfrage wären zwei Gelegenheiten, die JSON-Behandlung unterschiedlich
    falsch zu machen.
    """
    return _ereignisse(modul, schluessel, wert, limit=limit, offset=offset,
                       fenster=fenster)


def projekt_ereignisse(
    modul: str,
    projekt: str,
    *,
    limit: int = 200,
    offset: int = 0,
    fenster: int = _PROJEKT_FENSTER,
) -> dict[str, Any]:
    """Die Einträge **eines Projekts** aus dem Revisionspfad (#1851).

    Der Projektname steht nicht in einer eigenen Spalte, sondern als
    ``details.projekt`` — dort legen ihn die Modul-Helfer
    (``_audit(action, projekt=…)``) seit jeher ab. Eine neue Spalte wäre die
    naheliegende Ergänzung und wäre falsch: Sie wäre für den gesamten Bestand
    leer, und die Ansicht zeigte für jedes gewachsene Projekt eine leere Liste,
    die aussieht wie „nichts passiert".

    **Gefiltert wird in Python, nicht in SQL.** ``details`` ist TEXT; ein
    ``details::jsonb ->> 'projekt'`` müsste jede Zeile casten, und eine einzige
    Zeile, die kein JSON ist (``record_audit_event`` nimmt auch eine
    Zeichenkette an), ließe die ganze Abfrage mit 22P02 scheitern — also genau
    dann, wenn der Revisionspfad gebraucht wird. Vorgefiltert wird über
    ``module`` (indiziert); der Rest ist ein exakter Vergleich auf dem
    geparsten Wert, der keinen Eintrag verschweigen kann, den er gesehen hat.

    Returns:
        ``{events, total, limit, offset, fenster, fenster_erschoepft}``.
        ``fenster_erschoepft`` sagt, dass ältere Einträge dieses Moduls
        **nicht** durchgesehen wurden — die Ansicht muss das zeigen.
    """
    return _ereignisse(modul, "projekt", projekt, limit=limit, offset=offset,
                       fenster=fenster)


def _ereignisse(
    modul: str,
    schluessel: str,
    wert: str,
    *,
    limit: int,
    offset: int,
    fenster: int,
) -> dict[str, Any]:
    modul = str(modul or "")
    schluessel = str(schluessel or "")
    wert = str(wert or "")
    limit = max(1, min(int(limit), 1000))
    offset = max(0, int(offset))
    fenster = max(1, min(int(fenster), 50000))
    leer: dict[str, Any] = {"events": [], "total": 0, "limit": limit,
                            "offset": offset, "fenster": fenster,
                            "fenster_erschoepft": False}
    if not modul or not schluessel or not wert:
        return leer

    try:
        conn = _sdb.connect(str(AUDIT_DB_PATH))
    except Exception:  # noqa: BLE001 — ohne Datenbank gibt es keine Spur zu zeigen
        return leer
    try:
        ensure_audit_db(conn)
        cur = conn.cursor()
        # fenster+1 Zeilen: die eine überzählige sagt, dass es älteren Bestand gibt.
        cur.execute(
            "SELECT id, ts, event_type, actor, action, module, outcome, details "
            "FROM audit_events WHERE module = ? ORDER BY id DESC LIMIT ?",
            (modul, fenster + 1),
        )
        rohzeilen = [dict(r) for r in cur.fetchall()]
    except Exception:  # noqa: BLE001
        return leer
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

    erschoepft = len(rohzeilen) > fenster
    treffer: list[dict[str, Any]] = []
    for zeile in rohzeilen[:fenster]:
        details = zeile.get("details")
        if isinstance(details, str) and details:
            try:
                details = json.loads(details)
            except Exception:  # noqa: BLE001 — keine JSON-Details, kein Projektbezug
                details = None
        if not isinstance(details, dict):
            continue
        if str(details.get(schluessel) or "") != wert:
            continue
        zeile["details"] = details
        treffer.append(zeile)

    return {
        "events": treffer[offset:offset + limit],
        "total": len(treffer),
        "limit": limit,
        "offset": offset,
        "fenster": fenster,
        "fenster_erschoepft": erschoepft,
    }


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
