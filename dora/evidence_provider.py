"""DORA-Evidenz-Provider (Sprint #40, #1492).

Mappt DORA-Anforderungen auf den operativen Zustand des DORA-Moduls, damit die KI-Bewertung
anrechnet, was *durch die Software* erfasst ist: das IKT-Drittparteien-Register
(`dora_tpp_register`) für den Third-Party-Pfeiler und den Resilienz-Test-/TLPT-Plan
(`dora_testing_plan`) für den Testing-Pfeiler. Wird über `shared/evidence_context` aufgerufen.

Vertrag: ``relevant_for(projekt, requirement) -> list[EvidenceItem]``. Best-effort — jeder
DB-Zugriff ist gekapselt; Fehler liefern keine Evidenz, brechen aber nie ab.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.evidence_context import EvidenceItem, _clip

_DB = Path("data/db/dora.sqlite")

# Pfeiler, für die das jeweilige Register relevant ist.
_TPP_PFEILER = {"ICT-TP"}   # Third-Party Risk Management (Art. 28-44)
_TEST_PFEILER = {"ICT-RT"}  # Resilience Testing (Art. 24-27)

# Abgeschlossene/erledigte Test-Status.
_TEST_DONE = {"done", "completed", "abgeschlossen", "erledigt"}


def _tpp_items(projekt_name: str) -> list[EvidenceItem]:
    try:
        from dora.db import list_tpp
        tpps = list_tpp(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not tpps:
        return []
    kritisch = [t for t in tpps if int(t.get("kritisch") or 0)]
    items = [EvidenceItem(
        "DORA IKT-Drittparteien-Register", "register", "dora_tpp:summary",
        _clip(f"{len(tpps)} IKT-Drittdienstleister erfasst, davon {len(kritisch)} als "
              f"kritisch eingestuft — Register nach Art. 28 geführt."),
        relevance=1.8)]
    for t in kritisch[:3]:
        items.append(EvidenceItem(
            "DORA kritischer IKT-Drittdienstleister", "register",
            f"dora_tpp:{t.get('id')}",
            _clip(f"{t.get('name') or '—'} (Kategorie {t.get('kategorie') or '—'}, "
                  f"Risiko-Score {t.get('risiko_score') or '—'}, Status {t.get('status') or '—'})"),
            relevance=1.4))
    return items


def _test_items(projekt_name: str) -> list[EvidenceItem]:
    try:
        from dora.db import list_tests
        tests = list_tests(_DB, projekt_name)
    except Exception:  # noqa: BLE001
        return []
    if not tests:
        return []
    done = [t for t in tests if str(t.get("status") or "").lower() in _TEST_DONE]
    planned = [t for t in tests if str(t.get("status") or "").lower() not in _TEST_DONE]
    typen = sorted({str(t.get("test_typ") or "").strip() for t in tests if t.get("test_typ")})
    items = [EvidenceItem(
        "DORA Resilienz-Testplan", "register", "dora_testing:summary",
        _clip(f"{len(tests)} Resilienz-Tests im Plan ({len(done)} durchgeführt, "
              f"{len(planned)} geplant)" + (f"; Typen: {', '.join(typen)}" if typen else "") +
              " — Testprogramm nach Art. 24-26 (inkl. TLPT)."),
        relevance=1.8)]
    for t in tests[:3]:
        items.append(EvidenceItem(
            "DORA Resilienz-Test", "register", f"dora_testing:{t.get('id')}",
            _clip(f"{t.get('test_typ') or '—'} (Scope {t.get('scope') or '—'}, "
                  f"Frequenz {t.get('frequenz') or '—'}, Status {t.get('status') or '—'}, "
                  f"nächster Termin {t.get('naechster_termin') or '—'})"),
            relevance=1.3))
    return items


def relevant_for(projekt: dict[str, Any], requirement: dict[str, Any]) -> list[EvidenceItem]:
    name = (projekt.get("name") or "").strip()
    if not name:
        return []
    pfeiler = str(requirement.get("pfeiler") or "").upper()
    items: list[EvidenceItem] = []
    if pfeiler in _TPP_PFEILER:
        items += _tpp_items(name)
    if pfeiler in _TEST_PFEILER:
        items += _test_items(name)
    return items
