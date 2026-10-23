"""docxtpl-Render-Engine + Variablen-Extraktion (#989).

Nutzt eine Jinja2-SandboxedEnvironment, damit hochgeladene Vorlagen keine
gefährlichen Konstrukte ausführen können.

``ChainableUndefined`` (#989) sollte fehlende, auch verschachtelte Variablen leer
rendern lassen statt abzubrechen. Das gilt für ``{{ a.b }}`` — und fällt um, sobald
gerechnet oder formatiert wird: ``{{ a.b | round }}`` wirft ``TypeError``,
``{{ a.b + 1 }}`` einen ``UndefinedError``. Die Absicherung trug also gerade in den
Fällen nicht, für die sie gedacht war (#1741). Deshalb wird der Render-Abbruch hier
in :class:`RenderFehler` übersetzt — mit der Angabe, welche Variablen das Modul
nicht kennt und welches Modul sie kennt. Die REST-Schichten liefern das als 422
aus; vorher war es ein 500 mit „Bericht konnte nicht erzeugt werden".

Die Meldung ist dabei nur das Netz. Manche Zugriffe brechen nämlich **nicht** ab:
``{{ a.b | length }}`` liefert still ``0``, und eine fehlende Zahl als „0 %" in
einem Compliance-Bericht ist schlimmer als ein Fehler — der Bericht sieht korrekt
aus und ist falsch. Dagegen hilft nur die Prüfung **vor** dem Export
(:mod:`shared.templates.validate`), nicht die Fehlerbehandlung danach.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any


class RenderFehler(RuntimeError):
    """Die Vorlage ließ sich mit dem Kontext des Moduls nicht rendern.

    Trägt die Einzelteile mit, damit die REST-Schicht sie strukturiert
    weitergeben kann und nicht nur einen Satz Text.
    """

    def __init__(self, meldung: str, *, modul: str = "",
                 unbekannt: list[dict[str, Any]] | None = None,
                 zeile: int | None = None, urspruenglich: str = "") -> None:
        super().__init__(meldung)
        self.modul = modul
        self.unbekannt = list(unbekannt or [])
        self.zeile = zeile
        self.urspruenglich = urspruenglich

    def as_dict(self) -> dict[str, Any]:
        return {"error": str(self), "modul": self.modul, "unbekannt": self.unbekannt,
                "zeile": self.zeile, "ursache": self.urspruenglich}


def _sandbox_env():
    from jinja2.sandbox import SandboxedEnvironment
    from jinja2 import ChainableUndefined
    # ChainableUndefined: fehlende (auch verschachtelte) Variablen rendern leer
    # statt zu crashen — robust gegenüber Admin-Vorlagen mit optionalen Feldern.
    # Grenze dieser Zusage siehe Modul-Docstring + RenderFehler (#1741).
    return SandboxedEnvironment(autoescape=False, undefined=ChainableUndefined)


def _vorlagen_zeile(exc: BaseException) -> int | None:
    """Zeilennummer im Vorlagen-Code aus dem Traceback.

    Jinja kompiliert die Vorlage unter dem Dateinamen ``<template>``; der tiefste
    solche Frame ist die Stelle, die der Anwender in seinem Dokument sucht.
    """
    zeile = None
    tb = exc.__traceback__
    while tb is not None:
        name = tb.tb_frame.f_code.co_filename or ""
        if name.startswith("<template") or name.endswith(".docx"):
            zeile = tb.tb_lineno
        tb = tb.tb_next
    return zeile


def _als_render_fehler(template_path: Path | str, modul: str,
                       exc: BaseException) -> RenderFehler:
    """Baut aus dem Jinja-Abbruch eine Meldung, die den Anwender weiterbringt."""
    from shared.templates.validate import pruefe_variablen

    erg = pruefe_variablen(modul, template_path) if modul else None
    zeile = _vorlagen_zeile(exc)
    ort = f"Vorlagenzeile {zeile}" if zeile else "die Vorlage"
    ursache = f"{type(exc).__name__}: {exc}"

    if erg is not None and not erg.ok:
        meldung = (f"{erg.meldung} Der Abbruch geschah in {ort} "
                   f"— dort wird eine dieser Variablen verrechnet oder formatiert "
                   f"({ursache}).")
    else:
        # Alle Variablen bekannt: dann liegt es an Filter/Rechnung auf einem leeren
        # Feld. Die Zeile ist hier die ganze Information, die hilft.
        meldung = (f"Die Vorlage ließ sich nicht rendern: Fehler in {ort} ({ursache}). "
                   f"Die verwendeten Variablen sind im Modul bekannt — bitte Filter "
                   f"oder Rechenoperation in dieser Zeile prüfen; ein leeres Feld "
                   f"verträgt kein round und keine Arithmetik.")
    return RenderFehler(meldung, modul=modul,
                        unbekannt=(erg.unbekannt if erg else []),
                        zeile=zeile, urspruenglich=ursache)


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


def render_docx_from_path(template_path: Path | str, context: dict[str, Any], *,
                          modul: str = "") -> bytes:
    """Rendert eine Vorlagendatei mit dem Kontext und gibt DOCX-Bytes zurück.

    ``modul`` ist optional und dient nur der Fehlermeldung: mit ihm kann
    :class:`RenderFehler` sagen, welche Variablen das Modul nicht kennt und wohin
    sie gehören (#1741).
    """
    from docxtpl import DocxTemplate
    doc = DocxTemplate(str(template_path))
    try:
        doc.render(context or {}, _sandbox_env())
    except Exception as exc:  # noqa: BLE001 — Auswahl in der Prüfung darunter
        from jinja2 import UndefinedError
        # Beide Wege führen zum selben Anwenderproblem: UndefinedError bei direktem
        # Zugriff, TypeError sobald ein Filter auf ChainableUndefined trifft.
        if isinstance(exc, (UndefinedError, TypeError)):
            raise _als_render_fehler(template_path, modul, exc) from exc
        raise
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render_docx(db_path: Path, template_id: int, context: dict[str, Any]) -> bytes:
    """Rendert die Vorlage mit ``template_id`` aus der Registry."""
    from shared.templates import db as _db
    rec = _db.get_template(db_path, template_id)
    if not rec or not rec.get("aktiv", 1):
        raise ValueError(f"Vorlage {template_id} nicht gefunden oder inaktiv")
    # Das Modul steht in der Registry — nur deshalb kann die Fehlermeldung die
    # fremden Variablen benennen, ohne dass der Aufrufer es mitgeben muss.
    return render_docx_from_path(rec["datei_pfad"], context,
                                 modul=str(rec.get("modul") or ""))
