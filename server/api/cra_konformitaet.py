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
@cra_konformitaet_bp.get("/projekte/<projekt_name>/konformitaet/sicherheitstests")
@jwt_required()
@require_permission(Permission.CRA_READ)
def get_sicherheitstests(projekt_name):
    """#1824: Stand zu Anhang I Teil II Nr. 3 — Arten, Nachweise, Befunde."""
    from cra import sicherheitstests as st

    try:
        release = request.args.get("release", "")
        return jsonify({
            "arten": [{"wert": a, "label": st.ART_LABEL.get(a, a)}
                      for a in st.ARTEN],
            "min_begruendung": st.MIN_BEGRUENDUNG,
            "max_monate": st.MAX_MONATE,
            "befund": st.befund(DB_PATH, projekt_name, release)})
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.put("/projekte/<projekt_name>/konformitaet/sicherheitstests")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def put_sicherheitstests(projekt_name):
    """#1824: Womit wird Anhang I Teil II Nr. 3 belegt?

    Eigener Endpunkt und nicht ein paar Felder mehr am Konformitäts-Formular:
    Der Verzicht trägt Person und Zeitpunkt, und die stempelt der Server. Eine
    Entscheidung, deren Urheber der Browser mitschickt, ist keine (Muster
    ``release_art_setzen``, #1793).
    """
    from cra import sicherheitstests as st

    _, err = require_projekt(load_projekt, DB_PATH, projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        release = str(body.get("release_version") or "")
        rec = kdb.set_sicherheitstests(DB_PATH, projekt_name, release, body,
                                       von=str(get_jwt_identity() or ""))
        _audit("cra.sicherheitstests.gesetzt", projekt=projekt_name,
               release=release, art=rec.get("testnachweis_art"))
        return jsonify({"vorgang": rec,
                        "befund": st.befund(DB_PATH, projekt_name, release)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _log_500(e)


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


@cra_konformitaet_bp.get("/projekte/<projekt_name>/konformitaet/doc/vorschlag")
@jwt_required()
@require_permission(Permission.CRA_READ)
def doc_vorschlag(projekt_name):
    """Anhang-V-Angaben aus den Quellen — ohne KI, ohne Nebenwirkung (#1884/#1887).

    Liefert je Feld ``{wert, quelle, klasse}``, den Gegenstand samt
    Fundstellen und Auslassungen, die belegten Normen-Kandidaten, die beiden
    Auswahlkataloge **und** die Befunde aus #1885 — in **einer** Antwort.
    Zwei Abfragen für denselben Stand wären zwei Wahrheiten, und hier
    entscheidet der Stand, ob ein Knopf etwas füllen darf (#1726/#1727).

    Rein lesend: Geschrieben wird erst, wenn der Anwender übernimmt. Ein
    gefülltes Feld ist die Aussage eines Menschen (#1769/#1773).
    """
    _p, err = _require_projekt(projekt_name)
    if err:
        return err
    try:
        from cra import doc_pruefung, doc_vorschlag as dv

        release = request.args.get("release", "")
        out = dv.vorschlag(DB_PATH, projekt_name, release)
        try:
            out["befunde"] = doc_pruefung.befunde(DB_PATH, projekt_name, release)
        except Exception as e:  # noqa: BLE001
            # Ein Vorschlag ohne Befunde ist brauchbar; ein Vorschlag, der
            # ganz ausfällt, nicht. Der Ausstellungsweg prüft ohnehin
            # fail-closed (`_pruefe_anhang_v`).
            current_app.logger.warning("Befunde nicht ermittelbar: %s", e)
            out["befunde"] = []
        return jsonify(out)
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.put("/projekte/<projekt_name>/konformitaet/doc")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def save_doc(projekt_name):
    """Die Erklärung als Entwurf speichern (#1887).

    Bis v8.2.2 gab es nur „ausstellen" — und das verlangt alle Pflichtangaben.
    Wer die Erklärung ausfüllte und noch nicht ausstellen konnte, verlor beim
    nächsten Laden alles. Hier wird **nur** gespeichert: keine
    Vollständigkeitsprüfung, keine Fassungsnummer, kein ``doc_ausgestellt``.
    Geprüft wird beim Ausstellen — dort, wo es zählt.
    """
    body = request.get_json(silent=True) or {}
    try:
        rec = kdb.save_doc(DB_PATH, projekt_name, body.get("doc") or {},
                           body.get("release_version", ""))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.put("/projekte/<projekt_name>/konformitaet/hersteller")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def put_hersteller(projekt_name):
    """Herstellerangaben des **Mandanten** (#1887).

    Anschrift, Ort und Unterzeichner gehören der Firma, nicht dem einzelnen
    CRA-Projekt: Ein Mandant hat mehrere Produkte, und die Anschrift je Projekt
    zu tippen ist genau die Doppelpflege, die hier wegfällt — beim vierten Mal
    steht sonst eine andere da.

    Erfasst wird sie trotzdem **hier**, im Konformitäts-Tab, weil der Anwender
    beim Ausfüllen der Erklärung merkt, dass sie fehlt. Der Mandant wird über
    ``shared.firmen_link.projekt_firmen_id`` aufgelöst — dieselbe Auflösung,
    die die Firmen-ACL benutzt; wer das Projekt nicht sehen darf, kommt also
    auch an diese Angaben nicht.
    """
    _p, err = _require_projekt(projekt_name)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        from cra.doc_vorschlag import _STAMM_SPALTEN, hersteller_stammdaten
        from firmen.db import DEFAULT_DB_PATH as FIRMEN_DB, load_firma, save_firma
        from shared.firmen_link import firmen_name_to_id, projekt_firmen_id

        # `projekt_firmen_id` nimmt den **DB-Pfad**, nicht den Modulnamen:
        # `MODULE_PROJECT_TABLES` ist nach Dateinamen geschlüsselt.
        fid = projekt_firmen_id(DB_PATH, projekt_name)
        if not fid:
            return jsonify({
                "error": "Dem Projekt ist kein Mandant zugeordnet — die "
                         "Herstellerangaben haben damit keinen Ort. Firma im "
                         "Projekt zuordnen (Administration → Firmen-Zuordnung).",
                "code": "kein-mandant"}), 409
        name = ""
        for kandidat, kennung in (firmen_name_to_id(FIRMEN_DB) or {}).items():
            if int(kennung) == int(fid):
                name = str(kandidat)
                break
        if not name:
            return jsonify({"error": "Mandant nicht lesbar"}), 409

        # #1892: Geschrieben werden die **echten Spalten** der Firma, nicht
        # mehr `meta.hersteller`. Teil-Update: Nur was der Aufrufer nennt —
        # sonst leert jedes Speichern die übrigen Angaben (die Falle aus
        # #1540/#1771/#1805).
        felder = {spalte: str(body.get(schluessel) or "").strip()
                  for schluessel, spalte in _STAMM_SPALTEN.items()
                  if schluessel in body}
        if felder:
            save_firma(FIRMEN_DB, name, **felder)
        firma = load_firma(FIRMEN_DB, name) or {}
        _audit("cra.konformitaet.hersteller_gespeichert", projekt=projekt_name,
               firma=name, felder=sorted(felder))
        return jsonify({"firma": name,
                        "hersteller": hersteller_stammdaten(firma)})
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/konformitaet/doc")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def issue_doc(projekt_name):
    body = request.get_json(silent=True) or {}
    release = body.get("release_version", "")
    doc = body.get("doc") or {}
    bestaetigt = body.get("bestaetigt") or []
    if isinstance(bestaetigt, str):
        bestaetigt = [bestaetigt]
    try:
        # #1753: Eine Erklärung ohne die Pflichtangaben aus Anhang V ist
        # unwirksam. Sie als „ausgestellt“ zu speichern wäre deshalb schlimmer
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

        # #1885: Widersprüche blockieren; echte Grenzfälle verlangen eine
        # benannte Bestätigung (428, Muster `confirm_rot` aus #1611).
        from cra.doc_pruefung import BestaetigungErforderlich, ErklaerungUnstimmig

        try:
            rec = kdb.issue_doc(DB_PATH, projekt_name, doc, release, bestaetigt)
        except ErklaerungUnstimmig as e:
            return jsonify({"error": str(e), "befunde": e.befunde,
                            "code": "erklaerung-unstimmig"}), 409
        except BestaetigungErforderlich as e:
            return jsonify({"error": str(e), "befunde": e.befunde,
                            "bestaetigung": e.schluessel,
                            "code": "bestaetigung-erforderlich"}), 428
        _audit("cra.konformitaet.doc_ausgestellt", projekt=projekt_name,
               doc_version=rec.get("doc_version"),
               bestaetigt=list(bestaetigt))

        # Ausgestellte Fassung unveränderlich ablegen (PDF + SHA-256). Best
        # effort: Fehlt der PDF-Konverter, ist die Erklärung trotzdem
        # ausgestellt — aber der Aufrufer erfährt es, statt es zu vermuten.
        archiv_fehler = ""
        try:
            abgelegt = doc_export.ausstellen(projekt_name, release_version=release,
                                             von=str(get_jwt_identity() or ""),
                                             bestaetigt=bestaetigt)
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
        # #1876: Verworfene Vorgaenge stehen standardmaessig nicht in der
        # Liste — sie sollen sie nicht belasten. Sichtbar ueber ?mit_verworfenen=1,
        # denn geloescht sind sie nicht: Dass eine Version erwogen und dann
        # verworfen wurde, ist selbst eine Aussage ueber das Produkt.
        mit_verworfenen = str(request.args.get("mit_verworfenen", "")).lower() in (
            "1", "true", "ja")
        alle = [v for v in kdb.list_konformitaet(DB_PATH, projekt_name)
                if str(v.get("release_version") or "")]
        vorgaenge = alle if mit_verworfenen else [
            v for v in alle if str(v.get("freigabe_status") or "") != "verworfen"]
        verworfen_anzahl = sum(1 for v in alle
                               if str(v.get("freigabe_status") or "") == "verworfen")
        rel = rdb.get_release(DB_PATH, projekt_name)
        return jsonify({
            "releases": vorgaenge,
            # Damit die Oberflaeche den Schalter nur zeigt, wenn es etwas zu
            # zeigen gibt — ein Schalter ohne Wirkung ist ein Knopf ohne
            # Wirkung (#1805).
            "verworfen_anzahl": verworfen_anzahl,
            "aktuelle_version": (rel or {}).get("aktuelle_version", ""),
            # Phase 1 kompakt mitliefern: Das Frontend zeigt sie als eine Zeile
            # über der Liste und soll dafür keinen zweiten Aufruf brauchen.
            "cra_ready": {
                "status": (rel or {}).get("bereit_status", "offen"),
                "von": (rel or {}).get("bereit_von", ""),
                "am": (rel or {}).get("bereit_am"),
                "entzug_grund": (rel or {}).get("bereit_entzug_grund", ""),
                # Der Kommentar oben verspricht, dass die Phase-1-Zeile ohne
                # zweiten Aufruf auskommt — dann muss „überholt“ hier stehen.
                "ueberholt": rdb.bereit_ueberholt(rel, _gate(projekt_name)),
            },
        })
    except Exception as e:
        return _log_500(e)


def _arten_katalog() -> list[dict[str, str]]:
    """Die wählbaren Release-Arten mit Label und Erklärung.

    Serverseitig, damit die Oberfläche die Liste nicht ein zweites Mal führt —
    dieselbe Regel wie bei der Vorlagen-Vorauswahl (#1777) und der
    Modul-Sichtbarkeit (#1703/S9).
    """
    from cra import release_art as ra

    return [{"key": a, "label": ra.LABELS[a], "erklaerung": ra.ERKLAERUNG[a]}
            for a in ra.ARTEN]


def _art_vorschlag(rec: dict) -> dict[str, str]:
    from cra import release_art as ra

    return ra.vorschlag(str((rec or {}).get("release_art") or ""))


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
                            "arten": _arten_katalog(), "art_vorschlag": {},
                            "existiert": False})
        # Der gerechnete Stand kommt live aus dem Gate; was bei der Einreichung
        # galt, steht in `rec['gate']`. Beides getrennt ausliefern — sonst ist
        # nach der Freigabe nicht unterscheidbar, was geprüft wurde und was
        # sich seither geändert hat.
        return jsonify({"vorgang": rec, "gate": gate, "katalog": rc.katalog(),
                        "stand": rec.get("release_checkliste") or rc.leerer_stand(),
                        "gate_bei_einreichung": rec.get("gate") or {},
                        "arten": _arten_katalog(),
                        "art_vorschlag": _art_vorschlag(rec),
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


@cra_konformitaet_bp.post("/projekte/<projekt_name>/releases/<version>/verwerfen")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def release_verwerfen(projekt_name, version):
    """#1876: Einen nicht veröffentlichten Release-Vorgang verwerfen.

    Person und Zeitpunkt stempelt die Datenschicht, nicht der Aufrufer.
    Ein Versuch an einem veröffentlichten Release oder ohne Begründung
    kommt als 409 zurück — wie jede andere Fachregel hier.
    """
    body = request.get_json(silent=True) or {}
    try:
        rec = kdb.verwerfen(DB_PATH, projekt_name, version,
                            von=str(get_jwt_identity() or ""),
                            grund=str(body.get("grund") or ""))
        _audit("cra.release.verworfen", projekt=projekt_name, version=version,
               grund_laenge=len(str(body.get("grund") or "").strip()))
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/releases/<version>/wiederaufnehmen")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def release_wiederaufnehmen(projekt_name, version):
    """#1876: Einen verworfenen Vorgang zurück in den Entwurf holen."""
    try:
        rec = kdb.wiederaufnehmen(DB_PATH, projekt_name, version,
                                  von=str(get_jwt_identity() or ""))
        _audit("cra.release.wiederaufgenommen", projekt=projekt_name, version=version)
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.delete("/projekte/<projekt_name>/releases/<version>")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def release_loeschen(projekt_name, version):
    """#1876: Einen **unberührten** Entwurf hart entfernen.

    Die Ausnahme, nicht die Regel. Hängt am Vorgang schon etwas — eine
    Checklisten-Antwort, eine ausgestellte Erklärung, ein Snapshot, ein
    Archiv-Eintrag —, kommt 409 und der Weg heißt „verwerfen".
    """
    try:
        kdb.loeschen(DB_PATH, projekt_name, version)
        _audit("cra.release.geloescht", projekt=projekt_name, version=version)
        return jsonify({"ok": True, "geloescht": version})
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.put("/projekte/<projekt_name>/releases/<version>/art")
@jwt_required()
@require_permission(Permission.CRA_WRITE)
def release_art_setzen(projekt_name, version):
    """#1793: Die Art des Releases erklären.

    Die Antwort auf die Kernfrage wird hier **nicht** mitgeschrieben — der
    Vorschlag geht in der Antwort mit, gespeichert wird er über den eigenen
    Endpunkt. Sonst stünde eine Begründung in der Akte, die niemand gelesen hat.
    """
    from cra import release_art as ra

    body = request.get_json(silent=True) or {}
    try:
        rec = kdb.set_release_art(
            DB_PATH, projekt_name, version,
            art=str(body.get("art") or ""), von=str(get_jwt_identity() or ""))
        _audit("cra.release.art", projekt=projekt_name, release=version,
               art=rec.get("release_art"))
        return jsonify({"vorgang": rec,
                        "vorschlag": ra.vorschlag(str(rec.get("release_art") or ""))})
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
            # „überholt“ heißt: Die Feststellung steht, der heutige Stand trägt
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


# ── #1864/B: Die eigene Akte gegen die Rückfragen eines Prüfers lesen ──────────
#
# Auf **Knopfdruck**, nicht automatisch: Der Lauf liest die ganze Akte und
# kostet entsprechend. Er erzeugt eine Mängelliste, **kein** zweites Urteil —
# das Gate rechnet, die KI liest (#1726/#1727/#1776).

@cra_konformitaet_bp.get("/projekte/<projekt_name>/aktenpruefung/prompt")
@jwt_required()
@require_permission(Permission.CRA_READ)
def aktenpruefung_prompt(projekt_name):
    """Der Prompt zum Kopieren — der Copy/Paste-Weg bleibt erhalten."""
    try:
        from cra.aktenpruefung import baue_prompt
        version = request.args.get("version") or ""
        return jsonify({"prompt": baue_prompt(projekt_name, version),
                        "version": version})
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/aktenpruefung")
@jwt_required()
@require_permission(Permission.CRA_READ)
def aktenpruefung(projekt_name):
    """Direktlauf über die KI. Body: ``{version, confirmed}``.

    Lesendes Recht genügt: Der Lauf **schreibt nichts** an der Akte. Die
    Freigaberechte (#1743) bleiben der Freigabe vorbehalten.
    """
    try:
        from cra.aktenpruefung import pruefe
        from shared.ki_engine import EgressNichtBestaetigt
        daten = request.json or {}
        try:
            return jsonify(pruefe(projekt_name, str(daten.get("version") or "")))
        except EgressNichtBestaetigt as e:
            return jsonify({"error": str(e), "code": "egress-bestaetigung"}), 428
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 409
    except Exception as e:
        return _log_500(e)


@cra_konformitaet_bp.post("/projekte/<projekt_name>/aktenpruefung/import")
@jwt_required()
@require_permission(Permission.CRA_READ)
def aktenpruefung_import(projekt_name):
    """Eine von Hand eingefügte Antwort auswerten — gleiche Prüfung wie oben.

    Insbesondere fallen hier dieselben Felder weg: Eine mitgelieferte Ampel
    oder Punktzahl wird verworfen, nicht angezeigt.
    """
    try:
        from cra.aktenpruefung import parse_antwort
        daten = request.json or {}
        roh = daten.get("response") or daten.get("raw") or ""
        if not str(roh).strip():
            return jsonify({"error": "Keine Antwort übergeben"}), 400
        return jsonify({"befunde": parse_antwort(roh), "provider": "copy-paste"})
    except Exception as e:
        return _log_500(e)
