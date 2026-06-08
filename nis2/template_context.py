"""NIS2-Adapter für die zentrale Word-Vorlagen-Engine (#994, Story 6).

Stellt die beiden vom Schema-Dispatch (``shared/templates/schema.py``) erwarteten
Symbole bereit:

* :data:`NIS2_VARIABLES` – Variablen-Schema (Liste von
  ``{"key", "typ", "beschreibung", "pflicht"}``) für die Variablen-Hilfe.
* :func:`build_nis2_context` – baut aus der NIS2-SQLite-DB einen für Jinja
  robusten Render-Kontext (keine ``None``-Werte, leere Defaults statt fehlend).

Der Kontext ist bewusst flach strukturiert:

    {
      "projekt":      {...},   # Stammdaten + Reifegrad-Kennzahlen
      "meta":         {...},   # Erstelldatum, Rechtsgrundlage, Zähler
      "anforderungen":[...],   # voller Katalog inkl. Bewertung je Eintrag
      "kapitel":      [...],   # Kapitel-Übersicht mit Reifegrad je Kapitel
      "luecken":      [...],   # offene/kritische Anforderungen (Bewertung <= 2)
      "assets":       [...],   # N1 Asset-Inventar
      "risiken":      [...],   # N2 Risiko-Register
      "vendors":      [...],   # N4 Supply-Chain
      "incident_response": {...},  # N3 (1:1)
      "bcp":          {...},   # N5 (1:1)
    }
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from nis2 import db as _db
from nis2.requirements import (
    BEWERTUNG_LABELS,
    EINRICHTUNGSKLASSEN,
    KAPITEL,
    berechne_reifegrad,
    load_merged_anforderungen,
)

# ── Variablen-Schema (Variablen-Hilfe / „Verfügbare Variablen") ────────────────

NIS2_VARIABLES: list[dict[str, Any]] = [
    {"key": "projekt.name", "typ": "text",
     "beschreibung": "Name des NIS2-Projekts.", "pflicht": True},
    {"key": "projekt.unternehmen", "typ": "text",
     "beschreibung": "Name der Einrichtung / des Unternehmens.", "pflicht": True},
    {"key": "projekt.einrichtungsklasse", "typ": "text",
     "beschreibung": "Schlüssel der Einrichtungsklasse (wesentlich/wichtig/beide).",
     "pflicht": False},
    {"key": "projekt.einrichtungsklasse_label", "typ": "text",
     "beschreibung": "Anzeigename der Einrichtungsklasse.", "pflicht": False},
    {"key": "projekt.beschreibung", "typ": "text",
     "beschreibung": "Freitext-Beschreibung des Projekts.", "pflicht": False},
    {"key": "projekt.berater", "typ": "text",
     "beschreibung": "Verantwortlicher Berater.", "pflicht": False},
    {"key": "projekt.reifegrad_prozent", "typ": "zahl",
     "beschreibung": "Gesamt-Reifegrad in Prozent.", "pflicht": False},
    {"key": "projekt.reifegrad_text", "typ": "text",
     "beschreibung": "Konformitäts-Einstufung (Ampeltext) zum Reifegrad.",
     "pflicht": False},
    {"key": "projekt.gesamt_punkte", "typ": "zahl",
     "beschreibung": "Erreichte gewichtete Punkte.", "pflicht": False},
    {"key": "projekt.max_punkte", "typ": "zahl",
     "beschreibung": "Maximal erreichbare gewichtete Punkte.", "pflicht": False},
    {"key": "projekt.anzahl_anforderungen", "typ": "zahl",
     "beschreibung": "Anzahl der Anforderungen im Katalog.", "pflicht": False},
    {"key": "projekt.anzahl_bewertet", "typ": "zahl",
     "beschreibung": "Anzahl der bewerteten Anforderungen.", "pflicht": False},

    {"key": "meta.erstellt_am", "typ": "text",
     "beschreibung": "Erstelldatum (TT.MM.JJJJ).", "pflicht": False},
    {"key": "meta.rechtsgrundlage", "typ": "text",
     "beschreibung": "Zitierte Rechtsgrundlage (NIS2-Richtlinie).", "pflicht": False},

    {"key": "anforderungen", "typ": "liste",
     "beschreibung": "Anforderungskatalog; je Eintrag id, kapitel, titel, ref, "
                     "beschreibung, gewichtung, bewertung, bewertung_label, "
                     "kommentar, massnahme, verantwortlich, zieldatum.",
     "pflicht": False},
    {"key": "kapitel", "typ": "liste",
     "beschreibung": "Kapitel-Übersicht; je Eintrag id, titel, referenz, prozent, "
                     "anzahl, bewertet.", "pflicht": False},
    {"key": "luecken", "typ": "liste",
     "beschreibung": "Kritische/offene Anforderungen (Bewertung <= 2).",
     "pflicht": False},
    {"key": "assets", "typ": "liste",
     "beschreibung": "N1 Asset-Inventar.", "pflicht": False},
    {"key": "risiken", "typ": "liste",
     "beschreibung": "N2 Risiko-Register.", "pflicht": False},
    {"key": "vendors", "typ": "liste",
     "beschreibung": "N4 Supply-Chain-Vendoren.", "pflicht": False},
    {"key": "incident_response", "typ": "objekt",
     "beschreibung": "N3 Incident-Response-Plan (SLAs, CSIRT-Kontakt).",
     "pflicht": False},
    {"key": "bcp", "typ": "objekt",
     "beschreibung": "N5 Business-Continuity-Plan (RPO/RTO, Backup).",
     "pflicht": False},
]


# ── Hilfsfunktionen (None-sicher) ──────────────────────────────────────────────

def _s(value: Any) -> str:
    """Robuste String-Konversion: ``None`` → ``''``."""
    return "" if value is None else str(value)


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _reifegrad_text(pct: float) -> str:
    if pct >= 70:
        return "Weitgehend konform"
    if pct >= 40:
        return "Teilweise konform – Handlungsbedarf"
    return "Erhebliche Lücken – Dringender Handlungsbedarf"


def _clean_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Listenfelder None-frei machen (None-Werte → '')."""
    out: list[dict[str, Any]] = []
    for r in rows or []:
        out.append({k: ("" if v is None else v) for k, v in dict(r).items()})
    return out


def _clean_obj(obj: dict[str, Any] | None) -> dict[str, Any]:
    if not obj:
        return {}
    return {k: ("" if v is None else v) for k, v in dict(obj).items()}


# ── Kontext-Builder ────────────────────────────────────────────────────────────

def build_nis2_context(db_path: Path | str, projekt_name: str) -> dict[str, Any]:
    """Baut den Vorlagen-Render-Kontext für ein NIS2-Projekt.

    Robust gegenüber fehlenden Daten: ein nicht existierendes Projekt liefert
    trotzdem eine vollständige, Jinja-sichere Struktur mit leeren Defaults.
    """
    db_path = Path(db_path)
    _db.ensure_db(db_path)

    projekt_name = _s(projekt_name)

    rec = _db.load_projekt(db_path, projekt_name) or {}
    unternehmen = _s(rec.get("unternehmen"))
    einrichtungsklasse = _s(rec.get("einrichtungsklasse")) or "wesentlich"
    ekl_label = EINRICHTUNGSKLASSEN.get(einrichtungsklasse, {}).get(
        "label", einrichtungsklasse
    )

    # Anforderungskatalog + Bewertungen
    anforderungen = load_merged_anforderungen(db_path)
    bewertungen = _db.load_bewertungen(db_path, projekt_name)
    ergebnis = berechne_reifegrad(bewertungen, anforderungen)
    pct = float(ergebnis.get("prozent", 0.0) or 0.0)

    anf_ctx: list[dict[str, Any]] = []
    anzahl_bewertet = 0
    for req in anforderungen:
        bew = bewertungen.get(req["id"], {}) or {}
        wert = _i(bew.get("bewertung", 0))
        if wert > 0:
            anzahl_bewertet += 1
        anf_ctx.append({
            "id": _s(req.get("id")),
            "kapitel": _s(req.get("kapitel")),
            "kapitel_titel": KAPITEL.get(_s(req.get("kapitel")), {}).get("titel", ""),
            "ref": _s(req.get("ref")),
            "titel": _s(req.get("titel")),
            "beschreibung": _s(req.get("beschreibung")),
            "hinweise": _s(req.get("hinweise")),
            "gewichtung": _i(req.get("gewichtung", 1), 1),
            "bewertung": wert,
            "bewertung_label": BEWERTUNG_LABELS.get(wert, ""),
            "kommentar": _s(bew.get("kommentar")),
            "massnahme": _s(bew.get("massnahme")),
            "verantwortlich": _s(bew.get("verantwortlich")),
            "zieldatum": _s(bew.get("zieldatum")),
        })

    kapitel_scores = ergebnis.get("kapitel_scores", {}) or {}
    kapitel_ctx: list[dict[str, Any]] = []
    for kid, kinfo in KAPITEL.items():
        ks = kapitel_scores.get(kid, {}) or {}
        kapitel_ctx.append({
            "id": kid,
            "titel": _s(kinfo.get("titel")),
            "referenz": _s(kinfo.get("referenz")),
            "beschreibung": _s(kinfo.get("beschreibung")),
            "prozent": float(ks.get("prozent", 0.0) or 0.0),
            "anzahl": _i(ks.get("anzahl", 0)),
            "bewertet": _i(ks.get("bewertet", 0)),
        })

    luecken_ctx: list[dict[str, Any]] = []
    for req in ergebnis.get("luecken", []) or []:
        bew = bewertungen.get(req["id"], {}) or {}
        wert = _i(bew.get("bewertung", 0))
        luecken_ctx.append({
            "id": _s(req.get("id")),
            "kapitel": _s(req.get("kapitel")),
            "titel": _s(req.get("titel")),
            "ref": _s(req.get("ref")),
            "beschreibung": _s(req.get("beschreibung")),
            "gewichtung": _i(req.get("gewichtung", 1), 1),
            "bewertung": wert,
            "bewertung_label": BEWERTUNG_LABELS.get(wert, ""),
            "massnahme": _s(bew.get("massnahme")),
        })

    # Pflicht-Doku (N1–N5)
    assets = _clean_rows(_db.list_assets(db_path, projekt_name))
    risiken = _clean_rows(_db.list_risiken(db_path, projekt_name))
    vendors = _clean_rows(_db.list_vendors(db_path, projekt_name))
    incident_response = _clean_obj(_db.load_incident_response(db_path, projekt_name))
    bcp = _clean_obj(_db.load_bcp(db_path, projekt_name))

    return {
        "projekt": {
            "name": projekt_name,
            "unternehmen": unternehmen,
            "einrichtungsklasse": einrichtungsklasse,
            "einrichtungsklasse_label": _s(ekl_label),
            "beschreibung": _s(rec.get("beschreibung")),
            "berater": _s(rec.get("berater")),
            "reifegrad_prozent": pct,
            "reifegrad_text": _reifegrad_text(pct),
            "gesamt_punkte": _i(ergebnis.get("gesamt_punkte", 0)),
            "max_punkte": _i(ergebnis.get("max_punkte", 0)),
            "anzahl_anforderungen": len(anf_ctx),
            "anzahl_bewertet": anzahl_bewertet,
        },
        "meta": {
            "erstellt_am": date.today().strftime("%d.%m.%Y"),
            "rechtsgrundlage": "Richtlinie (EU) 2022/2555 (NIS2)",
            "anzahl_anforderungen": len(anf_ctx),
            "anzahl_luecken": len(luecken_ctx),
        },
        "anforderungen": anf_ctx,
        "kapitel": kapitel_ctx,
        "luecken": luecken_ctx,
        "assets": assets,
        "risiken": risiken,
        "vendors": vendors,
        "incident_response": incident_response,
        "bcp": bcp,
    }
