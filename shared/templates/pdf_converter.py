"""DOCX→PDF-Konversion (#990 / #1032).

Primär über einen **separaten Gotenberg-Container** (HTTP-API) — so bleibt das
App-Image schlank und LibreOffice muss nicht bei jedem App-Update gezogen werden.
Fallback auf lokales ``soffice`` (Entwicklungsmaschine), falls Gotenberg nicht
erreichbar ist und LibreOffice lokal installiert ist.

Konfiguration über ``GOTENBERG_URL`` (Default ``http://gotenberg:3000``).

**Die Zeitgrenzen hängen voneinander ab (#1903).** Gotenberg hat ein eigenes
Zeitlimit (``--api-timeout``, in ``docker-compose.yml`` auf 120 s). Gibt *unser*
Client vorher auf, bricht die HTTP-Verbindung ab (Gotenberg protokolliert
``status 499``) — der laufende ``soffice.bin`` läuft aber **weiter**. Ein so
verwaister Prozess hält das LibreOffice-Benutzerprofil, und **jede** weitere
Umwandlung endet mit ``supervisor run task: unix process error`` → HTTP 500.
Genau das ist auf Produktiv passiert: 28 Minuten hängender Prozess, danach
scheiterte jede PDF-Erzeugung der ganzen Installation.

Die Regel daraus: **Der Client darf nie vor dem Server aufgeben.** Sie wird hier
erzwungen (:func:`_wirksames_timeout`) und nicht dem Aufrufer überlassen — ein
zu kleiner Wert ist keine Einstellung, sondern ein Defekt mit Folgen für alle
weiteren Umwandlungen. Dieselbe Lehre wie #1807: Eine Zeit- oder Größengrenze
muss gegen **alle** Schichten geprüft werden, nicht nur gegen die eigene.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import uuid
from pathlib import Path

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_log = logging.getLogger(__name__)

#: Gotenbergs eigenes Zeitlimit (``--api-timeout``). **Eine** Zahl für beide
#: Seiten: ``docker-compose.yml`` setzt daraus den Schalter des Containers und
#: gibt sie dem Webdienst als Umgebungsvariable mit. Stünde sie zweimal, liefen
#: die Werte auseinander — und das Auseinanderlaufen ist genau der Defekt
#: (#1731/#1735 in der teuren Variante).
API_TIMEOUT_ENV = "GOTENBERG_API_TIMEOUT_S"
API_TIMEOUT_DEFAULT_S = 120

#: Zuschlag auf Gotenbergs Zeitlimit, damit der Server zuerst abbricht und
#: seinen LibreOffice-Prozess selbst aufräumt. 15 s deckt Verbindungsaufbau,
#: Übertragung des DOCX und die Antwort ab.
PUFFER_S = 15


class PDFConversionError(Exception):
    """Basisklasse für PDF-Konversionsfehler."""


class PDFConversionUnavailable(PDFConversionError):
    """Weder Gotenberg erreichbar noch lokales LibreOffice installiert."""


class PDFConversionTimeout(PDFConversionError):
    """Die Konversion hat das Zeitlimit überschritten."""

    def __init__(self, nachricht: str, *, timeout_s: int = 0) -> None:
        super().__init__(nachricht)
        #: Sekunden, die gewartet wurden — damit die Meldung an den Anwender die
        #: Zahl nennen kann, statt sie aus dem Text zu klauben.
        self.timeout_s = timeout_s


class PDFConversionFailed(PDFConversionError):
    """Der Konverter brach mit einem Fehler ab."""

    def __init__(self, nachricht: str, *, grund: str = "", status: int = 0) -> None:
        super().__init__(nachricht)
        #: Klartext des Konverters. Der Anwender erfährt sonst nie, *warum* die
        #: Umwandlung scheiterte — bis #1903 stand das nur im Server-Log, an das
        #: er nicht herankommt.
        self.grund = grund or nachricht
        #: HTTP-Status des Konverters (0 beim lokalen ``soffice``).
        self.status = status


def gotenberg_url() -> str:
    return os.environ.get("GOTENBERG_URL", "http://gotenberg:3000").rstrip("/")


def api_timeout_s() -> int:
    """Gotenbergs ``--api-timeout`` in Sekunden (aus der Umgebung, sonst Default)."""
    roh = (os.environ.get(API_TIMEOUT_ENV) or "").strip()
    try:
        wert = int(roh)
    except ValueError:
        return API_TIMEOUT_DEFAULT_S
    return wert if wert > 0 else API_TIMEOUT_DEFAULT_S


def mindest_client_timeout_s() -> int:
    """Kleinstes Client-Zeitlimit, das Gotenberg zuerst abbrechen lässt."""
    return api_timeout_s() + PUFFER_S


def _wirksames_timeout(gewuenscht: int) -> int:
    """Hebt ein zu kleines Client-Zeitlimit auf die Untergrenze an.

    Ein Wert unter Gotenbergs eigenem Limit ist nie richtig: Er lässt einen
    ``soffice``-Prozess verwaisen, der dann **jede** weitere Umwandlung der
    Installation scheitern lässt. Der Schutz gehört deshalb hierher und nicht in
    die 20 Aufrufer (dieselbe Begründung wie bei ``save_konformitaet`` in #1805).
    """
    mindest = mindest_client_timeout_s()
    if gewuenscht < mindest:
        _log.debug("PDF-Zeitlimit %ss < Gotenberg-Limit — auf %ss angehoben (#1903)",
                   gewuenscht, mindest)
        return mindest
    return gewuenscht


def konverter_status(timeout_s: int = 3) -> dict:
    """Zustand des Konverters — **gemessen**, nicht vermutet (#1903).

    Nur ``libreoffice`` zählt: Die DOCX→PDF-Route nutzt ausschließlich
    LibreOffice; ein Gotenberg mit ausgefallenem Chromium wandelt unsere
    Dokumente trotzdem um. Den Chromium-Zustand als Mangel zu melden hieße,
    einen Alarm für etwas zu geben, das wir nicht benutzen (die Lehre aus
    #1774/#1877: ein Prüfpunkt, der bei richtigem Verhalten anschlägt, wird
    abgeschaltet).
    """
    status: dict = {
        "gotenberg_url": gotenberg_url(),
        "erreichbar": False,
        "libreoffice": "unbekannt",
        "version": "",
        "lokales_soffice": shutil.which("soffice") is not None,
        "api_timeout_s": api_timeout_s(),
        "client_timeout_s": mindest_client_timeout_s(),
        "meldung": "",
    }
    try:
        import requests
        r = requests.get(f"{gotenberg_url()}/health", timeout=timeout_s)
        status["erreichbar"] = r.status_code == 200
        if r.status_code == 200:
            daten = r.json() if r.content else {}
            details = (daten.get("details") or {}) if isinstance(daten, dict) else {}
            lo = (details.get("libreoffice") or {}) if isinstance(details, dict) else {}
            status["libreoffice"] = str(lo.get("status") or "unbekannt")
        else:
            status["meldung"] = f"/health antwortete HTTP {r.status_code}"
    except Exception as exc:  # noqa: BLE001 — Netzfehler sind hier ein Zustand
        status["meldung"] = f"{type(exc).__name__}: {exc}"
    if status["erreichbar"]:
        try:
            import requests
            v = requests.get(f"{gotenberg_url()}/version", timeout=timeout_s)
            if v.status_code == 200:
                status["version"] = v.text.strip()[:40]
        except Exception:  # noqa: BLE001
            pass
    status["bereit"] = bool(
        (status["erreichbar"] and status["libreoffice"] != "down")
        or status["lokales_soffice"]
    )
    return status


def is_gotenberg_available(timeout_s: int = 3) -> bool:
    try:
        import requests
        r = requests.get(f"{gotenberg_url()}/health", timeout=timeout_s)
        return r.status_code == 200
    except Exception:
        return False


def is_soffice_available() -> bool:
    """Kompat-Name: True, wenn überhaupt PDF erzeugt werden kann
    (Gotenberg erreichbar ODER lokales soffice vorhanden)."""
    return is_gotenberg_available() or shutil.which("soffice") is not None


def _convert_via_gotenberg(docx_bytes: bytes, *, timeout_s: int) -> bytes:
    import requests
    url = f"{gotenberg_url()}/forms/libreoffice/convert"
    files = {"files": ("input.docx", docx_bytes, _DOCX_MIME)}
    wirksam = _wirksames_timeout(timeout_s)
    try:
        resp = requests.post(url, files=files, timeout=wirksam)
    except requests.Timeout as exc:
        raise PDFConversionTimeout(f"Gotenberg > {wirksam}s", timeout_s=wirksam) from exc
    except requests.RequestException as exc:
        # Verbindungsfehler → vom Aufrufer als „nicht erreichbar" behandelt
        raise ConnectionError(str(exc)) from exc
    if resp.status_code == 504:
        # Gotenberg hat sein eigenes Limit gerissen und aufgeräumt — das ist der
        # gewollte Weg, seit der Client länger wartet als der Server.
        raise PDFConversionTimeout(
            f"Gotenberg brach nach seinem Zeitlimit ab (HTTP 504)",
            timeout_s=api_timeout_s())
    if resp.status_code != 200:
        text = (resp.text or "").strip()[:300]
        raise PDFConversionFailed(
            f"Gotenberg HTTP {resp.status_code}: {text}",
            grund=text, status=resp.status_code)
    return resp.content


def _convert_via_local_soffice(docx_bytes: bytes, *, timeout_s: int) -> bytes:
    if not shutil.which("soffice"):
        raise PDFConversionUnavailable("Gotenberg nicht erreichbar und kein lokales LibreOffice")
    try:
        from server.api.workspace_tmp import workspace_tmpdir
        tmp_root = Path(workspace_tmpdir())
    except Exception:
        tmp_root = Path("data/tmp"); tmp_root.mkdir(parents=True, exist_ok=True)
    work = tmp_root / f"pdfconv_{uuid.uuid4().hex}"
    work.mkdir(parents=True, exist_ok=True)
    infile = work / "input.docx"
    try:
        infile.write_bytes(docx_bytes)
        try:
            # ``subprocess.run`` beendet den Prozess bei Zeitüberschreitung selbst —
            # hier kann also kein verwaister soffice zurückbleiben (anders als beim
            # HTTP-Weg oben, siehe Modul-Docstring).
            proc = subprocess.run(
                ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(work), str(infile)],
                capture_output=True, timeout=timeout_s,
                env={"HOME": str(work), "PATH": "/usr/bin:/bin:/usr/local/bin"})
        except subprocess.TimeoutExpired as exc:
            raise PDFConversionTimeout(f"soffice > {timeout_s}s", timeout_s=timeout_s) from exc
        if proc.returncode != 0:
            stderr = (proc.stderr or b'').decode('utf-8', 'replace')[:300]
            raise PDFConversionFailed(
                f"soffice exit {proc.returncode}: {stderr}", grund=stderr)
        pdf = work / "input.pdf"
        if not pdf.exists():
            raise PDFConversionFailed("soffice erzeugte keine PDF-Datei",
                                      grund="soffice erzeugte keine PDF-Datei")
        return pdf.read_bytes()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def convert_docx_to_pdf(docx_bytes: bytes, *, timeout_s: int = 0) -> bytes:
    """Konvertiert DOCX→PDF. Primär Gotenberg, Fallback lokales soffice.

    ``timeout_s`` ist eine **Untergrenze-geprüfte** Angabe: 0 (Vorgabe) nimmt
    Gotenbergs Zeitlimit plus Puffer, ein kleinerer Wert wird angehoben. Warum,
    steht im Modul-Docstring — ein Client, der vor dem Server aufgibt, legt die
    PDF-Erzeugung der ganzen Installation lahm.
    """
    gewuenscht = timeout_s if timeout_s > 0 else mindest_client_timeout_s()
    try:
        return _convert_via_gotenberg(docx_bytes, timeout_s=gewuenscht)
    except ConnectionError:
        # Gotenberg nicht erreichbar → lokaler Fallback (oder Unavailable)
        return _convert_via_local_soffice(docx_bytes, timeout_s=gewuenscht)
