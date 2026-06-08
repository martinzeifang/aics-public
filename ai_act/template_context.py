"""AI-Act-Adapter für die zentrale Word-Vorlagen-Engine (#995, Story 7).

Stellt den Jinja-Kontext-Builder ``build_aiact_context`` und das Variablen-Schema
``AIACT_VARIABLES`` bereit, die von ``shared/templates/schema.py`` über
``_ADAPTERS`` (Modul-Key ``aiact``) eingebunden werden.

Wichtig: Das Python-Paket heißt ``ai_act``, der Modul-Key/Funktions-/Variablen-
name verwenden jedoch durchgängig ``aiact``.

Der Kontext ist robust für Jinja: es treten **keine** ``None``-Werte auf —
fehlende Daten werden durch leere Strings, leere Listen oder leere Dicts ersetzt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import db as _db
from .requirements import (
    AI_ACT_REQUIREMENTS,
    BEWERTUNG_SKALA,
    berechne_reifegrad,
)


# ── Variablen-Schema ────────────────────────────────────────────────────────
# Ein Eintrag: {"key", "typ", "beschreibung", "pflicht"}.
AIACT_VARIABLES: list[dict[str, Any]] = [
    {"key": "projekt.name", "typ": "str", "beschreibung": "Projektname", "pflicht": True},
    {"key": "projekt.organisation", "typ": "str", "beschreibung": "Verantwortliche Organisation (Provider/Deployer)", "pflicht": False},
    {"key": "projekt.produkt", "typ": "str", "beschreibung": "Bezeichnung des AI-Systems / Produkts", "pflicht": False},
    {"key": "projekt.beschreibung", "typ": "str", "beschreibung": "Kurzbeschreibung des AI-Systems", "pflicht": False},
    {"key": "klassifizierung.risiko_stufe", "typ": "str", "beschreibung": "AI-Act-Risikostufe (z. B. hochrisiko, begrenzt, minimal)", "pflicht": False},
    {"key": "klassifizierung.risiko_label", "typ": "str", "beschreibung": "Lesbares Label der Risikostufe", "pflicht": False},
    {"key": "klassifizierung.ist_hochrisiko", "typ": "bool", "beschreibung": "True, wenn als Hochrisiko klassifiziert", "pflicht": False},
    {"key": "klassifizierung.begruendung", "typ": "str", "beschreibung": "Begründung der Klassifizierung", "pflicht": False},
    {"key": "klassifizierung.intended_purpose", "typ": "str", "beschreibung": "Zweckbestimmung des AI-Systems", "pflicht": False},
    {"key": "anforderungen", "typ": "list", "beschreibung": "Liste der AI-Act-Anforderungen mit Bewertung/Maßnahme", "pflicht": False},
    {"key": "meta.gesamt_pct", "typ": "float", "beschreibung": "Gewichteter Gesamt-Reifegrad in Prozent", "pflicht": False},
    {"key": "meta.ampel", "typ": "str", "beschreibung": "Ampelstatus (gruen/orange/rot)", "pflicht": False},
    {"key": "meta.bewertete_count", "typ": "int", "beschreibung": "Anzahl bewerteter Anforderungen", "pflicht": False},
    {"key": "meta.gesamt_count", "typ": "int", "beschreibung": "Gesamtzahl der Anforderungen", "pflicht": False},
    {"key": "meta.kapitel_pct", "typ": "dict", "beschreibung": "Reifegrad je Kapitel (HR/GOV/DATA/OPS)", "pflicht": False},
]


# Mögliche Risikostufen → lesbares Label
_RISIKO_LABELS: dict[str, str] = {
    "verboten": "Verbotenes KI-System (Art. 5)",
    "unannehmbar": "Unannehmbares Risiko (Art. 5)",
    "hochrisiko": "Hochrisiko-KI-System (Art. 6 / Annex III)",
    "high": "Hochrisiko-KI-System (Art. 6 / Annex III)",
    "begrenzt": "Begrenztes Risiko (Transparenzpflichten, Art. 50)",
    "limited": "Begrenztes Risiko (Transparenzpflichten, Art. 50)",
    "minimal": "Minimales Risiko",
    "gering": "Minimales Risiko",
}


def _s(value: Any) -> str:
    """None-sicherer String."""
    if value is None:
        return ""
    return str(value)


def _klassifizierung(projekt: dict[str, Any]) -> dict[str, Any]:
    """Baut den Klassifizierungs-Block aus Projekt-Stammdaten + meta.

    Die Risikostufe wird primär aus ``meta`` gelesen (verschiedene mögliche
    Schlüssel), da das Klassifizierungs-Ergebnis dort persistiert wird.
    """
    meta = projekt.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}

    raw_stufe = _s(
        meta.get("risiko_stufe")
        or meta.get("risikostufe")
        or meta.get("risk_level")
        or meta.get("klassifizierung")
    ).strip()

    norm = raw_stufe.lower()
    label = _RISIKO_LABELS.get(norm, raw_stufe)
    ist_hochrisiko = norm in ("hochrisiko", "high", "verboten", "unannehmbar")

    return {
        "risiko_stufe": raw_stufe,
        "risiko_label": label,
        "ist_hochrisiko": bool(ist_hochrisiko),
        "begruendung": _s(meta.get("klassifizierung_begruendung") or meta.get("begruendung")),
        "intended_purpose": _s(meta.get("intended_purpose") or meta.get("zweck")),
    }


def _anforderungen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Anforderungskatalog angereichert mit den gespeicherten Bewertungen."""
    try:
        bewertungen = _db.load_bewertungen(db_path, projekt_name)
    except Exception:
        bewertungen = {}

    out: list[dict[str, Any]] = []
    for req in AI_ACT_REQUIREMENTS:
        rid = _s(req.get("id"))
        bew_row = bewertungen.get(rid) or {}
        bew_val = int(bew_row.get("bewertung", 0) or 0)
        skala = BEWERTUNG_SKALA.get(bew_val, BEWERTUNG_SKALA[0])
        out.append(
            {
                "id": rid,
                "kapitel": _s(req.get("kapitel")),
                "titel": _s(req.get("titel")),
                "beschreibung": _s(req.get("beschreibung")),
                "hinweise": _s(req.get("hinweise")),
                "bewertung": bew_val,
                "bewertung_label": _s(skala.get("label")),
                "reife_pct": int(skala.get("reife_pct", 0) or 0),
                "kommentar": _s(bew_row.get("kommentar")),
                "massnahme": _s(bew_row.get("massnahme")),
                "ref": _s(req.get("ref")),
            }
        )
    return out


def build_aiact_context(db_path: Path | str, projekt_name: str) -> dict[str, Any]:
    """Baut den Jinja-Kontext für die AI-Act-Word-Vorlage.

    Liefert immer eine vollständige, ``None``-freie Struktur — auch wenn das
    Projekt (noch) nicht existiert.
    """
    db_path = Path(db_path)
    name = _s(projekt_name).strip()

    try:
        projekt = _db.load_projekt(db_path, name) or {}
    except Exception:
        projekt = {}

    projekt_ctx = {
        "name": _s(projekt.get("name") or name),
        "organisation": _s(projekt.get("organisation")),
        "produkt": _s(projekt.get("produkt")),
        "beschreibung": _s(projekt.get("beschreibung")),
    }

    anforderungen = _anforderungen(db_path, name)
    bew_map = {a["id"]: a["bewertung"] for a in anforderungen}
    reifegrad = berechne_reifegrad(bew_map, AI_ACT_REQUIREMENTS)

    meta_ctx = {
        "gesamt_pct": float(reifegrad.get("gesamt_pct", 0.0) or 0.0),
        "ampel": _s(reifegrad.get("ampel") or "rot"),
        "bewertete_count": int(reifegrad.get("bewertete_count", 0) or 0),
        "gesamt_count": int(reifegrad.get("gesamt_count", 0) or 0),
        "kapitel_pct": dict(reifegrad.get("kapitel_pct") or {}),
    }

    return {
        "projekt": projekt_ctx,
        "klassifizierung": _klassifizierung(projekt),
        "anforderungen": anforderungen,
        "meta": meta_ctx,
    }
