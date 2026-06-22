"""Audit-Trail auf Postgres mit Integritätskette (#1338).

Prüft: Append-only-Persistenz nach Postgres (Schema ``audit``), korrekte SHA-256-
Verkettung und Manipulations-Erkennung via ``verify_chain``.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def clean_audit(pg):
    """Audit-Tabelle vor und nach dem Test leeren (Schema ``audit`` wird NICHT
    automatisch zwischen Tests getruncatet — siehe shared/db._KEEP_SCHEMAS)."""
    from shared.audit_db import AUDIT_DB_PATH, ensure_audit_db

    def _wipe():
        with pg.connect(str(AUDIT_DB_PATH)) as conn:
            ensure_audit_db(conn)
            conn.execute("DELETE FROM audit_events")
            conn.commit()

    _wipe()
    yield
    _wipe()


def test_record_and_verify_chain(pg, clean_audit):
    from shared.audit_db import record_audit_event, verify_chain

    id1 = record_audit_event(ts="2026-06-19T10:00:00+00:00", action="auth.login",
                             module="auth", outcome="success", actor="u1",
                             details={"ip": "10.0.0.1"})
    id2 = record_audit_event(ts="2026-06-19T10:01:00+00:00", action="cra.delete",
                             module="cra", outcome="success", actor="u2",
                             details={"projekt": "P1"})
    assert id1 is not None and id2 is not None and id2 > id1

    result = verify_chain()
    assert result["ok"] is True
    assert result["count"] == 2
    assert result["broken_at"] is None


def test_chain_links_prev_hash(pg, clean_audit):
    from shared.audit_db import AUDIT_DB_PATH, ensure_audit_db, record_audit_event

    record_audit_event(ts="2026-06-19T11:00:00+00:00", action="a1", module="m")
    record_audit_event(ts="2026-06-19T11:00:01+00:00", action="a2", module="m")

    with pg.connect(str(AUDIT_DB_PATH)) as conn:
        ensure_audit_db(conn)
        cur = conn.cursor()
        cur.execute("SELECT id, prev_hash, row_hash FROM audit_events ORDER BY id ASC")
        rows = cur.fetchall()

    assert rows[0]["prev_hash"] == ""  # Genesis
    # prev_hash der zweiten Zeile == row_hash der ersten → lückenlose Kette
    assert rows[1]["prev_hash"] == rows[0]["row_hash"]


def test_tampering_breaks_chain(pg, clean_audit):
    from shared.audit_db import AUDIT_DB_PATH, ensure_audit_db, record_audit_event, verify_chain

    record_audit_event(ts="2026-06-19T12:00:00+00:00", action="ok1", module="m")
    tampered_id = record_audit_event(ts="2026-06-19T12:00:01+00:00", action="ok2", module="m")
    record_audit_event(ts="2026-06-19T12:00:02+00:00", action="ok3", module="m")

    # Nachträgliche Manipulation EINER Zeile (Inhalt geändert, Hash nicht) → Kette bricht.
    with pg.connect(str(AUDIT_DB_PATH)) as conn:
        ensure_audit_db(conn)
        conn.execute("UPDATE audit_events SET details = ? WHERE id = ?",
                     ('{"manipuliert": true}', tampered_id))
        conn.commit()

    result = verify_chain()
    assert result["ok"] is False
    assert result["broken_at"] == tampered_id
