#!/usr/bin/env python3
"""Redeploy eines AICS-Stacks auf eine Version — ohne Fremd-Images mitzuziehen (#1733).

Die Arbeit macht :mod:`shared.deploy.portainer`; dieses Skript ist die
Befehlszeile dazu. Seit #1908 hat dieselbe Logik einen zweiten Aufrufer, den
Endpunkt ``POST /api/admin/update`` — der schickte bis v8.2.3 ein
``pullImage: True`` an Portainer, zog damit jedes Image des Stacks neu (3,2 GB
Ollama, und ungefragt einen neuen Postgres-Stand) und prüfte die Herkunft nicht.
Eine Kopie der Logik im Webdienst hätte genau diesen Unterschied dauerhaft
gemacht, deshalb liegt sie unter ``shared/`` (``scripts/`` ist nicht im Image).

Aufruf::

    export PORTAINER_API_KEY=ptr_...
    python3 scripts/ops/portainer_redeploy.py --stack 45 --endpoint 2 --tag 7.4.6
    python3 scripts/ops/portainer_redeploy.py --stack 50 --endpoint 3 --tag 7.4.6 --pin-images

``--pin-images`` zieht zusätzlich die beweglichen Fremd-Tags in der
**Stack-Datei** auf die im Repo gepinnten Werte nach (Ollama, alpine). Das ist
nötig, weil ein Tag-Redeploy die Stack-Datei nicht anfasst: #1188 hat ``alpine``
im Repo gepinnt, in den Live-Stacks stand weiter ``alpine:latest``.

HERKUNFT DER IMAGES (#1719/E4)
Release- **und Beta**-Images kommen aus dem öffentlichen Repo ``aics-public``;
das private baut nur Dev-Tags (``:main``, ``:sha-…``). Vor dem Deploy wird
geprüft, aus welchem Quellbaum das gezogene Image gebaut wurde — sonst wäre die
Umstellung nicht nachweisbar. Ein Dev-Image deployt man bewusst mit
``--quelle privat``, jedes andere mit ``--quelle beliebig``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Die Namen stehen hier weiter zur Verfügung: `soc_stacks_entfernen.py` und
# vier Testdateien importieren sie aus **dieser** Datei. `__all__` sagt dem
# Prüfer, dass das Absicht ist — ohne das hält er sie für unbenutzte Importe,
# und eine Prüferausgabe, die man nicht mehr liest, prüft nichts
# (#1805/#1834).
from shared.deploy.portainer import (  # noqa: E402
    DEFAULT_BASE,
    ERWARTETE_QUELLE,
    NGINX_IMAGE,
    PINS,
    QUELL_LABEL,
    VERBOTENE_STACKS,
    WEB_IMAGE,
    DeployFehler,
    Portainer,
    _basis,
    _env_setzen,
    _key,
    aics_container,
    feste_images,
    parse_env,
    pin_stack_datei,
    pruefe_quelle,
    redeploy,
    warte_auf_version,
)

__all__ = [
    "DEFAULT_BASE", "ERWARTETE_QUELLE", "NGINX_IMAGE", "PINS", "QUELL_LABEL",
    "VERBOTENE_STACKS", "WEB_IMAGE", "DeployFehler", "Portainer", "_basis",
    "_env_setzen", "_key", "aics_container", "feste_images", "main",
    "parse_env", "pin_stack_datei", "pruefe_quelle", "redeploy",
    "warte_auf_version",
]


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
