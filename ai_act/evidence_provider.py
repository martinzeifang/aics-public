"""AI-Act-Evidenz-Provider (Sprint #40, #1490).

Mappt AI-Act-Anforderungen auf den operativen Zustand des AI-Act-Moduls, damit die
KI-Bewertung anrechnet, was *durch die Software* erfüllt ist: OWASP-LLM-Register
(``aiact_owasp_llm_checks`` + Mapping ``maps_to`` → Anforderung), die technische
System-Doku (``aiact_system_doku``), das GPAI-Register (``ai_act.gpai``) und das
verknüpfte Risikobewertungs-Projekt (``meta.linked_risk_projekt``) für die
risikobezogenen Anforderungen.

Vertrag: ``relevant_for(projekt, requirement) -> list[EvidenceItem]``. Best-effort —
jeder DB-Zugriff ist gekapselt; Fehler liefern keine Evidenz, brechen aber nie ab.

Hinweis (Generalisierung #1490): Die deterministische AIA-HR-01-Sonderlogik im
Endpoint (``_hr01_linked_risk_result``, #1452) bleibt unverändert. Hier wird die
verknüpfte Risikobewertung *zusätzlich* als Evidenz für *alle* risikobezogenen
Anforderungen bereitgestellt — additiv, nie ersetzend.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.evidence_context import EvidenceItem, _clip

_DB = Path("data/db/ai_act.sqlite")
_RB_DB = Path("data/db/risikobewertung.sqlite")

# Anforderungen, für die eine verknüpfte Risikobewertung relevant ist (Risikomanagement-,
# Bias-/Fairness- und Sicherheits-Anforderungen). Generalisiert über AIA-HR-01 hinaus.
_RISK_REQ = {"AIA-HR-01", "AIA-HR-02", "AIA-HR-07", "AIA-DATA-02"}

# Anforderungen, für die die technische System-Doku ein Erfüllungsnachweis ist.
_DOKU_REQ = {"AIA-HR-03", "AIA-HR-05", "AIA-DATA-01", "AIA-HR-07"}

# Anforderungen, für die das GPAI-Register relevant ist (Governance/Doku/Daten).
_GPAI_REQ = {"AIA-GOV-01", "AIA-HR-03", "AIA-DATA-01", "AIA-HR-02"}


def _owasp_items(projekt_name: str, rid: str) -> list[EvidenceItem]:
    """OWASP-LLM-Checks, deren ``maps_to`` die Anforderung ``rid`` enthält."""
    try:
        from ai_act.db import load_owasp_llm_checks
        from ai_act.owasp_llm_top10 import OWASP_LLM_TOP10
        checks = load_owasp_llm_checks(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not checks:
        return []
    # llm_id → Liste der zugeordneten AI-Act-Anforderungen
    maps: dict[str, list[str]] = {
        str(it.get("id")): list(it.get("maps_to") or []) for it in OWASP_LLM_TOP10
    }
    titles: dict[str, str] = {str(it.get("id")): str(it.get("title") or "") for it in OWASP_LLM_TOP10}
    items: list[EvidenceItem] = []
    for llm_id, chk in checks.items():
        if rid not in maps.get(str(llm_id), []):
            continue
        status = int(chk.get("status") or 0)
        if status <= 0:
            continue  # nur tatsächlich bewertete Checks zählen als Nachweis
        evi = chk.get("evidence") or []
        evi_n = len(evi) if isinstance(evi, list) else 0
        komm = (chk.get("kommentar") or "").strip()
        items.append(EvidenceItem(
            f"OWASP-LLM {llm_id} ({titles.get(str(llm_id), '')})", "register",
            f"aiact_owasp_llm:{llm_id}",
            _clip(f"Status {status}/5"
                  + (f", {evi_n} Repo-Nachweis(e)" if evi_n else "")
                  + (f": {komm}" if komm else "")),
            relevance=1.5))
    return items


def _doku_items(projekt_name: str) -> list[EvidenceItem]:
    """Technische System-Doku (Art. 11/Annex IV) als Erfüllungsnachweis."""
    try:
        from ai_act.db import load_system_doku
        doku = load_system_doku(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not doku:
        return []
    filled = [
        ("System", doku.get("system_name")),
        ("Zweck", doku.get("intended_purpose")),
        ("Architektur", doku.get("architecture")),
        ("Test-Methodik", doku.get("test_methodology")),
        ("Cybersicherheit", doku.get("cybersecurity_measures")),
        ("Genauigkeit/Robustheit", doku.get("accuracy_robustness")),
    ]
    present = [label for label, val in filled if (val or "").strip()]
    if not present:
        return []
    metrics = doku.get("performance_metrics") or []
    metrics_n = len(metrics) if isinstance(metrics, list) else 0
    return [EvidenceItem(
        "AI-Act System-Doku", "document", "aiact_system_doku",
        _clip(f"Technische Dokumentation gepflegt — ausgefüllt: {', '.join(present)}"
              + (f"; {metrics_n} Performance-Metrik(en)" if metrics_n else "")
              + (f". Zweck: {(doku.get('intended_purpose') or '').strip()}"
                 if (doku.get('intended_purpose') or '').strip() else "")),
        relevance=1.4)]


def _gpai_items(projekt_name: str) -> list[EvidenceItem]:
    """GPAI-Klassifizierung + Pflicht-Checks (sofern als GPAI eingestuft)."""
    try:
        from ai_act import gpai
        summ = gpai.summary(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not summ or not summ.get("ist_gpai"):
        return []
    gesamt = int(summ.get("checks_gesamt") or 0)
    erfuellt = int(summ.get("checks_erfuellt") or 0)
    sys_txt = "systemisch" if summ.get("systemisch") else "nicht systemisch"
    return [EvidenceItem(
        "GPAI-Register", "register", "aiact_gpai",
        _clip(f"Als GPAI-Modell klassifiziert ({sys_txt}); {erfuellt}/{gesamt} "
              f"GPAI-Pflicht-Checks erfüllt (Art. 53/55)."),
        relevance=1.3)]


def _linked_risk_items(projekt: dict[str, Any]) -> list[EvidenceItem]:
    """Verknüpftes Risikobewertungs-Projekt als Risikomanagement-Nachweis."""
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
              f"Risiken ({len(bewertet)} bewertet) — Risikomanagement etabliert "
              f"(EU AI Act Art. 9)."),
        relevance=1.5)]


def relevant_for(projekt: dict[str, Any], requirement: dict[str, Any]) -> list[EvidenceItem]:
    name = (projekt.get("name") or "").strip()
    if not name:
        return []
    rid = str(requirement.get("id") or "").upper()
    items: list[EvidenceItem] = []
    # OWASP-LLM-Checks sind immer dann relevant, wenn ein Check auf die Anforderung mappt.
    items += _owasp_items(name, rid)
    if rid in _DOKU_REQ:
        items += _doku_items(name)
    if rid in _GPAI_REQ:
        items += _gpai_items(name)
    if rid in _RISK_REQ:
        items += _linked_risk_items(projekt)
    return items
