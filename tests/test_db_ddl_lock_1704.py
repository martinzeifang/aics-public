"""#1704 — DDL-Advisory-Lock darf nicht unbegrenzt blockieren.

``shared.db`` serialisiert alle Schema-DDL über ``pg_advisory_xact_lock`` (#1355).
Dieser Lock gilt bis zum Ende der **Transaktion**. Wird eine Verbindung mitten im
DDL weggeworfen, ohne dass ``commit``/``rollback``/``close`` läuft, bleibt ihre
Transaktion offen — und jeder weitere DDL-Versuch im Prozess wartete *für immer*.

Im CI war das der Worst Case: ``pg_advisory_xact_lock`` blockiert unterhalb von
Python im Socket-Wait, also greift ``pytest-timeout --timeout-method=thread`` nicht.
Der Shard brach ohne pytest-Summary ab — im Log nicht von „alles grün" zu
unterscheiden.
"""
from __future__ import annotations

import uuid

import pytest

from shared import db as sdb


class FakeCur:
    """Minimaler Cursor-Ersatz — macht die SQL-Folge ohne Datenbank prüfbar."""

    def __init__(self, *, fehler_bei: str = '', fehler: Exception | None = None):
        self.aufrufe: list[tuple[str, tuple | None]] = []
        self._fehler_bei = fehler_bei
        self._fehler = fehler

    def execute(self, sql, params=None):
        self.aufrufe.append((sql, params))
        if self._fehler_bei and self._fehler_bei in sql:
            raise self._fehler


def _tabellen_weg(path: str) -> None:
    con = sdb.connect(path)
    try:
        namen = [r[0] for r in con.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
        ).fetchall()]
        for t in namen:
            con.execute(f'DROP TABLE "{t}" CASCADE')
        con.commit()
    finally:
        con.close()


@pytest.fixture
def schemata():
    a, b = 'data/db/_pytest_ddl_lock_a.sqlite', 'data/db/_pytest_ddl_lock_b.sqlite'
    yield a, b
    for p in (a, b):
        try:
            _tabellen_weg(p)
        except Exception:  # noqa: BLE001 — Aufräumen darf den Test nicht kippen
            pass


def test_ddl_lock_timeout_statt_haenger(schemata, monkeypatch):
    """Hält eine offene Transaktion den Lock, scheitert DDL sichtbar statt zu hängen."""
    a, b = schemata
    monkeypatch.setattr(sdb, '_DDL_LOCK_TIMEOUT_S', 0.3)

    halter = sdb.connect(a)
    try:
        # Plain CREATE (kein IF NOT EXISTS) → geht garantiert über den Lock-Pfad und
        # nicht über den Prozess-Cache für idempotentes DDL (#1396).
        halter.execute(f'CREATE TABLE sperre_{uuid.uuid4().hex[:8]} (id INTEGER)')
        # BEWUSST kein commit/close: genau der Zustand, der den Shard aufgehängt hat.

        zweite = sdb.connect(b)
        try:
            with pytest.raises(sdb.DDLLockTimeout):
                zweite.execute(f'CREATE TABLE blockiert_{uuid.uuid4().hex[:8]} (id INTEGER)')
        finally:
            zweite.close()
    finally:
        halter.close()


def test_lock_ist_nach_close_wieder_frei(schemata, monkeypatch):
    """``close()`` rollt zurück und gibt den Lock frei — danach läuft DDL normal."""
    a, b = schemata
    monkeypatch.setattr(sdb, '_DDL_LOCK_TIMEOUT_S', 5.0)

    halter = sdb.connect(a)
    halter.execute(f'CREATE TABLE haelt_{uuid.uuid4().hex[:8]} (id INTEGER)')
    halter.close()  # rollback + putconn → Transaktion zu, Lock frei

    zweite = sdb.connect(b)
    try:
        name = f'danach_{uuid.uuid4().hex[:8]}'
        zweite.execute(f'CREATE TABLE {name} (id INTEGER)')
        zweite.commit()
        treffer = zweite.execute(
            "SELECT count(*) FROM pg_tables "
            "WHERE schemaname = current_schema() AND tablename = ?", (name,)
        ).fetchone()
        assert treffer[0] == 1
    finally:
        zweite.close()


def test_timeout_null_behaelt_unbegrenztes_warten(monkeypatch):
    """``AICS_DDL_LOCK_TIMEOUT=0`` ist der Not-Ausstieg zum alten Verhalten (ohne DB)."""
    monkeypatch.setattr(sdb, '_DDL_LOCK_TIMEOUT_S', 0)

    cur = FakeCur()
    sdb._acquire_ddl_lock(cur)
    assert cur.aufrufe == [('SELECT pg_advisory_xact_lock(%s)', (sdb._DDL_LOCK_KEY,))]


def test_deadline_setzt_lock_timeout_und_raeumt_auf(monkeypatch):
    """Mit Deadline: lock_timeout setzen, blockierend sperren, danach zurückstellen."""
    monkeypatch.setattr(sdb, '_DDL_LOCK_TIMEOUT_S', 2.5)

    cur = FakeCur()
    sdb._acquire_ddl_lock(cur)

    assert cur.aufrufe == [
        ("SELECT set_config('lock_timeout', %s, true)", ('2500ms',)),
        ('SELECT pg_advisory_xact_lock(%s)', (sdb._DDL_LOCK_KEY,)),
        ("SELECT set_config('lock_timeout', '0', true)", None),
    ]


def test_lock_timeout_wird_zu_ddl_lock_timeout(monkeypatch):
    """SQLSTATE 55P03 wird in die sprechende DDLLockTimeout übersetzt."""
    monkeypatch.setattr(sdb, '_DDL_LOCK_TIMEOUT_S', 1.0)

    class Sperre(Exception):
        sqlstate = '55P03'

    cur = FakeCur(fehler_bei='pg_advisory_xact_lock', fehler=Sperre('lock timeout'))
    with pytest.raises(sdb.DDLLockTimeout) as info:
        sdb._acquire_ddl_lock(cur)
    assert 'AICS_DDL_LOCK_TIMEOUT=0' in str(info.value)


def test_andere_fehler_werden_nicht_verschluckt(monkeypatch):
    """Nur 55P03 wird übersetzt — alles andere muss unverändert durchfliegen."""
    monkeypatch.setattr(sdb, '_DDL_LOCK_TIMEOUT_S', 1.0)

    class Anders(Exception):
        sqlstate = '42501'  # insufficient_privilege

    cur = FakeCur(fehler_bei='pg_advisory_xact_lock', fehler=Anders('keine Rechte'))
    with pytest.raises(Anders):
        sdb._acquire_ddl_lock(cur)
