"""Fehlerarten der Issue-Anbindung (#1815).

Eine **fehlende Konfiguration** ist kein Serverfehler. Bis v8.0.11 schlug
``RuntimeError("Kein Issue-Backend verfügbar …")`` ungefangen bis zum
Flask-Handler durch: Der Anwender bekam HTTP 500 („etwas ist kaputt"), obwohl
nur etwas nicht eingerichtet war — und jeder Klick schrieb einen Traceback ins
Log, in dem echte Fehler untergehen.

Die Unterscheidung gehört an **eine** Stelle. Die Issue-Anlage steht in neun
Modulen (cra, nis2, aiact, dsgvo, soc …); sie alle einzeln zu reparieren wäre
die nächste Spiegel-Liste (#1731/#1735). Stattdessen wirft die VCS-Schicht
einen eigenen Typ, und ``server/app.py`` übersetzt ihn einmalig in 412.
"""
from __future__ import annotations


class IssueBackendFehlt(RuntimeError):
    """Kein Issue-Tracker erreichbar — Token/CLI fehlt oder ist unvollständig.

    Erbt bewusst von ``RuntimeError``: Aufrufer, die bisher ``RuntimeError``
    fangen, verhalten sich unverändert.
    """
