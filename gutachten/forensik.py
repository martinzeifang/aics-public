"""G4 — Forensik-Workflow.

G4-1 Asservat-PDF-Sicherungsprotokoll
G4-2 Werkzeug-Versionsregister-Validator
G4-3 MACB-Timeline-Builder
G4-4 Order-of-Volatility-Checklist
G4-5 Logfile-Klassifikator
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from shared import db as _sdb

from gutachten import gerichts_db as _gdb
from gutachten import werkzeuge as _werkz


# ─────────────────────────────────────────────────────────
# G4-1 — Sicherungsprotokoll als PDF
# ─────────────────────────────────────────────────────────

def build_sicherungsprotokoll_pdf(asset: dict[str, Any]) -> bytes:
    """Erzeugt ein einfaches PDF mit allen Asservat-Daten."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
    except ImportError:
        # Fallback: einfacher Plain-Text als "PDF" (für Test ohne reportlab)
        text = _build_sicherungsprotokoll_text(asset)
        return text.encode("utf-8")

    from io import BytesIO
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    y = height - 2 * cm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, "Sicherungsprotokoll (Chain of Custody)")
    y -= 0.8 * cm
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, "nach ISO/IEC 27037")
    y -= 1.0 * cm

    pairs = [
        ("Bezeichnung", asset.get("bezeichnung", "")),
        ("SHA-256", asset.get("sha256", "")),
        ("Akquisition (UTC)", asset.get("akquisitions_utc", "")),
        ("Ort", asset.get("akquisitions_ort", "")),
        ("Werkzeug", f"{asset.get('werkzeug_name', '')} {asset.get('werkzeug_version', '')}".strip()),
        ("Original-Dateiname", asset.get("original_dateiname", "")),
        ("Gegengezeichnet von", asset.get("gegengezeichnet_von", "")),
        ("Parteien anwesend", ", ".join(asset.get("parteien_anwesend", []) or [])),
        ("Bemerkungen", asset.get("bemerkungen", "")),
    ]
    c.setFont("Helvetica", 10)
    for label, value in pairs:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(2 * cm, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(6 * cm, y, (value or "—")[:80])
        y -= 0.6 * cm
        if y < 3 * cm:
            c.showPage()
            y = height - 2 * cm

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


def _build_sicherungsprotokoll_text(asset: dict[str, Any]) -> str:
    lines = [
        "Sicherungsprotokoll (Chain of Custody nach ISO/IEC 27037)",
        "=" * 60,
        f"Bezeichnung:          {asset.get('bezeichnung', '')}",
        f"SHA-256:              {asset.get('sha256', '')}",
        f"Akquisition (UTC):    {asset.get('akquisitions_utc', '')}",
        f"Ort:                  {asset.get('akquisitions_ort', '')}",
        f"Werkzeug:             {asset.get('werkzeug_name', '')} {asset.get('werkzeug_version', '')}",
        f"Original-Dateiname:   {asset.get('original_dateiname', '')}",
        f"Gegengezeichnet von:  {asset.get('gegengezeichnet_von', '')}",
        f"Parteien anwesend:    {', '.join(asset.get('parteien_anwesend', []) or [])}",
        f"Bemerkungen:          {asset.get('bemerkungen', '')}",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────
# G4-2 — Werkzeug-Versionsregister-Validator
# ─────────────────────────────────────────────────────────

def validate_werkzeuge_in_befunden(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Prüft, ob alle in Befunden genannten Werkzeuge im SV-Register stehen.

    Liefert {ok, unknown_tools: [{befund_id, befund_nr, tool_name, tool_version}]}.
    """
    befunde = _gdb.list_befunde(db_path, projekt_name)
    register = {(w["tool_name"].lower(), w["version"]) for w in _werkz.list_werkzeuge(db_path)}
    unknown: list[dict[str, Any]] = []
    for b in befunde:
        name = (b.get("werkzeug_name") or "").strip()
        version = (b.get("werkzeug_version") or "").strip()
        if name and version and (name.lower(), version) not in register:
            unknown.append({
                "befund_id": b.get("id"),
                "befund_nr": b.get("nr"),
                "tool_name": name,
                "tool_version": version,
            })
    return {"ok": not unknown, "unknown_tools": unknown}


# ─────────────────────────────────────────────────────────
# G4-3 — MACB-Timeline-Builder
# ─────────────────────────────────────────────────────────

_SCHEMA_MACB = """
CREATE TABLE IF NOT EXISTS gerichtsgutachten_macb (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name TEXT NOT NULL,
    datei_pfad   TEXT NOT NULL,
    modified_at  TEXT,
    accessed_at  TEXT,
    changed_at   TEXT,
    born_at      TEXT,
    bemerkung    TEXT
);
CREATE INDEX IF NOT EXISTS idx_macb_projekt ON gerichtsgutachten_macb(projekt_name);
"""


def _ensure_macb(db_path: Path) -> None:
    con = _sdb.connect(db_path)
    try:
        con.executescript(_SCHEMA_MACB)
        con.commit()
    finally:
        con.close()


def save_macb(db_path: Path, **f: Any) -> int:
    _ensure_macb(db_path)
    con = _sdb.connect(db_path)
    try:
        # #677 Edit-Support
        if f.get("id"):
            con.execute(
                """UPDATE gerichtsgutachten_macb SET
                   datei_pfad=?, modified_at=?, accessed_at=?, changed_at=?, born_at=?, bemerkung=?
                   WHERE id=?""",
                (f["datei_pfad"], f.get("modified_at"), f.get("accessed_at"),
                 f.get("changed_at"), f.get("born_at"), f.get("bemerkung", ""), int(f["id"])),
            )
            con.commit()
            return int(f["id"])
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_macb
                 (projekt_name, datei_pfad, modified_at, accessed_at, changed_at, born_at, bemerkung)
               VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (f["projekt_name"], f["datei_pfad"], f.get("modified_at"), f.get("accessed_at"),
             f.get("changed_at"), f.get("born_at"), f.get("bemerkung", "")),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def list_macb(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    _ensure_macb(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gerichtsgutachten_macb WHERE projekt_name=? ORDER BY modified_at, id",
            (projekt_name,),
        ).fetchall()
        out = [dict(r) for r in rows]
        # Timestomping-Hinweise: identische Stempel sind verdächtig
        for d in out:
            stamps = [d.get(k) for k in ("modified_at", "accessed_at", "changed_at", "born_at") if d.get(k)]
            if len(stamps) >= 3 and len(set(stamps)) == 1:
                d["timestomping_risk"] = True
        return out
    finally:
        con.close()


def delete_macb(db_path: Path, mid: int) -> None:
    _ensure_macb(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute("DELETE FROM gerichtsgutachten_macb WHERE id=?", (mid,))
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# G4-4 — Order-of-Volatility-Checklist
# ─────────────────────────────────────────────────────────

ORDER_OF_VOLATILITY = [
    {"key": "ram", "name": "RAM / flüchtige Daten", "reihenfolge": 1},
    {"key": "netzwerk", "name": "Aktive Netzwerkverbindungen", "reihenfolge": 2},
    {"key": "filesystem", "name": "Dateisystem (offene Dateien, Temp)", "reihenfolge": 3},
    {"key": "persistent", "name": "Persistente Speicher (Disk-Image)", "reihenfolge": 4},
]


def get_volatility_checklist() -> list[dict[str, Any]]:
    return list(ORDER_OF_VOLATILITY)


def check_volatility_compliance(befund: dict[str, Any], checked: dict[str, bool]) -> dict[str, Any]:
    """Bei Methode 'live-forensik' muss die Volatility-Checklist abgehakt sein."""
    if (befund.get("methode") or "") != "live-forensik":
        return {"required": False, "ok": True}
    fehlend = [item["name"] for item in ORDER_OF_VOLATILITY if not checked.get(item["key"], False)]
    return {"required": True, "ok": not fehlend, "fehlend": fehlend}


# ─────────────────────────────────────────────────────────
# G4-5 — Logfile-Klassifikator
# ─────────────────────────────────────────────────────────

LOG_KLASSEN = {
    "system": ["windows event", "syslog", "dmesg", "kern.log", "auth.log", "messages", "eventviewer", "linux"],
    "application": ["nginx", "apache", "access.log", "error.log", "postgresql", "mysql", "odoo", "tomcat", "java", "python", "uwsgi"],
    "network": ["firewall", "router", "dhcp", "ids", "ips", "siem", "snort", "suricata", "pcap", "tcpdump"],
}


def classify_log(filename: str, head_bytes: bytes = b"") -> str:
    """Heuristische Log-Klassifikation: filename + erste Bytes."""
    fn = (filename or "").lower()
    head = head_bytes[:2000].decode("utf-8", errors="ignore").lower()
    blob = fn + " " + head

    scores = {k: 0 for k in LOG_KLASSEN}
    for klasse, keywords in LOG_KLASSEN.items():
        for kw in keywords:
            if kw in blob:
                scores[klasse] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"
