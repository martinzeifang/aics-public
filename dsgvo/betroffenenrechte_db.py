"""DS8 (#1108) — Betroffenenrechte-Register (Art. 15-22 DSGVO).

Selbst-enthaltene neue Area: eigene Tabelle ``dsgvo_betroffenenrechte`` in der
geteilten ``data/db/dsgvo.sqlite`` — die zentrale ``dsgvo/db.py``-SCHEMA wird
NICHT angefasst. ``ensure_table()`` ist idempotent und wird zu Beginn jeder
Lese-/Schreiboperation aufgerufen (Muster wie ``shared/templates/db.py``).

Frist-Logik (Art. 12 Abs. 3 DSGVO): Antwort innerhalb eines Monats nach Eingang;
optional um zwei weitere Monate verlängerbar.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Geteilte DSGVO-DB; Verbindung wird über die zentrale dsgvo-Connection bezogen
# (con.row_factory = Row ist dort bereits gesetzt).
from dsgvo.db import _connect

DB_PATH = Path('data/db/dsgvo.sqlite')

# Erlaubte Antrags-Typen (Art. 15-22 DSGVO).
TYPEN = (
    'auskunft15',
    'berichtigung16',
    'loeschung17',
    'einschraenkung18',
    'portabilitaet20',
    'widerspruch21',
    'profiling22',
)

# Status-Workflow.
STATUS = (
    'eingegangen',
    'in_bearbeitung',
    'wartet_identitaet',
    'abgeschlossen',
    'abgelehnt',
)

# #1218 (Art. 19): Antragstypen, bei denen vor Abschluss die Empfänger-
# Benachrichtigung nachgewiesen sein muss (Berichtigung/Löschung/Einschränkung).
ART19_TYPEN = ('berichtigung16', 'loeschung17', 'einschraenkung18')

# #1218: Status der Empfänger-Benachrichtigung (Art. 19).
EMPFAENGER_STATUS = (
    'offen',        # noch nicht bearbeitet
    'benachrichtigt',  # alle Empfänger informiert (mit Datum)
    'entfaellt',    # keine Empfänger / keine Offenlegung erfolgt
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_betroffenenrechte (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_name       TEXT NOT NULL,
    antrag_id          TEXT NOT NULL DEFAULT '',
    typ                TEXT NOT NULL,
    eingang_datum      TEXT NOT NULL,
    frist_datum        TEXT NOT NULL DEFAULT '',
    verlaengert        INTEGER NOT NULL DEFAULT 0,
    identitaet_geprueft INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'eingegangen',
    bearbeiter         TEXT NOT NULL DEFAULT '',
    ergebnis           TEXT NOT NULL DEFAULT '',
    notizen            TEXT NOT NULL DEFAULT '',
    -- #1218 (Art. 19): Mitteilung an Empfänger bei Berichtigung/Löschung/Einschränkung
    empfaenger_status  TEXT NOT NULL DEFAULT 'offen',
    empfaenger_liste   TEXT NOT NULL DEFAULT '',
    empfaenger_datum   TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_br_projekt
    ON dsgvo_betroffenenrechte(projekt_name);
CREATE INDEX IF NOT EXISTS idx_dsgvo_br_status
    ON dsgvo_betroffenenrechte(projekt_name, status);
"""


# #1218: Spalten, die ggf. per ALTER nachgezogen werden (Bestands-DBs).
_MIGRATE_COLUMNS = {
    'empfaenger_status': "TEXT NOT NULL DEFAULT 'offen'",
    'empfaenger_liste': "TEXT NOT NULL DEFAULT ''",
    'empfaenger_datum': "TEXT NOT NULL DEFAULT ''",
}


def ensure_table(db_path: Path = DB_PATH) -> None:
    """Legt Tabelle + Indizes an (idempotent) und zieht neue Spalten nach."""
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        # #1218: Bestands-DBs ohne Art.-19-Spalten migrieren.
        existing = {r[1] for r in con.execute(
            "PRAGMA table_info(dsgvo_betroffenenrechte)").fetchall()}
        for col, ddl in _MIGRATE_COLUMNS.items():
            if col not in existing:
                con.execute(f"ALTER TABLE dsgvo_betroffenenrechte ADD COLUMN {col} {ddl}")
        con.commit()
    finally:
        con.close()


# ============================================================
# Frist-Berechnung
# ============================================================

def _add_months(d: date, months: int) -> date:
    """Addiert ganze Monate auf ein Datum (Monatsende-sicher)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    # Tag clampen (z. B. 31. Jan + 1 Monat → 28./29. Feb).
    last_day_by_month = [31, 29 if _is_leap(year) else 28, 31, 30, 31, 30,
                         31, 31, 30, 31, 30, 31]
    day = min(d.day, last_day_by_month[month - 1])
    return date(year, month, day)


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def compute_frist(eingang_datum: str, verlaengert: bool | int) -> str:
    """Frist = Eingang + 1 Monat (+ 2 Monate bei Verlängerung).

    Liefert ISO-Datum (YYYY-MM-DD) oder '' bei ungültigem Eingang.
    """
    d = _parse_date(eingang_datum)
    if d is None:
        return ''
    months = 1 + (2 if int(bool(verlaengert)) else 0)
    return _add_months(d, months).isoformat()


def _is_overdue(frist_datum: str, status: str) -> bool:
    """Überfällig, wenn Frist in der Vergangenheit liegt und nicht erledigt."""
    if status in ('abgeschlossen', 'abgelehnt'):
        return False
    f = _parse_date(frist_datum)
    if f is None:
        return False
    return f < date.today()


def _days_left(frist_datum: str) -> int | None:
    f = _parse_date(frist_datum)
    if f is None:
        return None
    return (f - date.today()).days


# ============================================================
# Serialisierung
# ============================================================

def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    d['verlaengert'] = int(d.get('verlaengert') or 0)
    d['identitaet_geprueft'] = int(d.get('identitaet_geprueft') or 0)
    d['overdue'] = _is_overdue(d.get('frist_datum', ''), d.get('status', ''))
    d['days_left'] = _days_left(d.get('frist_datum', ''))
    return d


# ============================================================
# CRUD
# ============================================================

def list_antraege(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM dsgvo_betroffenenrechte WHERE projekt_name = ? "
            "ORDER BY frist_datum ASC, id DESC",
            (projekt_name,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        con.close()


def get_antrag(db_path: Path, antrag_pk: int,
               projekt_name: str | None = None) -> dict[str, Any] | None:
    # #1173 IDOR: optional auf projekt_name einschränken (Mandanten-Scoping).
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if projekt_name is not None:
            r = con.execute(
                "SELECT * FROM dsgvo_betroffenenrechte WHERE id = ? AND projekt_name = ?",
                (antrag_pk, projekt_name),
            ).fetchone()
        else:
            r = con.execute(
                "SELECT * FROM dsgvo_betroffenenrechte WHERE id = ?",
                (antrag_pk,),
            ).fetchone()
        return _row_to_dict(r) if r is not None else None
    finally:
        con.close()


def _check_art19_gate(typ: str, status: str, empfaenger_status: str) -> None:
    """#1218 (Art. 19): Vor Abschluss eines Berichtigungs-/Löschungs-/
    Einschränkungsantrags muss die Empfänger-Benachrichtigung nachgewiesen sein
    (benachrichtigt mit Datum) oder ausdrücklich als 'entfällt' markiert werden."""
    if status == 'abgeschlossen' and typ in ART19_TYPEN \
            and (empfaenger_status or 'offen') == 'offen':
        raise ValueError(
            'Art. 19: Vor Abschluss muss die Empfänger-Benachrichtigung '
            'dokumentiert werden (benachrichtigt mit Datum) oder als '
            '„entfällt" (keine Empfänger) markiert sein.')


def create_antrag(db_path: Path, projekt_name: str, *, typ: str,
                  eingang_datum: str, antrag_id: str = '',
                  verlaengert: bool | int = 0,
                  identitaet_geprueft: bool | int = 0,
                  status: str = 'eingegangen', bearbeiter: str = '',
                  ergebnis: str = '', notizen: str = '',
                  empfaenger_status: str = 'offen',
                  empfaenger_liste: str = '',
                  empfaenger_datum: str = '') -> dict[str, Any]:
    ensure_table(db_path)
    if typ not in TYPEN:
        raise ValueError(f'Ungültiger Typ: {typ}')
    if empfaenger_status and empfaenger_status not in EMPFAENGER_STATUS:
        raise ValueError(f'Ungültiger Empfänger-Status: {empfaenger_status}')
    _check_art19_gate(typ, status, empfaenger_status)
    frist = compute_frist(eingang_datum, verlaengert)
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "INSERT INTO dsgvo_betroffenenrechte "
            "(projekt_name, antrag_id, typ, eingang_datum, frist_datum, "
            " verlaengert, identitaet_geprueft, status, bearbeiter, ergebnis, notizen, "
            " empfaenger_status, empfaenger_liste, empfaenger_datum) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (projekt_name, antrag_id, typ, eingang_datum, frist,
             int(bool(verlaengert)), int(bool(identitaet_geprueft)),
             status, bearbeiter, ergebnis, notizen,
             (empfaenger_status or 'offen'), empfaenger_liste, empfaenger_datum),
        )
        con.commit()
        new_id = cur.lastrowid
        r = con.execute(
            "SELECT * FROM dsgvo_betroffenenrechte WHERE id = ?", (new_id,),
        ).fetchone()
        return _row_to_dict(r)
    finally:
        con.close()


def update_antrag(db_path: Path, antrag_pk: int,
                  projekt_name: str | None = None,
                  **fields: Any) -> dict[str, Any] | None:
    ensure_table(db_path)
    # #1173 IDOR: existierenden Datensatz auf projekt_name prüfen.
    existing = get_antrag(db_path, antrag_pk, projekt_name)
    if existing is None:
        return None

    allowed = {
        'antrag_id', 'typ', 'eingang_datum', 'verlaengert',
        'identitaet_geprueft', 'status', 'bearbeiter', 'ergebnis', 'notizen',
        'empfaenger_status', 'empfaenger_liste', 'empfaenger_datum',
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}

    if 'typ' in updates and updates['typ'] not in TYPEN:
        raise ValueError(f"Ungültiger Typ: {updates['typ']}")
    if 'empfaenger_status' in updates and updates['empfaenger_status'] not in EMPFAENGER_STATUS:
        raise ValueError(f"Ungültiger Empfänger-Status: {updates['empfaenger_status']}")

    # #1218 (Art. 19): Gate gegen die effektiven Werte (Update überlagert Bestand).
    eff_typ = updates.get('typ', existing['typ'])
    eff_status = updates.get('status', existing['status'])
    eff_empf = updates.get('empfaenger_status', existing.get('empfaenger_status', 'offen'))
    _check_art19_gate(eff_typ, eff_status, eff_empf)

    # Frist neu berechnen, wenn Eingang oder Verlängerung sich ändert.
    eingang = updates.get('eingang_datum', existing['eingang_datum'])
    verlaengert = updates.get('verlaengert', existing['verlaengert'])
    if 'eingang_datum' in updates or 'verlaengert' in updates:
        updates['frist_datum'] = compute_frist(eingang, verlaengert)

    if 'verlaengert' in updates:
        updates['verlaengert'] = int(bool(updates['verlaengert']))
    if 'identitaet_geprueft' in updates:
        updates['identitaet_geprueft'] = int(bool(updates['identitaet_geprueft']))

    if not updates:
        return existing

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    params = list(updates.values()) + [antrag_pk]
    con = _connect(Path(db_path))
    try:
        con.execute(
            f"UPDATE dsgvo_betroffenenrechte SET {set_clause}, "
            f"updated_at = datetime('now') WHERE id = ?",
            params,
        )
        con.commit()
    finally:
        con.close()
    return get_antrag(db_path, antrag_pk, projekt_name)


def delete_antrag(db_path: Path, antrag_pk: int,
                  projekt_name: str | None = None) -> bool:
    # #1173 IDOR: optional auf projekt_name einschränken.
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if projekt_name is not None:
            cur = con.execute(
                "DELETE FROM dsgvo_betroffenenrechte WHERE id = ? AND projekt_name = ?",
                (antrag_pk, projekt_name),
            )
        else:
            cur = con.execute(
                "DELETE FROM dsgvo_betroffenenrechte WHERE id = ?", (antrag_pk,),
            )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()
