"""CRA-Evidenz-Provider (Sprint #40, #1488).

Mappt CRA-Anforderungen auf den operativen Zustand des CRA-Moduls, damit die KI-Bewertung
anrechnet, was *durch die Software* erfüllt ist: Schwachstellen-Sync (`cra_vuln`),
SBOM (`cra_sbom`), Threat-Model (`cra_threatmodel`) und das verknüpfte Risikobewertungs-
Projekt. Wird über `shared/evidence_context` aufgerufen.

Vertrag: ``relevant_for(projekt, requirement) -> list[EvidenceItem]``. Best-effort — jeder
DB-Zugriff ist gekapselt; Fehler liefern keine Evidenz, brechen aber nie ab.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.evidence_context import EvidenceItem, _clip

_DB = Path("data/db/cra.sqlite")
_RB_DB = Path("data/db/risikobewertung.sqlite")

# Offene-Vuln-Status (alles, was nicht abgeschlossen ist).
_VULN_CLOSED = {"fixed", "disclosed", "wontfix"}

# Anforderungen, für die Schwachstellen/SBOM/Threat/Risiko relevant sind.
_VULN_REQ = {"ART14-01", "ART14-02", "IMPL-03"}
_SBOM_REQ = {"ART13-01", "ART13-02", "ART13-03", "IMPL-03"}
_THREAT_REQ = {"ART13-01", "AI1-01", "IMPL-01"}
# vgl. cra.requirements.RISK_ASSESSMENT_REQUIREMENT_IDS
_RISK_REQ = {"ART13-01", "AI1-01", "ART13-02", "IMPL-02", "IMPL-05"}


def _vuln_items(projekt_name: str) -> list[EvidenceItem]:
    try:
        from cra.db import list_vuln
        vulns = list_vuln(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    open_v = [v for v in vulns if str(v.get("status") or "open") not in _VULN_CLOSED]
    if not open_v:
        # Auch das ist ein Nachweis: gepflegter Sync ohne offene Funde.
        if vulns:
            return [EvidenceItem(
                "CRA Schwachstellen-Sync", "vuln", "cra_vuln:summary",
                f"{len(vulns)} Schwachstellen erfasst, davon 0 offen (alle behoben/disclosed).",
                relevance=1.5)]
        return []
    by_sev: dict[str, int] = {}
    for v in open_v:
        by_sev[str(v.get("schwere") or "unknown")] = by_sev.get(str(v.get("schwere") or "unknown"), 0) + 1
    sev_txt = ", ".join(f"{k}: {n}" for k, n in by_sev.items())
    items = [EvidenceItem(
        "CRA Schwachstellen-Sync", "vuln", "cra_vuln:summary",
        _clip(f"{len(open_v)} offene Schwachstellen ({sev_txt}); kontinuierliches "
              f"Drittkomponenten-Monitoring aktiv (Dependabot/Advisories)."),
        relevance=1.8)]
    for v in open_v[:3]:
        items.append(EvidenceItem(
            "CRA Schwachstelle", "vuln", f"cra_vuln:{v.get('cve_id') or v.get('id')}",
            _clip(f"{v.get('cve_id') or ''} {v.get('titel') or ''} "
                  f"(Schwere {v.get('schwere') or '—'}, CVSS {v.get('cvss_score') or '—'}, "
                  f"Status {v.get('status') or 'open'})"),
            relevance=1.3))
    return items


def _sbom_items(projekt_name: str) -> list[EvidenceItem]:
    try:
        from cra.db import list_sbom
        sboms = list_sbom(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not sboms:
        return []
    s = sboms[0]
    komp = s.get("komponenten_count") or s.get("komponenten") or len(s.get("lizenzen") or [])
    return [EvidenceItem(
        "CRA SBOM", "sbom", "cra_sbom:latest",
        _clip(f"SBOM vorhanden (Format {s.get('sbom_format') or '—'}, "
              f"Release {s.get('release_version') or '—'}, {komp} Komponenten, "
              f"Stand {s.get('sbom_datum') or '—'})."),
        relevance=1.6)]


def _threat_items(projekt_name: str) -> list[EvidenceItem]:
    try:
        from cra.db import load_threatmodel
        tm = load_threatmodel(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not tm:
        return []
    import json as _json

    def _count(key: str) -> int:
        raw = tm.get(key) or tm.get(key + "_json")
        if isinstance(raw, str):
            try:
                raw = _json.loads(raw or "[]")
            except Exception:  # noqa: BLE001
                raw = []
        return len(raw) if isinstance(raw, list) else 0

    threats = _count("threats")
    mitig = _count("mitigations")
    if not threats and not mitig:
        return []
    return [EvidenceItem(
        "CRA Threat-Model", "register", "cra_threatmodel",
        _clip(f"Threat-Model (Framework {tm.get('framework') or '—'}) mit {threats} "
              f"Bedrohungen und {mitig} Gegenmaßnahmen dokumentiert."),
        relevance=1.4)]


def _linked_risk_items(projekt: dict[str, Any]) -> list[EvidenceItem]:
    meta = projekt.get("meta") if isinstance(projekt.get("meta"), dict) else {}
    rb_name = (meta.get("linked_risk_projekt") or "").strip()
    if not rb_name:
        return []
    try:
        from risikobewertung.db import load_risiken
        risiken = load_risiken(_RB_DB, rb_name)
    except Exception:  # noqa: BLE001
        return []
    if not risiken:
        return []
    bewertet = [r for r in risiken if r.get("risikowert") is not None]
    return [EvidenceItem(
        "Verknüpfte Risikobewertung", "risk", f"rb:{rb_name}",
        _clip(f"Verknüpftes Risikobewertungs-Projekt '{rb_name}' mit {len(risiken)} "
              f"Risiken ({len(bewertet)} bewertet) — Risikomanagement etabliert."),
        relevance=1.5)]


def relevant_for(projekt: dict[str, Any], requirement: dict[str, Any]) -> list[EvidenceItem]:
    name = (projekt.get("name") or "").strip()
    if not name:
        return []
    rid = str(requirement.get("id") or "").upper()
    kap = str(requirement.get("kapitel") or "").upper()
    items: list[EvidenceItem] = []
    if rid in _VULN_REQ or kap == "ART14":
        items += _vuln_items(name)
    if rid in _SBOM_REQ or rid == "IMPL-03":
        items += _sbom_items(name)
    if rid in _THREAT_REQ:
        items += _threat_items(name)
    if rid in _RISK_REQ:
        items += _linked_risk_items(projekt)
    return items
