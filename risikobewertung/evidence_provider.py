"""Risikobewertungs-Evidenz-Provider (Sprint #40, #1494).

Anders als die übrigen Module bewertet die Risikobewertung **Risiken** (keine
Katalog-Anforderungen) mit eigenen Prompt-Buildern. Dieser Provider liefert daher
nur die wenigen RB-spezifischen, gezielten Nachweise — den Hauptnutzen (Firmen-
Uploads + Risiko-Cockpit) steuert der generische Aggregator in
``shared/evidence_context`` bei.

Vertrag: ``relevant_for(projekt, requirement) -> list[EvidenceItem]``, wobei
``requirement`` hier ein **Risiko-Dict** ist (kein Katalogeintrag). Best-effort —
jeder DB-Zugriff ist gekapselt; Fehler liefern keine Evidenz, brechen aber nie ab.

RB-spezifisch:
- verknüpftes CRA-Projekt (``projekt['meta']['linked_cra_projekt']``) als
  Kurzübersicht (Schwachstellen-Sync etabliert),
- verknüpftes AI-Act-Projekt (``meta['linked_aiact_projekt']``), falls vorhanden.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.evidence_context import EvidenceItem, _clip

_CRA_DB = Path("data/db/cra.sqlite")
_AIACT_DB = Path("data/db/ai_act.sqlite")

_VULN_CLOSED = {"fixed", "disclosed", "wontfix"}


def _meta(projekt: dict[str, Any]) -> dict[str, Any]:
    meta = projekt.get("meta") if isinstance(projekt.get("meta"), dict) else {}
    return meta or {}


def _linked_cra_items(projekt: dict[str, Any]) -> list[EvidenceItem]:
    cra_name = (_meta(projekt).get("linked_cra_projekt") or "").strip()
    if not cra_name:
        return []
    items: list[EvidenceItem] = []
    try:
        from cra.db import list_vuln
        vulns = list_vuln(_CRA_DB, cra_name)
    except Exception:  # noqa: BLE001
        vulns = []
    if vulns:
        open_v = [v for v in vulns if str(v.get("status") or "open") not in _VULN_CLOSED]
        items.append(EvidenceItem(
            "Verknüpftes CRA-Projekt", "register", f"cra:{cra_name}",
            _clip(f"Verknüpftes CRA-Projekt '{cra_name}': {len(vulns)} Schwachstellen "
                  f"erfasst ({len(open_v)} offen) — Schwachstellen-Monitoring etabliert."),
            relevance=1.4))
    else:
        items.append(EvidenceItem(
            "Verknüpftes CRA-Projekt", "register", f"cra:{cra_name}",
            _clip(f"Verknüpftes CRA-Projekt '{cra_name}' — CRA-Compliance-Prozess etabliert."),
            relevance=1.0))
    return items


def _linked_aiact_items(projekt: dict[str, Any]) -> list[EvidenceItem]:
    aiact_name = (_meta(projekt).get("linked_aiact_projekt") or "").strip()
    if not aiact_name:
        return []
    return [EvidenceItem(
        "Verknüpftes AI-Act-Projekt", "register", f"aiact:{aiact_name}",
        _clip(f"Verknüpftes EU-AI-Act-Projekt '{aiact_name}' — KI-Risikomanagement "
              f"(Art. 9) verknüpft."),
        relevance=1.0)]


def relevant_for(projekt: dict[str, Any], requirement: dict[str, Any]) -> list[EvidenceItem]:
    """RB-spezifische Nachweise zu einem Risiko (``requirement`` ist ein Risiko-Dict)."""
    items: list[EvidenceItem] = []
    try:
        items += _linked_cra_items(projekt)
        items += _linked_aiact_items(projekt)
    except Exception:  # noqa: BLE001
        return []
    return items
