"""G0-6/7/8 — Cross-View + Audit-Kandidaten + Norms↔Audit.

Liefert für einen Firmen alle Gutachten (Audit + Gericht) inkl. Befangenheits-Warnung.
Liefert Audit-Befund-Kandidaten für ein neues Gerichtsgutachten (NUR Anhaltspunkte).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from shared import db as _sdb


def list_gutachten_for_firma(db_path: Path, firma: str) -> dict[str, Any]:
    """G0-7 — alle Gutachten zum Firmen + Warnung bei mehrfachem Vorkommen."""
    if not (firma or "").strip():
        return {"firma": firma, "audit_berichte": [], "gerichtsgutachten": [], "warnung": None}

    audit: list[dict[str, Any]] = []
    gerichts: list[dict[str, Any]] = []
    con = _sdb.connect(db_path)
    try:
        try:
            rows = con.execute(
                """SELECT name, created_at FROM gutachten_projects
                   WHERE name LIKE ? OR meta_json LIKE ?
                   ORDER BY created_at DESC""",
                (f"%{firma}%", f"%{firma}%"),
            ).fetchall()
            audit = [dict(r) for r in rows]
        except Exception:
            pass
        try:
            rows = con.execute(
                """SELECT name, aktenzeichen, status, erstellt_am
                   FROM gerichtsgutachten
                   WHERE klaeger_name LIKE ? OR beklagter_name LIKE ? OR name LIKE ?
                   ORDER BY erstellt_am DESC""",
                (f"%{firma}%", f"%{firma}%", f"%{firma}%"),
            ).fetchall()
            gerichts = [dict(r) for r in rows]
        except Exception:
            pass
    finally:
        con.close()

    warnung = None
    if audit and gerichts:
        warnung = (
            f"⚠ Für '{firma}' existieren sowohl Audit-Berichte ({len(audit)}) "
            f"als auch Gerichtsgutachten ({len(gerichts)}). "
            "Vorbefassungs-Risiko nach § 406 ZPO bitte prüfen."
        )
    return {
        "firma": firma,
        "audit_berichte": audit,
        "gerichtsgutachten": gerichts,
        "warnung": warnung,
    }


def list_audit_kandidaten(db_path: Path, firma: str, system: str = "") -> list[dict[str, Any]]:
    """G0-6 — Audit-Befunde als KANDIDATEN für ein Gerichtsgutachten.

    WICHTIG: nur read-only Hinweis-Liste. Der SV muss jeden Befund persönlich
    neu erheben (§ 407a Abs. 2 ZPO). Auto-Import findet NICHT statt.
    """
    if not (firma or "").strip():
        return []
    out: list[dict[str, Any]] = []
    con = _sdb.connect(db_path)
    try:
        try:
            # 1. Projekte zum Firmen finden
            proj_rows = con.execute(
                """SELECT name FROM gutachten_projects
                   WHERE name LIKE ? OR meta_json LIKE ?""",
                (f"%{firma}%", f"%{firma}%"),
            ).fetchall()
            for p in proj_rows:
                pname = p["name"]
                # 2. Bewertungen aus diesem Projekt (Compliance-Lücken)
                try:
                    a_rows = con.execute(
                        """SELECT framework_section, score, comment
                           FROM gutachten_assessments
                           WHERE project_name = ? AND score < 70
                           ORDER BY score ASC LIMIT 50""",
                        (pname,),
                    ).fetchall()
                    for a in a_rows:
                        out.append({
                            "audit_projekt": pname,
                            "framework_section": a["framework_section"],
                            "score": a["score"],
                            "kommentar": (a["comment"] or "")[:300],
                            "hinweis": "Aus Audit-Bericht — bitte unabhängig erneut prüfen (§ 407a ZPO).",
                        })
                except Exception:
                    pass
        except Exception:
            pass
    finally:
        con.close()
    return out


def link_norm_to_audit(db_path: Path, audit_projekt: str, norm_id: str, kategorie_id: str = "") -> None:
    """G0-8 — speichert in audit_norm_zitate (für Living-Norms-Watcher)."""
    con = _sdb.connect(db_path)
    try:
        con.executescript(
            """CREATE TABLE IF NOT EXISTS audit_norm_zitate (
                 audit_projekt_name TEXT NOT NULL,
                 norm_id TEXT NOT NULL,
                 kategorie_id TEXT NOT NULL DEFAULT '',
                 zitiert_am TEXT NOT NULL DEFAULT (aics_now()),
                 PRIMARY KEY (audit_projekt_name, norm_id, kategorie_id)
               );"""
        )
        con.execute(
            """INSERT INTO audit_norm_zitate
                 (audit_projekt_name, norm_id, kategorie_id) VALUES (?, ?, ?)
               ON CONFLICT DO NOTHING""",
            (audit_projekt, norm_id, kategorie_id),
        )
        con.commit()
    finally:
        con.close()


def list_norm_zitate(db_path: Path, audit_projekt: str | None = None) -> list[dict[str, Any]]:
    con = _sdb.connect(db_path)
    try:
        try:
            if audit_projekt:
                rows = con.execute(
                    "SELECT * FROM audit_norm_zitate WHERE audit_projekt_name=? ORDER BY norm_id",
                    (audit_projekt,),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM audit_norm_zitate ORDER BY audit_projekt_name, norm_id"
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
    finally:
        con.close()
