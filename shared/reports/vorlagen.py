"""Brücke Berichts-Center ↔ Word-Vorlagen-Engine (#1735).

Die hochgeladene Vorlage wurde bis hierher **nur** vom Test-Export im Admin-UI
genutzt: ``shared.templates.engine`` hatte in der ganzen Anwendung genau einen
Aufrufer (``server/api/templates``). Das Berichts-Center rief ``render(typ, fmt,
…)`` ohne jeden Vorlagen-Parameter — der Anwender lud also eine Vorlage hoch,
setzte sie als Standard, und im Modul kam weiter der programmatische Bericht.
Nichts schlug fehl, es passierte nur nicht.

Dieses Modul schließt die Lücke an einer Stelle für alle Module. Drei Punkte, die
dabei leicht schiefgehen:

* **Modulschlüssel laufen auseinander.** Das Berichts-Center registriert AI Act als
  ``ai_act``, die Vorlagen-Engine kennt ``aiact``. Ohne Normalisierung findet AI Act
  seine eigenen Vorlagen nicht.
* **Nicht jedes Modul mit Berichts-Center hat einen Adapter.** ``firmen`` hat keinen;
  dort darf keine Vorlagen-Auswahl erscheinen, sonst endet die Auswahl in einem 501.
* **Eine Vorlage gehört einem Modul.** Die Berichts-Routen hängen an den Permissions
  ihres Moduls; würde man hier eine fremde ``template_id`` rendern, käme man über das
  Audit-Modul an einen DSGVO-Bericht. Deshalb wird die Zugehörigkeit geprüft.

Eine Vorlage ist das ganze Dokument, nicht ein Berichtstyp. Der gewählte Typ geht
als ``bericht_typ`` in den Kontext — so kann die Vorlage selbst verzweigen
(``{% if bericht_typ == 'massnahmen' %}``), statt dass die Engine es ihr vorgibt.
"""
from __future__ import annotations

from typing import Any, Callable

from shared.templates import db as tdb
from shared.templates import engine, schema

#: Berichts-Center-Schlüssel → Vorlagen-Engine-Schlüssel. Nur echte Abweichungen.
_ALIASE: dict[str, str] = {"ai_act": "aiact"}


class VorlageFehlt(LookupError):
    """Vorlage gibt es nicht, ist gelöscht, oder gehört einem anderen Modul."""


def engine_modul(modul: str) -> str:
    """Modulschlüssel des Berichts-Centers auf den der Engine abbilden."""
    return _ALIASE.get(modul, modul)


def modul_hat_adapter(modul: str) -> bool:
    em = engine_modul(modul)
    return em in schema.MODULE and schema.get_context_builder(em) is not None


def vorlagen(modul: str) -> list[dict[str, Any]]:
    """Auswählbare Vorlagen des Moduls — leer, wenn es keinen Adapter gibt.

    Best effort: ohne Vorlagen-Datenbank (frische Installation) ist die Liste leer,
    das Berichts-Center bleibt aber nutzbar.
    """
    if not modul_hat_adapter(modul):
        return []
    try:
        recs = tdb.list_templates(tdb.DEFAULT_DB_PATH, engine_modul(modul))
    except Exception:  # noqa: BLE001
        return []
    return [{"id": r["id"], "name": r["name"], "version": r.get("version"),
             "ist_default": bool(r.get("ist_default"))}
            for r in recs if r.get("aktiv", 1)]


def _vorlage_oder_fehler(modul: str, template_id: int) -> dict[str, Any]:
    rec = tdb.get_template(tdb.DEFAULT_DB_PATH, int(template_id))
    if not rec or not rec.get("aktiv", 1):
        raise VorlageFehlt(f"Vorlage {template_id} nicht gefunden")
    if rec.get("modul") != engine_modul(modul):
        # Siehe Modul-Docstring: sonst Umweg über ein Modul mit schwächeren Rechten.
        raise VorlageFehlt(
            f"Vorlage {template_id} gehört zu Modul '{rec.get('modul')}', "
            f"nicht zu '{engine_modul(modul)}'")
    return rec


def render_vorlage(modul: str, template_id: int, *, projekt: str = "",
                   typ: str = "", fmt: str = "docx",
                   von: str | None = None, bis: str | None = None) -> bytes:
    """Rendert den Bericht durch die hochgeladene Vorlage (DOCX oder PDF)."""
    _vorlage_oder_fehler(modul, template_id)
    em = engine_modul(modul)
    builder = schema.get_context_builder(em)
    if builder is None:
        raise VorlageFehlt(f"Für Modul '{em}' ist kein Adapter implementiert")

    context = dict(builder(schema.MODULE_DB[em], projekt) or {})
    # Zusatzangaben, auf die eine Vorlage verzweigen kann.
    context.setdefault("bericht_typ", typ or "")
    context.setdefault("zeitraum", {"von": von or "", "bis": bis or ""})

    # Ein Render-Abbruch (Vorlage passt nicht zum Modul) wird bewusst
    # durchgelassen: ``engine.RenderFehler`` trägt die Klartext-Meldung, die
    # ``shared/reports/api.py`` als 422 ausliefert — vorher war es ein 500 ohne
    # jeden Hinweis (#1741).
    docx = engine.render_docx(tdb.DEFAULT_DB_PATH, int(template_id), context)
    if (fmt or "docx").lower() != "pdf":
        return docx
    # Fehler des Konverters bewusst durchlassen: das Berichts-Center bildet sie auf
    # 503/504 ab und empfiehlt DOCX.
    from shared.templates.pdf_converter import convert_docx_to_pdf
    return convert_docx_to_pdf(docx)


def render_callable(modul: str, template_id: int) -> Callable[..., bytes]:
    """``render``-kompatibles Callable für ``core.generate_and_store``."""
    def _render(typ: str, fmt: str, *, projekt: str = "", von: str | None = None,
                bis: str | None = None, **_: Any) -> bytes:
        return render_vorlage(modul, template_id, projekt=projekt, typ=typ,
                              fmt=fmt, von=von, bis=bis)
    return _render


def vorlage_name(modul: str, template_id: int) -> str:
    """Name für das Lauf-Protokoll; leer, wenn nicht ermittelbar."""
    try:
        rec = _vorlage_oder_fehler(modul, template_id)
    except Exception:  # noqa: BLE001
        return ""
    return f"{rec.get('name', '')} v{rec.get('version', '')}".strip()
