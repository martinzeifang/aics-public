"""Lightweight German-language guard for MkDocs docs.

This is intentionally simple: it fails the build if common English phrases or
section headers appear in docs/*.md. It prevents regressions where new pages are
added in English.

It is not a general language detector.
"""

from __future__ import annotations

import pathlib
import re
import sys


DOCS_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs"


_BAD_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("english-heading", re.compile(r"^#{1,6}\\s+(Goals|Scope|Implementation|Inputs|Output Schema|Troubleshooting)\\b")),
    ("english-phrase", re.compile(r"\\b(This document|The suite|Cloud mode|Safety Gate)\\b")),
]


def main() -> int:
    bad: list[str] = []
    for p in sorted(DOCS_DIR.rglob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as e:
            bad.append(f"{p}: read error: {e}")
            continue

        for i, line in enumerate(text.splitlines(), start=1):
            for tag, pat in _BAD_PATTERNS:
                if pat.search(line):
                    bad.append(f"{p.relative_to(DOCS_DIR)}:{i}: {tag}: {line.strip()}")

    if bad:
        sys.stderr.write("Docs language check failed. English fragments found:\n")
        sys.stderr.write("\n".join(bad) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
