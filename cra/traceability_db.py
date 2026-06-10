"""CRA Art. 13(1) / Annex VII — Traceability + Vollständigkeitsmatrix (#1217).

Verknüpft Nachweise (``cra_dokumente``) per ``anforderung_id``/``owasp_id`` mit
einzelnen Anforderungen/OWASP-Controls und aggregiert die technische Akte (Annex
VII) zu einer granularen Content-Matrix mit belegt/fehlt-Ampel.

KEINE Duplikation: nutzt die bestehenden ``cra_dokumente``-Zeilen (um
``anforderung_id``/``owasp_id``/``annex_baustein`` erweitert, Migration in
``cra/db.py``), die OWASP-Evidence (``cra_owasp_checks.evidence_json``) und die
Bewertungen (``cra_bewertungen``). Liefert die geprüfte Datenbasis für den
Sprint-#24-Annex-VII-Generator.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from cra.requirements import load_merged_anforderungen

DB_PATH = Path("data/db/cra.sqlite")


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


# #1217-Spalten von cra_dokumente (idempotent ergänzt, falls Tabelle aus
# älterem Schema stammt). Spiegelt die Migration in cra/db.py.
_DOK_COLS = (
    ("anforderung_id", "TEXT NOT NULL DEFAULT ''"),
    ("owasp_id", "TEXT NOT NULL DEFAULT ''"),
    ("annex_baustein", "TEXT NOT NULL DEFAULT ''"),
)


def ensure_db(db_path: Path = DB_PATH) -> None:
    """Idempotent: cra_dokumente anlegen + #1217-Spalten ergänzen.

    Eigenständig (kein cra.db-Re-Use), damit Tests mit tmp-DB außerhalb des
    Workspace-Roots laufen (cra.db._connect erzwingt safe_generated_file).
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_dokumente (
                id              INTEGER PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                doc_name        TEXT NOT NULL,
                doc_path        TEXT NOT NULL DEFAULT '',
                doc_type        TEXT NOT NULL DEFAULT 'resource',
                anforderung_id  TEXT NOT NULL DEFAULT '',
                owasp_id        TEXT NOT NULL DEFAULT '',
                annex_baustein  TEXT NOT NULL DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_cd_projekt ON cra_dokumente(projekt_name);
            CREATE TABLE IF NOT EXISTS cra_bewertungen (
                projekt_name    TEXT NOT NULL,
                anforderung_id  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cra_owasp_checks (
                projekt_name    TEXT NOT NULL,
                owasp_id        TEXT NOT NULL,
                evidence_json   TEXT NOT NULL DEFAULT '[]'
            );
            """
        )
        existing = {r[1] for r in con.execute("PRAGMA table_info(cra_dokumente)").fetchall()}
        for name, decl in _DOK_COLS:
            if name not in existing:
                con.execute(f"ALTER TABLE cra_dokumente ADD COLUMN {name} {decl}")
        con.commit()
    finally:
        con.close()


def _load_bewertungen(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_bewertungen WHERE projekt_name=?", (projekt_name,)
        ).fetchall()
        return {r["anforderung_id"]: dict(r) for r in rows}
    finally:
        con.close()


def _load_owasp_checks(db_path: Path, projekt_name: str) -> dict[str, dict[str, Any]]:
    con = _connect(db_path)
    try:
        out: dict[str, dict[str, Any]] = {}
        for r in con.execute(
            "SELECT * FROM cra_owasp_checks WHERE projekt_name=?", (projekt_name,)
        ).fetchall():
            d = dict(r)
            try:
                d["evidence"] = json.loads(d.get("evidence_json") or "[]")
            except Exception:
                d["evidence"] = []
            out[str(d.get("owasp_id", "")).strip()] = d
        return out
    finally:
        con.close()

# Annex-VII-Bausteine (technische Akte) als Einzel-Zeilen der Content-Matrix.
# key → (Label, [empfohlene doc_types als Beleg-Heuristik]).
ANNEX_VII_BAUSTEINE: list[dict[str, Any]] = [
    {"key": "produktbeschreibung", "label": "Allgemeine Produktbeschreibung & Zweckbestimmung",
     "doc_types": ["produktbeschreibung", "description"]},
    {"key": "design", "label": "Konzeption, Entwicklung & Architektur",
     "doc_types": ["design", "architektur"]},
    {"key": "risikobewertung", "label": "Cybersicherheits-Risikobewertung",
     "doc_types": ["risikobewertung", "risk"]},
    {"key": "sbom", "label": "Software-Bill-of-Materials (SBOM)",
     "doc_types": ["sbom"]},
    {"key": "testberichte", "label": "Testberichte & Security-Testing",
     "doc_types": ["testbericht", "test", "pentest"]},
    {"key": "vuln_handling", "label": "Vulnerability-Handling-Prozess",
     "doc_types": ["psirt", "vuln", "advisory"]},
    {"key": "doc", "label": "EU-Konformitätserklärung (DoC)",
     "doc_types": ["doc", "konformitaetserklaerung"]},
    {"key": "anleitung", "label": "Benutzeranleitung & Sicherheitsinformationen",
     "doc_types": ["anleitung", "manual"]},
]

# Pro Anforderungs-Kapitel geforderte Nachweis-Arten (Soll-Liste).
KAPITEL_SOLL_NACHWEISE: dict[str, list[str]] = {
    "AI1": ["risikobewertung", "design"],
    "AI2": ["testbericht", "design"],
    "ART13": ["produktbeschreibung", "doc"],
    "ART14": ["psirt", "advisory"],
    "IMPL": ["testbericht", "design"],
}


# ── Nachweis↔Anforderung-Verknüpfung (cra_dokumente) ────────────────────────────

def link_dokument(db_path: Path, dok_id: int, projekt_name: str, *,
                  anforderung_id: Optional[str] = None,
                  owasp_id: Optional[str] = None,
                  annex_baustein: Optional[str] = None,
                  doc_type: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Vorhandenes Dokument einer Anforderung/OWASP-Control/Annex-Baustein zuordnen."""
    ensure_db(db_path)
    sets, vals = [], []
    for col, val in (("anforderung_id", anforderung_id), ("owasp_id", owasp_id),
                     ("annex_baustein", annex_baustein), ("doc_type", doc_type)):
        if val is not None:
            sets.append(f"{col}=?")
            vals.append(val)
    if not sets:
        return get_dokument(db_path, dok_id, projekt_name)
    vals += [dok_id, projekt_name]
    con = _connect(db_path)
    try:
        cur = con.execute(
            f"UPDATE cra_dokumente SET {', '.join(sets)} WHERE id=? AND projekt_name=?",
            vals,
        )
        con.commit()
        if cur.rowcount == 0:
            return None
    finally:
        con.close()
    return get_dokument(db_path, dok_id, projekt_name)


def create_dokument(db_path: Path, projekt_name: str, doc_name: str, *,
                    doc_path: str = "", doc_type: str = "resource",
                    anforderung_id: str = "", owasp_id: str = "",
                    annex_baustein: str = "") -> int:
    """Nachweis-/Dokument-Eintrag anlegen (mit optionaler Requirement-Zuordnung)."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO cra_dokumente
                   (projekt_name, doc_name, doc_path, doc_type,
                    anforderung_id, owasp_id, annex_baustein)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (projekt_name, doc_name, doc_path, doc_type,
             anforderung_id, owasp_id, annex_baustein),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def get_dokument(db_path: Path, dok_id: int,
                 projekt_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if projekt_name is not None:
            r = con.execute(
                "SELECT * FROM cra_dokumente WHERE id=? AND projekt_name=?",
                (dok_id, projekt_name),
            ).fetchone()
        else:
            r = con.execute(
                "SELECT * FROM cra_dokumente WHERE id=?", (dok_id,)
            ).fetchone()
        return dict(r) if r else None
    finally:
        con.close()


def list_dokumente(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_dokumente WHERE projekt_name=? ORDER BY id",
            (projekt_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


# ── Per-Requirement Traceability ────────────────────────────────────────────────

def requirement_traceability(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Pro Anforderung: zugeordnete Nachweise + belegt/fehlt-Ampel.

    Eine Anforderung gilt als belegt, wenn ihr mindestens ein Dokument
    (``cra_dokumente.anforderung_id``) zugeordnet ist ODER eine Bewertung mit
    einer Maßnahme/Nachweis hinterlegt wurde.
    """
    ensure_db(db_path)
    anforderungen = load_merged_anforderungen(db_path)
    bewertungen = _load_bewertungen(db_path, projekt_name)
    docs = list_dokumente(db_path, projekt_name)
    docs_by_req: dict[str, list[dict[str, Any]]] = {}
    for d in docs:
        rid = (d.get("anforderung_id") or "").strip()
        if rid:
            docs_by_req.setdefault(rid, []).append(d)

    out: list[dict[str, Any]] = []
    for req in anforderungen:
        rid = req["id"]
        zugeordnete = docs_by_req.get(rid, [])
        bew = bewertungen.get(rid) or {}
        hat_bewertung = bool(bew.get("bewertung") or bew.get("massnahme")
                             or bew.get("kommentar"))
        belegt = bool(zugeordnete) or hat_bewertung
        out.append({
            "anforderung_id": rid,
            "kapitel": req.get("kapitel", ""),
            "titel": req.get("titel", ""),
            "nachweise": [{"id": d["id"], "doc_name": d.get("doc_name"),
                           "doc_type": d.get("doc_type")} for d in zugeordnete],
            "nachweis_count": len(zugeordnete),
            "hat_bewertung": hat_bewertung,
            "ampel": "belegt" if belegt else "fehlt",
        })
    return out


# ── Annex-VII-Vollständigkeitsmatrix ────────────────────────────────────────────

def annex_vii_status(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Granulare Annex-VII-Content-Matrix (Einzel-Zeilen) mit belegt/fehlt-Ampel.

    Aggregiert die Bausteine der technischen Akte: ein Baustein gilt als belegt,
    wenn ihm ein Dokument zugeordnet ist (``annex_baustein`` oder passender
    ``doc_type``). Liefert zusätzlich eine Vollständigkeitsquote.
    """
    ensure_db(db_path)
    docs = list_dokumente(db_path, projekt_name)
    owasp = _load_owasp_checks(db_path, projekt_name)

    # Nachweis-Heuristik je Baustein.
    matrix: list[dict[str, Any]] = []
    belegt_count = 0
    for b in ANNEX_VII_BAUSTEINE:
        zugeordnete = []
        for d in docs:
            baustein = (d.get("annex_baustein") or "").strip()
            dtype = (d.get("doc_type") or "").strip().lower()
            if baustein == b["key"] or dtype in [t.lower() for t in b["doc_types"]]:
                zugeordnete.append({"id": d["id"], "doc_name": d.get("doc_name"),
                                    "doc_type": d.get("doc_type")})
        # Risikobewertung: zusätzlich durch vorhandene OWASP-Evidence belegbar.
        if b["key"] == "risikobewertung" and not zugeordnete:
            if any((c.get("evidence") or []) for c in owasp.values()):
                zugeordnete.append({"id": None, "doc_name": "OWASP-Evidence",
                                    "doc_type": "owasp_evidence"})
        belegt = bool(zugeordnete)
        if belegt:
            belegt_count += 1
        matrix.append({
            "key": b["key"], "label": b["label"],
            "nachweise": zugeordnete, "nachweis_count": len(zugeordnete),
            "ampel": "belegt" if belegt else "fehlt",
        })

    total = len(ANNEX_VII_BAUSTEINE)
    return {
        "projekt_name": projekt_name,
        "bausteine": matrix,
        "belegt_count": belegt_count,
        "gesamt_count": total,
        "vollstaendig": belegt_count == total,
        "vollstaendigkeit_pct": round(100.0 * belegt_count / total, 1) if total else 0.0,
    }
