"""Eine Übersetzung von PDF-Konversionsfehlern in HTTP-Antworten (#1903).

**Der Befund:** 13 Endpunkte erzeugten PDF, und fast jeder gab für **jeden**
Fehler denselben Satz aus:

    PDF-Konverter ist derzeit nicht verfügbar — bitte als Word (DOCX)
    exportieren.

Auf Produktiv war der Konverter **verfügbar** (``/health`` → 200,
``libreoffice: up``, Version 8.39.0); ein hängender ``soffice.bin`` ließ jede
Umwandlung mit HTTP 500 scheitern. Die Meldung schickte den Anwender auf einen
Weg, der die Ursache nicht berührt, und der echte Grund stand nur in einem
Server-Log, an das er nicht herankommt. Das ist die Klasse aus #1805 und #1827:
**Es wird das Falsche gelesen bzw. gesagt, und nichts schlägt fehl.**

Die Regel, die daraus folgt und die dieses Modul erzwingt: **„nicht verfügbar"
darf nur dastehen, wenn das geprüft wurde.** Drei Fälle, drei Antworten:

===========================  ======  ====================================
Ausnahme                     Status  Bedeutung für den Anwender
===========================  ======  ====================================
``PDFConversionUnavailable``    503  Konverter nicht erreichbar
``PDFConversionTimeout``        504  hat zu lange gebraucht
``PDFConversionFailed``         502  Konverter antwortet, Umwandlung scheitert
===========================  ======  ====================================

Modell für diese Aufteilung war ``server/api/templates/__init__.py``, das sie
als einziger Endpunkt schon hatte (dort allerdings ``PDFConversionFailed`` → 500
ohne Grund). Eine zweite Fassung je Endpunkt wäre die Spiegel-Liste aus
#1731/#1735 — mit dem Unterschied, dass hier nicht eine Funktion ausfällt,
sondern eine **Falschaussage** an den Anwender geht.
"""
from __future__ import annotations

from typing import Any

#: Maschinenlesbare Kennungen (Muster ``code`` wie bei
#: ``issue-tracker-nicht-konfiguriert`` in #1815). Das Frontend soll nicht am
#: deutschen Text erkennen müssen, was passiert ist.
CODE_NICHT_ERREICHBAR = "pdf-konverter-nicht-erreichbar"
CODE_ZEITLIMIT = "pdf-zeitlimit"
CODE_FEHLGESCHLAGEN = "pdf-umwandlung-fehlgeschlagen"


def pdf_fehler_antwort(exc: Exception) -> tuple[dict[str, Any], int]:
    """Übersetzt einen Konversionsfehler in ``(payload, status)``.

    Ist ``exc`` kein ``PDFConversionError``, kommt ``(…, 0)`` zurück — der
    Aufrufer behandelt ihn dann wie bisher. So lässt sich dieses Modul in ein
    bestehendes ``except Exception`` einhängen, ohne dessen übrige Fälle zu
    verändern.
    """
    from shared.templates.pdf_converter import (
        PDFConversionError, PDFConversionFailed, PDFConversionTimeout,
        PDFConversionUnavailable)

    if not isinstance(exc, PDFConversionError):
        return {}, 0

    if isinstance(exc, PDFConversionUnavailable):
        return {
            "error": "Der PDF-Konverter ist nicht erreichbar. Das Word-Dokument "
                     "(DOCX) lässt sich weiter herunterladen.",
            "code": CODE_NICHT_ERREICHBAR,
            "hinweis": "Ein Administrator kann den Zustand unter "
                       "Administration → Einstellungen → PDF-Konverter prüfen.",
        }, 503

    if isinstance(exc, PDFConversionTimeout):
        sek = getattr(exc, "timeout_s", 0) or 0
        dauer = f" nach {sek} Sekunden" if sek else ""
        return {
            "error": f"Die Umwandlung in PDF wurde{dauer} abgebrochen, weil sie "
                     "zu lange gedauert hat. Bei einem sehr großen Dokument hilft "
                     "der Word-Export (DOCX); sonst bitte erneut versuchen.",
            "code": CODE_ZEITLIMIT,
            "timeout_s": sek,
        }, 504

    # PDFConversionFailed — und alles sonst unter PDFConversionError.
    grund = str(getattr(exc, "grund", "") or exc).strip()[:300]
    return {
        # Der Grund des Konverters gehört in die Meldung: Genau sein Fehlen hat
        # die Suche bei #1903 in die falsche Richtung geschickt. Die Anwendung ist
        # authentifiziert und admin-nah; ein Konverter-Klartext ist hier kein
        # Geheimnis, aber er bleibt ein **eigenes Feld**, damit die Oberfläche
        # entscheidet, wie prominent sie ihn zeigt.
        "error": "Der PDF-Konverter hat die Umwandlung abgelehnt. "
                 "Das Word-Dokument (DOCX) lässt sich weiter herunterladen.",
        "code": CODE_FEHLGESCHLAGEN,
        "grund": grund,
        "hinweis": "Tritt das bei jedem Dokument auf, hängt meist ein "
                   "LibreOffice-Prozess im Konverter-Container; ein Neustart des "
                   "Konverters behebt es.",
    }, 502


def ist_pdf_fehler(exc: Exception) -> bool:
    """True, wenn ``exc`` von :func:`pdf_fehler_antwort` behandelt wird."""
    try:
        from shared.templates.pdf_converter import PDFConversionError
    except Exception:  # noqa: BLE001 — Import darf einen Handler nie aufreißen
        return False
    return isinstance(exc, PDFConversionError)
