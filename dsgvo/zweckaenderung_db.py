"""DS-ZA (#1215) — Kompatibilitätstest bei Zweckänderung (Art. 6(4) DSGVO).

Sub-Register ``dsgvo_zweckaenderung`` (je VVT-Eintrag) für den dokumentierten
Vereinbarkeits-/Kompatibilitätstest bei Weiterverarbeitung zu einem anderen Zweck.
Die fünf Art.-6(4)-Kriterien:

  a) Zusammenhang ursprünglicher/neuer Zweck (Buchst. a)
  b) Erhebungskontext, insb. Verhältnis Betroffene ↔ Verantwortlicher (Buchst. b)
  c) Art der Daten, insb. besondere Kategorien Art. 9 / Art. 10 (Buchst. c)
  d) Mögliche Folgen für die Betroffenen (Buchst. d)
  e) Geeignete Garantien, z. B. Verschlüsselung/Pseudonymisierung (Buchst. e)

Ergebnis: ``vereinbar`` (zulässige Weiterverarbeitung) / ``unvereinbar`` (neue
Rechtsgrundlage erforderlich).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")

ERGEBNIS = ("offen", "vereinbar", "unvereinbar")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_zweckaenderung (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name         TEXT NOT NULL,
    za_id                TEXT NOT NULL,
    vvt_ref              TEXT NOT NULL DEFAULT '',
    urspruenglicher_zweck TEXT NOT NULL DEFAULT '',
    neuer_zweck          TEXT NOT NULL DEFAULT '',
    -- 5 Art.-6(4)-Kriterien
    krit_zusammenhang    TEXT NOT NULL DEFAULT '',   -- a
    krit_kontext         TEXT NOT NULL DEFAULT '',   -- b
    krit_datenart        TEXT NOT NULL DEFAULT '',   -- c
    krit_folgen          TEXT NOT NULL DEFAULT '',   -- d
    krit_garantien       TEXT NOT NULL DEFAULT '',   -- e
    ergebnis             TEXT NOT NULL DEFAULT 'offen',
    ergebnis_begruendung TEXT NOT NULL DEFAULT '',
    neue_rechtsgrundlage TEXT NOT NULL DEFAULT '',
    reviewer             TEXT NOT NULL DEFAULT '',
    review_datum         TEXT NOT NULL DEFAULT '',
    created_at           TEXT NOT NULL DEFAULT (aics_now()),
    updated_at           TEXT NOT NULL DEFAULT (aics_now()),
    UNIQUE(projekt_name, za_id)
);
CREATE INDEX IF NOT EXISTS idx_dsgvo_za_projekt ON dsgvo_zweckaenderung(projekt_name);
"""

_ALLOWED = (
    "vvt_ref", "urspruenglicher_zweck", "neuer_zweck", "krit_zusammenhang",
    "krit_kontext", "krit_datenart", "krit_folgen", "krit_garantien",
    "ergebnis", "ergebnis_begruendung", "neue_rechtsgrundlage",
    "reviewer", "review_datum",
)


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _row(r: Any) -> dict[str, Any]:
    return dict(r)


def list_za(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM dsgvo_zweckaenderung WHERE projekt_name=? ORDER BY za_id",
            (projekt_name,)).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()


def get_za(db_path: Path, pk: int, projekt_name: str | None = None) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if projekt_name is not None:
            r = con.execute("SELECT * FROM dsgvo_zweckaenderung WHERE id=? AND projekt_name=?",
                            (int(pk), projekt_name)).fetchone()
        else:
            r = con.execute("SELECT * FROM dsgvo_zweckaenderung WHERE id=?", (int(pk),)).fetchone()
        return _row(r) if r is not None else None
    finally:
        con.close()


def save_za(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_table(db_path)
    za_id = data.get("za_id")
    if not za_id:
        raise ValueError("'za_id' ist Pflicht")
    if data.get("ergebnis") and data["ergebnis"] not in ERGEBNIS:
        raise ValueError(f"Ungültiges Ergebnis: {data['ergebnis']}")

    values = {k: data.get(k) for k in _ALLOWED if k in data}
    con = _connect(Path(db_path))
    try:
        existing = con.execute(
            "SELECT id FROM dsgvo_zweckaenderung WHERE projekt_name=? AND za_id=?",
            (projekt_name, za_id)).fetchone()
        if existing:
            if values:
                sets = ", ".join(f"{k}=?" for k in values)
                con.execute(
                    f"UPDATE dsgvo_zweckaenderung SET {sets}, updated_at=aics_now() WHERE id=?",
                    list(values.values()) + [int(existing["id"])])
            pk = int(existing["id"])
        else:
            cols = ["za_id"] + list(values.keys())
            vals = [za_id] + list(values.values())
            ph = ",".join("?" for _ in cols)
            cur = con.execute(
                f"INSERT INTO dsgvo_zweckaenderung (projekt_name, {','.join(cols)}) "
                f"VALUES (?, {ph})", [projekt_name] + vals)
            pk = int(cur.lastrowid)
        con.commit()
        return pk
    finally:
        con.close()


def delete_za(db_path: Path, pk: int, projekt_name: str | None = None) -> bool:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        if projekt_name is not None:
            cur = con.execute("DELETE FROM dsgvo_zweckaenderung WHERE id=? AND projekt_name=?",
                              (int(pk), projekt_name))
        else:
            cur = con.execute("DELETE FROM dsgvo_zweckaenderung WHERE id=?", (int(pk),))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()
