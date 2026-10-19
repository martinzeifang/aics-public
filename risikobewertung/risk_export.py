"""Machine-readable risk export (JSON + Markdown summary).

Used for CRA automation workflows (diff-friendly exports for GitHub/GitLab).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def _safe_name(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "projekt"
    # Keep paths short on Windows to avoid MAX_PATH (WinError 206).
    raw = s
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in raw).strip() or "projekt"
    safe = safe.strip(" ._-\t") or "projekt"
    max_len = 24
    if len(safe) <= max_len:
        return safe
    h = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:8]
    keep = max(1, max_len - (1 + len(h)))
    return (safe[:keep].rstrip(" ._-\t") + "_" + h) or ("projekt_" + h)


def export_risk_json_md(
    *,
    out_dir: Path,
    projekt_name: str,
    framework: str,
    scope_label: str,
    risks: list[dict[str, Any]],
) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    proj_dir = out_dir / _safe_name(projekt_name)
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Stable file names for diff-friendly tracking.
    json_path = proj_dir / "risk-export.json"
    md_path = proj_dir / "risk-export.md"

    def risk_key(r: dict[str, Any]) -> tuple:
        try:
            nr = int(r.get("nr") or 0)
        except Exception:
            nr = 0
        return (nr, int(r.get("id") or 0))

    risks_sorted = sorted(risks or [], key=risk_key)

    payload = {
        "schema": "ai-compliance-suite/risk-export/v1",
        "generated_at": int(time.time()),
        "projekt": {
            "name": projekt_name,
            "framework": framework,
            "scope": scope_label,
        },
        "risks": [
            {
                "id": int(r.get("id") or 0),
                "nr": int(r.get("nr") or 0),
                "name": str(r.get("risk_name") or ""),
                "beschreibung": str(r.get("beschreibung") or ""),
                "framework": str(r.get("framework") or framework),
                "felder": r.get("felder") or {},
                "score": r.get("risikowert"),
                "level": str(r.get("risiko_label") or ""),
                "detail": str(r.get("detail_text") or ""),
                "bewertung": str(r.get("bewertung_text") or ""),
                "mitigation": str(r.get("empfehlung") or r.get("massnahme") or ""),
                "updated_at": r.get("updated_at"),
            }
            for r in risks_sorted
        ],
    }

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append(f"# Risk Export ({framework})")
    lines.append("")
    lines.append(f"Projekt: **{projekt_name}**")
    lines.append(f"Umfang: **{scope_label}**")
    lines.append(f"Generiert: {payload['generated_at']}")
    lines.append("")
    lines.append("## Zusammenfassung")
    lines.append(f"- Risiken: {len(risks_sorted)}")
    scored = [r for r in risks_sorted if r.get("risikowert") is not None]
    lines.append(f"- Bewertet: {len(scored)}")
    if scored:
        try:
            avg = sum(int(r.get("risikowert") or 0) for r in scored) / len(scored)
            lines.append(f"- Durchschnitt Score: {avg:.1f}")
        except Exception:
            pass
    lines.append("")
    lines.append("## Risiken")
    for r in risks_sorted:
        nr = r.get("nr")
        name = str(r.get("risk_name") or "")
        level = str(r.get("risiko_label") or "")
        score = r.get("risikowert")
        lines.append(f"- {nr}. {name} ({level}, score={score})")

    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, md_path
