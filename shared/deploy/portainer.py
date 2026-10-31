"""Einen AICS-Stack über Portainer auf eine Version umstellen (#1733, #1908).

WARUM NICHT ``pullImage: true``
-------------------------------
Portainers „Pull and redeploy" zieht **jedes** Image des Stacks neu, nicht nur
die beiden AICS-Images. An Stack 45 hängt ``ollama/ollama`` mit 3,2 GB; ein
App-Deploy, der in Sekunden durch wäre, stand damit 35 Minuten auf ``Status=3``
(gemessen bei v7.4.6). Schwerer wiegt das Stille daran: mitgezogen werden auch
``postgres:16-alpine``, ``gotenberg:8`` und ``redis:7-alpine`` — ein App-Update
kann so ungewollt **die Datenbank** auf einen neuen 16.x-Stand heben, ohne dass
das irgendwo als Datenbank-Update auftaucht.

Dieses Modul zieht deshalb **nur** die beiden AICS-Images in der Zielversion vor,
prüft dass sie auf dem Endpoint liegen (mit ``pullImage: false`` startet ein
Dienst sonst ohne Image — der Stack wird nicht alt, sondern tot), prüft ihre
**Herkunft** und deployt dann.

WARUM ES IN ``shared/`` LIEGT UND NICHT IN ``scripts/ops/`` (#1908)
-------------------------------------------------------------------
Weil es zwei Aufrufer hat: das Skript ``scripts/ops/portainer_redeploy.py`` und
den Endpunkt ``POST /api/admin/update``. Der Endpunkt tat bis v8.2.3 etwas
anderes — er schickte ``pullImage: True``, also genau das oben Beschriebene,
**ohne** Herkunftsprüfung und ohne die Zielversion setzen zu können. Der
dokumentierte Weg war scharf, der Knopf in der Oberfläche umging ihn.
``scripts/`` liegt nicht im Laufzeit-Image, also musste die Logik hierher.

MELDUNGEN STATT ``print``
-------------------------
:func:`redeploy` nimmt einen ``melde``-Callback. Das Skript übergibt ``print``
und verhält sich unverändert; der Endpunkt sammelt die Zeilen und gibt sie in
der Antwort zurück — ein Deploy, dessen Verlauf niemand sieht, ist in einer
Oberfläche wertlos.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, Callable

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#: Wohin der Verlauf geht. Vorgabe ist ``print`` — so verhaelt sich
#: ``scripts/ops/portainer_redeploy.py`` unveraendert; der Endpunkt uebergibt
#: eine Sammelfunktion und gibt die Zeilen in seiner Antwort zurueck.
Melder = Callable[..., None]

def _basis(roh: str) -> str:
    """Normalisiert die Portainer-Basis-URL auf ``…/api``.

    ``PORTAINER_URL`` steht in manchen Umgebungen ohne ``/api`` (also nur
    ``https://<host>:9443``). Ohne diese Normalisierung antwortet jeder Aufruf
    mit ``404 page not found`` — ein Fehlerbild, das nach „Stack gibt es nicht"
    aussieht und in die falsche Richtung schickt.

    Hier stand bis #1908 eine Beispiel-IP aus unserer eigenen Umgebung. Die
    Datei lag damals unter ``scripts/`` und kam nicht ins Image; seit sie unter
    ``shared/`` liegt, tut sie es — und ``scripts/sanitize-public.sh`` hätte die
    Adresse beim Spiegeln umgeschrieben. Das öffentlich gebaute Image hätte sich
    dann unsichtbar vom privaten unterschieden, genau das Fehlerbild aus #1738.
    Gefunden hat das ``tests/test_public_publisher_1738.py``, bevor es jemand
    gemerkt hätte.
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

    def delete(self, pfad: str, **kw: Any) -> requests.Response:
        """Für ``soc_stacks_entfernen.py`` (#1905) — Stacks und Images löschen.

        Hier und nicht dort, damit es **einen** Portainer-Client gibt: Ein
        zweiter Transport wäre der sechste eigene Client im Haus (die Lehre
        aus #1841), und die TLS-Entscheidung (``verify``) träfe er womöglich
        anders.
        """
        return requests.delete(f"{self.base}{pfad}", headers=self.h,
                               verify=self.verify, timeout=300, **kw)

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
                      timeout_s: int = 600, melde: Melder = print) -> bool:
    """Wartet, bis die AICS-Container des Stacks mit dem Zieltag laufen."""
    ende = time.time() + timeout_s
    while True:
        treffer = aics_container(p, endpoint, projekt)
        if len(treffer) >= 2 and all(
                i.endswith(f":{tag}") and s == "running" for _, i, s in treffer):
            for n, i, s in treffer:
                melde(f"  {n}: {i} ({s})")
            return True
        if time.time() >= ende:
            for n, i, s in treffer:
                melde(f"  noch {n}: {i} ({s})")
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
             zusatz_env: dict[str, str] | None = None,
             melde: Melder = print) -> None:
    if stack_id in VERBOTENE_STACKS:
        raise DeployFehler(
            f"Stack {stack_id} gehoert nicht zu AICS (aics-licensing) — abgebrochen.")

    # Welcher Portainer gemeint ist, gehoert ins Protokoll: ``PORTAINER_URL`` kann
    # aus der Umgebung kommen und auf eine andere Instanz zeigen als gedacht.
    melde(f"Portainer: {p.base}")
    s = p.stack(stack_id)
    melde(f"Stack {stack_id} '{s.get('Name')}' auf Endpoint {endpoint}")
    if s.get("Status") == 3:
        raise DeployFehler(
            "Es laeuft bereits ein Deploy (Status=3). Portainer antwortet auf einen "
            "zweiten PUT mit 409 — erst abwarten (docker logs portainer).")

    # 1) Nur die AICS-Images ziehen …
    for image in (WEB_IMAGE, NGINX_IMAGE):
        melde(f"  ziehe {image}:{tag} …")
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
            melde(f"  Herkunft {z}")
    else:
        for ref in refs:
            melde(f"  Herkunft {ref}: "
                  f"{p.image_quelle(endpoint, ref) or '(kein Label)'} (ungeprueft)")

    inhalt = p.stack_datei(stack_id)
    if pin_images:
        inhalt, aend = pin_stack_datei(inhalt)
        for a in aend:
            melde(f"  Stack-Datei: {a}")
        if not aend:
            melde("  Stack-Datei: Fremd-Images bereits gepinnt")

    # 3) Jedes feste Image der Stack-Datei muss auf dem Endpoint liegen — sonst
    #    startet der Dienst mit pullImage:false ohne Image. Betrifft vor allem
    #    gerade gepinnte Tags: ``alpine:3.20`` kann dort fehlen, waehrend
    #    ``alpine:latest`` lag. Fehlendes wird einzeln gezogen, Vorhandenes nicht
    #    angefasst — das ist der ganze Punkt dieses Skripts.
    for ref in feste_images(inhalt):
        if p.image_vorhanden(endpoint, ref):
            continue
        name, _, ref_tag = ref.rpartition(":")
        melde(f"  fehlt auf dem Endpoint, ziehe {ref} …")
        p.image_ziehen(endpoint, name, ref_tag)
        if not p.image_vorhanden(endpoint, ref):
            raise DeployFehler(
                f"{ref} liess sich nicht bereitstellen — nicht deployt.")

    env = s.get("Env") or []
    alt = _env_setzen(env, "AICS_IMAGE_TAG", tag)
    melde(f"  AICS_IMAGE_TAG: {alt} -> {tag}")
    for name, wert in (zusatz_env or {}).items():
        vorher = _env_setzen(env, name, wert)
        melde(f"  {name}: {vorher if vorher is not None else '(neu)'} -> {wert}")

    r = p.put(f"/stacks/{stack_id}", params={"endpointId": endpoint},
              json={"stackFileContent": inhalt, "env": env,
                    "prune": False, "pullImage": False})
    if r.status_code >= 300:
        raise DeployFehler(f"Redeploy fehlgeschlagen: HTTP {r.status_code} {r.text[:300]}")
    melde(f"  Redeploy angenommen (HTTP {r.status_code})")

    if warten and not warte_auf_version(p, endpoint, tag, str(s.get("Name") or ""),
                                        melde=melde):
        raise DeployFehler(
            f"Container laufen nach dem Timeout nicht auf {tag} — "
            f"Portainer-Log pruefen (docker logs portainer).")
