"""DS-SUB (#1214) — Subprozessor-Register mit Genehmigungs-Workflow (Art. 28(2)/(4)).

Untertabelle ``dsgvo_avv_subprozessoren`` (FK auf ``dsgvo_avv_tracker.id``) in der
geteilten ``data/db/dsgvo.sqlite``. Je Subprozessor: eigene Drittland-/Garantie-
Bewertung, Genehmigungs-Status (ausstehend/genehmigt/abgelehnt) + Datum sowie der
Nachweis der **back-to-back** Weitergabe identischer Datenschutzpflichten.

Trigger: Hat ein AVV-Eintrag mindestens einen ungenehmigten Subprozessor, gilt der
Haupt-AVV als ``review-faellig`` (Art. 28(2): vorherige Genehmigung erforderlich).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")

GENEHMIGUNG = ("ausstehend", "genehmigt", "abgelehnt")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_avv_subprozessoren (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name       TEXT NOT NULL,
    avv_pk             INTEGER NOT NULL,           -- FK -> dsgvo_avv_tracker.id
    name               TEXT NOT NULL,
    leistung           TEXT NOT NULL DEFAULT '',
    drittland          INTEGER NOT NULL DEFAULT 0,
    drittland_garantie TEXT NOT NULL DEFAULT '',   -- SCC | Adäquanz | BCR
    genehmigung_status TEXT NOT NULL DEFAULT 'ausstehend',
    genehmigung_datum  TEXT NOT NULL DEFAULT '',
    sub_avv_vorhanden  INTEGER NOT NULL DEFAULT 0,
    sub_avv_url        TEXT NOT NULL DEFAULT '',
    sub_avv_datum      TEXT NOT NULL DEFAULT '',
    pflichten_backtoback INTEGER NOT NULL DEFAULT 0, -- identische Pflichten weitergegeben
    notizen            TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT (aics_now()),
    updated_at         TEXT NOT NULL DEFAULT (aics_now())
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_sub_avv ON dsgvo_avv_subprozessoren(avv_pk);
CREATE INDEX IF NOT EXISTS idx_dsgvo_sub_projekt ON dsgvo_avv_subprozessoren(projekt_name);
"""

_ALLOWED = (
    "name", "leistung", "drittland", "drittland_garantie", "genehmigung_status",
    "genehmigung_datum", "sub_avv_vorhanden", "sub_avv_url", "sub_avv_datum",
    "pflichten_backtoback", "notizen",
)
_BOOL = ("drittland", "sub_avv_vorhanden", "pflichten_backtoback")


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    for b in _BOOL:
        d[b] = int(d.get(b) or 0)
    return d


def list_subprozessoren(db_path: Path, projekt_name: str, avv_pk: int
                        ) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM dsgvo_avv_subprozessoren WHERE projekt_name=? AND avv_pk=? "
            "ORDER BY name", (projekt_name, int(avv_pk))).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()


def get_subprozessor(db_path: Path, pk: int, projekt_name: str | None = None
                     ) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if projekt_name is not None:
            r = con.execute(
                "SELECT * FROM dsgvo_avv_subprozessoren WHERE id=? AND projekt_name=?",
                (int(pk), projekt_name)).fetchone()
        else:
            r = con.execute(
                "SELECT * FROM dsgvo_avv_subprozessoren WHERE id=?", (int(pk),)).fetchone()
        return _row(r) if r is not None else None
    finally:
        con.close()


def save_subprozessor(db_path: Path, projekt_name: str, avv_pk: int,
                      data: dict, *, pk: int | None = None) -> int:
    ensure_table(db_path)
    if not (data.get("name") or "").strip() and pk is None:
        raise ValueError("'name' ist Pflicht")
    if data.get("genehmigung_status") and data["genehmigung_status"] not in GENEHMIGUNG:
        raise ValueError(f"Ungültiger Genehmigungs-Status: {data['genehmigung_status']}")

    values = {k: data.get(k) for k in _ALLOWED if k in data}
    for b in _BOOL:
        if b in values:
            values[b] = int(bool(values[b]))

    con = _connect(Path(db_path))
    try:
        if pk is not None:
            # IDOR: nur eigener Projekt-Datensatz.
            existing = con.execute(
                "SELECT id FROM dsgvo_avv_subprozessoren WHERE id=? AND projekt_name=?",
                (int(pk), projekt_name)).fetchone()
            if not existing:
                raise ValueError("Subprozessor nicht gefunden")
            if values:
                sets = ", ".join(f"{k}=?" for k in values)
                con.execute(
                    f"UPDATE dsgvo_avv_subprozessoren SET {sets}, updated_at=aics_now() "
                    f"WHERE id=? AND projekt_name=?",
                    list(values.values()) + [int(pk), projekt_name])
            con.commit()
            return int(pk)
        cols = ["avv_pk"] + list(values.keys())
        vals = [int(avv_pk)] + list(values.values())
        ph = ",".join("?" for _ in cols)
        cur = con.execute(
            f"INSERT INTO dsgvo_avv_subprozessoren (projekt_name, {','.join(cols)}) "
            f"VALUES (?, {ph})", [projekt_name] + vals)
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def set_genehmigung(db_path: Path, pk: int, projekt_name: str, status: str,
                    *, datum: str = "") -> bool:
    ensure_table(db_path)
    if status not in GENEHMIGUNG:
        raise ValueError(f"Ungültiger Status: {status}")
    con = _connect(Path(db_path))
    try:
        cur = con.execute(
            "UPDATE dsgvo_avv_subprozessoren SET genehmigung_status=?, genehmigung_datum=?, "
            "updated_at=aics_now() WHERE id=? AND projekt_name=?",
            (status, datum, int(pk), projekt_name))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def delete_subprozessor(db_path: Path, pk: int, projekt_name: str | None = None) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if projekt_name is not None:
            cur = con.execute(
                "DELETE FROM dsgvo_avv_subprozessoren WHERE id=? AND projekt_name=?",
                (int(pk), projekt_name))
        else:
            cur = con.execute(
                "DELETE FROM dsgvo_avv_subprozessoren WHERE id=?", (int(pk),))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def avv_review_faellig(db_path: Path, projekt_name: str, avv_pk: int) -> bool:
    """True, wenn mind. ein Subprozessor noch nicht genehmigt ist (Art. 28(2))."""
    subs = list_subprozessoren(db_path, projekt_name, avv_pk)
    return any(s.get("genehmigung_status") != "genehmigt" for s in subs)


def counts_by_avv(db_path: Path, projekt_name: str) -> dict[int, dict[str, int]]:
    """{avv_pk: {gesamt, ausstehend}} — für Trigger-Pillen im AVV-Panel."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT avv_pk, genehmigung_status FROM dsgvo_avv_subprozessoren "
            "WHERE projekt_name=?", (projekt_name,)).fetchall()
    finally:
        con.close()
    out: dict[int, dict[str, int]] = {}
    for r in rows:
        d = out.setdefault(int(r["avv_pk"]), {"gesamt": 0, "ausstehend": 0})
        d["gesamt"] += 1
        if r["genehmigung_status"] != "genehmigt":
            d["ausstehend"] += 1
    return out
