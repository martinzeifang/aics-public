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


# ───────────────────────────────────────────────────────────────────────────
# #959 — Bracket-Platzhalter ([…]) für reale Word-Vorlagen (python-docx, ohne docxtpl)
# ───────────────────────────────────────────────────────────────────────────

import re as _re

_BRACKET_RE = _re.compile(r"\[[^\]\[]{1,120}\]")


def _iter_all_paragraphs(doc):
    """Alle Absätze: Body, Tabellen (rekursiv), Kopf-/Fußzeilen."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    def _cell_paragraphs(cell):
        for blk in cell._element.iterchildren():
            if blk.tag.endswith('}p'):
                yield Paragraph(blk, cell)
            elif blk.tag.endswith('}tbl'):
                for row in Table(blk, cell).rows:
                    for c in row.cells:
                        yield from _cell_paragraphs(c)

    yield from doc.paragraphs
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from _cell_paragraphs(cell)
    for section in doc.sections:
        for hf in (section.header, section.footer,
                   section.first_page_header, section.first_page_footer):
            if hf is not None:
                yield from hf.paragraphs


def detect_bracket_placeholders(template_path: Path) -> list[str]:
    """Liefert die distinkten ``[…]``-Platzhalter der Vorlage (Reihenfolge erhalten)."""
    from docx import Document
    doc = Document(str(template_path))
    seen: list[str] = []
    for p in _iter_all_paragraphs(doc):
        for tok in _BRACKET_RE.findall(p.text or ""):
            if tok not in seen and tok != "[…]":
                seen.append(tok)
    return seen


def template_has_jinja(template_path: Path) -> bool:
    """True, wenn die Vorlage docxtpl-Platzhalter ``{{ … }}`` enthält."""
    from docx import Document
    doc = Document(str(template_path))
    for p in _iter_all_paragraphs(doc):
        if "{{" in (p.text or "") or "{%" in (p.text or ""):
            return True
    return False


# Auto-Vorschlag: Stichwort im Platzhalter → Schema-Variable.
_SUGGEST_RULES: list[tuple[tuple[str, ...], str]] = [
    (("az.", "aktenzeichen", "ga-jjjj", "gutachten-nr"), "projekt.aktenzeichen"),
    (("titel des gutachten", "untertitel", "sachverhalt"), "projekt.thema"),
    (("name, anschrift", "auftraggeber"), "projekt.auftraggeber"),
    (("vorname nachname", "sachverständig"), "projekt.sv_name"),
    (("fachgebiet", "zertifiz", "bestell"), "projekt.sv_zertifizierung"),
    (("anschrift",), "projekt.sv_anschrift"),
    (("tt.mm.jjjj", "erstellt am", "datum"), "datum"),
    (("gericht",), "projekt.gericht"),
    (("kammer", "senat"), "projekt.kammer"),
    (("beweisfrage",), "beweisfragen"),
    (("feststellung", "befund"), "befunde"),
    (("beurteilung", "würdigung", "antwort"), "beurteilungen"),
    (("hilfsperson",), "hilfspersonen"),
]


def suggest_mapping(tokens: list[str]) -> dict[str, str]:
    """Heuristischer Auto-Vorschlag Platzhalter → Schema-Variable.

    Indizierte Listen-Platzhalter (z. B. '[Beweisfrage 2]') werden auf das
    konkrete Element abgebildet ('beweisfragen[1].frage_text'); unbekannte
    bleiben leer (''), damit der Wizard sie hervorhebt.
    """
    _list_field = {"beweisfragen": "frage_text", "befunde": "titel",
                   "beurteilungen": "titel", "hilfspersonen": "name"}
    out: dict[str, str] = {}
    for tok in tokens:
        low = tok.lower()
        key = ""
        for keywords, target in _SUGGEST_RULES:
            if not any(k in low for k in keywords):
                continue
            # Lange Freitext-Beschreibungen nicht auf Skalare wie 'datum' mappen
            # (z. B. '[Wörtliches Zitat – … Datum.]') — nur Listen erlaubt.
            if len(tok) > 45 and target not in ("beweisfragen", "befunde", "beurteilungen", "hilfspersonen"):
                continue
            key = target
            break
        if key in _list_field:
            m = _re.search(r"(\d+)\s*\]$", tok)
            if m:  # '[Beweisfrage 2]' → element 1
                key = f"{key}[{int(m.group(1)) - 1}].{_list_field[key]}"
        out[tok] = key
    return out


def _render_list(key: str, items: list) -> str:
    fmt = {
        "beweisfragen": lambda x: f"{x.get('nr', '')}. {x.get('frage_text', '')}".strip(),
        "befunde": lambda x: f"{x.get('nr', '')} {x.get('titel', '')}: {x.get('beschreibung_text', '')}".strip(),
        "beurteilungen": lambda x: f"{x.get('nr', '')} {x.get('titel', '')}: {x.get('bewertung_text', '')}".strip(),
        "hilfspersonen": lambda x: f"{x.get('name', '')} ({x.get('rolle', '')}) — {x.get('aufgabe', '')}".strip(),
    }.get(key, lambda x: str(x))
    return "\n".join(fmt(it) for it in items if isinstance(it, dict))


def resolve_mapping_value(spec: str, context: dict) -> str | None:
    """Löst einen Mapping-Wert gegen den Kontext auf.

    - '' / None            → None  (Platzhalter unverändert lassen)
    - '__empty__'          → ''     (Platzhalter entfernen)
    - 'const:TEXT'         → 'TEXT'
    - 'datum'              → Skalar aus context
    - 'projekt.feld'       → verschachtelter Skalar
    - 'beweisfragen'       → ganze Liste gerendert
    - 'beweisfragen[1].frage_text' → indiziertes Element/Feld
    """
    if not spec:
        return None
    if spec == "__empty__":
        return ""
    if spec.startswith("const:"):
        return spec[len("const:"):]

    m = _re.match(r"^([a-zA-Z_]+)\[(\d+)\](?:\.([a-zA-Z_]+))?$", spec)
    if m:
        base, idx, field = m.group(1), int(m.group(2)), m.group(3)
        items = context.get(base)
        if isinstance(items, list) and 0 <= idx < len(items):
            el = items[idx]
            if field:
                return str((el or {}).get(field, "") if isinstance(el, dict) else "")
            return str(el)
        return ""

    if "." in spec:
        root, field = spec.split(".", 1)
        obj = context.get(root)
        if isinstance(obj, dict):
            return str(obj.get(field, "") or "")
        return ""

    val = context.get(spec)
    if isinstance(val, list):
        return _render_list(spec, val)
    return str(val if val is not None else "")


def _replace_in_paragraph(paragraph, replacements: dict[str, str]) -> None:
    """Ersetzt ``[token]`` run-übergreifend; Mehrzeiligkeit via Zeilenumbruch-Runs."""
    runs = paragraph.runs
    if not runs:
        return
    full = "".join(r.text or "" for r in runs)
    new = full
    for tok, val in replacements.items():
        if tok in new:
            new = new.replace(tok, val)
    if new == full:
        return
    # Gesamten Text in den ersten Run (Formatierung bleibt), übrige leeren.
    first, *rest = runs
    for r in rest:
        r.text = ""
    if "\n" in new:
        # Mehrzeilig: erste Zeile in den Run, weitere als <w:br>-Zeilen anhängen.
        lines = new.split("\n")
        first.text = lines[0]
        for line in lines[1:]:
            first.add_break()
            first.add_text(line)
    else:
        first.text = new


def render_with_bracket_mapping(template_path: Path, mapping: dict, context: dict,
                                output_path: Path) -> Path:
    """Füllt eine ``[…]``-Vorlage anhand des Mappings und speichert sie (#959)."""
    from docx import Document
    doc = Document(str(template_path))
    # Mapping (token → spec) zu (token → konkreter Text) auflösen.
    resolved: dict[str, str] = {}
    for tok, spec in (mapping or {}).items():
        val = resolve_mapping_value(spec, context)
        if val is not None:
            resolved[tok] = val
    if resolved:
        for p in _iter_all_paragraphs(doc):
            if "[" in (p.text or ""):
                _replace_in_paragraph(p, resolved)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path


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
