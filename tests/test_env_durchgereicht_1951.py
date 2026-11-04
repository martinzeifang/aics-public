"""#1951 — Was der Code liest, muss der Container bekommen.

Gemeldet beim Einschalten der Verschlüsselung aus #1917: Der Schlüssel stand in
Portainers Stack-Env, der Container meldete ``FEHLT``, und die nächtliche
Sicherung lief weiter — unverschlüsselt. Ursache war **keine** Fehlbedienung:
``AICS_BACKUP_KEY`` fehlte in ``docker-compose.yml`` unter ``environment:``.

Portainers Stack-Env ist die ``.env`` für die **compose-Interpolation**. In den
Container kommt ein Wert nur über eine ``environment:``-Zeile. Fehlt sie, wird
der Container bei einer reinen Env-Änderung nicht einmal neu erstellt — der
Redeploy antwortet trotzdem mit HTTP 200. Genau diese Falle steht im Compose
seit #1738 an ``AICS_LICENSE_SERVER_URL`` kommentiert; sie traf hier eine
zweite Variable, und zwar leiser: Dort scheitert die Lizenzbestätigung sichtbar,
hier entstand ein Archiv, das für verschlüsselt gehalten wurde. Beim
Sicherungsschlüssel gibt es dazu **ausdrücklich keinen Rückfall**, also war die
Verschlüsselung in keiner Installation einschaltbar.

Das ist die Spiegel-Listen-Klasse aus #1731/#1735 über eine Dateigrenze hinweg:
Der Name entsteht im Python-Code, entschieden wird in einer YAML-Datei, und
nichts hält beide gegeneinander. Darum dieser Wächter — mit **Warteliste je mit
Grund**, denn eine Ausnahmeliste ohne Begründung wird zum Teppich
(#1805/#1834).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import yaml

_WURZEL = Path(__file__).resolve().parents[1]
_COMPOSE = _WURZEL / "docker-compose.yml"
_QUELLEN = ("shared", "server", "ai_compliance_suite")

#: Namen, die der Code liest und die **nicht** in die Container-Umgebung
#: gehören. Je Eintrag der Grund — wer hier etwas hinzufügt, muss ihn nennen.
_WARTELISTE: dict[str, str] = {
    "AICS_IMAGE_TAG":
        "wird von compose selbst für den Image-Tag interpoliert, ist keine "
        "Angabe für den laufenden Prozess",
    "AICS_UPDATE_CHANNEL_DEV":
        "#1908 ausdrücklich nicht durchgereicht — der Kanal `dev` schaltet die "
        "Herkunftsprüfung ab und muss von Hand am Container stehen, nicht per "
        "Stack-Variable erreichbar sein",
    "AICS_CONFIG_HMAC_KEY":
        "hat einen Rückfall auf AICS_AT_REST_KEY → JWT_SECRET_KEY "
        "(shared/config_io.py); ein eigener Wert ist Sonderfall",
    "AICS_DEV_PGDATA":
        "nur für den lokalen Entwicklungs-Postgres",
    "AICS_TRACK_SCHEMAS":
        "nur für den Test-Harness (Schema-Isolierung)",
    "AICS_DATA_DIR":
        "im Image fest auf /app/data; die Ablage bestimmen die Volumes",
    "AICS_CONFIG_ENFORCE_PERMS":
        "Vorgabe an, Abschalten ist bewusst kein Betriebsschalter",
    "AICS_INTEGRITY_ENFORCE":
        "Vorgabe an, Abschalten ist bewusst kein Betriebsschalter",
    "AICS_DDL_LOCK_TIMEOUT":
        "Feinstellung des Schema-Warmups, in der Installation nie gebraucht",
    "AICS_WARM_SCHEMAS":
        "Feinstellung des Schema-Warmups, in der Installation nie gebraucht",
}


def _gelesene_namen() -> set[str]:
    """Jeder ``"AICS_…"``-String im Produktionscode, ohne Kommentarzeilen.

    Das Programm prüfen, nicht die Erzählung (#1834/#1867/#1878/#1903): Ein
    Name, der nur im Dateikopf erklärt wird, ist keine Leseabhängigkeit.
    """
    muster = re.compile(r'"(AICS_[A-Z0-9_]+)"')
    namen: set[str] = set()
    for ordner in _QUELLEN:
        for pfad in (_WURZEL / ordner).rglob("*.py"):
            for zeile in pfad.read_text(encoding="utf-8").splitlines():
                ohne = zeile.split("#", 1)[0]
                namen.update(muster.findall(ohne))
    return namen


def _web_umgebung() -> dict[str, str]:
    doc = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    eintraege = doc["services"]["web"]["environment"]
    umgebung: dict[str, str] = {}
    for e in eintraege:
        name, _, wert = str(e).partition("=")
        umgebung[name.strip()] = wert
    return umgebung


# ── Der gemeldete Fall ───────────────────────────────────────────────────────

def test_der_sicherungsschluessel_kommt_im_container_an() -> None:
    """Der Name kommt aus dem Modul, nicht aus diesem Test.

    Sonst prüft der Wächter nach einer Umbenennung die falsche Wahrheit.
    """
    from shared.backup.verschluesselung import SCHLUESSEL_ENV

    umgebung = _web_umgebung()
    assert SCHLUESSEL_ENV in umgebung, (
        f"{SCHLUESSEL_ENV} fehlt in docker-compose.yml unter services.web."
        f"environment. Portainers Stack-Env erreicht den Container nur über "
        f"diese Zeile — ohne sie entsteht die Sicherung unverschlüsselt, "
        f"obwohl der Schlüssel gesetzt scheint, und der Redeploy meldet Erfolg."
    )
    assert umgebung[SCHLUESSEL_ENV] == "${%s:-}" % SCHLUESSEL_ENV, (
        "Der Wert muss aus der Stack-Variable interpoliert werden und leer "
        "bleiben dürfen (leer = unverändertes Verhalten)."
    )


def test_ohne_schluessel_in_der_umgebung_gilt_er_als_nicht_vorhanden(monkeypatch) -> None:
    """Die Zusage „kein Rückfall" hält — das ist der Grund für den Test oben."""
    from shared.backup import verschluesselung

    monkeypatch.delenv(verschluesselung.SCHLUESSEL_ENV, raising=False)
    monkeypatch.setenv("AICS_AT_REST_KEY", "nicht-der-sicherungsschluessel")
    monkeypatch.setenv("JWT_SECRET_KEY", "auch-nicht")
    assert verschluesselung.schluessel_vorhanden() is False


# ── Die Klasse ───────────────────────────────────────────────────────────────

def test_jeder_gelesene_name_ist_durchgereicht_oder_begruendet() -> None:
    umgebung = _web_umgebung()
    offen = {
        n for n in _gelesene_namen()
        if n not in umgebung and n not in _WARTELISTE
    }
    assert not offen, (
        "Diese Namen liest der Code, der Container bekommt sie aber nicht: "
        f"{sorted(offen)}. Entweder eine environment:-Zeile in "
        "docker-compose.yml ergänzen oder in _WARTELISTE mit Grund aufnehmen."
    )


def test_die_warteliste_hat_keine_toten_eintraege() -> None:
    """Eine Warteliste, die veraltet, verdeckt den nächsten echten Befund."""
    gelesen = _gelesene_namen()
    umgebung = _web_umgebung()
    tot = {n for n in _WARTELISTE if n not in gelesen}
    doppelt = {n for n in _WARTELISTE if n in umgebung}
    assert not tot, f"Wird nicht mehr gelesen, gehört aus der Liste: {sorted(tot)}"
    assert not doppelt, (
        f"Steht in der Warteliste UND im Compose — ein Widerspruch, der "
        f"erklärt werden muss: {sorted(doppelt)}"
    )


@pytest.mark.parametrize("name", sorted(_WARTELISTE))
def test_jede_ausnahme_nennt_einen_grund(name: str) -> None:
    assert len(_WARTELISTE[name].strip()) >= 20
