"""DSGVO-Adapter für die zentrale Word-Vorlagen-Engine (#996, Story 8).

Liefert:
- ``DSGVO_VARIABLES`` — das Variablen-Schema für die Vorlagen-Variablen-Hilfe.
- ``build_dsgvo_context(db_path, projekt_name)`` — einen Jinja-robusten Kontext
  (keine ``None``-Werte; leere Defaults statt ``None``), den
  ``shared.templates.engine.render_docx_from_path`` direkt rendern kann.

Top-Level-Keys: ``projekt``, ``anforderungen``, ``toms``, ``vvt``, ``dpia``,
``avv``, ``datenpannen``, ``meta``.

Für den DSMS-Gesamtbericht (#1113) zusätzlich:
``tom_katalog``, ``betroffenenrechte``, ``transfers``, ``loeschregeln``,
``einwilligungen``, ``dsb``.
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
    # ── DSMS-Gesamtbericht (#1113) ───────────────────────────────────────────
    {"key": "tom_katalog", "typ": "liste",
     "beschreibung": "TOM-Katalog nach Schutzzielen "
                     "(ziel, massnahme_key, titel, status, soll, verantwortlich)",
     "pflicht": False},
    {"key": "betroffenenrechte", "typ": "liste",
     "beschreibung": "Betroffenenanträge & Fristen (Art. 12-22) "
                     "(antrag_id, typ, eingang_datum, frist_datum, status)",
     "pflicht": False},
    {"key": "transfers", "typ": "liste",
     "beschreibung": "Drittlandtransfers & TIA (Art. 44-49) "
                     "(transfer_id, empfaenger, drittland, grundlage, tia_status)",
     "pflicht": False},
    {"key": "loeschregeln", "typ": "liste",
     "beschreibung": "Löschkonzept / Aufbewahrungsfristen (Art. 17) "
                     "(regel_id, datenkategorie, aufbewahrungsfrist, status)",
     "pflicht": False},
    {"key": "einwilligungen", "typ": "liste",
     "beschreibung": "Einwilligungs-Nachweise (Art. 7) "
                     "(einwilligung_id, zweck, zeitpunkt, kanal, status)",
     "pflicht": False},
    {"key": "dsb", "typ": "objekt",
     "beschreibung": "Datenschutzbeauftragter (Art. 37-39): "
                     "vorhanden, typ, name, kontakt_email, bestelldatum",
     "pflicht": False},
    {"key": "meta.anzahl_tom_katalog", "typ": "zahl",
     "beschreibung": "Anzahl TOM-Katalog-Maßnahmen", "pflicht": False},
    {"key": "meta.anzahl_betroffenenrechte", "typ": "zahl",
     "beschreibung": "Anzahl Betroffenenanträge", "pflicht": False},
    {"key": "meta.anzahl_transfers", "typ": "zahl",
     "beschreibung": "Anzahl Drittlandtransfers", "pflicht": False},
    {"key": "meta.anzahl_loeschregeln", "typ": "zahl",
     "beschreibung": "Anzahl Löschregeln", "pflicht": False},
    {"key": "meta.anzahl_einwilligungen", "typ": "zahl",
     "beschreibung": "Anzahl Einwilligungen", "pflicht": False},
    {"key": "meta.dsb_vorhanden", "typ": "wahrheitswert",
     "beschreibung": "Ist ein DSB benannt/erfasst?", "pflicht": False},
    {"key": "meta.anzahl_anforderungen", "typ": "zahl",
     "beschreibung": "Anzahl der Anforderungen im Katalog", "pflicht": False},
    {"key": "meta.anzahl_toms", "typ": "zahl",
     "beschreibung": "Anzahl erfasster TOMs", "pflicht": False},
    {"key": "meta.anzahl_vvt", "typ": "zahl",
     "beschreibung": "Anzahl Verarbeitungstätigkeiten", "pflicht": False},
    {"key": "meta.reifegrad", "typ": "zahl",
     "beschreibung": "Durchschnittlicher Reifegrad (0-5) der bewerteten Anforderungen",
     "pflicht": False},
    {"key": "dokumente", "typ": "liste",
     "beschreibung": "Finalisierte/freigegebene gemanagte Dokumente des Projekts "
                     "(titel, doc_type, rechtsgrundlage, status, version, stand)",
     "pflicht": False},
]


# DB-Modulkennung für die generische Dokument-Persistenz (shared.documents).
_DOC_MODUL = "dsgvo"


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

    # ── DSMS-Gesamtbericht-Bereiche (#1113) ─────────────────────────────────
    # Jeder Bereich wird defensiv geladen; fehlt ein Modul, bleibt die Liste leer.

    # TOM-Katalog nach Schutzzielen (eigene Tabelle, nicht zu verwechseln mit
    # den Art.-32-„toms" oben aus db.list_tom)
    tom_katalog: list[dict[str, Any]] = []
    try:
        from dsgvo import tom_katalog as tomkat
        for m in tomkat.list_massnahmen(db_path, projekt_name):
            tom_katalog.append({
                "ziel": _s(m.get("ziel")),
                "massnahme_key": _s(m.get("massnahme_key")),
                "titel": _s(m.get("titel")),
                "beschreibung": _s(m.get("beschreibung")),
                "status": _i(m.get("status"), 0),
                "soll": _i(m.get("soll"), 5),
                "verantwortlich": _s(m.get("verantwortlich")),
                "wirksamkeit_datum": _s(m.get("wirksamkeit_datum")),
                "wirksamkeit_ergebnis": _s(m.get("wirksamkeit_ergebnis")),
                "vvt_ref": _s(m.get("vvt_ref")),
            })
    except Exception:
        tom_katalog = []

    # Betroffenenrechte (Art. 12-22)
    betroffenenrechte: list[dict[str, Any]] = []
    try:
        from dsgvo import betroffenenrechte_db as brdb
        for a in brdb.list_antraege(db_path, projekt_name):
            betroffenenrechte.append({
                "antrag_id": _s(a.get("antrag_id")),
                "typ": _s(a.get("typ")),
                "eingang_datum": _s(a.get("eingang_datum")),
                "frist_datum": _s(a.get("frist_datum")),
                "verlaengert": bool(a.get("verlaengert")),
                "status": _s(a.get("status")),
                "bearbeiter": _s(a.get("bearbeiter")),
                "ergebnis": _s(a.get("ergebnis")),
            })
    except Exception:
        betroffenenrechte = []

    # Drittlandtransfers (Art. 44-49)
    transfers: list[dict[str, Any]] = []
    try:
        from dsgvo import transfer_db
        for t in transfer_db.list_transfers(db_path, projekt_name):
            transfers.append({
                "transfer_id": _s(t.get("transfer_id")),
                "empfaenger": _s(t.get("empfaenger")),
                "drittland": _s(t.get("drittland")),
                "grundlage": _s(t.get("grundlage")),
                "garantie_detail": _s(t.get("garantie_detail")),
                "tia_status": _s(t.get("tia_status")),
                "vvt_ref": _s(t.get("vvt_ref")),
                "avv_ref": _s(t.get("avv_ref")),
            })
    except Exception:
        transfers = []

    # Löschkonzept / Aufbewahrungsfristen (Art. 17)
    loeschregeln: list[dict[str, Any]] = []
    try:
        from dsgvo import loeschkonzept_db
        for r in loeschkonzept_db.list_regeln(db_path, projekt_name):
            loeschregeln.append({
                "regel_id": _s(r.get("regel_id")),
                "datenkategorie": _s(r.get("datenkategorie")),
                "aufbewahrungsfrist": _s(r.get("aufbewahrungsfrist")),
                "rechtsgrundlage_frist": _s(r.get("rechtsgrundlage_frist")),
                "loeschklasse": _s(r.get("loeschklasse")),
                "loesch_trigger": _s(r.get("loesch_trigger")),
                "verantwortlich": _s(r.get("verantwortlich")),
                "status": _s(r.get("status")),
                "vvt_ref": _s(r.get("vvt_ref")),
            })
    except Exception:
        loeschregeln = []

    # Einwilligungs-Nachweise (Art. 7)
    einwilligungen: list[dict[str, Any]] = []
    try:
        from dsgvo import einwilligung_db
        for e in einwilligung_db.list_einwilligungen(db_path, projekt_name):
            einwilligungen.append({
                "einwilligung_id": _s(e.get("einwilligung_id")),
                "zweck": _s(e.get("zweck")),
                "text_version": _s(e.get("text_version")),
                "zeitpunkt": _s(e.get("zeitpunkt")),
                "kanal": _s(e.get("kanal")),
                "betroffener_quelle": _s(e.get("betroffener_quelle")),
                "widerruf_zeitpunkt": _s(e.get("widerruf_zeitpunkt")),
                "status": _s(e.get("status")),
            })
    except Exception:
        einwilligungen = []

    # Datenschutzbeauftragter (Art. 37-39) — Einzelobjekt
    dsb: dict[str, Any] = {
        "vorhanden": False,
        "typ": "",
        "name": "",
        "bestelldatum": "",
        "kontakt_email": "",
        "kontakt_veroeffentlicht": False,
        "gemeldet_aufsicht": False,
        "aufgaben_nachweis": "",
        "taetigkeitsbericht": "",
    }
    try:
        from dsgvo import dsb_db
        raw_dsb = dsb_db.get_dsb(db_path, projekt_name)
        if raw_dsb:
            dsb = {
                "vorhanden": True,
                "typ": _s(raw_dsb.get("typ")),
                "name": _s(raw_dsb.get("name")),
                "bestelldatum": _s(raw_dsb.get("bestelldatum")),
                "kontakt_email": _s(raw_dsb.get("kontakt_email")),
                "kontakt_veroeffentlicht": bool(raw_dsb.get("kontakt_veroeffentlicht")),
                "gemeldet_aufsicht": bool(raw_dsb.get("gemeldet_aufsicht")),
                "aufgaben_nachweis": _s(raw_dsb.get("aufgaben_nachweis")),
                "taetigkeitsbericht": _s(raw_dsb.get("taetigkeitsbericht")),
            }
    except Exception:
        pass

    # ── Meta ────────────────────────────────────────────────────────────────
    reifegrad = round(sum(bewertungswerte) / len(bewertungswerte), 2) if bewertungswerte else 0
    meta = {
        "anzahl_anforderungen": len(anforderungen),
        "anzahl_toms": len(toms),
        "anzahl_vvt": len(vvt),
        "anzahl_dpia": len(dpia),
        "anzahl_avv": len(avv),
        "anzahl_datenpannen": len(datenpannen),
        "anzahl_tom_katalog": len(tom_katalog),
        "anzahl_betroffenenrechte": len(betroffenenrechte),
        "anzahl_transfers": len(transfers),
        "anzahl_loeschregeln": len(loeschregeln),
        "anzahl_einwilligungen": len(einwilligungen),
        "dsb_vorhanden": bool(dsb.get("vorhanden")),
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
        "tom_katalog": tom_katalog,
        "betroffenenrechte": betroffenenrechte,
        "transfers": transfers,
        "loeschregeln": loeschregeln,
        "einwilligungen": einwilligungen,
        "dsb": dsb,
        "meta": meta,
        "dokumente": _dokumente(db_path, projekt_name),
    }
