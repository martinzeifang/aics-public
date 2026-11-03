"""DEMO-Lockerungen greifen nie in Produktion (#1737).

Beim Deploy von v7.4.6 fiel auf, dass Stack 50 (Produktiv) ``ENABLE_DEMO_USERS=true``
in der Env hatte. ``server/auth/users_db.py`` ist dagegen seit #744 fail-closed —
Demo-Benutzer entstehen in Produktion nicht. An **zwei weiteren** Stellen fehlte
derselbe Vorbehalt, und die zweite war ausnutzbar:

* ``password_policy.validate_password`` ließ für echte Benutzer 8-Zeichen-Passwörter
  ohne Zeichenklassen zu.
* ``POST /api/auth/password/forgot`` gab den **Reset-Token in der Antwort** zurück.
  Der Endpunkt ist unauthentifiziert: wer eine E-Mail-Adresse kannte, bekam einen
  gültigen Single-Use-Link und damit das Konto, Administratoren eingeschlossen.

Die Regel gehört an **eine** Stelle (``demo_mode_aktiv``), und diese Tests halten
alle drei Verwender daran.
"""
from __future__ import annotations

import pytest

from server.auth.password_policy import PasswordPolicyError, demo_mode_aktiv, validate_password


@pytest.fixture
def demo_prod(monkeypatch):
    """Die Fehlkonfiguration, die es real gab: Demo-Flag auf einem Prod-Stack."""
    monkeypatch.setenv("ENABLE_DEMO_USERS", "true")
    monkeypatch.setenv("FLASK_ENV", "production")


@pytest.fixture
def demo_dev(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_USERS", "true")
    monkeypatch.setenv("FLASK_ENV", "development")


def test_demo_mode_in_produktion_aus(demo_prod):
    assert demo_mode_aktiv() is False


def test_demo_mode_ausserhalb_produktion_an(demo_dev):
    assert demo_mode_aktiv() is True


def test_ohne_flag_immer_aus(monkeypatch):
    monkeypatch.delenv("ENABLE_DEMO_USERS", raising=False)
    monkeypatch.setenv("FLASK_ENV", "development")
    assert demo_mode_aktiv() is False


def test_passwort_policy_gilt_in_produktion(demo_prod):
    """8 Zeichen ohne Ziffer waren auf Produktiv erlaubt — jetzt nicht mehr."""
    with pytest.raises(PasswordPolicyError):
        validate_password("abcdefgh", email="user@example.com")


def test_passwort_policy_gelockert_in_der_demo(demo_dev):
    """Die Demo-Zugänge müssen weiter funktionieren."""
    validate_password("abcdefgh", email="user@example.com")


def test_reset_token_nicht_in_produktion_ausgeliefert(monkeypatch):
    """Der eigentliche Angriffspfad: Reset-Link aus einem offenen Endpunkt.

    Geprüft wird die Entscheidung im Endpunkt — ohne Flask-Kontext, denn es geht
    genau um die eine Bedingung, die vorher den rohen ENV-Wert las.
    """
    import inspect

    import server.api.auth as auth_api

    quelle = inspect.getsource(auth_api.password_forgot)
    assert "reset_url" in quelle
    # Die Zuweisung darf nur unter demo_mode_aktiv() stehen, nicht unter dem ENV-Wert.
    zeile = next(l for l in quelle.splitlines() if "reset_url'] =" in l)
    bedingung = quelle.split(zeile)[0].splitlines()[-2:]
    assert any("demo_mode_aktiv()" in b for b in bedingung), bedingung
    assert "ENABLE_DEMO_USERS" not in "".join(bedingung)


def test_public_config_meldet_was_die_anwendung_tut(monkeypatch):
    """Der Login zeigte auf Produktiv „Test-Umgebung"."""
    import inspect

    import server.api.auth as auth_api

    quelle = inspect.getsource(auth_api.public_config)
    assert "demo_mode_aktiv()" in quelle
    # Kein roher ENV-Vergleich mehr für das Demo-Flag.
    assert "getenv('ENABLE_DEMO_USERS'" not in quelle.replace('"', "'")
