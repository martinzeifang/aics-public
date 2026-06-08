"""WiBA-Adapter für die zentrale Word-Vorlagen-Engine (W8, #1126).

Stellt den Kontext-Builder ``build_wiba_context`` und die Variablen-Schema-Liste
``WIBA_VARIABLES`` bereit, die von ``shared.templates.schema`` über *guarded
imports* aggregiert werden (Wiring übernimmt der Integrator).

Der Kontext ist robust für Jinja-Rendering: es kommen **keine ``None``-Werte**
vor — fehlende Felder werden auf leere Strings/Listen/0 normalisiert.

Top-Level-Keys: ``projekt``, ``meta``, ``themen``, ``offene_punkte``,
``prueffragen``.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path("data/db/wiba.sqlite")

# ── Variablen-Schema ────────────────────────────────────────────────────────
# Ein Eintrag: {"key", "typ", "beschreibung", "pflicht"}.
WIBA_VARIABLES: list[dict[str, Any]] = [
    {"key": "projekt.name", "typ": "text",
     "beschreibung": "Name des WiBA-Projekts", "pflicht": True},
    {"key": "projekt.unternehmen", "typ": "text",
     "beschreibung": "Geprüfte Organisation / geprüftes Unternehmen", "pflicht": True},
    {"key": "projekt.berater", "typ": "text",
     "beschreibung": "Prüfer / Berater", "pflicht": False},
    {"key": "meta.gesamt_pct", "typ": "zahl",
     "beschreibung": "Gesamt-Reifegrad in Prozent (0-100)", "pflicht": False},
    {"key": "meta.beantwortet", "typ": "zahl",
     "beschreibung": "Anzahl beantworteter Prüffragen (ja/nein)", "pflicht": False},
    {"key": "meta.offen", "typ": "zahl",
     "beschreibung": "Anzahl offener Prüffragen (Status offen)", "pflicht": False},
    {"key": "meta.datum", "typ": "text",
     "beschreibung": "Berichtsdatum (YYYY-MM-DD)", "pflicht": False},
    {"key": "themen", "typ": "liste",
     "beschreibung": "Themen des WiBA-Katalogs "
                     "(titel, bausteine, pct, prueffragen[{nr, frage, status, notiz}])",
     "pflicht": False},
    {"key": "prueffragen", "typ": "liste",
     "beschreibung": "Flache Liste aller Prüffragen "
                     "(thema, nr, control_id, frage, status, notiz)",
     "pflicht": False},
    {"key": "offene_punkte", "typ": "liste",
     "beschreibung": "Offene Punkte / Maßnahmen (Status nein) "
                     "(thema, nr, frage, notiz, verantwortlich, zieldatum)",
     "pflicht": False},
]


# ── Helfer ──────────────────────────────────────────────────────────────────

def _s(value: Any) -> str:
    """Niemals None: gibt einen sauberen String zurück."""
    if value is None:
        return ""
    return str(value)


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ── Kontext-Builder ─────────────────────────────────────────────────────────

def build_wiba_context(db_path: Path | str, projekt_name: str) -> dict[str, Any]:
    """Baut einen Jinja-robusten Render-Kontext für ein WiBA-Projekt.

    Liefert immer ein vollständiges, ``None``-freies Dict — auch wenn das
    Projekt nicht existiert (dann mit leeren Defaults und dem übergebenen Namen).
    """
    db_path = Path(db_path)
    projekt_name = _s(projekt_name)

    from wiba import db as wdb
    from wiba.constants import normalize_status

    wdb.ensure_db(db_path)

    raw = wdb.load_projekt(db_path, projekt_name) or {}
    projekt = {
        "name": _s(raw.get("name")) or projekt_name,
        "unternehmen": _s(raw.get("unternehmen")),
        "berater": _s(raw.get("berater")),
        "beschreibung": _s(raw.get("beschreibung")),
    }

    themen_cat = wdb.list_themen(db_path) or []
    fragen_cat = wdb.list_prueffragen(db_path) or []
    antworten = wdb.load_antworten(db_path, projekt_name) or {}
    try:
        reife = wdb.compute_reifegrad(db_path, projekt_name) or {}
    except Exception:
        reife = {}
    reife_themen = reife.get("themen") or {}

    fragen_by_theme: dict[str, list[dict[str, Any]]] = {}
    for f in fragen_cat:
        fragen_by_theme.setdefault(_s(f.get("theme_key")), []).append(f)

    themen: list[dict[str, Any]] = []
    flach: list[dict[str, Any]] = []
    offene_punkte: list[dict[str, Any]] = []
    beantwortet = 0
    offen = 0

    for t in themen_cat:
        tk = _s(t.get("theme_key"))
        titel = _s(t.get("titel")) or tk
        bausteine = _s(t.get("bausteine"))
        pct = _f((reife_themen.get(tk) or {}).get("pct"), 0.0)
        rows: list[dict[str, Any]] = []
        for f in sorted(fragen_by_theme.get(tk, []), key=lambda x: _i(x.get("nr"))):
            cid = _s(f.get("control_id"))
            a = antworten.get(cid, {})
            st = normalize_status(a.get("status"))
            notiz = _s(a.get("notiz"))
            frage = _s(f.get("frage"))
            nr = _i(f.get("nr"))
            row = {"nr": nr, "control_id": cid, "frage": frage, "status": st, "notiz": notiz}
            rows.append(row)
            flach.append({"thema": titel, **row})
            if st in ("ja", "nein"):
                beantwortet += 1
            elif st == "offen":
                offen += 1
            if st == "nein":
                offene_punkte.append({
                    "thema": titel,
                    "nr": nr,
                    "control_id": cid,
                    "frage": frage,
                    "notiz": notiz,
                    "verantwortlich": _s(a.get("verantwortlich")),
                    "zieldatum": _s(a.get("zieldatum")),
                })
        themen.append({
            "theme_key": tk,
            "titel": titel,
            "bausteine": bausteine,
            "pct": pct,
            "prueffragen": rows,
        })

    meta = {
        "gesamt_pct": _f(reife.get("gesamt_pct"), 0.0),
        "beantwortet": beantwortet,
        "offen": offen,
        "anzahl_themen": len(themen),
        "datum": datetime.date.today().isoformat(),
    }

    return {
        "projekt": projekt,
        "meta": meta,
        "themen": themen,
        "prueffragen": flach,
        "offene_punkte": offene_punkte,
    }
