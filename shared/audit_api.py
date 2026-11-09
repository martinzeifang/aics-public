"""Der Revisionspfad eines Projekts — je Modul angehängt (#1851).

Alle sechs Module schreiben seit Jahren über ``shared.audit.audit_event`` in
dieselbe append-only Tabelle (#1338); **ansehen** konnte man das nur in der
Risikobewertung und in der Administration. Der Anwender, der belegen muss, wer
eine Bewertung geändert hat, kommt an die Administration nicht heran — und
genau er wird gefragt.

WARUM UNTER DEM MODUL-PREFIX
Wörtlich die Lehre aus #1765/#1835: ``server/middleware/authz.py`` leitet Modul
und Aktion aus dem URL-Prefix ab. Ein eigener Prefix wäre kein Modul-Pfad —
jeder angemeldete Nutzer könnte den Revisionspfad fremder Mandanten lesen, und
die Firmen-ACL aus #1185 griffe nicht. Deshalb **muss** der Pfad-Parameter
``projekt_name`` heißen; die ACL löst die Firma über
``view_args['projekt_name']`` auf.

ZWEI QUELLEN, EINE ANSICHT
Der Revisionspfad sagt *wer wann welche Handlung ausgelöst hat*
(``risikobewertung.framework_changed``, ``cra.release.freigegeben``). Die
Risikobewertung führt zusätzlich ein **Änderungsprotokoll** auf Feldebene
(``rb_change_log``: vorher/nachher je Risiko). Das sind zwei verschiedene
Aussagen, und beide heißen für den Anwender „Audit-Log".

Die Ansicht zeigt deshalb beides, jeder Eintrag mit seiner ``quelle``. Die
Alternative wäre gewesen, RBs Protokoll durch den Revisionspfad zu ersetzen —
das hätte eine vorhandene Fähigkeit genommen, um Einheitlichkeit zu
behaupten. Zusammengeführt wird **hier**, nicht in der Maske: Sonst müsste die
geteilte Komponente wissen, welches Modul eine zweite Quelle hat, und wäre
keine geteilte mehr (dieselbe Überlegung wie bei ``ObjektArt`` in #1846).
"""
from __future__ import annotations

from typing import Any, Callable


# Eine Handlung, egal aus welcher Quelle. Die Maske liest nur diese Schlüssel.
QUELLEN = {
    "revisionspfad": "Revisionspfad",
    "aenderungen": "Änderungsprotokoll",
}


def _aus_revisionspfad(zeile: dict[str, Any]) -> dict[str, Any]:
    """``audit_events``-Zeile → Eintrag der Ansicht."""
    details = zeile.get("details") if isinstance(zeile.get("details"), dict) else {}
    objekt = ""
    objekt_id = ""
    for schluessel in ("object_kind", "art", "kind"):
        if details.get(schluessel):
            objekt = str(details[schluessel])
            break
    for schluessel in ("object_id", "objekt_id", "id", "risk_id", "doc_id"):
        if details.get(schluessel) is not None:
            objekt_id = str(details[schluessel])
            break
    return {
        "quelle": "revisionspfad",
        "zeit": str(zeile.get("ts") or ""),
        "aktion": str(zeile.get("action") or ""),
        "akteur": str(zeile.get("actor") or ""),
        "ergebnis": str(zeile.get("outcome") or ""),
        "objekt": objekt,
        "objekt_id": objekt_id,
        "details": details,
    }


def _rb_aenderungen(projekt_name: str, grenze: int = 500) -> list[dict[str, Any]]:
    """Das Änderungsprotokoll der Risikobewertung (``rb_change_log``).

    Best effort: Fehlt die Tabelle (frische Installation), bleibt die Quelle
    leer — der Revisionspfad steht dann allein, und das ist eine Aussage, keine
    Störung.
    """
    try:
        from contextlib import closing
        from pathlib import Path

        from shared import db as _sdb

        # Der logische Pfad (das Schema leitet der Kompat-Layer aus dem
        # Dateinamen ab). **Nicht** aus `risikobewertung.db` importiert: Dort
        # gibt es kein `DB_PATH`, und ein ImportError wäre hier vom `except`
        # geschluckt worden — das Änderungsprotokoll hätte stillschweigend nie
        # erschienen. Genau die Fehlerklasse, die dieser Umbau beseitigt.
        DB_PATH = Path("data/db/risikobewertung.sqlite")

        with closing(_sdb.connect(str(DB_PATH))) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=current_schema() AND table_name='rb_change_log'"
            )
            if not cur.fetchone():
                return []
            cur.execute(
                "SELECT created_at, action, object_kind, object_id, before_json, after_json "
                "FROM rb_change_log WHERE projekt_name=? ORDER BY created_at DESC LIMIT ?",
                (projekt_name, int(grenze)),
            )
            zeilen = [dict(r) for r in cur.fetchall()]
    except Exception:  # noqa: BLE001 — eine fehlende Nebenquelle darf die Ansicht nicht nehmen
        return []

    eintraege: list[dict[str, Any]] = []
    for z in zeilen:
        eintraege.append({
            "quelle": "aenderungen",
            "zeit": str(z.get("created_at") or ""),
            "aktion": str(z.get("action") or ""),
            # Das Feldprotokoll hält den Handelnden nicht fest — das zu
            # behaupten wäre schlimmer als die Lücke zu zeigen (#1784).
            "akteur": "",
            "ergebnis": "",
            "objekt": str(z.get("object_kind") or ""),
            "objekt_id": "" if z.get("object_id") is None else str(z.get("object_id")),
            "details": {},
        })
    return eintraege


# Module mit einer zweiten Quelle. Eine Liste und nicht ein Parameter je
# Aufrufer, damit die Registrierung in allen sechs Modulen gleich aussieht.
_ZUSATZQUELLEN: dict[str, Callable[[str], list[dict[str, Any]]]] = {
    "risikobewertung": _rb_aenderungen,
}


def projekt_revision(modul: str, projekt_name: str, *, limit: int = 200,
                     offset: int = 0) -> dict[str, Any]:
    """Revisionspfad **und** Änderungsprotokoll dieses Projekts, zusammengeführt.

    Sortiert nach Zeit, neueste zuerst. ``fenster_erschoepft`` reist mit: Der
    Revisionspfad wird nur über ein Fenster der neuesten Modul-Einträge
    durchgesehen (siehe ``shared.audit_db.projekt_ereignisse``), und eine
    Ansicht, die ihre Grenze verschweigt, behauptet Vollständigkeit.
    """
    from shared.audit_db import projekt_ereignisse

    # Beide Quellen vollständig holen und erst danach schneiden — ein
    # modul-weises LIMIT vor dem Zusammenführen würde die jüngeren Einträge der
    # einen Quelle gegen die älteren der anderen ausspielen.
    roh = projekt_ereignisse(modul, projekt_name, limit=1000, offset=0)
    eintraege = [_aus_revisionspfad(z) for z in roh.get("events", [])]

    zusatz = _ZUSATZQUELLEN.get(modul)
    if zusatz is not None:
        eintraege.extend(zusatz(projekt_name))

    eintraege.sort(key=lambda e: e.get("zeit") or "", reverse=True)
    gesamt = len(eintraege)
    limit = max(1, min(int(limit), 1000))
    offset = max(0, int(offset))
    return {
        "eintraege": eintraege[offset:offset + limit],
        "total": gesamt,
        "limit": limit,
        "offset": offset,
        "modul": modul,
        "projekt": projekt_name,
        "quellen": sorted({str(e.get("quelle")) for e in eintraege}),
        "fenster_erschoepft": bool(roh.get("fenster_erschoepft")),
    }


def register_routes(bp, modul: str) -> None:
    """Hängt ``GET /projekte/<projekt_name>/audit`` an ``bp``."""
    from flask import current_app, jsonify, request
    from flask_jwt_extended import jwt_required

    ep = f"audit_{modul}"

    def lesen(projekt_name: str):
        try:
            limit = int(request.args.get("limit", 200))
            offset = int(request.args.get("offset", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "limit/offset müssen Zahlen sein"}), 400
        try:
            return jsonify(projekt_revision(modul, projekt_name,
                                            limit=limit, offset=offset))
        except Exception as e:  # noqa: BLE001
            current_app.logger.exception("%s %s — %s", request.method,
                                         request.path, e)
            return jsonify({"error": "Interner Serverfehler"}), 500

    lesen.__name__ = f"{ep}_lesen"
    bp.add_url_rule("/projekte/<projekt_name>/audit", f"{ep}_lesen",
                    jwt_required()(lesen), methods=["GET"])


__all__ = ["QUELLEN", "projekt_revision", "register_routes"]
