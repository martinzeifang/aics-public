"""Custom-Word-Vorlagen-Renderer für Gutachten (#957).

Rendert ein Gutachten in eine vom Anwender hochgeladene DOCX-Vorlage (docxtpl /
Jinja2). Sicherheits-Validierung (verbotene Jinja-Konstrukte, Größe, Format) ist
von docxtpl unabhängig und damit ohne installierte Engine testbar.
"""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from gutachten.template_schema import FORBIDDEN_JINJA

MAX_TEMPLATE_BYTES = 20 * 1024 * 1024  # 20 MB (#957 Phase 6)
_DOCX_MAGIC = b"PK\x03\x04"


def validate_template_bytes(data: bytes, filename: str = "") -> list[str]:
    """Pre-Flight-Sicherheitscheck einer hochgeladenen Vorlage.

    Liefert eine Liste von Fehlermeldungen (leer = ok). Braucht **kein** docxtpl.
    """
    errors: list[str] = []
    if not data:
        return ["Datei ist leer"]
    if len(data) > MAX_TEMPLATE_BYTES:
        errors.append(f"Datei größer als {MAX_TEMPLATE_BYTES // (1024*1024)} MB")
    if filename and not filename.lower().endswith((".docx", ".dotx")):
        errors.append("Nur .docx/.dotx erlaubt")
    if data[:4] != _DOCX_MAGIC:
        errors.append("Keine gültige DOCX-Datei (ZIP-Signatur fehlt)")
        return errors
    # XML-Teile auf verbotene Jinja-Konstrukte prüfen (Schutz vor Datei-Lesen/RCE).
    try:
        import io
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # Zip-Bomb-Schutz: unkomprimierte Gesamtgröße begrenzen
            if sum(i.file_size for i in zf.infolist()) > 200 * 1024 * 1024:
                errors.append("Vorlage entpackt zu groß (möglicher Zip-Bomb)")
                return errors
            for info in zf.infolist():
                if not info.filename.endswith(".xml"):
                    continue
                try:
                    xml = zf.read(info.filename).decode("utf-8", "ignore")
                except Exception:
                    continue
                for bad in FORBIDDEN_JINJA:
                    if bad in xml:
                        errors.append(f"Verbotenes Template-Konstrukt: {bad!r}")
    except zipfile.BadZipFile:
        errors.append("DOCX-Datei ist beschädigt (kein gültiges ZIP)")
    return errors


def extract_variables(template_path: Path) -> set[str]:
    """Alle ``{{ … }}``-Tokens der Vorlage (docxtpl). Braucht docxtpl."""
    from docxtpl import DocxTemplate
    tpl = DocxTemplate(str(template_path))
    return set(tpl.get_undeclared_template_variables())


def build_template_context(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Baut den Render-Kontext aus den DB-Daten (#957 Phase 1)."""
    from gutachten import gerichts_db as gdb
    projekt = gdb.load_gerichts_projekt(db_path, projekt_name)
    if not projekt:
        raise ValueError(f"Projekt '{projekt_name}' nicht gefunden")
    return {
        "projekt": projekt,
        "beweisfragen": gdb.list_beweisfragen(db_path, projekt_name),
        "befunde": gdb.list_befunde(db_path, projekt_name),
        "beurteilungen": gdb.list_beurteilungen(db_path, projekt_name),
        "hilfspersonen": gdb.list_hilfspersonen_for_projekt(db_path, projekt_name),
        "datum": datetime.now().strftime("%d.%m.%Y"),
    }


def render_with_template(template_path: Path, context: dict, output_path: Path) -> Path:
    """Rendert den Kontext in die Vorlage und speichert nach output_path.

    Wirft ValueError bei fehlender Engine oder Render-Fehler (mit klarer Meldung).
    """
    try:
        from docxtpl import DocxTemplate
    except ImportError as e:  # pragma: no cover
        raise ValueError("Vorlagen-Engine 'docxtpl' nicht installiert") from e
    try:
        from jinja2 import Environment
        from jinja2.sandbox import SandboxedEnvironment
        tpl = DocxTemplate(str(template_path))
        # Sandbox-Environment statt Default → blockt gefährliche Attribute-Zugriffe.
        jenv: Environment = SandboxedEnvironment()
        tpl.render(context, jinja_env=jenv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tpl.save(str(output_path))
        return output_path
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Vorlagen-Render fehlgeschlagen: {e}") from e
