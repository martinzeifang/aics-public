"""Risikobewertung-Adapter für die zentrale Word-Vorlagen-Engine (#997, Story 9).

Stellt den Kontext-Builder ``build_risikobewertung_context`` und die
Variablen-Schema-Liste ``RISIKOBEWERTUNG_VARIABLES`` bereit, die von
``shared.templates.schema`` über *guarded imports* aggregiert werden.

Der Kontext ist robust für Jinja-Rendering: es kommen **keine ``None``-Werte**
vor — fehlende Felder werden auf leere Strings/Listen/0 normalisiert.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

# ── Variablen-Schema ────────────────────────────────────────────────────────
# Ein Eintrag: {"key", "typ", "beschreibung", "pflicht"}.
RISIKOBEWERTUNG_VARIABLES: list[dict[str, Any]] = [
    {"key": "projekt.name", "typ": "text",
     "beschreibung": "Name des Risikobewertungs-Projekts", "pflicht": True},
    {"key": "projekt.framework", "typ": "text",
     "beschreibung": "Verwendetes Bewertungs-Framework (TARA, STRIDE, …)",
     "pflicht": True},
    {"key": "projekt.beschreibung", "typ": "text",
     "beschreibung": "Beschreibung/Scope des Projekts", "pflicht": False},
    {"key": "projekt.unternehmen", "typ": "text",
     "beschreibung": "Unternehmen/Auftraggeber", "pflicht": False},
    {"key": "projekt.produkt", "typ": "text",
     "beschreibung": "Bewertetes Produkt", "pflicht": False},
    {"key": "projekt.berater", "typ": "text",
     "beschreibung": "Verantwortlicher Berater/Bewerter", "pflicht": False},
    {"key": "framework", "typ": "text",
     "beschreibung": "Framework des Projekts (Kurzform, identisch zu projekt.framework)",
     "pflicht": False},
    {"key": "risiken", "typ": "liste",
     "beschreibung": "Liste der Risiken (nr, risk_name, beschreibung, framework, "
                     "risikowert, risiko_label, is_resolved, detail_text, bewertung_text)",
     "pflicht": False},
    {"key": "meta.anzahl_risiken", "typ": "zahl",
     "beschreibung": "Gesamtzahl der Risiken", "pflicht": False},
    {"key": "meta.anzahl_offen", "typ": "zahl",
     "beschreibung": "Anzahl offener (nicht erledigter) Risiken", "pflicht": False},
    {"key": "meta.anzahl_erledigt", "typ": "zahl",
     "beschreibung": "Anzahl erledigter Risiken", "pflicht": False},
    {"key": "meta.erstellt_am", "typ": "text",
     "beschreibung": "Erstellungsdatum des Exports (YYYY-MM-DD)", "pflicht": False},
]


def _s(value: Any) -> str:
    """None/leer-sicher in String wandeln."""
    if value is None:
        return ""
    return str(value)


def _i(value: Any) -> int:
    """None-sicher in Integer wandeln (0 bei nicht-numerisch)."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_risiko(risk: dict[str, Any]) -> dict[str, Any]:
    """Ein Risiko-Record in einen Jinja-sicheren Dict ohne None-Werte wandeln."""
    risk = risk or {}
    felder = risk.get("felder")
    if not isinstance(felder, dict):
        felder = {}
    return {
        "nr": _i(risk.get("nr")),
        "risk_name": _s(risk.get("risk_name")),
        "beschreibung": _s(risk.get("beschreibung")),
        "framework": _s(risk.get("framework")),
        "risikowert": _i(risk.get("risikowert")),
        "risiko_label": _s(risk.get("risiko_label")),
        "is_resolved": bool(risk.get("is_resolved")),
        "resolved_reason": _s(risk.get("resolved_reason")),
        "detail_text": _s(risk.get("detail_text")),
        "bewertung_text": _s(risk.get("bewertung_text")),
        "felder": {str(k): _s(v) for k, v in felder.items()},
    }


def build_risikobewertung_context(db_path: Path | str, projekt_name: str) -> dict[str, Any]:
    """Baut den Jinja-Render-Kontext für ein Risikobewertungs-Projekt.

    Liefert immer ein vollständiges, ``None``-freies Dict — auch wenn das
    Projekt nicht existiert (dann mit leeren Defaults und dem übergebenen
    Namen). Top-Level-Keys: ``projekt``, ``risiken``, ``framework``, ``meta``.
    """
    from risikobewertung import db as _db

    db_path = Path(db_path)
    projekt_name = _s(projekt_name)

    projekt = _db.load_projekt(db_path, projekt_name) or {}
    framework = _s(projekt.get("framework"))

    try:
        risiken_raw = _db.load_risiken(db_path, projekt_name) or []
    except Exception:
        risiken_raw = []
    risiken = [_normalize_risiko(r) for r in risiken_raw]

    anzahl = len(risiken)
    anzahl_erledigt = sum(1 for r in risiken if r["is_resolved"])
    anzahl_offen = anzahl - anzahl_erledigt

    projekt_ctx = {
        "name": _s(projekt.get("name")) or projekt_name,
        "framework": framework,
        "beschreibung": _s(projekt.get("beschreibung")),
        "unternehmen": _s(projekt.get("unternehmen")),
        "produkt": _s(projekt.get("produkt")),
        "berater": _s(projekt.get("berater")),
    }

    return {
        "projekt": projekt_ctx,
        "framework": framework,
        "risiken": risiken,
        "meta": {
            "anzahl_risiken": anzahl,
            "anzahl_offen": anzahl_offen,
            "anzahl_erledigt": anzahl_erledigt,
            "erstellt_am": datetime.now().strftime("%Y-%m-%d"),
        },
    }
