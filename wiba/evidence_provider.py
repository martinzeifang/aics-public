"""WiBA-Evidenz-Provider (Sprint #40, #1493).

Mappt WiBA-Prüffragen auf den operativen Zustand der Suite, damit die KI-Bewertung
anrechnet, was *durch die Software* bzw. benachbarte Module erfüllt ist:
- DSGVO-TOM-Maßnahmen der Firma (Cross-Link, vgl. W6 ``/tom-evidence``) als Nachweis,
- das verknüpfte Risikobewertungs-Projekt der „Nein"-Befunde (W7, ``meta.linked_risk_projekt``).

Generische Firmen-Uploads liefert bereits der Aggregator (`shared.evidence_context.
firm_upload_items`) — sie werden hier NICHT dupliziert. Der bestehende Copy/Paste-Prompt
(``wiba/prompts.build_prompt`` mit ``evidence_texts``) bleibt unverändert.

Vertrag: ``relevant_for(projekt, requirement) -> list[EvidenceItem]``. Best-effort —
jeder DB-Zugriff ist gekapselt; Fehler liefern keine Evidenz, brechen aber nie ab.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.evidence_context import EvidenceItem, _clip

_DSGVO_DB = Path("data/db/dsgvo.sqlite")
_RB_DB = Path("data/db/risikobewertung.sqlite")


def _tom_items(firma: str) -> list[EvidenceItem]:
    """DSGVO-TOM-Maßnahmen der Firma als Nachweis (W6-Cross-Link).

    Spiegelt die Logik von ``server.api.wiba.tom_evidence``: DSGVO-Projekte der Firma
    über ``unternehmen`` finden und umgesetzte (Status > 0) TOM-Maßnahmen sammeln.
    """
    if not firma:
        return []
    try:
        from shared import db as _sdb
        from dsgvo import tom_katalog as tk
        con = _sdb.connect(str(_DSGVO_DB))
        try:
            rows = con.execute(
                "SELECT name FROM dsgvo_projekte WHERE unternehmen=?", (firma,)).fetchall()
        finally:
            con.close()
    except Exception:  # noqa: BLE001
        return []

    massnahmen: list[dict[str, Any]] = []
    for row in rows or []:
        dp = row[0] if not isinstance(row, dict) else row.get("name")
        if not dp:
            continue
        try:
            for m in tk.list_massnahmen(_DSGVO_DB, dp) or []:
                if int(m.get("status") or 0) > 0:
                    massnahmen.append({"dsgvo_projekt": dp, **m})
        except Exception:  # noqa: BLE001
            continue

    if not massnahmen:
        return []

    items: list[EvidenceItem] = [EvidenceItem(
        "DSGVO-TOM (Cross-Link)", "register", "dsgvo_tom:summary",
        _clip(f"{len(massnahmen)} umgesetzte technisch-organisatorische Maßnahmen (TOM) "
              f"aus dem DSGVO-Modul der Firma — anrechenbar als Nachweis der "
              f"Basis-Absicherung."),
        relevance=1.5)]
    for m in massnahmen[:3]:
        wirk = m.get("wirksamkeit_ergebnis") or ""
        items.append(EvidenceItem(
            "DSGVO-TOM-Maßnahme", "register",
            f"dsgvo_tom:{m.get('dsgvo_projekt')}:{m.get('id') or m.get('titel')}",
            _clip(f"{m.get('titel') or m.get('ziel') or 'Maßnahme'} "
                  f"(Ziel {m.get('ziel') or '—'}, Status {m.get('status')}"
                  + (f", Wirksamkeit: {wirk}" if wirk else "") + ")"),
            relevance=1.2))
    return items


def _linked_risk_items(projekt: dict[str, Any]) -> list[EvidenceItem]:
    """Verknüpftes Risikobewertungs-Projekt der „Nein"-Befunde (W7)."""
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
    offen = [r for r in risiken if not r.get("is_resolved")]
    return [EvidenceItem(
        "Verknüpfte Risikobewertung (WiBA-Befunde)", "risk", f"rb:{rb_name}",
        _clip(f"Verknüpftes Risikobewertungs-Projekt '{rb_name}' mit {len(risiken)} "
              f"Risiken aus offenen WiBA-Befunden ({len(offen)} offen) — "
              f"Befunde werden im Risikomanagement nachverfolgt."),
        relevance=1.4)]


def relevant_for(projekt: dict[str, Any], requirement: dict[str, Any]) -> list[EvidenceItem]:
    """App-Evidenz für eine WiBA-Prüffrage (best-effort, wirft nie)."""
    if not isinstance(projekt, dict):
        return []
    firma = (projekt.get("unternehmen") or projekt.get("organisation")
             or projekt.get("firma") or "").strip()
    items: list[EvidenceItem] = []
    items += _tom_items(firma)
    items += _linked_risk_items(projekt)
    return items
