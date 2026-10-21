"""G6-6 — Cross-Reference-Linter: prüft strukturelle Vollständigkeit.

Anforderungen (BISG/DIN EN 16775):
- Jeder Befund (IV) muss in mindestens 1 Beurteilung (V) referenziert sein
- Jede Beurteilung (V) muss eine Norm-Referenz haben
- Jede Beweisfrage muss in mindestens 1 Beurteilung begründet sein
- Jede Beurteilung muss mindestens 1 Befund referenzieren
"""
from __future__ import annotations

from typing import Any


def lint_struktur(
    beweisfragen: list[dict[str, Any]],
    befunde: list[dict[str, Any]],
    beurteilungen: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Strukturelle Vollständigkeitsprüfung.

    Erwartete Felder:
    - beweisfragen: [{nr, frage_text, antwort_text, referenz_beurteilung_ids: [int,...]}]
    - befunde:     [{id, nr, titel}]
    - beurteilungen: [{id, nr, titel, befund_ids: [int,...], norm_referenz: str}]
    """
    hints: list[dict[str, Any]] = []
    beurteilung_ids = {b.get("id") for b in beurteilungen}
    befund_ids = {b.get("id") for b in befunde}

    # 1. Jeder Befund in mindestens 1 Beurteilung
    referenzierte_befunde: set[int] = set()
    for u in beurteilungen:
        for bid in u.get("befund_ids", []) or []:
            referenzierte_befunde.add(bid)
    for b in befunde:
        if b.get("id") not in referenzierte_befunde:
            hints.append({
                "level": "warn",
                "kind": "befund-ohne-beurteilung",
                "ref_id": b.get("id"),
                "ref_nr": b.get("nr", ""),
                "message": f"Befund {b.get('nr', '?')} ({b.get('titel', '?')[:50]}) wird in keiner Beurteilung referenziert",
            })

    # 2. Jede Beurteilung mit Norm-Referenz
    for u in beurteilungen:
        if not (u.get("norm_referenz") or "").strip():
            hints.append({
                "level": "error",
                "kind": "beurteilung-ohne-norm",
                "ref_id": u.get("id"),
                "ref_nr": u.get("nr", ""),
                "message": f"Beurteilung {u.get('nr', '?')} hat keine Norm-Referenz (Pflicht)",
            })

    # 3. Jede Beurteilung referenziert min. 1 Befund
    for u in beurteilungen:
        bids = u.get("befund_ids", []) or []
        if not bids:
            hints.append({
                "level": "error",
                "kind": "beurteilung-ohne-befund",
                "ref_id": u.get("id"),
                "ref_nr": u.get("nr", ""),
                "message": f"Beurteilung {u.get('nr', '?')} referenziert keinen Befund",
            })
        else:
            unbekannte = [bid for bid in bids if bid not in befund_ids]
            if unbekannte:
                hints.append({
                    "level": "error",
                    "kind": "beurteilung-mit-unbekanntem-befund",
                    "ref_id": u.get("id"),
                    "message": f"Beurteilung {u.get('nr', '?')} referenziert nicht-existente Befund-IDs: {unbekannte}",
                })

    # 4. Jede Beweisfrage hat Antwort + Verweis zu Beurteilung
    for f in beweisfragen:
        if not (f.get("antwort_text") or "").strip():
            hints.append({
                "level": "error",
                "kind": "beweisfrage-unbeantwortet",
                "ref_nr": f.get("nr", ""),
                "message": f"Beweisfrage {f.get('nr', '?')} ist nicht beantwortet",
            })
        refs = f.get("referenz_beurteilung_ids", []) or []
        if not refs:
            hints.append({
                "level": "warn",
                "kind": "beweisfrage-ohne-beurteilung-verweis",
                "ref_nr": f.get("nr", ""),
                "message": f"Beweisfrage {f.get('nr', '?')} verweist auf keine Beurteilung in Kap. V",
            })
        else:
            unbekannt = [bid for bid in refs if bid not in beurteilung_ids]
            if unbekannt:
                hints.append({
                    "level": "error",
                    "kind": "beweisfrage-mit-unbekanntem-verweis",
                    "ref_nr": f.get("nr", ""),
                    "message": f"Beweisfrage {f.get('nr', '?')} verweist auf nicht-existente Beurteilungs-IDs: {unbekannt}",
                })

    return hints
