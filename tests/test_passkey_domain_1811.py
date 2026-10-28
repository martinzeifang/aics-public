"""Ein Passkey gilt nur für seine Domain — und es muss einen Rückweg geben (#1811).

Aus dem Betrieb: Nach dem Umbenennen der Instanzen („das geht irgendwie nicht
mehr") verlangte ein Konto einen zweiten Faktor, den es nicht mehr erfüllen
konnte. Der Passkey war unter ``compliancesuite.c99781.intern`` registriert und
unter ``aics-test.290985.intern`` wertlos; das Kennwort allein reichte nicht.

Derselbe Fall entsteht beim Übernehmen einer Sicherung: Die Credentials wandern
mit, gelten aber auf der Zielinstallation nicht.

Zwei Lücken, beide hier festgehalten:

* Die Anwendung **wusste nicht**, für welche Domain ein Passkey gilt — die
  Tabelle hatte kein ``rp_id``. Sie konnte den Fall also nicht einmal benennen.
* Es gab **keinen Rückweg** ohne Datenbankzugriff. In einer gehosteten
  Installation hat ein Administrator den nicht.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from server.auth import users_db as u


# ── Die Anwendung merkt sich die Domain ─────────────────────────────────────

def test_tabelle_haelt_die_rp_id_fest():
    quelle = inspect.getsource(u)
    assert "rp_id" in quelle, "Die Credential-Tabelle vermerkt die Domain nicht"
    assert "ADD COLUMN" in quelle and "rp_id" in quelle, \
        "Für Bestandsinstallationen fehlt die Migration"


def test_registrierung_schreibt_die_rp_id():
    sig = inspect.signature(u.add_webauthn_credential)
    assert "rp_id" in sig.parameters, "Beim Anlegen wird die Domain nicht mitgegeben"
    api = Path("server/api/webauthn.py").read_text(encoding="utf-8")
    assert "rp_id=" in api, "Der Endpunkt übergibt die Domain nicht"


def test_altbestand_bleibt_unbekannt():
    """Geraten wird nichts: Ein Passkey von vor dieser Änderung hat keine
    vermerkte Domain, und „könnte passen" ist keine Grundlage für eine Warnung."""
    quelle = inspect.getsource(u._row_to_credential)
    assert "rp_id" in quelle
    assert "''" in quelle, "Fehlende Angabe muss leer sein, nicht erfunden"


# ── Der Hinweis beim Anmelden ───────────────────────────────────────────────

def test_login_nennt_die_abweichende_domain():
    quelle = Path("server/api/auth.py").read_text(encoding="utf-8")
    assert "_passkey_domain_hinweis" in quelle, "Kein Hinweis im Login-Pfad"
    assert "passkey_domain_hinweis" in quelle, "Die Antwort trägt den Hinweis nicht"

    helfer = quelle[quelle.index("def _passkey_domain_hinweis"):][:1800]
    assert "if not bekannt or any(" in helfer, \
        "Ohne vermerkte Domain darf kein Hinweis erscheinen"
    assert "except Exception" in helfer, \
        "Ein Hinweis darf die Anmeldung nicht verhindern"


# ── Der Rückweg ─────────────────────────────────────────────────────────────

def test_zweiter_faktor_laesst_sich_zuruecksetzen():
    assert hasattr(u, "zweiten_faktor_zuruecksetzen"), "Kein Rückweg vorhanden"
    quelle = inspect.getsource(u.zweiten_faktor_zuruecksetzen)
    assert "DELETE FROM webauthn_credentials" in quelle, "Passkeys bleiben stehen"
    assert "totp_enabled=0" in quelle, "TOTP bleibt aktiv"
    assert "bump_token_version" in quelle, \
        "Offene Sitzungen müssen enden — sonst gilt der entfernte Faktor weiter"


def test_reset_ist_admin_pflichtig_und_wird_protokolliert():
    quelle = Path("server/api/admin.py").read_text(encoding="utf-8")
    assert "/users/<user_id>/mfa/reset" in quelle, "Kein Endpunkt"
    stelle = quelle[quelle.index("/users/<user_id>/mfa/reset"):][:1500]
    assert "admin:users" in stelle, "Der Endpunkt ist nicht berechtigungspflichtig"
    assert "admin.user.mfa_reset" in stelle, \
        "Wer einem Konto den zweiten Faktor nimmt, gehört in den Revisionspfad"
    assert "ziel_email" in stelle, "Der Eintrag nennt das betroffene Konto nicht"


def test_der_rueckweg_hat_einen_knopf():
    """Ein Endpunkt allein ist kein Rückweg.

    Das Issue nennt zwei Lücken: den fehlenden Hinweis und den fehlenden
    Rückweg. Letzterer besteht für einen Administrator ohne Shell erst, wenn er
    ihn in der Benutzerverwaltung findet — ohne Knopf bliebe er auf dem
    Datenbankzugriff sitzen, den er in einer gehosteten Installation nicht hat.
    """
    view = Path("frontend/src/views/admin/AdminUsersView.vue").read_text(encoding="utf-8")
    assert "onMfaReset" in view, "Kein Knopf in der Benutzerverwaltung"
    assert "/mfa/reset" in view, "Der Knopf ruft den Endpunkt nicht"

    stelle = view[view.index("const onMfaReset"):][:1200]
    assert "confirm(" in stelle, \
        "Das Absenken des Schutzniveaus darf nicht ohne Rückfrage passieren"
    for wort in ("Passkeys", "Kennwort", "Revisionspfad"):
        assert wort in stelle, f"Die Rückfrage nennt '{wort}' nicht"
