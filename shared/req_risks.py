"""Risiko für Nichterfüllung an Anforderungen/Controls ausweisen (#1564).

Modulübergreifend für CRA, NIS2, DSGVO und AI Act: An jeder Anforderung bzw. jedem
OWASP-Control kann ein Risiko der **verknüpften Risikobewertung** (``meta.linked_risk_projekt``
des Modul-Projekts) zugeordnet oder neu angelegt werden. Bewertet wird das Risiko in der
Risikobewertung — hier entstehen nur Verknüpfung + (unbewertetes) Risiko mit Herkunft.

Speicherort der Verknüpfung: ``risk_requirement_links`` in der RB-DB
(:mod:`shared.risk_req_links`, Spalten ``modul``/``object_kind``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

RB_DB_PATH = Path("data/db/risikobewertung.sqlite")
OBJECT_KINDS = ("requirement", "owasp", "owasp_llm")


@dataclass(frozen=True)
class ModulSpec:
    key: str
    label: str
    db_path: Path
    firma_field: str
    default_framework: str
    allowed_frameworks: frozenset[str] | None  # None = jede Bewertungsart
    rb_backref: str  # Rückverweis im RB-meta_json

    def load(self, name: str) -> dict[str, Any] | None:
        return _module_db(self.key).load_projekt(self.db_path, name)

    def update_meta(self, name: str, meta: dict[str, Any]) -> None:
        _module_db(self.key).update_projekt_meta(self.db_path, name, meta)


MODULE: dict[str, ModulSpec] = {
    "cra": ModulSpec("cra", "CRA", Path("data/db/cra.sqlite"), "unternehmen",
                     "STRIDE", None, "linked_cra_projekt"),
    "nis2": ModulSpec("nis2", "NIS2", Path("data/db/nis2.sqlite"), "unternehmen",
                      "STRIDE", None, "linked_nis2_projekt"),
    "dsgvo": ModulSpec("dsgvo", "DSGVO", Path("data/db/dsgvo.sqlite"), "unternehmen",
                       "DSGVO-DSFA", None, "linked_dsgvo_projekt"),
    # AI Act: A3/HR-01 verlangen die Bewertungsart EU-AI-Act (#1046) — gilt auch hier.
    "aiact": ModulSpec("aiact", "AI Act", Path("data/db/ai_act.sqlite"), "organisation",
                       "EU-AI-Act", frozenset({"EU-AI-Act"}), "linked_aiact_projekt"),
}


def _module_db(key: str):
    if key == "cra":
        import cra.db as m
    elif key == "nis2":
        import nis2.db as m
    elif key == "dsgvo":
        import dsgvo.db as m
    else:
        import ai_act.db as m
    return m


def spec(modul: str) -> ModulSpec:
    if modul not in MODULE:
        raise ValueError(f"Unbekanntes Modul: {modul}")
    return MODULE[modul]


def _meta(p: dict[str, Any] | None) -> dict[str, Any]:
    m = (p or {}).get("meta")
    return dict(m) if isinstance(m, dict) else {}


# ── RB-Projekt-Verknüpfung (modulweit) ──────────────────────────────────────────

def linked_rb(modul: str, projekt: str) -> str:
    return (_meta(spec(modul).load(projekt)).get("linked_risk_projekt") or "").strip()


def rb_candidates(modul: str, projekt: str) -> list[dict[str, Any]]:
    """Verknüpfbare RB-Projekte: gleiche Firma zuerst; AI Act nur EU-AI-Act."""
    s = spec(modul)
    p = s.load(projekt) or {}
    firma = (p.get(s.firma_field) or "").strip().casefold()
    from risikobewertung.db import list_projekte, load_projekt as rb_load
    out = []
    for name in list_projekte(RB_DB_PATH):
        rbp = rb_load(RB_DB_PATH, name) or {}
        fw = rbp.get("framework") or ""
        if s.allowed_frameworks and fw not in s.allowed_frameworks:
            continue
        unt = (rbp.get("unternehmen") or "").strip()
        out.append({"name": name, "framework": fw, "unternehmen": unt,
                    "firma_match": bool(firma) and unt.casefold() == firma})
    out.sort(key=lambda c: (not c["firma_match"], c["name"].casefold()))
    return out


def link_rb(modul: str, projekt: str, rb_name: str) -> None:
    """RB-Projekt bidirektional verknüpfen (gleiche Meta-Keys wie CRA #881 / AI Act #1044)."""
    s = spec(modul)
    p = s.load(projekt)
    if not p:
        raise LookupError("Projekt nicht gefunden")
    from risikobewertung.db import load_projekt as rb_load, update_projekt_meta as rb_update
    rbp = rb_load(RB_DB_PATH, rb_name)
    if not rbp:
        raise LookupError(f"Risikobewertung nicht gefunden: {rb_name}")
    if s.allowed_frameworks and (rbp.get("framework") or "") not in s.allowed_frameworks:
        raise ValueError(f"Für {s.label} sind nur Risikobewertungen mit Bewertungsart "
                         f"{', '.join(sorted(s.allowed_frameworks))} zulässig.")
    meta = _meta(p)
    meta["linked_risk_projekt"] = rb_name
    s.update_meta(projekt, meta)
    rb_meta = _meta(rbp)
    rb_meta[s.rb_backref] = projekt
    rb_update(RB_DB_PATH, rb_name, rb_meta)


def create_rb(modul: str, projekt: str, framework: str | None = None) -> str:
    """Neue Risikobewertung „<Projekt> – Risikoanalyse" anlegen und verknüpfen."""
    s = spec(modul)
    p = s.load(projekt)
    if not p:
        raise LookupError("Projekt nicht gefunden")
    if linked_rb(modul, projekt):
        raise ValueError("Es ist bereits eine Risikobewertung verknüpft.")
    fw = (framework or s.default_framework).strip()
    if s.allowed_frameworks and fw not in s.allowed_frameworks:
        fw = s.default_framework
    from risikobewertung.db import load_projekt as rb_load, save_projekt as rb_save
    base = f"{projekt} – Risikoanalyse"
    name, n = base, 2
    while rb_load(RB_DB_PATH, name):
        name, n = f"{base} ({n})", n + 1
    rb_save(RB_DB_PATH, name, fw, f"Risikoanalyse zu {s.label}-Projekt „{projekt}“.",
            meta={s.rb_backref: projekt},
            unternehmen=(p.get(s.firma_field) or "").strip(),
            produkt=(p.get("produkt") or "").strip())
    link_rb(modul, projekt, name)
    return name


# ── Risiken an Anforderung/Control ──────────────────────────────────────────────

def _risk_view(r: dict[str, Any]) -> dict[str, Any]:
    return {"id": r.get("id"), "nr": r.get("nr"), "risk_name": r.get("risk_name") or "",
            "risikowert": r.get("risikowert"), "risiko_label": r.get("risiko_label") or "",
            "bewertet": r.get("risikowert") is not None, "is_resolved": bool(r.get("is_resolved")),
            # #1608/#1613: Behandlung/Akzeptanz an der Anforderungs-Verknüpfung sichtbar
            "behandlung": r.get("behandlung") or "offen",
            "akzeptanz_kategorie": r.get("akzeptanz_kategorie") or "",
            "akzeptanz_grund": r.get("akzeptanz_grund") or "",
            "akzeptanz_von": r.get("akzeptanz_von") or "",
            "akzeptanz_am": r.get("akzeptanz_am"),
            "rechtsgrundlage": r.get("rechtsgrundlage") or ""}


def _require_rb(modul: str, projekt: str) -> str:
    rb = linked_rb(modul, projekt)
    if not rb:
        raise ValueError("Keine Risikobewertung verknüpft.")
    return rb


def _check_kind(kind: str) -> None:
    if kind not in OBJECT_KINDS:
        raise ValueError(f"Unbekannte Objektart: {kind}")


def object_risks(modul: str, projekt: str, kind: str, obj_id: str) -> dict[str, Any]:
    """Verknüpfte Risiken eines Objekts + übrige Risiken der RB (zum Verknüpfen)."""
    _check_kind(kind)
    rb = linked_rb(modul, projekt)
    if not rb:
        return {"linked_risk_projekt": None, "risks": [], "verfuegbar": []}
    from risikobewertung.db import load_risiken
    from shared.risk_req_links import list_for_object
    alle = {int(r["id"]): r for r in load_risiken(RB_DB_PATH, rb) if r.get("id") is not None}
    ids = [l.risk_id for l in list_for_object(RB_DB_PATH, rb_projekt_name=rb, modul=modul,
                                               object_kind=kind, anforderung_id=obj_id)]
    risks = [_risk_view(alle[i]) for i in ids if i in alle]
    verfuegbar = [_risk_view(r) for i, r in sorted(alle.items()) if i not in set(ids)]
    return {"linked_risk_projekt": rb, "risks": risks, "verfuegbar": verfuegbar}


def gap_text(modul: str, kind: str, obj_id: str, titel: str, score: Any, kommentar: str) -> tuple[str, str]:
    """Titel + Beschreibung eines Nichterfüllungs-Risikos (vorbefüllt, editierbar)."""
    art = {"requirement": "Anforderung", "owasp": "OWASP-Control", "owasp_llm": "OWASP-LLM-Risiko"}[kind]
    name = f"Nichterfüllung {obj_id}: {titel}".strip().rstrip(":")[:250]
    lines = [f"{spec(modul).label}-{art} {obj_id} ({titel}) ist nicht vollständig erfüllt."]
    if score not in (None, ""):
        lines.append(f"Aktueller Erfüllungsgrad: {score}/5.")
    if (kommentar or "").strip():
        lines += ["", "Bewertungskommentar:", kommentar.strip()[:3000]]
    lines += ["", "Risiko aus der Nichterfüllung — Eintrittswahrscheinlichkeit und Auswirkung "
              "sind in der Risikobewertung zu bewerten."]
    return name, "\n".join(lines)


def create_gap_risk(modul: str, projekt: str, kind: str, obj_id: str, *, titel: str,
                    risk_name: str = "", beschreibung: str = "", score: Any = None,
                    kommentar: str = "") -> dict[str, Any]:
    """Unbewertetes Risiko in der verknüpften RB anlegen und mit dem Objekt verknüpfen.

    Herkunft wird in ``felder._source``/``_source_id`` festgehalten (Muster #887)."""
    _check_kind(kind)
    rb = _require_rb(modul, projekt)
    from risikobewertung.db import load_projekt as rb_load, load_risiken, save_risiko
    from shared.risk_req_links import add_link
    d_name, d_beschr = gap_text(modul, kind, obj_id, titel, score, kommentar)
    rbp = rb_load(RB_DB_PATH, rb) or {}
    nr = max([int(r.get("nr") or 0) for r in load_risiken(RB_DB_PATH, rb)] or [0]) + 1
    rid = save_risiko(RB_DB_PATH, {
        "projekt_name": rb, "nr": nr,
        "risk_name": (risk_name or d_name).strip()[:250],
        "beschreibung": (beschreibung or d_beschr).strip(),
        "framework": rbp.get("framework") or spec(modul).default_framework,
        "felder": {"_source": "req-gap", "_source_id": f"{modul}:{kind}:{obj_id}",
                   "_source_projekt": projekt},
        "risikowert": None, "risiko_label": "", "detail_text": "",
    })
    add_link(RB_DB_PATH, rb_projekt_name=rb, risk_id=int(rid), anforderung_id=obj_id,
             cra_projekt_name=projekt, modul=modul, object_kind=kind)
    return {"rb_projekt": rb, "risk_id": int(rid), "nr": nr}


def link_risk(modul: str, projekt: str, kind: str, obj_id: str, risk_id: int) -> None:
    _check_kind(kind)
    rb = _require_rb(modul, projekt)
    from risikobewertung.db import load_risiken
    if not any(int(r.get("id") or 0) == int(risk_id) for r in load_risiken(RB_DB_PATH, rb)):
        raise LookupError("Risiko nicht gefunden")
    from shared.risk_req_links import add_link
    add_link(RB_DB_PATH, rb_projekt_name=rb, risk_id=int(risk_id), anforderung_id=obj_id,
             cra_projekt_name=projekt, modul=modul, object_kind=kind)


def unlink_risk(modul: str, projekt: str, kind: str, obj_id: str, risk_id: int) -> None:
    """Nur die Verknüpfung lösen — das Risiko bleibt in der Risikobewertung bestehen."""
    _check_kind(kind)
    rb = _require_rb(modul, projekt)
    from shared.risk_req_links import delete_object_link
    delete_object_link(RB_DB_PATH, rb_projekt_name=rb, risk_id=int(risk_id), modul=modul,
                       object_kind=kind, anforderung_id=obj_id)


def coverage(modul: str, projekt: str) -> dict[str, Any]:
    """Anzahl verknüpfter Risiken je ``<kind>:<id>`` (für Listen-Badges)."""
    rb = linked_rb(modul, projekt)
    out: dict[str, int] = {}
    if rb:
        from shared.risk_req_links import list_for_project
        for l in list_for_project(RB_DB_PATH, rb_projekt_name=rb):
            if l.modul == modul:
                k = f"{l.object_kind}:{l.anforderung_id}"
                out[k] = out.get(k, 0) + 1
    return {"linked_risk_projekt": rb or None, "coverage": out}


# ── REST-Routen (an jeden Modul-Blueprint gehängt) ──────────────────────────────

def register_routes(bp, modul: str) -> None:
    """Hängt ``/projekte/<p>/req-risks…`` an ``bp`` (CRA/NIS2/DSGVO/AI Act)."""
    from flask import jsonify, request
    from flask_jwt_extended import jwt_required, get_jwt_identity

    ep = f"req_risks_{modul}"

    def _audit(action: str, projekt: str, **details):
        try:
            from shared.audit import audit_event
            audit_event(f"{modul}.{action}", module=modul,
                        details={"projekt": projekt, "actor": str(get_jwt_identity() or ""), **details})
        except Exception:  # noqa: BLE001
            pass

    def _wrap(fn):
        def inner(*a, **kw):
            try:
                if not spec(modul).load(kw.get("projekt_name", "")):
                    return jsonify({"error": "Projekt nicht gefunden"}), 404
                return fn(*a, **kw)
            except LookupError as e:
                return jsonify({"error": str(e)}), 404
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:  # noqa: BLE001
                from flask import current_app
                current_app.logger.exception("%s %s — %s", request.method, request.path, e)
                return jsonify({"error": "Interner Serverfehler"}), 500
        inner.__name__ = f"{ep}_{fn.__name__}"
        return jwt_required()(inner)

    def overview(projekt_name):
        out = coverage(modul, projekt_name)
        out["framework_hint"] = spec(modul).default_framework
        out["frameworks_fix"] = sorted(spec(modul).allowed_frameworks or [])
        if not out["linked_risk_projekt"]:
            out["candidates"] = rb_candidates(modul, projekt_name)
        return jsonify(out)

    def set_link(projekt_name):
        rb = str((request.get_json(silent=True) or {}).get("rb_projekt") or "").strip()
        if not rb:
            return jsonify({"error": 'Feld "rb_projekt" ist Pflicht'}), 400
        link_rb(modul, projekt_name, rb)
        _audit("req_risk.rb_linked", projekt_name, rb_projekt=rb)
        return jsonify({"linked_risk_projekt": rb})

    def create_rb_route(projekt_name):
        body = request.get_json(silent=True) or {}
        rb = create_rb(modul, projekt_name, body.get("framework"))
        _audit("req_risk.rb_created", projekt_name, rb_projekt=rb)
        return jsonify({"linked_risk_projekt": rb}), 201

    def get_obj(projekt_name, kind, obj_id):
        return jsonify(object_risks(modul, projekt_name, kind, obj_id))

    def post_obj(projekt_name, kind, obj_id):
        body = request.get_json(silent=True) or {}
        if body.get("risk_id") not in (None, ""):
            link_risk(modul, projekt_name, kind, obj_id, int(body["risk_id"]))
            _audit("req_risk.linked", projekt_name, kind=kind, object_id=obj_id, risk_id=body["risk_id"])
            return jsonify(object_risks(modul, projekt_name, kind, obj_id))
        res = create_gap_risk(modul, projekt_name, kind, obj_id,
                              titel=str(body.get("titel") or ""),
                              risk_name=str(body.get("risk_name") or ""),
                              beschreibung=str(body.get("beschreibung") or ""),
                              score=body.get("score"), kommentar=str(body.get("kommentar") or ""))
        _audit("req_risk.created", projekt_name, kind=kind, object_id=obj_id, **res)
        return jsonify({**object_risks(modul, projekt_name, kind, obj_id), "created": res}), 201

    def del_obj(projekt_name, kind, obj_id, risk_id):
        unlink_risk(modul, projekt_name, kind, obj_id, risk_id)
        _audit("req_risk.unlinked", projekt_name, kind=kind, object_id=obj_id, risk_id=risk_id)
        return jsonify(object_risks(modul, projekt_name, kind, obj_id))

    base = "/projekte/<projekt_name>/req-risks"
    bp.add_url_rule(base, f"{ep}_overview", _wrap(overview), methods=["GET"])
    bp.add_url_rule(f"{base}/link", f"{ep}_link", _wrap(set_link), methods=["PUT"])
    bp.add_url_rule(f"{base}/create-rb", f"{ep}_create_rb", _wrap(create_rb_route), methods=["POST"])
    bp.add_url_rule(f"{base}/<kind>/<obj_id>", f"{ep}_get", _wrap(get_obj), methods=["GET"])
    bp.add_url_rule(f"{base}/<kind>/<obj_id>", f"{ep}_post", _wrap(post_obj), methods=["POST"])
    bp.add_url_rule(f"{base}/<kind>/<obj_id>/<int:risk_id>", f"{ep}_del", _wrap(del_obj),
                    methods=["DELETE"])
