"""Sprint #50 — Lizenzmanagement & Mandantenfähigkeit (#1704–#1711).

Reine Logik-Tests ohne DB: Modul-Registry/Lizenz-Gate, Preisblatt inkl.
Mengenstaffel, CSV-Export und die Scoping-Helfer der Mandantenfähigkeit.
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ── #1704 Modul-Registry & Lizenz-Gate ───────────────────────────────────────

@pytest.mark.parametrize('path,erwartet', [
    ('/api/cra/projekte', 'cra'),
    ('/api/dsgvo-tom/projekte/x/massnahmen', 'dsgvo'),       # #1169 Bindestrich-Prefix
    ('/api/cra-konformitaet/projekte/x/nachweis', 'cra'),
    ('/api/aiact-literacy/register', 'aiact'),
    ('/api/ai_act/projekte', 'aiact'),                        # Alias
    ('/api/nis2-audit/x', 'nis2'),
    ('/api/wiba/projekte', 'wiba'),                           # vorher NICHT gegated
    ('/api/pentest/firma/berichte', 'pentest'),               # vorher NICHT gegated
    ('/api/firmen', 'firmen'),
    ('/api/kunden/x', 'firmen'),                              # Deprecation-Alias #1003
    ('/api/risk-cockpit/7', None),                            # read-only, kein Modul
    ('/api/admin/settings', None),
    ('/api/auth/login', None),
    ('/api/health', None),
    ('', None),
])
def test_module_for_path(path, erwartet):
    from shared.licensing.modules import module_for_path
    assert module_for_path(path) == erwartet


def test_wildcard_erlaubt_alles_ausser_gutachten():
    """``*`` deckt Grundpreis + Zusatzmodule + SOC ab, aber nicht Gutachten.

    Regression zum Verhalten vor #1704: Gutachten brauchte schon immer die
    explizite Nennung, SOC lief unter Wildcard (SOC-Portal auf Volllizenz).
    """
    from shared.licensing.modules import is_allowed
    for mod in ('cra', 'nis2', 'aiact', 'dsgvo', 'wiba', 'pentest',
                'risikobewertung', 'soc'):
        assert is_allowed(mod, None) is True, mod
    assert is_allowed('gutachten', None) is False


def test_ohne_lizenz_keine_fachmodul_schreibzugriffe():
    """Leeres Set = keine bestätigte Lizenz → alles gegatete blockiert."""
    from shared.licensing.modules import is_allowed
    for mod in ('cra', 'nis2', 'aiact', 'dsgvo', 'wiba', 'pentest', 'risikobewertung'):
        assert is_allowed(mod, set()) is False, mod


def test_grundpreis_module_brauchen_keine_einzelnennung():
    """#1704 Kern: WiBA/Pentest/Risikobewertung sind im Grundpreis enthalten —
    jede gültige Lizenz schließt sie ein, auch wenn der Token sie nicht nennt."""
    from shared.licensing.modules import is_allowed
    allowed = {'cra', 'dsgvo'}
    assert is_allowed('wiba', allowed) is True
    assert is_allowed('pentest', allowed) is True
    assert is_allowed('risikobewertung', allowed) is True
    # Nicht gebuchte Zusatzmodule bleiben gesperrt.
    assert is_allowed('nis2', allowed) is False
    assert is_allowed('aiact', allowed) is False


def test_firmen_ist_nie_modul_gegated():
    """Mandantenregister darf nie wegen eines Lizenzproblems ausfallen (Recovery)."""
    from shared.licensing.modules import is_allowed
    for allowed in (None, set(), {'cra'}):
        assert is_allowed('firmen', allowed) is None


def test_gate_deckt_alle_modul_prefixe_ab():
    """Regression: kein Fachmodul-Prefix fällt mehr durchs Gate (altes LIC_MODULES
    kannte wiba/pentest nicht)."""
    from shared.licensing.modules import GATED_MODULES, module_for_path
    for prefix in ('cra', 'nis2', 'aiact', 'dsgvo', 'wiba', 'pentest',
                   'risikobewertung', 'gutachten', 'soc'):
        assert module_for_path(f'/api/{prefix}/x') in GATED_MODULES


def test_effektive_und_abrechenbare_module():
    from shared.licensing.modules import billable_modules, effective_modules
    eff = effective_modules({'cra', 'dsgvo'})
    assert 'wiba' in eff and 'pentest' in eff and 'firmen' in eff
    assert 'nis2' not in eff
    assert billable_modules({'cra', 'dsgvo'}) == ['cra', 'dsgvo']


# ── #1821 Keine Preise in der Anwendung ──────────────────────────────────────

def test_kein_preisblatt_in_der_anwendung():
    """Die Installation des Kunden führt keine Preise (#1821).

    Bis v8.0.11 lag hier ein pflegbares Preisblatt — Grundpreis, Modulpreise,
    Mengenstaffel — mit Editor unter *Administration → Abrechnung*. Das war aus
    zwei Gründen falsch:

    * Preise gehören auf die Seite des Vermieters. Eine Installation, die dem
      Kunden seine Einkaufspreise anzeigt, kennt man von anderer Software auch
      nicht; verbindlich ist der Vertrag, gerechnet wird im Lizenzserver aus
      dem Mandanten-Inventar, das der Heartbeat ohnehin meldet.
    * Es gab das Preisblatt **zweimal**, hier und im Lizenzserver, und beide
      waren bereits auseinandergelaufen (CRA 150 gegen 190 €). Zwei Preislisten
      sind eine zu viel — dieselbe Fehlerklasse wie die Spiegel-Listen aus
      #1731/#1735, nur dass sie hier im Angebot landet.
    """
    import importlib
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module('shared.licensing.pricing')


def test_nutzungsreport_nennt_keine_betraege():
    """Was genutzt wird: ja. Was es kostet: nicht hier."""
    from shared.licensing import usage
    quelle = Path('shared/licensing/usage.py').read_text(encoding='utf-8')
    for wort in ('monatspreis', 'listenpreis', 'rabatt_prozent', 'waehrung',
                 'preisblatt', 'pricing'):
        assert wort not in quelle, f"'{wort}' gehoert nicht mehr in den Nutzungsreport"
    assert hasattr(usage, 'build_usage') and hasattr(usage, 'usage_csv')


def test_keine_preis_endpunkte_mehr():
    quelle = Path('server/api/admin.py').read_text(encoding='utf-8')
    assert "'/licensing/preisblatt'" not in quelle
    assert 'save_preisblatt' not in quelle
    # Der Nutzungsreport bleibt — Mandanten und Module sind Betriebsdaten.
    assert "'/licensing/usage'" in quelle


def test_oberflaeche_zeigt_keine_betraege():
    ansicht = Path('frontend/src/views/admin/LicensingUsageView.vue').read_text(
        encoding='utf-8')
    for wort in ('monatspreis', 'jahrespreis', 'listenpreis_monat', 'preisDraft',
                 'vollpreis'):
        assert wort not in ansicht, f"'{wort}' wird wieder angezeigt"


# ── #1706 Abrechnungs-Export ─────────────────────────────────────────────────

def _report():
    return {
        'stichtag': '2026-10-20',
        'mandanten': [{
            'firmen_id': 1, 'name': 'Muster GmbH', 'unternehmen': 'Muster',
            'berater': 'MZ', 'aktiv': True, 'ruhend': False, 'projekte_gesamt': 3,
            'module_gebucht': ['cra', 'wiba', 'risikobewertung', 'pentest'],
        }],
        'summe': {'mandanten_aktiv': 1, 'mandanten_gesamt': 2},
    }


def test_usage_csv_ohne_betraege():
    """Der Export nennt Mandanten und gebuchte Module — keine Beträge (#1821)."""
    from shared.licensing.usage import usage_csv
    csv_text = usage_csv(_report())
    kopf, zeile = csv_text.splitlines()[0], csv_text.splitlines()[1]
    assert kopf.startswith('Stichtag;Firmen-ID;Mandant')
    assert 'Muster GmbH' in zeile
    assert zeile.count(';') == kopf.count(';')
    assert 'SUMME' in csv_text
    for wort in ('Monatspreis', 'Listenpreis', 'Grundpreis', 'Währung'):
        assert wort not in kopf, f"'{wort}' gehoert nicht mehr in den Export"


def test_tage_her_parst_verschiedene_stempel():
    from shared.licensing.usage import _tage_her
    assert _tage_her('') is None
    assert _tage_her('kaputt') is None
    for stamp in ('2026-10-13', '2026-10-13T10:00:00Z', '2026-10-13 10:00:00'):
        tage = _tage_her(stamp)
        assert isinstance(tage, int) and tage >= 0


def test_projekt_zuordnung_prioritaet():
    """firmen_id gewinnt, dann Firmenname, dann Projektname (Auto-Anlage #430)."""
    from shared.licensing.usage import _assign
    gruppen = _assign(
        [{'name': 'P-FK', 'firma_name': 'Falsch', 'firmen_id': 7},
         {'name': 'P-Name', 'firma_name': 'Muster GmbH', 'firmen_id': None},
         {'name': 'Andere AG', 'firma_name': '', 'firmen_id': None},
         {'name': 'Waise', 'firma_name': 'Unbekannt AG', 'firmen_id': None}],
        {7: 'Muster GmbH'},
        {'muster gmbh': 'Muster GmbH', 'andere ag': 'Andere AG'},
    )
    assert {p['name'] for p in gruppen['Muster GmbH']} == {'P-FK', 'P-Name'}
    assert [p['name'] for p in gruppen['Andere AG']] == ['Andere AG']
    assert [p['name'] for p in gruppen['']] == ['Waise']  # Waisen unter ''


# ── #1707 Mandantenfähigkeit: Listen-Scoping ─────────────────────────────────

def test_item_firma_keys():
    from shared.tenancy import item_firma_keys
    assert item_firma_keys({'name': 'A – Produkt', 'unternehmen': 'A GmbH'}) == \
        {'a – produkt', 'a gmbh'}
    assert item_firma_keys({'name': 'X', 'organisation': 'Org AG'}) == {'x', 'org ag'}
    assert item_firma_keys({}) == set()


def test_scoping_ohne_whitelist_filtert_nicht(monkeypatch):
    from shared import tenancy
    items = [{'name': 'A', 'unternehmen': 'A GmbH'}, {'name': 'B'}]
    assert tenancy.scope_projekt_items(items, {'allowed_firmen': None}) == items
    assert tenancy.scope_projekt_items(items, {}) == items


def test_scoping_mit_whitelist_ist_fail_closed(monkeypatch):
    """Projekte ohne auflösbare Firma werden bei aktiver Whitelist ausgeblendet —
    sie gehören keinem der freigegebenen Mandanten."""
    from shared import tenancy
    monkeypatch.setattr(tenancy, 'allowed_firma_keys',
                        lambda claims, db_dir=None: {'a gmbh'})
    items = [
        {'name': 'A – Produkt', 'unternehmen': 'A GmbH'},   # Treffer über unternehmen
        {'name': 'A GmbH'},                                  # Treffer über Projektname
        {'name': 'B – Produkt', 'unternehmen': 'B GmbH'},    # fremder Mandant
        {'name': 'Waise'},                                   # keine Zuordnung
    ]
    sichtbar = {it['name'] for it in
                tenancy.scope_projekt_items(items, {'allowed_firmen': [1]})}
    assert sichtbar == {'A – Produkt', 'A GmbH'}


def test_leere_whitelist_gibt_nichts_frei(monkeypatch):
    from shared import tenancy
    monkeypatch.setattr(tenancy, 'allowed_firma_keys',
                        lambda claims, db_dir=None: set())
    items = [{'name': 'A', 'unternehmen': 'A GmbH'}]
    assert tenancy.scope_projekt_items(items, {'allowed_firmen': []}) == []


def test_scope_current_request_ohne_jwt_kontext():
    """Ohne Request-/JWT-Kontext (CLI, Tests) darf nichts gefiltert werden."""
    from shared.tenancy import scope_current_request
    items = [{'name': 'A'}]
    assert scope_current_request(items) == items
