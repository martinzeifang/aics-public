"""Output-Encoding / Escaping Utilities (OWASP-PC-C4).

Diese Funktionen sind klein, deterministisch und kontextabhängig.
"""

from __future__ import annotations

from typing import Any


_CSV_DANGEROUS_PREFIXES = ("=", "+", "-", "@")


def escape_csv_cell(value: Any) -> str:
    """Schützt CSV/Excel vor Formula-Injection.

    Wenn ein Feld mit = + - @ beginnt, interpretiert Excel dies als Formel.
    Wir prefixen dann mit einem Apostroph.
    """
    s = "" if value is None else str(value)
    s_stripped = s.lstrip()
    if s_stripped.startswith(_CSV_DANGEROUS_PREFIXES):
        return "'" + s
    return s


def escape_markdown_codeblock(text: str) -> str:
    """Escaped Text für Markdown-Codefences.

    Verhindert das "Ausbrechen" aus ```-Codefences.
    """
    t = str(text or "")
    # Break triple-backticks deterministically.
    return t.replace("```", "``\u200b`")
