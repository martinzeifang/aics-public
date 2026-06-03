from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from typing import Callable, Optional

from security_utils import safe_generated_dir, sanitize_untrusted_text, workspace_root_from

# Maximum JSON answer file size: 5MB
MAX_ANSWER_JSON_SIZE = 5 * 1024 * 1024

from .io_xlsx import write_answers_to_copy
from .io_xlsx import read_items
from .prompts import needs_answer


_FULL_ID_RE = re.compile(r"^(?P<file>[^:]+)::(?P<sheet>[^:]+)::R(?P<row>\d+)$")
_ROW_ONLY_RE = re.compile(r"^R?(?P<row>\d+)$", re.IGNORECASE)
_SCHUTZZIEL_CANONICAL = {
    "vertraulichkeit": "Vertraulichkeit",
    "confidentiality": "Vertraulichkeit",
    "integritaet": "Integrität",
    "integritat": "Integrität",
    "integrität": "Integrität",
    "integrity": "Integrität",
    "verfuegbarkeit": "Verfügbarkeit",
    "verfugbarkeit": "Verfügbarkeit",
    "verfügbarkeit": "Verfügbarkeit",
    "availability": "Verfügbarkeit",
    "belastbarkeit": "Belastbarkeit",
    "resilience": "Belastbarkeit",
}
_ALLOWED_KEYS = {"id", "schutzziele", "bemerkung", "contract_assured", "ops_met", "umsetzung", "schutzziel"}


def _normalize_schutzziel(value: object) -> str | None:
    text = sanitize_untrusted_text(value, max_len=40)
    if not text:
        return None
    key = text.casefold()
    return _SCHUTZZIEL_CANONICAL.get(key)


def validate_answer_payload(raw: object, *, expected_file: str) -> list[dict]:
    items = raw if isinstance(raw, list) else [raw] if isinstance(raw, dict) else None
    if items is None:
        raise ValueError("Antwortdatei muss ein JSON-Array oder -Objekt sein")

    out: list[dict] = []
    for idx, obj in enumerate(items, start=1):
        if not isinstance(obj, dict):
            raise ValueError(f"Antwort {idx} ist kein JSON-Objekt")
        unknown = [k for k in obj.keys() if k not in _ALLOWED_KEYS]
        if unknown:
            raise ValueError(f"Antwort {idx} enthaelt unerlaubte Felder: {', '.join(sorted(map(str, unknown)))}")

        item_id = str(obj.get("id") or "").strip()
        row = _parse_row_from_id(item_id, default_file=expected_file)
        if row is None:
            raise ValueError(f"Antwort {idx} hat eine ungueltige oder fremde ID: {item_id!r}")

        schutzziele_raw = obj.get("schutzziele") or []
        if isinstance(schutzziele_raw, str):
            schutzziele_raw = [part.strip() for part in re.split(r"[,;\n]+", schutzziele_raw) if part.strip()]
        if not isinstance(schutzziele_raw, list):
            raise ValueError(f"Antwort {idx}: 'schutzziele' muss ein Array oder String sein")
        schutzziele: list[str] = []
        for raw_target in schutzziele_raw:
            normalized_target = _normalize_schutzziel(raw_target)
            if not normalized_target:
                continue
            if normalized_target not in schutzziele:
                schutzziele.append(normalized_target)

        normalized = {
            "id": item_id,
            "schutzziele": schutzziele,
            "bemerkung": sanitize_untrusted_text(obj.get("bemerkung"), max_len=4000),
        }
        for key in ("contract_assured", "ops_met", "umsetzung", "schutzziel"):
            if key in obj and obj.get(key) is not None:
                if key == "schutzziel":
                    normalized[key] = _normalize_schutzziel(obj.get(key)) or sanitize_untrusted_text(obj.get(key), max_len=120)
                else:
                    normalized[key] = sanitize_untrusted_text(obj.get(key), max_len=120)
        out.append(normalized)
    return out


def apply_answers(new_dir: Path, answers_dir: Path, out_dir: Path, *, evaluated_by: str) -> None:
    apply_answers_selected(
        new_dir=new_dir,
        answers_dir=answers_dir,
        out_dir=out_dir,
        evaluated_by=evaluated_by,
        workbook_names=None,
        overwrite_existing=True,
    )


def apply_answers_selected(
    new_dir: Path,
    answers_dir: Path,
    out_dir: Path,
    *,
    evaluated_by: str,
    workbook_names: list[str] | None = None,
    overwrite_existing: bool = True,
) -> None:
    """Apply answers for all or selected workbooks."""
    root = workspace_root_from(Path(__file__))
    answers_dir = safe_generated_dir(answers_dir, root)
    out_dir = safe_generated_dir(out_dir, root)
    out_dir.mkdir(parents=True, exist_ok=True)
    evaluated_at = date.today().isoformat()
    allowed = {str(x) for x in workbook_names} if workbook_names else None

    for xlsx in sorted(new_dir.glob("*.xlsx")):
        if allowed is not None and xlsx.name not in allowed:
            continue

        existing_items = {int(it.row): it for it in read_items(xlsx)}

        cand = []
        single = answers_dir / f"{xlsx.name}.json"
        if single.exists():
            cand.append(single)
        cand.extend(sorted(answers_dir.glob(f"{xlsx.name}.part*.json")))
        cand.extend(sorted(answers_dir.glob(f"{xlsx.name}.missing*.json")))
        if not cand:
            continue

        data = []
        for ap in cand:
            json_text = ap.read_text(encoding="utf-8")
            if len(json_text) > MAX_ANSWER_JSON_SIZE:
                raise ValueError(
                    f"JSON-Datei zu groß in {ap.name}: "
                    f"{len(json_text) / 1024 / 1024:.1f}MB (max {MAX_ANSWER_JSON_SIZE / 1024 / 1024:.1f}MB)"
                )
            loaded = json.loads(json_text)
            data.extend(validate_answer_payload(loaded, expected_file=xlsx.name))

        updates = []
        for obj in data:
            item_id = obj.get("id")
            row = _parse_row_from_id(item_id, default_file=xlsx.name)
            if row is None:
                raise ValueError(f"Bad id: {item_id!r}")

            current = existing_items.get(int(row))
            if current is None:
                continue
            if (not overwrite_existing) and (not needs_answer(current)):
                continue

            schutzziele = obj.get("schutzziele") or []
            primary = schutzziele[0] if schutzziele else None
            bemerkung = (obj.get("bemerkung") or "").strip()

            upd = {
                "row": row,
                "evaluated_by": evaluated_by,
                "evaluated_at": evaluated_at,
            }

            is_service = ("contract_assured" in obj) or ("ops_met" in obj)
            if not is_service:
                upd["umsetzung"] = obj.get("umsetzung")
                upd["schutzziel"] = obj.get("schutzziel") or primary
                upd["bemerkung_umsetzung"] = bemerkung
            else:
                upd["contract_assured"] = obj.get("contract_assured")
                upd["ops_met"] = obj.get("ops_met")
                if schutzziele:
                    bemerkung = f"Schutzziele: {', '.join(schutzziele)}\n\n{bemerkung}".strip()
                upd["bemerkung"] = bemerkung

            updates.append(upd)

        dst = out_dir / xlsx.name
        write_answers_to_copy(xlsx, dst, updates)

        remaining = [it for it in read_items(dst) if needs_answer(it)]
        if remaining:
            sample = ", ".join(f"R{it.row}" for it in remaining[:10])
            raise ValueError(
                f"Nicht alle Fragen beantwortet in {xlsx.name} (z.B. {sample}). "
                "Bitte fehlende Prompts erzeugen oder Antworten vervollstaendigen."
            )


def analyze_answer_coverage(
    new_dir: Path,
    prompts_dir: Path,
    answers_dir: Path,
    *,
    progress: Optional[Callable[[int, int, str], None]] = None,
    workbook_names: Optional[list[str]] = None,
) -> list[dict]:
    """Analyze which prompt/answer files are missing rows.

    Returns a list of workbook reports. Each report contains prompt-level details.
    """
    reports: list[dict] = []

    files = sorted(new_dir.glob("*.xlsx"))
    if workbook_names:
        allowed = {str(x) for x in workbook_names}
        files = [p for p in files if p.name in allowed]
    total = len(files)
    if progress:
        progress(0, total, "")

    for idx, xlsx in enumerate(files, start=1):
        open_rows = {int(it.row) for it in read_items(xlsx) if needs_answer(it)}
        workbook_report = {
            "workbook": xlsx.name,
            "open_rows": sorted(open_rows),
            "missing_rows": [],
            "prompts": [],
        }

        covered_rows: set[int] = set()
        prompt_files = sorted(prompts_dir.glob(f"{xlsx.name}*.md"))
        for prompt_path in prompt_files:
            prompt_rows = _rows_from_prompt(prompt_path)
            answer_path = answers_dir / (prompt_path.name[:-3] + ".json")
            answer_rows = _rows_from_answer(answer_path) if answer_path.exists() else set()
            missing_in_answer = sorted(r for r in prompt_rows if r in open_rows and r not in answer_rows)
            covered_rows |= {r for r in prompt_rows if r in open_rows}
            workbook_report["prompts"].append(
                {
                    "prompt_file": prompt_path.name,
                    "answer_file": answer_path.name,
                    "prompt_rows": sorted(prompt_rows),
                    "answer_rows": sorted(answer_rows),
                    "missing_rows": missing_in_answer,
                    "answer_exists": answer_path.exists(),
                }
            )

        workbook_report["missing_rows"] = sorted(r for r in open_rows if r not in covered_rows)
        reports.append(workbook_report)
        if progress:
            progress(idx, total, xlsx.name)

    return reports
def _parse_row_from_id(item_id: object, *, default_file: str) -> int | None:
    """Parse BASO IDs.

    Preferred format: <file>::<sheet>::R<row>
    Legacy compatibility: R<row> / <row>
    """
    if not item_id:
        return None
    s = str(item_id).strip()
    if not s:
        return None

    row_only = _ROW_ONLY_RE.match(s)
    if row_only:
        return int(row_only.group("row"))

    m = _FULL_ID_RE.match(s)
    if not m:
        return None
    if m.group("file") != default_file:
        return None
    return int(m.group("row"))


def _rows_from_prompt(prompt_path: Path) -> set[int]:
    rows: set[int] = set()
    try:
        for line in prompt_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("ID:"):
                row = _parse_row_from_id(line.split(":", 1)[1].strip(), default_file=prompt_path.name)
                if row is not None:
                    rows.add(row)
    except Exception:
        return rows
    return rows


def _rows_from_answer(answer_path: Path) -> set[int]:
    rows: set[int] = set()
    try:
        raw = json.loads(answer_path.read_text(encoding="utf-8"))
    except Exception:
        return rows

    items = raw if isinstance(raw, list) else [raw] if isinstance(raw, dict) else []
    for obj in items:
        if not isinstance(obj, dict):
            continue
        row = _parse_row_from_id(obj.get("id"), default_file=answer_path.name)
        if row is not None:
            rows.add(row)
    return rows
