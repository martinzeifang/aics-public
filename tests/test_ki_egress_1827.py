"""Cloud-Egress wird am Ergebnis geprüft, nicht am Bruchstück (#1827).

Der gemeldete Fall: Auf der Demo-Instanz ließ sich der KI-Provider nicht auf
Cloud umstellen — „Cloud-Provider braucht allow_data_egress=true". Daran war
zweierlei falsch.

Die Prüfung las ``data['ai']['cloud']`` aus dem **Request**, gespeichert wird
aber über einen Tiefen-Merge gegen die bestehende Konfiguration. Ein
Teil-Update, das allein den Provider umstellt, fiel damit durch, obwohl der
Datenausgang längst erlaubt war; und über eine Sicherheitsfrage entschied, was
der Client zufällig mitschickte, statt der Zustand, der anschließend gilt.
Nebenbei lief die SSRF-Prüfung der Base-URL (#741) gar nicht, wenn die Adresse
schon gespeichert war und nicht mitgeschickt wurde.

Zum anderen nannte die Meldung einen Konfigurationsschlüssel. In der Oberfläche
heißt das Feld anders — eine Wegbeschreibung auf ein Wort, das dort nicht
vorkommt, ist schlechter als keine (die Lehre aus #1805).
"""
from __future__ import annotations

import inspect

import pytest

from server.api.admin import EGRESS_HAKEN, _pruefe_ki_egress, update_settings


def _cfg(provider="cloud", egress=True, base_url="https://api.openai.com/v1"):
    return {"ai": {"provider": provider,
                   "cloud": {"allow_data_egress": egress, "base_url": base_url}}}


# ── Die Regel selbst ────────────────────────────────────────────────────────

def test_cloud_mit_erlaubnis_geht_durch():
    assert _pruefe_ki_egress(_cfg()) is None


def test_cloud_ohne_erlaubnis_wird_abgewiesen():
    fehler = _pruefe_ki_egress(_cfg(egress=False))
    assert fehler is not None
    assert fehler["code"] == "cloud-egress-nicht-erlaubt"


def test_anderer_provider_wird_nicht_geprueft():
    """Ohne Cloud gibt es keinen Datenausgang zu erlauben."""
    assert _pruefe_ki_egress(_cfg(provider="on_prem", egress=False)) is None
    assert _pruefe_ki_egress({"ai": {"provider": "none"}}) is None


def test_meldung_nennt_die_handlung_und_nicht_den_schluessel():
    """Der Anwender sucht in der Oberfläche nach einer Beschriftung."""
    text = _pruefe_ki_egress(_cfg(egress=False))["error"]
    assert EGRESS_HAKEN in text
    assert "allow_data_egress" not in text
    # Der zweite Weg heraus gehört in die Meldung: Wer den Datenausgang NICHT
    # erlauben will, muss den Provider wechseln können.
    assert "anderen" in text and "Provider" in text
    # Und der Preis der Zustimmung wird benannt, nicht verschwiegen.
    assert "verlassen" in text


def test_base_url_wird_auch_geprueft():
    fehler = _pruefe_ki_egress(_cfg(base_url="http://aics.example.com/v1"))
    assert fehler is not None
    assert fehler["code"] == "cloud-base-url-unzulaessig"


def test_leere_base_url_blockiert_nicht():
    """Ohne Adresse gibt es nichts zu prüfen — die Pflicht meldet der Provider."""
    assert _pruefe_ki_egress(_cfg(base_url="")) is None


@pytest.mark.parametrize("cfg", [{}, {"ai": {}}, {"ai": {"cloud": {}}}])
def test_unvollstaendige_konfiguration_bricht_nicht(cfg):
    """Eine frische Installation hat den Block noch gar nicht."""
    assert _pruefe_ki_egress(cfg) is None


# ── Die Verdrahtung ─────────────────────────────────────────────────────────

def test_endpunkt_prueft_das_ergebnis_des_merges():
    """Wächter: Die Prüfung muss NACH dem Zusammenführen laufen.

    Stünde sie wieder davor, wäre der gemeldete Fehler zurück — und zwar
    lautlos, weil der Einstellungsdialog ohnehin das ganze Formular schickt und
    davon nichts merkt. Nur andere Aufrufer liefen hinein.
    """
    quelle = inspect.getsource(update_settings)
    assert "_pruefe_ki_egress(merged)" in quelle, \
        "Der Endpunkt muss die zusammengeführte Konfiguration prüfen"
    assert quelle.index("merged = _deep_merge") < quelle.index("_pruefe_ki_egress"), \
        "Die Prüfung steht vor dem Merge — dann prüft sie wieder das Bruchstück"
    assert "allow_data_egress" not in quelle, \
        "Die Regel gehört in _pruefe_ki_egress, nicht ein zweites Mal hierher"
