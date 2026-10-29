"""REST-Zugang zu den gespeicherten Prompt-Hinweisen (#1835) — je Modul angehängt.

WARUM UNTER DEM MODUL-PREFIX UND NICHT ALS EIGENER BLUEPRINT
Wörtlich die Lehre aus #1765: ``server/middleware/authz.py`` leitet Modul und
Aktion aus dem URL-Prefix ab. Ein eigener Prefix wäre kein Modul-Pfad — jeder
angemeldete Nutzer könnte die Hinweise fremder Mandanten lesen und setzen, und
das Objekt-RBAC aus #1185 (``allowed_firmen``) griffe ebenfalls nicht.

Unter dem Modul-Prefix greift beides ohne eine Zeile Zusatzcode: Lesen
verlangt ``<modul>:read``, Schreiben ``<modul>:write``, und die Firmen-ACL
löst die Firma über ``view_args['projekt_name']`` auf. Deshalb **muss** der
Pfad-Parameter ``projekt_name`` heißen.

Ein eigenes Recht „darf Hinweise setzen" wäre die naheliegende Ergänzung — es
wäre aber ``<modul>:write`` in Grün: Wer bewerten darf, darf ohnehin
schreiben, und wer nur lesen darf, kommt an den ``PUT`` nicht heran.

Muster: ``shared/ki_herkunft_api.register_routes`` (#1765),
``shared/req_risks.register_routes`` (#1564).
"""
from __future__ import annotations

from shared import prompt_hinweise


def register_routes(bp, modul: str) -> None:
    """Hängt ``/projekte/<projekt_name>/prompt-hinweise…`` an ``bp``."""
    from flask import jsonify, request
    from flask_jwt_extended import get_jwt_identity, jwt_required

    ep = f"prompt_hinweise_{modul}"

    def _wrap(fn):
        def inner(*a, **kw):
            try:
                return fn(*a, **kw)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:  # noqa: BLE001
                from flask import current_app
                current_app.logger.exception("%s %s — %s", request.method,
                                             request.path, e)
                return jsonify({"error": "Interner Serverfehler"}), 500
        inner.__name__ = f"{ep}_{fn.__name__}"
        return jwt_required()(inner)

    def lesen(projekt_name: str):
        """Aufgelöster Vorbelegungstext **und** die Einzeleinträge.

        Der aufgelöste Text ist das, was das Feld füllt; die Einzeleinträge
        braucht die Verwaltung („welcher Hinweis gilt wofür, von wem").
        Beides in einem Abruf, damit die Maske nicht zweimal fragt.
        """
        bereich = str(request.args.get("bereich") or "")
        if bereich and bereich not in prompt_hinweise.BEREICHE:
            raise ValueError(f'Unbekannter Bereich "{bereich}"')
        auf = prompt_hinweise.aufgeloest(modul, projekt_name, bereich=bereich)
        return jsonify({**auf, "modul": modul,
                        "eintraege": prompt_hinweise.liste(modul, projekt_name),
                        "bereiche": list(prompt_hinweise.BEREICHE)})

    def setzen(projekt_name: str):
        """Hinweis für dieses Projekt merken. Leerer Text löscht ihn."""
        body = request.get_json(silent=True) or {}
        bereich = str(body.get("bereich") or "")
        ident = str(get_jwt_identity() or "")
        eintrag = prompt_hinweise.setze(modul, projekt_name, body.get("text"),
                                        bereich=bereich, von=ident)
        _audit(modul, projekt_name, bereich, ident, bool(eintrag.get("text")))
        return jsonify({"ok": True, "eintrag": eintrag,
                        **prompt_hinweise.aufgeloest(modul, projekt_name,
                                                     bereich=bereich)})

    def loeschen(projekt_name: str, bereich: str):
        if bereich == "alle":
            bereich = ""
        if bereich and bereich not in prompt_hinweise.BEREICHE:
            raise ValueError(f'Unbekannter Bereich "{bereich}"')
        prompt_hinweise.loesche(modul, projekt_name, bereich=bereich)
        ident = str(get_jwt_identity() or "")
        _audit(modul, projekt_name, bereich, ident, False)
        return jsonify({"ok": True,
                        **prompt_hinweise.aufgeloest(modul, projekt_name,
                                                     bereich=bereich)})

    basis = "/projekte/<projekt_name>/prompt-hinweise"
    bp.add_url_rule(basis, f"{ep}_lesen", _wrap(lesen), methods=["GET"])
    bp.add_url_rule(basis, f"{ep}_setzen", _wrap(setzen), methods=["PUT"])
    bp.add_url_rule(f"{basis}/<bereich>", f"{ep}_loeschen", _wrap(loeschen),
                    methods=["DELETE"])


def _audit(modul: str, projekt: str, bereich: str, ident: str, gesetzt: bool) -> None:
    """Wer hat die Vorbelegung gesetzt oder entfernt.

    Ein gespeicherter Hinweis steuert künftig jeden KI-Lauf dieses Projekts,
    auch die von Kollegen. ``user_id`` muss mit, sonst steht im Revisionspfad
    „irgendwer hat gehandelt" (#1784).
    """
    try:
        from shared.audit import audit_event
        audit_event("ai.prompt.hinweis", module=modul, details={
            "user_id": ident,
            "projekt": str(projekt)[:120],
            "bereich": bereich,
            "gesetzt": gesetzt,
        })
    except Exception:  # noqa: BLE001
        pass


__all__ = ["register_routes"]
