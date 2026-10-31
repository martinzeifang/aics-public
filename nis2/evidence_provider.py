"""NIS2-Evidenz-Provider (Sprint #40, #1489).

Mappt NIS2-Anforderungen auf den operativen Zustand des NIS2-Moduls, damit die KI-Bewertung
anrechnet, was *durch die Software* gepflegt ist: Asset-Inventar (N1), Risiko-Register (N2),
Incident-Response-Plan (N3), Supply-Chain-Register (N4) und Business-Continuity-Plan (N5).
Wird über `shared/evidence_context` aufgerufen.

Vertrag: ``relevant_for(projekt, requirement) -> list[EvidenceItem]``. Best-effort — jeder
DB-Zugriff ist gekapselt; Fehler liefern keine Evidenz, brechen aber nie ab.

Anforderungs→Register-Mapping (Katalog-`kapitel`/`id`):
- N1 Asset-Inventar    → NIS2-01 (Risikoanalyse), NIS2-09 (Asset-Management)
- N2 Risiko-Register   → NIS2-01/NIS2-02 (Risikoanalyse-Konzepte), NIS2-06 (Wirksamkeit)
- N3 Incident-Response → NIS2-03 (Bewältigung Sicherheitsvorfälle), Kapitel NIS3 (Meldepflichten)
- N4 Supply-Chain      → Kapitel NIS4 (Lieferkettensicherheit)
- N5 BCP               → NIS2-04 (Business Continuity)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.evidence_context import EvidenceItem, _clip

_DB = Path("data/db/nis2.sqlite")

# Offene-Risiko-Status (alles, was nicht abgeschlossen ist).
_RISK_OPEN = {"offen", "in-behandlung"}

# Anforderungen, für die die jeweiligen Register relevant sind.
_ASSET_REQ = {"NIS2-01", "NIS2-09"}
_RISK_REQ = {"NIS2-01", "NIS2-02", "NIS2-06"}
_INCIDENT_REQ = {"NIS2-03"}      # zusätzlich gesamtes Kapitel NIS3
_BCP_REQ = {"NIS2-04"}


def _asset_items(projekt_name: str) -> list[EvidenceItem]:
    try:
        from nis2.db import list_assets
        assets = list_assets(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not assets:
        return []
    kritisch = [a for a in assets if str(a.get("kritikalitaet") or "").lower() in ("hoch", "kritisch")]
    return [EvidenceItem(
        "NIS2 Asset-Inventar", "register", "nis2_asset_inventory:summary",
        _clip(f"{len(assets)} Assets im Inventar erfasst, davon {len(kritisch)} hoch/kritisch — "
              f"Anlagen- und Asset-Management etabliert (Art. 21)."),
        relevance=1.6)]


def _risk_items(projekt_name: str) -> list[EvidenceItem]:
    try:
        from nis2.db import list_risiken
        risiken = list_risiken(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not risiken:
        return []
    offen = [r for r in risiken if str(r.get("status") or "offen").lower() in _RISK_OPEN]
    importiert = sorted({str(r.get("source_modul")).strip() for r in risiken
                         if str(r.get("source_modul") or "").strip()})
    src_txt = (f"; {len(importiert)} Quelle(n) importiert ({', '.join(importiert)})"
               if importiert else "")
    return [EvidenceItem(
        "NIS2 Risiko-Register", "register", "nis2_risiko_register:summary",
        _clip(f"{len(risiken)} Risiken erfasst, davon {len(offen)} offen/in Behandlung{src_txt} — "
              f"Risikoanalyse/-management dokumentiert (Art. 21)."),
        relevance=1.6)]


def _incident_items(projekt_name: str) -> list[EvidenceItem]:
    try:
        from nis2.db import load_incident_response
        ir = load_incident_response(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not ir:
        return []
    csirt = (ir.get("csirt_kontakt") or "").strip()
    playbook = bool((ir.get("playbook_url") or "").strip())
    early = ir.get("early_warning_sla") or "—"
    notif = ir.get("notification_sla") or "—"
    final = ir.get("final_report_sla") or "—"
    return [EvidenceItem(
        "NIS2 Incident-Response", "register", "nis2_incident_response:summary",
        _clip(f"Incident-Response-Plan vorhanden: CSIRT-Kontakt {csirt or '(offen)'}, "
              f"SLAs Frühwarnung {early} / Meldung {notif} / Abschluss {final}, "
              f"Playbook {'hinterlegt' if playbook else 'fehlt'} (Art. 23)."),
        relevance=1.7)]


def _supply_items(projekt_name: str) -> list[EvidenceItem]:
    try:
        from nis2.db import list_vendors
        vendors = list_vendors(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not vendors:
        return []
    bewertet = [v for v in vendors if (v.get("assessment_datum") or "").strip()
                or int(v.get("assessment_score") or 0) > 0]
    kritisch = [v for v in vendors if str(v.get("kritikalitaet") or "").lower() in ("hoch", "kritisch")]
    return [EvidenceItem(
        "NIS2 Supply-Chain", "register", "nis2_supply_chain:summary",
        _clip(f"{len(vendors)} Lieferanten erfasst ({len(kritisch)} hoch/kritisch), "
              f"{len(bewertet)} mit Sicherheitsbewertung — Lieferkettensicherheit "
              f"dokumentiert (Art. 21 Abs. 2 lit. d)."),
        relevance=1.6)]


def _bcp_items(projekt_name: str) -> list[EvidenceItem]:
    try:
        from nis2.db import load_bcp
        bcp = load_bcp(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not bcp:
        return []
    rpo = bcp.get("rpo_minuten")
    rto = bcp.get("rto_minuten")
    backup = (bcp.get("backup_strategie") or "").strip()
    test = (bcp.get("test_datum") or "").strip()
    return [EvidenceItem(
        "NIS2 Business-Continuity", "register", "nis2_bcp:summary",
        _clip(f"BCP/BCM vorhanden: RPO {rpo} min / RTO {rto} min, "
              f"Backup-Strategie {backup or '(offen)'}, "
              f"letzte BCP-Übung {test or '(keine erfasst)'} (Art. 21 Abs. 2 lit. c)."),
        relevance=1.6)]


def relevant_for(projekt: dict[str, Any], requirement: dict[str, Any]) -> list[EvidenceItem]:
    name = (projekt.get("name") or "").strip()
    if not name:
        return []
    rid = str(requirement.get("id") or "").upper()
    kap = str(requirement.get("kapitel") or "").upper()
    items: list[EvidenceItem] = []
    if rid in _ASSET_REQ:
        items += _asset_items(name)
    if rid in _RISK_REQ:
        items += _risk_items(name)
    if rid in _INCIDENT_REQ or kap == "NIS3":
        items += _incident_items(name)
    if kap == "NIS4":
        items += _supply_items(name)
    if rid in _BCP_REQ:
        items += _bcp_items(name)
    return items
