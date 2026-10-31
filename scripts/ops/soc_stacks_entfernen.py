#!/usr/bin/env python3
"""Die SOC-Stacks und ihre Images von den Servern nehmen (#1905).

WAS DAS SKRIPT TUT
------------------
Das SOC-Modul ist mit v8.3.0 aus der Suite entfernt. Auf den Servern laufen
aber noch zwei eigene Stacks mit einem **alten** Suite-Image (6.28.0):

====  =========  =================================================
Stack  Endpoint   Container
====  =========  =================================================
62     2          ``aicssoc_web`` ``aicssoc_nginx`` ``aicssoc_gotenberg`` ``aicssoc_ollama``
59     3          dieselben vier
====  =========  =================================================

Das Skript löscht die Stacks und danach die beiden AICS-Images in der
SOC-Version. **Reihenfolge ist wichtig:** erst der Stack, dann das Image —
umgekehrt steht ein Image im Weg, das laufende Container noch brauchen.

DREI RIEGEL, UND KEINER IST DIE STACKNUMMER
-------------------------------------------
Eine Nummer ist kein Beweis. Die Nummerierung unterscheidet sich zwischen den
beiden Portainer-Instanzen (die Umgebungsvariable zeigt auf **docker02**, der
AICS-Manager läuft auf **docker01**), und auf dem falschen Manager träfe
„Stack 59" etwas völlig anderes. Deshalb:

1. Der Stack muss **``aics-soc`` heißen** — sonst Abbruch.
2. Seine Container müssen das Präfix **``aicssoc_``** tragen.
3. ``VERBOTENE_STACKS`` aus ``portainer_redeploy`` gilt weiter
   (``aics-licensing`` ist ein anderes Produkt).

Vorgabe ist der **Trockenlauf**. Ohne ``--confirm`` wird nur gezeigt.

    python3 scripts/ops/soc_stacks_entfernen.py --base https://docker01:9443/api
    python3 scripts/ops/soc_stacks_entfernen.py --base https://docker01:9443/api --confirm

Der API-Key kommt aus ``PORTAINER_API_KEY`` oder ``--key``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ops.portainer_redeploy import (  # noqa: E402
    DEFAULT_BASE, VERBOTENE_STACKS, DeployFehler, Portainer, _basis, _key)

#: So muss der Stack heißen. Alles andere wird nicht angefasst.
STACK_NAME = "aics-soc"

#: So müssen seine Container heißen.
CONTAINER_PREFIX = "aicssoc_"

#: Die Images, die danach weg können — die SOC-Stacks sind ihre letzten Nutzer.
SOC_IMAGES = (
    "ghcr.io/martinzeifang/ai_compliance_suite:6.28.0",
    "ghcr.io/martinzeifang/aics-nginx:6.28.0",
)


def soc_stacks(p: Portainer) -> list[dict]:
    r = p.get("/stacks")
    if r.status_code != 200:
        raise DeployFehler(f"Stacks nicht lesbar: HTTP {r.status_code}")
    return [s for s in r.json() if str(s.get("Name", "")) == STACK_NAME]


def container_des_stacks(p: Portainer, endpoint: int) -> list[str]:
    r = p.get(f"/endpoints/{endpoint}/docker/containers/json",
              params={"all": "1"})
    if r.status_code != 200:
        return []
    namen: list[str] = []
    for c in r.json():
        for n in c.get("Names") or []:
            name = str(n).lstrip("/")
            if name.startswith(CONTAINER_PREFIX):
                namen.append(name)
    return sorted(namen)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=DEFAULT_BASE, type=_basis)
    ap.add_argument("--key", default=None)
    ap.add_argument("--confirm", action="store_true",
                    help="wirklich löschen (ohne diesen Schalter wird nur gezeigt)")
    ap.add_argument("--images-behalten", action="store_true",
                    help="nur die Stacks löschen, die Images stehen lassen")
    args = ap.parse_args(argv)

    p = Portainer(args.base, _key(args.key))
    gefunden = soc_stacks(p)
    if not gefunden:
        print(f"Kein Stack namens „{STACK_NAME}“ an {args.base} — nichts zu tun.")
        return 0

    print(f"Gefunden an {args.base}:")
    plan: list[tuple[int, int]] = []
    for s in gefunden:
        sid = int(s.get("Id"))
        ep = int(s.get("EndpointId") or 0)
        if sid in VERBOTENE_STACKS:
            print(f"  ! Stack {sid} steht in VERBOTENE_STACKS — übersprungen.")
            continue
        namen = container_des_stacks(p, ep)
        print(f"  Stack {sid} „{s.get('Name')}“ · Endpoint {ep}")
        for n in namen:
            print(f"      {n}")
        if not namen:
            print("      (keine Container mit Präfix "
                  f"„{CONTAINER_PREFIX}“ — Stack trotzdem löschbar)")
        plan.append((sid, ep))

    if not plan:
        print("\nNichts zu löschen.")
        return 0

    if not args.confirm:
        print("\nTrockenlauf — nichts gelöscht. Mit --confirm erneut aufrufen.")
        if not args.images_behalten:
            print("Danach entfernt würden außerdem:")
            for ref in SOC_IMAGES:
                print(f"  {ref}")
        return 0

    for sid, ep in plan:
        r = p.delete(f"/stacks/{sid}", params={"endpointId": ep})
        ok = r.status_code in (200, 204)
        print(f"Stack {sid} gelöscht: HTTP {r.status_code}" if ok
              else f"! Stack {sid} NICHT gelöscht: HTTP {r.status_code} {r.text[:200]}")
        if not ok:
            # Ein stehengebliebener Stack hält das Image — dann ist auch das
            # Entfernen der Images sinnlos und würde nur verwirren.
            print("  Abbruch: erst den Stack klären, dann die Images.")
            return 1

    if args.images_behalten:
        return 0

    endpoints = sorted({ep for _sid, ep in plan})
    for ep in endpoints:
        for ref in SOC_IMAGES:
            r = p.delete(f"/endpoints/{ep}/docker/images/{ref}",
                         params={"force": "false"})
            if r.status_code in (200, 204):
                print(f"Image entfernt (ep {ep}): {ref}")
            elif r.status_code == 404:
                print(f"Image war nicht da (ep {ep}): {ref}")
            else:
                # Kein Abbruch: Ein Image, das noch ein anderer Container
                # benutzt, SOLL stehen bleiben. Das ist kein Fehler des
                # Rückbaus, sondern der Beweis, dass es noch gebraucht wird.
                print(f"! Image nicht entfernt (ep {ep}): {ref} — "
                      f"HTTP {r.status_code} {r.text[:160]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DeployFehler as e:
        print(f"Fehler: {e}", file=sys.stderr)
        raise SystemExit(2) from e
