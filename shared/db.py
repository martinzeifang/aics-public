"""Zentraler PostgreSQL-Kompatibilitäts-Layer (#1330).

Ersetzt die per-Modul ``sqlite3``-Verbindungen durch **psycopg3** gegen **eine**
PostgreSQL-Datenbank mit **einem Schema je Modul** (Namespacing). Ziel: die bestehenden
Modul-``db.py`` mit minimaler Änderung portieren — die Funktions-Signaturen
``_connect(db_path)`` / ``ensure_db(db_path)`` bleiben, ``db_path`` wird zum **logischen
Schema-Selektor** (Stem des Pfades, z. B. ``data/db/soc.sqlite`` → Schema ``soc``).

Kernbausteine:
- ``translate_sql`` — quote-aware Übersetzung ``?`` → ``%s`` und Verdopplung literaler
  ``%`` → ``%%`` (psycopg-Anforderung). **Reines Python, ohne psycopg testbar.**
- ``schema_for`` — Schema-Name aus dem db_path-Stem.
- ``connect`` — liefert eine ``ConnWrapper`` (sqlite3-ähnliche API) aus dem Pool, mit
  gesetztem ``search_path`` auf das Modul-Schema.

psycopg wird **lazy** importiert, damit Translator-/Schema-Unittests ohne installiertes
psycopg laufen.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Reine Python-Helfer (ohne psycopg) ──────────────────────────────────────


def translate_sql(sql: str) -> str:
    """SQLite-Platzhalter/Prozent in psycopg-Syntax übersetzen.

    Regeln (single-pass, quote-aware):
    - jedes literale ``%`` → ``%%`` (psycopg interpretiert ``%`` als Format-Marker,
      sobald Parameter übergeben werden — auch innerhalb von String-Literalen).
    - ``?`` → ``%s``, **nur außerhalb** einfacher String-Literale (``'...'``).
    - ``''`` innerhalb eines String-Literals ist ein escaptes Anführungszeichen.
    """
    out: list[str] = []
    in_s = False  # innerhalb '...'-Literal
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "%":
            out.append("%%")
            i += 1
            continue
        if c == "'":
            out.append(c)
            if in_s:
                if i + 1 < n and sql[i + 1] == "'":  # escaptes ''
                    out.append("'")
                    i += 2
                    continue
                in_s = False
            else:
                in_s = True
            i += 1
            continue
        if c == "?" and not in_s:
            out.append("%s")
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


_SCHEMA_RE = re.compile(r"[^a-z0-9_]")


def schema_for(db_path: Any) -> str:
    """Schema-Name aus einem db_path ableiten (Stem, sanitisiert).

    ``data/db/soc.sqlite`` → ``soc`` · ``ai_act.sqlite`` → ``ai_act`` ·
    ``data/db/pytest_x.sqlite`` → ``pytest_x``. Erlaubt auch direkte Schema-Strings.
    """
    s = Path(str(db_path)).name
    if s.endswith(".sqlite"):
        s = s[: -len(".sqlite")]
    s = s.lower().strip()
    s = _SCHEMA_RE.sub("_", s)
    if not s:
        s = "public"
    if s[0].isdigit():
        s = "s_" + s
    return s[:63]


def database_url() -> str:
    """Postgres-DSN aus der Umgebung (oder lokaler Default)."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "aics")
    pw = os.environ.get("DB_PASSWORD", "aics")
    name = os.environ.get("DB_NAME", "aics")
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}"


# ── psycopg3-gestützter Verbindungs-Layer (lazy import) ─────────────────────

_pool = None
_pool_lock = threading.Lock()
_ensured_schemas: set[str] = set()
_ensured_lock = threading.Lock()
_bootstrap_done = False
# Prozess-Cache bereits ausgeführter Schema-Skripte (Schema, hash(sql)) → executescript
# läuft je Worker nur einmal statt bei jedem Request.
_ensured_scripts: set[tuple[str, int]] = set()
# #1396: Prozess-Cache idempotenter Einzel-DDL (Schema, hash(sql)) — ALTER/CREATE/DROP
# mit IF [NOT] EXISTS; nach erstem Erfolg übersprungen (ensure_db-Migrationen).
_ensured_ddl: set[tuple[str, int]] = set()
# Globaler Advisory-Lock-Key: serialisiert ALLE Schema-DDL (CREATE/ALTER/DROP) prozess-
# und workerübergreifend. Unter SQLite war ensure_db dank Single-Writer unkritisch; unter
# Postgres deadlocken konkurrierende DDL-Läufe mehrerer gunicorn-Worker (#1355).
_DDL_LOCK_KEY = 770155330099
# #1704: Der Advisory-Lock gilt bis zum Ende der TRANSAKTION. Wird eine Verbindung
# mitten im DDL weggeworfen, ohne dass commit/rollback/close läuft (abgebrochene
# Fixture, Exception ohne finally), bleibt ihre Transaktion offen — und JEDER weitere
# DDL-Versuch im selben Prozess wartet *unbegrenzt*. Im CI sah das aus wie ein
# stummer Abbruch: ``pg_advisory_xact_lock`` blockiert unterhalb von Python im
# Socket-Wait, also greift auch ``pytest-timeout --timeout-method=thread`` nicht.
# Deshalb wird der Lock nur mit Deadline genommen (0 = altes, unbegrenztes Warten).
_DDL_LOCK_TIMEOUT_S = float(os.environ.get("AICS_DDL_LOCK_TIMEOUT", "60"))


class DDLLockTimeout(RuntimeError):
    """Der globale DDL-Advisory-Lock war nicht innerhalb der Deadline zu bekommen."""


def _acquire_ddl_lock(cur) -> None:
    """Globalen DDL-Lock nehmen — mit Deadline statt unbegrenztem Warten (#1704).

    ``cur`` ist ein roher psycopg-Cursor. Der Lock wird weiter **blockierend** genommen
    (``pg_advisory_xact_lock``) — damit bleibt die faire FIFO-Reihenfolge des
    Postgres-Lockmanagers erhalten, anders als beim Pollen mit
    ``pg_try_advisory_xact_lock``, wo ein Worker unter Dauerlast aushungern kann.
    Begrenzt wird über ``lock_timeout``, das auch für Advisory-Locks gilt (Abbruch mit
    SQLSTATE 55P03). Daraus wird :class:`DDLLockTimeout` — ein sichtbarer Fehler statt
    eines hängenden Workers.

    ``lock_timeout`` wird per ``set_config(..., true)`` **transaktionslokal** gesetzt
    und nach dem Erwerb wieder auf 0 gestellt, damit die Begrenzung nur das Warten auf
    den Advisory-Lock betrifft und nicht das nachfolgende DDL selbst.

    Achtung: Nach 55P03 ist die Transaktion abgebrochen (wie bei jedem gescheiterten
    Statement unter Postgres) — der Aufrufer muss zurückrollen. ``ConnWrapper.close``
    tut das.
    """
    if _DDL_LOCK_TIMEOUT_S <= 0:  # Not-Ausstieg: altes, unbegrenztes Warten
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_DDL_LOCK_KEY,))
        return
    ms = max(1, int(_DDL_LOCK_TIMEOUT_S * 1000))
    # set_config statt "SET LOCAL": parametrisierbar (kein SQL-Zusammenbau).
    cur.execute("SELECT set_config('lock_timeout', %s, true)", (f"{ms}ms",))
    try:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_DDL_LOCK_KEY,))
    except Exception as exc:
        if getattr(exc, "sqlstate", None) != "55P03":  # LockNotAvailable
            raise
        raise DDLLockTimeout(
            f"DDL-Lock nach {_DDL_LOCK_TIMEOUT_S:g}s nicht erhalten. Vermutlich hält "
            "eine andere Verbindung eine offene Transaktion mit DDL — siehe pg_locks / "
            "pg_stat_activity (state='idle in transaction'). "
            "AICS_DDL_LOCK_TIMEOUT=0 stellt das alte, unbegrenzte Warten her."
        ) from exc
    cur.execute("SELECT set_config('lock_timeout', '0', true)")

# Test-Isolation-Beschleunigung (#1340): Statt VOR JEDEM Test ALLE Modul-Tabellen zu
# truncaten (TRUNCATE aller Schemata ≈ 5 s/Test → Suite praktisch nicht lauffähig),
# merken wir uns die tatsächlich berührten Schemata und leeren nur DIESE. Tracking ist
# standardmäßig AUS (kein Lock-/CPU-Overhead in Produktion) und wird vom Test-Harness
# via ``enable_schema_tracking()`` bzw. ``AICS_TRACK_SCHEMAS=1`` aktiviert.
_track_schemas = os.environ.get("AICS_TRACK_SCHEMAS") == "1"
_touched_schemas: set[str] = set()
_touched_lock = threading.Lock()


def enable_schema_tracking() -> None:
    """Aktiviert das Berührte-Schemata-Tracking (nur Tests; siehe drop_test_schemas)."""
    global _track_schemas
    _track_schemas = True

# Postgres-Pendant zu SQLites datetime('now'): liefert UTC-Text im EXAKTEN SQLite-Format
# 'YYYY-MM-DD HH:MM:SS'. So bleiben Timestamp-Spalten TEXT und der bestehende Python-Code
# (String-Slicing/strptime auf Timestamps) funktioniert unverändert.
_AICS_NOW_DDL = (
    "CREATE OR REPLACE FUNCTION public.aics_now() RETURNS text LANGUAGE sql STABLE AS "
    "$$ SELECT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') $$"
)


def _make_row_factory():
    """Row-Factory: dict-artig (``r['col']``) UND index-artig (``r[0]``), wie sqlite3.Row."""

    def row_factory(cursor):
        cols = [d.name for d in cursor.description] if cursor.description else []

        def make(values):
            return DBRow(cols, values)

        return make

    return row_factory


class DBRow(dict):
    """dict-Subklasse mit zusätzlicher Positions-Indizierung (``r[0]``)."""

    __slots__ = ("_vals",)

    def __init__(self, cols, values):
        super().__init__(zip(cols, values))
        self._vals = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return super().__getitem__(key)


def get_pool():
    """Globaler psycopg3-Connection-Pool (lazy, Singleton)."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                from psycopg_pool import ConnectionPool

                _pool = ConnectionPool(
                    conninfo=database_url(),
                    # #1701: Pool muss ≥ gunicorn-Threads/Worker sein (Default 24),
                    # sonst warten Threads auf freie Verbindungen → wirkt wie
                    # "Backend weg". max_size ist der Deckel je Worker-Prozess
                    # (Prozesse × max_size < Postgres max_connections einplanen).
                    min_size=int(os.environ.get("DB_POOL_MIN", "2")),
                    max_size=int(os.environ.get("DB_POOL_MAX", "28")),
                    kwargs={"autocommit": False},
                    open=True,
                )
    return _pool


def _ensure_bootstrap(conn) -> None:
    """Globale Helfer (public.aics_now()) einmalig anlegen."""
    global _bootstrap_done
    if _bootstrap_done:
        return
    with _ensured_lock:
        if _bootstrap_done:
            return
        with conn.cursor() as cur:
            cur.execute(_AICS_NOW_DDL)
        conn.commit()
        _bootstrap_done = True


def _ensure_schema(conn, schema: str) -> None:
    _ensure_bootstrap(conn)
    if schema in _ensured_schemas:
        return
    with _ensured_lock:
        if schema in _ensured_schemas:
            return
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        conn.commit()
        _ensured_schemas.add(schema)


class CurWrapper:
    """sqlite3-ähnlicher Cursor über einem psycopg3-Cursor."""

    def __init__(self, cur, schema: str = ""):
        self._cur = cur
        self._schema = schema
        self.lastrowid = None

    def execute(self, sql: str, params: Any = None):
        q = translate_sql(sql)
        p = tuple(params) if params is not None else None
        self.lastrowid = None
        # DDL (CREATE/ALTER/DROP/COMMENT) global serialisieren → verhindert Deadlocks
        # konkurrierender ensure_db-Läufe unter mehreren Workern (Postgres-Migration).
        _w = q.lstrip().split(None, 1)
        if _w and _w[0].upper() in ("CREATE", "ALTER", "DROP", "COMMENT"):
            # #1396: Idempotente DDL (IF [NOT] EXISTS, parameterlos) je Prozess+Schema
            # nur EINMAL ausführen. ensure_db ruft pro Request/Test ~30 ALTER … IF NOT
            # EXISTS auf; jedes nahm den Advisory-Lock + Roundtrip (~1,6 s/Test). Nach
            # dem ersten Erfolg ist die Wiederholung ein No-op → überspringen.
            _qu = q.upper()
            if p is None and ("IF NOT EXISTS" in _qu or "IF EXISTS" in _qu):
                _key = (self._schema, hash(q))
                with _ensured_lock:
                    _cached = _key in _ensured_ddl
                if _cached:
                    return self
                _acquire_ddl_lock(self._cur)
                self._cur.execute(q, p)
                with _ensured_lock:
                    _ensured_ddl.add(_key)
                return self
            _acquire_ddl_lock(self._cur)
        # lastrowid-Kompat (modulweit, ohne Einzeledits): bei INSERT ohne RETURNING
        # automatisch "RETURNING id" versuchen; Tabellen ohne id-Spalte → sauberer
        # Fallback per SAVEPOINT (kein vergifteter Transaktionszustand).
        is_insert = q.lstrip()[:6].upper() == "INSERT" and "RETURNING" not in q.upper()
        if is_insert:
            self._cur.execute("SAVEPOINT _aics_li")
            try:
                self._cur.execute(q + " RETURNING id", p)
                row = self._cur.fetchone()
                self.lastrowid = row[0] if row else None
                self._cur.execute("RELEASE SAVEPOINT _aics_li")
                return self
            except Exception as exc:  # i. d. R. UndefinedColumn (42703): keine id-Spalte
                code = getattr(exc, "sqlstate", None)
                self._cur.execute("ROLLBACK TO SAVEPOINT _aics_li")
                if code not in (None, "42703"):
                    raise
                self._cur.execute(q, p)
                return self
        self._cur.execute(q, p)
        # Falls explizites RETURNING vorhanden: Skalar als lastrowid merken
        try:
            if self._cur.description and re.search(r"\bRETURNING\b", q, re.I) \
                    and len(self._cur.description) == 1 and self._cur.rowcount == 1:
                row = self._cur.fetchone()
                self.lastrowid = row[0] if row else None
        except Exception:
            self.lastrowid = None
        return self

    def executemany(self, sql: str, seq):
        self._cur.executemany(translate_sql(sql), [tuple(p) for p in seq])
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def __iter__(self):
        return iter(self._cur)

    def close(self):
        self._cur.close()


class ConnWrapper:
    """sqlite3.Connection-ähnliche Fassade über einer gepoolten psycopg3-Verbindung."""

    def __init__(self, conn, pool, schema: str):
        self._conn = conn
        self._pool = pool
        self._schema = schema
        self._closed = False

    def execute(self, sql: str, params: Any = None) -> CurWrapper:
        cur = CurWrapper(self._conn.cursor(row_factory=_make_row_factory()), self._schema)
        return cur.execute(sql, params)

    def executemany(self, sql: str, seq) -> CurWrapper:
        cur = self.cursor()
        cur.executemany(sql, seq)
        return cur

    def executescript(self, sql: str) -> None:
        # Prozess-Cache: je Worker nur einmal ausführen (statt bei jedem ensure_db-Call).
        key = (self._schema, hash(sql))
        with _ensured_lock:
            if key in _ensured_scripts:
                return
        # Advisory-Lock serialisiert das DDL prozessübergreifend (Deadlock-Schutz unter
        # Nebenläufigkeit). Mehrere Statements ohne Parameter: psycopg3 in einem execute.
        with self._conn.cursor() as cur:
            _acquire_ddl_lock(cur)
            cur.execute(translate_sql(sql))
        self._conn.commit()
        with _ensured_lock:
            _ensured_scripts.add(key)

    def cursor(self) -> CurWrapper:
        return CurWrapper(self._conn.cursor(row_factory=_make_row_factory()), self._schema)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def try_execute(self, sql: str, params: Any = None) -> bool:
        """PG-sicheres **optionales** Statement via Savepoint.

        In PostgreSQL bricht ein fehlgeschlagenes Statement die ganze Transaktion
        ab — ein ``try/except: pass`` um ein optionales Statement (z. B. DELETE aus
        einer evtl. nicht existierenden Tabelle) macht die Transaktion unbenutzbar
        (InFailedSqlTransaction bei Folge-Statements). Dieser Helfer kapselt das
        Statement in einem SAVEPOINT und rollt bei Fehler NUR bis dahin zurück, sodass
        die Transaktion weiter nutzbar bleibt. Returns True=ausgeführt, False=übersprungen.
        """
        sp = "aics_opt_sp"
        try:
            with self._conn.cursor() as c:
                c.execute(f"SAVEPOINT {sp}")
        except Exception:
            # Kein offener Transaktionsblock → ohne Savepoint versuchen.
            try:
                self.execute(sql, params)
                return True
            except Exception:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                return False
        try:
            self.execute(sql, params)
            with self._conn.cursor() as c:
                c.execute(f"RELEASE SAVEPOINT {sp}")
            return True
        except Exception:
            try:
                with self._conn.cursor() as c:
                    c.execute(f"ROLLBACK TO SAVEPOINT {sp}")
            except Exception:
                pass
            return False

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._conn.rollback()
        except Exception:
            pass
        self._pool.putconn(self._conn)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


def connect(db_path: Any, **_kw: Any) -> ConnWrapper:
    """Liefert eine ConnWrapper für das aus ``db_path`` abgeleitete Modul-Schema."""
    schema = schema_for(db_path)
    if _track_schemas:  # nur in Tests aktiv (#1340)
        with _touched_lock:
            _touched_schemas.add(schema)
    pool = get_pool()
    conn = pool.getconn()
    # #1530: Eine aus dem Pool geholte Verbindung kann noch eine ABGEBROCHENE
    # Transaktion tragen (z. B. ein Endpoint, der nach einem SQL-Fehler 400/404
    # liefert, ohne zu rollbacken). Der erste Befehl unten liefe dann in
    # InFailedSqlTransaction und die Kaskade zöge sich durch alle Folgezugriffe
    # (besonders sichtbar in Tests mit kleinem Pool). Residualen Zustand hart
    # zurücksetzen — auf einer sauberen/idle Verbindung ist das ein No-op.
    try:
        conn.rollback()
    except Exception:
        pass
    try:
        _ensure_schema(conn, schema)
        with conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{schema}", public')
        conn.commit()
    except Exception:
        pool.putconn(conn)
        raise
    return ConnWrapper(conn, pool, schema)


# ── Test-/Betriebs-Helfer ───────────────────────────────────────────────────

def reset_pool() -> None:
    """Pool schließen + Schema-Cache leeren (z. B. nach DATABASE_URL-Wechsel in Tests)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.close()
            except Exception:
                pass
            _pool = None
    with _ensured_lock:
        global _bootstrap_done
        _ensured_schemas.clear()
        _ensured_scripts.clear()
        _ensured_ddl.clear()
        _bootstrap_done = False


# Schemata, die zwischen Tests NICHT gedroppt werden (App-/System-State).
_KEEP_SCHEMAS = {"public", "information_schema", "pg_catalog", "pg_toast",
                 "scheduler", "users", "audit"}


def _truncate_nonempty(cur, pairs) -> int:
    """#1396: TRUNCATE nur der **nicht-leeren** Tabellen aus ``pairs`` [(schema, table)].

    TRUNCATE von Dutzenden Tabellen (RESTART IDENTITY CASCADE) kostet ~750 ms (ACCESS
    EXCLUSIVE-Lock + Datei-Truncate je Tabelle), auch wenn fast alle leer sind. Ein
    test berührt aber meist nur 1–5 Tabellen. Ein billiger ``SELECT 1 … LIMIT 1`` je
    Tabelle filtert die leeren heraus → nur die wenigen nicht-leeren werden geleert.
    """
    nonempty = []
    for s, t in pairs:
        cur.execute(f'SELECT 1 FROM "{s}"."{t}" LIMIT 1')
        if cur.fetchone() is not None:
            nonempty.append((s, t))
    if nonempty:
        ident = ", ".join(f'"{s}"."{t}"' for s, t in nonempty)
        cur.execute(f"TRUNCATE TABLE {ident} RESTART IDENTITY CASCADE")
    return len(nonempty)


def drop_test_schemas(keep: set[str] | None = None, *,
                      alle_schemata: bool = False) -> None:
    """Per-Test-Isolation (#1341): Daten aller Modul-/Test-Tabellen leeren.

    **TRUNCATE statt DROP** — die Tabellen bleiben bestehen (App-/API-Endpunkte setzen
    sie als vorhanden voraus), nur die Daten werden geleert und IDENTITY-Sequenzen
    zurückgesetzt. Behält users/audit/scheduler/public + System-Schemata unangetastet.

    Args:
        alle_schemata: Tracking übergehen und **alle** Nicht-System-Schemata leeren.
            Nötig beim Sessionstart (#1706): Das Tracking kennt nur die Schemata, die
            *dieser Prozess* berührt hat — zu Beginn ist die Liste leer, also überlebt
            der Datenbestand eines vorherigen Laufs. Gegen eine dauerhafte Testdatenbank
            schlugen Tests dadurch je nach Vorgeschichte fehl (``assert 3 == 1``).
    """
    keep_all = (keep or set()) | _KEEP_SCHEMAS
    # #1340: Bei aktivem Tracking nur die vom letzten Test berührten Schemata leeren
    # (massiv schneller). Sonst (Fallback) alle Nicht-System-Schemata.
    if _track_schemas and not alle_schemata:
        with _touched_lock:
            only = {s for s in _touched_schemas if s not in keep_all}
            _touched_schemas.clear()
        if not only:
            return  # nichts berührt → nichts zu tun
    else:
        only = None
    pool = get_pool()
    conn = pool.getconn()
    try:
        try:
            conn.rollback()  # evtl. angefasste Verbindung sauber machen
        except Exception:
            pass
        with conn.cursor() as cur:
            # Harte Zeit-/Lock-Grenzen: die Bereinigung darf NIE hängen. Nicht-destruktiv
            # (kein Verbindungs-Kill) → keine InFailedSqlTransaction-Kaskaden.
            # #1706: Beim Sessionstart (alle_schemata) grosszuegiger — dort laeuft es
            # EINMAL und darf etwas kosten. Per-Test bleibt es knapp, damit die
            # Bereinigung nie zum Hänger wird.
            if alle_schemata:
                cur.execute("SET lock_timeout = '5s'")
                cur.execute("SET statement_timeout = '60s'")
            else:
                cur.execute("SET lock_timeout = '500ms'")
                cur.execute("SET statement_timeout = '5s'")
            if only is not None:
                cur.execute(
                    "SELECT table_schema, table_name FROM information_schema.tables "
                    "WHERE table_type='BASE TABLE' AND table_schema = ANY(%s)",
                    (list(only),))
            else:
                cur.execute(
                    "SELECT table_schema, table_name FROM information_schema.tables "
                    "WHERE table_type='BASE TABLE'")
            targets = [(s, t) for s, t in cur.fetchall()
                       if s not in keep_all and not s.startswith("pg_")]
            if targets:
                try:
                    _truncate_nonempty(cur, targets)
                    conn.commit()
                except Exception:
                    conn.rollback()  # gesperrt → Bereinigung überspringen (kein Hänger)
                    # #1706: NICHT mehr stillschweigend. Genau hier verschwand der
                    # Hinweis, dass die Bereinigung an `max_locks_per_transaction`
                    # scheiterte (1048 Schemata / 7157 Tabellen angesammelt) — und
                    # damit der Grund, warum Tests je nach Vorgeschichte fehlschlugen.
                    log.warning("Test-Bereinigung uebersprungen (%d Tabellen, "
                                "alle_schemata=%s)", len(targets), alle_schemata,
                                exc_info=True)
    finally:
        pool.putconn(conn)


def drop_schema(db_path: Any) -> None:
    """Schema des Moduls für die Test-Isolation leeren.

    #1396: Statt DROP SCHEMA CASCADE + komplettem Neu-Anlegen aller Tabellen (teuer:
    das folgende ensure_db musste die gesamte DDL je Fixture-Test erneut ausführen,
    z. B. SOC ~1,5 s/Test) werden bestehende Tabellen nur **getruncatet**. Die Tabellen
    bleiben → das nachgelagerte ensure_db ist ein Cache-Treffer (No-op). Nur wenn das
    Schema/keine Tabellen existiert, wird das Schema angelegt (ensure_db erstellt dann
    die Tabellen wie gehabt). Datenstand identisch zu vorher (leer, IDENTITY reset).
    """
    schema = schema_for(db_path)
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s AND table_type = 'BASE TABLE'", (schema,))
            tables = [r[0] for r in cur.fetchall()]
            if tables:
                _truncate_nonempty(cur, [(schema, t) for t in tables])
            else:
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        conn.commit()
    finally:
        pool.putconn(conn)
    with _ensured_lock:
        _ensured_schemas.add(schema)
        # Tabellen bleiben bestehen → executescript-Cache bleibt gültig (kein Clear).


def drop_stale_test_schemas(*, batch: int = 50, limit: int = 0) -> int:
    """Wegwerf-Schemata vorheriger Testläufe **löschen** (#1706).

    Die Per-Test-Isolation leert nur die *berührten* Schemata (#1340) — zu Beginn
    eines Prozesses ist diese Liste leer, also überlebt alles aus vorherigen Läufen.
    Gegen eine dauerhafte Entwicklungs-Datenbank schlugen Tests dadurch je nach
    Vorgeschichte fehl (``assert 3 == 1``, weil Zeilen von gestern noch lagen).

    Truncaten reicht hier nicht: Jeder Lauf legt **neue** Schemata an (``tmp_path``-
    und uuid-basierte Namen). Lokal standen 1048 Schemata mit 7157 Tabellen; ein
    TRUNCATE über alle sprengt ``max_locks_per_transaction``:

        psycopg.errors.OutOfMemory: out of shared memory

    Diese Ausnahme wurde von ``drop_test_schemas`` stillschweigend verschluckt
    („gesperrt → überspringen"), weshalb der Altbestand unbemerkt wuchs. Deshalb
    hier **DROP SCHEMA CASCADE in Stapeln**, je Stapel eine eigene Transaktion —
    das hält die Lock-Zahl klein und räumt dauerhaft auf.

    Vorsicht: Läuft bewusst global. Zwei **parallele** pytest-Prozesse gegen dieselbe
    Datenbank würden sich die Schemata wegräumen. Im CI unkritisch (je Job eine eigene
    Datenbank), lokal laufen die Dateien sequenziell.

    Args:
        batch: Schemata je Transaktion.
        limit: höchstens so viele Schemata löschen (0 = alle). Für einen begrenzten
            Erstlauf, wenn sich sehr viel angesammelt hat.

    Returns:
        Anzahl gelöschter Schemata.
    """
    pool = get_pool()
    conn = pool.getconn()
    geloescht = 0
    try:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name <> ALL(%s) AND schema_name NOT LIKE 'pg\\_%%'",
                (list(_KEEP_SCHEMAS),))
            schemata = [r[0] for r in cur.fetchall()]
        conn.commit()
        if limit and limit > 0:
            schemata = schemata[:limit]

        for i in range(0, len(schemata), batch):
            teil = schemata[i:i + batch]
            try:
                with conn.cursor() as cur:
                    # Grosszuegiger als die Per-Test-Bereinigung: das laeuft einmal
                    # je Session und darf etwas kosten.
                    cur.execute("SET lock_timeout = '5s'")
                    cur.execute("SET statement_timeout = '60s'")
                    for name in teil:
                        cur.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')  # nosec B608 — Katalogname
                conn.commit()
                geloescht += len(teil)
            except Exception:  # noqa: BLE001 — ein Stapel darf den Rest nicht stoppen
                conn.rollback()
                log.warning("Konnte Schema-Stapel nicht loeschen (%d Schemata)",
                            len(teil), exc_info=True)
    finally:
        pool.putconn(conn)

    if geloescht:
        # Prozess-Caches entwerten — die Tabellen sind weg, ensure_db muss neu anlegen.
        with _ensured_lock:
            _ensured_schemas.clear()
            _ensured_scripts.clear()
            _ensured_ddl.clear()
    return geloescht
