"""#2130: Eigene Normen per Wizard anlegen und einbinden."""
from pathlib import Path

import gutachten.gerichts_db as g
from gutachten.db import ingest_sections
import gutachten.ki_assistenten as k

DB = Path("data/db/gutachten.sqlite")


def test_anlegen_vergibt_key_und_framework():
    g.ensure_db(DB)
    c = g.save_custom_norm(DB, titel="ISO/IEC 30111 — Vulnerability Handling 2130",
                           version="2019", domain="sicherheit",
                           soll_kurz="Umgang mit gemeldeten Schwachstellen.")
    assert c["norm_key"].startswith("custom-")
    assert c["framework"] == c["norm_key"].replace("-", "_").upper()
    assert c["framework"].startswith("CUSTOM_") and "CUSTOM_CUSTOM" not in c["framework"]


def test_eindeutiger_slug_bei_gleichem_titel():
    g.ensure_db(DB)
    a = g.save_custom_norm(DB, titel="Doppelter Titel 2130")
    b = g.save_custom_norm(DB, titel="Doppelter Titel 2130")
    assert a["norm_key"] != b["norm_key"]


def test_effektive_framework_config_enthaelt_custom():
    g.ensure_db(DB)
    c = g.save_custom_norm(DB, titel="Framework-Slot-Norm 2130")
    import server.api.compliance_audit as ca
    fw = ca._effective_framework_config()
    assert c["framework"] in fw
    assert fw[c["framework"]]["data_dir"].endswith(c["norm_key"])


def test_normtext_wird_in_recherche_belegbar():
    g.ensure_db(DB)
    c = g.save_custom_norm(DB, titel="Recherche-Norm 2130")
    ingest_sections(DB, c["framework"], "norm.pdf", [
        {"section_ref": "5", "title": "Prozess",
         "text": "Der Hersteller behandelt gemeldete Schwachstellen nach einem definierten Prozess."}])
    tr = k.norm_volltext_treffer("Wie werden gemeldete Schwachstellen behandelt?",
                                 [{"titel": c["titel"], "framework": c["framework"]}], DB)
    assert tr and "Schwachstellen" in tr[0]["auszug"]


def test_loeschen():
    g.ensure_db(DB)
    c = g.save_custom_norm(DB, titel="Lösch-Norm 2130")
    g.delete_custom_norm(DB, c["id"])
    assert g.get_custom_norm(DB, c["norm_key"]) is None
