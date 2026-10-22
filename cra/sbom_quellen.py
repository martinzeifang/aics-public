"""SBOM-Dateien dort einlesen, wo sie ohnehin liegen (#1769).

Der Autodetect fand bisher nur **wo** eine SBOM liegt — Release-Asset,
CI-Artefakt, Workflow-Datei — und trug `komponenten_count: 0`, `lizenzen: []`
ein. Der Rest war Handarbeit: Format, Anzahl, Lizenzen tippen, und die
Komponentenliste (#1761) blieb leer, weil ihr die Datei fehlte.

Aus der Rückmeldung des Anwenders: „Ich finde die Software sollte das auch
finden, wenn es an der richtigen Stelle liegt."

ZUR ABGRENZUNG GEGEN #1761
Dort wurde ein serverseitiger Abruf **bewusst ausgeschlossen**: Die SBOM wird
nicht aus `blob_path` nachgeladen, weil das eine vom Anwender eingetippte URL
ist — ein beliebiger Host, also der klassische SSRF-Weg. Diese Entscheidung
steht und wird hier nicht aufgeweicht.

Was hier passiert, ist etwas anderes:

* **Ziel ist fest.** Gesprochen wird ausschließlich mit ``api.github.com``.
  Der Pfad wird aus ``owner``/``repo`` des **für das Projekt konfigurierten**
  Repositorys und der numerischen Asset-ID gebaut, die die GitHub-API selbst
  geliefert hat. Aus einer Antwort wird nie eine URL übernommen.
* **Dieselbe Vertrauensgrenze**, die der Schwachstellen-Sync seit #937 benutzt:
  dasselbe Repo, dasselbe Token.
* **Begrenzt.** Es wird höchstens :data:`MAX_BYTES` gelesen und abgebrochen,
  bevor etwas geparst wird.

Dazu der zweite, einfachere Weg: ein **Ablageort im Dateisystem**. Was unter
``data/cra/sbom/<projekt>/`` liegt, wird gefunden — ohne Repo, ohne Netz. Das
ist „die richtige Stelle" für eine Installation ohne angebundenes Repository.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

#: Mehr als das wird nicht gelesen. Gleiche Grenze wie der Import-Endpunkt
#: (#1761) — eine SBOM, die größer ist, gehört nicht ungefragt in den Speicher.
MAX_BYTES = 8 * 1024 * 1024

#: Ablageort für Installationen ohne angebundenes Repository.
LOKAL_BASIS = Path("data/cra/sbom")

_GH_API = "https://api.github.com"
_ASSET_PFAD = re.compile(r"^[A-Za-z0-9._-]+$")


def _sicherer_name(wert: str) -> str:
    """Owner/Repo dürfen nur aus unverfänglichen Zeichen bestehen.

    Sie stammen aus der Projekt-Konfiguration, also aus einer Eingabe. Ein
    ``../`` oder ein ``@host`` darin würde den Pfad verbiegen, den wir gerade
    selbst bauen — die Prüfung kostet nichts und nimmt dem Rest die Frage ab.
    """
    s = str(wert or "").strip()
    if not s or not _ASSET_PFAD.match(s):
        raise ValueError(f"Unzulässiger Repository-Bestandteil: {wert!r}")
    return s


def lade_release_asset(owner: str, repo: str, asset_id: int | str) -> str | None:
    """Inhalt eines Release-Assets über die GitHub-API holen.

    Gibt ``None`` zurück, wenn nichts zu holen ist (kein Token, 404, zu groß,
    Netzfehler). Das ist bewusst still: Der Autodetect soll weiterlaufen und
    den Fund als Pfad eintragen, auch wenn der Inhalt nicht lesbar war.
    """
    try:
        import requests
        from shared.github_config import get_github_token, github_headers
    except Exception as e:  # noqa: BLE001
        log.debug("GitHub-Zugang nicht verfügbar: %s", e)
        return None

    if not get_github_token():
        # Ohne Token kein Asset-Download: Die Asset-API verlangt
        # Authentifizierung, und ein anonymer Umweg über eine Download-URL
        # wäre genau der Abruf, den wir nicht wollen.
        return None

    try:
        owner = _sicherer_name(owner)
        repo = _sicherer_name(repo)
        aid = int(asset_id)
    except (ValueError, TypeError) as e:
        log.debug("Asset-Bezug unbrauchbar: %s", e)
        return None

    url = f"{_GH_API}/repos/{owner}/{repo}/releases/assets/{aid}"
    kopf = dict(github_headers())
    kopf["Accept"] = "application/octet-stream"
    try:
        with requests.get(url, headers=kopf, timeout=30, stream=True) as r:
            if r.status_code >= 300:
                log.debug("Asset %s: HTTP %s", aid, r.status_code)
                return None
            roh = bytearray()
            for stueck in r.iter_content(chunk_size=65536):
                roh.extend(stueck)
                if len(roh) > MAX_BYTES:
                    log.info("SBOM-Asset %s über %s Bytes — abgebrochen", aid, MAX_BYTES)
                    return None
        return roh.decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        log.debug("Asset %s nicht ladbar: %s", aid, e)
        return None


def auswerten(inhalt: str) -> dict[str, Any] | None:
    """SBOM-Inhalt zu den Feldern machen, die sonst von Hand einzutragen sind.

    Liefert ``None``, wenn der Inhalt keine lesbare SBOM ist — dann bleibt der
    Fund ein Pfad, und niemand bekommt eine halbe Komponentenliste, die wie
    eine vollständige aussieht (dieselbe Regel wie beim Import, #1761).
    """
    try:
        from cra.sbom_komponenten import parse_sbom

        komponenten, fmt = parse_sbom(inhalt)
    except Exception as e:  # noqa: BLE001
        log.debug("SBOM nicht auswertbar: %s", e)
        return None
    if not komponenten:
        return None

    lizenzen = sorted({str(k.get("lizenz") or "").strip()
                       for k in komponenten if str(k.get("lizenz") or "").strip()})
    return {
        "sbom_format": fmt,
        "komponenten_count": len(komponenten),
        "lizenzen": lizenzen,
        "komponenten": komponenten,
    }


def finde_lokal(projekt_name: str, basis: Path | None = None) -> list[dict[str, Any]]:
    """SBOMs aus dem Ablageort im Dateisystem lesen.

    Erwartet ``<basis>/<projekt>/<version>.<format>.json``; die Version wird
    aus dem Dateinamen genommen (``gateway-1.9.0.cdx.json`` → ``1.9.0``).
    Lässt sich keine Version erkennen, wird der Dateiname ohne Endung genommen
    — eine erfundene Version wäre schlimmer als eine unschöne.
    """
    wurzel = Path(basis or LOKAL_BASIS) / _dateiname(projekt_name)
    if not wurzel.is_dir():
        return []

    funde: list[dict[str, Any]] = []
    for pfad in sorted(wurzel.glob("*.json")):
        try:
            if pfad.stat().st_size > MAX_BYTES:
                log.info("SBOM %s über %s Bytes — übersprungen", pfad, MAX_BYTES)
                continue
            inhalt = pfad.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            log.debug("SBOM %s nicht lesbar: %s", pfad, e)
            continue
        ausgewertet = auswerten(inhalt)
        if not ausgewertet:
            continue
        funde.append({
            "release_version": _version_aus_name(pfad.name),
            # #1771: Der Teil **vor** der Version benennt das Artefakt
            # (`gateway-1.9.0.cdx.json` → `gateway`). Mehrere Artefakte je
            # Release sind damit unterscheidbar, ohne dass jemand etwas tippt.
            "artefakt": _artefakt_aus_name(pfad.name),
            "sbom_datum": _datum(pfad),
            "quelle": f"auto:lokal:{pfad.name}",
            "blob_path": str(pfad),
            "notizen": f"Aus dem Ablageort gelesen ({pfad.parent}).",
            **ausgewertet,
        })
    return funde


def _dateiname(wert: str) -> str:
    """Projektname → Verzeichnisname, ohne Pfadtrenner."""
    s = re.sub(r"[\\/:*?\"<>|]", "-", str(wert or "")).strip()
    return re.sub(r"\s+", "_", s).strip("._") or "unbenannt"


def _artefakt_aus_name(name: str) -> str:
    """Artefakt-Name aus dem Dateinamen: alles vor der Versionsnummer.

    ``gateway-1.9.0.cdx.json`` → ``gateway``. Ohne erkennbare Version bleibt
    das Feld leer — ein geratener Name wäre schlechter als keiner.
    """
    m = re.search(r"^(.*?)[-_.]?(\d+\.\d+(?:\.\d+)?)", name)
    if m and m.group(1).strip("-_. "):
        return m.group(1).strip("-_. ")
    return ""


def _version_aus_name(name: str) -> str:
    m = re.search(r"(\d+\.\d+(?:\.\d+)?(?:[-+][\w.]+)?)", name)
    if m:
        return m.group(1)
    return re.sub(r"\.(spdx|cdx|cyclonedx)?\.?json$", "", name, flags=re.IGNORECASE)


def _datum(pfad: Path) -> str:
    from datetime import datetime, timezone

    try:
        return datetime.fromtimestamp(pfad.stat().st_mtime,
                                      tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return ""


__all__ = ["MAX_BYTES", "LOKAL_BASIS", "lade_release_asset", "auswerten", "finde_lokal"]
