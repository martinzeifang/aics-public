"""docxtpl-Render-Engine + Variablen-Extraktion (#989).

Nutzt eine Jinja2-SandboxedEnvironment, damit hochgeladene Vorlagen keine
gefährlichen Konstrukte ausführen können.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any


def _sandbox_env():
    from jinja2.sandbox import SandboxedEnvironment
    from jinja2 import ChainableUndefined
    # ChainableUndefined: fehlende (auch verschachtelte) Variablen rendern leer
    # statt zu crashen — robust gegenüber Admin-Vorlagen mit optionalen Feldern.
    return SandboxedEnvironment(autoescape=False, undefined=ChainableUndefined)


def extract_variables(template_path: Path | str) -> list[str]:
    """Liefert alle ``{{ … }}``-Top-Level-Variablen der Vorlage (sortiert, distinkt)."""
    from docxtpl import DocxTemplate
    doc = DocxTemplate(str(template_path))
    try:
        variables = doc.get_undeclared_template_variables(_sandbox_env())
    except TypeError:
        # ältere docxtpl-Signatur ohne env-Argument
        variables = doc.get_undeclared_template_variables()
    return sorted(str(v) for v in variables)


def render_docx_from_path(template_path: Path | str, context: dict[str, Any]) -> bytes:
    """Rendert eine Vorlagendatei mit dem Kontext und gibt DOCX-Bytes zurück."""
    from docxtpl import DocxTemplate
    doc = DocxTemplate(str(template_path))
    doc.render(context or {}, _sandbox_env())
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render_docx(db_path: Path, template_id: int, context: dict[str, Any]) -> bytes:
    """Rendert die Vorlage mit ``template_id`` aus der Registry."""
    from shared.templates import db as _db
    rec = _db.get_template(db_path, template_id)
    if not rec or not rec.get("aktiv", 1):
        raise ValueError(f"Vorlage {template_id} nicht gefunden oder inaktiv")
    return render_docx_from_path(rec["datei_pfad"], context)
