"""SBOM aus der Container-Registry holen (#1770).

Für ein Container-Produkt liegt die SBOM oft **nicht als Datei**: Sie hängt als
signierte Attestation am Image. Genau so macht es diese Suite selbst — der
Build-Workflow setzt bewusst ``upload-release-assets: false``, weil eine SBOM
ein Image beschreibt und nicht einen Git-Tag; als Attestation ist sie an den
Digest gebunden statt eine lose Behauptung daneben zu sein.

Die Folge war eine Lücke: #1769 liest Release-Assets und Dateien aus einem
Verzeichnis — beides setzt eine Datei voraus. Wer sein Produkt als Image
ausliefert, musste die SBOM von Hand mit ``cosign`` herausziehen.

WIE DAS GEHT (reine Registry-API, kein cosign, kein Docker)
1. ``GET /v2/<repo>/manifests/<tag>`` → Digest des Images.
2. cosign legt die Attestation unter dem **Tag** ``sha256-<digest>.att`` ab.
3. Dessen erster Layer ist ein DSSE-Envelope; ``payload`` ist base64-kodiert
   und enthält eine in-toto-Aussage mit dem SPDX-Dokument als ``predicate``.

ZUM HOST — DAS IST HIER DIE EIGENTLICHE ENTSCHEIDUNG
Die Registry steht in einer **Eingabe** (dem Feld „Pfad zur SBOM-Datei"). Ein
Abruf gegen einen frei wählbaren Host wäre genau der SSRF-Weg, den #1761
ausgeschlossen und #1769 bewusst umgangen hat. Deshalb gilt hier eine
**Positivliste**: Es wird nur mit Registries gesprochen, die in
``cra.config.json → sbom.registries`` stehen (Default ``ghcr.io``). Wer eine
eigene Registry nutzt, trägt sie dort ein — eine bewusste Entscheidung des
Betreibers, keine Nebenwirkung einer Formulareingabe.

Dazu: nur ``https``, Umleitungen nur zu erlaubten Hosts bzw. zum
Blob-Speicher der Registry, Größendeckel **vor** dem Verarbeiten.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger(__name__)

#: Gleicher Deckel wie beim Datei-Import (#1761/#1769).
MAX_BYTES = 8 * 1024 * 1024

#: Ohne Konfiguration wird nur mit GHCR gesprochen.
STANDARD_REGISTRIES = ("ghcr.io",)

#: Blob-Speicher je Registry. Eine Registry legt die eigentlichen Daten
#: bauartbedingt woanders ab und leitet dorthin um — GHCR auf
#: ``pkg-containers.githubusercontent.com``. Diese Hosts gehören deshalb in die
#: Positivliste, sonst scheitert jeder Abruf an der eigenen Prüfung. Sie
#: **aufzuweichen** (Umleitungen einfach zu folgen) wäre der falsche Ausweg:
#: Dann bestimmte die Antwort der Gegenstelle, wohin wir als Nächstes sprechen.
STANDARD_SPEICHER: dict[str, tuple[str, ...]] = {
    "ghcr.io": ("pkg-containers.githubusercontent.com",),
    "registry.gitlab.com": ("storage.googleapis.com",),
}

#: ``<host>/<pfad>`` mit ``:tag`` oder ``@sha256:…``
_REF = re.compile(
    r"^(?:oci://)?(?P<host>[a-z0-9.\-]+(?::\d+)?)/"
    r"(?P<repo>[a-z0-9._\-/]+?)"
    r"(?::(?P<tag>[\w][\w.\-]*))?"
    r"(?:@sha256:(?P<digest>[0-9a-f]{64}))?$",
    re.IGNORECASE)


class RegistryFehler(RuntimeError):
    """Abruf nicht möglich — mit einem Text, der sagt warum."""


def erlaubte_registries() -> tuple[str, ...]:
    """Positivliste aus der Konfiguration, sonst der Default."""
    try:
        from pathlib import Path

        from cra.config import load_config

        cfg = load_config(Path("cra.config.json")) or {}
        werte = ((cfg.get("sbom") or {}).get("registries")) or []
        sauber = tuple(str(w).strip().lower() for w in werte if str(w).strip())
        if sauber:
            return sauber
    except Exception as e:  # noqa: BLE001 — eine kaputte Konfig darf nicht öffnen
        log.debug("sbom.registries nicht lesbar: %s", e)
    return STANDARD_REGISTRIES


def ist_image_referenz(wert: Any) -> bool:
    """Sieht der Wert nach einer OCI-Referenz aus (und nicht nach einer URL)?"""
    s = str(wert or "").strip()
    if not s or s.startswith(("http://", "https://")) or s.startswith("/"):
        return False
    m = _REF.match(s)
    return bool(m and "/" in s and ("." in m.group("host") or ":" in m.group("host")))


def zerlege(referenz: str) -> dict[str, str]:
    """Referenz in Host, Repository und Tag/Digest zerlegen — mit Host-Prüfung."""
    s = str(referenz or "").strip()
    m = _REF.match(s)
    if not m:
        raise RegistryFehler(f"Keine gültige Image-Referenz: {referenz!r}")
    host = m.group("host").lower()
    erlaubt = erlaubte_registries()
    if host not in erlaubt:
        raise RegistryFehler(
            f"Registry '{host}' steht nicht in der Positivliste. "
            f"Erlaubt sind: {', '.join(erlaubt)}. "
            f"Eintragen unter cra.config.json → sbom.registries.")
    return {"host": host, "repo": m.group("repo"),
            "tag": m.group("tag") or "latest", "digest": m.group("digest") or ""}


def erlaubte_hosts(host: str) -> set[str]:
    """Alle Hosts, mit denen für diese Registry gesprochen werden darf.

    Das ist die Registry selbst plus ihr Blob-Speicher (siehe
    :data:`STANDARD_SPEICHER`), erweiterbar über
    ``cra.config.json → sbom.storage_hosts`` für eigene Registries.
    """
    erlaubt = set(erlaubte_registries()) | {host}
    for reg in list(erlaubt):
        erlaubt |= set(STANDARD_SPEICHER.get(reg, ()))
    try:
        from pathlib import Path

        from cra.config import load_config

        cfg = load_config(Path("cra.config.json")) or {}
        zusatz = ((cfg.get("sbom") or {}).get("storage_hosts")) or []
        erlaubt |= {str(h).strip().lower() for h in zusatz if str(h).strip()}
    except Exception as e:  # noqa: BLE001
        log.debug("sbom.storage_hosts nicht lesbar: %s", e)
    return erlaubt


def _pruefe_url(url: str, host: str) -> None:
    """Nur https, und nur zu einem Host, mit dem wir sprechen dürfen.

    Greift auch bei **Umleitungen** — und das ist der Punkt: Gefolgt wird nur
    einer Umleitung zu einem Host, der vorher feststand. Sonst bestimmte die
    Antwort der Gegenstelle, wohin wir als Nächstes sprechen, und die
    Positivliste wäre wertlos.
    """
    p = urlparse(url)
    if p.scheme != "https":
        raise RegistryFehler(f"Nur https erlaubt, nicht {p.scheme!r}")
    ziel = (p.hostname or "").lower()
    erlaubt = erlaubte_hosts(host)
    if not any(ziel == h or ziel.endswith("." + h) for h in erlaubt):
        raise RegistryFehler(f"Umleitung auf nicht erlaubten Host: {ziel}")


def _token(host: str, repo: str) -> str:
    """Pull-Token holen. Für öffentliche Pakete reicht ein anonymes."""
    import requests

    url = f"https://{host}/token?scope=repository:{repo}:pull&service={host}"
    _pruefe_url(url, host)
    try:
        r = requests.get(url, timeout=30)
        if r.status_code >= 300:
            return ""
        return str((r.json() or {}).get("token") or "")
    except Exception as e:  # noqa: BLE001
        log.debug("Token für %s/%s nicht erhältlich: %s", host, repo, e)
        return ""


def _hole(url: str, host: str, token: str, accept: str | None = None) -> bytes:
    import requests

    _pruefe_url(url, host)
    kopf = {"Authorization": f"Bearer {token}"} if token else {}
    if accept:
        kopf["Accept"] = accept
    r = requests.get(url, headers=kopf, timeout=60, stream=True, allow_redirects=False)
    # Umleitungen selbst prüfen, statt requests folgen zu lassen.
    while r.status_code in (301, 302, 303, 307, 308):
        ziel = r.headers.get("Location") or ""
        r.close()
        _pruefe_url(ziel, host)
        r = requests.get(ziel, timeout=60, stream=True, allow_redirects=False)
    if r.status_code >= 300:
        r.close()
        raise RegistryFehler(f"Registry antwortet mit HTTP {r.status_code}")
    roh = bytearray()
    for stueck in r.iter_content(chunk_size=65536):
        roh.extend(stueck)
        if len(roh) > MAX_BYTES:
            r.close()
            raise RegistryFehler(
                f"Attestation über {MAX_BYTES // 1024 // 1024} MB — abgebrochen")
    r.close()
    return bytes(roh)


_MANIFEST_ACCEPT = ("application/vnd.oci.image.index.v1+json,"
                    "application/vnd.docker.distribution.manifest.list.v2+json,"
                    "application/vnd.oci.image.manifest.v1+json,"
                    "application/vnd.docker.distribution.manifest.v2+json")


def hole_sbom(referenz: str) -> dict[str, Any]:
    """SPDX-Dokument der am Image hängenden Attestation holen.

    Returns:
        ``{"inhalt": <json-text>, "digest": "sha256:…", "referenz": …}``

    Raises:
        RegistryFehler: Host nicht erlaubt, nichts gefunden, zu groß, Netz.
    """
    import requests

    teile = zerlege(referenz)
    host, repo = teile["host"], teile["repo"]
    token = _token(host, repo)

    # 1. Digest des Images bestimmen
    digest = teile["digest"]
    if not digest:
        url = f"https://{host}/v2/{repo}/manifests/{teile['tag']}"
        _pruefe_url(url, host)
        kopf = {"Accept": _MANIFEST_ACCEPT}
        if token:
            kopf["Authorization"] = f"Bearer {token}"
        try:
            r = requests.head(url, headers=kopf, timeout=30)
            if r.status_code >= 300:
                r = requests.get(url, headers=kopf, timeout=30)
        except Exception as e:  # noqa: BLE001
            raise RegistryFehler(f"Manifest nicht abrufbar: {e}") from e
        if r.status_code in (401, 403):
            # #1823: „nicht gefunden" war hier eine Behauptung, die die Suche in
            # die falsche Richtung schickt. Eine Registry **verrät nicht**, ob
            # ein nicht zugängliches Paket existiert — sonst ließen sich private
            # Paketnamen abfragen. 401/403 heißt deshalb genau zweierlei, und
            # die Meldung muss beides nennen statt sich für eins zu entscheiden.
            raise RegistryFehler(
                f"Die Registry gibt {teile['host']}/{teile['repo']}:{teile['tag']} "
                f"nicht heraus (HTTP {r.status_code}). Entweder gibt es das Paket "
                f"unter diesem Namen nicht, oder es ist nicht öffentlich — die "
                f"Registry unterscheidet das bewusst nicht. Prüfen Sie den Namen; "
                f"öffentliche Pakete sind ohne Zugangsdaten lesbar.")
        if r.status_code >= 300:
            raise RegistryFehler(
                f"Image {teile['repo']}:{teile['tag']} nicht gefunden (HTTP {r.status_code})")
        digest = (r.headers.get("docker-content-digest") or "").replace("sha256:", "")
        if not digest:
            raise RegistryFehler("Registry nennt keinen Digest zum Image")

    # 2. Attestation unter dem cosign-Tag
    att_url = f"https://{host}/v2/{repo}/manifests/sha256-{digest}.att"
    try:
        manifest = json.loads(_hole(att_url, host, token,
                                    "application/vnd.oci.image.manifest.v1+json"))
    except RegistryFehler:
        raise
    except Exception as e:  # noqa: BLE001
        raise RegistryFehler(f"Attestation nicht lesbar: {e}") from e

    layers = manifest.get("layers") or []
    if not layers:
        raise RegistryFehler(
            "Zum Image existiert keine SBOM-Attestation "
            "(cosign-Tag vorhanden, aber ohne Inhalt).")

    # 3. DSSE-Envelope → in-toto-Aussage → SPDX
    letzter_fehler = "kein SPDX-Dokument in der Attestation"
    for layer in layers:
        try:
            blob = _hole(f"https://{host}/v2/{repo}/blobs/{layer['digest']}", host, token)
            env = json.loads(blob)
            aussage = json.loads(base64.b64decode(env["payload"]))
        except Exception as e:  # noqa: BLE001
            letzter_fehler = f"Envelope nicht lesbar: {e}"
            continue
        art = str(aussage.get("predicateType") or "")
        if "spdx" not in art.lower():
            letzter_fehler = f"Attestation ist kein SPDX ({art or 'ohne Typ'})"
            continue
        pred = aussage.get("predicate") or {}
        spdx = pred.get("Data") if isinstance(pred, dict) and "Data" in pred else pred
        if isinstance(spdx, str):
            inhalt = spdx
        else:
            inhalt = json.dumps(spdx, ensure_ascii=False)
        return {"inhalt": inhalt, "digest": f"sha256:{digest}",
                "referenz": f"{host}/{repo}@sha256:{digest}"}

    raise RegistryFehler(letzter_fehler)


__all__ = ["MAX_BYTES", "STANDARD_REGISTRIES", "STANDARD_SPEICHER", "RegistryFehler",
           "erlaubte_registries", "erlaubte_hosts", "ist_image_referenz",
           "zerlege", "hole_sbom"]
