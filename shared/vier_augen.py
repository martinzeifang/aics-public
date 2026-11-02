"""Vier-Augen-Prinzip: niemand leistet beide Unterschriften (#1780).

Die Trennung gehört an die **Handlung**, nicht an die Rechtevergabe. Wer beide
Rechte hält, ist der Normalfall in kleinen Häusern — unzulässig ist, dass
dieselbe Person beide Unterschriften unter **denselben Vorgang** setzt. Genau
das muss eine Eigenschaft der Anwendung sein und keine Absprache, denn der
Nachweis behauptet später, dass zwei Personen beteiligt waren.

WARUM DIESE DATEI
Die Regel stand dreimal im Code: in ``cra/konformitaet_db.freigeben`` (#1743),
in ``ai_act/aenderungen_db.freigeben`` (#1756) — und im DSGVO-Jahresbericht
(#1132) **gar nicht**: Dort konnte dieselbe Person als Geschäftsführung
freigeben und als Datenschutzbeauftragte:r signieren. Drei Kopien derselben
Aussage sind drei Gelegenheiten, dass eine fehlt; genau das ist passiert.

ZWEI ENTSCHEIDUNGEN
* **Verglichen wird die Benutzer-ID**, nicht der Anzeigename. Namen sind nicht
  eindeutig und ändern sich; ``get_jwt_identity()`` ist der stabile Schlüssel.
  Die Aufrufer übergeben deshalb die Identität, nicht die Anzeige.
* **Unbekannte erste Person lässt die zweite zu.** Ist die erste Unterschrift
  nicht zugeordnet (Altbestand vor Einführung der Felder), lässt sich nicht
  zeigen, dass es dieselbe Person ist — und eine Sperre, die niemand auflösen
  kann, würde Bestandsvorgänge dauerhaft blockieren. Das ist die eine Stelle,
  an der hier bewusst nicht fail-closed entschieden wird; sie ist durch die
  Spalten selbst begrenzt und verschwindet mit dem Altbestand.
"""

from __future__ import annotations


class VierAugenVerletzt(ValueError):
    """Dieselbe Person würde beide Unterschriften leisten.

    Erbt von ``ValueError``, weil die bestehenden Endpunkte Fachfehler bereits
    als ``409`` ausliefern — so greift die Prüfung ohne Umbau der REST-Schicht.
    """

    def __init__(self, meldung: str, *, erste: str = "", zweite: str = "",
                 erste_handlung: str = "", zweite_handlung: str = "") -> None:
        self.erste = erste
        self.zweite = zweite
        self.erste_handlung = erste_handlung
        self.zweite_handlung = zweite_handlung
        super().__init__(meldung)

    def as_dict(self) -> dict[str, str]:
        return {"error": str(self), "code": "vier_augen",
                "erste_handlung": self.erste_handlung,
                "zweite_handlung": self.zweite_handlung}


def _norm(person: object) -> str:
    return str(person or "").strip().lower()


def dieselbe_person(erste: object, zweite: object) -> bool:
    """Sind beide Unterschriften von derselben Person?

    ``False``, sobald eine Seite unbekannt ist — siehe Modul-Docstring.
    """
    a, b = _norm(erste), _norm(zweite)
    return bool(a) and a == b


def pruefe(erste: object, zweite: object, *, erste_handlung: str,
           zweite_handlung: str, rechtsgrundlage: str = "") -> None:
    """Wirft :class:`VierAugenVerletzt`, wenn beide Unterschriften zusammenfallen.

    ``erste_handlung``/``zweite_handlung`` sind Verben aus Sicht des Anwenders
    („einreicht"/„freigeben"), denn die Meldung soll sagen, was zu tun ist:
    eine zweite Person holen.
    """
    if not dieselbe_person(erste, zweite):
        return
    meldung = (f"Wer {erste_handlung}, darf nicht {zweite_handlung} — dafür "
               f"braucht es eine zweite Person (Vier-Augen-Prinzip)")
    if rechtsgrundlage:
        meldung += f". {rechtsgrundlage}"
    raise VierAugenVerletzt(meldung, erste=str(erste or ""), zweite=str(zweite or ""),
                            erste_handlung=erste_handlung,
                            zweite_handlung=zweite_handlung)
