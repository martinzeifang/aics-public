"""Rollentrennung Entwicklung/Compliance + Statusmaschine je Release (#1743).

Der Anwender beschreibt den Ablauf so: „Entwicklung macht ein Release,
Compliance prüft die CRA-Readiness." Vor 8.0.0 war das eine Absprache und keine
Eigenschaft der Anwendung: ``RoleEnum.CRA_EDITOR`` erbte ``MODULE_PERMISSIONS['cra']``
samt ``CRA_APPROVE``, und die generische ``editor``-Rolle bekam über
``_ALL_WRITE`` ohnehin jedes Modulrecht — also auch jede Freigabe und jede
Signatur. Wer einen Nachweis erstellt, konnte ihn selbst freigeben.

Für einen Konformitätsnachweis ist genau das der Punkt: Eine Freigabe, die der
Ersteller selbst erteilen kann, belegt nichts. Diese Tests halten die drei
Bedingungen fest, die das ändern — getrennte Rechte, erzwungener Prüfschritt,
und der Einreicher ist nicht der Freigeber.
"""
from __future__ import annotations

import pytest

PROJ = 'pytest-release-1743'


# ── Rechte ──────────────────────────────────────────────────────────────────
def test_editor_darf_nicht_mehr_freigeben():
    from server.models.permission import Permission, resolve_permissions

    rechte = resolve_permissions(['cra_editor'])
    assert 'cra:write' in rechte, 'der Editor muss weiter schreiben dürfen'
    assert Permission.CRA_APPROVE.value not in rechte, (
        'CRA_APPROVE steckt noch in der Editor-Rolle — damit ist die '
        'Vier-Augen-Prüfung wirkungslos')


def test_generische_editor_rolle_vergibt_keine_freigaben():
    """Der stillste Teil des Fehlers: ``editor`` bekam über ``_ALL_WRITE``
    **alle** Modulrechte, also auch ``dsgvo:approve`` und ``dsgvo:sign``.

    Die Rollen GESCHAEFTSFUEHRER und DSB aus #1128 waren damit dekorativ.
    """
    from server.models.permission import SIGN_OFF_PERMISSIONS, resolve_permissions

    rechte = set(resolve_permissions(['editor']))
    treffer = {p.value for p in SIGN_OFF_PERMISSIONS} & rechte
    assert not treffer, f'die editor-Rolle vergibt noch Sign-off-Rechte: {treffer}'
    # Schreiben kann sie weiterhin — sonst wäre der Fix eine Störung.
    assert 'cra:write' in rechte and 'dsgvo:write' in rechte


def test_approver_darf_freigeben_aber_nicht_schreiben():
    from server.models.permission import resolve_permissions

    rechte = set(resolve_permissions(['cra_approver']))
    assert 'cra:approve' in rechte and 'cra:read' in rechte
    assert 'cra:write' not in rechte, (
        'ein Prüfer mit Schreibrecht kann den Gegenstand seiner Prüfung ändern')


def test_admin_behaelt_alles():
    """Sonst sperrt sich die Installation nach dem Update selbst aus."""
    from server.models.permission import Permission, resolve_permissions

    rechte = set(resolve_permissions(['admin']))
    assert Permission.CRA_APPROVE.value in rechte
    assert Permission.DSGVO_SIGN.value in rechte


def test_rolle_erscheint_im_katalog():
    """Die Benutzerverwaltung liest den Rollen-Katalog aus dem Enum — eine Rolle,
    die dort fehlt, kann niemand zuweisen."""
    from server.models.permission import ROLE_PERMISSIONS, RoleEnum

    assert RoleEnum.CRA_APPROVER in ROLE_PERMISSIONS
    assert RoleEnum('cra_approver') is RoleEnum.CRA_APPROVER


def test_approve_bleibt_im_modul_set():
    """Das Recht gehört fachlich weiter zu CRA — es wird nur nicht mehr
    implizit verteilt. Fehlte es im Modul-Set, verschwände es aus dem
    Rechte-Feintuning der Benutzerverwaltung."""
    from server.models.permission import MODULE_PERMISSIONS, Permission

    assert Permission.CRA_APPROVE in MODULE_PERMISSIONS['cra']


# ── Statusmaschine ──────────────────────────────────────────────────────────
@pytest.fixture
def vorgang(tmp_path):
    """Ein versionierter Vorgang mit abgeschlossenem Bewertungsweg."""
    from cra import konformitaet_db as kdb

    db = tmp_path / 'cra.sqlite'
    kdb.save_konformitaet(db, PROJ, {'release_version': '1.0.0', 'bewertungsweg': 'A',
                                     'bewertung_abgeschlossen': True})
    return db


def test_freigabe_ohne_einreichung_abgelehnt(vorgang):
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError, match='Einreichung'):
        kdb.freigeben(vorgang, PROJ, '1.0.0', von='compliance@example.com')


def test_einreicher_darf_nicht_selbst_freigeben(vorgang):
    """Der Kern der Vier-Augen-Prüfung. Beide Rollen zu haben genügt nicht —
    es muss eine zweite **Person** sein."""
    from cra import konformitaet_db as kdb

    kdb.einreichen(vorgang, PROJ, '1.0.0', von='dev@example.com')
    with pytest.raises(ValueError, match='zweite Person'):
        kdb.freigeben(vorgang, PROJ, '1.0.0', von='dev@example.com')
    # Groß-/Kleinschreibung darf die Prüfung nicht aushebeln.
    with pytest.raises(ValueError, match='zweite Person'):
        kdb.freigeben(vorgang, PROJ, '1.0.0', von='Dev@Example.com')


def test_durchlauf_einreichen_freigeben_veroeffentlichen(vorgang):
    from cra import konformitaet_db as kdb

    rec = kdb.einreichen(vorgang, PROJ, '1.0.0', von='dev@example.com')
    assert rec['freigabe_status'] == 'in_pruefung'
    assert rec['erstellt_von'] == 'dev@example.com' and rec['eingereicht_am']
    assert rec['gesperrt'] is True, (
        'nach dem Einreichen muss gesperrt sein — sonst prüft Compliance einen '
        'Stand, der sich unter der Hand noch ändert')

    rec = kdb.freigeben(vorgang, PROJ, '1.0.0', von='compliance@example.com')
    assert rec['freigabe_status'] == 'freigegeben'
    assert rec['geprueft_von'] == 'compliance@example.com' and rec['geprueft_am']

    rec = kdb.veroeffentlichen(vorgang, PROJ, '1.0.0')
    assert rec['freigabe_status'] == 'veroeffentlicht' and rec['veroeffentlicht_am']
    assert rec['gesperrt'] is True


def test_zurueckweisen_braucht_begruendung(vorgang):
    from cra import konformitaet_db as kdb

    kdb.einreichen(vorgang, PROJ, '1.0.0', von='dev@example.com')
    with pytest.raises(ValueError, match='Begründung'):
        kdb.zurueckweisen(vorgang, PROJ, '1.0.0', von='c@example.com', grund='nein')

    rec = kdb.zurueckweisen(vorgang, PROJ, '1.0.0', von='c@example.com',
                            grund='SBOM fehlt für diese Version')
    assert rec['freigabe_status'] == 'zurueckgewiesen'
    assert 'SBOM' in rec['zurueckweisung_grund']
    assert rec['gesperrt'] is False, 'nach der Zurückweisung muss nachgearbeitet werden können'

    # Erneutes Einreichen behält den ursprünglichen Einreicher: sonst könnte
    # sich der Ersteller durch ein zweites Einreichen selbst zum Freigeber machen.
    rec = kdb.einreichen(vorgang, PROJ, '1.0.0', von='compliance@example.com')
    assert rec['erstellt_von'] == 'dev@example.com'
    assert rec['zurueckweisung_grund'] == ''


def test_veroeffentlichen_setzt_freigabe_voraus(vorgang):
    from cra import konformitaet_db as kdb

    with pytest.raises(ValueError, match='Freigabe'):
        kdb.veroeffentlichen(vorgang, PROJ, '1.0.0')


def test_produkt_datensatz_behaelt_den_ablauf_aus_1220(tmp_path):
    """Der Datensatz ohne Release-Version ist der **Produkt**-Datensatz
    (Bewertungsweg, Notified Body, CE) — Phase 1, kein Release.

    Er behält den Sign-off aus #1220-A. Andernfalls müsste jede bestehende
    Installation ihren Produkt-Datensatz durch einen Prüfschritt schicken, den
    es für sie nie gab — ein Update, das laufende Nachweise anhält.
    """
    from cra import konformitaet_db as kdb

    db = tmp_path / 'cra.sqlite'
    kdb.save_konformitaet(db, PROJ, {'bewertungsweg': 'A',
                                     'bewertung_abgeschlossen': True})
    rec = kdb.freigeben(db, PROJ, '', von='gf@example.com')
    assert rec['freigabe_status'] == 'freigegeben'
    with pytest.raises(ValueError, match='Release-Version'):
        kdb.einreichen(db, PROJ, '', von='dev@example.com')
