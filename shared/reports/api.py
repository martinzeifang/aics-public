"""REST-Anbindung des geteilten Berichts-Centers (Sprint #35, #1382).

``register_report_routes`` hängt die vier Standard-Endpunkte an einen bestehenden
Flask-Blueprint — projektbezogen (CRA/NIS2/…) oder global (SOC). Das Modul liefert
nur Katalog + Render-Callable; Zeitraum/Historie/DOCX/PDF kommen aus dem Framework.

Endpunkte (projektbezogen: Präfix ``/projekte/<projekt>``; global: ohne):
    GET  …/berichte                       Katalog + Historie + zeitraum-Flag
    GET  …/berichte/<typ>?format&von&bis  Ad-hoc-Export (Datei)
    POST …/berichte/<typ>/generate        Erzeugen + ablegen + protokollieren
    GET  …/berichte/runs/<id>/download    Datei aus der Historie
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from flask import Response, current_app, request
from flask_jwt_extended import jwt_required

from shared.templates.engine import RenderFehler

from . import core
from . import vorlagen as vorlagen_bruecke
from .core import ReportSpec

_MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def _zusatz(render, quelle: dict[str, Any] | None = None) -> dict[str, str]:
    """Zusätzliche Query-Parameter, die **dieser** Renderer versteht.

    Das Berichts-Center bedient acht Module mit einer festen Signatur
    ``render(typ, fmt, projekt=, von=, bis=)``. CRA braucht zusätzlich die
    Release-Version (#1748): Ohne sie berichtet der Vorgangsbericht immer über
    den jüngsten Vorgang, und „Bericht zu diesem Release" wäre nicht möglich.

    Unbedingt durchzureichen wäre falsch — die sieben übrigen Provider kennen
    den Parameter nicht und würden mit ``TypeError`` brechen. Deshalb wird die
    Signatur gefragt, statt einen Fehler zu verschlucken.
    """
    import inspect

    out: dict[str, str] = {}
    try:
        erlaubt = inspect.signature(render).parameters
    except (TypeError, ValueError):
        return out
    hat_rest = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in erlaubt.values())
    for name in ("version",):
        roh = (quelle or {}).get(name) if quelle is not None else request.args.get(name)
        wert = str(roh or "").strip()
        if wert and (name in erlaubt or hat_rest):
            out[name] = wert
    return out


def _template_id(roh: Any) -> int:
    """``template_id`` aus Query/Body — 0 bedeutet „Standard-Bericht"."""
    try:
        tid = int(roh or 0)
    except (TypeError, ValueError):
        return 0
    return tid if tid > 0 else 0


def register_report_routes(
    bp,
    *,
    modul: str,
    db_path: Any,
    catalog: Sequence[ReportSpec] | Callable[[str], Sequence[ReportSpec]],
    render: Callable[..., bytes],
    project_scoped: bool = True,
    zeitraum: bool = False,
    permission: Callable | None = None,
    summary_context: Callable[[str], dict] | None = None,
    modul_label: str | None = None,
) -> None:
    """Registriert die Berichts-Center-Routen auf ``bp``.

    Args:
      modul: Modul-Key (Storage-Verzeichnis ``data/<modul>/berichte``).
      db_path: Pfad/Schema-Selektor für die Historie-Tabelle.
      catalog: Liste von ReportSpec ODER Callable(projekt)->Liste.
      render: ``render(typ, fmt, *, projekt, von, bis) -> bytes``.
      project_scoped: True → Routen unter ``/projekte/<projekt>``.
      zeitraum: True → Zeitraum-Picker im Frontend + von/bis an render.
      permission: optionaler Decorator (z. B. require_permission(...)).
    """
    prefix = "/projekte/<projekt>" if project_scoped else ""

    def _guard(fn):
        fn = jwt_required()(fn)
        return permission(fn) if permission else fn

    def _catalog(projekt: str) -> list[ReportSpec]:
        return list(catalog(projekt) if callable(catalog) else catalog)

    def _typ_ok(projekt: str, typ: str) -> bool:
        return any(s.key == typ for s in _catalog(projekt))

    # ── Katalog + Historie ──────────────────────────────────────────────
    def _list(projekt: str = ""):
        try:
            runs = core.list_runs(db_path, projekt=(projekt if project_scoped else None))
            # #1778: Mandant des Projekts — er entscheidet, welche Vorlagen
            # überhaupt in die Auswahl kommen. Ohne auflösbaren Mandanten bleibt
            # es bei den Haus-Vorlagen.
            fid = vorlagen_bruecke.projekt_firma(modul, projekt) if projekt else None
            vl = vorlagen_bruecke.vorlagen(modul, firmen_id=fid)
            reports: list[dict[str, Any]] = []
            for spec in _catalog(projekt):
                eintrag = spec.as_dict()
                # #1777: Die Vorauswahl rechnet der Server, damit Oberfläche und
                # Export dieselbe Vorlage meinen.
                eintrag["vorlage_id"] = vorlagen_bruecke.vorauswahl(
                    modul, spec.key, firmen_id=fid,
                    vorgeschrieben=bool(spec.vorgeschrieben), alle=vl)
                reports.append(eintrag)
            return {
                "reports": reports,
                "runs": runs,
                "zeitraum": zeitraum,
                "ki_summary": summary_context is not None,
                # Leer, wenn das Modul keinen Vorlagen-Adapter hat (z. B. firmen) —
                # das Frontend zeigt die Auswahl dann nicht (#1735).
                "vorlagen": vl,
                "firmen_id": fid,
            }, 200
        except Exception as e:  # noqa: BLE001
            current_app.logger.exception("%s %s — %s", request.method, request.path, e)
            return {"error": "Berichts-Center nicht ladbar"}, 500

    # ── Ad-hoc-Export ───────────────────────────────────────────────────
    def _export(typ: str, projekt: str = ""):
        fmt = (request.args.get("format") or "docx").lower()
        if fmt not in _MIME:
            return {"error": "Format muss docx|pdf sein"}, 400
        if not _typ_ok(projekt, typ):
            return {"error": f"Unbekannter Berichtstyp: {typ}"}, 404
        von = request.args.get("von") if zeitraum else None
        bis = request.args.get("bis") if zeitraum else None
        tid = _template_id(request.args.get("template_id"))
        try:
            # Ohne template_id bleibt es beim programmatischen Bericht — Verhalten
            # unverändert (#1735).
            zusatz = _zusatz(render)
            data = (vorlagen_bruecke.render_vorlage(
                        modul, tid, projekt=projekt, typ=typ, fmt=fmt, von=von, bis=bis,
                        version=str(request.args.get("version") or ""))
                    if tid else render(typ, fmt, projekt=projekt, von=von, bis=bis,
                                       **zusatz))
        except vorlagen_bruecke.VorlageFehlt as e:
            return {"error": str(e)}, 404
        except RenderFehler as e:
            # Fehler der Vorlage, nicht des Servers: 422 mit Klartext, welche
            # Variablen fehlen und welches Modul sie kennt (#1741). Vorher kam hier
            # ein 500 und im Frontend „Bericht konnte nicht erzeugt werden".
            current_app.logger.warning("%s %s — Vorlage passt nicht: %s",
                                       request.method, request.path, e)
            return e.as_dict(), 422
        except Exception as e:  # noqa: BLE001
            from shared.templates.pdf_converter import (
                PDFConversionTimeout, PDFConversionUnavailable)
            if isinstance(e, PDFConversionUnavailable):
                return {"error": "PDF-Konverter nicht verfügbar (Gotenberg/LibreOffice). "
                                 "Bitte Word (DOCX) nutzen."}, 503
            if isinstance(e, PDFConversionTimeout):
                return {"error": "PDF-Erzeugung hat zu lange gedauert. Bitte erneut versuchen "
                                 "oder Word (DOCX) nutzen."}, 504
            current_app.logger.exception("%s %s — %s", request.method, request.path, e)
            return {"error": "Bericht konnte nicht erzeugt werden"}, 500
        name = core._safe_name(modul, typ, projekt, fmt)
        return Response(data, mimetype=_MIME[fmt],
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    # ── Generieren + ablegen ────────────────────────────────────────────
    def _generate(typ: str, projekt: str = ""):
        if not _typ_ok(projekt, typ):
            return {"error": f"Unbekannter Berichtstyp: {typ}"}, 404
        body = request.json or {}
        fmt = (body.get("format") or "docx").lower()
        if fmt not in _MIME:
            return {"error": "Format muss docx|pdf sein"}, 400
        von = body.get("von") if zeitraum else None
        bis = body.get("bis") if zeitraum else None
        tid = _template_id(body.get("template_id"))
        vorlage = ""
        # ``core.generate_and_store`` fängt jeden Fehler, protokolliert den Fehllauf
        # und gibt nur einen Text zurück — die Unterscheidung „Vorlage passt nicht"
        # (422) von „Server kaputt" (500) wäre damit verloren. Deshalb hält der
        # Wrapper den RenderFehler fest; der Fehllauf bleibt wie bisher im
        # Protokoll (#1741).
        gefangen: list[RenderFehler] = []
        if tid:
            try:
                vorlagen_bruecke.pruefe(modul, tid, typ=typ, projekt=projekt)
                vorlage = vorlagen_bruecke.vorlage_name(modul, tid)
                basis = vorlagen_bruecke.render_callable(modul, tid)
            except vorlagen_bruecke.VorlageFehlt as e:
                return {"error": str(e)}, 404

            def _mit_vorlage(_typ: str, _fmt: str, **kw: Any) -> bytes:
                try:
                    return basis(_typ, _fmt, **kw)
                except RenderFehler as e:
                    gefangen.append(e)
                    raise

            renderer = _mit_vorlage
        else:
            renderer = render

        res = core.generate_and_store(db_path, modul, typ, renderer, projekt=projekt,
                                      fmt=fmt, von=von, bis=bis, erzeugt_von="user",
                                      vorlage=vorlage, **_zusatz(renderer, body))
        if not res.get("ok"):
            if gefangen:
                current_app.logger.warning("%s %s — Vorlage passt nicht: %s",
                                           request.method, request.path, gefangen[-1])
                return gefangen[-1].as_dict(), 422
            return {"error": res.get("error") or "Erzeugung fehlgeschlagen"}, 500
        return res, 201

    # ── Datei aus der Historie ──────────────────────────────────────────
    def _download_run(run_id: int, projekt: str = ""):
        runs = core.list_runs(db_path, projekt=(projekt if project_scoped else None), limit=1000)
        run = next((r for r in runs if int(r.get("id") or 0) == int(run_id)), None)
        if not run or not run.get("dateiname"):
            return {"error": "Bericht nicht gefunden"}, 404
        data = core.read_stored(modul, run["dateiname"])
        if data is None:
            return {"error": "Datei nicht gefunden"}, 404
        fmt = (run.get("format") or "docx").lower()
        return Response(data, mimetype=_MIME.get(fmt, "application/octet-stream"),
                        headers={"Content-Disposition": f'attachment; filename="{run["dateiname"]}"'})

    # ── KI-Management-Zusammenfassung (#1393) ───────────────────────────
    def _ki_summary(projekt: str = ""):
        if summary_context is None:
            return {"error": "KI-Zusammenfassung nicht verfügbar"}, 404
        from .summary import SummaryError, SummaryUnavailable, generate_summary
        try:
            ctx = summary_context(projekt)
        except Exception as e:  # noqa: BLE001
            current_app.logger.exception("%s %s — %s", request.method, request.path, e)
            return {"error": "Kennzahlen nicht ladbar"}, 500
        try:
            res = generate_summary(modul_label or modul, projekt, ctx)
        except SummaryUnavailable as e:
            return {"error": str(e)}, 409
        except SummaryError as e:
            return {"error": str(e)}, 502
        return res, 200

    def _ki_summary_stream(projekt: str = ""):
        """Live-Streaming-Variante der KI-Management-Zusammenfassung (#1408)."""
        if summary_context is None:
            return {"error": "KI-Zusammenfassung nicht verfügbar"}, 404
        from shared.sse import stream_ai_sse
        from .summary import _SYSTEM, build_summary_prompt
        try:
            ctx = summary_context(projekt)
        except Exception as e:  # noqa: BLE001
            current_app.logger.exception("%s %s — %s", request.method, request.path, e)
            return {"error": "Kennzahlen nicht ladbar"}, 500
        prompt = build_summary_prompt(modul_label or modul, projekt, ctx)
        return stream_ai_sse(_SYSTEM, prompt, temperature=0.3, num_predict=2048)  # #1588

    # ── Routen registrieren (eindeutige Endpoint-Namen je Modul) ─────────
    tag = f"reports_{modul}"
    if project_scoped:
        bp.add_url_rule(f"{prefix}/berichte", f"{tag}_list", _guard(_list), methods=["GET"])
        bp.add_url_rule(f"{prefix}/berichte/<typ>", f"{tag}_export", _guard(_export), methods=["GET"])
        bp.add_url_rule(f"{prefix}/berichte/<typ>/generate", f"{tag}_generate", _guard(_generate), methods=["POST"])
        bp.add_url_rule(f"{prefix}/berichte/runs/<int:run_id>/download", f"{tag}_run_dl", _guard(_download_run), methods=["GET"])
        if summary_context is not None:
            bp.add_url_rule(f"{prefix}/berichte/ki-summary", f"{tag}_ki_summary", _guard(_ki_summary), methods=["POST"])
            bp.add_url_rule(f"{prefix}/berichte/ki-summary/stream", f"{tag}_ki_summary_stream", _guard(_ki_summary_stream), methods=["POST"])
    else:
        bp.add_url_rule("/berichte", f"{tag}_list", _guard(_list), methods=["GET"])
        bp.add_url_rule("/berichte/<typ>", f"{tag}_export", _guard(_export), methods=["GET"])
        bp.add_url_rule("/berichte/<typ>/generate", f"{tag}_generate", _guard(_generate), methods=["POST"])
        bp.add_url_rule("/berichte/runs/<int:run_id>/download", f"{tag}_run_dl", _guard(_download_run), methods=["GET"])
        if summary_context is not None:
            bp.add_url_rule("/berichte/ki-summary", f"{tag}_ki_summary", _guard(_ki_summary), methods=["POST"])
            bp.add_url_rule("/berichte/ki-summary/stream", f"{tag}_ki_summary_stream", _guard(_ki_summary_stream), methods=["POST"])
