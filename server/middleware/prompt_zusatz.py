"""Eigene Hinweise in den Copy/Paste-Prompt einsetzen (#1833).

Die Suite hat 60 Routen, die einen KI-Prompt zum Kopieren ausliefern — in neun
Modulen, von ``/anforderungen/<id>/prompt`` bis zu den ~45 Assistenten. Alle
antworten mit JSON, das ein Feld ``prompt`` trägt. Dieser Einsetzer hängt den
Hinweis des Bearbeiters dort an, wenn der Request einen mitgebracht hat.

WARUM HIER UND NICHT IN DEN ROUTEN
Jede Route einzeln um einen Parameter zu erweitern wäre die Spiegel-Liste aus
#1731/#1735: 60 Fundstellen, und bei der 61. fehlt sie, ohne dass etwas
fehlschlägt — es fehlt bloß die Möglichkeit, und niemand sucht nach etwas, das
er nicht kennt. Eine Verdrahtung am Request-Rand gilt auch für Routen, die noch
niemand geschrieben hat. Muster sind die übrigen querschnittlichen Riegel:
``server/middleware/authz.py``, ``firma_acl.py``,
``shared/tenancy.scope_current_request``.

Das Gegenstück für den API-Weg steht in ``shared/sse.stream_ai_sse`` — dort
laufen alle serverseitigen Streams zusammen, einschließlich
``/api/ai/run-stream``.
"""
from __future__ import annotations

import json

from shared import prompt_zusatz as pz


#: Schlüssel, unter denen ein Eintrag in einer ``prompts``-Liste seinen Text
#: führt. Zwei, weil die beiden Mehrfach-Routen sich nie abgestimmt haben:
#: ``/fragen/prompt`` im Compliance-Audit nennt ihn ``content``,
#: ``/risiken/mass-assess-prompt`` in der Risikobewertung ``prompt``.
_LISTEN_SCHLUESSEL = ("prompt", "content")


def _einsetzen(daten: dict, zusatz: str) -> bool:
    """Setzt den Hinweis in eine JSON-Antwort ein. Liefert, ob etwas geschah.

    Zwei Antwortformen, weil es zwei gibt: ein einzelnes ``prompt`` (58 Routen)
    und eine ``prompts``-**Liste** (2 Routen — Fragebogen je Framework und
    Risiko-Massenbewertung). Die Liste wurde beim ersten Anlauf übersehen; sie
    ist genau die Art Ausnahme, die später als „wirkt dort halt nicht" auffällt
    und niemand mehr zuordnen kann.
    """
    from shared import prompt_zusatz as pz

    getroffen = False
    basis = daten.get("prompt")
    if isinstance(basis, str) and basis.strip():
        daten["prompt"] = pz.komponiere(basis, zusatz)
        getroffen = True

    liste = daten.get("prompts")
    if isinstance(liste, list):
        for eintrag in liste:
            if not isinstance(eintrag, dict):
                continue
            for schluessel in _LISTEN_SCHLUESSEL:
                wert = eintrag.get(schluessel)
                if isinstance(wert, str) and wert.strip():
                    eintrag[schluessel] = pz.komponiere(wert, zusatz)
                    getroffen = True
                    break
    return getroffen


def register_prompt_zusatz(app) -> None:
    """Hängt den Einsetzer an die App.

    Er greift nur, wenn **alle** Bedingungen zutreffen: Der Request brachte
    einen Hinweis mit, die Antwort ist JSON mit Status 200 und trägt einen
    nichtleeren Prompt. Damit bleibt jede andere Antwort unberührt — auch
    solche, die zufällig ``prompt`` heißen, denn ohne Hinweis passiert nichts.
    """

    @app.after_request
    def eigene_hinweise_einsetzen(response):  # noqa: ANN001 — Flask-Hook
        try:
            zusatz = pz.aus_request()
            if not zusatz:
                return response
            # Streams (SSE) und Dateien gar nicht anfassen: ``get_data`` auf
            # einer durchgereichten Antwort wirft.
            if response.direct_passthrough or response.status_code != 200:
                return response
            if (response.mimetype or "") != "application/json":
                return response
            daten = response.get_json(silent=True)
            if not isinstance(daten, dict):
                return response
            if not _einsetzen(daten, zusatz):
                return response
            response.set_data(json.dumps(daten, ensure_ascii=False, default=str))
            response.headers["Content-Length"] = str(len(response.get_data()))
        except Exception:  # noqa: BLE001 — ein Hinweis darf keine Antwort zerreißen
            try:
                app.logger.warning("Prompt-Zusatz (#1833) konnte nicht eingesetzt "
                                   "werden", exc_info=True)
            except Exception:  # noqa: BLE001
                pass
        return response
