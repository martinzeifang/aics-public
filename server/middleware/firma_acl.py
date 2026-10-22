"""Objektbezogene Zugriffskontrolle auf Firmen-Ebene (#1185).

Ergänzt die modulweite Autorisierung (``authz.py``) um eine Firmen-Whitelist je Nutzer:
der JWT-Claim ``allowed_firmen`` (Liste von ``firmen_id`` oder ``None`` = alle Firmen,
Admins immer ``None``) wird gegen die Firma des angefragten Objekts geprüft.

Best-effort & fail-open: kann aus der Anfrage keine firmen_id abgeleitet werden, wird der
Zugriff NICHT blockiert (kein Bruch bestehender Routen). Greift nur, wenn der Nutzer eine
explizite Whitelist hat UND die Objekt-Firma eindeutig auflösbar ist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared import db as _sdb
from shared.firmen_link import MODULE_PROJECT_TABLES

_DB_DIR = Path("data/db")
_FIRMEN_DB = _DB_DIR / "firmen.sqlite"

# authz-Modulschlüssel → SQLite-Dateiname (für die Projekt-Tabellen-Auflösung).
_MODULE_DBFILE: dict[str, str] = {
    "cra": "cra.sqlite",
    "dsgvo": "dsgvo.sqlite",
    "nis2": "nis2.sqlite",
    "aiact": "ai_act.sqlite",
    "ai_act": "ai_act.sqlite",
    "wiba": "wiba.sqlite",
    "risikobewertung": "risikobewertung.sqlite",
    "soc": "soc.sqlite",
}


def firma_id_by_name(name: str) -> int | None:
    if not name:
        return None
    try:
        with _sdb.connect(str(_FIRMEN_DB)) as con:
            row = con.execute(
                "SELECT id FROM firmen WHERE name=? AND COALESCE(is_deleted,0)=0",
                (name,),
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else None
    except Exception:  # noqa: BLE001 — fail-open
        return None


def project_firmen_id(module: str, projekt_name: str) -> int | None:
    """firmen_id eines Modul-Projekts über dessen Projektnamen auflösen (#1071-FK)."""
    fname = _MODULE_DBFILE.get((module or "").lower())
    if not fname or not projekt_name:
        return None
    table, _name_col = MODULE_PROJECT_TABLES.get(fname, (None, None))
    if not table:
        return None
    try:
        with _sdb.connect(str(_DB_DIR / fname)) as con:
            row = con.execute(
                f"SELECT firmen_id FROM {table} WHERE name=? LIMIT 1", (projekt_name,)
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else None
    except Exception:  # noqa: BLE001 — fail-open (z. B. Tabelle ohne firmen_id-Spalte)
        return None


def request_firmen_id(module: str, view_args: dict[str, Any]) -> int | None:
    """Beste-Schätzung der angefragten Objekt-Firma aus den URL-Parametern."""
    view_args = view_args or {}
    # 1. Direkte firmen_id im Pfad (z. B. /api/risk-cockpit/<firmen_id>)
    for k in ("firmen_id", "firma_id"):
        if view_args.get(k) is not None:
            try:
                return int(view_args[k])
            except (TypeError, ValueError):
                pass
    # 2. Firma per Name (z. B. /api/firmen/<firma_name>)
    fname = view_args.get("firma_name") or view_args.get("firma")
    if fname:
        return firma_id_by_name(str(fname))
    # 3. Projekt per Name (z. B. /api/<modul>/projekte/<projekt_name>/…)
    pname = view_args.get("projekt_name") or view_args.get("projekt")
    if pname:
        return project_firmen_id(module, str(pname))
    return None


def access_denied_for_firma(claims: dict[str, Any], module: str, view_args: dict[str, Any]) -> bool:
    """True, wenn der Nutzer eine Firmen-Whitelist hat und die Objekt-Firma NICHT enthalten ist."""
    allowed = claims.get("allowed_firmen")
    if not isinstance(allowed, list):  # None = alle Firmen (z. B. Admin)
        return False
    fid = request_firmen_id(module, view_args)
    if fid is None:
        return False  # nicht auflösbar → fail-open
    return fid not in allowed


def filter_allowed_firmen_ids(claims: dict[str, Any], ids: list[int]) -> list[int]:
    """Filtert eine Liste von firmen_id auf die für den Nutzer freigegebenen (#1185 Listen)."""
    allowed = claims.get("allowed_firmen")
    if not isinstance(allowed, list):
        return ids
    allowset = {int(x) for x in allowed}
    return [i for i in ids if int(i) in allowset]
