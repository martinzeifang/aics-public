"""Schutz vor CSV-/Formula-Injection beim Schreiben von Excel-/CSV-Zellen (Issue #804).

Hintergrund: Beginnt ein Zellwert mit ``=``, ``+``, ``-``, ``@`` (oder Tab/CR/LF),
interpretieren Tabellenkalkulationen (Excel, LibreOffice, Google Sheets) den Inhalt
beim Öffnen als Formel. Über `=HYPERLINK`, `=cmd|...`, DDE u. ä. kann das zur
Ausführung schädlicher Inhalte oder zur Datenexfiltration führen
(OWASP „CSV Injection" / „Formula Injection").

Gegenmaßnahme (OWASP-Empfehlung): gefährdete Werte mit einem führenden
einfachen Anführungszeichen (`'`) versehen. Excel zeigt den Text dann unverändert
an, wertet ihn aber nicht als Formel.

Nur Strings werden behandelt. Zahlen, Datumswerte, Booleans und ``None`` bleiben
unverändert (sie sind nicht als Formel interpretierbar und sollen ihren Typ behalten).
"""

from __future__ import annotations

from typing import Any

# Zeichen, die am Zeilenanfang eine Formel-Interpretation auslösen können.
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r", "\n")


def safe_cell_value(value: Any) -> Any:
    """Neutralisiert Formula-Injection in einem Zellwert.

    - Nicht-Strings (int/float/bool/None/datetime/…) werden unverändert zurückgegeben.
    - Strings, deren erstes Zeichen ein Formel-Trigger ist, werden mit ``'`` geprefixt.
    - Bereits geprefixte oder unkritische Strings bleiben unverändert.
    """
    if not isinstance(value, str):
        return value
    if value and value[0] in _FORMULA_TRIGGERS:
        return "'" + value
    return value
