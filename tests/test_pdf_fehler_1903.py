"""#1903 — „Konverter nicht verfügbar" muss geprüft sein, sonst nicht gesagt.

Der gemeldete Fall: Beim Speichern des SBOM-Begleitdokuments als PDF erschien
„PDF-Konverter ist derzeit nicht verfügbar — bitte als Word (DOCX)
exportieren." Der Konverter **war** verfügbar (``/health`` → 200,
``libreoffice: up``, 8.39.0 auf allen vier Instanzen); ein seit 28 Minuten
hängender ``soffice.bin`` ließ jede Umwandlung mit HTTP 500 scheitern.

Dieser Wächter hält vier Dinge fest, die beim Nachsehen gefunden wurden:

1. Die drei Fälle werden **unterschieden** (503/504/502) und der Grund des
   Konverters wird weitergegeben.
2. Das **Client-Zeitlimit liegt über Gotenbergs** ``--api-timeout``. Das ist die
   Ursache des verwaisten Prozesses, und es ist eine Beziehung zwischen zwei
   Dateien — genau die Art Aussage, die ohne Prüfer auseinanderläuft (#1807).
3. Kein Endpunkt sagt mehr pauschal „nicht verfügbar".
4. Die **Statusabfrage** bewertet nur LibreOffice, nicht Chromium.

Geprüft wird jeweils das **Programm**, nicht die Erzählung: Kommentare dürfen
die alten Texte zitieren (sie tun es, als Begründung), ohne den Test grün oder
rot zu machen. Diese Lehre hat sich beim Bauen bestätigt — ein Skript, das auf
das Vorkommen von ``utils/pdfFehler`` prüfte, traf den eigenen Kommentar und
ließ fünf Importe aus; gefunden hat das der Typprüfer aus #1858.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]


def _ohne_kommentare_py(text: str) -> str:
    return "\n".join(z for z in text.splitlines()
                     if not z.lstrip().startswith("#"))


def _ohne_kommentare_ts(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(z for z in text.splitlines()
                     if not z.lstrip().startswith("//"))


# ── 1. Die drei Fälle ───────────────────────────────────────────────────

def test_die_drei_faelle_haben_drei_verschiedene_status():
    from shared.pdf_fehler import pdf_fehler_antwort
    from shared.templates.pdf_converter import (
        PDFConversionFailed, PDFConversionTimeout, PDFConversionUnavailable)

    _, s_unavail = pdf_fehler_antwort(PDFConversionUnavailable("weg"))
    _, s_timeout = pdf_fehler_antwort(PDFConversionTimeout("zu lang", timeout_s=135))
    _, s_failed = pdf_fehler_antwort(PDFConversionFailed("abgelehnt", grund="HTTP 500"))

    assert (s_unavail, s_timeout, s_failed) == (503, 504, 502), (
        "503 nicht erreichbar · 504 Zeitlimit · 502 Konverter lehnt ab — "
        "vorher war alles 503 (bzw. 500) und damit die Falschaussage")


def test_der_grund_des_konverters_kommt_beim_anwender_an():
    """Sein Fehlen hat die Suche in die falsche Richtung geschickt."""
    from shared.pdf_fehler import pdf_fehler_antwort
    from shared.templates.pdf_converter import PDFConversionFailed

    nutzlast, status = pdf_fehler_antwort(
        PDFConversionFailed("Gotenberg HTTP 500: supervisor run task",
                            grund="supervisor run task: unix process error",
                            status=500))
    assert status == 502
    assert "supervisor run task" in nutzlast["grund"]
    # Und die Meldung behauptet NICHT, der Konverter sei nicht erreichbar.
    assert "nicht erreichbar" not in nutzlast["error"]


def test_nur_bei_unavailable_steht_nicht_erreichbar():
    from shared.pdf_fehler import pdf_fehler_antwort
    from shared.templates.pdf_converter import (
        PDFConversionFailed, PDFConversionTimeout, PDFConversionUnavailable)

    nutzlast, _ = pdf_fehler_antwort(PDFConversionUnavailable("weg"))
    assert "nicht erreichbar" in nutzlast["error"]
    for exc in (PDFConversionTimeout("x", timeout_s=1),
                PDFConversionFailed("y", grund="z")):
        nutzlast, _ = pdf_fehler_antwort(exc)
        assert "nicht erreichbar" not in nutzlast["error"], type(exc).__name__


def test_das_zeitlimit_steht_in_der_meldung():
    from shared.pdf_fehler import pdf_fehler_antwort
    from shared.templates.pdf_converter import PDFConversionTimeout

    nutzlast, _ = pdf_fehler_antwort(PDFConversionTimeout("x", timeout_s=135))
    assert "135" in nutzlast["error"]
    assert nutzlast["timeout_s"] == 135


def test_fremde_ausnahme_wird_nicht_angefasst():
    """Damit sich das Modul in ein bestehendes ``except Exception`` einhängen lässt."""
    from shared.pdf_fehler import ist_pdf_fehler, pdf_fehler_antwort

    nutzlast, status = pdf_fehler_antwort(ValueError("etwas anderes"))
    assert (nutzlast, status) == ({}, 0)
    assert ist_pdf_fehler(ValueError("x")) is False


# ── 2. Die Reihenfolge der Zeitlimits (die eigentliche Ursache) ─────────

def _api_timeout_aus_compose() -> int:
    compose = (WURZEL / "docker-compose.yml").read_text(encoding="utf-8")
    treffer = re.search(r'--api-timeout=\$\{GOTENBERG_API_TIMEOUT_S:-(\d+)\}s', compose)
    assert treffer, ("Gotenbergs --api-timeout muss aus GOTENBERG_API_TIMEOUT_S "
                     "kommen — eine zweite Zahl läuft auseinander, und genau das "
                     "Auseinanderlaufen ist der Defekt")
    return int(treffer.group(1))


def test_der_client_wartet_laenger_als_gotenberg():
    """**Der Kern von #1903.**

    Gotenberg durfte 120 s arbeiten, der Client gab nach 60 s auf. Der Abbruch
    beendet den laufenden ``soffice.bin`` nicht (Gotenberg protokolliert
    ``status 499``); der verwaiste Prozess hält das LibreOffice-Profil, und jede
    weitere Umwandlung endet mit HTTP 500 — für die **ganze** Installation.

    Die Regel: Der Server muss zuerst abbrechen, damit er selbst aufräumt.
    """
    from shared.templates.pdf_converter import (
        API_TIMEOUT_DEFAULT_S, mindest_client_timeout_s)

    assert API_TIMEOUT_DEFAULT_S == _api_timeout_aus_compose(), (
        "Der Default im Code und die Zahl im Compose müssen übereinstimmen")
    assert mindest_client_timeout_s() > API_TIMEOUT_DEFAULT_S, (
        "Der Client muss länger warten als Gotenberg — sonst bleiben "
        "soffice-Prozesse zurück")


def test_ein_zu_kleines_zeitlimit_wird_angehoben():
    """Der Schutz gehört in die Funktion, nicht in die 20 Aufrufer (#1805)."""
    from shared.templates.pdf_converter import (
        _wirksames_timeout, mindest_client_timeout_s)

    mindest = mindest_client_timeout_s()
    assert _wirksames_timeout(1) == mindest
    assert _wirksames_timeout(60) == mindest, (
        "60 s war der alte Default und ist kleiner als Gotenbergs Limit")
    assert _wirksames_timeout(mindest + 100) == mindest + 100, (
        "Ein großzügigerer Wert bleibt unangetastet")


def test_der_bestandsaufrufer_mit_90s_wird_mitgeschuetzt():
    """``docx_bytes_to_pdf`` reicht 90 s durch — auch das ist zu wenig."""
    import inspect

    from shared.reports import docx_pdf
    from shared.templates.pdf_converter import (
        _wirksames_timeout, mindest_client_timeout_s)

    quelle = inspect.getsource(docx_pdf.docx_bytes_to_pdf)
    treffer = re.search(r"timeout_s: int = (\d+)", quelle)
    assert treffer, "Signatur von docx_bytes_to_pdf unerwartet"
    assert _wirksames_timeout(int(treffer.group(1))) == mindest_client_timeout_s()


# ── 3. Kein Endpunkt sagt mehr pauschal „nicht verfügbar" ───────────────

#: Hier darf der Satz stehen: die **eine** Übersetzung und ihr Frontend-Pendant.
ERLAUBT = {
    "shared/pdf_fehler.py",
    "frontend/src/utils/pdfFehler.ts",
}


def test_kein_endpunkt_behauptet_pauschal_nicht_verfuegbar():
    funde = []
    for muster in ("server/api/**/*.py", "shared/**/*.py"):
        for datei in WURZEL.glob(muster):
            rel = datei.relative_to(WURZEL).as_posix()
            if rel in ERLAUBT:
                continue
            text = _ohne_kommentare_py(datei.read_text(encoding="utf-8"))
            if "PDF-Konverter nicht verfügbar" in text:
                funde.append(rel)
    assert not funde, (
        "Diese Stellen behaupten weiter ungeprüft, der Konverter sei nicht "
        f"verfügbar: {funde}. Die Übersetzung gehört in shared/pdf_fehler.py.")


def test_das_frontend_erfindet_keinen_text_fuer_503():
    funde = []
    for endung in ("*.ts", "*.vue"):
        for datei in (WURZEL / "frontend" / "src").rglob(endung):
            rel = datei.relative_to(WURZEL).as_posix()
            if rel in ERLAUBT:
                continue
            text = _ohne_kommentare_ts(datei.read_text(encoding="utf-8"))
            if ("PDF-Konverter nicht verfügbar" in text
                    or "PDF-Konverter ist derzeit nicht" in text):
                funde.append(rel)
    assert not funde, (
        "Diese Masken übersetzen einen Status wieder selbst in "
        f"„Konverter nicht verfügbar': {funde}. "
        "utils/pdfFehler.pdfFehlerText nimmt die Aussage des Servers.")


def test_die_blob_antwort_wird_ausgepackt():
    """Ohne das käme die Servermeldung nie an (die Falle aus #1735/#1841)."""
    quelle = (WURZEL / "frontend/src/utils/pdfFehler.ts").read_text(encoding="utf-8")
    programm = _ohne_kommentare_ts(quelle)
    assert "instanceof Blob" in programm and ".text()" in programm, (
        "Alle Export-Aufrufe nutzen responseType:'blob' — eine Fehlerantwort "
        "ist dann ein Blob und muss ausgepackt werden")


def test_kein_dsgvo_endpunkt_faengt_den_pdf_fehler_als_runtimeerror():
    """Der Zweig war **toter Code**: ``PDFConversionError`` erbt von ``Exception``.

    Jeder PDF-Fehler fiel dort in ``_log_500`` → HTTP 500 „Interner
    Serverfehler". Das Frontend wartete auf 503 und bekam nie eines.
    """
    from shared.templates.pdf_converter import PDFConversionError
    assert not issubclass(PDFConversionError, RuntimeError), (
        "Erbt der Fehler plötzlich von RuntimeError, greifen alte "
        "except-RuntimeError-Zweige wieder und geben ihre Falschmeldung aus")

    funde = []
    for datei in (WURZEL / "server" / "api").glob("dsgvo_*.py"):
        text = datei.read_text(encoding="utf-8")
        if ("convert_docx_to_pdf" not in text and "build_pdf" not in text
                and "_pdf(" not in text):
            continue
        if "except RuntimeError as e:" in text and "PDFConversionError" not in text:
            funde.append(datei.name)
    assert not funde, f"PDF-Fehler werden hier nie gefangen: {funde}"


# ── 4. Die Statusabfrage ────────────────────────────────────────────────

def test_der_status_bewertet_libreoffice_und_nicht_chromium(monkeypatch):
    """Die DOCX-Route nutzt nur LibreOffice.

    Ein Gotenberg mit ausgefallenem Chromium wandelt unsere Dokumente trotzdem
    um; ihn als defekt zu melden wäre ein Alarm für etwas, das wir nicht
    benutzen (#1774/#1877).
    """
    import requests

    import shared.templates.pdf_converter as pc

    class Antwort:
        status_code = 200
        content = b"{}"
        text = "8.39.0"

        def __init__(self, daten):
            self._daten = daten

        def json(self):
            return self._daten

    def gefaelscht(url, timeout=0):
        if url.endswith("/health"):
            return Antwort({"status": "up", "details": {
                "chromium": {"status": "down"},
                "libreoffice": {"status": "up"}}})
        return Antwort({})

    monkeypatch.setattr(requests, "get", gefaelscht)
    status = pc.konverter_status()
    assert status["libreoffice"] == "up"
    assert status["bereit"] is True, "Chromium down darf uns nicht stören"


def test_libreoffice_down_heisst_nicht_bereit(monkeypatch):
    import requests

    import shared.templates.pdf_converter as pc

    class Antwort:
        status_code = 200
        content = b"{}"
        text = ""

        def json(self):
            return {"status": "down", "details": {"libreoffice": {"status": "down"}}}

    monkeypatch.setattr(requests, "get", lambda url, timeout=0: Antwort())
    monkeypatch.setattr(pc.shutil, "which", lambda _n: None)
    status = pc.konverter_status()
    assert status["libreoffice"] == "down"
    assert status["bereit"] is False


def test_unerreichbarer_dienst_ist_ein_zustand_und_kein_absturz(monkeypatch):
    import requests

    import shared.templates.pdf_converter as pc

    def wirft(url, timeout=0):
        raise requests.ConnectionError("Name oder Dienst nicht bekannt")

    monkeypatch.setattr(requests, "get", wirft)
    monkeypatch.setattr(pc.shutil, "which", lambda _n: None)
    status = pc.konverter_status()
    assert status["erreichbar"] is False
    assert status["bereit"] is False
    assert "ConnectionError" in status["meldung"]


def test_die_statusabfrage_wandelt_nichts_um():
    """Ein Testlauf im Fehlerfall würde das Problem vergrößern."""
    import inspect

    import shared.templates.pdf_converter as pc
    quelle = _ohne_kommentare_py(inspect.getsource(pc.konverter_status))
    assert "convert" not in quelle, (
        "Die Statusabfrage darf keine Umwandlung starten — sie kostet im "
        "Fehlerfall das Zeitlimit und beschäftigt selbst einen LibreOffice")


# ── 5. Das Netz im errorhandler ─────────────────────────────────────────

def test_der_errorhandler_uebersetzt_den_pdf_fehler():
    """Damit jeder **künftige** PDF-Endpunkt richtig antwortet (#1815-Muster)."""
    quelle = _ohne_kommentare_py(
        (WURZEL / "server" / "app.py").read_text(encoding="utf-8"))
    assert "ist_pdf_fehler" in quelle and "pdf_fehler_antwort" in quelle


@pytest.mark.parametrize("exc_name,status", [
    ("PDFConversionUnavailable", 503),
    ("PDFConversionTimeout", 504),
    ("PDFConversionFailed", 502),
])
def test_der_errorhandler_wirkt_wirklich(exc_name, status):
    """Verhaltensprobe statt Textsuche — ein Wächter prüft das Programm."""
    from flask import Flask

    import shared.templates.pdf_converter as pc
    from shared.pdf_fehler import ist_pdf_fehler, pdf_fehler_antwort

    app = Flask(__name__)

    @app.errorhandler(Exception)
    def _handle(exc):  # dieselbe Logik wie in server/app.py
        if ist_pdf_fehler(exc):
            nutzlast, st = pdf_fehler_antwort(exc)
            return nutzlast, st
        raise exc

    @app.get("/x")
    def _x():
        raise getattr(pc, exc_name)("kaputt")

    antwort = app.test_client().get("/x")
    assert antwort.status_code == status
    assert antwort.get_json()["code"].startswith("pdf-")
