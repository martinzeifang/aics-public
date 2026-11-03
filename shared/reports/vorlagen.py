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


def vorlagen(modul: str, *, firmen_id: int | None = None) -> list[dict[str, Any]]:
    """Auswählbare Vorlagen des Moduls — leer, wenn es keinen Adapter gibt.

    Mit ``firmen_id`` kommen die Vorlagen **dieses** Mandanten und die
    Haus-Vorlagen zurück, sonst nur die Haus-Vorlagen. Das ist bewusst die
    engere Seite: Ohne auflösbaren Mandanten darf keine Kundenvorlage in der
    Auswahl stehen — sie trägt den Namen eines fremden Mandanten (#1778,
    dieselbe Preisgabe wie bei den Projektlisten in #1703).

    Best effort: ohne Vorlagen-Datenbank (frische Installation) ist die Liste leer,
    das Berichts-Center bleibt aber nutzbar.
    """
    if not modul_hat_adapter(modul):
        return []
    try:
        recs = tdb.list_templates(tdb.DEFAULT_DB_PATH, engine_modul(modul),
                                  firmen_id=firmen_id,
                                  nur_haus=firmen_id in (None, 0))
    except Exception:  # noqa: BLE001
        return []
    return [{"id": r["id"], "name": r["name"], "version": r.get("version"),
             "ist_default": bool(r.get("ist_default")),
             "bericht_typ": str(r.get("bericht_typ") or ""),
             "firmen_id": r.get("firmen_id")}
            for r in recs if r.get("aktiv", 1)]


def gilt_fuer_typ(rec: dict[str, Any], typ: str) -> bool:
    """Ist diese Vorlage für diesen Berichtstyp benutzbar?

    Eine Vorlage ohne ``bericht_typ`` gilt für alle Berichte des Moduls — das
    war bis v8.0.3 die einzige Möglichkeit und bleibt gültig.
    """
    eigen = str(rec.get("bericht_typ") or "")
    return not eigen or eigen == str(typ or "")


def vorauswahl(modul: str, typ: str, *, firmen_id: int | None = None,
               vorgeschrieben: bool = False,
               alle: list[dict[str, Any]] | None = None) -> int:
    """Welche Vorlage ist für diesen Bericht vorausgewählt? (0 = keine)

    Rangfolge: Mandanten-Vorlage für genau diesen Bericht, dann Haus-Vorlage für
    genau diesen Bericht, dann — nur bei Berichten ohne vorgeschriebene Struktur
    — die modulweite Standard-Vorlage (Mandant vor Haus).

    **Warum der Vorbehalt bei vorgeschriebenen Dokumenten (#1777):** Eine
    modulweite Standard-Vorlage galt bis v8.0.3 für jeden Berichtstyp. Bei CRA
    sind das sechs verschiedene Dokumente, darunter die EU-Konformitätserklärung
    und der Konformitätsnachweis. Ein Haus-Standard für „den CRA-Bericht" hat
    damit lautlos ein Rechtsdokument ersetzt — der Anwender klickte den Nachweis
    und erhielt die Readiness-Übersicht. Für solche Dokumente muss die Vorlage
    sie **benennen**; wer sie dennoch mit einer allgemeinen Vorlage erzeugen
    will, kann sie weiterhin ausdrücklich wählen.

    Die Regel steht hier und nicht im Frontend: Dieselbe Rechnung an zwei
    Stellen läuft auseinander (die Lehre aus #1703/S9). ``alle`` nimmt eine
    bereits geladene Liste — das Berichts-Center fragt für sieben Typen, und
    sieben Abfragen für dieselbe Liste wären N+1 (#1703/S6).
    """
    if alle is None:
        alle = vorlagen(modul, firmen_id=firmen_id)
    defaults = [v for v in alle if v["ist_default"]]

    def _erster(bedingung) -> int:
        for v in defaults:
            if bedingung(v):
                return int(v["id"])
        return 0

    fid = firmen_id if firmen_id not in (None, 0) else None
    for treffer in (
        lambda v: v["bericht_typ"] == typ and v["firmen_id"] == fid and fid is not None,
        lambda v: v["bericht_typ"] == typ and v["firmen_id"] is None,
    ):
        tid = _erster(treffer)
        if tid:
            return tid
    if vorgeschrieben:
        return 0
    for treffer in (
        lambda v: not v["bericht_typ"] and v["firmen_id"] == fid and fid is not None,
        lambda v: not v["bericht_typ"] and v["firmen_id"] is None,
    ):
        tid = _erster(treffer)
        if tid:
            return tid
    return 0


def projekt_firma(modul: str, projekt: str) -> int | None:
    """Mandant eines Projekts — ``None``, wenn nicht bestimmbar (#1778)."""
    from shared.firmen_link import projekt_firmen_id

    em = engine_modul(modul)
    db = schema.MODULE_DB.get(em)
    if db is None or not projekt:
        return None
    try:
        return projekt_firmen_id(db, projekt)
    except Exception:  # noqa: BLE001
        return None


def _vorlage_oder_fehler(modul: str, template_id: int, *, typ: str = "",
                         projekt: str = "") -> dict[str, Any]:
    rec = tdb.get_template(tdb.DEFAULT_DB_PATH, int(template_id))
    if not rec or not rec.get("aktiv", 1):
        raise VorlageFehlt(f"Vorlage {template_id} nicht gefunden")
    if rec.get("modul") != engine_modul(modul):
        # Siehe Modul-Docstring: sonst Umweg über ein Modul mit schwächeren Rechten.
        raise VorlageFehlt(
            f"Vorlage {template_id} gehört zu Modul '{rec.get('modul')}', "
            f"nicht zu '{engine_modul(modul)}'")
    if typ and not gilt_fuer_typ(rec, typ):
        raise VorlageFehlt(
            f"Vorlage „{rec.get('name')}“ ist für den Bericht "
            f"'{rec.get('bericht_typ')}' hinterlegt, angefordert wurde '{typ}'")
    fid = rec.get("firmen_id")
    if fid and projekt:
        # Eine Kundenvorlage darf nur Dokumente dieses Mandanten erzeugen. Sonst
        # entstünde ein Nachweis für Mandant B im Briefkopf von Mandant A — ein
        # Fehler, den niemand am Dokument erkennt, weil es gültig aussieht.
        eigen = projekt_firma(modul, projekt)
        if eigen is not None and int(fid) != int(eigen):
            raise VorlageFehlt(
                f"Vorlage „{rec.get('name')}“ gehört zu einem anderen Mandanten")
    return rec


def kontext(modul: str, projekt: str, *, typ: str = "",
            version: str = "") -> dict[str, Any]:
    """Modul-Kontext bauen und dem Builder nur geben, was seine Signatur kennt.

    Der Nachweis braucht die Release-Version, der Gesamtbericht nicht, und die
    sieben übrigen Adapter kennen beide Angaben nicht — sie würden mit
    ``TypeError`` brechen. Deshalb wird gefragt statt geraten; dasselbe Muster
    wie ``shared/reports/api._zusatz`` (#1777).
    """
    import inspect

    em = engine_modul(modul)
    builder = schema.get_context_builder(em)
    if builder is None:
        raise VorlageFehlt(f"Für Modul '{em}' ist kein Adapter implementiert")
    extra: dict[str, Any] = {}
    try:
        erlaubt = inspect.signature(builder).parameters
    except (TypeError, ValueError):
        erlaubt = {}
    if "bericht_typ" in erlaubt:
        extra["bericht_typ"] = typ or ""
    if "version" in erlaubt:
        extra["version"] = version or ""
    return dict(builder(schema.MODULE_DB[em], projekt, **extra) or {})


def pruefe(modul: str, template_id: int, *, typ: str = "",
           projekt: str = "") -> dict[str, Any]:
    """Darf diese Vorlage für diesen Bericht und dieses Projekt benutzt werden?

    Wirft :class:`VorlageFehlt` mit Klartext. Der Aufrufer prüft **vor** dem
    Lauf: ``core.generate_and_store`` fängt jeden Fehler und protokolliert ihn
    als Fehllauf — aus „falsche Vorlage gewählt" würde dort ein 500 ohne
    Hinweis (dieselbe Verwechslung, die #1741 behoben hat).
    """
    return _vorlage_oder_fehler(modul, template_id, typ=typ, projekt=projekt)


def render_vorlage(modul: str, template_id: int, *, projekt: str = "",
                   typ: str = "", fmt: str = "docx",
                   von: str | None = None, bis: str | None = None,
                   version: str = "") -> bytes:
    """Rendert den Bericht durch die hochgeladene Vorlage (DOCX oder PDF)."""
    _vorlage_oder_fehler(modul, template_id, typ=typ, projekt=projekt)
    context = kontext(modul, projekt, typ=typ, version=version)
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
                bis: str | None = None, version: str = "", **_: Any) -> bytes:
        return render_vorlage(modul, template_id, projekt=projekt, typ=typ,
                              fmt=fmt, von=von, bis=bis, version=version)
    return _render


def vorlage_name(modul: str, template_id: int) -> str:
    """Name für das Lauf-Protokoll; leer, wenn nicht ermittelbar."""
    try:
        rec = _vorlage_oder_fehler(modul, template_id)
    except Exception:  # noqa: BLE001
        return ""
    return f"{rec.get('name', '')} v{rec.get('version', '')}".strip()
