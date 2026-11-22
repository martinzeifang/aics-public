"""Milestone #24 — DSGVO Jahres-Kontrollzyklus + Jahresbericht + Sign-off.

DB-Ebene (hermetisch) + Rollen/Permissions. Deckt #1128–#1134 (Kern) ab.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def dsgvo_db(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parent.parent
    db = repo_root / "data" / "db" / "pytest_dsgvo_jz_1128.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("", "-wal", "-shm"):
        p = Path(str(db) + ext)
        if p.exists():
            p.unlink()
    yield db
    for ext in ("", "-wal", "-shm"):
        p = Path(str(db) + ext)
        if p.exists():
            p.unlink()


# ── #1128 Rollen/Permissions ────────────────────────────────────────────────

def test_rollen_und_permissions():
    from server.models.permission import Permission, RoleEnum, ROLE_PERMISSIONS
    assert Permission.DSGVO_APPROVE.value == "dsgvo:approve"
    assert Permission.DSGVO_SIGN.value == "dsgvo:sign"
    assert Permission.DSGVO_APPROVE in ROLE_PERMISSIONS[RoleEnum.GESCHAEFTSFUEHRER]
    assert Permission.DSGVO_SIGN in ROLE_PERMISSIONS[RoleEnum.DSB]
    # Admin hat beides, Viewer keins
    assert Permission.DSGVO_SIGN in ROLE_PERMISSIONS[RoleEnum.ADMIN]
    assert Permission.DSGVO_APPROVE not in ROLE_PERMISSIONS[RoleEnum.VIEWER]


# ── #1129/#1130/#1131 Kontrollplan + Freigabe + Anhänge ──────────────────────

def test_kontrollplan_flow(dsgvo_db):
    from dsgvo import kontrollen_db as k
    k.ensure_table(dsgvo_db)
    n = k.seed_standard(dsgvo_db, "P", 2026)
    assert n == len(k.STANDARD_KONTROLLEN)
    # idempotent
    assert k.seed_standard(dsgvo_db, "P", 2026) == 0
    ks = k.list_kontrollen(dsgvo_db, "P", jahr=2026)
    pk = ks[0]["id"]
    # Freigabe
    k.set_status(dsgvo_db, pk, "freigegeben", freigabe_von="gf@x")
    assert k.get_kontrolle(dsgvo_db, pk)["status"] == "freigegeben"
    assert k.get_kontrolle(dsgvo_db, pk)["freigabe_von"] == "gf@x"
    # Durchführung + Abschluss
    k.dokumentieren(dsgvo_db, pk, durchgefuehrt_am="2026-05-01",
                    durchgefuehrt_von="dsb@x", ergebnis="ok", abschliessen=True)
    assert k.get_kontrolle(dsgvo_db, pk)["status"] == "abgeschlossen"


def test_kontroll_anhaenge(dsgvo_db):
    from dsgvo import kontrollen_db as k
    k.ensure_table(dsgvo_db)
    pk = k.save_kontrolle(dsgvo_db, "P", {"kontroll_id": "K1", "titel": "T", "jahr": 2026})
    rec = k.add_anhang(dsgvo_db, pk, filename="nachweis.txt", data=b"beleg", mime="text/plain")
    assert rec["sha256"]
    assert len(k.list_anhaenge(dsgvo_db, pk)) == 1
    assert k.soft_delete_anhang(dsgvo_db, rec["id"], by="u", reason="Testlauf") is True
    assert len(k.list_anhaenge(dsgvo_db, pk)) == 0


# ── #1132 Aggregation + #1133 Export + #1134 Sign-off ────────────────────────

def test_jahresbericht_aggregation_und_export(dsgvo_db):
    from dsgvo import kontrollen_db as k
    from dsgvo.jahresbericht import build_jahresbericht_context
    from dsgvo.jahresbericht_export import build_jahresbericht_docx
    k.ensure_table(dsgvo_db)
    k.seed_standard(dsgvo_db, "P", 2026)
    ctx = build_jahresbericht_context(dsgvo_db, "P", 2026)
    assert ctx["jahr"] == 2026
    assert ctx["meta"]["anzahl_kontrollen"] == len(k.STANDARD_KONTROLLEN)
    # DOCX-Export (python-docx, ohne Netz)
    data = build_jahresbericht_docx(dsgvo_db, "P", 2026, signoff={"status": "entwurf"})
    assert data[:2] == b"PK"  # docx = zip
    assert len(data) > 5000


def test_jahresbericht_signoff(dsgvo_db):
    from dsgvo import jahresbericht_db as jdb
    assert jdb.get(dsgvo_db, "P", 2026)["status"] == "entwurf"
    r = jdb.freigeben(dsgvo_db, "P", 2026, von="gf@x")
    assert r["status"] == "freigegeben"
    assert r["freigabe_von"] == "gf@x"
    r2 = jdb.signieren(dsgvo_db, "P", 2026, von="dsb@x", name="Dr. DSB", pdf_bytes=b"%PDF-1.4 test")
    assert r2["status"] == "signiert"
    assert r2["sha256"] and r2["signatur_name"] == "Dr. DSB"
    # Nach Signatur: erneute Freigabe wirkungslos (nur Entwürfe)
    r3 = jdb.freigeben(dsgvo_db, "P", 2026, von="gf2")
    assert r3["status"] == "signiert"


# ── #1135–#1137 Einzelberichte ───────────────────────────────────────────────

def test_einzelberichte(dsgvo_db):
    from dsgvo import einzelberichte as eb
    keys = {r["key"] for r in eb.available_reports()}
    assert {"vvt", "tom", "loeschkonzept", "betroffenenrechte", "transfer",
            "einwilligung", "dsfa", "dsb"} <= keys
    # DOCX-Render auch ohne Daten (leeres Projekt) robust
    data = eb.build_docx(dsgvo_db, "LeeresProjekt", "vvt")
    assert data[:2] == b"PK" and len(data) > 3000
