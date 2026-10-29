"""Evidenz-Kontext für die KI-Bewertung von Anforderungen (Sprint #40, #1483/#1484).

Sammelt für eine Anforderung die **App-eigenen Nachweise** (operativer Zustand der Suite)
und rendert sie als Prompt-Block, damit die KI-Bewertung anrechnen kann, was bereits *durch
die Software* erfüllt ist (z. B. CRA-Schwachstellen-Sync, SBOM, hochgeladene Nachweise,
verknüpfte Risiken). Bisher sah der Bewertungs-Prompt nur Katalogfelder + den manuell
gespeicherten Stand.

Aufbau:
- ``EvidenceItem``         — ein Nachweis (Quelle, Art, Referenz, Text, Relevanz, sensibel?).
- ``ModuleEvidenceProvider`` (Protokoll) — je Modul ein ``evidence_provider``-Modul mit
  ``relevant_for(projekt, requirement) -> list[EvidenceItem]`` (Anforderung→Register-Mapping).
- ``build_context(...)``   — aggregiert Provider-Items + generische Quellen (Firmen-Uploads,
  genehmigte Mappings, Risiko-Cockpit), redigiert für Cloud, budgetiert, rendert.
- ``evidence_block_for(...)`` — Endpoint-Einstieg: respektiert Cloud-/Egress-/Config-Gates
  (#1486) und liefert den fertigen Block + Quellenliste.

Best-effort: jeder DB-Zugriff ist gekapselt; ein Fehler liefert KEINE Evidenz, bricht die
Bewertung aber NIE ab. Ohne Evidenz bleibt der Prompt byte-identisch zum bisherigen Verhalten.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Datenmodell ─────────────────────────────────────────────────────────────


@dataclass
class EvidenceItem:
    """Ein einzelner Nachweis aus dem operativen Zustand der Anwendung."""

    quelle: str          # menschenlesbares Label, z. B. "CRA Schwachstellen-Sync"
    kind: str            # Kategorie: vuln|sbom|risk|document|register|upload|mapping|…
    ref: str             # stabile Referenz, z. B. "cra_vuln:CVE-2024-1234"
    text: str            # der Nachweis-Inhalt (Kurzfassung)
    relevance: float = 1.0   # höher = wichtiger (Ranking bei Budget-Knappheit)
    sensitive: bool = False  # enthält personenbezogene/sensible Daten → Cloud-Redaktion

    def render(self) -> str:
        return f"- **{self.quelle}** ({self.ref}): {self.text}"


# ── Provider-Registry (#1484) ───────────────────────────────────────────────
# Modul-Name → Import-Pfad eines Moduls mit ``relevant_for(projekt, requirement)``.
# Guarded import: fehlt der Provider, fällt der Aggregator auf generische Quellen zurück.
_PROVIDER_MODULES: dict[str, str] = {
    "cra": "cra.evidence_provider",
    "nis2": "nis2.evidence_provider",
    "ai_act": "ai_act.evidence_provider",
    "aiact": "ai_act.evidence_provider",
    "dsgvo": "dsgvo.evidence_provider",
    "wiba": "wiba.evidence_provider",
    "risikobewertung": "risikobewertung.evidence_provider",
}


def get_evidence_provider(modul: str):
    """Liefert das Provider-Modul für ``modul`` oder ``None`` (guarded import)."""
    path = _PROVIDER_MODULES.get((modul or "").lower())
    if not path:
        return None
    try:
        return importlib.import_module(path)
    except Exception:  # noqa: BLE001 — Provider optional
        return None


# ── Firmen-/Projekt-Auflösung ───────────────────────────────────────────────

_EVIDENCE_DB = Path("data/db/evidence.sqlite")
_FIRMEN_DB = Path("data/db/firmen.sqlite")


def resolve_firmen_id(projekt: dict[str, Any]) -> int | None:
    """firmen_id aus dem Projekt ableiten (direkt oder per Namens-Match, #1071)."""
    fid = projekt.get("firmen_id")
    if fid:
        try:
            return int(fid)
        except (TypeError, ValueError):
            pass
    name = (projekt.get("unternehmen") or projekt.get("organisation")
            or projekt.get("firma") or "").strip()
    if not name:
        return None
    try:
        from shared.firmen_link import firmen_name_to_id
        return firmen_name_to_id(_FIRMEN_DB).get(name.casefold())
    except Exception:  # noqa: BLE001
        return None


# ── Generische Quellen (modulübergreifend) ──────────────────────────────────


def _clip(text: str, n: int = 600) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def approved_mapping_items(requirement_id: str, firmen_id: int | None) -> list[EvidenceItem]:
    """Von Menschen freigegebene Anforderung→Nachweis-Mappings (höchste Qualität)."""
    if not requirement_id:
        return []
    try:
        from evidence import db as edb
        rows = edb.list_approved_mappings(str(_EVIDENCE_DB), requirement_id, firmen_id=firmen_id)
    except Exception:  # noqa: BLE001
        return []
    items: list[EvidenceItem] = []
    for r in rows or []:
        claim = r.get("claim") if isinstance(r, dict) else None
        conf = r.get("confidence") if isinstance(r, dict) else None
        if not claim:
            continue
        items.append(EvidenceItem(
            quelle="Freigegebener Nachweis",
            kind="mapping",
            ref=f"mapping:{requirement_id}",
            text=_clip(f"{claim}" + (f" (Konfidenz {conf})" if conf else "")),
            relevance=2.0,  # human-approved → vorrangig
        ))
    return items


def firm_upload_items(firmen_id: int | None, *, limit: int = 4) -> list[EvidenceItem]:
    """Bei der Firma hochgeladene Nachweis-Dokumente (Volltext-Auszug)."""
    if firmen_id is None:
        return []
    try:
        from evidence import db as edb
        docs = edb.list_documents(str(_EVIDENCE_DB), firmen_id=firmen_id)
    except Exception:  # noqa: BLE001
        return []
    items: list[EvidenceItem] = []
    for d in (docs or [])[:limit]:
        doc_id = getattr(d, "id", None) if not isinstance(d, dict) else d.get("id")
        fname = getattr(d, "filename", None) if not isinstance(d, dict) else d.get("filename")
        if doc_id is None:
            continue
        try:
            from evidence import db as edb
            txt = edb.get_extracted_text(str(_EVIDENCE_DB), doc_id) or ""
        except Exception:  # noqa: BLE001
            txt = ""
        if not txt.strip():
            continue
        items.append(EvidenceItem(
            quelle=f"Hochgeladener Nachweis: {fname or doc_id}",
            kind="upload",
            ref=f"doc:{doc_id}",
            text=_clip(txt, 500),
            relevance=1.2,
        ))
    return items


def open_risk_items(firmen_id: int | None) -> list[EvidenceItem]:
    """Kurzübersicht offener Risiken/Schwachstellen der Firma (Risiko-Cockpit)."""
    if firmen_id is None:
        return []
    try:
        from shared.risk_cockpit import build_cockpit
        cockpit = build_cockpit(
            firmen_id,
            rb_db=Path("data/db/risikobewertung.sqlite"),
            cra_db=Path("data/db/cra.sqlite"),
            soc_db=Path("data/db/soc.sqlite"),
        )
    except Exception:  # noqa: BLE001
        return []
    summary = (cockpit or {}).get("summary") or {}
    total = summary.get("total") or 0
    if not total:
        return []
    by_sev = summary.get("by_severity") or {}
    sev_txt = ", ".join(f"{k}: {v}" for k, v in by_sev.items() if v)
    return [EvidenceItem(
        quelle="Risiko-Cockpit (firmenweit)",
        kind="risk",
        ref="risk_cockpit",
        text=_clip(f"{total} offene Risiken/Schwachstellen über alle Module" +
                   (f" — {sev_txt}" if sev_txt else "")),
        relevance=0.8,
    )]


# ── Pure Helfer (ohne DB — direkt testbar) ──────────────────────────────────


def _cached(cache: dict[str, Any] | None, key: str, producer):
    """Firmenweite Lookups je Lauf memoisieren (#1495/Q1)."""
    if cache is None:
        return producer()
    if key not in cache:
        cache[key] = producer()
    return cache[key]


def dedup_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Doppelte (gleiche ref + gleicher Text) entfernen, Reihenfolge erhalten."""
    seen: set[tuple[str, str]] = set()
    out: list[EvidenceItem] = []
    for it in items:
        key = (it.ref, it.text)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


_REDACTED = "[Inhalt redigiert für Cloud-Übertragung — nur on-prem sichtbar]"


def redact_for_cloud(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Sensible Items (PII) für den Cloud-Versand entschärfen (#1486).

    Quelle/Art/Referenz bleiben (die KI weiß, DASS ein Nachweis existiert), der Inhalt
    wird ersetzt. Nicht-sensible Items bleiben unverändert.
    """
    out: list[EvidenceItem] = []
    for it in items:
        if it.sensitive:
            out.append(EvidenceItem(it.quelle, it.kind, it.ref, _REDACTED,
                                    it.relevance, it.sensitive))
        else:
            out.append(it)
    return out


def rank_and_truncate(items: list[EvidenceItem], max_chars: int) -> list[EvidenceItem]:
    """Nach Relevanz sortieren und auf das Zeichen-Budget kürzen (Prompt-Bloat-Schutz)."""
    ranked = sorted(items, key=lambda i: i.relevance, reverse=True)
    out: list[EvidenceItem] = []
    used = 0
    for it in ranked:
        ln = len(it.render()) + 1
        if out and used + ln > max_chars:
            break
        out.append(it)
        used += ln
    return out


def render_block(items: list[EvidenceItem]) -> str:
    """Items als Markdown-Liste rendern (leer → '')."""
    return "\n".join(it.render() for it in items) if items else ""


# ── Aggregator (#1483) ──────────────────────────────────────────────────────


def build_context(
    modul: str,
    projekt: dict[str, Any],
    requirement: dict[str, Any],
    *,
    firmen_id: int | None = None,
    max_chars: int = 3500,
    for_cloud: bool = False,
    include_uploads: bool = True,
    include_risks: bool = True,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregiert die App-Evidenz für eine Anforderung.

    Returns ``{items, rendered_block, sources}``. Best-effort, wirft nie.

    ``cache`` (#1495/Q1): optionales Dict, in dem firmenweite Lookups (firmen_id,
    Uploads, Risiko-Cockpit) über mehrere Anforderungen EINES Laufs gemerkt werden —
    die Massenbewertung löst sie so nur einmal statt je Anforderung neu auf.
    """
    items: list[EvidenceItem] = []
    if firmen_id is None:
        if cache is not None and "firmen_id" in cache:
            firmen_id = cache["firmen_id"]
        else:
            firmen_id = resolve_firmen_id(projekt)
            if cache is not None:
                cache["firmen_id"] = firmen_id

    req_id = str(requirement.get("id") or "") if isinstance(requirement, dict) else ""

    # 1. Modul-spezifischer Provider (relevanteste, gezielte Nachweise — IMMER pro Anforderung)
    prov = get_evidence_provider(modul)
    if prov is not None and hasattr(prov, "relevant_for"):
        try:
            extra = prov.relevant_for(projekt, requirement) or []
            items.extend(it for it in extra if isinstance(it, EvidenceItem))
        except Exception:  # noqa: BLE001
            pass

    # 2. Von Menschen freigegebene Anforderung→Nachweis-Mappings (pro Anforderung)
    items.extend(approved_mapping_items(req_id, firmen_id))

    # 3. Generische Firmen-Quellen (firmenweit → cachebar pro Lauf)
    if include_uploads:
        items.extend(_cached(cache, "uploads", lambda: firm_upload_items(firmen_id)))
    if include_risks:
        items.extend(_cached(cache, "risks", lambda: open_risk_items(firmen_id)))

    items = dedup_items(items)
    if for_cloud:
        items = redact_for_cloud(items)
    items = rank_and_truncate(items, max_chars)
    return {
        "items": items,
        "rendered_block": render_block(items),
        "sources": [it.ref for it in items],
    }


# ── Endpoint-Einstieg mit Cloud-/Config-Gate (#1485/#1486) ──────────────────


def _config_ai() -> dict[str, Any]:
    try:
        from ai_compliance_suite.config import load_config
        return (load_config() or {}).get("ai", {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def evidence_enabled(for_cloud: bool) -> bool:
    """Ob App-Evidenz injiziert werden darf (#1486).

    on_prem: Default an. cloud: nur Opt-in (``ai.include_app_evidence=true``) UND
    ``ai.cloud.allow_data_egress=true``.
    """
    ai = _config_ai()
    flag = ai.get("include_app_evidence")
    if not for_cloud:
        return True if flag is None else bool(flag)
    # Cloud: hartes Opt-in + Egress-Erlaubnis
    if not bool(flag):
        return False
    return bool((ai.get("cloud", {}) or {}).get("allow_data_egress", False))


def evidence_block_for(
    modul: str,
    projekt: dict[str, Any],
    requirement: dict[str, Any],
    *,
    enabled: bool | None = None,
    max_chars: int = 3500,
    cache: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """Fertiger Evidenz-Block + Quellenliste für einen Bewertungs-Endpoint.

    Respektiert Provider (Cloud vs. on-prem) und das Config-Gate. Liefert ``("", [])``,
    wenn keine Evidenz erlaubt/vorhanden ist → Prompt bleibt dann unverändert.
    ``cache``: für Massenbewertung — firmenweite Lookups je Lauf wiederverwenden (Q1).
    """
    try:
        from ai_compliance_suite.ai.dispatch import is_cloud_provider
        for_cloud = bool(is_cloud_provider())
    except Exception:  # noqa: BLE001
        for_cloud = False

    if enabled is None:
        enabled = evidence_enabled(for_cloud)
    if not enabled:
        return "", []

    try:
        ctx = build_context(modul, projekt, requirement,
                            for_cloud=for_cloud, max_chars=max_chars, cache=cache)
    except Exception:  # noqa: BLE001
        return "", []
    return ctx["rendered_block"], ctx["sources"]


def audit_assessment(modul: str, req_id: str, sources: list[str],
                     genutzte_nachweise: list[str] | None, provider: str | None) -> None:
    """Q3 (#1497): protokolliert eine evidenzgestützte KI-Bewertung append-only (#1338).

    Nur wenn tatsächlich App-Evidenz im Prompt war (``sources`` nicht leer). Best-effort.
    """
    if not sources:
        return
    try:
        from shared.audit import audit_event
        audit_event(
            "ai.assessment.evidence_used",
            module=str(modul),
            details={
                "req_id": req_id,
                "sources": sources,
                "genutzte_nachweise": genutzte_nachweise or [],
                "provider": provider,
            },
        )
    except Exception:  # noqa: BLE001
        pass


__all__ = [
    "EvidenceItem",
    "audit_assessment",
    "get_evidence_provider",
    "resolve_firmen_id",
    "approved_mapping_items",
    "firm_upload_items",
    "open_risk_items",
    "dedup_items",
    "redact_for_cloud",
    "rank_and_truncate",
    "render_block",
    "build_context",
    "evidence_enabled",
    "evidence_block_for",
]
