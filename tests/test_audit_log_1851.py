"""Der Revisionspfad eines Projekts — in allen sechs Modulen (#1851).

Alle sechs Module schreiben seit #1338 in dieselbe append-only Spur;
**ansehen** konnte man das nur in der Risikobewertung und in der
Administration. Der Anwender, der belegen muss, wer eine Bewertung geändert
hat, kommt an die Administration nicht heran — und genau er wird gefragt.

Geprüft wird das **Verhalten**, nicht die Verdrahtung: Ein Eintrag wird
geschrieben und muss in der Ansicht dieses Projekts auftauchen — und der
Eintrag eines **anderen** Projekts darf es nicht. Der zweite Test hat beim
Schreiben einen echten Defekt gefunden: `_rb_aenderungen` importierte
`risikobewertung.db.DB_PATH`, das es dort nicht gibt. Der ImportError wurde
vom `except` geschluckt, und das Änderungsprotokoll wäre **stillschweigend**
nie erschienen — genau die Fehlerklasse, die dieser Umbau beseitigt.
"""
import pytest
from shared.audit import audit_event


@pytest.fixture(autouse=True)
def _lizenz():
    from server import license_state
    cur = license_state._current
    vorher = (cur.state, list(cur.modules))
    cur.state, cur.modules = "ok", ["*"]
    yield
    cur.state, cur.modules = vorher


def test_audit_zeigt_eintraege_dieses_projekts(client, auth_headers):
    from cra.db import ensure_db, save_projekt, delete_projekt
    from server.api.cra import DB_PATH
    ensure_db(DB_PATH)
    save_projekt(DB_PATH, name="probe-audit-1851", unternehmen="U", produkt="P")
    try:
        audit_event("cra.probe.eins", module="cra",
                    details={"projekt": "probe-audit-1851", "user_id": "u1"})
        audit_event("cra.probe.fremd", module="cra",
                    details={"projekt": "ein-anderes-projekt", "user_id": "u2"})
        r = client.get("/api/cra/projekte/probe-audit-1851/audit",
                       headers=auth_headers)
        assert r.status_code == 200, r.get_json()
        d = r.get_json()
        aktionen = [e["aktion"] for e in d["eintraege"]]
        assert "cra.probe.eins" in aktionen, d
        assert "cra.probe.fremd" not in aktionen, "fremdes Projekt ist mitgekommen"
        eins = next(e for e in d["eintraege"] if e["aktion"] == "cra.probe.eins")
        assert eins["akteur"] == "u1", eins
        assert eins["quelle"] == "revisionspfad"
        assert d["fenster_erschoepft"] is False
        print("OK:", d["total"], "Einträge, Quellen:", d["quellen"])
    finally:
        delete_projekt(DB_PATH, "probe-audit-1851")


def test_rb_aenderungsprotokoll_kommt_mit(client, auth_headers):
    """Die zweite Quelle der Risikobewertung darf nicht stillschweigend fehlen."""
    from pathlib import Path
    # `_connect` legt das Schema an (es gibt kein `ensure_db` in diesem Modul).
    from risikobewertung.db import save_projekt, save_risiko, delete_projekt
    DB = Path("data/db/risikobewertung.sqlite")
    name = "probe-rb-audit-1851"
    save_projekt(DB, name=name, framework="STRIDE", beschreibung="Probe")
    try:
        save_risiko(DB, {"projekt_name": name, "risk_name": "Probe", "felder": {}})
        r = client.get(f"/api/risikobewertung/projekte/{name}/audit",
                       headers=auth_headers)
        assert r.status_code == 200, r.get_json()
        d = r.get_json()
        assert "aenderungen" in d["quellen"], (
            "Das Änderungsprotokoll (rb_change_log) fehlt — die zweite Quelle "
            f"ist nicht angekommen: {d}")
        print("OK: Quellen =", d["quellen"], "·", d["total"], "Einträge")
    finally:
        delete_projekt(DB, name)
