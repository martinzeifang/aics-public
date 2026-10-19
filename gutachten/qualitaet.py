"""G5 — Qualitäts-Gates + Compliance.

G5-1 Pre-Export-Validator (delegiert an gerichtsgutachten_gen + wizards)
G5-2 Peer-Review-Workflow
G5-3 QES-Hinweis + PDF-Export
G5-4 JVEG-Honorargruppe + Stundenzettel + Rechnung
G5-5 10-Jahre-Aufbewahrungs-Reminder + Archiv-Export
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

from shared import db as _sdb

from gutachten import gerichts_db as _gdb
from gutachten import honorar as _honorar


_SCHEMA = """
CREATE TABLE IF NOT EXISTS gerichtsgutachten_peer_review (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name    TEXT NOT NULL,
    reviewer_name   TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'angefordert',  -- angefordert|in_arbeit|abgeschlossen
    kommentare_json TEXT NOT NULL DEFAULT '[]',
    angefordert_am  TEXT NOT NULL DEFAULT (aics_now()),
    abgeschlossen_am TEXT
);
CREATE INDEX IF NOT EXISTS idx_peer_projekt ON gerichtsgutachten_peer_review(projekt_name);

CREATE TABLE IF NOT EXISTS gerichtsgutachten_aufbewahrung (
    projekt_name      TEXT PRIMARY KEY,
    eingereicht_am    TEXT NOT NULL DEFAULT (aics_now()),
    archiv_bis_datum  TEXT NOT NULL
);
"""


def _ensure(db_path: Path) -> None:
    con = _sdb.connect(db_path)
    try:
        con.executescript(_SCHEMA)
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# G5-2 Peer-Review-Workflow
# ─────────────────────────────────────────────────────────

def request_peer_review(db_path: Path, projekt_name: str, reviewer_name: str) -> int:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO gerichtsgutachten_peer_review (projekt_name, reviewer_name)
               VALUES (?, ?) RETURNING id""",
            (projekt_name, reviewer_name),
        )
        row = cur.fetchone()
        con.commit()
        return int(row[0])
    finally:
        con.close()


def add_peer_kommentar(db_path: Path, review_id: int, kapitel: str, text: str, author: str) -> None:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        cur = con.execute(
            "SELECT kommentare_json FROM gerichtsgutachten_peer_review WHERE id=?",
            (review_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("peer-review not found")
        try:
            komms = json.loads(row[0] or "[]")
        except Exception:
            komms = []
        komms.append({
            "kapitel": kapitel,
            "text": text,
            "author": author,
            "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        con.execute(
            "UPDATE gerichtsgutachten_peer_review SET kommentare_json=?, status='in_arbeit' WHERE id=?",
            (json.dumps(komms, ensure_ascii=False), review_id),
        )
        con.commit()
    finally:
        con.close()


def close_peer_review(db_path: Path, review_id: int) -> None:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        con.execute(
            """UPDATE gerichtsgutachten_peer_review
               SET status='abgeschlossen', abgeschlossen_am=aics_now()
               WHERE id=?""",
            (review_id,),
        )
        con.commit()
    finally:
        con.close()


def list_peer_reviews(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gerichtsgutachten_peer_review WHERE projekt_name=? ORDER BY angefordert_am DESC",
            (projekt_name,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["kommentare"] = json.loads(d.get("kommentare_json") or "[]")
            except Exception:
                d["kommentare"] = []
            out.append(d)
        return out
    finally:
        con.close()


# ─────────────────────────────────────────────────────────
# G5-3 PDF-Export (für QES/beA)
# ─────────────────────────────────────────────────────────

QES_HINWEIS = (
    "§ 130a ZPO: Elektronisch eingereichte Gutachten erfordern eine qualifizierte "
    "elektronische Signatur (QES). Bitte das PDF mit Ihrer beA-Karte signieren, "
    "bevor Sie es einreichen."
)


def docx_to_pdf_bytes(docx_bytes: bytes) -> bytes:
    """Konvertiert DOCX zu PDF via LibreOffice (falls verfügbar).

    Fallback: einfaches PDF-Stub mit Hinweis (statt zu crashen).
    """
    try:
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            docx_p = tmp_path / "doc.docx"
            docx_p.write_bytes(docx_bytes)
            res = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp_path), str(docx_p)],
                capture_output=True, timeout=120,
            )
            pdf_p = tmp_path / "doc.pdf"
            if pdf_p.exists():
                return pdf_p.read_bytes()
    except Exception:
        pass
    # Fallback: minimaler PDF-Stub
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.drawString(50, 800, "PDF-Konvertierung fehlgeschlagen — DOCX bitte separat herunterladen.")
        c.save()
        return buf.getvalue()
    except Exception:
        return b"%PDF-1.4\n%%EOF\n"


def compute_hash_sidecar(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ─────────────────────────────────────────────────────────
# G5-4 JVEG-Rechnung
# ─────────────────────────────────────────────────────────

def build_rechnung_pdf(
    db_path: Path,
    projekt_name: str,
    projekt_typ: str = "gerichts",
    rechnungs_nr: str = "",
    auftraggeber: str = "",
    mwst_satz: float = 0.19,
) -> bytes:
    """Generiert JVEG-konforme Rechnung als PDF."""
    eintraege = _honorar.list_eintraege(db_path, projekt_typ, projekt_name)
    summary = _honorar.summary(db_path, projekt_typ, projekt_name)

    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
    except ImportError:
        # Plain-Text Fallback
        lines = [f"Rechnung {rechnungs_nr}", f"Projekt: {projekt_name}",
                 f"Auftraggeber: {auftraggeber}"]
        for e in eintraege:
            lines.append(f"  {e['datum'][:10]} {e['kategorie']:15s} {e['dauer_minuten']}min @ {e['stundensatz_eur']:.2f}€")
        lines.append(f"Summe: {summary['summe_brutto_eur']:.2f}€ + {mwst_satz*100:.0f}% MwSt")
        return "\n".join(lines).encode("utf-8")

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, f"Rechnung {rechnungs_nr}")
    y -= 0.8 * cm
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, f"Projekt: {projekt_name}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Auftraggeber: {auftraggeber}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Datum: {datetime.now().strftime('%d.%m.%Y')}")
    y -= 1.2 * cm

    # Header
    c.setFont("Helvetica-Bold", 9)
    c.drawString(2 * cm, y, "Datum")
    c.drawString(5 * cm, y, "Kategorie")
    c.drawString(8.5 * cm, y, "Min.")
    c.drawString(10.5 * cm, y, "Satz")
    c.drawString(13 * cm, y, "Honorar")
    c.drawString(16 * cm, y, "Auslagen")
    y -= 0.4 * cm
    c.line(2 * cm, y, 19 * cm, y)
    y -= 0.4 * cm

    c.setFont("Helvetica", 9)
    for e in eintraege:
        if y < 4 * cm:
            c.showPage()
            y = height - 2 * cm
            c.setFont("Helvetica", 9)
        c.drawString(2 * cm, y, (e["datum"] or "")[:10])
        c.drawString(5 * cm, y, e["kategorie"][:15])
        c.drawRightString(10 * cm, y, str(e["dauer_minuten"]))
        c.drawRightString(12.5 * cm, y, f"{float(e['stundensatz_eur']):.2f}€")
        honorar_zeile = (e["dauer_minuten"] / 60.0) * float(e["stundensatz_eur"])
        c.drawRightString(15.5 * cm, y, f"{honorar_zeile:.2f}€")
        c.drawRightString(18.5 * cm, y, f"{float(e['auslage_eur']):.2f}€")
        y -= 0.4 * cm

    y -= 0.4 * cm
    c.line(2 * cm, y, 19 * cm, y)
    y -= 0.6 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, "Summe Honorar:")
    c.drawRightString(15.5 * cm, y, f"{summary['honorar_eur']:.2f}€")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, "Summe Auslagen:")
    c.drawRightString(18.5 * cm, y, f"{summary['auslagen_eur']:.2f}€")
    y -= 0.5 * cm
    netto = summary["summe_brutto_eur"]
    mwst = netto * mwst_satz
    brutto = netto + mwst
    c.drawString(2 * cm, y, f"Netto: {netto:.2f}€  |  MwSt ({mwst_satz*100:.0f}%): {mwst:.2f}€  |  Brutto: {brutto:.2f}€")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────
# G5-5 10-Jahre-Aufbewahrung + Archiv
# ─────────────────────────────────────────────────────────

def set_aufbewahrung(db_path: Path, projekt_name: str, jahre: int = 10) -> str:
    _ensure(db_path)
    bis = (datetime.utcnow() + timedelta(days=jahre * 365)).strftime("%Y-%m-%d")
    con = _sdb.connect(db_path)
    try:
        con.execute(
            """INSERT INTO gerichtsgutachten_aufbewahrung (projekt_name, archiv_bis_datum)
               VALUES (?, ?)
               ON CONFLICT(projekt_name) DO UPDATE SET archiv_bis_datum=excluded.archiv_bis_datum""",
            (projekt_name, bis),
        )
        con.commit()
    finally:
        con.close()
    return bis


def get_aufbewahrung(db_path: Path, projekt_name: str) -> dict[str, Any] | None:
    _ensure(db_path)
    con = _sdb.connect(db_path)
    try:
        r = con.execute(
            "SELECT * FROM gerichtsgutachten_aufbewahrung WHERE projekt_name=?",
            (projekt_name,),
        ).fetchone()
        if not r:
            return None
        d = dict(r)
        try:
            bis = datetime.strptime(d["archiv_bis_datum"], "%Y-%m-%d")
            d["tage_verbleibend"] = max(0, (bis - datetime.utcnow()).days)
        except Exception:
            d["tage_verbleibend"] = None
        return d
    finally:
        con.close()


def list_archive_due(db_path: Path) -> list[dict[str, Any]]:
    """Listet alle Gutachten, deren archiv_bis erreicht ist."""
    _ensure(db_path)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    con = _sdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM gerichtsgutachten_aufbewahrung WHERE archiv_bis_datum<=?",
            (today,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def build_archiv_zip(db_path: Path, projekt_name: str, docx_bytes: bytes | None = None,
                    pdf_bytes: bytes | None = None) -> bytes:
    """Erzeugt ZIP-Archiv mit allen relevanten Artefakten + Hash-Manifest."""
    import zipfile
    buf = BytesIO()
    manifest_entries: list[dict[str, str]] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # Projekt-JSON
        projekt = _gdb.load_gerichts_projekt(db_path, projekt_name) or {}
        ereignisse = _gdb.list_verfahrensereignisse(db_path, projekt_name)
        befunde = _gdb.list_befunde(db_path, projekt_name)
        beurteilungen = _gdb.list_beurteilungen(db_path, projekt_name)
        assets = _gdb.list_assets(db_path, projekt_name)
        beweisfragen = _gdb.list_beweisfragen(db_path, projekt_name)
        snapshot = {
            "projekt": projekt,
            "beweisfragen": beweisfragen,
            "befunde": befunde,
            "beurteilungen": beurteilungen,
            "assets": assets,
            "verfahrensereignisse": ereignisse,
            "exportiert_am_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        snap_bytes = json.dumps(snapshot, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        z.writestr("projekt-snapshot.json", snap_bytes)
        manifest_entries.append({"file": "projekt-snapshot.json",
                                 "sha256": compute_hash_sidecar(snap_bytes)})

        if docx_bytes:
            z.writestr(f"{projekt_name}.docx", docx_bytes)
            manifest_entries.append({"file": f"{projekt_name}.docx",
                                     "sha256": compute_hash_sidecar(docx_bytes)})
        if pdf_bytes:
            z.writestr(f"{projekt_name}.pdf", pdf_bytes)
            manifest_entries.append({"file": f"{projekt_name}.pdf",
                                     "sha256": compute_hash_sidecar(pdf_bytes)})

        # Hash-Manifest schreiben
        z.writestr("HASH-MANIFEST.json", json.dumps(manifest_entries, indent=2, ensure_ascii=False).encode("utf-8"))
    buf.seek(0)
    return buf.getvalue()
