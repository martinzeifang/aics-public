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
    ("wiba", "wiba.template_context", "WIBA_VARIABLES", "build_wiba_context"),
    ("nis2", "nis2.template_context", "NIS2_VARIABLES", "build_nis2_context"),
    ("aiact", "ai_act.template_context", "AIACT_VARIABLES", "build_aiact_context"),
    ("dsgvo", "dsgvo.template_context", "DSGVO_VARIABLES", "build_dsgvo_context"),
    ("risikobewertung", "risikobewertung.template_context",
     "RISIKOBEWERTUNG_VARIABLES", "build_risikobewertung_context"),
    ("soc", "soc.template_context", "SOC_VARIABLES", "build_soc_context"),
    ("compliance_audit", "compliance_audit.template_context",
     "COMPLIANCE_AUDIT_VARIABLES", "build_compliance_audit_context"),
]

#: Alle registrierten Modulschlüssel. Die REST-Schicht
#: (``server/api/templates``) und das Admin-UI müssen jeden davon kennen —
#: ein Adapter ohne Verdrahtung antwortet sonst mit 404/403 (#1731).
MODULE: tuple[str, ...] = tuple(m for m, _, _, _ in _ADAPTERS)

#: Datenbank je Modul — hier, nicht in der REST-Schicht, weil inzwischen zwei
#: Aufrufer sie brauchen (``server/api/templates`` und die Berichts-Center-Brücke
#: ``shared/reports/vorlagen.py``, #1735). Eine zweite Kopie wäre die sechste
#: Spiegel-Liste derselben Zuordnung gewesen (#1731).
MODULE_DB: dict[str, Path] = {
    "cra": Path("data/db/cra.sqlite"),
    "wiba": Path("data/db/wiba.sqlite"),
    "nis2": Path("data/db/nis2.sqlite"),
    "aiact": Path("data/db/ai_act.sqlite"),
    "dsgvo": Path("data/db/dsgvo.sqlite"),
    "risikobewertung": Path("data/db/risikobewertung.sqlite"),
    "soc": Path("data/db/soc.sqlite"),
    # Historischer Dateiname: die Audit-Tabellen liegen in der Gutachten-DB (#1713).
    "compliance_audit": Path("data/db/gutachten.sqlite"),
}


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


def berichte_typen(modul: str) -> list[dict[str, Any]]:
    """Berichtstypen eines Moduls — für die Frage „für welchen Bericht?" (#1777).

    Der Pfad wird aus dem Adapter-Eintrag **abgeleitet**
    (``ai_act.template_context`` → ``ai_act.berichte_provider``), statt eine
    neunte Spiegel-Liste zu führen; die Modulschlüssel laufen hier bekanntlich
    auseinander (``aiact`` ↔ ``ai_act``, #1735). Ohne Berichts-Center kommt eine
    leere Liste — dann bleibt es bei „gilt für alle Berichte".
    """
    for m, path, _, _ in _ADAPTERS:
        if m != modul:
            continue
        fn = _load_attr(path.rsplit(".", 1)[0] + ".berichte_provider", "catalog")
        if fn is None:
            return []
        try:
            return [s.as_dict() for s in (fn() or [])]
        except Exception:  # noqa: BLE001 — ein kaputter Katalog darf den Upload nicht stoppen
            return []
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
