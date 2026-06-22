"""G0-1 — Geteilte Normen-Library.

Wird von beiden Generatoren (Audit-Bericht + Gerichtsgutachten) genutzt.
Datenquelle: gutachten/data/normen.json (versioniert).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).parent / "data" / "normen.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    # Ausfallsicher: fehlt/defekt die Datendatei (z. B. in einem Build, der
    # gutachten/data/ nicht enthält), liefert die Library eine leere Normen-Liste
    # statt einen 500 zu werfen. Alle Aufrufer nutzen .get("normen", []).
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def list_normen() -> list[dict[str, Any]]:
    """Alle Normen als Kurz-Index."""
    data = _load()
    return [
        {
            "id": n["id"],
            "titel": n["titel"],
            "version": n.get("version", ""),
            "domain": n.get("domain", ""),
            "soll_kurz": n.get("soll_kurz", ""),
            "kategorien_anzahl": len(n.get("kategorien", [])),
        }
        for n in data.get("normen", [])
    ]


def get_norm(norm_id: str) -> dict[str, Any] | None:
    """Voll-Detail einer Norm (inkl. Kategorien + Sub-Merkmale)."""
    if not norm_id:
        return None
    for n in _load().get("normen", []):
        if n.get("id") == norm_id:
            return n
    return None


def get_sub_merkmal(norm_id: str, sub_id: str) -> dict[str, Any] | None:
    """Ein einzelnes Sub-Merkmal — für Beurteilungs-Referenzen."""
    n = get_norm(norm_id)
    if not n:
        return None
    for k in n.get("kategorien", []):
        for s in k.get("sub_merkmale", []):
            if s.get("id") == sub_id:
                return {
                    "norm_id": norm_id,
                    "norm_titel": n.get("titel"),
                    "kategorie_id": k.get("id"),
                    "kategorie_name": k.get("name"),
                    **s,
                }
    return None


def search_normen(query: str) -> list[dict[str, Any]]:
    """Volltextsuche über Titel + Kategorien + Sub-Merkmale.

    Liefert {norm_id, titel, treffer: [{kategorie_id, kategorie_name, sub_id, sub_name}]}.
    """
    if not query or not query.strip():
        return []
    q = query.strip().lower()
    out: list[dict[str, Any]] = []
    for n in _load().get("normen", []):
        treffer: list[dict[str, Any]] = []
        for k in n.get("kategorien", []):
            if q in k.get("name", "").lower() or q in k.get("id", "").lower():
                treffer.append({
                    "kategorie_id": k.get("id"),
                    "kategorie_name": k.get("name"),
                    "sub_id": None,
                    "sub_name": None,
                })
            for s in k.get("sub_merkmale", []):
                hay = " ".join(filter(None, [s.get("name", ""), s.get("id", ""), s.get("beschreibung", "")]))
                if q in hay.lower():
                    treffer.append({
                        "kategorie_id": k.get("id"),
                        "kategorie_name": k.get("name"),
                        "sub_id": s.get("id"),
                        "sub_name": s.get("name"),
                    })
        if treffer or q in n.get("titel", "").lower() or q in n.get("id", "").lower():
            out.append({"norm_id": n.get("id"), "titel": n.get("titel"), "treffer": treffer})
    return out


def reload_cache() -> None:
    """Cache zurücksetzen (für Tests / Hot-Reload)."""
    _load.cache_clear()
