"""CRA-Adapter für die zentrale Word-Vorlagen-Engine (#993, Story 5).

Liefert einen für Jinja-Vorlagen robusten Kontext (``build_cra_context``) sowie
die dokumentierte Variablenliste (``CRA_VARIABLES``). Die Engine in
``shared/templates/engine.py`` rendert hochgeladene DOCX-Vorlagen mit diesem
Kontext; ``shared/templates/schema.py`` lädt beide Symbole per guarded import.

Design-Regeln:
  - **Keine None-Werte**: fehlende Daten werden zu leeren Strings/Listen/0.
  - Vorhandene Bericht-Logik (Reifegrad, verknüpfte Risikobewertung) wird über
    ``cra.report_export``/``cra.requirements`` wiederverwendet, NICHT dupliziert.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


# ── Dokumentierte Top-Level-Variablen ──────────────────────────────────────────
CRA_VARIABLES: list[dict[str, Any]] = [
    {
        "key": "projekt",
        "typ": "object",
        "beschreibung": "Projekt-Stammdaten (name, unternehmen, produkt, "
                        "produktklasse, produktklasse_label, beschreibung, "
                        "berater, konformitaet, referenz).",
        "pflicht": True,
    },
    {
        "key": "bewertungen",
        "typ": "list",
        "beschreibung": "Anforderungsbewertungen je CRA-Anforderung "
                        "(id, kapitel, titel, ref, bewertung, bewertung_label, "
                        "kommentar, massnahme, verantwortlich, zieldatum, gewichtung).",
        "pflicht": False,
    },
    {
        "key": "risiken",
        "typ": "list",
        "beschreibung": "Top-Risiken aus der verknüpften Risikobewertung "
                        "(name, label, wert). Leer, wenn keine RB verknüpft ist.",
        "pflicht": False,
    },
    {
        "key": "meta",
        "typ": "object",
        "beschreibung": "Berichts-Metadaten (datum, reifegrad_pct, ampel, "
                        "bewertete_count, gesamt_count, kapitel, "
                        "risiko_verknuepft, risiko_projekt, framework, "
                        "vulns, threatmodel).",
        "pflicht": False,
    },
    {
        "key": "dokumente",
        "typ": "list",
        "beschreibung": "Finalisierte/freigegebene gemanagte Dokumente des "
                        "Projekts (titel, doc_type, rechtsgrundlage, status, "
                        "version, stand).",
        "pflicht": False,
    },
]


# DB-Modulkennung für die generische Dokument-Persistenz (shared.documents).
_DOC_MODUL = "cra"


def _s(value: Any) -> str:
    """None-sichere String-Konvertierung."""
    return "" if value is None else str(value)


def _dokumente(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Finalisierte/freigegebene gemanagte Dokumente (Jinja-sicher, nie None)."""
    try:
        from shared.documents.db import list_documents
        from shared.documents.catalog import get_doc_spec
        out: list[dict[str, Any]] = []
        for d in list_documents(db_path, _DOC_MODUL, projekt_name):
            if _s(d.get("status")) not in ("final", "freigegeben"):
                continue
            spec = get_doc_spec(_DOC_MODUL, _s(d.get("doc_type"))) or {}
            out.append({
                "titel": _s(d.get("titel")),
                "doc_type": _s(d.get("doc_type")),
                "rechtsgrundlage": _s(spec.get("rechtsgrundlage")),
                "status": _s(d.get("status")),
                "version": d.get("version") if d.get("version") is not None else 1,
                "stand": _s(d.get("updated_at")),
            })
        return out
    except Exception:
        return []


def build_cra_context(db_path: Path | str, projekt_name: str) -> dict[str, Any]:
    """Baut den Vorlagen-Kontext für ein CRA-Projekt.

    Liefert immer ein vollständiges Dict mit den Top-Level-Keys
    ``projekt``, ``bewertungen``, ``risiken``, ``meta`` — fehlende Daten als
    leere Defaults (nie ``None``)."""
    from cra import db as cdb
    from cra.requirements import (
        BEWERTUNG_SKALA,
        CRA_ANFORDERUNGEN,
        KAPITEL,
        PRODUKTKLASSEN,
        berechne_reifegrad,
    )
    from cra.report_export import build_rb_risk_summary

    db_path = Path(db_path)

    proj = cdb.load_projekt(db_path, projekt_name) or {}
    produktklasse = _s(proj.get("produktklasse") or "default") or "default"
    pk_info = PRODUKTKLASSEN.get(produktklasse, PRODUKTKLASSEN["default"])

    projekt = {
        "name": _s(proj.get("name") or projekt_name),
        "unternehmen": _s(proj.get("unternehmen")),
        "produkt": _s(proj.get("produkt")),
        "produktklasse": produktklasse,
        "produktklasse_label": _s(pk_info.get("label")),
        "beschreibung": _s(proj.get("beschreibung")),
        "berater": _s(proj.get("berater")),
        "konformitaet": _s(pk_info.get("konformitaet")),
        "referenz": _s(pk_info.get("referenz")),
    }

    # ── Bewertungen je Anforderung (stabile Anzeige-Reihenfolge) ───────────────
    bew_raw = cdb.load_bewertungen(db_path, projekt_name)
    bewertungen: list[dict[str, Any]] = []
    for req in CRA_ANFORDERUNGEN:
        rid = req["id"]
        d = bew_raw.get(rid, {})
        bval = int(d.get("bewertung", 0) or 0)
        binfo = BEWERTUNG_SKALA.get(bval, BEWERTUNG_SKALA[0])
        bewertungen.append({
            "id": rid,
            "kapitel": _s(req.get("kapitel")),
            "titel": _s(req.get("titel")),
            "ref": _s(req.get("ref")),
            "bewertung": bval,
            "bewertung_label": _s(binfo.get("label")),
            "kommentar": _s(d.get("kommentar")),
            "massnahme": _s(d.get("massnahme")),
            "verantwortlich": _s(d.get("verantwortlich")),
            "zieldatum": _s(d.get("zieldatum")),
            "gewichtung": int(req.get("gewichtung", 1) or 1),
        })

    # ── Reifegrad (wiederverwendete Bericht-Logik) ─────────────────────────────
    reife = berechne_reifegrad({rid: int(d.get("bewertung", 0) or 0)
                                for rid, d in bew_raw.items()})
    kapitel_meta = []
    for kap_id, kap_info in KAPITEL.items():
        kapitel_meta.append({
            "id": kap_id,
            "titel": _s(kap_info.get("titel")),
            "referenz": _s(kap_info.get("referenz")),
            "reifegrad_pct": reife["kapitel_pct"].get(kap_id, 0.0),
        })

    # ── Verknüpfte Risikobewertung (Top-Risiken) ───────────────────────────────
    rb = build_rb_risk_summary(db_path, projekt_name)
    risiken = [{
        "name": _s(t.get("name")),
        "label": _s(t.get("label")),
        "wert": t.get("wert") if t.get("wert") is not None else "",
    } for t in (rb.get("top") or [])]

    # ── Zusatz-Doku (Vulns / Threatmodel) ──────────────────────────────────────
    try:
        vulns = cdb.list_vuln(db_path, projekt_name)
    except Exception:
        vulns = []
    try:
        tm = cdb.load_threatmodel(db_path, projekt_name) or {}
    except Exception:
        tm = {}

    meta = {
        "datum": date.today().isoformat(),
        "reifegrad_pct": reife.get("gesamt_pct", 0.0),
        "ampel": _s(reife.get("ampel")),
        "bewertete_count": reife.get("bewertete_count", 0),
        "gesamt_count": reife.get("gesamt_count", 0),
        "kapitel": kapitel_meta,
        "risiko_verknuepft": bool(rb.get("linked")),
        "risiko_projekt": _s(rb.get("rb_projekt")),
        "framework": _s(rb.get("framework")) or _s(tm.get("framework")),
        "vulns": [{
            "cve_id": _s(v.get("cve_id")),
            "titel": _s(v.get("titel")),
            "schwere": _s(v.get("schwere")),
            "status": _s(v.get("status")),
        } for v in vulns],
        "threatmodel": {
            "framework": _s(tm.get("framework")),
            "scope": _s(tm.get("scope")),
        },
    }

    return {
        "projekt": projekt,
        "bewertungen": bewertungen,
        "risiken": risiken,
        "meta": meta,
        "dokumente": _dokumente(db_path, projekt_name),
    }
