"""SQL-Hilfsfunktionen (SQLite).

Ziel: sichere Verwendung dynamischer Identifiers (Tabellen-/Spaltennamen)
ohne SQL-Injection. Werte müssen weiterhin als Parameter gebunden werden.
"""

from __future__ import annotations

import re


_RE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(name: str) -> str:
    n = str(name or "").strip()
    if not n or not _RE_IDENT.match(n):
        raise ValueError(f"Ungültiger SQL-Identifier: {name!r}")
    return n


def quote_ident(name: str) -> str:
    """Quote an identifier for SQLite (double quotes).

    Only allows strict identifier charset (no dots, no spaces).
    """
    n = validate_identifier(name)
    return '"' + n.replace('"', '""') + '"'
