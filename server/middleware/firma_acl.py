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
#
# **Abgeleitet** aus ``MODULE_PROJECT_TABLES``, nicht von Hand geführt (#2031).
# Bis v8.6.3 stand hier eine zweite, handgepflegte Liste über dieselben
# Zeichenketten — die Fehlerklasse aus #1731/#1735, hier mit dem teuersten
# Ausgang: Fehlt ein Eintrag, liefert ``project_firmen_id`` ``None``, und
# ``access_denied_for_firma`` fällt **fail-open** durch. Genau so waren
# ``firmen``, ``compliance_audit`` und ``gutachten`` ungeschützt, obwohl ihre
# ``firmen_id`` in ``MODULE_PROJECT_TABLES`` längst auflösbar war.
#
# Der Dateistamm **ist** der Modulschlüssel; nur echte Abweichungen stehen
# unten als Alias. ``tests/test_mandantentrennung_2030.py`` hält beide Seiten
# gegeneinander und wird rot, wenn ein Modul unversorgt bleibt.
_MODULE_ALIASES: dict[str, str] = {
    # authz-Schlüssel ohne Unterstrich (#1169-Geschwisterregel).
    "aiact": "ai_act.sqlite",
    # Eigenes Modul seit v7.4.0, Tabellenname historisch (#1713).
    "compliance_audit": "gutachten.sqlite",
}

_MODULE_DBFILE: dict[str, str] = {
    **{Path(_f).stem: _f for _f in MODULE_PROJECT_TABLES},
    **_MODULE_ALIASES,
}

# Module, deren Projekt-Parameter einen **Firmennamen** trägt, kein Projekt
# (#2031): Das Berichts-Center registriert ``firmen`` mit
# ``project_scoped=True`` (``shared/reports/api.py``), und der Wert von
# ``<projekt>`` ist dort der Firmenname. Ohne diese Unterscheidung lief
# ``GET /api/firmen/projekte/<fremde Firma>/berichte/gesamt`` in die
# Projekt-Auflösung, fand nichts und wurde durchgelassen.
_FIRMA_IM_PROJEKT_PARAM: frozenset[str] = frozenset({"firmen"})


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
    """firmen_id eines Modul-Projekts über dessen Projektnamen auflösen (#1071-FK).

    Die Abfrage selbst steht in ``shared/firmen_link`` — dort liegt die Zuordnung
    Modul → Projekt-Tabelle, und seit #1778 braucht sie ein zweiter Aufrufer
    (Vorlagen-Auflösung). Hier bleibt nur die Übersetzung Modulschlüssel →
    Datenbankdatei.
    """
    fname = _MODULE_DBFILE.get((module or "").lower())
    if not fname or not projekt_name:
        return None
    from shared.firmen_link import projekt_firmen_id
    return projekt_firmen_id(_DB_DIR / fname, projekt_name)


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
    #    ``project_name`` ist die englische Schreibweise im Compliance-Audit
    #    (alle 35 Routen) — sie wurde in keinem Schritt gelesen (#2031), womit
    #    jede Detailroute des Moduls fail-open war.
    pname = (view_args.get("projekt_name") or view_args.get("projekt")
             or view_args.get("project_name"))
    if pname:
        if (module or "").lower() in _FIRMA_IM_PROJEKT_PARAM:
            return firma_id_by_name(str(pname))
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
