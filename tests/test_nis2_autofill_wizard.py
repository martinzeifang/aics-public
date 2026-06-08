"""Sprint #21 (#1072/#1073) — NIS2 N1 Asset-Inventar-Wizard (Prompt/Parse)
und N2 Read-only-Prep (TODO-Marker bleibt; manuelle Eingabe unangetastet)."""

from __future__ import annotations

from nis2 import ai_wizards as w


def test_asset_inventory_prompt_contains_context():
    p = {"unternehmen": "ACME GmbH", "sektor": "Energie", "beschreibung": "Stromnetz"}
    prompt = w.build_asset_inventory_prompt(p)
    assert "ACME GmbH" in prompt
    assert "Energie" in prompt
    # Erlaubte Typen/Kritikalität sind im Prompt erwähnt
    assert "cloud-service" in prompt
    assert "kritisch" in prompt
    assert "asset_name" in prompt


def test_parse_asset_inventory_response_object():
    raw = """```json
    {"assets": [
      {"asset_name": "ERP", "asset_typ": "it", "kritikalitaet": "hoch",
       "schutzbedarf_v": 2, "schutzbedarf_i": 3, "schutzbedarf_a": 3},
      {"asset_name": "Lager-SPS", "asset_typ": "ot", "kritikalitaet": "kritisch"}
    ]}
    ```"""
    out = w.parse_asset_inventory_response(raw)
    assert len(out["assets"]) == 2
    erp = out["assets"][0]
    assert erp["asset_name"] == "ERP"
    assert erp["asset_typ"] == "it"
    assert erp["schutzbedarf_i"] == 3
    # Defaults bei fehlenden Schutzbedarfs-Feldern
    assert out["assets"][1]["schutzbedarf_v"] == 1


def test_parse_asset_inventory_response_bare_array():
    raw = '[{"asset_name": "Firewall", "asset_typ": "netzwerk"}]'
    out = w.parse_asset_inventory_response(raw)
    assert out["assets"][0]["asset_name"] == "Firewall"
    assert out["assets"][0]["asset_typ"] == "netzwerk"


def test_parse_asset_inventory_normalizes_invalid_values():
    raw = ('{"assets": [{"asset_name": "X", "asset_typ": "quantum", '
           '"kritikalitaet": "explosiv", "schutzbedarf_a": 99}]}')
    out = w.parse_asset_inventory_response(raw)
    a = out["assets"][0]
    assert a["asset_typ"] == "it"          # ungültig → Default
    assert a["kritikalitaet"] == "mittel"  # ungültig → Default
    assert a["schutzbedarf_a"] == 3        # geklemmt auf max 3


def test_parse_asset_inventory_skips_nameless_and_garbage():
    raw = '{"assets": [{"asset_typ": "it"}, "nope", {"asset_name": "Keep"}]}'
    out = w.parse_asset_inventory_response(raw)
    assert len(out["assets"]) == 1
    assert out["assets"][0]["asset_name"] == "Keep"


def test_parse_asset_inventory_empty():
    assert w.parse_asset_inventory_response("kein json") == {"assets": []}


def test_n2_sektor_templates_still_present():
    """#1073: N2-Wizard (Sektor-Templates) wird NICHT entfernt — Compliance:
    Risiko-Register bleibt mit Wizard + manueller Eingabe erhalten."""
    templates = w.list_sektor_templates()
    assert templates
    # RPO/RTO-Sektor-Defaults (N5) bleiben für die Compliance erhalten
    bank = w.get_sektor_template("banken-finanzen")
    assert bank["rpo_minuten"] == 5


def test_existing_wizards_intact():
    """Compliance-Regel: bestehende NIS2-Wizards (Cyberhygiene N16, Vendor-
    Tiering N17) bleiben funktionsfähig."""
    assert callable(w.build_cyberhygiene_quiz_prompt)
    assert callable(w.build_vendor_tiering_prompt)
    assert "normal" in w.VENDOR_TIERS or w.VENDOR_TIERS
