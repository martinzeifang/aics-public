"""G6 — Kreative Ideen (8 Stück).

G6-1 Hypothesen-Tree für Kap. V
G6-2 Drittgutachter-Simulator (Reproduzierbarkeits-Anleitung)
G6-3 Befangenheits-Check vor Annahme (erweitert G0-9)
G6-4 Living-Norms-Watcher-UI (Frontend, nutzt G0-5)
G6-5 Sprach-Linter-Extension — bereits in G0-2/G3-1 mit Slogans + AI-Phrasen
G6-6 Cross-Ref-Linter-API für Gerichtsgutachten
G6-7 Anonymisierungs-Tool — Endpoint für anonymized DOCX
G6-8 Honoraranspruchs-Tracker — bereits in G0-4 + G5-4
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared import db as _sdb

from gutachten import gerichts_db as _gdb
from gutachten.linters import cross_ref as _cross_ref
from gutachten.linters import anonymisierung as _anonym


# ─────────────────────────────────────────────────────────
# G6-1 Hypothesen-Tree
# ─────────────────────────────────────────────────────────

_SCHEMA_HYPOTHESEN = """
CREATE TABLE IF NOT EXISTS gerichtsgutachten_hypothesen (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    beurteilung_id  INTEGER NOT NULL,
    hypothese_text  TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'offen',  -- offen|verworfen|akzeptiert
    begruendung     TEXT NOT NULL DEFAULT '',
    erstellt_am     TEXT NOT NULL DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_hyp_beurt ON gerichtsgutachten_hypothesen(beurteilung_id);
"""


def _ensure_hyp(db_path: Path) -> None:
    con = _sdb.connect(db_path)
    try:
        con.executescript(_SCHEMA_HYPOTHESEN)
        con.commit()
    finally:
        con.close()


def save_hypothese(db_path: Path, beurteilung_id: int, hypothese_text: str,
                   status: str = "offen", begruendung: str = "") -> int:
    _ensure_hyp(db_path)
    con = _sdb.connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_hypothesen
                 (beurteilung_id, hypothese_text, status, begruendung)
               VALUES (?, ?, ?, ?) RETURNING id""",
            (beurteilung_id, hypothese_text, status, begruendung),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def list_hypothesen(db_path: Path, beurteilung_id: int | None = None,
                    projekt_name: str | None = None) -> list[dict[str, Any]]:
    _ensure_hyp(db_path)
    con = _sdb.connect(db_path)
    try:
        if beurteilung_id:
            rows = con.execute(
                "SELECT * FROM gerichtsgutachten_hypothesen WHERE beurteilung_id=? ORDER BY id",
                (beurteilung_id,),
            ).fetchall()
        elif projekt_name:
            # Hole alle Hypothesen aller Beurteilungen des Projekts
            ids = [u["id"] for u in _gdb.list_beurteilungen(db_path, projekt_name)]
            if not ids:
                return []
            placeholders = ",".join("?" * len(ids))
            rows = con.execute(
                f"SELECT * FROM gerichtsgutachten_hypothesen WHERE beurteilung_id IN ({placeholders}) ORDER BY id",
                ids,
            ).fetchall()
        else:
            rows = con.execute("SELECT * FROM gerichtsgutachten_hypothesen ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def update_hypothese_status(db_path: Path, hid: int, status: str, begruendung: str = "") -> None:
    _ensure_hyp(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute(
            "UPDATE gerichtsgutachten_hypothesen SET status=?, begruendung=? WHERE id=?",
            (status, begruendung, hid),
        )
        con.commit()
    finally:
        con.close()


def delete_hypothese(db_path: Path, hid: int) -> None:
    _ensure_hyp(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_hypothesen WHERE id=?", (hid,))
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# G6-2 Drittgutachter-Simulator
# ─────────────────────────────────────────────────────────

def build_drittgutachter_prompt(befund: dict[str, Any]) -> str:
    return f"""Du simulierst einen unabhängigen Drittgutachter (DIN EN 16775).
Generiere aus folgendem Befund eine schrittweise Reproduktionsanleitung,
die ein anderer SV nutzen könnte, um zum gleichen Ergebnis zu kommen.

# Befund
- Nr: {befund.get('nr', '')}
- Titel: {befund.get('titel', '')}
- Methode: {befund.get('methode', '')}
- Werkzeug: {befund.get('werkzeug_name', '')} {befund.get('werkzeug_version', '')}
- Beschreibung: {befund.get('beschreibung_text', '')}

Antworte **ausschließlich** als JSON:
```json
{{
  "schritte": ["Schritt 1: ...", "Schritt 2: ..."],
  "voraussetzungen": ["Werkzeug X.Y", "Zugriff auf Asservat-Hash"],
  "erwartetes_ergebnis": "...",
  "potenzielle_abweichungen": ["...", "..."],
  "reproduzierbarkeits_bewertung": "hoch|mittel|niedrig"
}}
```
"""


def selbst_audit(reproduktionsanleitung: dict[str, Any]) -> dict[str, Any]:
    """Bewertet die Reproduktionsanleitung gegen DIN EN 16775-Kriterien."""
    checks = {
        "schritte_vorhanden": bool(reproduktionsanleitung.get("schritte")),
        "werkzeuge_genannt": bool(reproduktionsanleitung.get("voraussetzungen")),
        "ergebnis_definiert": bool(reproduktionsanleitung.get("erwartetes_ergebnis")),
        "reproduzierbarkeit_bewertet": bool(reproduktionsanleitung.get("reproduzierbarkeits_bewertung")),
    }
    score = sum(1 for v in checks.values() if v)
    return {
        "checks": checks,
        "score": score,
        "max_score": len(checks),
        "drittgutachter_tauglich": score == len(checks),
    }


# ─────────────────────────────────────────────────────────
# G6-6 Cross-Ref-Linter-API für Gerichtsgutachten
# ─────────────────────────────────────────────────────────

def cross_ref_check_gerichts(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Wendet den cross_ref-Linter aus G0-2 auf ein konkretes Gerichtsgutachten an."""
    beweisfragen = _gdb.list_beweisfragen(db_path, projekt_name)
    befunde = _gdb.list_befunde(db_path, projekt_name)
    beurteilungen = _gdb.list_beurteilungen(db_path, projekt_name)
    hints = _cross_ref.lint_struktur(beweisfragen, befunde, beurteilungen)
    return {
        "hints": hints,
        "errors": [h for h in hints if h["level"] == "error"],
        "warnings": [h for h in hints if h["level"] == "warn"],
        "ok": all(h["level"] != "error" for h in hints),
    }


# ─────────────────────────────────────────────────────────
# G6-7 Anonymisierungs-Tool für DOCX-Export
# ─────────────────────────────────────────────────────────

def anonymize_gerichts_data(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Anonymisiert alle Text-Felder eines Projekts (für Peer-Review / Lehre)."""
    projekt = _gdb.load_gerichts_projekt(db_path, projekt_name) or {}
    if not projekt:
        return {}
    befunde = _gdb.list_befunde(db_path, projekt_name)
    beurteilungen = _gdb.list_beurteilungen(db_path, projekt_name)
    beweisfragen = _gdb.list_beweisfragen(db_path, projekt_name)

    def anon(d: dict[str, Any], fields: list[str]) -> dict[str, Any]:
        out = dict(d)
        for f in fields:
            if f in out and isinstance(out[f], str):
                out[f] = _anonym.anonymize(out[f])
        return out

    return {
        "projekt": anon(projekt, ["gericht", "kammer", "aktenzeichen", "klaeger_name",
                                  "klaeger_anwalt", "beklagter_name", "beklagter_anwalt",
                                  "thema", "sv_anschrift", "sv_kontakt"]),
        "beweisfragen": [anon(f, ["frage_text", "antwort_text"]) for f in beweisfragen],
        "befunde": [anon(b, ["titel", "beschreibung_text", "zeugen_text"]) for b in befunde],
        "beurteilungen": [anon(u, ["titel", "soll_text", "ist_text",
                                    "kausalitaet_text", "bewertung_text"]) for u in beurteilungen],
        "anonymisiert_am": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
