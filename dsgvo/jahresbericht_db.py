"""DS-J3 (#1134) — Jahresbericht Online-Freigabe (GF) + DSB-Signatur.

Status: entwurf → freigegeben (GF) → signiert (DSB). Nach Signatur unveränderlich
(finalisierte PDF + SHA-256 im Archiv).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dsgvo.db import _connect

DB_PATH = Path("data/db/dsgvo.sqlite")
FINAL_DIR = Path("data/dsgvo/jahresberichte")

STATUS = ("entwurf", "freigegeben", "signiert")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dsgvo_jahresbericht (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name  TEXT NOT NULL,
    jahr          INTEGER NOT NULL,
    status        TEXT NOT NULL DEFAULT 'entwurf',
    freigabe_von  TEXT NOT NULL DEFAULT '',
    freigabe_am   TEXT NOT NULL DEFAULT '',
    signatur_von  TEXT NOT NULL DEFAULT '',
    signatur_name TEXT NOT NULL DEFAULT '',
    signatur_am   TEXT NOT NULL DEFAULT '',
    sha256        TEXT NOT NULL DEFAULT '',
    pdf_path      TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (aics_now()),
    updated_at    TEXT NOT NULL DEFAULT (aics_now()),
    UNIQUE(projekt_name, jahr)
);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def get(db_path: Path, projekt_name: str, jahr: int) -> dict[str, Any]:
    """Liefert den Datensatz (oder einen Default-Entwurf, falls noch keiner existiert)."""
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        r = con.execute(
            "SELECT * FROM dsgvo_jahresbericht WHERE projekt_name=? AND jahr=?",
            (projekt_name, int(jahr))).fetchone()
        if r:
            return dict(r)
        return {"projekt_name": projekt_name, "jahr": int(jahr), "status": "entwurf",
                "freigabe_von": "", "freigabe_am": "", "signatur_von": "",
                "signatur_name": "", "signatur_am": "", "sha256": "", "pdf_path": ""}
    finally:
        con.close()


def _ensure_row(con: Any, projekt_name: str, jahr: int) -> None:
    con.execute(
        "INSERT INTO dsgvo_jahresbericht (projekt_name, jahr) VALUES (?,?) ON CONFLICT DO NOTHING",
        (projekt_name, int(jahr)))


def freigeben(db_path: Path, projekt_name: str, jahr: int, *, von: str) -> dict[str, Any]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        _ensure_row(con, projekt_name, jahr)
        con.execute(
            "UPDATE dsgvo_jahresbericht SET status='freigegeben', freigabe_von=?, "
            "freigabe_am=aics_now(), updated_at=aics_now() "
            "WHERE projekt_name=? AND jahr=? AND status='entwurf'",
            (von, projekt_name, int(jahr)))
        con.commit()
    finally:
        con.close()
    return get(db_path, projekt_name, jahr)


def signieren(db_path: Path, projekt_name: str, jahr: int, *, von: str, name: str,
              pdf_bytes: bytes) -> dict[str, Any]:
    """Signiert (DSB) + speichert finalisierte PDF unveränderlich (SHA-256)."""
    import hashlib
    ensure_table(db_path)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    safe = f"{projekt_name}_{jahr}_{sha[:12]}.pdf".replace("/", "-")
    dest = FINAL_DIR / safe
    dest.write_bytes(pdf_bytes)
    con = _connect(Path(db_path))
    try:
        _ensure_row(con, projekt_name, jahr)
        con.execute(
            "UPDATE dsgvo_jahresbericht SET status='signiert', signatur_von=?, "
            "signatur_name=?, signatur_am=aics_now(), sha256=?, pdf_path=?, "
            "updated_at=aics_now() WHERE projekt_name=? AND jahr=?",
            (von, name, sha, str(dest), projekt_name, int(jahr)))
        con.commit()
    finally:
        con.close()
    return get(db_path, projekt_name, jahr)
