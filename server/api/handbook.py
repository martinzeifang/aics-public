"""Benutzerhandbuch-Auslieferung (#1473).

Liefert das Benutzerhandbuch-PDF aus dem Daten-Volume aus, damit es direkt aus der
Anwendung (über den „❓ Hilfe"-Dialog) geöffnet/heruntergeladen werden kann. Das PDF
(~27 MB, aus dem Wiki generiert) wird BEWUSST nicht ins Git/Image gebacken, sondern
liegt unter ``data/handbook/`` im persistenten Daten-Volume.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, send_file, abort
from flask_jwt_extended import jwt_required

handbook_bp = Blueprint("handbook", __name__)

HANDBOOK_DIR = Path("data/handbook")


def _latest_pdf() -> Path | None:
    """Neuestes Handbuch-PDF im Verzeichnis (Dateiname enthält Datum → lexikografisch)."""
    try:
        if not HANDBOOK_DIR.is_dir():
            return None
        pdfs = sorted(HANDBOOK_DIR.glob("*.pdf"))
        return pdfs[-1] if pdfs else None
    except Exception:
        return None


@handbook_bp.get("/available")
@jwt_required()
def available():
    """Ob ein Handbuch-PDF bereitsteht (steuert die Sichtbarkeit des Hilfe-Links)."""
    p = _latest_pdf()
    if not p:
        return jsonify({"available": False})
    return jsonify({"available": True, "filename": p.name, "size": p.stat().st_size})


@handbook_bp.get("")
@jwt_required()
def download():
    """Das aktuelle Benutzerhandbuch als PDF ausliefern (inline, im Browser anzeigbar)."""
    p = _latest_pdf()
    if not p:
        abort(404, description="Kein Benutzerhandbuch hinterlegt")
    return send_file(p.resolve(), mimetype="application/pdf",
                     as_attachment=False, download_name=p.name)
