from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional


def today_ddmmyyyy() -> str:
    return date.today().strftime("%d.%m.%Y")


def normalize_ddmmyyyy(s: str) -> str:
    """Normalize date to dd.mm.yyyy when possible.

    Accepts common inputs: yyyy-mm-dd, dd.mm.yyyy, dd/mm/yyyy, yyyy/mm/dd.
    If parsing fails, returns the original string trimmed.
    """
    raw = (s or "").strip()
    if not raw:
        return raw

    # Extract date-like prefix if time is included.
    m = re.match(r"^(\d{1,4}[-./]\d{1,2}[-./]\d{1,4})", raw)
    if m:
        raw2 = m.group(1)
    else:
        raw2 = raw

    fmts = [
        "%d.%m.%Y",
        "%d.%m.%y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]
    for f in fmts:
        try:
            dt = datetime.strptime(raw2, f)
            return dt.strftime("%d.%m.%Y")
        except Exception:
            continue

    return raw
