#!/usr/bin/env python3
"""Redeploy eines AICS-Stacks auf eine Version — ohne Fremd-Images mitzuziehen (#1733).

WARUM NICHT EINFACH ``pullImage: true``
Portainers "Pull and redeploy" zieht **jedes** Image des Stacks neu, nicht nur die
beiden AICS-Images. Bei Stack 45 haengt daran ``ollama/ollama`` mit 3,2 GB; ein
App-Deploy, der in Sekunden durch waere, stand damit 35 Minuten auf ``Status=3``
(beobachtet bei v7.4.6). Schwerer wiegt das Stille daran: mitgezogen werden auch
``postgres:16-alpine`` und ``gotenberg:8`` — ein App-Update kann so ungewollt die
Datenbank auf einen neuen 16.x-Stand heben, ohne dass das irgendwo als
Datenbank-Update auftaucht.

Dieses Skript zieht deshalb **nur** die beiden AICS-Images in der Zielversion vor und
deployt dann mit ``pullImage: false``. Dass die Images danach wirklich auf dem Endpoint
liegen, wird geprueft: mit ``pullImage: false`` wuerde ein fehlgeschlagener Pull sonst
einen Dienst ohne Image starten lassen — der Stack wird dann nicht alt, sondern tot.

Aufruf::

    export PORTAINER_API_KEY=ptr_...
    python3 scripts/ops/portainer_redeploy.py --stack 45 --endpoint 2 --tag 7.4.6
    python3 scripts/ops/portainer_redeploy.py --stack 50 --endpoint 3 --tag 7.4.6 --pin-images

``--pin-images`` zieht zusaetzlich die beweglichen Fremd-Tags in der **Stack-Datei** auf
die im Repo gepinnten Werte nach (Ollama, alpine). Das ist noetig, weil ein
Tag-Redeploy die Stack-Datei nicht anfasst: #1188 hat ``alpine`` im Repo gepinnt, in
den Live-Stacks stand weiter ``alpine:latest``.

HERKUNFT DER IMAGES (#1719/E4)
Release-Images kommen aus dem **oeffentlichen** Repo ``aics-public``; das private baut
nur noch Dev-Tags (``:main``, ``:sha-…``). Vor dem Deploy wird deshalb geprueft, aus
welchem Quellbaum das gezogene Image gebaut wurde — sonst waere die Umstellung nicht
nachweisbar. Ein Dev-Image deployt man bewusst mit ``--quelle privat``, jedes andere
mit ``--quelle beliebig``.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _basis(roh: str) -> str:
    """Normalisiert die Portainer-Basis-URL auf ``…/api``.

    ``PORTAINER_URL`` steht in manchen Umgebungen ohne ``/api`` (z. B.
    ``https://portainer.example.com:9443``). Ohne diese Normalisierung antwortet jeder
    Aufruf mit ``404 page not found`` — ein Fehlerbild, das nach „Stack gibt es
    nicht" aussieht und in die falsche Richtung schickt.
    """
    b = roh.rstrip("/")
    return b if b.endswith("/api") else f"{b}/api"


DEFAULT_BASE = _basis(os.environ.get("PORTAINER_URL", "https://docker01:9443"))

WEB_IMAGE = "ghcr.io/martinzeifang/ai_compliance_suite"
NGINX_IMAGE = "ghcr.io/martinzeifang/aics-nginx"

# Seit #1719/E4 baut und veroeffentlicht das **oeffentliche** Repo die
# Release-Images; das private pusht nur noch Dev-Tags (``:main``, ``:sha-…``).
# Beide Workflows schreiben aber in dieselben zwei GHCR-Pakete, und am Tag
# ``7.4.8`` ist nicht zu erkennen, wer ihn gesetzt hat. Das Label
# ``org.opencontainers.image.source`` ist der einzige Beleg am Artefakt selbst.
# Ohne diese Pruefung waere die Umstellung nicht nachweisbar: ein versehentlich
# privat gebautes Image deployt sich genauso klaglos, und wir testen dann ein
# anderes Artefakt als der Kunde bekommt — genau das sollte aufhoeren.
QUELL_LABEL = "org.opencontainers.image.source"
ERWARTETE_QUELLE = "https://github.com/martinzeifang/aics-public"

# Gepinnte Fremd-Images — identisch zu docker-compose.yml. Eine zweite Liste ist hier
# unvermeidlich (die Live-Stack-Dateien sind Kopien), deshalb steht die Begruendung an
# beiden Stellen und ``tests/test_ollama_pin_1733.py`` haelt sie gleich.
PINS: dict[str, str] = {
    "ollama/ollama": "0.40.8",
    "alpine": "3.20",
}

# Stack 51 ist ``aics-licensing`` — ein anderes Produkt auf demselben Portainer.
# Ein Zahlendreher im ``--stack`` wuerde dort eine fremde Anwendung neu deployen.
VERBOTENE_STACKS = {51}


class DeployFehler(RuntimeError):
    pass


def _key(explizit: str | None) -> str:
    k = explizit or os.environ.get("PORTAINER_API_KEY", "")
    if not k:
        raise DeployFehler(
            "Kein API-Key: PORTAINER_API_KEY setzen oder --key uebergeben.")
    return k


class Portainer:
    def __init__(self, base: str, key: str, verify: bool = False) -> None:
        self.base = base.rstrip("/")
        self.h = {"X-API-Key": key}
        self.verify = verify

    def get(self, pfad: str, **kw: Any) -> requests.Response:
        return requests.get(f"{self.base}{pfad}", headers=self.h,
                            verify=self.verify, timeout=60, **kw)

    def post(self, pfad: str, **kw: Any) -> requests.Response:
        return requests.post(f"{self.base}{pfad}", headers=self.h,
                             verify=self.verify, timeout=1800, **kw)

    def put(self, pfad: str, **kw: Any) -> requests.Response:
        return requests.put(f"{self.base}{pfad}", headers=self.h,
                            verify=self.verify, timeout=1800, **kw)

    # ---- Images ----------------------------------------------------------
    def image_vorhanden(self, endpoint: int, ref: str) -> bool:
        r = self.get(f"/endpoints/{endpoint}/docker/images/{ref}/json")
        return r.status_code == 200

    def image_quelle(self, endpoint: int, ref: str) -> str:
        """``org.opencontainers.image.source`` des Images — leer wenn unbekannt."""
        r = self.get(f"/endpoints/{endpoint}/docker/images/{ref}/json")
        if r.status_code != 200:
            return ""
        labels = ((r.json().get("Config") or {}).get("Labels") or {})
        return labels.get(QUELL_LABEL, "")

    def image_ziehen(self, endpoint: int, image: str, tag: str) -> None:
        r = self.post(f"/endpoints/{endpoint}/docker/images/create",
                      params={"fromImage": image, "tag": tag})
        if r.status_code >= 300:
            raise DeployFehler(f"Pull {image}:{tag} fehlgeschlagen: "
                               f"HTTP {r.status_code} {r.text[:200]}")

    # ---- Stack -----------------------------------------------------------
    def stack(self, stack_id: int) -> dict[str, Any]:
        r = self.get(f"/stacks/{stack_id}")
        if r.status_code != 200:
            raise DeployFehler(f"Stack {stack_id} nicht lesbar: HTTP {r.status_code}")
        return r.json()

    def stack_datei(self, stack_id: int) -> str:
        r = self.get(f"/stacks/{stack_id}/file")
        if r.status_code != 200:
            raise DeployFehler(f"Stack-Datei {stack_id} nicht lesbar: HTTP {r.status_code}")
        return r.json()["StackFileContent"]

    def container(self, endpoint: int) -> list[dict[str, Any]]:
        r = self.get(f"/endpoints/{endpoint}/docker/containers/json",
                     params={"all": "1"})
        return r.json() if r.status_code == 200 else []


def pin_stack_datei(inhalt: str, pins: dict[str, str] | None = None) -> tuple[str, list[str]]:
    """Zieht bewegliche Fremd-Tags auf die gepinnten Werte. Idempotent.

    Ersetzt nur ``image: <name>:latest`` bzw. einen abweichenden konkreten Tag —
    eine bereits gepinnte oder per ``${VAR:-...}`` ueberschreibbare Zeile bleibt, wie
    sie ist, damit ein bewusstes Override im Stack nicht ueberfahren wird.
    """
    pins = pins or PINS
    aenderungen: list[str] = []
    for name, version in pins.items():
        muster = re.compile(
            r"^(?P<pre>\s*image:\s*)" + re.escape(name)
            + r":(?P<tag>[\w.\-]+)(?P<post>[ \t]*(?:#.*)?)$",
            re.MULTILINE)

        def ersetze(m: re.Match[str], _n: str = name, _v: str = version) -> str:
            if m.group("tag") == _v:
                return m.group(0)
            aenderungen.append(f"{_n}:{m.group('tag')} -> {_n}:{_v}")
            # Ein etwaiger Kommentar der Zeile bleibt stehen.
            return f"{m.group('pre')}{_n}:{_v}{m.group('post')}"

        inhalt = muster.sub(ersetze, inhalt)
    return inhalt, aenderungen


_FESTES_IMAGE = re.compile(r"^\s*image:\s*(?P<ref>[^\s${}#]+:[\w.\-]+)\s*(?:#.*)?$",
                           re.MULTILINE)


def feste_images(inhalt: str) -> list[str]:
    """Alle Images der Stack-Datei mit festem ``name:tag``.

    Zeilen mit ``${VAR}`` bleiben aussen vor: deren Wert steht in der Env des
    Stacks, nicht in der Datei — die AICS-Images werden ohnehin eigens gezogen.
    """
    gesehen: list[str] = []
    for m in _FESTES_IMAGE.finditer(inhalt):
        ref = m.group("ref")
        if ref not in gesehen:
            gesehen.append(ref)
    return gesehen


def pruefe_quelle(p: Portainer, endpoint: int, refs: list[str],
                  erwartet: str = ERWARTETE_QUELLE) -> list[str]:
    """Stellt sicher, dass die Images aus dem erwarteten Repo gebaut wurden.

    Gibt die gelesenen Quellen zurueck (fuer das Protokoll) oder wirft
    ``DeployFehler``. Ein leeres Label gilt als Abweichung: ein Image ohne
    Herkunftsangabe ist genau das, was hier nicht deployt werden soll.
    """
    quellen: list[str] = []
    abweichend: list[str] = []
    for ref in refs:
        quelle = p.image_quelle(endpoint, ref)
        quellen.append(f"{ref}: {quelle or '(kein Label)'}")
        if quelle != erwartet:
            abweichend.append(f"{ref} -> {quelle or '(kein Label)'}")
    if abweichend:
        raise DeployFehler(
            "Images stammen nicht aus dem erwarteten Repo: "
            + "; ".join(abweichend)
            + f" (erwartet {erwartet}). Entweder ist der oeffentliche Build nicht "
            "gelaufen (Release -> sync-to-public -> 'Docker Image' in aics-public) "
            "oder die Variable PUBLISH_IMAGES steht dort nicht auf 'true'. "
            "Bewusst ueberstimmen: --quelle beliebig.")
    return quellen


def _env_setzen(env: list[dict[str, str]], name: str, wert: str) -> str | None:
    """Setzt eine Env-Variable, laesst alle anderen unangetastet. Gibt den Altwert."""
    for e in env:
        if e.get("name") == name:
            alt = e.get("value")
            e["value"] = wert
            return alt
    env.append({"name": name, "value": wert})
    return None


def aics_container(p: Portainer, endpoint: int, projekt: str) -> list[tuple[str, str, str]]:
    """Die beiden AICS-Container **dieses** Stacks: (Name, Image, Zustand).

    Unterschieden wird ueber das Compose-Projekt, nicht ueber den Containernamen.
    Auf docker02 laufen vier Stacks mit Containern ``*_web``/``*_nginx`` aus
    denselben zwei Images (Prod, Demo, SOC, aics-licensing) — ein Name-Match traf
    den falschen Stack bzw. auf Demo (``aicsdemo_web``) gar keinen.
    """
    treffer = []
    for c in p.container(endpoint):
        if (c.get("Labels") or {}).get("com.docker.compose.project") != projekt:
            continue
        image = c.get("Image", "")
        if image.startswith(f"{WEB_IMAGE}:") or image.startswith(f"{NGINX_IMAGE}:"):
            name = next((n.lstrip("/") for n in c.get("Names", [])), "?")
            treffer.append((name, image, c.get("State", "")))
    return sorted(treffer)


def warte_auf_version(p: Portainer, endpoint: int, tag: str, projekt: str,
                      timeout_s: int = 600) -> bool:
    """Wartet, bis die AICS-Container des Stacks mit dem Zieltag laufen."""
    ende = time.time() + timeout_s
    while True:
        treffer = aics_container(p, endpoint, projekt)
        if len(treffer) >= 2 and all(
                i.endswith(f":{tag}") and s == "running" for _, i, s in treffer):
            for n, i, s in treffer:
                print(f"  {n}: {i} ({s})")
            return True
        if time.time() >= ende:
            for n, i, s in treffer:
                print(f"  noch {n}: {i} ({s})")
            return False
        time.sleep(5)


def parse_env(eintraege: list[str] | None) -> dict[str, str]:
    """``NAME=WERT``-Argumente in ein Dict. Leere Werte sind erlaubt (Löschen
    ist es nicht: dafür gibt es die Portainer-Oberfläche, und ein versehentlich
    entfernter Eintrag ist schwerer zu bemerken als ein leerer).

    Was hier gesetzt wird, ist Portainers Stack-Env — die ``.env`` für die
    compose-Interpolation. Sie erreicht den Container **nur**, wenn die
    Stack-Datei den Namen unter ``environment:`` durchreicht. Beobachtet bei
    #1738: ``AICS_LICENSE_SERVER_URL`` auf Stack 45 gesetzt, Redeploy mit HTTP
    200 angenommen — und im Container war die Variable nicht da, der Container
    nicht einmal neu erstellt (für compose hatte sich nichts geändert).
    """
    out: dict[str, str] = {}
    for roh in eintraege or []:
        name, trenner, wert = roh.partition("=")
        if not trenner or not name.strip():
            raise DeployFehler(f"--env erwartet NAME=WERT, bekam: {roh!r}")
        out[name.strip()] = wert
    return out


def redeploy(p: Portainer, stack_id: int, endpoint: int, tag: str, *,
             pin_images: bool = False, warten: bool = True,
             quelle: str | None = ERWARTETE_QUELLE,
             zusatz_env: dict[str, str] | None = None) -> None:
    if stack_id in VERBOTENE_STACKS:
        raise DeployFehler(
            f"Stack {stack_id} gehoert nicht zu AICS (aics-licensing) — abgebrochen.")

    # Welcher Portainer gemeint ist, gehoert ins Protokoll: ``PORTAINER_URL`` kann
    # aus der Umgebung kommen und auf eine andere Instanz zeigen als gedacht.
    print(f"Portainer: {p.base}")
    s = p.stack(stack_id)
    print(f"Stack {stack_id} '{s.get('Name')}' auf Endpoint {endpoint}")
    if s.get("Status") == 3:
        raise DeployFehler(
            "Es laeuft bereits ein Deploy (Status=3). Portainer antwortet auf einen "
            "zweiten PUT mit 409 — erst abwarten (docker logs portainer).")

    # 1) Nur die AICS-Images ziehen …
    for image in (WEB_IMAGE, NGINX_IMAGE):
        print(f"  ziehe {image}:{tag} …", flush=True)
        p.image_ziehen(endpoint, image, tag)

    # 2) … und pruefen, dass sie da sind. Mit pullImage:false startet der Dienst
    #    sonst ohne Image.
    fehlend = [f"{i}:{tag}" for i in (WEB_IMAGE, NGINX_IMAGE)
               if not p.image_vorhanden(endpoint, f"{i}:{tag}")]
    if fehlend:
        raise DeployFehler(
            f"Images nicht auf dem Endpoint: {fehlend} — nicht deployt. "
            f"(Mit pullImage:false waere der Dienst ohne Image gestartet.)")

    # 2b) Herkunft pruefen, bevor irgendetwas umgestellt wird (#1719/E4).
    refs = [f"{i}:{tag}" for i in (WEB_IMAGE, NGINX_IMAGE)]
    if quelle:
        for z in pruefe_quelle(p, endpoint, refs, quelle):
            print(f"  Herkunft {z}")
    else:
        for ref in refs:
            print(f"  Herkunft {ref}: "
                  f"{p.image_quelle(endpoint, ref) or '(kein Label)'} (ungeprueft)")

    inhalt = p.stack_datei(stack_id)
    if pin_images:
        inhalt, aend = pin_stack_datei(inhalt)
        for a in aend:
            print(f"  Stack-Datei: {a}")
        if not aend:
            print("  Stack-Datei: Fremd-Images bereits gepinnt")

    # 3) Jedes feste Image der Stack-Datei muss auf dem Endpoint liegen — sonst
    #    startet der Dienst mit pullImage:false ohne Image. Betrifft vor allem
    #    gerade gepinnte Tags: ``alpine:3.20`` kann dort fehlen, waehrend
    #    ``alpine:latest`` lag. Fehlendes wird einzeln gezogen, Vorhandenes nicht
    #    angefasst — das ist der ganze Punkt dieses Skripts.
    for ref in feste_images(inhalt):
        if p.image_vorhanden(endpoint, ref):
            continue
        name, _, ref_tag = ref.rpartition(":")
        print(f"  fehlt auf dem Endpoint, ziehe {ref} …", flush=True)
        p.image_ziehen(endpoint, name, ref_tag)
        if not p.image_vorhanden(endpoint, ref):
            raise DeployFehler(
                f"{ref} liess sich nicht bereitstellen — nicht deployt.")

    env = s.get("Env") or []
    alt = _env_setzen(env, "AICS_IMAGE_TAG", tag)
    print(f"  AICS_IMAGE_TAG: {alt} -> {tag}")
    for name, wert in (zusatz_env or {}).items():
        vorher = _env_setzen(env, name, wert)
        print(f"  {name}: {vorher if vorher is not None else '(neu)'} -> {wert}")

    r = p.put(f"/stacks/{stack_id}", params={"endpointId": endpoint},
              json={"stackFileContent": inhalt, "env": env,
                    "prune": False, "pullImage": False})
    if r.status_code >= 300:
        raise DeployFehler(f"Redeploy fehlgeschlagen: HTTP {r.status_code} {r.text[:300]}")
    print(f"  Redeploy angenommen (HTTP {r.status_code})")

    if warten and not warte_auf_version(p, endpoint, tag, str(s.get("Name") or "")):
        raise DeployFehler(
            f"Container laufen nach dem Timeout nicht auf {tag} — "
            f"Portainer-Log pruefen (docker logs portainer).")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stack", type=int, required=True, help="Portainer-Stack-ID")
    ap.add_argument("--endpoint", type=int, required=True,
                    help="Portainer-Endpoint (2=docker01, 3=docker02)")
    ap.add_argument("--tag", required=True, help="Zielversion, z. B. 7.4.6")
    ap.add_argument("--pin-images", action="store_true",
                    help="bewegliche Fremd-Tags in der Stack-Datei nachziehen")
    ap.add_argument("--no-wait", action="store_true",
                    help="nicht auf die neuen Container warten")
    ap.add_argument("--quelle", choices=("public", "privat", "beliebig"),
                    default="public",
                    help="erwartete Image-Herkunft (Default public = aics-public; "
                         "'beliebig' prueft nicht, gibt sie aber aus)")
    ap.add_argument("--env", action="append", metavar="NAME=WERT",
                    help="Stack-Env setzen (mehrfach moeglich); alle uebrigen "
                         "Eintraege bleiben unberuehrt. ACHTUNG: Das ist die "
                         "compose-.env, nicht die Container-Env — im Container "
                         "landet der Wert nur, wenn die Stack-Datei ihn unter "
                         "environment: durchreicht")
    # `type=_basis`: Die Normalisierung griff nur auf `PORTAINER_URL`, nicht auf
    # `--base`. Wer die Umgebungsvariable überstimmt (sie zeigt hier auf docker02,
    # der Manager läuft auf docker01), bekam mit `--base https://docker01:9443`
    # ein HTTP 404 — genau das Fehlerbild, vor dem `_basis` im Docstring warnt,
    # und es sieht aus wie „Stack gibt es nicht".
    ap.add_argument("--base", default=DEFAULT_BASE, type=_basis)
    ap.add_argument("--key", default=None, help="sonst PORTAINER_API_KEY")
    a = ap.parse_args(argv)

    quelle = {"public": ERWARTETE_QUELLE,
              "privat": "https://github.com/martinzeifang/AI_Compliance_Suite",
              "beliebig": None}[a.quelle]

    try:
        p = Portainer(a.base, _key(a.key))
        redeploy(p, a.stack, a.endpoint, a.tag,
                 pin_images=a.pin_images, warten=not a.no_wait, quelle=quelle,
                 zusatz_env=parse_env(a.env))
    except DeployFehler as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 1
    print("fertig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
