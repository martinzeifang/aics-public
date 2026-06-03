"""G0-9 — Befangenheits-Warnung bei Vorbefassung (§ 406 ZPO).

Prüft beim Anlegen eines Gerichtsgutachtens, ob für dieselbe Partei/dasselbe System
bereits Audit-Berichte oder andere Gerichtsgutachten existieren.

Risiko-Levels:
- hoch     → derselbe SV hat den Firmen vorher als Audit-Bericht-Ersteller bedient
- mittel   → derselbe Firma wurde von einem anderen SV bedient (Kontext erklären)
- niedrig  → namentliche Übereinstimmung in Notizen ohne klare Vorbefassung
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gutachten_befangenheits_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    check_at      TEXT NOT NULL DEFAULT (datetime('now')),
    sv_user       TEXT NOT NULL DEFAULT '',
    firma         TEXT NOT NULL DEFAULT '',
    system        TEXT NOT NULL DEFAULT '',
    treffer_json  TEXT NOT NULL DEFAULT '[]',
    entscheidung  TEXT NOT NULL DEFAULT 'pending'  -- pending|annehmen|ablehnen|offen
);

CREATE INDEX IF NOT EXISTS idx_befang_firma ON gutachten_befangenheits_log(firma);
"""


def _ensure(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(_SCHEMA)
        con.commit()
    finally:
        con.close()


def check(db_path: Path, firma: str, system: str = "", parteien: list[str] | None = None,
          exclude_projekt_name: str | None = None) -> list[dict[str, Any]]:
    """Sucht in den existierenden Gutachten nach Vorbefassung.

    Liefert Liste von Treffern mit {typ, projekt_name, risiko, grund}.

    exclude_projekt_name: schließt das aktuelle Projekt aus den Treffern aus
    (#654 — verhindert Selbstreferenz beim Selbstcheck).
    """
    _ensure(db_path)
    parteien = parteien or []
    treffer: list[dict[str, Any]] = []

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        # 1. Audit-Berichte zum gleichen Firmen — RISIKO HOCH
        # Tabelle: gutachten_projects (existing Audit-Bericht-Tabelle)
        try:
            rows = con.execute(
                "SELECT name FROM gutachten_projects WHERE name LIKE ? OR meta_json LIKE ?",
                (f"%{firma}%", f"%{firma}%"),
            ).fetchall()
            for r in rows:
                treffer.append({
                    "typ": "audit-bericht",
                    "projekt_name": r["name"],
                    "risiko": "hoch",
                    "grund": f"Audit-Bericht '{r['name']}' enthält den Firmen — Vorbefassung möglich (§ 406 ZPO)",
                })
        except sqlite3.OperationalError:
            pass  # Tabelle existiert noch nicht

        # 2. Andere Gerichtsgutachten zum gleichen Firmen — RISIKO MITTEL/HOCH
        try:
            rows = con.execute(
                """SELECT name FROM gerichtsgutachten
                   WHERE klaeger_name LIKE ? OR beklagter_name LIKE ?
                      OR sv_name LIKE ?""",
                (f"%{firma}%", f"%{firma}%", f"%{firma}%"),
            ).fetchall()
            for r in rows:
                treffer.append({
                    "typ": "gerichtsgutachten",
                    "projekt_name": r["name"],
                    "risiko": "hoch",
                    "grund": f"Anderes Gerichtsgutachten '{r['name']}' nennt den Firmen — Vorbefassung möglich",
                })
        except sqlite3.OperationalError:
            pass  # Tabelle existiert noch nicht (G1 fehlt)

        # 3. System-Name Suche in Notizen / Beschreibungen — RISIKO NIEDRIG
        if system:
            try:
                rows = con.execute(
                    "SELECT name FROM gutachten_projects WHERE meta_json LIKE ?",
                    (f"%{system}%",),
                ).fetchall()
                for r in rows:
                    # Filtere bereits gefundene weg
                    if not any(t["projekt_name"] == r["name"] for t in treffer):
                        treffer.append({
                            "typ": "audit-bericht",
                            "projekt_name": r["name"],
                            "risiko": "niedrig",
                            "grund": f"System '{system}' in Audit-Notizen erwähnt",
                        })
            except sqlite3.OperationalError:
                pass

        # 4. Partei-Namen-Match — RISIKO MITTEL
        for partei in parteien:
            partei = (partei or "").strip()
            if not partei:
                continue
            try:
                rows = con.execute(
                    "SELECT name FROM gutachten_projects WHERE meta_json LIKE ?",
                    (f"%{partei}%",),
                ).fetchall()
                for r in rows:
                    if not any(t["projekt_name"] == r["name"] for t in treffer):
                        treffer.append({
                            "typ": "audit-bericht",
                            "projekt_name": r["name"],
                            "risiko": "mittel",
                            "grund": f"Partei '{partei}' in Audit-Notizen erwähnt",
                        })
            except sqlite3.OperationalError:
                pass
    finally:
        con.close()
    if exclude_projekt_name:
        treffer = [t for t in treffer if t.get("projekt_name") != exclude_projekt_name]
    return treffer


def aggregate_risk(treffer: list[dict[str, Any]]) -> str:
    """Gesamtrisiko aus Treffern: hoch > mittel > niedrig > keins."""
    if any(t.get("risiko") == "hoch" for t in treffer):
        return "hoch"
    if any(t.get("risiko") == "mittel" for t in treffer):
        return "mittel"
    if treffer:
        return "niedrig"
    return "keins"


def recommendation(risiko: str) -> dict[str, str]:
    """Handlungsempfehlung pro Risiko-Level."""
    if risiko == "hoch":
        return {
            "level": "hoch",
            "headline": "⚠ Vorbefassung wahrscheinlich",
            "empfehlung": (
                "Es liegen Anhaltspunkte für eine Vorbefassung vor (§ 406 ZPO). "
                "Prüfung: Ablehnung des Gutachtens ist zulässig (§ 407 Abs. 2 ZPO). "
                "Bei Annahme: dokumentierte Vorbefassung dem Gericht offenlegen."
            ),
        }
    if risiko == "mittel":
        return {
            "level": "mittel",
            "headline": "Vorbefassung möglich — bitte einzeln prüfen",
            "empfehlung": (
                "Hinweise auf indirekte Vorbefassung. Bitte jeden Treffer einzeln prüfen "
                "und dokumentiert entscheiden."
            ),
        }
    if risiko == "niedrig":
        return {
            "level": "niedrig",
            "headline": "Schwacher Hinweis — bitte dokumentieren",
            "empfehlung": "Schwache namentliche Übereinstimmung — Dokumentation empfohlen.",
        }
    return {
        "level": "keins",
        "headline": "✓ Keine Anhaltspunkte für Vorbefassung",
        "empfehlung": "Selbstcheck als Verfahrensereignis dokumentieren.",
    }


def log_check(
    db_path: Path,
    sv_user: str,
    firma: str,
    system: str,
    treffer_json: str,
    entscheidung: str = "pending",
) -> int:
    _ensure(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            """INSERT INTO gutachten_befangenheits_log
                 (sv_user, firma, system, treffer_json, entscheidung)
               VALUES (?, ?, ?, ?, ?)
               RETURNING id""",
            (sv_user, firma, system, treffer_json, entscheidung),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def update_entscheidung(db_path: Path, log_id: int, entscheidung: str) -> None:
    _ensure(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "UPDATE gutachten_befangenheits_log SET entscheidung = ? WHERE id = ?",
            (entscheidung, log_id),
        )
        con.commit()
    finally:
        con.close()
