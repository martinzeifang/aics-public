"""CRA Art. 32 / Annex VIII — Konformitätsbewertung + DoC/CE (#1201).

REST-Blueprint ``/api/cra-konformitaet``. Bindestrich-Prefix → cra-Authz (#1169).
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from server.models.permission import Permission, require_permission
from server.api._common import require_projekt

from cra.db import load_projekt
from cra import konformitaet_db as kdb

cra_konformitaet_bp = Blueprint("cra_konformitaet", __name__)
DB_PATH = Path("data/db/cra.sqlite")


def _log_500(e: Exception):
    current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                 type(e).__name__, e)
    return jsonify({"error": "Interner Serverfehler"}), 500


def _audit(action: str, **fields):
    try:
        from shared.audit import audit_event
        fields.setdefault("actor", str(get_jwt_identity() or ""))
        audit_event(action, module="cra", details=fields)
    except Exception:  # noqa: BLE001
        pass


@cra_konformitaet_bp.get("/constants")
@jwt_required()
@require_permission(Permission.CRA_READ)
def constants():
    return jsonify({"wege": list(kdb.WEGE), "ce_status": list(kdb.CE_STATUS),
                    "checkliste": kdb.CHECKLISTE})


@cra_konformitaet_bp.get("/projekte/<projekt_name>/konformitaet")
@jwt_required()
@require_permission(Permission.CRA_READ)
def get_konformitaet(projekt_name):
    try:
        release = request.args.get("release", "")
        rec = kdb.get_konformitaet(DB_PATH, projekt_name, release)
        return jsonify(rec or {})
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/konformitaet/list")
@jwt_required()
@require_permission(Permission.CRA_READ)
def list_konformitaet(projekt_name):
    try:
        return jsonify(kdb.list_konformitaet(DB_PATH, projekt_name))
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.put("/projekte/<projekt_name>/konformitaet")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def put_konformitaet(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        rec = kdb.save_konformitaet(DB_PATH, projekt_name, body)
        _audit("cra.konformitaet.gespeichert", projekt=projekt_name,
               weg=rec.get("bewertungsweg"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


# #1220-A: Governance-Sign-off (Freigabe + Lock) — separate CRA_APPROVE-Permission.
@cra_konformitaet_bp.post("/projekte/<projekt_name>/konformitaet/freigeben")
@jwt_required()
@require_permission(Permission.CRA_APPROVE)
def freigeben(projekt_name):
    body = request.get_json(silent=True) or {}
    release = body.get("release_version", "")
    try:
        rec = kdb.freigeben(DB_PATH, projekt_name, release,
                            von=str(get_jwt_identity() or ""))
        _audit("cra.konformitaet.freigegeben", projekt=projekt_name,
               release=release, freigegeben_von=rec.get("freigegeben_von"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/konformitaet/reopen")
@jwt_required()
@require_permission(Permission.CRA_APPROVE)
def reopen(projekt_name):
    body = request.get_json(silent=True) or {}
    release = body.get("release_version", "")
    try:
        rec = kdb.reopen(DB_PATH, projekt_name, release)
        _audit("cra.konformitaet.reopened", projekt=projekt_name, release=release)
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/konformitaet/doc")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def issue_doc(projekt_name):
    body = request.get_json(silent=True) or {}
    release = body.get("release_version", "")
    doc = body.get("doc") or {}
    try:
        # #1753: Eine Erklärung ohne die Pflichtangaben aus Anhang V ist
        # unwirksam. Sie als „ausgestellt" zu speichern wäre deshalb schlimmer
        # als sie abzulehnen: Der Datensatz sähe gültig aus, das Dokument wäre
        # es nicht. Geprüft wird VOR dem Speichern und mit Nennung der Lücken —
        # eine Ablehnung ohne Liste schickt den Anwender auf die Suche.
        from cra import doc_export

        # Der Datensatz wird mit dem eingehenden Körper zusammengeführt, bevor
        # geprüft wird: Wer nur ein Feld nachreicht, soll nicht an den Angaben
        # scheitern, die längst gespeichert sind.
        basis = doc_export.doc_daten(DB_PATH, projekt_name, release or None)
        zusammen = dict(basis.get("doc") or {})
        zusammen.update(doc or {})
        fehlend = doc_export.fehlende_pflichtfelder(
            zusammen, nb_pflichtig=bool(basis.get("nb_pflichtig")))
        if fehlend:
            return jsonify({
                "error": "Die Erklärung ist unvollständig und kann nicht "
                         "ausgestellt werden (Art. 28 i.V.m. Anhang V).",
                "fehlend": fehlend,
            }), 409

        rec = kdb.issue_doc(DB_PATH, projekt_name, doc, release)
        _audit("cra.konformitaet.doc_ausgestellt", projekt=projekt_name,
               doc_version=rec.get("doc_version"))

        # Ausgestellte Fassung unveränderlich ablegen (PDF + SHA-256). Best
        # effort: Fehlt der PDF-Konverter, ist die Erklärung trotzdem
        # ausgestellt — aber der Aufrufer erfährt es, statt es zu vermuten.
        archiv_fehler = ""
        try:
            abgelegt = doc_export.ausstellen(projekt_name, release_version=release,
                                             von=str(get_jwt_identity() or ""))
            rec["archiv"] = abgelegt
            _audit("cra.konformitaet.doc_archiviert", projekt=projekt_name,
                   sha256=(abgelegt or {}).get("sha256"))
        except Exception as e:  # noqa: BLE001
            archiv_fehler = f"{type(e).__name__}: {e}"
            current_app.logger.warning("DoC-Archivierung fehlgeschlagen: %s", archiv_fehler)
            rec["archiv_fehler"] = archiv_fehler
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/doc/archiv")
@jwt_required()
@require_permission(Permission.CRA_READ)
def doc_archiv(projekt_name):
    """Die unveränderlich abgelegten Fassungen der Konformitätserklärung."""
    try:
        from cra import doc_export
        return jsonify({"archiv": doc_export.list_archiv(DB_PATH, projekt_name)})
    except Exception as e:
        return _log_500(e)


# ── Sprint #49: Release-Check (Gate) + Konformitätsnachweis + Sign-off-Archiv ────

@cra_konformitaet_bp.get("/projekte/<projekt_name>/release-check")
@jwt_required()
@require_permission(Permission.CRA_READ)
def release_check(projekt_name):
    """#1612/#1615: Konformitäts-Gate/Release-Readiness mit offenen Punkten + Deep-Links."""
    try:
        from cra.konformitaet_gate import evaluate
        version = request.args.get("version") or None
        return jsonify(evaluate(projekt_name, version=version))
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/nachweis")
@jwt_required()
@require_permission(Permission.CRA_EXPORT)
def konformitaet_nachweis(projekt_name):
    """#1610: Kundenfähiger CRA-Konformitätsnachweis je Version (docx|pdf)."""
    try:
        from cra.konformitaet_report import build_docx, build_pdf
        version = request.args.get("version") or None
        fmt = (request.args.get("format") or "pdf").lower()
        from flask import send_file
        from io import BytesIO
        if fmt == "docx":
            data = build_docx(projekt_name, version=version)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"
        else:
            data = build_pdf(projekt_name, version=version)
            mime = "application/pdf"; ext = "pdf"
        _audit("cra.konformitaet.nachweis_erzeugt", projekt=projekt_name, version=version, format=ext)
        name = f"CRA-Konformitaetsnachweis_{projekt_name}_{version or 'aktuell'}.{ext}"
        return send_file(BytesIO(data), mimetype=mime, as_attachment=True, download_name=name)
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/nachweis/freigeben")
@jwt_required()
@require_permission(Permission.CRA_EXPORT)
def konformitaet_nachweis_freigeben(projekt_name):
    """#1611: Nachweis je Version freigeben → PDF unveränderlich mit SHA-256 archivieren."""
    try:
        from cra.konformitaet_report import build_pdf
        from cra.konformitaet_gate import evaluate
        from cra import konformitaet_final_db as fdb
        body = request.get_json(silent=True) or {}
        version = str(body.get("version") or "").strip()
        if not version:
            return jsonify({"error": "Feld 'version' ist Pflicht"}), 400
        gate = evaluate(projekt_name, version=version)
        if gate["ampel"] == "rot" and not body.get("confirm_rot"):
            return jsonify({"error": "release_rot", "ampel": "rot",
                            "hinweis": "Release ist nicht konform (offene Punkte). Freigabe nur mit "
                                       "confirm_rot=true (als bewusste bedingte Freigabe).",
                            "offene_punkte": gate["offene_punkte"]}), 428
        pdf = build_pdf(projekt_name, version=version)
        rec = fdb.add_final(DB_PATH, projekt_name, version=version, pdf_bytes=pdf,
                            ampel=gate["ampel"], freigegeben_von=str(get_jwt_identity() or ""))
        _audit("cra.konformitaet.nachweis_freigegeben", projekt=projekt_name, version=version,
               sha256=rec["sha256"], ampel=gate["ampel"])
        return jsonify(rec)
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/nachweis/archiv")
@jwt_required()
@require_permission(Permission.CRA_READ)
def konformitaet_nachweis_archiv(projekt_name):
    try:
        from cra import konformitaet_final_db as fdb
        return jsonify({"eintraege": fdb.list_final(DB_PATH, projekt_name)})
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/nachweis/archiv/<int:final_id>/download")
@jwt_required()
@require_permission(Permission.CRA_READ)
def konformitaet_nachweis_archiv_download(projekt_name, final_id):
    try:
        from cra import konformitaet_final_db as fdb
        from flask import send_file
        rec = fdb.get_final(DB_PATH, projekt_name, final_id)
        if not rec or not Path(rec["pdf_path"]).is_file():
            return jsonify({"error": "Nachweis nicht gefunden"}), 404
        _audit("cra.konformitaet.nachweis_heruntergeladen", projekt=projekt_name, final_id=final_id)
        return send_file(Path(rec["pdf_path"]).resolve(), mimetype="application/pdf",
                         as_attachment=True,
                         download_name=f"CRA-Konformitaetsnachweis_{projekt_name}_{rec.get('version') or ''}.pdf")
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/versions")
@jwt_required()
@require_permission(Permission.CRA_READ)
def release_versions(projekt_name):
    """#1662: Versions-/Tag-Historie des verknüpften Repos (GitHub/GitLab)."""
    try:
        from shared.vcs_repo_config import resolve_repo
        from shared.vcs_versions import list_versions
        projekt = load_projekt(DB_PATH, projekt_name) or {}
        meta = projekt.get("meta") if isinstance(projekt.get("meta"), dict) else {}
        vcs = meta.get("vcs_publish") if isinstance(meta.get("vcs_publish"), dict) else {}
        repo = resolve_repo(vcs, None)
        provider = str(vcs.get("provider") or "github").strip().lower()
        versions = list_versions(provider, repo, vcs) if repo else []
        return jsonify({"repo": repo, "provider": provider if repo else None, "versions": versions})
    except Exception as e:
        return _log_500(e)


# ═══════════════════════════════════════════════════════════════════════════
# Release-Vorgang (#1743/#1744) und Phase-1-Feststellung (#1746) — v8.0.0
#
# CRA zerfällt für den Anwender in zwei Phasen: das Produkt einmalig konform
# machen, und danach bei jedem Release nachweisen, dass es dabei geblieben ist.
# Die Endpunkte hier bedienen die zweite Phase; die erste ist eine Feststellung
# am Projekt (`/cra-ready`).
#
# Die Rechte sind bewusst gemischt: Einreichen und Veröffentlichen gehören zur
# Entwicklung (CRA_WRITE), Freigabe und Zurückweisung zur Compliance
# (CRA_APPROVE). Eine Rolle, die beides kann, gibt es nicht mehr (#1743).
# ═══════════════════════════════════════════════════════════════════════════

def _gate(projekt_name: str, version: str = ""):
    """Rechenstand aus dem Gate — ohne Version die Produktsicht (Phase 1)."""
    from cra.konformitaet_gate import evaluate
    return evaluate(projekt_name, version=version or None)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/releases/katalog")
@jwt_required()
@require_permission(Permission.CRA_READ)
def release_katalog(projekt_name):
    """Der Rechts-Kanon der Release-Pflichten (Soll), unabhängig vom Vorgang."""
    from cra import release_checkliste as rc
    return jsonify({"katalog": rc.katalog(),
                    "begruendung_pflicht": sorted(rc.BEGRUENDUNG_PFLICHT),
                    "status_werte": list(rc.STATUS)})


@cra_konformitaet_bp.get("/projekte/<projekt_name>/releases")
@jwt_required()
@require_permission(Permission.CRA_READ)
def releases_liste(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    try:
        from cra import release_db as rdb
        vorgaenge = [v for v in kdb.list_konformitaet(DB_PATH, projekt_name)
                     if str(v.get("release_version") or "")]
        rel = rdb.get_release(DB_PATH, projekt_name)
        return jsonify({
            "releases": vorgaenge,
            "aktuelle_version": (rel or {}).get("aktuelle_version", ""),
            # Phase 1 kompakt mitliefern: Das Frontend zeigt sie als eine Zeile
            # über der Liste und soll dafür keinen zweiten Aufruf brauchen.
            "cra_ready": {
                "status": (rel or {}).get("bereit_status", "offen"),
                "von": (rel or {}).get("bereit_von", ""),
                "am": (rel or {}).get("bereit_am"),
                "entzug_grund": (rel or {}).get("bereit_entzug_grund", ""),
                # Der Kommentar oben verspricht, dass die Phase-1-Zeile ohne
                # zweiten Aufruf auskommt — dann muss „überholt" hier stehen.
                "ueberholt": rdb.bereit_ueberholt(rel, _gate(projekt_name)),
            },
        })
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.get("/projekte/<projekt_name>/releases/<version>")
@jwt_required()
@require_permission(Permission.CRA_READ)
def release_detail(projekt_name, version):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    try:
        from cra import release_checkliste as rc
        # Ein GET darf keinen Vorgang anlegen (#1747-Fund): Sonst erzeugt ein
        # Deep-Link mit Tippfehler in der Version einen leeren Entwurf, und
        # jeder Vorab-Abruf des Browsers schreibt in die Datenbank. Angelegt
        # wird ausdrücklich über POST.
        rec = kdb.get_konformitaet(DB_PATH, projekt_name, version)
        gate = _gate(projekt_name, version)
        if not rec:
            return jsonify({"vorgang": None, "gate": gate, "katalog": rc.katalog(),
                            "stand": rc.leerer_stand(), "gate_bei_einreichung": {},
                            "existiert": False})
        # Der gerechnete Stand kommt live aus dem Gate; was bei der Einreichung
        # galt, steht in `rec['gate']`. Beides getrennt ausliefern — sonst ist
        # nach der Freigabe nicht unterscheidbar, was geprüft wurde und was
        # sich seither geändert hat.
        return jsonify({"vorgang": rec, "gate": gate, "katalog": rc.katalog(),
                        "stand": rec.get("release_checkliste") or rc.leerer_stand(),
                        "gate_bei_einreichung": rec.get("gate") or {},
                        "existiert": True})
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/releases/<version>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def release_anlegen(projekt_name, version):
    """Vorgang für eine Release-Version ausdrücklich anlegen (idempotent)."""
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    if not str(version or "").strip():
        return jsonify({"error": "Version fehlt"}), 400
    try:
        rec = kdb.get_konformitaet(DB_PATH, projekt_name, version)
        if not rec:
            rec = kdb.save_konformitaet(DB_PATH, projekt_name,
                                        {"release_version": version})
            _audit("cra.release.angelegt", projekt=projekt_name, release=version)
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.put("/projekte/<projekt_name>/releases/<version>/checkliste/<item_id>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def release_checkliste_setzen(projekt_name, version, item_id):
    body = request.get_json(silent=True) or {}
    try:
        rec = kdb.set_release_checkliste(
            DB_PATH, projekt_name, version, item_id,
            status=str(body.get("status") or "offen"),
            begruendung=str(body.get("begruendung") or ""),
            von=str(get_jwt_identity() or ""))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.put("/projekte/<projekt_name>/releases/<version>/wesentliche-aenderung")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def release_wesentliche_aenderung(projekt_name, version):
    body = request.get_json(silent=True) or {}
    try:
        rec = kdb.set_wesentliche_aenderung(
            DB_PATH, projekt_name, version,
            wert=str(body.get("wert") or ""), grund=str(body.get("grund") or ""),
            von=str(get_jwt_identity() or ""))
        _audit("cra.release.wesentliche_aenderung", projekt=projekt_name,
               release=version, wert=rec.get("wesentliche_aenderung"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/releases/<version>/einreichen")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def release_einreichen(projekt_name, version):
    try:
        from cra import release_db as rdb
        gate = _gate(projekt_name, version)
        rec = kdb.einreichen(DB_PATH, projekt_name, version,
                             von=str(get_jwt_identity() or ""), gate=gate)
        # Bei JEDEM Release einen Snapshot einfrieren, nicht nur bei
        # wesentlichen Änderungen: Der Nachweis muss auf einen Stand zeigen,
        # der sich nicht mehr bewegt.
        rdb.snapshot_einfrieren(DB_PATH, projekt_name, version,
                                grund="Einreichung zur Prüfung")
        _audit("cra.release.eingereicht", projekt=projekt_name, release=version,
               ampel=gate.get("ampel"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/releases/<version>/zurueckweisen")
@jwt_required()
@require_permission(Permission.CRA_APPROVE)
def release_zurueckweisen(projekt_name, version):
    body = request.get_json(silent=True) or {}
    try:
        rec = kdb.zurueckweisen(DB_PATH, projekt_name, version,
                                von=str(get_jwt_identity() or ""),
                                grund=str(body.get("grund") or ""))
        _audit("cra.release.zurueckgewiesen", projekt=projekt_name, release=version)
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/releases/<version>/veroeffentlichen")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def release_veroeffentlichen(projekt_name, version):
    try:
        rec = kdb.veroeffentlichen(DB_PATH, projekt_name, version)
        _audit("cra.release.veroeffentlicht", projekt=projekt_name, release=version)
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


# ── Phase 1: CRA-Ready (#1746) ─────────────────────────────────────────────
@cra_konformitaet_bp.get("/projekte/<projekt_name>/cra-ready")
@jwt_required()
@require_permission(Permission.CRA_READ)
def cra_ready(projekt_name):
    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    try:
        from cra import release_db as rdb
        rec = rdb.get_release(DB_PATH, projekt_name)
        gate = _gate(projekt_name)
        return jsonify({
            "status": (rec or {}).get("bereit_status", "offen"),
            "von": (rec or {}).get("bereit_von", ""),
            "am": (rec or {}).get("bereit_am"),
            "entzug_grund": (rec or {}).get("bereit_entzug_grund", ""),
            "gate": gate,
            "gate_bei_feststellung": (rec or {}).get("bereit_gate") or {},
            # „überholt" heißt: Die Feststellung steht, der heutige Stand trägt
            # sie nicht mehr. Sie wird deshalb nicht gelöscht, sondern
            # widersprochen — löschen würde eine menschliche Aussage durch einen
            # Rechenlauf ersetzen.
            "ueberholt": rdb.bereit_ueberholt(rec, gate),
        })
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/cra-ready/feststellen")
@jwt_required()
@require_permission(Permission.CRA_APPROVE)
def cra_ready_feststellen(projekt_name):
    try:
        from cra import release_db as rdb
        rec = rdb.cra_ready_feststellen(DB_PATH, projekt_name,
                                        von=str(get_jwt_identity() or ""),
                                        gate=_gate(projekt_name))
        _audit("cra.cra_ready.festgestellt", projekt=projekt_name,
               von=rec.get("bereit_von"))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/cra-ready/entziehen")
@jwt_required()
@require_permission(Permission.CRA_APPROVE)
def cra_ready_entziehen(projekt_name):
    body = request.get_json(silent=True) or {}
    try:
        from cra import release_db as rdb
        rec = rdb.cra_ready_entziehen(DB_PATH, projekt_name,
                                      von=str(get_jwt_identity() or ""),
                                      grund=str(body.get("grund") or ""))
        _audit("cra.cra_ready.entzogen", projekt=projekt_name)
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)
