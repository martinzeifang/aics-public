"""Antwortzeiten aus ``logs/audit.log`` lesen — #2024.

WAS HIER FEHLTE
Die Anwendung schreibt seit #1338 für **jede** Anfrage einen Eintrag nach
``logs/audit.log``: ``ts``, ``path``, ``status_code``, ``user_id`` und
**``duration_ms``**. Die Datei ist append-only, liegt im Datenvolumen und
überlebt das Neuerstellen des Containers. Auf Demo waren das am 09.11.2026
432 019 Einträge seit Juni.

Gelesen hat sie niemand. Als das System zweimal einfror (#2023), habe ich im
falschen Log gesucht — nginx und ``docker logs``, deren Puffer mein eigener
Deploy ohnehin geleert hatte — und zuerst notiert, es gebe „nichts zu messen".
Das war falsch in der Richtung, die am meisten kostet: Ein Vorgang, der eine
vorhandene Fähigkeit als fehlend meldet, lädt dazu ein, ein zweites Protokoll
zu bauen.

Dieses Modul ist die Lesebrille. Es rechnet nichts neu und schreibt nichts —
es wertet aus, was ohnehin dasteht.

WAS ES BEANTWORTET
* Wie schnell ist die Installation **normalerweise**? (p50, p95 je Stunde)
* Gab es einen **Stau**? (Antworten über einer Schwelle, je Pfad gebündelt)
* Enden viele Anfragen **gleichzeitig**? Das ist der Fingerabdruck eines Staus,
  der sich auf einen Schlag löst — und er unterscheidet ihn von gleichmäßiger
  Langsamkeit.
* Welche **Pfade** tragen die Last?

Die Auswertung ist bewusst **streaming**: 111 MB Log in einem Rutsch zu laden
wäre auf einer Instanz mit 1 GB Speicherdeckel genau der falsche Weg.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

#: Vorgabe-Schwelle für „langsam". 2 s ist die Schwelle, die auch
#: ``log_min_duration_statement`` auf der Datenbankseite trägt (#2095) — zwei
#: verschiedene Schwellen für dieselbe Frage wären zwei Bilder desselben Staus.
LANGSAM_MS = 2000.0

#: Obergrenze für die Zahl gelesener Zeilen je Abfrage. Ein Endpunkt, der eine
#: 111-MB-Datei vollständig liest, ist selbst die nächste Störung.
MAX_ZEILEN = 400_000

LOG = Path("logs/audit.log")


def _eintraege(pfad: Path, tag: str = "", grenze: int = MAX_ZEILEN) -> Iterator[dict]:
    """Zeilen des Logs als Dicts — gefiltert **vor** dem JSON-Parsen.

    Der Datumsvergleich auf der rohen Zeile spart bei 432 019 Einträgen den
    Parser für 99 % davon; gemessen macht das aus Minuten Sekunden.
    """
    if not pfad.is_file():
        return
    gelesen = 0
    with pfad.open(encoding="utf-8", errors="replace") as f:
        for zeile in f:
            if tag and tag not in zeile:
                continue
            gelesen += 1
            if gelesen > grenze:
                return
            try:
                e = json.loads(zeile)
            except Exception:  # noqa: BLE001 — eine kaputte Zeile ist kein Abbruch
                continue
            if e.get("duration_ms") is None:
                continue
            yield e


def _quantil(werte: list[float], anteil: float) -> float:
    if not werte:
        return 0.0
    sortiert = sorted(werte)
    i = min(len(sortiert) - 1, int(len(sortiert) * anteil))
    return sortiert[i]


def profil(tag: str, *, pfad: Path | None = None,
           langsam_ms: float = LANGSAM_MS) -> dict[str, Any]:
    """Antwortzeiten eines Tages (``JJJJ-MM-TT``).

    Rückgabe ist bewusst flach und zahlenlastig — sie geht in eine Admin-Maske
    und soll ohne Nachrechnen lesbar sein.
    """
    datei = pfad or LOG
    je_stunde: dict[str, list[float]] = defaultdict(list)
    je_pfad: dict[str, list[float]] = defaultdict(list)
    langsame: list[dict[str, Any]] = []
    enden: Counter[str] = Counter()
    gesamt = 0

    for e in _eintraege(datei, tag):
        d = float(e["duration_ms"])
        ts = str(e.get("ts") or "")
        p = str(e.get("path") or "")
        gesamt += 1
        je_stunde[ts[11:13]].append(d)
        je_pfad[p].append(d)
        if d >= langsam_ms:
            langsame.append({"ts": ts, "path": p, "dauer_s": round(d / 1000, 2),
                             "status": e.get("status_code")})
            # #2024: Der Fingerabdruck eines Staus ist, dass vieles in
            # **derselben Sekunde** endet — danach ist er von gleichmäßiger
            # Langsamkeit unterscheidbar.
            enden[ts[:19]] += 1

    stunden = []
    for h in sorted(je_stunde):
        w = je_stunde[h]
        stunden.append({
            "stunde": h, "anzahl": len(w),
            "p50_s": round(statistics.median(w) / 1000, 3),
            "p95_s": round(_quantil(w, 0.95) / 1000, 3),
            "max_s": round(max(w) / 1000, 2),
            "langsam": sum(1 for x in w if x >= langsam_ms),
        })

    pfade = sorted(
        ({"path": p, "anzahl": len(w),
          "p50_s": round(statistics.median(w) / 1000, 3),
          "max_s": round(max(w) / 1000, 2),
          "summe_s": round(sum(w) / 1000, 1)}
         for p, w in je_pfad.items() if len(w) >= 3),
        key=lambda r: -r["summe_s"])[:25]

    langsame.sort(key=lambda r: -r["dauer_s"])
    return {
        "tag": tag,
        "log_vorhanden": datei.is_file(),
        "anfragen": gesamt,
        "schwelle_s": langsam_ms / 1000,
        "stunden": stunden,
        "langsamste": langsame[:40],
        "langsam_gesamt": len(langsame),
        # Sekunden, in denen mehr als zwei langsame Antworten **endeten**.
        "gleichzeitige_enden": [
            {"sekunde": s, "anzahl": n} for s, n in enden.most_common(10) if n > 2],
        "teuerste_pfade": pfade,
        "gelesene_grenze_erreicht": gesamt >= MAX_ZEILEN,
    }


def tage(pfad: Path | None = None, grenze: int = 14) -> list[str]:
    """Die jüngsten Tage, für die das Log Einträge hat.

    Gelesen wird vom **Ende** her: Ein Log mit 432 019 Zeilen von vorn zu
    durchlaufen, nur um die Datumsliste zu füllen, wäre die Last, die dieses
    Modul vermeiden soll.
    """
    datei = pfad or LOG
    if not datei.is_file():
        return []
    gefunden: list[str] = []
    gesehen: set[str] = set()
    with datei.open("rb") as f:
        f.seek(0, 2)
        groesse = f.tell()
        block = 1 << 20
        rest = b""
        pos = groesse
        while pos > 0 and len(gesehen) < grenze:
            lese = min(block, pos)
            pos -= lese
            f.seek(pos)
            puffer = f.read(lese) + rest
            zeilen = puffer.split(b"\n")
            rest = zeilen.pop(0)
            for zeile in reversed(zeilen):
                try:
                    ts = json.loads(zeile).get("ts") or ""
                except Exception:  # noqa: BLE001
                    continue
                tag = str(ts)[:10]
                if len(tag) == 10 and tag not in gesehen:
                    gesehen.add(tag)
                    gefunden.append(tag)
                    if len(gesehen) >= grenze:
                        break
    return gefunden


__all__ = ["LANGSAM_MS", "MAX_ZEILEN", "LOG", "profil", "tage"]
