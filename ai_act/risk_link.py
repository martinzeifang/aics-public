"""AIA-HR-01 (Art. 9 Risikomanagement-System) aus der verknüpften Risikobewertung (#1561).

Vorher (#1452) galt HR-01 pauschal als erfüllt (Score 5), sobald *irgendein*
Risikobewertungs-Projekt verknüpft war — auch ein leeres. Für einen Audit-Nachweis
muss der Score dem **Inhalt** folgen. Regel (transparent, im Kommentar begründet):

====  ======================================================================
Score Bedingung
====  ======================================================================
1     verknüpft, aber noch keine Risiken erfasst
2     Risiken erfasst, aber nicht alle bewertet
3     alle Risiken bewertet
4     alle bewertet und ≥ 50 % der hohen/kritischen Risiken behandelt
5     alle bewertet und alle hohen/kritischen Risiken behandelt
====  ======================================================================

„Behandelt" = ``is_resolved`` im RB-Projekt. Gibt es keine hohen/kritischen
Risiken, reicht „alle bewertet" + mindestens ein Risiko für Score 5.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

HIGH_LABELS = frozenset({"hoch", "sehr hoch", "kritisch"})
RB_DB_PATH = Path("data/db/risikobewertung.sqlite")


def risk_stats(risiken: list[dict[str, Any]]) -> dict[str, int]:
    """Kennzahlen eines RB-Projekts für den HR-01-Nachweis."""
    bewertet = [r for r in risiken if r.get("risikowert") is not None]
    hoch = [r for r in bewertet if str(r.get("risiko_label") or "").strip().casefold() in HIGH_LABELS]
    return {
        "total": len(risiken),
        "bewertet": len(bewertet),
        "hoch": len(hoch),
        "hoch_behandelt": sum(1 for r in hoch if r.get("is_resolved")),
        "behandelt": sum(1 for r in risiken if r.get("is_resolved")),
    }


def score_from_stats(s: dict[str, int]) -> int:
    if s["total"] == 0:
        return 1
    if s["bewertet"] < s["total"]:
        return 2
    if s["hoch"] == 0 or s["hoch_behandelt"] == s["hoch"]:
        return 5
    if s["hoch_behandelt"] * 2 >= s["hoch"]:
        return 4
    return 3


def kommentar_from_stats(rb_name: str, s: dict[str, int], score: int) -> str:
    lage = (f"{s['total']} Risiken, davon {s['bewertet']} bewertet; "
            f"{s['hoch']} hoch/kritisch, davon {s['hoch_behandelt']} behandelt")
    hinweis = {
        1: "Es sind noch keine Risiken erfasst — Risikoidentifikation (Art. 9 Abs. 2 a) fehlt.",
        2: "Nicht alle Risiken sind bewertet — Abschätzung/Bewertung (Art. 9 Abs. 2 b) unvollständig.",
        3: "Hohe/kritische Risiken sind überwiegend noch nicht behandelt (Art. 9 Abs. 2 d, Abs. 5).",
        4: "Ein Teil der hohen/kritischen Risiken ist noch offen (Art. 9 Abs. 5).",
        5: "Risiken identifiziert, bewertet und die hohen/kritischen behandelt.",
    }[score]
    return (f"Risikomanagement-System (Art. 9) über die verknüpfte Risikobewertung "
            f"„{rb_name}“: {lage}. {hinweis}")


def evaluate(rb_name: str, *, rb_db: Path | None = None) -> dict[str, Any] | None:
    """HR-01-Vorschlag aus dem verknüpften RB-Projekt; ``None`` ohne Verknüpfung.

    Best-effort: ist das RB-Projekt nicht lesbar, gilt es als leer (Score 1)."""
    name = (rb_name or "").strip()
    if not name:
        return None
    try:
        from risikobewertung.db import load_risiken
        risiken = load_risiken(rb_db or RB_DB_PATH, name)
    except Exception:  # noqa: BLE001
        risiken = []
    stats = risk_stats(risiken)
    score = score_from_stats(stats)
    return {"rb_projekt": name, "stats": stats, "score": score,
            "kommentar": kommentar_from_stats(name, stats, score)}
