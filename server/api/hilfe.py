"""Die Hilfe fragbar machen (#1878) — nur der Prompt, nicht der Lauf.

WARUM HIER KEIN EIGENER KI-ENDPUNKT STEHT
`/api/ai/run-stream` leistet bereits alles, was ein KI-Lauf hier braucht:
Verfügbarkeitsprüfung mit 409 statt eines leeren Streams, Egress-Bestätigung
samt Revisionseintrag (#1519/#1840), die eigenen Hinweise des Bearbeiters
(#1832) und das Budget nach Aufgabenart (#1841). Diesen Weg hier zu
wiederholen wäre der sechste eigene Transport — genau das, was #1841
beseitigt hat.

Darum liefert dieses Modul nur den **geerdeten Prompt**. Ausgeführt wird er
von derselben Maske über denselben Endpunkt wie jeder Assistenten-Prompt.

WARUM DER PROMPT SERVERSEITIG ENTSTEHT
Im Frontend zusammengebaut wäre er die zweite Zusammenbau-Stelle — und
auffallen würde das erst, wenn jemand eine Antwort nicht mehr erklären kann
(die Lehre aus #1834). Außerdem liegt das Handbuch im Image, nicht im Browser.
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

hilfe_bp = Blueprint("hilfe", __name__)


@hilfe_bp.post("/prompt")
@jwt_required()
def hilfe_prompt():
    """Baut den Hilfe-Prompt aus Frage, Handbuch, Hilfe-Abschnitt und Stand.

    Body::

        {"frage": "...", "modul": "cra", "bereich": "releases",
         "hilfe_text": "<Text des offenen Hilfe-Abschnitts>",
         "stand": {"Projekt": "...", "Tab": "..."}}

    Antwort: ``{prompt, fundstellen}``. ``fundstellen`` sind die
    Handbuch-Überschriften, die eingeflossen sind — die Oberfläche weist sie
    aus, damit die Grundlage der Antwort nachsehbar bleibt.
    """
    data = request.get_json(silent=True) or {}
    frage = str(data.get("frage") or "").strip()
    if not frage:
        return {"error": 'Feld "frage" ist Pflicht'}, 400
    try:
        from shared.hilfe import baue_prompt

        stand = data.get("stand")
        prompt, fundstellen = baue_prompt(
            frage,
            modul=str(data.get("modul") or ""),
            bereich=str(data.get("bereich") or ""),
            hilfe_text=str(data.get("hilfe_text") or ""),
            stand=stand if isinstance(stand, dict) else None,
        )
        return jsonify({"prompt": prompt, "fundstellen": fundstellen})
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                     type(e).__name__, e)
        return {"error": "Interner Serverfehler"}, 500


@hilfe_bp.get("/handbuch/<modul>")
@jwt_required()
def hilfe_handbuch(modul: str):
    """Die Abschnitts-Überschriften der Modul-Doku.

    Damit die Oberfläche sagen kann, worauf sich eine Antwort überhaupt
    stützen *kann* — und ob das Handbuch im Image überhaupt vorliegt. Ohne
    diese Auskunft sähe eine Installation ohne Doku genauso aus wie eine mit.
    """
    try:
        from shared.hilfe import ALLGEMEIN_DATEI, MODUL_DATEI, _lies, handbuch

        teile = handbuch(modul)
        datei = MODUL_DATEI.get(str(modul or "").strip().lower())
        return jsonify({
            "modul": modul,
            # `vorhanden`: gibt es überhaupt Material? Die allgemeine
            # Bedienanleitung zählt mit, denn aus ihr lässt sich antworten.
            "vorhanden": bool(teile),
            # `modul_doku`: gibt es die Doku DIESES Moduls? Ohne diese
            # Unterscheidung sähe ein Modul ohne eigenes Handbuch genauso aus
            # wie eines mit.
            "modul_doku": bool(datei and _lies(datei)),
            "allgemein": bool(_lies(ALLGEMEIN_DATEI)),
            "abschnitte": [t for t, _ in teile if t],
        })
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("%s %s — %s: %s", request.method, request.path,
                                     type(e).__name__, e)
        return {"error": "Interner Serverfehler"}, 500
