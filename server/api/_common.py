"""Gemeinsame Helfer für die API-Blueprints.

Konsolidiert die zuvor pro Modul duplizierten ``_require_<modul>_projekt``-
Helfer (DSGVO, NIS2, AI-Act, CRA …). Das Verhalten ist identisch zu den
früheren Einzel-Implementierungen: Projekt laden und bei Nichtexistenz eine
404-JSON-Antwort als Fehler zurückgeben.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Tuple

from flask import jsonify


def require_projekt(
    load_projekt: Callable[[Path, str], Any],
    db_path: Path,
    projekt_name: str,
) -> Tuple[Optional[Any], Optional[Tuple[Any, int]]]:
    """Lädt ein Projekt oder liefert eine 404-Fehlerantwort.

    Rückgabe: ``(projekt, None)`` bei Erfolg, sonst ``(None, (response, 404))``.
    Das entspricht exakt dem Vertrag der vormaligen ``_require_*_projekt``-Helfer.
    """
    p = load_projekt(db_path, projekt_name)
    if not p:
        return None, (
            jsonify({'error': f'Projekt "{projekt_name}" nicht gefunden'}),
            404,
        )
    return p, None
