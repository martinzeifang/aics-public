"""Bewegliche Image-Tags und der Deploy-Weg (#1733).

Ein App-Redeploy mit ``pullImage: true`` zieht **jedes** Image des Stacks neu. Bei
Stack 45 haengt daran ``ollama/ollama`` (3,2 GB) — der Deploy von v7.4.6 stand dadurch
35 Minuten. Stiller und schwerer: mitgezogen werden auch ``postgres`` und ``gotenberg``,
ein App-Update kann also ungewollt die Datenbank anheben.

Diese Tests halten die zwei Entscheidungen fest, die das verhindern:

1. Kein bewegliches ``:latest`` in ``docker-compose.yml`` (die Entscheidung aus #1188,
   die bei Ollama nie angewandt wurde).
2. Die Pin-Liste im Deploy-Skript ist mit der compose-Datei deckungsgleich — sie ist
   eine zweite Kopie derselben Liste, und genau diese Fehlerklasse (eine Liste an
   mehreren Orten) hat uns schon die Dockerfile-``COPY``-Liste und die
   Vorlagen-Verdrahtung gekostet.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
COMPOSE = REPO / "docker-compose.yml"

_IMAGE = re.compile(r"^\s*image:\s*(?P<ref>\S+)\s*(?:#.*)?$", re.MULTILINE)

# Die eigenen Images sind hier bewusst ausgenommen: ihr Tag kommt aus
# ``${AICS_IMAGE_TAG}``, den jeder Deploy explizit auf die Release-Version setzt. Der
# Rueckfall auf ``latest`` ist fuer ein ``docker compose up`` beim Kunden gedacht.
# Gepruefte Invariante ist also: **Fremd-Images muessen gepinnt sein** — nur die zieht
# ein Redeploy ungefragt auf einen neuen Stand.
EIGENE = "ghcr.io/martinzeifang/"


def _fremde_refs() -> list[str]:
    """Alle ``image:``-Werte mit aufgeloesten ``${VAR:-default}``-Vorgaben."""
    refs = []
    for m in _IMAGE.finditer(COMPOSE.read_text()):
        ref = re.sub(r"\$\{[A-Z_]+:-([^}]*)\}", r"\1", m.group("ref"))
        if EIGENE not in ref:
            refs.append(ref)
    return refs


def test_kein_latest_bei_fremd_images():
    """``:latest`` macht jeden Deploy zum Download und jeden Stand unreproduzierbar."""
    beweglich = [r for r in _fremde_refs() if r.endswith(":latest")]
    assert not beweglich, (
        f"bewegliche Tags in docker-compose.yml: {beweglich} — jeder Redeploy zieht "
        f"sie neu (#1733)")


def test_jedes_fremd_image_hat_einen_tag():
    """Ohne Tag gilt implizit ``:latest`` — dasselbe Problem, nur unsichtbar."""
    ohne = [r for r in _fremde_refs() if ":" not in r.rsplit("/", 1)[-1]]
    assert not ohne, f"Image ohne Tag (= implizit latest): {ohne}"


def test_ollama_ist_gepinnt_und_ueberschreibbar():
    """Die Version muss bewusst angehoben werden, nicht vom Registry-Stand abhaengen."""
    text = COMPOSE.read_text()
    m = re.search(r"image:\s*\$\{AICS_OLLAMA_IMAGE:-ollama/ollama:([\w.\-]+)\}", text)
    assert m, ("ollama muss als ${AICS_OLLAMA_IMAGE:-ollama/ollama:<version>} stehen "
               "(pinnen + ueberschreibbar wie AICS_IMAGE)")
    assert m.group(1) != "latest"


def test_deploy_skript_pins_passen_zur_compose():
    """Zwei Kopien derselben Liste laufen auseinander — hier faellt das auf."""
    from scripts.ops.portainer_redeploy import PINS

    text = COMPOSE.read_text()
    for name, version in PINS.items():
        treffer = re.findall(
            r"image:\s*(?:\$\{[A-Z_]+:-)?" + re.escape(name) + r":([\w.\-]+)", text)
        assert treffer, f"{name} steht nicht in docker-compose.yml, ist aber gepinnt"
        assert all(t == version for t in treffer), (
            f"{name}: Deploy-Skript pinnt {version}, compose nutzt {set(treffer)}")


def test_pin_transform_ist_idempotent_und_zieht_latest_nach():
    """Die Stack-Datei im Portainer ist eine Kopie — sie driftet (dort stand noch
    ``alpine:latest``, obwohl #1188 im Repo gepinnt hatte)."""
    from scripts.ops.portainer_redeploy import PINS, pin_stack_datei

    roh = ("services:\n"
           "  ollama:\n"
           "    image: ollama/ollama:latest\n"
           "  helper:\n"
           "    image: alpine:latest\n")
    neu, aenderungen = pin_stack_datei(roh)
    assert ":latest" not in neu, neu
    assert len(aenderungen) == 2, aenderungen
    assert f"ollama/ollama:{PINS['ollama/ollama']}" in neu

    nochmal, keine = pin_stack_datei(neu)
    assert nochmal == neu and keine == [], "Transform ist nicht idempotent"


def test_pin_transform_laesst_override_zeilen_in_ruhe():
    """Ein bewusstes ``${VAR:-...}``-Override im Stack darf nicht ueberfahren werden."""
    from scripts.ops.portainer_redeploy import pin_stack_datei

    roh = "    image: ${AICS_OLLAMA_IMAGE:-ollama/ollama:0.1.2}\n"
    neu, aenderungen = pin_stack_datei(roh)
    assert neu == roh and aenderungen == []


def test_feste_images_fuer_praesenz_pruefung():
    """Mit ``pullImage: false`` muss jedes feste Image schon auf dem Host liegen.

    Der Fall, der das noetig macht: ``--pin-images`` schreibt ``alpine:3.20`` in die
    Stack-Datei, auf dem Host lag aber nur ``alpine:latest`` — der Init-Dienst waere
    ohne Image gestartet. ``${VAR}``-Zeilen bleiben aussen vor; die AICS-Images werden
    eigens gezogen, ihr Tag steht in der Stack-Env, nicht in der Datei.
    """
    from scripts.ops.portainer_redeploy import feste_images

    datei = ("services:\n"
             "  web:\n"
             "    image: ${AICS_IMAGE:-ghcr.io/x/y}:${AICS_IMAGE_TAG:-latest}\n"
             "  redis:\n"
             "    image: redis:7-alpine\n"
             "  helper:\n"
             "    image: alpine:3.20\n"
             "  doppelt:\n"
             "    image: redis:7-alpine\n"
             "  mit_kommentar:\n"
             "    image: gotenberg/gotenberg:8  # bewegliches Major-Tag\n")
    assert feste_images(datei) == ["redis:7-alpine", "alpine:3.20",
                                   "gotenberg/gotenberg:8"]


def test_container_erkennung_trennt_die_stacks():
    """Auf docker02 laufen vier Stacks mit ``*_web``/``*_nginx`` aus denselben Images.

    Ein Name-Match (``aics_web``) traf auf Demo (``aicsdemo_web``) gar nichts und auf
    docker02 beinahe den Prod-Stack. Unterschieden wird ueber das Compose-Projekt.
    """
    from scripts.ops.portainer_redeploy import (NGINX_IMAGE, Portainer,
                                                WEB_IMAGE, aics_container)

    antwort = [
        {"Names": ["/aicsdemo_web"], "Image": f"{WEB_IMAGE}:7.4.6", "State": "running",
         "Labels": {"com.docker.compose.project": "aics-demo"}},
        {"Names": ["/aicsdemo_nginx"], "Image": f"{NGINX_IMAGE}:7.4.6", "State": "running",
         "Labels": {"com.docker.compose.project": "aics-demo"}},
        {"Names": ["/aics_web"], "Image": f"{WEB_IMAGE}:7.4.5", "State": "running",
         "Labels": {"com.docker.compose.project": "ai-compliance-suite"}},
        {"Names": ["/aicsdemo_postgres"], "Image": "postgres:16-alpine", "State": "running",
         "Labels": {"com.docker.compose.project": "aics-demo"}},
    ]
    p = Portainer("https://example.invalid/api", "ptr_test")
    p.container = lambda endpoint: antwort  # type: ignore[method-assign]

    demo = aics_container(p, 3, "aics-demo")
    assert [n for n, _, _ in demo] == ["aicsdemo_nginx", "aicsdemo_web"], demo
    assert [n for n, _, _ in aics_container(p, 3, "ai-compliance-suite")] == ["aics_web"]
    assert aics_container(p, 3, "gibt-es-nicht") == []


def test_basis_url_wird_auf_api_normalisiert():
    """``PORTAINER_URL`` steht in der Umgebung ohne ``/api`` — sonst 404 ueberall."""
    from scripts.ops.portainer_redeploy import _basis

    assert _basis("https://portainer.example.com:9443") == "https://portainer.example.com:9443/api"
    assert _basis("https://docker01:9443/api/") == "https://docker01:9443/api"
    assert _basis("https://docker01:9443/api") == "https://docker01:9443/api"


def test_lizenz_stack_ist_gesperrt():
    """Stack 51 ist ein anderes Produkt auf demselben Portainer (aics-licensing).

    Ein Zahlendreher im ``--stack`` wuerde dort eine fremde Anwendung neu deployen.
    """
    from scripts.ops.portainer_redeploy import (DeployFehler, Portainer,
                                                VERBOTENE_STACKS, redeploy)

    assert 51 in VERBOTENE_STACKS
    p = Portainer("https://example.invalid/api", "ptr_test")
    with pytest.raises(DeployFehler, match="aics-licensing"):
        redeploy(p, 51, 3, "7.4.6")
