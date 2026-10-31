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


def pdf_fehler(exc: Exception, kontext: str = '') -> Tuple[Any, int]:
    """PDF-Konversionsfehler → JSON-Antwort mit **unterschiedenem** Status (#1903).

    Für Endpunkte, die den Fehler selbst fangen müssen, weil ein äußeres
    ``except Exception`` ihn sonst zu einem 500 macht. Wer nichts fängt, wird
    vom ``errorhandler`` in :mod:`server.app` genauso behandelt — die
    Übersetzung selbst steht nur in :mod:`shared.pdf_fehler`.
    """
    from flask import current_app

    from shared.pdf_fehler import pdf_fehler_antwort

    nutzlast, status = pdf_fehler_antwort(exc)
    try:
        current_app.logger.warning('PDF-Konversion%s — %s: %s',
                                   f' ({kontext})' if kontext else '',
                                   type(exc).__name__, exc)
    except Exception:  # noqa: BLE001 — ohne App-Kontext (Test) nicht protokollieren
        pass
    return jsonify(nutzlast), status
