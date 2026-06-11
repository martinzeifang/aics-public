"""S8 (#1078): Aggregations-Logik für das zentrale Risiko-Cockpit.

Das Cockpit fasst pro Firma alle **offenen** Risiken modulübergreifend zusammen:

* ``rb_risiken`` aus allen ``rb_projekte`` mit passender ``firmen_id``
  (Risikobewertung-Modul, ``data/db/risikobewertung.sqlite``)
* ``cra_vuln`` aus allen ``cra_projekte`` mit passender ``firmen_id``
  (CRA-Modul, ``data/db/cra.sqlite``)

Wichtige Eigenschaften:

* **Read-only.** Es werden ausschließlich SELECTs ausgeführt. ``rb_risiken`` und
  ``cra_vuln`` werden NICHT mutiert (Compliance: keine Auto-Promotion hier).
* **Separate DB-Dateien.** Die Modul-DBs sind eigenständige SQLite-Dateien. Wir
  lesen sequentiell pro Datei (kein ATTACH nötig) und normalisieren auf ein
  gemeinsames Schema.
* **Firmen-FK.** Die Zuordnung erfolgt über die in S1 (#1071) ergänzte logische
  Spalte ``firmen_id`` auf den Projekt-Tabellen (siehe ``shared/firmen_link.py``).
* **Dedup.** Falls eine CRA-Schwachstelle bereits als RB-Risiko promoted wurde,
  trägt das RB-Risiko einen ``provenance_key`` (sofern die Spalte existiert).
  Stimmt dieser mit einem CRA-Eintrag überein, gewinnt der CRA-Eintrag (CRA
  primär), das RB-Duplikat wird unterdrückt.

Normalisiertes Schema (ein Dict je Eintrag)::

    {
        "source":   "rb" | "cra",
        "projekt":  <projekt_name>,
        "titel":    <kurztitel>,
        "severity": "critical"|"high"|"medium"|"low"|"unknown",
        "status":   <roher status-string>,
        "ref":      <stabile referenz, z.B. "rb:<id>" / "cra:CVE-...">,
        "firmen_id": <int>,
        # zusätzliche kontextfelder (best effort):
        "id":       <row id>,
        "cve_id":   <nur cra>,
        "cvss_score": <nur cra, float>,
        "beschreibung": <kurz>,
        "provenance_key": <nur rb, falls vorhanden>,
    }
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

# Standard-Pfade der Modul-DBs (separate Dateien unter data/db/).
DEFAULT_RB_DB = Path("data/db/risikobewertung.sqlite")
DEFAULT_CRA_DB = Path("data/db/cra.sqlite")
DEFAULT_SOC_DB = Path("data/db/soc.sqlite")

# Kanonische Severity-Reihenfolge (hoch → niedrig) für Sortierung.
SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}


def _open_ro(db_path: Path) -> sqlite3.Connection | None:
    """Read-only-Connection; ``None`` falls Datei fehlt/unlesbar."""
    p = Path(db_path)
    if not p.exists():
        return None
    try:
        con = sqlite3.connect(str(p))
        con.row_factory = sqlite3.Row
        return con
    except sqlite3.Error:
        return None


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def normalize_cra_severity(schwere: str | None) -> str:
    """``cra_vuln.schwere`` → kanonische Severity."""
    s = (schwere or "").strip().lower()
    if s in ("critical", "kritisch"):
        return "critical"
    if s in ("high", "hoch"):
        return "high"
    if s in ("medium", "mittel", "moderat"):
        return "medium"
    if s in ("low", "gering", "niedrig"):
        return "low"
    return "unknown"


def normalize_rb_severity(risiko_label: str | None, risikowert: Any = None) -> str:
    """RB ``risiko_label`` (+ optionaler ``risikowert``) → kanonische Severity.

    Deutsche Labels (gering/mittel/hoch/sehr hoch) werden gemappt; bei leerem
    Label dient der numerische ``risikowert`` als Fallback (TARA-Skala 1..4 bzw.
    größere Wertebereiche werden grob klassifiziert).
    """
    l = (risiko_label or "").strip().lower()
    if l:
        if any(w in l for w in ("sehr hoch", "kritisch", "existenz")):
            return "critical"
        if any(w in l for w in ("hoch", "relevant")):
            return "high"
        if any(w in l for w in ("mittel", "moderat")):
            return "medium"
        if any(w in l for w in ("gering", "niedrig", "vernachl")):
            return "low"
    # Numerischer Fallback
    try:
        v = float(risikowert)
    except (TypeError, ValueError):
        return "unknown"
    if v <= 0:
        return "unknown"
    if v >= 12 or v == 4:
        return "critical"
    if v >= 8 or v == 3:
        return "high"
    if v >= 4 or v == 2:
        return "medium"
    return "low"


def _firmen_projekt_names(
    con: sqlite3.Connection, projekt_table: str, firmen_id: int
) -> list[str]:
    """Projektnamen der Firma; leer wenn ``firmen_id``-Spalte fehlt."""
    cols = _table_columns(con, projekt_table)
    if "firmen_id" not in cols or "name" not in cols:
        return []
    rows = con.execute(
        f"SELECT name FROM {projekt_table} WHERE firmen_id = ?", (int(firmen_id),)
    ).fetchall()
    return [r["name"] for r in rows if r["name"]]


def _shorten(text: str | None, limit: int = 200) -> str:
    s = (text or "").strip().replace("\n", " ")
    return s if len(s) <= limit else s[: limit - 1] + "…"


def collect_rb_risks(rb_db: Path, firmen_id: int) -> list[dict[str, Any]]:
    """Offene ``rb_risiken`` aller RB-Projekte der Firma (read-only)."""
    con = _open_ro(rb_db)
    if con is None:
        return []
    try:
        projekte = _firmen_projekt_names(con, "rb_projekte", firmen_id)
        if not projekte:
            return []
        risk_cols = _table_columns(con, "rb_risiken")
        if not risk_cols:
            return []
        has_prov = "provenance_key" in risk_cols
        has_resolved = "is_resolved" in risk_cols
        out: list[dict[str, Any]] = []
        placeholders = ",".join("?" for _ in projekte)
        where = f"projekt_name IN ({placeholders})"
        if has_resolved:
            where += " AND COALESCE(is_resolved, 0) = 0"
        rows = con.execute(
            f"SELECT * FROM rb_risiken WHERE {where} ORDER BY projekt_name, nr, id",
            tuple(projekte),
        ).fetchall()
        for r in rows:
            d = dict(r)
            prov = d.get("provenance_key") if has_prov else None
            out.append(
                {
                    "source": "rb",
                    "projekt": d.get("projekt_name", ""),
                    "titel": _shorten(d.get("risk_name")) or f"Risiko {d.get('nr', '')}",
                    "severity": normalize_rb_severity(
                        d.get("risiko_label"), d.get("risikowert")
                    ),
                    "status": "resolved"
                    if (has_resolved and d.get("is_resolved"))
                    else "open",
                    "ref": f"rb:{d.get('id')}",
                    "firmen_id": int(firmen_id),
                    "id": d.get("id"),
                    "beschreibung": _shorten(d.get("beschreibung")),
                    "provenance_key": prov or "",
                }
            )
        return out
    finally:
        con.close()


def collect_cra_vulns(cra_db: Path, firmen_id: int) -> list[dict[str, Any]]:
    """Offene ``cra_vuln`` aller CRA-Projekte der Firma (read-only).

    "Offen" = Status nicht in {fixed, disclosed, wontfix}.
    """
    con = _open_ro(cra_db)
    if con is None:
        return []
    try:
        projekte = _firmen_projekt_names(con, "cra_projekte", firmen_id)
        if not projekte:
            return []
        vuln_cols = _table_columns(con, "cra_vuln")
        if not vuln_cols:
            return []
        out: list[dict[str, Any]] = []
        placeholders = ",".join("?" for _ in projekte)
        closed = ("fixed", "disclosed", "wontfix")
        rows = con.execute(
            f"SELECT * FROM cra_vuln WHERE projekt_name IN ({placeholders}) "
            f"AND LOWER(COALESCE(status,'open')) NOT IN ({','.join('?' for _ in closed)}) "
            f"ORDER BY cvss_score DESC, cve_id",
            tuple(projekte) + closed,
        ).fetchall()
        for r in rows:
            d = dict(r)
            cve = d.get("cve_id", "")
            out.append(
                {
                    "source": "cra",
                    "projekt": d.get("projekt_name", ""),
                    "titel": _shorten(d.get("titel")) or cve,
                    "severity": normalize_cra_severity(d.get("schwere")),
                    "status": d.get("status", "open"),
                    "ref": f"cra:{cve}" if cve else f"cra:{d.get('id')}",
                    "firmen_id": int(firmen_id),
                    "id": d.get("id"),
                    "cve_id": cve,
                    "cvss_score": float(d.get("cvss_score") or 0.0),
                    "beschreibung": _shorten(d.get("triage_kommentar")),
                }
            )
        return out
    finally:
        con.close()


def collect_soc_incidents(soc_db: Path, firmen_id: int) -> list[dict[str, Any]]:
    """Offene SOC-Incidents der Firma (read-only, #1276).

    "Offen" = Status nicht in {closed, false_positive, resolved}.
    """
    con = _open_ro(soc_db)
    if con is None:
        return []
    try:
        cols = _table_columns(con, "soc_incidents")
        if "firmen_id" not in cols:
            return []
        closed = ("closed", "false_positive", "resolved")
        rows = con.execute(
            f"SELECT * FROM soc_incidents WHERE firmen_id = ? "
            f"AND LOWER(COALESCE(status,'new')) NOT IN ({','.join('?' for _ in closed)}) "
            f"ORDER BY id DESC",
            (int(firmen_id),) + closed,
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            sev = str(d.get("severity") or "medium").lower()
            out.append({
                "source": "soc",
                "projekt": "",
                "titel": _shorten(d.get("titel")) or f"Incident #{d.get('id')}",
                "severity": sev if sev in SEVERITY_ORDER else "medium",
                "status": d.get("status", "new"),
                "ref": f"soc:{d.get('id')}",
                "firmen_id": int(firmen_id),
                "id": d.get("id"),
                "beschreibung": _shorten(d.get("beschreibung")),
            })
        return out
    finally:
        con.close()


def _dedup(
    rb_items: list[dict[str, Any]], cra_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """RB-Duplikate promoteter CRA-Schwachstellen entfernen (CRA primär).

    Ein RB-Risiko gilt als Duplikat, wenn sein ``provenance_key`` mit einem
    CRA-Eintrag matcht. Der ``provenance_key`` einer CRA-Schwachstelle ist
    konventionell ``cve:<CVE-ID>`` bzw. ``cra:<projekt>:<CVE-ID>``. Wir prüfen
    mehrere plausible Schlüssel, um robust gegen Format-Varianten zu sein.
    """
    cra_keys: set[str] = set()
    for c in cra_items:
        cve = (c.get("cve_id") or "").strip()
        if cve:
            cl = cve.lower()
            cra_keys.add(cl)
            cra_keys.add(f"cve:{cl}")
            cra_keys.add(f"cra:{cl}")
            cra_keys.add(f"cra:{(c.get('projekt') or '').lower()}:{cl}")
        ref = (c.get("ref") or "").strip().lower()
        if ref:
            cra_keys.add(ref)

    kept_rb: list[dict[str, Any]] = []
    for r in rb_items:
        prov = (r.get("provenance_key") or "").strip().lower()
        if prov and prov in cra_keys:
            continue  # CRA gewinnt
        kept_rb.append(r)
    return kept_rb


def build_cockpit(
    firmen_id: int,
    *,
    rb_db: Path | None = None,
    cra_db: Path | None = None,
    soc_db: Path | None = None,
) -> dict[str, Any]:
    """Zentrales Cockpit für eine Firma. Read-only Aggregation + Dedup.

    Liefert ``{"firmen_id", "items": [...], "summary": {...}}``.
    ``items`` ist nach Severity (hoch→niedrig), dann Source, Projekt sortiert.
    """
    fid = int(firmen_id)
    rb_items = collect_rb_risks(rb_db or DEFAULT_RB_DB, fid)
    cra_items = collect_cra_vulns(cra_db or DEFAULT_CRA_DB, fid)
    soc_items = collect_soc_incidents(soc_db or DEFAULT_SOC_DB, fid)
    rb_items = _dedup(rb_items, cra_items)

    items = cra_items + rb_items + soc_items
    items.sort(
        key=lambda it: (
            -SEVERITY_ORDER.get(it.get("severity", "unknown"), 0),
            it.get("source", ""),
            it.get("projekt", ""),
            str(it.get("ref", "")),
        )
    )

    summary: dict[str, Any] = {
        "total": len(items),
        "by_source": {"rb": len(rb_items), "cra": len(cra_items), "soc": len(soc_items)},
        "by_severity": {k: 0 for k in SEVERITY_ORDER},
        "projekte": sorted({it["projekt"] for it in items if it.get("projekt")}),
    }
    for it in items:
        sev = it.get("severity", "unknown")
        summary["by_severity"][sev] = summary["by_severity"].get(sev, 0) + 1

    return {"firmen_id": fid, "items": items, "summary": summary}
