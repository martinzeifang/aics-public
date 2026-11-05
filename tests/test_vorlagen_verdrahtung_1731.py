"""Vorlagen-Engine: jeder Adapter muss verdrahtet sein (#1731).

Die Zuordnung Modul → Adapter steht an **fünf** Stellen, die von Hand
gleichgehalten werden: ``shared/templates/schema.py`` (``_ADAPTERS``), die drei
Maps in ``server/api/templates`` (``_READ_PERM``, ``_EXPORT_PERM``,
``_MODULE_DB``) und die Auswahlliste im Admin-UI.

Beim Anbinden des Compliance-Audits kam heraus, dass **WiBA** (und das mit
#1905 entfernte SOC) einen
fertigen Adapter hatten, in der REST-Schicht aber unbekannt waren:

* ``GET /api/templates/schema/wiba`` → ``404 Unbekanntes Modul``
* Render → ``_EXPORT_PERM.get('wiba')`` ist ``None`` → ``has_permission(roles,
  None)`` ist ``False`` → **403 für jeden**, auch für Administratoren.

Kein Sicherheitsloch (es scheitert fail-closed), aber der WiBA-Vorlagen-Export
war seit #1126 unbenutzbar, ohne dass es auffiel. Dieselbe Fehlerklasse wie die
``COPY``-Liste im Dockerfile (#1714) und die dreifach kopierte Firmen-Whitelist:
**eine Liste an mehreren Orten läuft auseinander.** Deshalb dieser Test.

REGEL FÜR NEUE ADAPTER
Ein Kontext-Builder darf **kein** ``None`` liefern: Jinja druckt das wörtlich,
und so stand „None" in einem Kundenbericht. Der Test dazu hing am
SOC-Builder und ist mit dem Modul entfallen (#1905) — die Regel nicht.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from shared.templates import schema

REPO = Path(__file__).resolve().parent.parent
VIEW = REPO / 'frontend/src/views/admin/AdminTemplatesView.vue'


@pytest.fixture(scope='module')
def rest():
    import server.api.templates as t
    return t


def test_jeder_adapter_ist_in_der_rest_schicht(rest):
    """Ohne Eintrag antwortet das Modul mit 404 (Schema) bzw. 403 (Render)."""
    for name, karte in (('_READ_PERM', rest._READ_PERM),
                        ('_EXPORT_PERM', rest._EXPORT_PERM),
                        ('_MODULE_DB', rest._MODULE_DB)):
        fehlend = [m for m in schema.MODULE if m not in karte]
        assert not fehlend, (
            f'{name} kennt {fehlend} nicht — Vorlagen dieser Module sind '
            f'nicht nutzbar (404/403), obwohl ein Adapter existiert')


def test_keine_verwaisten_rest_eintraege(rest):
    """Umgekehrt: ein Eintrag ohne Adapter führt zu 501 beim Anwender."""
    for name, karte in (('_READ_PERM', rest._READ_PERM),
                        ('_EXPORT_PERM', rest._EXPORT_PERM),
                        ('_MODULE_DB', rest._MODULE_DB)):
        fremd = [m for m in karte if m not in schema.MODULE]
        assert not fremd, f'{name} nennt {fremd} ohne Adapter in der Engine'


def test_export_permission_passt_zum_modul(rest):
    """Die Export-Permission muss zum Modul gehören, nicht zu einem anderen.

    Ein Zahlendreher hier gäbe fremden Nutzern Zugriff auf die Vorlagen eines
    Moduls — das fällt im Betrieb kaum auf, weil der Export einfach funktioniert.
    """
    abweichend = []
    for modul, perm in rest._EXPORT_PERM.items():
        wert = getattr(perm, 'value', str(perm))
        erlaubt = {modul, modul.replace('_', ''),          # compliance_audit
                   {'aiact': 'ai_act', 'risikobewertung': 'rb'}.get(modul, modul)}
        if wert.split(':', 1)[0] not in erlaubt:
            abweichend.append((modul, wert))
    assert not abweichend, f'Permission gehoert zu einem anderen Modul: {abweichend}'
    assert all(getattr(p, 'value', '').endswith(':export')
               for p in rest._EXPORT_PERM.values()), 'keine Export-Permission'


def test_adapter_ist_im_admin_ui_auswaehlbar():
    """Ohne Eintrag im UI kann niemand eine Vorlage für das Modul hochladen."""
    block = re.search(r'const MODULE = \[(.*?)\]', VIEW.read_text(), re.DOTALL)
    assert block, 'Modul-Liste im Admin-UI nicht gefunden'
    ids = set(re.findall(r"id:\s*'([^']+)'", block.group(1)))
    fehlend = [m for m in schema.MODULE if m not in ids]
    assert not fehlend, f'Admin-UI kennt {fehlend} nicht'
    fremd = [m for m in ids if m not in schema.MODULE]
    assert not fremd, f'Admin-UI bietet {fremd} ohne Adapter an'


def test_jedes_modul_liefert_variablen_und_builder():
    """Ein registriertes Modul ohne Inhalt wäre eine leere Zusage."""
    leer = [m for m in schema.MODULE if not schema.get_variables(m)]
    assert not leer, f'ohne Variablen-Schema: {leer}'
    ohne = [m for m in schema.MODULE if schema.get_context_builder(m) is None]
    assert not ohne, f'ohne Kontext-Builder (→ 501): {ohne}'


def test_variablen_schema_ist_einheitlich_aufgebaut():
    """Das Admin-UI rendert alle Module mit denselben Feldern."""
    for modul in schema.MODULE:
        for v in schema.get_variables(modul):
            assert set(v) >= {'key', 'typ', 'beschreibung'}, (modul, v)
            assert v['key'] and v['beschreibung'], (modul, v)


def test_compliance_audit_nutzt_die_gutachten_db(rest):
    """Historischer Dateiname — hier leicht zu übersehen (#1713).

    Ein eigener ``compliance_audit.sqlite`` wäre leer, der Export also ohne
    Inhalt, ohne dass irgendetwas fehlschlägt.
    """
    assert rest._MODULE_DB['compliance_audit'].name == 'gutachten.sqlite'
