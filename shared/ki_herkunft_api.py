"""REST-Zugang zum KI-Herkunfts-Register (#1765) — je Modul angehängt.

Die Kennzeichnung steht seit v8.0.0 nicht mehr im gespeicherten Text, sondern
in ``shared/ki_herkunft``. Damit braucht die Oberfläche zwei Dinge: die
Herkunft **lesen** (um „KI-Entwurf, ungeprüft" anzuzeigen) und die fachliche
Prüfung **festhalten**. Beides steht hier.

WARUM NICHT EIN EIGENER BLUEPRINT
``/api/ki-herkunft/<modul>/…`` wäre für den zentralen Guard
(``server/middleware/authz.py``) kein Modul-Pfad: Er leitet Modul und Aktion
aus dem URL-Prefix ab. Ein eigener Prefix hätte die Prüfung umgangen — jeder
angemeldete Nutzer hätte fremde Bewertungen als „fachlich geprüft" ausweisen
können, und das Objekt-RBAC aus #1185 (``allowed_firmen``) hätte ebenfalls
nicht gegriffen.

Unter dem Modul-Prefix greift beides ohne eine Zeile Zusatzcode: Lesen
verlangt ``<modul>:read``, die Prüfung ``<modul>:write``, und die Firmen-ACL
löst die Firma über ``view_args['projekt_name']`` auf. Deshalb **muss** der
Pfad-Parameter ``projekt_name`` heißen.

Muster ist ``shared/req_risks.register_routes`` (#1564).
"""
from __future__ import annotations

from typing import Any

from shared import ki_herkunft

#: Objektarten, die es gibt. Die Liste ist bewusst eng: Sie beschreibt, wo in
#: der Suite KI-Bewertungen gespeichert und später gedruckt werden.
ARTEN = (
    'requirement',    # Anforderungen CRA/NIS2/AI-Act/DSGVO
    'owasp',          # OWASP-Proactive-Controls (CRA)
    'owasp_llm',      # OWASP-LLM-Register (AI Act)
    'wiba_control',   # WiBA-Prüffragen
    'risk',           # Risiken der Risikobewertung
    'tom',            # DSGVO-TOM-Maßnahmen
    'audit_question', # Compliance-Audit-Fragen
    # #1773: Bewertung einer Fremdkomponente nach Art. 13 Abs. 5. Sie kommt
    # anders zustande als die übrigen — der Entwurf entsteht für eine **Gruppe**
    # gleichartiger Komponenten und wird von einem Menschen für die Gruppe
    # übernommen (``ki_herkunft.vermerken_viele``). Die Objekt-ID ist die
    # Zeilen-ID aus ``cra_sbom_komponenten``.
    'sbom_komponente',
)


def register_routes(bp, modul: str) -> None:
    """Hängt ``/projekte/<projekt_name>/ki-herkunft…`` an ``bp``."""
    from flask import jsonify, request
    from flask_jwt_extended import jwt_required, get_jwt_identity

    ep = f"ki_herkunft_{modul}"

    def _wrap(fn):
        def inner(*a, **kw):
            try:
                return fn(*a, **kw)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:  # noqa: BLE001
                from flask import current_app
                current_app.logger.exception("%s %s — %s", request.method, request.path, e)
                return jsonify({"error": "Interner Serverfehler"}), 500
        inner.__name__ = f"{ep}_{fn.__name__}"
        return jwt_required()(inner)

    def uebersicht(projekt_name: str):
        """Herkunft aller Objekte eines Projekts — **ein** Abruf.

        Die Oberfläche zeigt Listen; je Zeile zu fragen wären bei 32
        CRA-Anforderungen 32 Abfragen. Das Projekt wird hier nicht auf
        Existenz geprüft: Ein unbekannter Name liefert eine leere Karte, und
        eine Projekt-Prüfung bräuchte eine sechste Kopie der
        Modul→Tabelle-Spiegelliste (die Fehlerklasse aus #1731/#1735).
        """
        art = str(request.args.get("art") or "").strip()
        if art and art not in ARTEN:
            raise ValueError(f'Unbekannte Objektart "{art}"')
        items = ki_herkunft.fuer_projekt(modul, projekt_name, art)
        return jsonify({"items": items, "art": art, "modul": modul})

    def geprueft(projekt_name: str, art: str, objekt_id: str):
        """Fachliche Prüfung festhalten.

        Ohne Eintrag gibt es nichts zu prüfen — dann ist der Inhalt nicht
        KI-erzeugt, und eine Prüfung zu quittieren würde eine Aussage über
        etwas treffen, das das Register nicht kennt.
        """
        if art not in ARTEN:
            raise ValueError(f'Unbekannte Objektart "{art}"')
        vorher = ki_herkunft.status(modul, projekt_name, art, str(objekt_id))
        if not vorher.get("ki"):
            return jsonify({"error": "Für dieses Objekt ist keine KI-Erzeugung "
                                     "vermerkt — es gibt nichts zu prüfen."}), 404
        ident = str(get_jwt_identity() or "").strip()
        st = ki_herkunft.pruefen(modul, projekt_name, art, str(objekt_id),
                                 von=_person(ident))
        _audit(modul, projekt_name, art, objekt_id, ident)
        return jsonify({"ok": True, "status": st})

    base = "/projekte/<projekt_name>/ki-herkunft"
    bp.add_url_rule(base, f"{ep}_uebersicht", _wrap(uebersicht), methods=["GET"])
    bp.add_url_rule(f"{base}/<art>/<objekt_id>/geprueft", f"{ep}_geprueft",
                    _wrap(geprueft), methods=["POST"])


def _person(ident: str) -> str:
    """Aus der JWT-Identität eine **lesbare Person** machen.

    ``get_jwt_identity()`` liefert die Benutzer-ID (``user-001``). In einem
    Prüfvermerk ist das wertlos: Das Feld beantwortet die Frage „wer hat das
    bestätigt?", und eine interne ID beantwortet sie nicht. Im Audit-Trail
    bleibt die ID — dort ist sie der stabile Schlüssel.

    Fällt die Auflösung aus, steht die ID da. Das ist besser als „unbekannt":
    Sie lässt sich nachschlagen.
    """
    ident = str(ident or "").strip()
    if not ident:
        return "unbekannt"
    try:
        from server.auth.users_db import get_user_by_id

        u = get_user_by_id(ident) or {}
        return str(u.get("name") or u.get("email") or ident).strip() or ident
    except Exception:  # noqa: BLE001
        return ident


def _audit(modul: str, projekt: str, art: str, objekt_id: Any, actor: str) -> None:
    """Die Prüfung gehört in den Revisionspfad.

    Sie ist die Aussage eines Menschen, dass eine maschinell erzeugte
    Bewertung fachlich trägt — genau die Art Aussage, die später jemand
    nachvollziehen will.
    """
    try:
        from shared.audit import audit_event
        audit_event("ai.assessment.reviewed", module=modul,
                    details={"projekt": projekt, "objekt_art": art,
                             "objekt_id": str(objekt_id), "actor": actor})
    except Exception:  # noqa: BLE001
        pass
