"""Sprint #28 (#1241) — NIS2 Web-Verknüpfung + Links/Verweise im Bericht.

Web-Link-Modus für Pflichtdokumente (über die generische DokumenteRegister/
Editor-Mechanik, #1233) erscheint als Bericht-Referenz; interne Verweise
(Playbook-URL, CSIRT, BCP-URL, Vendor-SLA/DPA) werden gebündelt. Tests laufen
auf einer isolierten tmp-DB.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from nis2 import db as ndb
from nis2.template_context import build_nis2_context, NIS2_VARIABLES
from shared.documents import db as ddb

# nis2.db erzwingt eine Workspace-Root-Sandbox (shared/db_security) → die
# isolierte Test-DB muss in-Repo unter data/db/ liegen (eindeutiger Name +
# Cleanup), nicht unter /tmp.
_REPO = Path(__file__).resolve().parent.parent

PROJ = "VerweiseTest"


@pytest.fixture
def nis2_db():
    tag = uuid.uuid4().hex[:8]
    db = _REPO / "data" / "db" / f"_test_nis2_verweise_{tag}.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    ndb.ensure_db(db)
    ndb.save_projekt(db, PROJ, unternehmen="ACME GmbH")
    yield db
    for e in ("", "-wal", "-shm"):
        p = Path(str(db) + e)
        if p.exists():
            p.unlink()


# ── Interne Verweise: gebündelt aus N3/N4/N5 (keine Neu-Erfassung) ──────────

def test_dokument_verweise_bundles_internal_refs(nis2_db):
    ndb.save_incident_response(nis2_db, PROJ, {
        "csirt_kontakt": "CERT-Bund", "csirt_email": "cert@example.org",
        "playbook_url": "https://wiki/playbook"})
    ndb.save_bcp(nis2_db, PROJ, {"bcp_url": "https://wiki/bcp"})
    ndb.save_vendor(nis2_db, PROJ, {
        "vendor_name": "CloudCo", "leistung": "IaaS",
        "sla_url": "https://cloudco/sla", "dpa_url": "https://cloudco/dpa"})

    ctx = build_nis2_context(nis2_db, PROJ)
    verweise = ctx["dokument_verweise"]
    urls = {v["url"] for v in verweise}
    assert "https://wiki/playbook" in urls
    assert "cert@example.org" in urls
    assert "https://wiki/bcp" in urls
    assert "https://cloudco/sla" in urls
    assert "https://cloudco/dpa" in urls
    # Jeder Verweis nennt das zugehörige Pflichtdokument.
    assert all(v["label"] and v["quelle"] for v in verweise)


def test_dokument_verweise_empty_when_no_refs(nis2_db):
    ctx = build_nis2_context(nis2_db, PROJ)
    assert ctx["dokument_verweise"] == []


# ── Web-Link-Dokument erscheint als Bericht-Referenz (#1233 + #1241) ─────────

def test_external_document_referenced_in_report(nis2_db):
    did = ddb.create_document(
        nis2_db, "nis2", projekt=PROJ, doc_type="krypto_richtlinie",
        titel="Krypto-Policy (extern)", doc_mode="extern",
        external_url="https://confluence/krypto", external_label="Confluence")
    ddb.set_status(nis2_db, "nis2", did, "freigegeben")

    ctx = build_nis2_context(nis2_db, PROJ)
    docs = {d["doc_type"]: d for d in ctx["dokumente"]}
    assert "krypto_richtlinie" in docs
    d = docs["krypto_richtlinie"]
    assert d["extern"] is True
    assert d["doc_mode"] == "extern"
    assert d["external_url"] == "https://confluence/krypto"
    assert d["external_label"] == "Confluence"


def test_inapp_document_default_mode(nis2_db):
    did = ddb.create_document(nis2_db, "nis2", projekt=PROJ,
                              doc_type="is_leitlinie", titel="IS-Leitlinie",
                              content_html="<h1>IS</h1>")
    ddb.set_status(nis2_db, "nis2", did, "final")
    ctx = build_nis2_context(nis2_db, PROJ)
    d = {x["doc_type"]: x for x in ctx["dokumente"]}["is_leitlinie"]
    assert d["extern"] is False
    assert d["doc_mode"] == "inapp"


def test_variables_documented():
    keys = {v["key"] for v in NIS2_VARIABLES}
    assert "dokument_verweise" in keys
    assert "dokumente" in keys
