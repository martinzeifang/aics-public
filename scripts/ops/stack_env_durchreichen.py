#!/usr/bin/env python3
"""Eine Umgebungsvariable in der LIVE-Stack-Datei durchreichen (#1951).

Warum es dieses Skript gibt
===========================
``portainer_redeploy.py`` liest die **Live**-Stack-Datei und schreibt sie
zurueck. Eine neue ``environment:``-Zeile in ``docker-compose.yml`` des
Repositories erreicht einen **bestehenden** Stack deshalb nie — die Live-Datei
ist eine Kopie aus der Zeit der Stack-Anlage und driftet (bei Stack 50 am
04.11.2026: 516 abweichende Zeilen, siehe #1948).

Genau daran scheiterte das Einschalten der Sicherungs-Verschluesselung: Der
Schluessel stand in Portainers Stack-Env, der Container meldete ``FEHLT``, und
der Redeploy antwortete trotzdem mit HTTP 200. Portainers Stack-Env ist die
``.env`` fuer die compose-**Interpolation**; in den Container kommt ein Wert nur
ueber eine ``environment:``-Zeile.

Warum NICHT die Repo-Datei hochgeladen wird
===========================================
Naheliegend waere, ``docker-compose.yml`` als Stack-Datei zu pushen und die
Drift damit zu beenden. Das ist hier **falsch**: Auf Produktiv wuerden mit
einer Zeile Absicht mehrere hundert Zeilen ungeprueft mitgeaendert — Haertung,
Limits, Healthchecks, gepinnte Fremd-Images. Die Drift ist ein eigener Vorgang
(#1948) und braucht ein eigenes Fenster. Dieses Skript aendert **nur** die
genannten Zeilen und beweist das.

Der Beweis
==========
Nach der Textaenderung wird die Datei geparst und mit dem Zustand davor
verglichen — nach Entfernen der eingefuegten Eintraege muss die Struktur
**identisch** sein. Eine Textbearbeitung an YAML ohne diesen Gegencheck ist
eine Behauptung.

Aufruf
======
    PORTAINER_API_KEY=… python3 scripts/ops/stack_env_durchreichen.py \\
        --base https://docker01:9443 --stack 63 --name AICS_BACKUP_KEY

Trockenlauf ist die Vorgabe und zeigt den Unterschied. Geschrieben wird erst
mit ``--confirm``.

**Der PUT ersetzt die Container** — Portainer rollt den Stack beim Schreiben der
Datei aus. Der Tag bleibt dabei unberuehrt (``pullImage: false``, ``Env``
unveraendert), es ist also kein Versionswechsel; ein solcher laeuft weiter ueber
``portainer_redeploy.py`` mit seinen Herkunfts- und Signaturpruefungen (#1738).
Wer beides braucht, zahlt zwei kurze Neuerstellungen — die Pruefungen dort
nachzubauen waere der falsche Preis fuer die gesparte Minute.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

#: Wie im Deploy-Skript. Der Lizenzserver wird von AICS-Werkzeugen nie
#: angefasst — die Nummerierung gilt fuer den Portainer auf docker01.
VERBOTENE_STACKS = {51}

_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _pruefe_name(name: str) -> str:
    if not _NAME.match(name):
        raise SystemExit(f"Kein gueltiger Variablenname: {name!r}")
    return name


def _dienst_block(zeilen: list[str], dienst: str) -> tuple[int, int]:
    """Zeilenbereich [start, ende) des Dienstes unter ``services:``."""
    start = None
    for i, z in enumerate(zeilen):
        if re.match(rf"^  {re.escape(dienst)}:\s*$", z):
            start = i
            break
    if start is None:
        raise SystemExit(f"Dienst {dienst!r} nicht in der Stack-Datei gefunden.")
    for j in range(start + 1, len(zeilen)):
        # Naechster Eintrag auf derselben Ebene (zwei Leerzeichen, kein Listen-
        # oder Kommentarzeichen) beendet den Block.
        if re.match(r"^  [A-Za-z0-9_.-]+:\s*$", zeilen[j]):
            return start, j
    return start, len(zeilen)


def einfuegen(inhalt: str, dienst: str, namen: list[str]) -> tuple[str, list[str]]:
    """``- NAME=${NAME:-}`` in die Umgebung des Dienstes, falls nicht vorhanden.

    Eingefuegt wird direkt nach ``environment:`` — die Reihenfolge einer
    compose-Umgebungsliste ist bedeutungslos, und so wird kein Kommentar
    zerrissen, der zu einem bestehenden Eintrag gehoert.
    """
    import yaml

    vorher = yaml.safe_load(inhalt)
    zeilen = inhalt.splitlines(keepends=True)
    start, ende = _dienst_block(zeilen, dienst)

    env_zeile = None
    for i in range(start, ende):
        if re.match(r"^    environment:\s*$", zeilen[i]):
            env_zeile = i
            break
    if env_zeile is None:
        raise SystemExit(
            f"{dienst} hat keinen `environment:`-Block in Listenform — "
            f"von Hand pruefen, hier wird nicht geraten.")

    # Der Einzug kommt aus der DATEI, nicht aus dieser Zeile. Die Live-Dateien
    # ruecken Listeneintraege mit 4 Leerzeichen ein, `docker-compose.yml` im
    # Repository mit 6 — beides ist gueltiges YAML, aber MISCHEN bricht den
    # Block: Ein tieferer Eintrag nach `environment:` beginnt eine
    # verschachtelte Sequenz, und der naechste flache Eintrag ist dann ein
    # Syntaxfehler. Beim ersten Anlauf fest verdrahtet, vom Gegencheck unten
    # abgefangen, bevor etwas geschrieben wurde.
    einzug = None
    for i in range(env_zeile + 1, ende):
        m = re.match(r"^(\s+)- ", zeilen[i])
        if m:
            einzug = m.group(1)
            break
        if zeilen[i].strip() and not zeilen[i].lstrip().startswith("#"):
            break  # Ende der Liste erreicht
    if einzug is None:
        raise SystemExit(
            f"{dienst}.environment hat keinen Listeneintrag, aus dem sich der "
            f"Einzug ablesen laesst — von Hand pruefen.")

    env_alt = (vorher.get("services", {}).get(dienst, {}) or {}).get("environment")
    if not isinstance(env_alt, list):
        raise SystemExit(
            f"{dienst}.environment ist {type(env_alt).__name__}, erwartet Liste.")
    vorhanden = {str(e).partition("=")[0].strip() for e in env_alt}

    neu: list[str] = []
    for name in namen:
        if name in vorhanden:
            continue
        neu.append(name)

    if not neu:
        return inhalt, []

    eingefuegt = [f"{einzug}- {n}=${{{n}:-}}\n" for n in neu]
    zeilen[env_zeile + 1:env_zeile + 1] = eingefuegt
    danach = "".join(zeilen)

    # ---- Der Gegencheck: nur die neuen Eintraege dürfen anders sein ----
    nachher = yaml.safe_load(danach)
    probe = copy.deepcopy(nachher)
    env_neu = probe["services"][dienst]["environment"]
    probe["services"][dienst]["environment"] = [
        e for e in env_neu if str(e).partition("=")[0].strip() not in neu
    ]
    if probe != vorher:
        raise SystemExit(
            "Die Textaenderung hat mehr als die neuen Eintraege veraendert — "
            "nichts geschrieben.")
    for n in neu:
        if nachher["services"][dienst]["environment"].count(f"{n}=${{{n}:-}}") != 1:
            raise SystemExit(f"{n} steht nach der Aenderung nicht genau einmal.")

    return danach, neu


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stack", type=int, required=True)
    ap.add_argument("--endpoint", type=int, default=None,
                    help="nur fuer den PUT; Vorgabe: der Endpoint des Stacks")
    ap.add_argument("--name", action="append", required=True,
                    help="Variablenname, mehrfach moeglich")
    ap.add_argument("--dienst", default="web")
    ap.add_argument("--base", default=os.environ.get("PORTAINER_URL", ""))
    ap.add_argument("--key", default=os.environ.get("PORTAINER_API_KEY", ""))
    ap.add_argument("--confirm", action="store_true",
                    help="schreiben; ohne dies nur Trockenlauf")
    a = ap.parse_args(argv)

    if a.stack in VERBOTENE_STACKS:
        print(f"Stack {a.stack} ist gesperrt.", file=sys.stderr)
        return 2
    if not a.key:
        print("Kein API-Key (PORTAINER_API_KEY oder --key).", file=sys.stderr)
        return 2

    namen = [_pruefe_name(n) for n in a.name]

    from shared.deploy.portainer import Portainer

    p = Portainer(a.base, a.key)
    s = p.stack(a.stack)
    alt = p.stack_datei(a.stack)
    endpoint = a.endpoint or int(s.get("EndpointId") or 0)
    print(f"Stack {a.stack} ({s.get('Name')}), Endpoint {endpoint}, "
          f"Dienst {a.dienst}")

    neu_inhalt, neu = einfuegen(alt, a.dienst, namen)
    if not neu:
        print("  Alle Namen sind schon durchgereicht — nichts zu tun.")
        return 0

    print("  Einfuegen: " + ", ".join(neu))
    for zeile in difflib.unified_diff(
            alt.splitlines(), neu_inhalt.splitlines(),
            "live (vorher)", "live (nachher)", lineterm="", n=2):
        print("  " + zeile)

    if not a.confirm:
        print("\n  TROCKENLAUF — nichts geschrieben. Mit --confirm ausfuehren.")
        return 0

    env = s.get("Env") or []
    r = p.put(f"/stacks/{a.stack}", params={"endpointId": endpoint},
              json={"stackFileContent": neu_inhalt, "env": env,
                    "prune": False, "pullImage": False})
    if r.status_code >= 300:
        print(f"  FEHLER: HTTP {r.status_code} {r.text[:300]}", file=sys.stderr)
        return 1
    print(f"  geschrieben (HTTP {r.status_code})")

    kontrolle = p.stack_datei(a.stack)
    fehlt = [n for n in neu if f"- {n}=" not in kontrolle]
    if fehlt:
        print(f"  FEHLER: nach dem Schreiben fehlen noch {fehlt}", file=sys.stderr)
        return 1
    print("  nachgelesen: steht in der Live-Datei")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
