"""Meldepflicht-Brücken: SOC-Incident → echte Melde-Records der Zielmodule.

Der Meldepflicht-Router (#1281) legt die Tracks an; diese Brücken überführen einen
bestätigten Incident in den konkreten Record des jeweiligen Moduls und hinterlegen
die Referenz im Track (``target_ref``).

- DSGVO Art. 33/34  → ``dsgvo_datenpannen`` (#1272)
- CRA Art. 14       → ``cra_vuln`` (#1282)
- NIS2 Art. 23      → Meldeentwurf-Dokument (#1273)  [Folge-Commit]
- AI-Act Art. 73    → Meldeentwurf-Dokument (#1283)  [Folge-Commit]
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from soc import db as sdb

DSGVO_DB = Path("data/db/dsgvo.sqlite")
CRA_DB = Path("data/db/cra.sqlite")
NIS2_DB = Path("data/db/nis2.sqlite")
AIACT_DB = Path("data/db/ai_act.sqlite")


def _set_track_ref(soc_db: Path, incident_id: int, regime: str, target_ref: str,
                   status: str = "in_arbeit") -> None:
    for t in sdb.list_meldetracks(soc_db, incident_id):
        if t["regime"] == regime:
            sdb.update_meldetrack(soc_db, t["id"], status=status, target_ref=target_ref)
            return


def to_dsgvo_datenpanne(soc_db: Path, incident_id: int, projekt_name: str, *,
                        actor: str = "") -> dict[str, Any]:
    """Erzeugt eine DSGVO-Datenpanne (Art. 33(3)-Felder) aus dem Incident."""
    from dsgvo import db as ddb
    inc = sdb.get_incident(soc_db, incident_id)
    if not inc:
        return {"ok": False, "error": "Incident nicht gefunden"}
    festgestellt = (inc.get("awareness_at") or inc.get("created_at") or "")[:10]
    high = inc.get("severity") in ("high", "critical")
    data = {
        "panne_id": f"SOC-{incident_id}",
        "titel": inc.get("titel") or f"SOC-Incident #{incident_id}",
        "beschreibung": inc.get("beschreibung", ""),
        "art": inc.get("klassifikation", "") or "Sicherheitsvorfall (SOC)",
        "festgestellt_am": festgestellt or "1970-01-01",
        "betroffene_anzahl": 0,
        "datenkategorien": "",
        "risikoeinschaetzung": "hoch" if high else "mittel",
        "meldung_aufsicht_pflicht": True,             # Art. 33 — im Zweifel melden
        "meldung_betroffene_pflicht": high,           # Art. 34 — bei hohem Risiko
        "sofortmassnahmen": inc.get("response_actions", ""),
        "ursache": "",
        "lessons_learned": inc.get("lessons_learned", ""),
        "status": "offen",
        "notizen": f"Automatisch aus SOC-Incident #{incident_id} erzeugt (Meldepflicht-Router).",
    }
    try:
        pid = ddb.save_panne(DSGVO_DB, projekt_name, data)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"DSGVO-Datenpanne konnte nicht angelegt werden: {e}"}
    ref = f"dsgvo:{projekt_name}:{pid}"
    _set_track_ref(soc_db, incident_id, "dsgvo", ref)
    sdb.add_timeline_note(soc_db, incident_id, actor=actor or "router",
                          detail=f"DSGVO-Datenpanne angelegt (Projekt '{projekt_name}', ID {pid})")
    return {"ok": True, "panne_id": pid, "projekt": projekt_name, "target_ref": ref}


def to_cra_vuln(soc_db: Path, incident_id: int, projekt_name: str, *,
                cve_id: str = "", actor: str = "") -> dict[str, Any]:
    """Übernimmt den Incident als aktiv ausgenutzte Schwachstelle in ``cra_vuln``."""
    from cra import db as cdb
    inc = sdb.get_incident(soc_db, incident_id)
    if not inc:
        return {"ok": False, "error": "Incident nicht gefunden"}
    sev_map = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
    finding = {
        "cve_id": cve_id or f"SOC-INC-{incident_id}",
        "titel": inc.get("titel") or f"SOC-Incident #{incident_id}",
        "beschreibung": inc.get("beschreibung", ""),
        "schwere": sev_map.get(inc.get("severity", "medium"), "medium"),
        "status": "open",
        "quelle": "soc",
        "exploited": True,
    }
    try:
        res = cdb.upsert_vuln(CRA_DB, projekt_name, finding)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"cra_vuln-Eintrag fehlgeschlagen: {e}"}
    ref = f"cra:{projekt_name}:{finding['cve_id']}"
    _set_track_ref(soc_db, incident_id, "cra", ref)
    sdb.add_timeline_note(soc_db, incident_id, actor=actor or "router",
                          detail=f"CRA-Schwachstelle {finding['cve_id']} (aktiv ausgenutzt) in Projekt '{projekt_name}'")
    return {"ok": True, "cve_id": finding["cve_id"], "action": res.get("action"), "target_ref": ref}


def _meldeentwurf_html(inc: dict[str, Any], titel: str, legal: str, pflichtfelder: list[str]) -> str:
    rows = "".join(f"<li>{p}</li>" for p in pflichtfelder)
    return (
        f"<h1>{titel}</h1>"
        f"<p><strong>Rechtsgrundlage:</strong> {legal}</p>"
        f"<p><strong>Vorfall:</strong> {inc.get('titel', '')}</p>"
        f"<p><strong>Bekannt geworden am (Awareness):</strong> {inc.get('awareness_at') or inc.get('created_at', '')}</p>"
        f"<p><strong>Schwere:</strong> {inc.get('severity', '')}</p>"
        f"<p><strong>Betroffenes Asset:</strong> {inc.get('agent_name', '')}</p>"
        f"<h2>Beschreibung</h2><p>{inc.get('beschreibung', '') or '—'}</p>"
        f"<h2>Bereits getroffene Maßnahmen</h2><p>{inc.get('response_actions', '') or '—'}</p>"
        f"<h2>Pflichtangaben (auszufüllen)</h2><ul>{rows}</ul>"
        f"<p><em>Automatisch aus SOC-Incident #{inc.get('id')} erzeugt (Meldepflicht-Router). Vor Versand prüfen.</em></p>"
    )


def _to_meldeentwurf(soc_db: Path, incident_id: int, *, regime: str, modul: str, module_db: Path,
                     projekt: str, titel: str, legal: str, pflichtfelder: list[str],
                     actor: str = "") -> dict[str, Any]:
    from shared.documents import db as docdb
    inc = sdb.get_incident(soc_db, incident_id)
    if not inc:
        return {"ok": False, "error": "Incident nicht gefunden"}
    if not projekt:
        return {"ok": False, "error": "projekt_name nötig"}
    html = _meldeentwurf_html(inc, titel, legal, pflichtfelder)
    try:
        doc_id = docdb.create_document(
            module_db, modul, projekt=projekt, doc_type="meldung", titel=titel,
            content_html=html, source="import", created_by=actor or "soc-router",
            meta={"soc_incident": incident_id, "regime": regime, "legal": legal})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Meldeentwurf konnte nicht angelegt werden: {e}"}
    ref = f"{modul}_managed_docs:{doc_id}"
    _set_track_ref(soc_db, incident_id, regime, ref)
    sdb.add_timeline_note(soc_db, incident_id, actor=actor or "router",
                          detail=f"{legal}: Meldeentwurf-Dokument in {modul} angelegt (ID {doc_id})")
    return {"ok": True, "doc_id": doc_id, "modul": modul, "projekt": projekt, "target_ref": ref}


def to_nis2_meldung(soc_db: Path, incident_id: int, projekt: str, *, actor: str = "") -> dict[str, Any]:
    """NIS2 Art. 23 Meldeentwurf (Frühwarnung/Meldung/Abschluss)."""
    return _to_meldeentwurf(
        soc_db, incident_id, regime="nis2", modul="nis2", module_db=NIS2_DB, projekt=projekt,
        titel=f"NIS2-Meldung — SOC-Incident #{incident_id}", legal="Art. 23 NIS2",
        pflichtfelder=[
            "Erste Bewertung (Schweregrad, Auswirkung, grenzüberschreitende Wirkung)",
            "Art der Bedrohung / Ursache (soweit bekannt)",
            "Betroffene Dienste und Nutzerzahl",
            "Indikatoren für Kompromittierung (IoCs)",
            "Frühwarnung (24h) · Meldung (72h) · Abschlussbericht (1 Monat)",
        ], actor=actor)


def to_aiact_meldung(soc_db: Path, incident_id: int, projekt: str, *, actor: str = "") -> dict[str, Any]:
    """AI-Act Art. 73 Meldeentwurf für schweren Vorfall (Hochrisiko-KI)."""
    return _to_meldeentwurf(
        soc_db, incident_id, regime="aiact", modul="ai_act", module_db=AIACT_DB, projekt=projekt,
        titel=f"AI-Act schwerer Vorfall — SOC-Incident #{incident_id}", legal="Art. 73 AI-Act",
        pflichtfelder=[
            "Betroffenes Hochrisiko-KI-System (Bezeichnung, Zweck)",
            "Art des schweren Vorfalls und kausaler Zusammenhang",
            "Auswirkungen auf Gesundheit/Sicherheit/Grundrechte",
            "Ergriffene Korrekturmaßnahmen",
            "Frist: unverzüglich, spätestens 15 Tage (2 Tage bei breiter Verletzung/ernstem Risiko)",
        ], actor=actor)
