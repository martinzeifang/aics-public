"""Der KI-Cloud-Schlüssel wird maskiert und verschlüsselt (#2001).

DER BEFUND
Er war das **einzige** Geheimnis der Konfiguration, das weder maskiert noch
at-rest verschlüsselt wurde — und das eine, das in der Oberfläche im Klartext
stehen konnte. Drei Dinge griffen ineinander:

1. ``_mask_sensitive`` maskierte ``integrations.github.token`` (#416) und
   ``integrations.portainer.api_key`` (#1534), aber **nicht**
   ``ai.cloud.api_key``. ``GET /api/admin/settings`` trug ihn im Klartext.
   Die Lücke stand im Quelltext: ``_deep_redact_secrets`` (#1509) begründet
   sich wörtlich damit, dass ``ai.cloud.api_key`` von ``_mask_sensitive`` nicht
   maskiert wird. Für das Support-Bundle wurde sie geschlossen, hier nicht.
2. Der Platzhalter am Feld verspricht „wird **verschlüsselt** in der Config
   gespeichert" — es gab kein ``_encrypt_ai_cloud_key_in_place``. Eine Zusage
   der Maske, die der Server nicht hielt (Klasse #1735/#1841).
3. ``_resolve_api_key`` nimmt einen Wert aus ``api_key_env`` als Schlüssel, wenn
   er kein Variablenname ist. Gut gemeint — nur ist ``api_key_env`` in der Maske
   ein **gewöhnliches Textfeld**. So ist auf einer Instanz ein Anthropic-Key
   offen auf dem Bildschirm gestanden, und **nichts hat widersprochen**: Der
   Lauf funktionierte, also sah alles richtig aus.

WAS HIER NICHT GEPRÜFT WIRD
Dass der tolerante Rückfall verschwindet. Er bleibt — ihn zu entfernen nähme
jeder Installation, die den Schlüssel heute so hinterlegt hat, sofort alle
KI-Funktionen. Er warnt jetzt und wird durch die Umlagerung gegenstandslos.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.api import admin as A

WURZEL = Path(__file__).resolve().parents[1]
SCHLUESSEL = "sk-ant-api03-" + "x" * 64


def _cfg(**cloud) -> dict:
    return {"ai": {"provider": "cloud", "cloud": dict(cloud)}}


# ── Was ist ein Variablenname, was ein Geheimnis ────────────────────────────

@pytest.mark.parametrize("wert,ist_name", [
    ("AI_CLOUD_API_KEY", True),
    ("_GEHEIM", True),
    ("A1", True),
    (SCHLUESSEL, False),          # Bindestriche → kein Name
    ("sk-ant-123", False),
    ("", False),
    (None, False),
    ("mit leerzeichen", False),
    ("1ABC", False),              # darf nicht mit einer Ziffer beginnen
])
def test_env_name_erkennung(wert, ist_name):
    assert A.ist_env_name(wert) is ist_name


def test_die_regel_ist_dieselbe_wie_im_provider():
    """Zwei Fassungen derselben Regel wären zwei Wahrheiten darüber, was ein
    Geheimnis ist — und die eine Seite maskierte dann, was die andere als Namen
    behandelt."""
    quelle = (WURZEL / "ai_compliance_suite" / "ai" / "providers" / "cloud.py"
              ).read_text(encoding="utf-8")
    assert r"[A-Za-z_][A-Za-z0-9_]*" in quelle, (
        "Der Provider prüft den Variablennamen nicht mehr mit diesem Muster — "
        "dann weicht `ist_env_name` davon ab (#2001).")


# ── Maskierung ──────────────────────────────────────────────────────────────

def test_der_schluessel_wird_maskiert():
    """Der Kern: Die Antwort des Lese-Endpunkts trägt ihn nicht mehr."""
    aus = A._mask_sensitive(_cfg(api_key=SCHLUESSEL, api_key_env=""))
    cloud = aus["ai"]["cloud"]
    assert cloud["api_key"] == "***"
    assert cloud["api_key_set"] is True
    assert SCHLUESSEL not in json.dumps(aus)


def test_ohne_schluessel_sagt_es_das_auch():
    """`***` allein ist nicht unterscheidbar — das Feld zeigt Punkte, auch wenn
    es leer ist. Deshalb `api_key_set`."""
    aus = A._mask_sensitive(_cfg(api_key="", api_key_env="AI_CLOUD_API_KEY"))
    assert aus["ai"]["cloud"]["api_key"] == "***"
    assert aus["ai"]["cloud"]["api_key_set"] is False


def test_ein_variablenname_bleibt_lesbar():
    """Er ist kein Geheimnis, und der Anwender muss ihn prüfen können."""
    aus = A._mask_sensitive(_cfg(api_key="", api_key_env="AI_CLOUD_API_KEY"))
    assert aus["ai"]["cloud"]["api_key_env"] == "AI_CLOUD_API_KEY"


def test_ein_schluessel_im_namensfeld_wird_maskiert():
    """Genau der Fall, der aufgefallen ist."""
    aus = A._mask_sensitive(_cfg(api_key="", api_key_env=SCHLUESSEL))
    assert aus["ai"]["cloud"]["api_key_env"] == "***"
    assert SCHLUESSEL not in json.dumps(aus)


def test_die_maskierung_laesst_die_nachbarn_unberuehrt():
    """Regressionsschutz für #416 und #1534."""
    cfg = {"integrations": {"github": {"token": "ghp_x"},
                            "portainer": {"api_key": "ptr_y"}},
           "auth": {"password_hash": "argon2$x"}}
    aus = A._mask_sensitive(cfg)
    assert aus["integrations"]["github"]["token"] == "***"
    assert aus["integrations"]["portainer"]["api_key"] == "***"
    assert aus["auth"]["password_hash"] == "***"
    assert "ghp_x" not in json.dumps(aus) and "ptr_y" not in json.dumps(aus)


def test_kein_geheimnis_ueberlebt_die_maskierung():
    """Breiter Wächter: Nach der Maskierung darf **kein** Feld, dessen Name auf
    ein Geheimnis deutet, noch einen Wert tragen — `api_key_set` ausgenommen,
    das ist ein Boolean und genau dafür da."""
    cfg = {"ai": {"provider": "cloud",
                  "cloud": {"api_key": SCHLUESSEL, "api_key_env": SCHLUESSEL}},
           "integrations": {"github": {"token": "ghp_x"},
                            "portainer": {"api_key": "ptr_y"}}}
    aus = A._mask_sensitive(cfg)

    treffer: list[str] = []

    def _geh(obj, pfad=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{pfad}.{k}" if pfad else str(k)
                if (isinstance(v, str) and v and v != "***"
                        and any(h in str(k).lower() for h in A._SECRET_KEY_HINTS)
                        and not str(k).endswith("_set")
                        and not str(k).endswith("_env")):
                    treffer.append(f"{p}={v[:12]}…")
                _geh(v, p)
        elif isinstance(obj, list):
            for x in obj:
                _geh(x, pfad)

    _geh(aus)
    assert not treffer, f"unmaskierte Geheimnisse: {treffer}"


# ── Umlagerung ──────────────────────────────────────────────────────────────

def test_ein_schluessel_wandert_aus_dem_namensfeld():
    cfg = _cfg(api_key="", api_key_env=SCHLUESSEL)
    assert A._verschiebe_ki_schluessel_in_place(cfg) is True
    assert cfg["ai"]["cloud"]["api_key"] == SCHLUESSEL
    assert cfg["ai"]["cloud"]["api_key_env"] == ""


def test_ein_variablenname_wird_nicht_verschoben():
    """Er ist das vorgesehene, sichere Verfahren — ihn wegzuräumen wäre falsch."""
    cfg = _cfg(api_key="", api_key_env="AI_CLOUD_API_KEY")
    assert A._verschiebe_ki_schluessel_in_place(cfg) is False
    assert cfg["ai"]["cloud"]["api_key_env"] == "AI_CLOUD_API_KEY"


def test_ein_vorhandener_direkter_schluessel_wird_nicht_ueberschrieben():
    """Der Provider nimmt ``api_key`` zuerst — ihn zu ersetzen würde den
    arbeitenden Schlüssel gegen einen alten tauschen."""
    cfg = _cfg(api_key="sk-neu", api_key_env=SCHLUESSEL)
    assert A._verschiebe_ki_schluessel_in_place(cfg) is True
    assert cfg["ai"]["cloud"]["api_key"] == "sk-neu"
    assert cfg["ai"]["cloud"]["api_key_env"] == ""


def test_umlagerung_ist_idempotent():
    cfg = _cfg(api_key="", api_key_env=SCHLUESSEL)
    A._verschiebe_ki_schluessel_in_place(cfg)
    assert A._verschiebe_ki_schluessel_in_place(cfg) is False


def test_umlagerung_vertraegt_fehlende_abschnitte():
    for cfg in ({}, {"ai": {}}, {"ai": {"cloud": None}}, {"ai": {"cloud": {}}}):
        assert A._verschiebe_ki_schluessel_in_place(cfg) is False


# ── Verschlüsselung at rest ─────────────────────────────────────────────────

def _mit_at_rest_key(monkeypatch):
    import base64
    import os
    monkeypatch.setenv("AICS_AT_REST_KEY",
                       base64.b64encode(os.urandom(32)).decode())


def test_der_schluessel_wird_verschluesselt_gespeichert(monkeypatch, app):
    """Die Zusage der Oberfläche („wird verschlüsselt gespeichert") gilt jetzt."""
    from shared.crypto_at_rest import decrypt_field, is_encrypted_field

    _mit_at_rest_key(monkeypatch)
    cfg = _cfg(api_key=SCHLUESSEL)
    with app.app_context():
        A._encrypt_ai_cloud_key_in_place(cfg)
    gespeichert = cfg["ai"]["cloud"]["api_key"]
    assert gespeichert != SCHLUESSEL
    assert is_encrypted_field(gespeichert)
    assert decrypt_field(gespeichert) == SCHLUESSEL


def test_verschluesseln_ist_idempotent(monkeypatch, app):
    _mit_at_rest_key(monkeypatch)
    cfg = _cfg(api_key=SCHLUESSEL)
    with app.app_context():
        A._encrypt_ai_cloud_key_in_place(cfg)
        einmal = cfg["ai"]["cloud"]["api_key"]
        A._encrypt_ai_cloud_key_in_place(cfg)
    assert cfg["ai"]["cloud"]["api_key"] == einmal


def test_der_provider_macht_ihn_wieder_auf(monkeypatch):
    from ai_compliance_suite.ai.providers.cloud import CloudProvider
    from shared.crypto_at_rest import encrypt_field

    _mit_at_rest_key(monkeypatch)
    verschluesselt = encrypt_field(SCHLUESSEL)
    p = CloudProvider({"base_url": "https://api.anthropic.com/v1",
                       "api_key": verschluesselt, "model": "x"})
    assert p._resolve_api_key() == SCHLUESSEL


def test_ein_unverschluesselter_altwert_funktioniert_weiter(monkeypatch):
    """Sonst verlöre jede Bestandsinstallation beim Update ihre KI-Funktionen."""
    from ai_compliance_suite.ai.providers.cloud import CloudProvider

    _mit_at_rest_key(monkeypatch)
    p = CloudProvider({"base_url": "https://api.anthropic.com/v1",
                       "api_key": SCHLUESSEL, "model": "x"})
    assert p._resolve_api_key() == SCHLUESSEL


def test_der_tolerante_rueckfall_bleibt(monkeypatch):
    """Er ist der Grund für den Befund — und ihn zu entfernen wäre schlimmer."""
    from ai_compliance_suite.ai.providers.cloud import CloudProvider

    p = CloudProvider({"base_url": "https://api.anthropic.com/v1",
                       "api_key": "", "api_key_env": SCHLUESSEL, "model": "x"})
    assert p._resolve_api_key() == SCHLUESSEL


def test_der_rueckfall_protokolliert_das(monkeypatch, caplog):
    """Stumm wäre er wieder der Weg, auf dem ein Geheimnis in ein Klartextfeld
    gerät, ohne dass jemand widerspricht."""
    import logging

    from ai_compliance_suite.ai.providers.cloud import CloudProvider

    p = CloudProvider({"base_url": "https://api.anthropic.com/v1",
                       "api_key": "", "api_key_env": SCHLUESSEL, "model": "x"})
    with caplog.at_level(logging.WARNING):
        p._resolve_api_key()
    text = caplog.text
    assert "api_key_env" in text
    assert SCHLUESSEL not in text, "Die Warnung darf den Schlüssel nicht echoen"


# ── Verdrahtung ─────────────────────────────────────────────────────────────

def test_der_speicherpfad_ruft_beide_schritte():
    """Umlagern **vor** Verschlüsseln — andernfalls bliebe ein im Namensfeld
    eingetragener Schlüssel unverschlüsselt im Klartextfeld stehen."""
    import inspect

    quelle = inspect.getsource(A.update_settings)
    i_v = quelle.find("_verschiebe_ki_schluessel_in_place")
    i_e = quelle.find("_encrypt_ai_cloud_key_in_place")
    assert i_v > 0, "die Umlagerung läuft beim Speichern nicht"
    assert i_e > 0, "die Verschlüsselung läuft beim Speichern nicht"
    assert i_v < i_e, "erst umlagern, dann verschlüsseln"


def test_api_key_set_wird_nicht_persistiert():
    """Ein reines Antwortfeld in der Konfiguration wäre Müll, der mitgespeichert
    und beim nächsten Lesen überschrieben wird."""
    assert "ai.cloud.api_key_set" in A._RESPONSE_ONLY_FIELDS
    d = {"ai": {"cloud": {"api_key_set": True, "model": "x"}}}
    A._strip_response_only(d)
    assert "api_key_set" not in d["ai"]["cloud"]
    assert d["ai"]["cloud"]["model"] == "x"


def test_ein_maskiertes_feld_ueberschreibt_nichts():
    """Das Formular schickt das ganze Objekt zurück. `***` muss raus, sonst
    wäre `***` der neue Schlüssel (die Falle aus #416)."""
    d = {"ai": {"cloud": {"api_key": "***", "api_key_env": "***", "model": "x"}}}
    A._strip_masked(d)
    assert "api_key" not in d["ai"]["cloud"]
    assert "api_key_env" not in d["ai"]["cloud"]
    assert d["ai"]["cloud"]["model"] == "x"


def test_der_modell_endpunkt_nimmt_kein_maskiertes_feld_als_schluessel():
    """**Verhalten, nicht Erzählung.**

    Der erste Anlauf dieses Tests suchte im Rumpf der Route nach der
    Zeichenkette ``'***'`` — und blieb grün, als der Schutz entfernt wurde, weil
    sie dort noch an anderer Stelle vorkam. Ein Wächter, der ein Vorkommen
    zählt, prüft nichts (die Lehre aus #1834). Deshalb liegt die Logik jetzt in
    ``formular_cloud_cfg`` und wird aufgerufen.
    """
    from server.api.ai_status import formular_cloud_cfg

    aus = formular_cloud_cfg({"api_key": "***", "api_key_env": "***",
                              "base_url": "***", "model": "***"})
    assert aus["api_key"] == "", "'***' darf nicht als Schlüssel durchgehen"
    assert aus["api_key_env"] == "AI_CLOUD_API_KEY"
    assert aus["base_url"] == "https://api.openai.com/v1"
    assert aus["model"] == ""

    # Und echte Werte kommen unverändert an.
    echt = formular_cloud_cfg({"api_key": SCHLUESSEL, "api_key_env": "MEIN_KEY",
                               "base_url": "https://api.anthropic.com/v1",
                               "model": "claude-sonnet-4-6"})
    assert echt["api_key"] == SCHLUESSEL
    assert echt["api_key_env"] == "MEIN_KEY"
    assert echt["model"] == "claude-sonnet-4-6"


def test_die_oberflaeche_zeigt_den_zustand_ohne_den_schluessel():
    """`api_key` ist ein Passwortfeld, aber das allein sagt nicht, **ob** einer
    hinterlegt ist — und das Namensfeld muss widersprechen, wenn dort ein
    Schlüssel steht."""
    quelle = (WURZEL / "frontend" / "src" / "components" / "SettingsDialog.vue"
              ).read_text(encoding="utf-8")
    assert "kiSchluesselHinterlegt" in quelle
    assert "api_key_set" in quelle
    assert "envFeldHaeltSchluessel" in quelle
    # Und das Feld bleibt ein Passwortfeld.
    assert 'type="password" v-model="form.ai.cloud.api_key"' in quelle
