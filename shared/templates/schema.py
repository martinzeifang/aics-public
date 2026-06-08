"""Pro-Modul-Variablen-Schemas + Kontext-Builder-Dispatch (#989).

Die einzelnen Modul-Adapter (Stories 5–9) definieren ihre Variablenliste
``<MODUL>_VARIABLES`` und ihren Kontext-Builder ``build_<modul>_context`` in
``<modul>/template_context.py``. Dieses Modul aggregiert sie über *guarded
imports*, sodaß ein noch nicht implementierter Adapter den Rest nicht bricht.

Ein Variablen-Eintrag: ``{"key": str, "typ": str, "beschreibung": str, "pflicht": bool}``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

# (modul, python-modulpfad, VARIABLES-Attr, builder-Attr)
_ADAPTERS: list[tuple[str, str, str, str]] = [
    ("cra", "cra.template_context", "CRA_VARIABLES", "build_cra_context"),
    ("nis2", "nis2.template_context", "NIS2_VARIABLES", "build_nis2_context"),
    ("aiact", "ai_act.template_context", "AIACT_VARIABLES", "build_aiact_context"),
    ("dsgvo", "dsgvo.template_context", "DSGVO_VARIABLES", "build_dsgvo_context"),
    ("risikobewertung", "risikobewertung.template_context",
     "RISIKOBEWERTUNG_VARIABLES", "build_risikobewertung_context"),
]


def _load_attr(module_path: str, attr: str):
    import importlib
    try:
        mod = importlib.import_module(module_path)
    except Exception:
        return None
    return getattr(mod, attr, None)


def get_variables(modul: str) -> list[dict[str, Any]]:
    """Variablen-Schema eines Moduls (leere Liste, wenn Adapter fehlt)."""
    for m, path, var_attr, _ in _ADAPTERS:
        if m == modul:
            return list(_load_attr(path, var_attr) or [])
    return []


def get_context_builder(modul: str) -> Callable[[Path, str], dict[str, Any]] | None:
    """Kontext-Builder eines Moduls oder None (→ 501 Not Implemented)."""
    for m, path, _, builder_attr in _ADAPTERS:
        if m == modul:
            return _load_attr(path, builder_attr)
    return None


def context_builders() -> dict[str, Callable[[Path, str], dict[str, Any]]]:
    """Dispatch-Map aller verfügbaren Kontext-Builder."""
    out: dict[str, Callable[[Path, str], dict[str, Any]]] = {}
    for m, path, _, builder_attr in _ADAPTERS:
        fn = _load_attr(path, builder_attr)
        if fn is not None:
            out[m] = fn
    return out
