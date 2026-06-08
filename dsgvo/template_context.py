"""DSGVO-Adapter für die zentrale Word-Vorlagen-Engine (#996, Story 8).

Liefert:
- ``DSGVO_VARIABLES`` — das Variablen-Schema für die Vorlagen-Variablen-Hilfe.
- ``build_dsgvo_context(db_path, projekt_name)`` — einen Jinja-robusten Kontext
  (keine ``None``-Werte; leere Defaults statt ``None``), den
  ``shared.templates.engine.render_docx_from_path`` direkt rendern kann.

Top-Level-Keys: ``projekt``, ``anforderungen``, ``toms``, ``vvt``, ``dpia``,
``avv``, ``datenpannen``, ``meta``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# ── Variablen-Schema ────────────────────────────────────────────────────────
# Ein Eintrag: {"key", "typ", "beschreibung", "pflicht"}
DSGVO_VARIABLES: list[dict[str, Any]] = [
    {"key": "projekt.name", "typ": "text",
     "beschreibung": "Name des DSGVO-Projekts", "pflicht": True},
    {"key": "projekt.unternehmen", "typ": "text",
     "beschreibung": "Verantwortliches Unternehmen / Organisation", "pflicht": True},
    {"key": "projekt.organisationstyp", "typ": "text",
     "beschreibung": "verantwortlicher | auftragsverarbeiter | beides", "pflicht": False},
    {"key": "projekt.beschreibung", "typ": "text",
     "beschreibung": "Kurzbeschreibung des Projekts", "pflicht": False},
    {"key": "projekt.berater", "typ": "text",
     "beschreibung": "Datenschutzberater / DSB", "pflicht": False},
    {"key": "anforderungen", "typ": "liste",
     "beschreibung": "Bewertete DSGVO-Anforderungen "
                     "(id, kapitel, ref, titel, bewertung, kommentar, massnahme)",
     "pflicht": False},
    {"key": "toms", "typ": "liste",
     "beschreibung": "Technische und organisatorische Maßnahmen (Art. 32)",
     "pflicht": False},
    {"key": "vvt", "typ": "liste",
     "beschreibung": "Verzeichnis der Verarbeitungstätigkeiten (Art. 30)",
     "pflicht": False},
    {"key": "dpia", "typ": "liste",
     "beschreibung": "Datenschutz-Folgenabschätzungen (Art. 35)", "pflicht": False},
    {"key": "avv", "typ": "liste",
     "beschreibung": "Auftragsverarbeitungs-Verträge (Art. 28)", "pflicht": False},
    {"key": "datenpannen", "typ": "liste",
     "beschreibung": "Datenpannen-Register (Art. 33-34)", "pflicht": False},
    {"key": "meta.anzahl_anforderungen", "typ": "zahl",
     "beschreibung": "Anzahl der Anforderungen im Katalog", "pflicht": False},
    {"key": "meta.anzahl_toms", "typ": "zahl",
     "beschreibung": "Anzahl erfasster TOMs", "pflicht": False},
    {"key": "meta.anzahl_vvt", "typ": "zahl",
     "beschreibung": "Anzahl Verarbeitungstätigkeiten", "pflicht": False},
    {"key": "meta.reifegrad", "typ": "zahl",
     "beschreibung": "Durchschnittlicher Reifegrad (0-5) der bewerteten Anforderungen",
     "pflicht": False},
]


# ── Helfer ──────────────────────────────────────────────────────────────────

def _s(value: Any) -> str:
    """Niemals None: gibt einen sauberen String zurück."""
    if value is None:
        return ""
    return str(value)


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ── Kontext-Builder ─────────────────────────────────────────────────────────

def build_dsgvo_context(db_path: Path | str, projekt_name: str) -> dict[str, Any]:
    """Baut einen Jinja-robusten Render-Kontext für ein DSGVO-Projekt.

    Es werden niemals ``None``-Werte zurückgegeben; fehlende Daten werden durch
    leere Strings bzw. leere Listen ersetzt. Liefert immer ein vollständiges
    Kontext-Gerüst, auch wenn das Projekt nicht existiert.
    """
    db_path = Path(db_path)
    projekt_name = _s(projekt_name)

    from dsgvo import db as ddb

    ddb.ensure_db(db_path)

    # ── Projekt ─────────────────────────────────────────────────────────────
    raw = ddb.load_projekt(db_path, projekt_name) or {}
    projekt = {
        "name": _s(raw.get("name")) or projekt_name,
        "unternehmen": _s(raw.get("unternehmen")),
        "organisationstyp": _s(raw.get("organisationstyp")) or "verantwortlicher",
        "beschreibung": _s(raw.get("beschreibung")),
        "berater": _s(raw.get("berater")),
    }

    # ── Anforderungen + Bewertungen ─────────────────────────────────────────
    anforderungen: list[dict[str, Any]] = []
    bewertungswerte: list[int] = []
    try:
        from dsgvo.requirements import load_merged_anforderungen
        katalog = load_merged_anforderungen(db_path)
    except Exception:
        try:
            from dsgvo.requirements import DSGVO_ANFORDERUNGEN
            katalog = list(DSGVO_ANFORDERUNGEN)
        except Exception:
            katalog = []

    bewertungen = ddb.load_bewertungen(db_path, projekt_name)
    for req in katalog:
        rid = _s(req.get("id"))
        bew = bewertungen.get(rid, {})
        wert = _i(bew.get("bewertung"), 0)
        if rid in bewertungen:
            bewertungswerte.append(wert)
        anforderungen.append({
            "id": rid,
            "kapitel": _s(req.get("kapitel")),
            "ref": _s(req.get("ref")),
            "titel": _s(req.get("titel")),
            "beschreibung": _s(req.get("beschreibung")),
            "bewertung": wert,
            "kommentar": _s(bew.get("kommentar")),
            "massnahme": _s(bew.get("massnahme")),
            "verantwortlich": _s(bew.get("verantwortlich")),
            "zieldatum": _s(bew.get("zieldatum")),
        })

    # ── TOMs (Art. 32) ──────────────────────────────────────────────────────
    toms = [{
        "kategorie": _s(t.get("kategorie")),
        "massnahme": _s(t.get("massnahme")),
        "beschreibung": _s(t.get("beschreibung")),
        "umsetzungsstatus": _s(t.get("umsetzungsstatus")),
        "verantwortlich": _s(t.get("verantwortlich")),
        "review_datum": _s(t.get("review_datum")),
        "notizen": _s(t.get("notizen")),
    } for t in ddb.list_tom(db_path, projekt_name)]

    # ── VVT (Art. 30) ───────────────────────────────────────────────────────
    vvt = [{
        "vvt_id": _s(v.get("vvt_id")),
        "name": _s(v.get("name")),
        "zweck": _s(v.get("zweck")),
        "rechtsgrundlage": _s(v.get("rechtsgrundlage")),
        "betroffene_kategorien": _s(v.get("betroffene_kategorien")),
        "datenkategorien": _s(v.get("datenkategorien")),
        "empfaenger": _s(v.get("empfaenger")),
        "drittland": _s(v.get("drittland")),
        "loeschfrist": _s(v.get("loeschfrist")),
        "tom_referenz": _s(v.get("tom_referenz")),
        "verantwortlich": _s(v.get("verantwortlich")),
        "notizen": _s(v.get("notizen")),
    } for v in ddb.list_vvt(db_path, projekt_name)]

    # ── DPIA (Art. 35) ──────────────────────────────────────────────────────
    dpia = [{
        "dpia_id": _s(d.get("dpia_id")),
        "titel": _s(d.get("titel")),
        "bezug_vvt": _s(d.get("bezug_vvt")),
        "notwendigkeit_grund": _s(d.get("notwendigkeit_grund")),
        "beschreibung_verarbeitung": _s(d.get("beschreibung_verarbeitung")),
        "risiken": _s(d.get("risiken")),
        "massnahmen": _s(d.get("massnahmen")),
        "restrisiko": _s(d.get("restrisiko")),
        "status": _s(d.get("status")),
    } for d in ddb.list_dpia(db_path, projekt_name)]

    # ── AVV (Art. 28) ───────────────────────────────────────────────────────
    avv = [{
        "auftragsverarbeiter": _s(a.get("auftragsverarbeiter")),
        "leistung": _s(a.get("leistung")),
        "avv_vorhanden": bool(a.get("avv_vorhanden")),
        "avv_datum": _s(a.get("avv_datum")),
        "avv_version": _s(a.get("avv_version")),
        "drittland": bool(a.get("drittland")),
        "drittland_garantie": _s(a.get("drittland_garantie")),
        "status": _s(a.get("status")),
    } for a in ddb.list_avv(db_path, projekt_name)]

    # ── Datenpannen (Art. 33-34) ────────────────────────────────────────────
    datenpannen = [{
        "panne_id": _s(p.get("panne_id")),
        "titel": _s(p.get("titel")),
        "art": _s(p.get("art")),
        "festgestellt_am": _s(p.get("festgestellt_am")),
        "betroffene_anzahl": _i(p.get("betroffene_anzahl"), 0),
        "risikoeinschaetzung": _s(p.get("risikoeinschaetzung")),
        "status": _s(p.get("status")),
    } for p in ddb.list_pannen(db_path, projekt_name)]

    # ── Meta ────────────────────────────────────────────────────────────────
    reifegrad = round(sum(bewertungswerte) / len(bewertungswerte), 2) if bewertungswerte else 0
    meta = {
        "anzahl_anforderungen": len(anforderungen),
        "anzahl_toms": len(toms),
        "anzahl_vvt": len(vvt),
        "anzahl_dpia": len(dpia),
        "anzahl_avv": len(avv),
        "anzahl_datenpannen": len(datenpannen),
        "reifegrad": reifegrad,
    }

    return {
        "projekt": projekt,
        "anforderungen": anforderungen,
        "toms": toms,
        "vvt": vvt,
        "dpia": dpia,
        "avv": avv,
        "datenpannen": datenpannen,
        "meta": meta,
    }
