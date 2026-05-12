"""AI Act report export (Markdown)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_act.db import load_bewertungen, load_projekt
from ai_act.requirements import AI_ACT_REQUIREMENTS, BEWERTUNG_SKALA, berechne_reifegrad


def export_markdown(*, db_path: Path, projekt_name: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    proj = load_projekt(db_path, projekt_name) or {}
    bew_raw = load_bewertungen(db_path, projekt_name)
    bew = {rid: int(d.get("bewertung", 0) or 0) for rid, d in bew_raw.items()}
    reife = berechne_reifegrad(bew)

    def _label(val: int) -> str:
        return str(BEWERTUNG_SKALA.get(val, {}).get("label", str(val)))

    lines: list[str] = []
    lines.append(f"# AI Act Readiness Report – {projekt_name}")
    lines.append("")
    lines.append(f"- Reifegrad: {float(reife.get('gesamt_pct', 0.0) or 0.0):.0f}% ({reife.get('ampel','')})")
    lines.append(f"- Bewertet: {int(reife.get('bewertete_count', 0) or 0)}/{int(reife.get('gesamt_count', 0) or 0)}")

    org = str(proj.get("organisation") or "").strip()
    prod = str(proj.get("produkt") or "").strip()
    if org:
        lines.append(f"- Organisation: {org}")
    if prod:
        lines.append(f"- Produkt/System: {prod}")
    lines.append("")

    lines.append("## Anforderungen")
    lines.append("")
    for req in AI_ACT_REQUIREMENTS:
        rid = str(req.get("id") or "")
        if not rid:
            continue
        r = bew_raw.get(rid, {})
        score = int(r.get("bewertung", 0) or 0)
        kom = str(r.get("kommentar", "") or "").strip()
        mass = str(r.get("massnahme", "") or "").strip()
        lines.append(f"### {rid} – {req.get('titel','')}")
        lines.append(f"- Kapitel: {req.get('kapitel','')}")
        lines.append(f"- Bewertung: {score} – {_label(score)}")
        if req.get("ref"):
            lines.append(f"- Ref: {req.get('ref')}")
        if req.get("beschreibung"):
            lines.append(f"- Beschreibung: {str(req.get('beschreibung') or '').strip()}")
        ev = req.get("evidence")
        if isinstance(ev, list) and ev:
            lines.append("- Evidence (Beispiele):")
            for x in ev[:10]:
                lines.append(f"  - {x}")
        if kom:
            lines.append(f"- Kommentar: {kom}")
        if mass:
            lines.append(f"- Maßnahme: {mass}")
        lines.append("")

    fn_safe = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in projekt_name)
    out_path = out_dir / f"ai-act-report_{fn_safe}.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
