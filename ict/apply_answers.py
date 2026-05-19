from __future__ import annotations

import json
import re
from pathlib import Path

from security_utils import safe_generated_dir, workspace_root_from

from .io_xlsx import read_items, write_answers_to_copy
from .prompts import validate_answer_payload

# Maximum JSON answer file size: 5MB
MAX_ANSWER_JSON_SIZE = 5 * 1024 * 1024


_FULL_ID_RE = re.compile(r"^(?P<file>[^:]+)::(?P<sheet>[^:]+)::R(?P<row>\d+)$")
_ROW_ONLY_RE = re.compile(r"^R?(?P<row>\d+)$", re.IGNORECASE)


def _parse_row_from_id(item_id: object, *, default_file: str) -> int | None:
    if not item_id:
        return None
    s = str(item_id).strip()
    if not s:
        return None
    m = _ROW_ONLY_RE.match(s)
    if m:
        return int(m.group("row"))
    m = _FULL_ID_RE.match(s)
    if not m:
        return None
    if m.group("file") != default_file:
        return None
    return int(m.group("row"))


def apply_answers_selected(new_dir: Path, answers_dir: Path, out_dir: Path, *, workbook_names: list[str] | None = None) -> None:
    root = workspace_root_from(Path(__file__))
    answers_dir = safe_generated_dir(answers_dir, root)
    out_dir = safe_generated_dir(out_dir, root)
    out_dir.mkdir(parents=True, exist_ok=True)
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

        data: list[dict] = []
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
        seen_rows: set[int] = set()
        for obj in data:
            row = _parse_row_from_id(obj.get("id"), default_file=xlsx.name)
            if row is None or row in seen_rows:
                continue
            current = existing_items.get(int(row))
            if current is None:
                continue
            seen_rows.add(row)
            updates.append({
                "row": row,
                "answer": obj.get("answer"),
                "maturity": obj.get("maturity"),
                "explanation": obj.get("explanation"),
                "optimization_potential": obj.get("optimization_potential"),
            })

        dst = out_dir / xlsx.name
        write_answers_to_copy(xlsx, dst, updates)
