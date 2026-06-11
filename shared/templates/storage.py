"""Template-Storage: Upload, Versionierung, SHA-256, Soft-Delete (#989)."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any, BinaryIO

from shared.fs_perms import ensure_private_dir, ensure_private_file
from shared.upload_validation import validate_upload_file
from shared.templates import db as _db
from shared.templates.engine import extract_variables

STORAGE_ROOT = Path("data/templates")
DEFAULT_DB_PATH = _db.DEFAULT_DB_PATH


def _safe_name(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "vorlage").strip()).strip("_")
    return base or "vorlage"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_template(src_path: Path, *, modul: str, name: str, db_path: Path = DEFAULT_DB_PATH,
                    hochgeladen_von: str = "", notizen: str = "",
                    storage_root: Path = STORAGE_ROOT) -> dict[str, Any]:
    """Validiert + speichert eine DOCX-Vorlage und legt eine Registry-Zeile an.

    Re-Upload gleicher (modul, name) → neue Version, alte bleibt erhalten.
    """
    src_path = Path(src_path)
    # Magic-Bytes / Zip-Bomb-Schutz (DOCX = ZIP-Office-Format)
    validate_upload_file(src_path, suffix=".docx")

    _db.ensure_db(db_path)
    con = _db._connect(db_path)
    try:
        version = _db.next_version(con, modul, name)
    finally:
        con.close()

    mod_dir = Path(storage_root) / modul
    ensure_private_dir(mod_dir)
    # vorläufiger Insert, um die id für den Dateinamen zu erhalten
    variablen = extract_variables(src_path)
    tmp_target = mod_dir / f"_pending__{_safe_name(name)}__v{version}.docx"
    shutil.copyfile(src_path, tmp_target)
    sha = _sha256(tmp_target)

    tid = _db.insert_template(
        db_path, modul=modul, name=name, version=version,
        datei_pfad=str(tmp_target), datei_sha256=sha,
        variablen_json=json.dumps(variablen, ensure_ascii=False),
        hochgeladen_von=hochgeladen_von, notizen=notizen,
    )
    final = mod_dir / f"{tid}__{_safe_name(name)}.docx"
    tmp_target.rename(final)
    ensure_private_file(final)
    con = _db._connect(db_path)
    try:
        con.execute("UPDATE template_registry SET datei_pfad=? WHERE id=?", (str(final), tid))
        con.commit()
    finally:
        con.close()
    rec = _db.get_template(db_path, tid)
    assert rec is not None
    return rec


def list_templates(db_path: Path = DEFAULT_DB_PATH, modul: str | None = None,
                   include_inactive: bool = False) -> list[dict[str, Any]]:
    return _db.list_templates(db_path, modul, include_inactive)


def get_template(db_path: Path = DEFAULT_DB_PATH, template_id: int = 0) -> dict[str, Any] | None:
    return _db.get_template(db_path, template_id)


def set_default(db_path: Path, template_id: int) -> None:
    _db.set_default(db_path, template_id)


def set_mapping(db_path: Path, template_id: int, mapping: dict[str, Any]) -> None:
    _db.set_mapping(db_path, template_id, json.dumps(mapping, ensure_ascii=False))


def soft_delete(db_path: Path, template_id: int, *, by: str = "", reason: str = "") -> None:
    """Markiert aktiv=0 + deleted_* und löscht die Datei (Zeile bleibt)."""
    rec = _db.get_template(db_path, template_id)
    _db.soft_delete(db_path, template_id, by=by, reason=reason)
    if rec and rec.get("datei_pfad"):
        try:
            Path(rec["datei_pfad"]).unlink()
        except OSError:
            pass
