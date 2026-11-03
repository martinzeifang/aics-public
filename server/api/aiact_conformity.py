"""AI-Act Art. 43/48 — Konformitätsbewertung + CE REST-Blueprint (``/api/aiact-conformity``, #1198).

Strukturiertes Konformitätsbewertungsverfahren (Annex VI intern / Annex VII NB),
Annex-VI-Checkliste, NB-Zertifikats-Upload, CE-Register, Re-Assessment-Trigger und
DoC-Gate. Bindestrich-Prefix mappt automatisch auf den ``aiact``-Guard.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission

from ai_act import conformity as conf
from ai_act.db import load_projekt

aiact_conformity_bp = Blueprint("aiact_conformity", __name__)
DB_PATH = Path("data/db/ai_act.sqlite")

# #1562: keine System-Controls in einer Organisation mit KI-Systemen (409).
from ai_act.scope import make_org_write_guard as _org_guard  # noqa: E402
aiact_conformity_bp.before_request(_org_guard(DB_PATH))

_MAX_CERT_BYTES = 25 * 1024 * 1024


def _verordnung_liegt_vor() -> bool:
    """Liegt die amtliche Fassung der KI-VO in der Installation? (#1894)

    Best effort: Eine nicht beantwortbare Frage darf die Maske nicht aufhalten
    — dann steht dort schlicht kein Hinweis.
    """
    try:
        from shared.verordnungen import liegt_vor
        return liegt_vor("ki-vo")
    except Exception:  # noqa: BLE001
        return False


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="aiact", details=fields)
    except Exception:  # noqa: BLE001
        pass


@aiact_conformity_bp.get("/constants")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def constants():
    return jsonify({"verfahren": conf.verfahren_katalog(),
                    "checkliste": conf.checkliste_katalog(),
                    "ergebnis": list(conf.ERGEBNIS)})


@aiact_conformity_bp.get("/projekte/<projekt_name>/conformity")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_conformity(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify({
            "record": conf.get_or_empty(DB_PATH, projekt_name),
            "doc_gate": conf.doc_gate(DB_PATH, projekt_name),
        })
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.put("/projekte/<projekt_name>/conformity")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def save_conformity(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        rec = conf.save(DB_PATH, projekt_name, body)
        _audit("aiact.conformity.saved", projekt=projekt_name,
               verfahren=rec.get("verfahren"), ergebnis=rec.get("ergebnis"))
        return jsonify({"record": rec, "doc_gate": conf.doc_gate(DB_PATH, projekt_name)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.post("/projekte/<projekt_name>/certificate")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def upload_certificate(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"error": 'Datei-Feld "file" fehlt'}), 400
        if not f.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Nur PDF-Zertifikate werden unterstützt"}), 400
        content = f.read()
        if not content:
            return jsonify({"error": "Leere Datei"}), 400
        if len(content) > _MAX_CERT_BYTES:
            return jsonify({"error": "Zertifikat zu groß (max. 25 MB)"}), 400
        # Magic-Byte-Prüfung (PDF).
        try:
            from shared.upload_validation import validate_magic_bytes
            validate_magic_bytes(content, suffix=".pdf")
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        rec = conf.store_certificate(DB_PATH, projekt_name, f.filename, content)
        _audit("aiact.conformity.certificate_uploaded", projekt=projekt_name,
               sha256=rec.get("nb_zertifikat_sha256"))
        return jsonify({"record": rec, "doc_gate": conf.doc_gate(DB_PATH, projekt_name)}), 201
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.get("/projekte/<projekt_name>/doc-gate")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def doc_gate(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify(conf.doc_gate(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


# ── Optionale CRA-Verknüpfung (#1243) ───────────────────────────────────────────
# Grundfall: keine Verknüpfung (manuell). Optional kann ein CRA-Projekt verknüpft
# werden → dessen CE/Konformitätsdaten werden read-only referenziert. „Manuell
# überstimmen" (sticky) verhindert jede Automatik-Übernahme. Jederzeit lösbar.

@aiact_conformity_bp.get("/cra-projekte")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def cra_projekte():
    """Auswahlliste verknüpfbarer CRA-Projekte (read-only, optional).

    #1560: ALLE CRA-Projekte (vorher nur solche mit ``cra_konformitaet``-Zeile und
    hinter einem toten ``Path.exists()``-Guard → unter Postgres immer leer).
    Optional ``?projekt=<AI-Act-Projekt>``: Projekte derselben Firma zuerst, ein
    Produkt-Treffer (``<Firma> – <Produkt>``, #1541) als ``vorschlag``.
    """
    try:
        from cra.db import list_projekte as cra_list, load_projekt as cra_load
        from cra.konformitaet_db import DB_PATH as CRA_DB
        firma = produkt = ""
        p = load_projekt(DB_PATH, request.args.get("projekt", "")) if request.args.get("projekt") else None
        if p:
            firma = (p.get("organisation") or "").strip().casefold()
            produkt = (p.get("produkt") or "").strip().casefold()
        items = []
        for name in cra_list(Path(CRA_DB)):
            cp = cra_load(Path(CRA_DB), name) or {}
            same_firma = bool(firma) and (cp.get("unternehmen") or "").strip().casefold() == firma
            same_produkt = same_firma and bool(produkt) and (cp.get("produkt") or "").strip().casefold() == produkt
            items.append({"name": name, "unternehmen": cp.get("unternehmen") or "",
                          "produkt": cp.get("produkt") or "",
                          "firma_match": same_firma, "produkt_match": same_produkt})
        items.sort(key=lambda i: (not i["produkt_match"], not i["firma_match"], i["name"].casefold()))
        vorschlag = next((i["name"] for i in items if i["produkt_match"]), "")
        # "projekte" bleibt eine Namensliste (Abwärtskompatibilität des Stores).
        return jsonify({"projekte": [i["name"] for i in items], "items": items,
                        "vorschlag": vorschlag})
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.get("/projekte/<projekt_name>/cra-link")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_cra_link(projekt_name):
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        return jsonify(conf.get_cra_link(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.put("/projekte/<projekt_name>/cra-link")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def put_cra_link(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        link = conf.set_cra_link(
            DB_PATH, projekt_name,
            linked_cra_projekt=body.get("linked_cra_projekt"),
            manual_override=body.get("manual_override"))
        _audit("aiact.conformity.cra_link_set", projekt=projekt_name,
               linked=link.get("linked_cra_projekt"),
               manual_override=link.get("manual_override"))
        return jsonify(link)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


# ── EU-Konformitätserklärung (Art. 47 i.V.m. Anhang V · #1889) ──────────────
#
# Sie existierte bis v8.2.3 **nur als Prompt** (``wizards`` A8): kein
# Datensatz, keine Prüfung, kein Ausstellen, kein Archiv — obwohl Art. 47
# Abs. 2 verlangt, sie zehn Jahre bereitzuhalten. Der Bauplan ist der aus
# #1884–#1887, die gemeinsamen Teile liegen in ``shared/formular_*``.

@aiact_conformity_bp.get("/projekte/<projekt_name>/doc")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def get_doc(projekt_name):
    """Der erfasste Stand der Erklärung, die Lücken und die Befunde.

    **Eine** Antwort: Lücken, Widersprüche und Vorschläge beschreiben denselben
    Stand, und zwei Abfragen dafür wären zwei Wahrheiten (#1726/#1727).
    """
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        from ai_act import doc_export as de
        from ai_act import doc_pruefung as dp

        d = de.doc_daten(DB_PATH, projekt_name)
        befunde = []
        try:
            befunde = dp.befunde(DB_PATH, projekt_name)
        except Exception as e:  # noqa: BLE001
            # Eine Maske ohne Befunde ist brauchbar; eine, die ganz ausfällt,
            # nicht. Das Ausstellen prüft ohnehin fail-closed.
            current_app.logger.warning("Befunde nicht ermittelbar: %s", e)
        angaben = []
        for a in de.ANHANG_V:
            if a.bedingt == "nb" and not d["nb_pflichtig"]:
                continue
            leer = [f for f in a.felder
                    for e in d["fehlend"] if f in (e.get("felder") or [])]
            angaben.append({**a.as_dict(), "erfasst": not leer,
                            "leere_felder": sorted(set(leer))})
        return jsonify({
            "doc": d["doc"], "angaben": angaben, "fehlend": d["fehlend"],
            "vollstaendig": d["vollstaendig"], "befunde": befunde,
            "nb_pflichtig": d["nb_pflichtig"], "verfahren": d["verfahren"],
            "doc_allowed": d["doc_allowed"],
            "doc_version": d["doc_version"],
            "doc_ausgestellt": d["doc_ausgestellt"],
            "ausgestellt_am": d["ausgestellt_am"],
            "ist_entwurf": d["ist_entwurf"],
            "rechtsgrundlage": de.RECHTSGRUNDLAGE,
            # #1894: Liegt die amtliche Fassung in der Installation? Die
            # Nummerierung von Anhang V ist gegen zwei unabhängige Wiedergaben
            # geprüft, maßgeblich bleibt das Amtsblatt — und wer eine Angabe
            # nachlesen will, soll sehen, ob der Text zur Hand ist.
            "verordnung_liegt_vor": _verordnung_liegt_vor(),
        })
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.get("/projekte/<projekt_name>/doc/vorschlag")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def doc_vorschlag(projekt_name):
    """Anhang-V-Angaben aus den Quellen — ohne KI, ohne Nebenwirkung."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        from ai_act.doc_vorschlag import vorschlag

        return jsonify(vorschlag(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.put("/projekte/<projekt_name>/doc")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def save_doc(projekt_name):
    """Die Erklärung als Entwurf speichern.

    Ohne Vollständigkeitsprüfung und ohne Fassungsnummer — geprüft wird beim
    Ausstellen. Der Mangel, den das verhindert: Im CRA schrieb den Datensatz
    nur das Ausstellen, und wer nicht fertig wurde, verlor alles (#1887).
    """
    body = request.get_json(silent=True) or {}
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        rec = conf.save_doc(DB_PATH, projekt_name, body.get("doc") or {})
        return jsonify({"record": rec})
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.post("/projekte/<projekt_name>/doc")
@jwt_required()
@require_permission(Permission.AIACT_WRITE)
def issue_doc(projekt_name):
    """Die Erklärung ausstellen und unveränderlich ablegen (Art. 47 Abs. 2)."""
    body = request.get_json(silent=True) or {}
    bestaetigt = body.get("bestaetigt") or []
    if isinstance(bestaetigt, str):
        bestaetigt = [bestaetigt]
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        from ai_act import doc_export as de
        from ai_act.doc_pruefung import (BestaetigungErforderlich,
                                         ErklaerungUnstimmig)

        try:
            rec = conf.issue_doc(DB_PATH, projekt_name, body.get("doc") or {},
                                 bestaetigt)
        except de.PflichtfelderFehlen as e:
            return jsonify({"error": str(e), "fehlend": e.fehlend,
                            "code": "pflichtangaben-fehlen"}), 409
        except ErklaerungUnstimmig as e:
            return jsonify({"error": str(e), "befunde": e.befunde,
                            "code": "erklaerung-unstimmig"}), 409
        except BestaetigungErforderlich as e:
            return jsonify({"error": str(e), "befunde": e.befunde,
                            "bestaetigung": e.schluessel,
                            "code": "bestaetigung-erforderlich"}), 428
        _audit("aiact.doc.ausgestellt", projekt=projekt_name,
               doc_version=rec.get("doc_version"),
               bestaetigt=list(bestaetigt))

        # Ausgestellte Fassung ablegen. Best effort: Fehlt der PDF-Konverter,
        # ist die Erklärung trotzdem ausgestellt — aber der Aufrufer erfährt
        # es, statt es zu vermuten (Muster aus #1753).
        try:
            abgelegt = de.ausstellen(projekt_name, db_path=DB_PATH,
                                     von=str(get_jwt_identity() or ""),
                                     bestaetigt=bestaetigt)
            rec["archiv"] = abgelegt
            _audit("aiact.doc.archiviert", projekt=projekt_name,
                   sha256=(abgelegt or {}).get("sha256"))
        except Exception as e:  # noqa: BLE001
            current_app.logger.warning("DoC-Archivierung fehlgeschlagen: %s", e)
            rec["archiv_fehler"] = f"{type(e).__name__}: {e}"
        return jsonify({"record": rec})
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.get("/projekte/<projekt_name>/doc/export")
@jwt_required()
@require_permission(Permission.AIACT_EXPORT)
def export_doc(projekt_name):
    """Die Erklärung als DOCX oder PDF."""
    try:
        if not load_projekt(DB_PATH, projekt_name):
            return jsonify({"error": "Projekt nicht gefunden"}), 404
        from ai_act import doc_export as de

        fmt = (request.args.get("format") or "docx").lower()
        roh = de.build(projekt_name, fmt=fmt, db_path=DB_PATH)
        endung = "pdf" if fmt == "pdf" else "docx"
        typ = ("application/pdf" if fmt == "pdf" else
               "application/vnd.openxmlformats-officedocument."
               "wordprocessingml.document")
        safe = "".join(c if c.isalnum() or c in "-_." else "_"
                       for c in projekt_name)
        from io import BytesIO
        return send_file(BytesIO(roh), mimetype=typ, as_attachment=True,
                         download_name=f"EU-Konformitaetserklaerung_{safe}.{endung}")
    except Exception as e:
        return _log_500(e)


@aiact_conformity_bp.get("/projekte/<projekt_name>/doc/archiv")
@jwt_required()
@require_permission(Permission.AIACT_READ)
def doc_archiv(projekt_name):
    """Die unveränderlich abgelegten Fassungen (Art. 47 Abs. 2: zehn Jahre)."""
    try:
        from ai_act import doc_export as de

        return jsonify({"archiv": de.list_archiv(DB_PATH, projekt_name)})
    except Exception as e:
        return _log_500(e)
