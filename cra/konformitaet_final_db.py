"""Unveränderliches Archiv des Konformitätsnachweises je Release (#1611).

Nach Freigabe wird die finalisierte PDF mit SHA-256 und Freigeber dauerhaft abgelegt
(wie Gutachten-Final #969 / DSGVO-Jahresbericht #1132). Danach unveränderlich.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from shared import db as _sdb

DB = Path("data/db/cra.sqlite")
STORE = Path("data/cra/konformitaet")


def ensure_table(db_path: Path = DB) -> None:
    con = _sdb.connect(str(db_path))
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS cra_konformitaet_final (
                   id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                   projekt_name TEXT NOT NULL,
                   version TEXT NOT NULL DEFAULT '',
                   pdf_path TEXT NOT NULL DEFAULT '',
                   sha256 TEXT NOT NULL DEFAULT '',
                   ampel TEXT NOT NULL DEFAULT '',
                   freigegeben_von TEXT NOT NULL DEFAULT '',
                   freigegeben_am TEXT DEFAULT (aics_now())
               )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_cra_konf_final_proj "
                    "ON cra_konformitaet_final(projekt_name)")
        con.commit()
    finally:
        con.close()


def _pruefe_vorbedingung(db_path: Path, projekt_name: str, version: str,
                         freigegeben_von: str) -> None:
    """Darf für diese Fassung überhaupt ein Nachweis archiviert werden? (#2035)

    Die Prüfung gehört **hierher** und nicht in den Endpunkt — das ist die Lehre
    aus #1760 („das stand bisher nur im Endpunkt") und aus #1780, wo
    ``signieren`` die Freigabe selbst verlangt. ``add_final`` prüfte bis v8.6.3
    **nichts**: kein ``freigabe_status``, keine Einreichung, keine
    Vier-Augen-Prüfung — der INSERT lief direkt.

    Warum das die Rollentrennung aus #1743 aushöhlte: Der Zustandsautomat blieb
    unversehrt, das **Artefakt**, das er schützen soll, entstand daneben. Ein
    Konto mit Rolle ``cra_editor`` konnte einen Vorgang einreichen, an der
    Freigabe scheitern (409 Vier-Augen) und anschließend über diesen Weg einen
    unveränderlichen, SHA-256-gesicherten Konformitätsnachweis mit sich selbst
    als Freigeber archivieren. Für einen Prüfer ist das archivierte PDF der
    Nachweis, nicht der Datenbankzustand des Vorgangs.

    ``confirm_rot`` bleibt davon unberührt: Eine rote Ampel bewusst zu
    überstimmen ist eine dokumentierte Entscheidung (#1611) und keine Umgehung.
    """
    from cra.konformitaet_db import get_konformitaet
    from shared.vier_augen import pruefe as _vier_augen

    rec = get_konformitaet(db_path, projekt_name, version) or {}
    if not rec:
        raise ValueError(
            "Für diese Fassung gibt es keinen Release-Vorgang — ein Nachweis "
            "ohne Vorgang wäre nicht zuordenbar")
    status = str(rec.get("freigabe_status") or "entwurf")
    if status not in ("freigegeben", "veroeffentlicht"):
        raise ValueError(
            f"Der Release-Vorgang steht auf '{status}' — ein Konformitätsnachweis "
            "wird erst nach der Freigabe archiviert (Vier-Augen, #1743)")
    # Zweite Hälfte: Der Archiveintrag trägt `freigegeben_von`. Ist das der
    # Einreicher, behauptet das Archiv eine Freigabe durch ihn, obwohl ein
    # anderer sie erteilt hat.
    _vier_augen(rec.get("erstellt_von"), freigegeben_von,
                erste_handlung="den Vorgang einreicht",
                zweite_handlung="den Nachweis archivieren",
                rechtsgrundlage="Art. 13 i.V.m. Anhang VIII (Konformitätsbewertung)")


def add_final(db_path: Path, projekt_name: str, *, version: str, pdf_bytes: bytes,
              ampel: str, freigegeben_von: str,
              vorbedingung_pruefen: bool = True) -> dict[str, Any]:
    """Nachweis archivieren. ``vorbedingung_pruefen=False`` nur für Altbestands-
    Werkzeuge und Tests, die den Vorgang selbst stellen (#2035)."""
    if vorbedingung_pruefen:
        _pruefe_vorbedingung(db_path, projekt_name, str(version or ""), freigegeben_von)
    ensure_table(db_path)
    STORE.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in f"{projekt_name}_{version or 'v'}")
    path = STORE / f"{safe}_{sha[:12]}.pdf"
    path.write_bytes(pdf_bytes)
    con = _sdb.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO cra_konformitaet_final (projekt_name, version, pdf_path, sha256, ampel, freigegeben_von) "
            "VALUES (?,?,?,?,?,?)",
            (projekt_name, version or "", str(path), sha, ampel, freigegeben_von))
        con.commit()
    finally:
        con.close()
    return {"version": version, "sha256": sha, "pdf_path": str(path), "ampel": ampel}


def list_final(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _sdb.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT id, version, sha256, ampel, freigegeben_von, freigegeben_am "
            "FROM cra_konformitaet_final WHERE projekt_name=? ORDER BY freigegeben_am DESC",
            (projekt_name,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_final(db_path: Path, projekt_name: str, final_id: int) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _sdb.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT * FROM cra_konformitaet_final WHERE id=? AND projekt_name=?",
            (int(final_id), projekt_name)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()
