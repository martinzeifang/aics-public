"""Kern des geteilten Berichts-Centers (Sprint #35, #1382) — modul-unabhängig.

Zeitraum-Helfer, Lauf-Historie (Tabelle ``<schema>_bericht_runs`` im Modul-Schema)
und ``generate_and_store`` über einen modul-eigenen Render-Callable.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from shared.db import connect, schema_for

_FMT = "%Y-%m-%d %H:%M:%S"


@dataclass
class ReportSpec:
    """Ein Berichtstyp im Katalog (Single Source of Truth je Modul)."""
    key: str
    titel: str
    norm: str = ""
    beschreibung: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"key": self.key, "titel": self.titel, "norm": self.norm,
                "beschreibung": self.beschreibung}


# ── Zeitraum ────────────────────────────────────────────────────────────────

def normalize_zeitraum(von: str | None, bis: str | None) -> tuple[str, str]:
    """('YYYY-MM-DD 00:00:00', 'YYYY-MM-DD 23:59:59'); Default: letzte 90 Tage."""
    def _day(v: str | None) -> date | None:
        if not v:
            return None
        try:
            return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    bis_d = _day(bis) or date.today()
    von_d = _day(von) or (bis_d - timedelta(days=90))
    if von_d > bis_d:
        von_d, bis_d = bis_d, von_d
    return (f"{von_d.isoformat()} 00:00:00", f"{bis_d.isoformat()} 23:59:59")


def quarter_range(*, today: date | None = None) -> tuple[str, str, str]:
    """(von, bis, Label) des zuletzt abgeschlossenen Quartals."""
    t = today or date.today()
    q = (t.month - 1) // 3
    year = t.year
    if q == 0:
        year, sq = t.year - 1, 3
    else:
        sq = q - 1
    start_month = sq * 3 + 1
    end_month = start_month + 2
    von = date(year, start_month, 1)
    bis = date(year, end_month, monthrange(year, end_month)[1])
    return von.isoformat(), bis.isoformat(), f"Q{sq + 1}/{year}"


def year_range(*, today: date | None = None) -> tuple[str, str, str]:
    """(von, bis, Label) des zuletzt abgeschlossenen Kalenderjahres."""
    t = today or date.today()
    y = t.year - 1
    return date(y, 1, 1).isoformat(), date(y, 12, 31).isoformat(), str(y)


# ── Ablage + Historie (je Modul-Schema) ─────────────────────────────────────

def storage_dir(modul: str) -> Path:
    d = Path("data") / modul / "berichte"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _history_table(db_path: Any) -> str:
    return f"{schema_for(db_path)}_bericht_runs"


def ensure_history(db_path: Any) -> None:
    """Lauf-Historie-Tabelle im Modul-Schema anlegen (idempotent)."""
    tbl = _history_table(db_path)
    with connect(db_path) as con:
        con.executescript(f"""
        CREATE TABLE IF NOT EXISTS {tbl} (
            id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            projekt     TEXT NOT NULL DEFAULT '',
            typ         TEXT NOT NULL,
            periode     TEXT NOT NULL DEFAULT '',
            von         TEXT NOT NULL DEFAULT '',
            bis         TEXT NOT NULL DEFAULT '',
            format      TEXT NOT NULL DEFAULT 'docx',
            dateiname   TEXT NOT NULL DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'finished',
            fehler      TEXT NOT NULL DEFAULT '',
            erzeugt_von TEXT NOT NULL DEFAULT 'user',
            created_at  TEXT DEFAULT (aics_now())
        );
        """)


def record_run(db_path: Any, *, typ: str, projekt: str = "", periode: str = "",
               von: str = "", bis: str = "", fmt: str = "docx", dateiname: str = "",
               status: str = "finished", fehler: str = "",
               erzeugt_von: str = "user") -> int:
    ensure_history(db_path)
    tbl = _history_table(db_path)
    with connect(db_path) as con:
        cur = con.execute(
            f"""INSERT INTO {tbl}(projekt, typ, periode, von, bis, format, dateiname,
                status, fehler, erzeugt_von) VALUES(?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            (projekt, typ, periode, von, bis, fmt, dateiname, status, fehler, erzeugt_von))
        return int(cur.lastrowid or 0)


def list_runs(db_path: Any, *, projekt: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    ensure_history(db_path)
    tbl = _history_table(db_path)
    with connect(db_path) as con:
        if projekt is not None:
            rows = con.execute(
                f"SELECT * FROM {tbl} WHERE projekt=? ORDER BY id DESC LIMIT ?",
                (projekt, int(limit))).fetchall()
        else:
            rows = con.execute(
                f"SELECT * FROM {tbl} ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]


def _safe_name(modul: str, typ: str, projekt: str, fmt: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    proj = "".join(c for c in (projekt or "") if c.isalnum() or c in "-_")[:40]
    parts = [modul, typ] + ([proj] if proj else []) + [stamp]
    return "_".join(parts) + f".{fmt}"


def read_stored(modul: str, name: str) -> bytes | None:
    """Abgelegten Bericht lesen (Pfad-Traversal-sicher)."""
    if "/" in name or "\\" in name or ".." in name:
        return None
    base = storage_dir(modul).resolve()
    fp = (base / name).resolve()
    try:
        if fp.parent != base or not fp.is_file():
            return None
        return fp.read_bytes()
    except OSError:
        return None


def generate_and_store(db_path: Any, modul: str, typ: str,
                       render: Callable[..., bytes], *, projekt: str = "",
                       fmt: str = "docx", von: str | None = None, bis: str | None = None,
                       periode: str = "", erzeugt_von: str = "user",
                       **ctx: Any) -> dict[str, Any]:
    """Erzeugt einen Bericht via ``render(typ, fmt, projekt=…, von=…, bis=…, **ctx)``,
    legt ihn unter ``data/<modul>/berichte/`` ab und protokolliert den Lauf.

    PDF wird versucht; scheitert der Konverter, Fallback auf DOCX (kein harter Fehler).
    """
    von_d, bis_d = (normalize_zeitraum(von, bis)[0][:10], normalize_zeitraum(von, bis)[1][:10])
    use_fmt = (fmt or "docx").lower()
    try:
        try:
            data = render(typ, use_fmt, projekt=projekt, von=von_d, bis=bis_d, **ctx)
        except Exception:
            if use_fmt == "pdf":  # Konverter weg → DOCX-Fallback
                use_fmt = "docx"
                data = render(typ, use_fmt, projekt=projekt, von=von_d, bis=bis_d, **ctx)
            else:
                raise
        name = _safe_name(modul, typ, projekt, use_fmt)
        (storage_dir(modul) / name).write_bytes(data)
        rid = record_run(db_path, typ=typ, projekt=projekt, periode=periode, von=von_d,
                         bis=bis_d, fmt=use_fmt, dateiname=name, erzeugt_von=erzeugt_von)
        return {"ok": True, "id": rid, "dateiname": name, "format": use_fmt}
    except Exception as e:  # noqa: BLE001
        record_run(db_path, typ=typ, projekt=projekt, periode=periode, von=von_d, bis=bis_d,
                   fmt=use_fmt, dateiname="", status="failed", fehler=str(e),
                   erzeugt_von=erzeugt_von)
        return {"ok": False, "error": str(e)}
