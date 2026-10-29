"""Alle Module können dasselbe mit Issues — und der Abgleich markiert (#1846/#1850).

Vor dem Umbau konnte jedes Modul etwas anderes: CRA-Risiken und
-Schwachstellen ließen sich verknüpfen, aber kein Issue-Inhalt übernehmen;
DSGVO glich projektweit ab, ohne zu markieren; WiBA hatte gar keinen
projektweiten Weg. Das war nicht entschieden, sondern über Jahre
nebeneinander gewachsen.

Geprüft wird hier **über die Routen** — der Unterschied zu
`test_issue_abgleich_1850.py` (dort der Kern ohne Flask) und zu
`test_issue_routen_inventar_1846.py` (dort die URLs). Netz gibt es nicht:
Der Abgleich fällt dann auf den gespeicherten Issue-Stand zurück, und genau
das ist der Pfad, den eine Installation ohne Token auch sieht.
"""
from __future__ import annotations

import sqlite3

import pytest

from cra.db import delete_projekt, ensure_db, list_vuln, load_owasp_checks, save_projekt, save_vuln
from server.api.cra import DB_PATH
from shared.issue_abgleich import MARKER
from shared.issue_links import add_link, ensure_tables, list_links

PROJ = "pytest-paritaet-1846"
BASE = "/api/cra"


@pytest.fixture(autouse=True)
def _volle_lizenz():
    from server import license_state
    cur = license_state._current
    vorher = (cur.state, list(cur.modules))
    cur.state, cur.modules = "ok", ["*"]
    yield
    cur.state, cur.modules = vorher


@pytest.fixture(autouse=True)
def _kein_netz(monkeypatch):
    """Kein Abruf nach außen — der Abgleich nutzt den gespeicherten Stand."""
    def _nein(*a, **kw):
        raise RuntimeError("kein Netz im Test")
    import shared.issue_sync as sync
    monkeypatch.setattr(sync, "sync_github_issue", _nein)
    monkeypatch.setattr(sync, "sync_gitlab_issue", _nein)


@pytest.fixture()
def projekt(client, auth_headers):
    ensure_db(DB_PATH)
    _links_weg()
    save_projekt(DB_PATH, name=PROJ, unternehmen="U", produkt="P")
    yield PROJ
    _links_weg()
    delete_projekt(DB_PATH, PROJ)


def _links_weg():
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("DELETE FROM linked_issues WHERE projekt_name=?", (PROJ,))
        con.commit()
        con.close()
    except Exception:  # noqa: BLE001
        pass


def _geschlossener_link(kind: str, objekt_id: str, nummer: int = 77):
    ensure_tables(DB_PATH)
    return add_link(DB_PATH, projekt_name=PROJ, object_kind=kind,
                    object_id=str(objekt_id), provider="github", repo="o/r",
                    url=f"https://github.com/o/r/issues/{nummer}",
                    issue_number=nummer, title="T", state="closed",
                    state_reason="completed")


def _feedback(monkeypatch, text: str = "## Issue #77\nEin Kommentar aus dem Ticket."):
    """`collect_issue_feedback` ersetzen — es würde sonst GitHub abrufen."""
    import shared.issue_feedback as fb
    monkeypatch.setattr(fb, "collect_issue_feedback",
                        lambda links, **kw: (text, [{"ok": True, "url": "u"}]))


def _erste_anforderung() -> str:
    from cra.requirements import load_merged_anforderungen
    reqs = load_merged_anforderungen(DB_PATH)
    assert reqs, "Der CRA-Anforderungskatalog ist leer"
    return str(reqs[0]["id"])


# ── CRA: Risiken und Schwachstellen können jetzt alles ──────────────────────

def test_schwachstelle_kann_issue_verknuepfen_und_inhalt_uebernehmen(
        client, auth_headers, projekt, monkeypatch):
    """Beides fehlte: An der Schwachstelle gab es weder `link` noch `import-issue`."""
    vid = save_vuln(DB_PATH, PROJ, {
        "cve_id": "CVE-2026-1846", "titel": "Lücke", "schwere": "high",
        "status": "open"})

    r = client.post(f"{BASE}/projekte/{PROJ}/vulns/{vid}/issues/link",
                    headers=auth_headers,
                    json={"url": "https://github.com/o/r/issues/12"})
    assert r.status_code == 201, r.get_json()
    assert list_links(DB_PATH, projekt_name=PROJ, object_kind="vuln",
                      object_id=str(vid))

    _feedback(monkeypatch)
    r = client.post(f"{BASE}/projekte/{PROJ}/vulns/{vid}/import-issue",
                    headers=auth_headers, json={})
    assert r.status_code == 200, r.get_json()
    v = next(v for v in list_vuln(DB_PATH, PROJ) if str(v["id"]) == str(vid))
    assert "Ein Kommentar aus dem Ticket." in (v.get("triage_kommentar") or "")
    assert v["status"] == "open", "Die Übernahme eines Textes bewertet nicht (#1526)."


def test_ungueltige_issue_url_ist_eine_eingabefehlermeldung(
        client, auth_headers, projekt):
    """`_parse_issue_url` wirft nicht, es liefert `None` — ohne Prüfung ein 500."""
    vid = save_vuln(DB_PATH, PROJ, {"cve_id": "CVE-2026-0001", "status": "open"})
    r = client.post(f"{BASE}/projekte/{PROJ}/vulns/{vid}/issues/link",
                    headers=auth_headers, json={"url": "kein-issue"})
    assert r.status_code == 400, r.get_json()


# ── Der projektweite Abgleich markiert ──────────────────────────────────────

def test_projektweiter_abgleich_markiert_die_bewertete_anforderung(
        client, auth_headers, projekt):
    req_id = _erste_anforderung()
    client.post(f"{BASE}/projekte/{PROJ}/bewertungen", headers=auth_headers,
                json={"anforderung_id": req_id, "bewertung": 3,
                      "kommentar": "Teilweise erfüllt"})
    _geschlossener_link("requirement", req_id, nummer=101)

    r = client.post(f"{BASE}/projekte/{PROJ}/issues/sync", headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["markiert"] == 1
    assert d["auto_completed"] == 1, "Bestandsschlüssel der Oberfläche"

    from cra.db import load_bewertungen
    b = load_bewertungen(DB_PATH, PROJ)[req_id]
    assert MARKER in b["kommentar"]
    assert "#101" in b["kommentar"], "Der Marker nennt das Ticket."
    assert int(b["bewertung"]) == 3, "Score unverändert (#1526)."


def test_projektweiter_abgleich_umfasst_alle_objektarten(
        client, auth_headers, projekt):
    """Vorher sah dieser Weg nur Anforderungen und OWASP — Risiken/Vulns nicht."""
    vid = save_vuln(DB_PATH, PROJ, {"cve_id": "CVE-2026-4242", "status": "open",
                                    "titel": "X"})
    _geschlossener_link("vuln", vid, nummer=202)

    r = client.post(f"{BASE}/projekte/{PROJ}/issues/sync", headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["je_art"].get("vuln") == 1

    v = next(v for v in list_vuln(DB_PATH, PROJ) if str(v["id"]) == str(vid))
    assert MARKER in (v.get("triage_kommentar") or "")


def test_projektweite_uebernahme_fuellt_jede_objektart(
        client, auth_headers, projekt, monkeypatch):
    from cra.owasp_proactive_controls import OWASP_PC_V3
    req_id = _erste_anforderung()
    owasp_id = str(OWASP_PC_V3[0]["id"])
    client.put(f"{BASE}/projekte/{PROJ}/owasp/{owasp_id}", headers=auth_headers,
               json={"status": 2, "kommentar": "Start"})
    _geschlossener_link("requirement", req_id, nummer=301)
    _geschlossener_link("owasp", owasp_id, nummer=302)
    _feedback(monkeypatch, "Inhalt aus dem Ticket")

    r = client.post(f"{BASE}/projekte/{PROJ}/issues/import", headers=auth_headers,
                    json={})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["imported"] == 2, (
        "Beide Objektarten — vorher übernahm dieser Weg nur Anforderungen.")

    from cra.db import load_bewertungen
    assert "Inhalt aus dem Ticket" in load_bewertungen(DB_PATH, PROJ)[req_id]["kommentar"]
    chk = load_owasp_checks(DB_PATH, PROJ)[owasp_id]
    assert "Inhalt aus dem Ticket" in chk["kommentar"]
    assert int(chk["status"]) == 2, "Status unverändert (#1526)."


def test_unbewertete_anforderung_wird_nicht_markiert(client, auth_headers, projekt):
    """Eine Markierung, die alle trifft, trifft niemanden (#1508)."""
    req_id = _erste_anforderung()
    _geschlossener_link("requirement", req_id, nummer=404)

    r = client.post(f"{BASE}/projekte/{PROJ}/issues/sync", headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()["markiert"] == 0

    from cra.db import load_bewertungen
    assert MARKER not in (load_bewertungen(DB_PATH, PROJ).get(req_id, {})
                          .get("kommentar") or "")
